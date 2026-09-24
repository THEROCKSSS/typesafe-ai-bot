"""1000-case moderation load test.

Two modes:
  local  — run every case through the live judge chain + policy engine in-process.
           Fast; produces the full scoring matrix (catch/miss/false-positive).
  live   — sample N cases, post them through the REAL Discord webhook into the
           test channel, and verify from the database that exactly the expected
           ones were caught. Real-time end-to-end evidence.

Usage:
  python tools/loadtest/runner.py --mode local
  python tools/loadtest/runner.py --mode live --sample 20
  python tools/loadtest/runner.py --mode local --json-out data/loadtest.json

Exit code is nonzero when the run reveals leaks/false-positives above the
configured gates (so CI/staff see the regression).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "loadtest"))

from cases import build_corpus  # noqa: E402
from tsabot.config import load_config  # noqa: E402
from tsabot.judge import JudgeChain  # noqa: E402
from tsabot.policy import decide, load_rules  # noqa: E402


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.is_file():
        for line in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------- local mode
def run_local(cfg, rules, *, progress=None) -> dict:
    corpus = build_corpus()
    chain = JudgeChain(cfg, db=None)
    results = []
    by_cat = defaultdict(lambda: {"total": 0, "caught": 0, "missed": 0, "fp": 0})

    t0 = time.time()
    for i, case in enumerate(corpus):
        res = chain.ask_message(content=case.text, author="loadtest", channel="bot-testing",
                                rules=rules)
        decisions = decide(rules, res.verdicts,
                           high=cfg.automod_high, medium=cfg.automod_medium)
        caught = len(decisions) > 0
        expect = case.expected == "violation"
        outcome = ("catch" if caught and expect else
                   "miss" if not caught and expect else
                   "false_positive" if caught and not expect else "correct_pass")
        by_cat[case.category]["total"] += 1
        if outcome == "catch":
            by_cat[case.category]["caught"] += 1
        elif outcome == "miss":
            by_cat[case.category]["missed"] += 1
        elif outcome == "false_positive":
            by_cat[case.category]["fp"] += 1
        results.append({
            "id": case.id, "category": case.category, "text": case.text[:200],
            "expected": case.expected,
            "decision": decisions[0].outcome if decisions else None,
            "rule": decisions[0].rule_id if decisions else None,
            "p": round(decisions[0].probability, 3) if decisions else
                 round(res.max_prob, 3),
            "layer": res.layer, "outcome": outcome,
        })
        if progress and i % 50 == 0:
            progress(i, len(corpus))

    total = len(corpus)
    violations = sum(1 for c in corpus if c.expected == "violation")
    clean = total - violations
    catches = sum(1 for r in results if r["outcome"] == "catch")
    misses = sum(1 for r in results if r["outcome"] == "miss")
    fps = sum(1 for r in results if r["outcome"] == "false_positive")
    summary = {
        "mode": "local",
        "total": total, "violations": violations, "clean": clean,
        "caught": catches, "missed": misses, "false_positives": fps,
        "leak_rate": round(misses / violations, 4) if violations else 0.0,
        "fp_rate": round(fps / clean, 4) if clean else 0.0,
        "recall": round(catches / violations, 4) if violations else 0.0,
        "precision": round(catches / (catches + fps), 4) if (catches + fps) else 0.0,
        "seconds": round(time.time() - t0, 1),
        "by_category": {k: v for k, v in sorted(by_cat.items())},
        "by_layer": dict(Counter(r["layer"] for r in results)),
        "results": results,
        "missed_samples": [r for r in results if r["outcome"] == "miss"][:40],
        "fp_samples": [r for r in results if r["outcome"] == "false_positive"][:40],
    }
    return summary


# ----------------------------------------------------------------- live mode
def webhook_post(wh: str, token: str, content: str, username: str) -> str | None:
    """Post via webhook; returns the created message id or None."""
    body = json.dumps({"content": content, "username": username,
                       "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(
        f"https://discord.com/api/v10/webhooks/{wh}/{token}?wait=true",
        data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "DiscordBot (https://local, 0.1) tsabot-loadtest")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                if r.status in (200, 204):
                    data = json.loads(r.read() or b"{}")
                    return str(data.get("id") or "")
        except urllib.error.HTTPError as e:
            if e.code in (429, 1010, 403):
                time.sleep(3 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(2)
    return None


def run_live(cfg, *, sample: int, delay: float = 2.2, progress=None) -> dict:
    env = load_env()
    wh, wht = env.get("TEST_WEBHOOK_ID"), env.get("TEST_WEBHOOK_TOKEN")
    if not wh or not wht:
        raise SystemExit("TEST_WEBHOOK_ID / TEST_WEBHOOK_TOKEN missing from .env")
    db_path = cfg.effective_db_path(ROOT)

    corpus = build_corpus()
    # stratified sample: proportional pull from every category, deterministic
    per_cat = max(1, sample // 10)
    sampled = []
    for cat in dict.fromkeys(c.category for c in corpus):
        cat_cases = [c for c in corpus if c.category == cat]
        sampled.extend(cat_cases[:per_cat])
    sampled = sampled[:sample]

    def case_count() -> int:
        try:
            return sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        except Exception:
            return 0

    before_cases = case_count()
    sent = 0
    posted = []  # (case, message_id)
    for i, case in enumerate(sampled):
        mid = webhook_post(wh, wht, case.text, f"loadtest-{case.category}")
        if mid:
            sent += 1
            posted.append((case, mid))
        if progress:
            progress(i, len(sampled))
        time.sleep(delay)

    # wait for the judge queue to drain (fallback chain can add latency)
    time.sleep(15)

    # Match cases by the webhook message id recorded in detail_json, falling back
    # to content matching for robustness.
    import json as _json
    rows = []
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(
            "SELECT id, kind, action, reason, detail_json, created_at FROM cases "
            "ORDER BY id DESC LIMIT 400")]
    except Exception:
        pass

    by_msg_id = {}
    by_content = set()
    for r in rows:
        try:
            det = _json.loads(r.get("detail_json") or "{}")
        except Exception:
            det = {}
        if det.get("message_id"):
            by_msg_id[str(det["message_id"])] = r
        if det.get("content"):
            by_content.add(det["content"][:120])
        if r.get("reason"):
            by_content.add(r["reason"][:120])

    caught_ids = set()
    for case, mid in posted:
        hit = by_msg_id.get(str(mid))
        if hit is None and case.text[:120] in by_content:
            hit = True
        if hit:
            caught_ids.add(case.id)

    expect = [c for c in sampled if c.expected == "violation"]
    clean = [c for c in sampled if c.expected == "clean"]
    caught = [c for c in expect if c.id in caught_ids]
    missed = [c for c in expect if c.id not in caught_ids]
    fp = [c for c in clean if c.id in caught_ids]

    return {
        "mode": "live",
        "total": len(sampled), "sent": sent,
        "violations": len(expect), "clean": len(clean),
        "caught": len(caught), "missed": len(missed), "false_positives": len(fp),
        "leak_rate": round(len(missed) / len(expect), 4) if expect else 0.0,
        "fp_rate": round(len(fp) / len(clean), 4) if clean else 0.0,
        "recall": round(len(caught) / len(expect), 4) if expect else 0.0,
        "cases_before": before_cases, "cases_after": case_count(),
        "missed_samples": [{"id": c.id, "text": c.text, "category": c.category}
                           for c in missed],
        "caught_samples": [{"id": c.id, "text": c.text} for c in caught[:20]],
    }


# ------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "live"], default="local")
    ap.add_argument("--sample", type=int, default=20, help="live mode: cases to send")
    ap.add_argument("--delay", type=float, default=2.2, help="live mode: seconds between posts")
    ap.add_argument("--json-out", default=str(ROOT / "data" / "loadtest_results.json"))
    ap.add_argument("--max-leak", type=float, default=None,
                    help="fail when leak_rate exceeds this (local mode)")
    ap.add_argument("--max-fp", type=float, default=None,
                    help="fail when fp_rate exceeds this (local mode)")
    args = ap.parse_args()

    cfg = load_config(base=ROOT)
    rules = load_rules(cfg.effective_rules_path(ROOT))

    def progress(i, n):
        print(f"  ... {i}/{n}", file=sys.stderr)

    if args.mode == "local":
        summary = run_local(cfg, rules, progress=progress)
    else:
        summary = run_live(cfg, sample=args.sample, delay=args.delay, progress=progress)

    out = pathlib.Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("results", "missed_samples", "fp_samples",
                                   "by_category", "by_layer")}, indent=2))
    if summary.get("by_category"):
        print("\nby category:")
        for cat, s in summary["by_category"].items():
            print(f"  {cat:14} total={s['total']:3} caught={s['caught']:3} "
                  f"missed={s['missed']:3} fp={s['fp']:3}")

    failed = False
    if args.max_leak is not None and summary["leak_rate"] > args.max_leak:
        print(f"\nFAIL: leak_rate {summary['leak_rate']} > {args.max_leak}")
        failed = True
    if args.max_fp is not None and summary["fp_rate"] > args.max_fp:
        print(f"\nFAIL: fp_rate {summary['fp_rate']} > {args.max_fp}")
        failed = True
    print(f"\nresults written: {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
