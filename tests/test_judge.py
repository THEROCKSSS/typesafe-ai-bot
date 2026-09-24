"""Judge chain: layered fallback, breaker, and the heuristic floor.

Uses fake backends - no network in unit tests. The real API is exercised by
tools/judge_selftest.py (live evidence).
"""
import pytest

from tsabot.config import load_config
from tsabot.judge import JudgeChain, JudgeResult, heuristic_verdicts

RULES = [
    {"id": "harassment", "title": "No harassment", "description": "no insults",
     "severity": "high", "enabled": True, "auto_action": "timeout"},
    {"id": "spam", "title": "No spam", "description": "no spam",
     "severity": "medium", "enabled": True, "auto_action": "review"},
]


class FakeJev:
    def __init__(self, *, response=None, error=None):
        self.calls = 0
        self.response = response
        self.error = error

    def ask(self, state, questions):
        self.calls += 1
        if self.error:
            return None, self.error
        resp = self.response or {
            "model": "jev-1.13.0",
            "answers": {
                "harassment": {"type": "noul", "noul": 0.95},
                "spam": {"type": "noul", "noul": 0.10},
                "tone": {"type": "choice", "choice": "hostile", "confidence": 0.9},
                "severity": {"type": "score", "score": 3.1, "confidence": 0.8},
            },
            "usage": {"input_tokens": 333, "output_tokens": 40},
        }
        return resp, None


class FakeOpenCode:
    def __init__(self, *, data=None, available=True):
        self.data = data
        self._avail = available
        self.calls = 0
        self.model = "opencode/jev-1.13-free"

    def available(self):
        return self._avail

    def ask(self, prompt):
        self.calls += 1
        if self.data is None:
            return None, "opencode failed"
        return self.data, None


def make_chain(*, jev=None, opencode=None, db=None, **kw):
    cfg = load_config(env={}, base=__import__("pathlib").Path("."))
    return JudgeChain(cfg, db, jev=jev or FakeJev(), opencode=opencode or FakeOpenCode(),
                      **kw)


def test_primary_layer_success():
    chain = make_chain()
    res = chain.ask_message(content="you are trash", author="a", channel="c", rules=RULES)
    assert res.layer == "jev"
    assert res.model == "jev-1.13.0"
    assert res.input_tokens == 333
    assert res.max_prob == pytest.approx(0.95)
    assert chain.status()["outage"] is False


def test_fallback_to_opencode_after_primary_failure():
    chain = make_chain(jev=FakeJev(error="HTTP 503"),
                       opencode=FakeOpenCode(data={"harassment": 0.9, "spam": 0.1,
                                                   "tone": "hostile"}))
    res = chain.ask_message(content="x", author="a", channel="c", rules=RULES)
    assert res.layer == "opencode"
    assert res.verdicts["harassment"]["noul"] == pytest.approx(0.9)
    assert res.degraded_reason  # primary failure recorded


def test_last_resort_heuristics_never_ok():
    chain = make_chain(jev=FakeJev(error="down"),
                       opencode=FakeOpenCode(available=False))
    res = chain.ask_message(content="kys loser", author="a", channel="c", rules=RULES)
    assert res.layer == "heuristic"
    assert res.ok is False
    assert res.verdicts["_heuristic"]["flagged"] is True


def test_heuristic_clean_message_not_flagged():
    """Non-severe content must NOT flag: heuristics never guess."""
    chain = make_chain(jev=FakeJev(error="down"),
                       opencode=FakeOpenCode(available=False))
    res = chain.ask_message(content="gg great raid tonight", author="a", channel="c",
                            rules=RULES)
    assert res.layer == "heuristic"
    assert res.verdicts["_heuristic"]["flagged"] is False


def test_breaker_opens_after_threshold_and_recovers():
    jev = FakeJev(error="boom")
    chain = make_chain(jev=jev, opencode=FakeOpenCode(available=False),
                       breaker_threshold=3, breaker_cooldown=0.05)
    for _ in range(3):
        chain.ask_message(content="x", author="a", channel="c", rules=RULES)
    assert chain.breaker_open is True
    assert chain.status()["outage"] is True
    calls_before = jev.calls
    chain.ask_message(content="x", author="a", channel="c", rules=RULES)
    assert jev.calls == calls_before  # breaker short-circuits
    import time
    time.sleep(0.06)
    ok = FakeJev()
    chain.jev = ok
    res = chain.ask_message(content="x", author="a", channel="c", rules=RULES)
    assert res.layer == "jev"
    assert chain.status()["outage"] is False


def test_report_reason_questions_and_fallback():
    resp = {
        "model": "jev-1.13.0",
        "answers": {
            "reason_valid": {"type": "noul", "noul": 0.92},
            "recommended_action": {"type": "choice", "choice": "disconnect",
                                   "confidence": 0.8},
        },
        "usage": {"input_tokens": 200, "output_tokens": 20},
    }
    chain = make_chain(jev=FakeJev(response=resp))
    res = chain.ask_report_reason(reporter="r", target="t", reason="they spammed slurs")
    assert res.verdicts["reason_valid"]["noul"] == pytest.approx(0.92)
    assert res.verdicts["recommended_action"]["choice"] == "disconnect"


def test_heuristic_verdicts_shapes():
    v = heuristic_verdicts({"message": {"content": "kys"}}, ["harassment"])
    assert v["_heuristic"]["flagged"] is True
    assert v["harassment"]["noul"] == pytest.approx(0.9)
    clean = heuristic_verdicts({"message": {"content": "hello everyone"}}, ["harassment"])
    assert clean["_heuristic"]["flagged"] is False


def test_judge_accounting_recorded(tmp_path):
    from tsabot.db import Database
    db = Database(tmp_path / "j.db")
    db.init()
    chain = make_chain(db=db)
    chain.ask_message(content="x", author="a", channel="c", rules=RULES)
    stats = db.judge_stats()
    assert stats["calls"] == 1
    assert stats["by_layer"] == {"jev": 1}
