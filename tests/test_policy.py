"""Policy: rulebook loading + verdict -> decision banding."""
import json

import pytest

from tsabot.policy import Decision, RulebookError, decide, load_rules

RULES = [
    {"id": "harassment", "title": "No harassment", "description": "d", "severity": "high",
     "enabled": True, "auto_action": "timeout", "timeout_minutes": 30},
    {"id": "spam", "title": "No spam", "description": "d", "severity": "medium",
     "enabled": True, "auto_action": "review"},
    {"id": "off", "title": "Disabled", "description": "d", "severity": "low",
     "enabled": False, "auto_action": "timeout"},
]


def test_load_rules_ok(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"rules": RULES}), encoding="utf-8")
    rules = load_rules(p)
    assert len(rules) == 3


def test_load_rules_errors(tmp_path):
    p = tmp_path / "rules.json"
    with pytest.raises(RulebookError):
        load_rules(p)  # missing file
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(RulebookError):
        load_rules(p)
    p.write_text(json.dumps({"rules": []}), encoding="utf-8")
    with pytest.raises(RulebookError):
        load_rules(p)
    p.write_text(json.dumps({"rules": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(RulebookError):
        load_rules(p)
    dup = [dict(RULES[0]), dict(RULES[0])]
    p.write_text(json.dumps({"rules": dup}), encoding="utf-8")
    with pytest.raises(RulebookError):
        load_rules(p)


def test_decide_high_band_actions():
    v = {"harassment": {"type": "noul", "noul": 0.95}}
    ds = decide(RULES, v, high=0.85, medium=0.6)
    assert ds and ds[0].outcome == "action" and ds[0].action == "timeout"


def test_decide_medium_band_reviews():
    v = {"harassment": {"type": "noul", "noul": 0.7}}
    ds = decide(RULES, v, high=0.85, medium=0.6)
    assert ds and ds[0].outcome == "review"


def test_decide_low_band_nothing():
    v = {"harassment": {"type": "noul", "noul": 0.3}}
    assert decide(RULES, v, high=0.85, medium=0.6) == []


def test_decide_ignores_disabled_rules():
    v = {"off": {"type": "noul", "noul": 0.99}}
    assert decide(RULES, v, high=0.85, medium=0.6) == []


def test_decide_review_action_never_auto_acts():
    # spam rule has auto_action=review: even at 0.99 it must not become an action
    v = {"spam": {"type": "noul", "noul": 0.99}}
    ds = decide(RULES, v, high=0.85, medium=0.6)
    assert ds and ds[0].outcome == "review"


def test_critical_severity_lowers_action_bar():
    rules = [{"id": "hate", "title": "Hate", "description": "d", "severity": "critical",
              "enabled": True, "auto_action": "timeout", "timeout_minutes": 60}]
    # 0.65 sits between medium (0.6) and high (0.85): a non-critical rule would
    # only review here; a critical rule acts.
    v = {"hate": {"type": "noul", "noul": 0.65}}
    ds = decide(rules, v, high=0.85, medium=0.6)
    assert ds and ds[0].outcome == "action"
    # sanity: same probability on a high (non-critical) rule reviews instead
    rules_hi = [dict(rules[0], severity="high")]
    ds2 = decide(rules_hi, v, high=0.85, medium=0.6)
    assert ds2 and ds2[0].outcome == "review"


def test_decide_sorted_action_first():
    v = {"harassment": {"type": "noul", "noul": 0.9},
         "spam": {"type": "noul", "noul": 0.62}}
    ds = decide(RULES, v, high=0.85, medium=0.6)
    assert ds[0].outcome == "action"
