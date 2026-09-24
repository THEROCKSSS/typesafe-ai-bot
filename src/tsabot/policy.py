"""Policy: load the rulebook and map Jev verdicts through confidence bands.

Pure decision logic: verdicts + config -> decision. No Discord, no I/O
beyond loading the rules file (which is a separate function).
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass


class RulebookError(Exception):
    pass


@dataclass
class Decision:
    outcome: str          # "log" | "review" | "action"
    rule_id: str | None
    rule_title: str | None
    probability: float
    severity: str | None
    action: str | None    # rule's configured action when outcome == "action"
    reason: str


def load_rules(path: str | pathlib.Path) -> list[dict]:
    p = pathlib.Path(path)
    if not p.is_file():
        raise RulebookError(f"rulebook not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RulebookError(f"rulebook is not valid JSON: {e}") from e
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RulebookError("rulebook has no 'rules' array")
    seen = set()
    for i, r in enumerate(rules):
        for field_name in ("id", "title", "description", "severity"):
            if not r.get(field_name):
                raise RulebookError(f"rule #{i} missing required field '{field_name}'")
        if r["id"] in seen:
            raise RulebookError(f"duplicate rule id: {r['id']}")
        seen.add(r["id"])
        if r["severity"] not in ("low", "medium", "high", "critical"):
            raise RulebookError(f"rule {r['id']}: severity must be low|medium|high|critical")
    return rules


def decide(rules: list[dict], verdicts: dict, *, high: float, medium: float) -> list[Decision]:
    """Map one message's verdict set into decisions.

    Bands (configurable):
      p >= high    -> action   (per the rule's auto_action, when set)
      medium <= p < high -> review
      p < medium   -> log
    Severity may lower the action threshold: critical rules act from `medium`.
    """
    decisions: list[Decision] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        v = verdicts.get(rule["id"])
        if not isinstance(v, dict) or v.get("type") != "noul":
            continue
        p = float(v.get("noul", 0.0))
        eff_high = high if rule.get("severity") != "critical" else max(medium, 0.5)
        if p >= eff_high and rule.get("auto_action") in ("timeout", "mute", "disconnect"):
            decisions.append(Decision(
                outcome="action", rule_id=rule["id"], rule_title=rule["title"],
                probability=p, severity=rule["severity"], action=rule["auto_action"],
                reason=f"{rule['title']} (p={p:.2f})"))
        elif p >= medium:
            decisions.append(Decision(
                outcome="review", rule_id=rule["id"], rule_title=rule["title"],
                probability=p, severity=rule["severity"], action=None,
                reason=f"possible violation: {rule['title']} (p={p:.2f})"))
    order = {"action": 2, "review": 1, "log": 0}
    decisions.sort(key=lambda d: (order[d.outcome], d.probability), reverse=True)
    return decisions
