"""Judge chain: every AI judgment in the product flows through here.

Layers, in order:
  1. TypeSafe Jev direct API  (primary — verified live, jev-1.13.0)
  2. OpenCode CLI running free Jev (`opencode run -m opencode/jev-1.13-free`)
  3. Local heuristics (last resort — never auto-punishes; flags for review)

Policy: Jev returns typed verdicts; CODE owns thresholds and actions.
Circuit breaker: consecutive failures open the breaker, a probe auto-recovers.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

JEV_URL = "https://api.typesafe.ai/v1/systemone"


@dataclass
class JudgeResult:
    """Verdicts from one screening call plus bookkeeping."""
    verdicts: dict = field(default_factory=dict)
    layer: str = "heuristic"
    model: str | None = None
    ok: bool = True
    error: str | None = None
    input_tokens: int = 0
    latency_ms: int = 0
    degraded_reason: str | None = None

    @property
    def max_prob(self) -> float:
        """Highest Noul probability across rule verdicts (0 if none)."""
        best = 0.0
        for v in self.verdicts.values():
            if isinstance(v, dict) and v.get("type") == "noul":
                best = max(best, float(v.get("noul", 0.0)))
        return best


class JevBackend:
    """Calls the TypeSafe HTTP API."""

    def __init__(self, api_key: str, model: str = "jev-latest", timeout: float = 30.0,
                 ua: str | None = None):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        # The API's edge blocks default Python UAs; a normal browser UA is required.
        self.ua = ua or ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

    def ask(self, state: str | dict, questions: dict) -> tuple[dict | None, str | None]:
        """Returns (response, error)."""
        if not self.api_key:
            return None, "no TYPESAFE_API_KEY configured"
        body = json.dumps({"state": state, "model": self.model,
                           "questions": questions}).encode()
        req = urllib.request.Request(JEV_URL, data=body, method="POST")
        req.add_header("Authorization", "Bearer " + self.api_key)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", self.ua)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode()), None
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            return None, f"HTTP {e.code}: {detail}"
        except Exception as e:  # noqa: BLE001 - network class
            return None, f"{type(e).__name__}: {e}"


class OpenCodeBackend:
    """Shells out to the OpenCode CLI running the free Jev model id.

    NOTE (2026-09-20): the free tier only answers from inside OpenCode and may
    be data-collecting during its free period. Failures fall through to the
    heuristic layer, never to punishment. A failing backend is put on
    cooldown so it cannot slow down every message with a 90s retry.
    """

    FAIL_COOLDOWN = 600.0  # seconds to skip a known-broken CLI

    def __init__(self, model: str = "opencode/jev-1.13-free", timeout: float = 90.0):
        self.model = model
        self.timeout = timeout
        self._failed_at: float | None = None

    def available(self) -> bool:
        if self._failed_at and (time.time() - self._failed_at) < self.FAIL_COOLDOWN:
            return False
        try:
            subprocess.run(["opencode", "--version"], capture_output=True, timeout=10)
            return True
        except Exception:
            self._failed_at = time.time()
            return False

    def ask(self, prompt: str) -> tuple[dict | None, str | None]:
        try:
            proc = subprocess.run(
                ["opencode", "run", "-m", self.model, prompt],
                capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError:
            self._failed_at = time.time()
            return None, "opencode CLI not installed"
        except subprocess.TimeoutExpired:
            self._failed_at = time.time()
            return None, "opencode timed out"
        except Exception as e:  # noqa: BLE001
            self._failed_at = time.time()
            return None, f"{type(e).__name__}: {e}"
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 or not out:
            self._failed_at = time.time()
            return None, f"opencode rc={proc.returncode}"
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0)), None
            except json.JSONDecodeError:
                pass
        return {"text": out[-1500:]}, None


# ---- heuristics (last resort; conservative) -------------------------
# Threat patterns require TARGETING intent — bare "kill" is normal gaming
# vocabulary ("team-kill", "the kill was clean") and must NOT flag.
_SEVERE_PATTERNS = [
    (r"\b(kys|kill\s+your\s?self)\b", "self-harm encouragement"),
    (r"\b(i'?ll?|we'?ll?|gonna|going to)\s+kill\s+(you|u|him|her|them|everyone)\b",
     "threat-like language"),
    (r"\b(kill|murder)\s+(you|u)\b", "threat-like language"),
    (r"\b(nigg|fagg|retard)\w*", "slur-like token"),
    (r"\b(dox|doxx?ing)\b", "doxxing reference"),
]

def heuristic_verdicts(state: dict, rule_ids: list[str]) -> dict:
    """Conservative local screen. Only ever raises REVIEW flags, never actions."""
    text = str(state.get("message", {}).get("content", ""))
    hits = []
    for pat, label in _SEVERE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            hits.append(label)
    out: dict = {"_heuristic": {"hits": hits, "flagged": bool(hits)}}
    for rid in rule_ids:
        out[rid] = {"type": "noul", "noul": 0.9 if hits else 0.05}
    return out


class JudgeChain:
    """The one interface every caller uses.

    ask_message()       -> rule verdicts for one chat message (batched questions)
    ask_report_reason() -> validity + recommended action for a member report

    Both return JudgeResult and record accounting in the Database (optional).
    """

    def __init__(self, cfg, db=None, *, jev: JevBackend | None = None,
                 opencode: OpenCodeBackend | None = None,
                 breaker_threshold: int = 5, breaker_cooldown: float = 120.0):
        self.cfg = cfg
        self.db = db
        self.jev = jev or JevBackend(cfg.typesafe_api_key, cfg.jev_model)
        self.opencode = opencode or OpenCodeBackend()
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown = breaker_cooldown
        self._fail_streak = 0
        self._breaker_opened_at: float | None = None
        self._last_success_at: float | None = None
        self.outage = False

    # ---- breaker ----------------------------------------------------
    @property
    def breaker_open(self) -> bool:
        if self._breaker_opened_at is None:
            return False
        if time.time() - self._breaker_opened_at >= self.breaker_cooldown:
            return False  # half-open: allow a probe through
        return True

    def _note_failure(self) -> None:
        self._fail_streak += 1
        if self._fail_streak >= self.breaker_threshold:
            self._breaker_opened_at = time.time()
            self.outage = True

    def _note_success(self) -> None:
        self._fail_streak = 0
        self._breaker_opened_at = None
        self._last_success_at = time.time()
        self.outage = False

    def status(self) -> dict:
        return {
            "breaker_open": self.breaker_open,
            "fail_streak": self._fail_streak,
            "outage": self.outage,
            "last_success_at": self._last_success_at,
        }

    def friendly_error(self, err: str | None) -> str:
        """Turn a raw backend error into something a human can act on."""
        if not err:
            return "the primary judge is temporarily paused after repeated failures"
        e = str(err)
        if "402" in e or "billing" in e.lower() or "credits" in e.lower():
            return ("TypeSafe API credits are exhausted — add credits at "
                    "console.typesafe.ai to restore full AI judging")
        if "breaker" in e:
            return "the primary judge is briefly paused after repeated failures; it retries automatically"
        if "401" in e:
            return "the TypeSafe API key was rejected (check TYPESAFE_API_KEY)"
        if "429" in e:
            return "the TypeSafe API rate limit was hit; requests will slow briefly"
        if "timed out" in e.lower() or "timeout" in e.lower():
            return "the judge did not answer in time"
        return e[:160]

    # ---- message screening ------------------------------------------
    def ask_message(self, *, content: str, author: str, channel: str,
                    rules: list[dict], context: list[str] | None = None) -> JudgeResult:
        started = time.time()
        enabled = [r for r in rules if r.get("enabled", True)]
        rule_ids = [r["id"] for r in enabled]

        state = {
            "message": {"content": content, "author": author, "channel": channel},
            "server_rules": [
                {"id": r["id"], "title": r["title"], "description": r["description"],
                 "severity": r["severity"]}
                for r in enabled
            ],
        }
        if context:
            state["recent_context"] = context[-5:]

        questions = {
            rid: {
                "type": "noul",
                "instructions": f"Does `message.content` break the rule \"{r['title']}\"?",
                "criteria": {
                    "true": r["description"],
                    "false": "The message does not violate this rule",
                },
            }
            for rid, r in ((r["id"], r) for r in enabled)
        }
        questions["tone"] = {
            "type": "choice",
            "instructions": "What is the message's tone?",
            "criteria": {"friendly": None, "neutral": None, "tense": None, "hostile": None},
        }
        questions["severity"] = {
            "type": "score",
            "instructions": "How disruptive to the community is this message?",
            "criteria": [
                "Normal conversation; nothing disruptive",
                "Borderline - rude or edgy but not clearly actionable",
                "Clearly breaking a house rule; needs moderator attention",
                "Severe - targeted abuse, hate, or threats requiring immediate action",
            ],
        }

        # layer 1: Jev
        if not self.breaker_open:
            resp, err = self.jev.ask(state, questions)
            if resp and isinstance(resp.get("answers"), dict):
                self._note_success()
                res = JudgeResult(
                    verdicts=resp["answers"],
                    layer="jev",
                    model=resp.get("model"),
                    input_tokens=int((resp.get("usage") or {}).get("input_tokens", 0)),
                    latency_ms=int((time.time() - started) * 1000),
                )
                self._record(res, content=content)
                return res
            self._note_failure()
            last_err = err or "empty response"
        else:
            last_err = "circuit breaker open"

        # layer 2: OpenCode free Jev
        if self.opencode.available():
            prompt = (
                "You are a Discord moderation classifier. Reply with ONLY a JSON object "
                "with one key per rule id, value = probability (0..1) that the message "
                f"breaks that rule, plus \"tone\" (friendly|neutral|tense|hostile). "
                f"Rules: {json.dumps([{ 'id': r['id'], 'title': r['title'], 'description': r['description']} for r in enabled])} "
                f"Message: {json.dumps(content)}"
            )
            data, oerr = self.opencode.ask(prompt)
            if data and isinstance(data, dict):
                verdicts = {}
                for rid in rule_ids:
                    if rid in data:
                        try:
                            verdicts[rid] = {"type": "noul", "noul": float(data[rid])}
                        except (TypeError, ValueError):
                            pass
                if "tone" in data:
                    verdicts["tone"] = {"type": "choice", "choice": str(data["tone"]),
                                        "confidence": 0.5}
                if verdicts:
                    res = JudgeResult(
                        verdicts=verdicts, layer="opencode",
                        model=getattr(self.opencode, "model", None),
                        latency_ms=int((time.time() - started) * 1000),
                        degraded_reason=last_err)
                    self._record(res, content=content)
                    return res

        # layer 3: heuristics (never auto-punish; route to review)
        verdicts = heuristic_verdicts(state, rule_ids)
        res = JudgeResult(
            verdicts=verdicts, layer="heuristic", ok=False,
            error=last_err, latency_ms=int((time.time() - started) * 1000),
            degraded_reason="all AI layers unavailable; heuristics + human review only")
        self._record(res, content=content)
        return res

    # ---- report reason ----------------------------------------------
    def ask_report_reason(self, *, reporter: str, target: str, reason: str,
                          context: str | None = None) -> JudgeResult:
        started = time.time()
        state = {"report": {"reporter": reporter, "target": target,
                            "reason": reason, "context": context or ""}}
        questions = {
            "reason_valid": {
                "type": "noul",
                "instructions": "Is `report.reason` a concrete, plausible, good-faith "
                                "reason to review the reported member's behavior?",
                "criteria": {
                    "true": "States a specific behavior that would break a normal community rule",
                    "false": "Vague, retaliatory, joke, or no actual misconduct described",
                },
            },
            "recommended_action": {
                "type": "choice",
                "instructions": "If the reason is valid, which consequence fits the "
                                "described behavior?",
                "criteria": {
                    "none_of_above": "No consequence warranted; report should be dismissed",
                    "mute_1h": "Disruptive but minor - a one-hour voice mute suffices",
                    "disconnect": "Serious disruption - removing them from voice now is warranted",
                },
            },
        }
        if not self.breaker_open:
            resp, err = self.jev.ask(state, questions)
            if resp and isinstance(resp.get("answers"), dict):
                self._note_success()
                res = JudgeResult(verdicts=resp["answers"], layer="jev",
                                  model=resp.get("model"),
                                  input_tokens=int((resp.get("usage") or {}).get("input_tokens", 0)),
                                  latency_ms=int((time.time() - started) * 1000))
                self._record(res, content=reason)
                return res
            self._note_failure()
            last_err = err or "empty response"
        else:
            last_err = "circuit breaker open"

        verdicts = heuristic_verdicts({"message": {"content": reason}},
                                      ["reason_valid"])
        res = JudgeResult(verdicts=verdicts, layer="heuristic", ok=False, error=last_err,
                          latency_ms=int((time.time() - started) * 1000),
                          degraded_reason="judge unavailable; owner review required")
        self._record(res, content=reason)
        return res

    # ---- vote adjudication ------------------------------------------
    def adjudicate_vote(self, *, target: str, reason: str, reporter: str,
                        votes: dict, total_votes: int, context: str | None = None) -> JudgeResult:
        """Jev reviews a CLOSED community vote: was the outcome justified?

        Returns verdicts: `justified` (noul) + `verdict_note` (choice).
        On any failure the caller must fall back to "pending human review".
        """
        started = time.time()
        state = {
            "vote": {"target": target, "reporter": reporter, "reason": reason,
                     "ballots": votes, "total_votes": total_votes,
                     "context": context or ""},
        }
        questions = {
            "justified": {
                "type": "noul",
                "instructions": "Do `vote.ballots` and `vote.reason` support the outcome "
                                "the community voted for?",
                "criteria": {
                    "true": "The reason describes real misconduct and the vote reflects it",
                    "false": "The reason is weak, the vote looks brigaded, or no misconduct is described",
                },
            },
            "verdict": {
                "type": "choice",
                "instructions": "What should happen to this outcome?",
                "criteria": {
                    "uphold": "The vote stands as cast",
                    "reduce": "The punishment should be reduced or shortened",
                    "overturn": "The vote should be overturned; no action",
                },
            },
        }
        if not self.breaker_open:
            resp, err = self.jev.ask(state, questions)
            if resp and isinstance(resp.get("answers"), dict):
                self._note_success()
                res = JudgeResult(verdicts=resp["answers"], layer="jev",
                                  model=resp.get("model"),
                                  input_tokens=int((resp.get("usage") or {}).get("input_tokens", 0)),
                                  latency_ms=int((time.time() - started) * 1000))
                self._record(res, content=reason)
                return res
            self._note_failure()
            last_err = err or "empty response"
        else:
            last_err = "circuit breaker open"

        res = JudgeResult(verdicts={}, layer="heuristic", ok=False, error=last_err,
                          latency_ms=int((time.time() - started) * 1000),
                          degraded_reason="judge unavailable; vote outcome needs human review")
        self._record(res, content=reason)
        return res

    # ---- util -------------------------------------------------------
    def _record(self, res: JudgeResult, *, content: str = "") -> None:
        if self.db is None:
            return
        try:
            self.db.record_judge_call(
                layer=res.layer, model=res.model, ok=res.ok,
                input_tokens=res.input_tokens, latency_ms=res.latency_ms,
                error=res.error)
        except Exception:
            pass
