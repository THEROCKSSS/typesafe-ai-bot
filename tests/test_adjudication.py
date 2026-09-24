"""Vote adjudication + friendly errors + enrichment round-trips."""
import pytest

from tsabot.config import load_config
from tsabot.db import Database
from tsabot.judge import JudgeChain
from tsabot.judge import JudgeResult


class FakeJev:
    def __init__(self, *, response=None, error=None):
        self.response = response
        self.error = error

    def ask(self, state, questions):
        if self.error:
            return None, self.error
        return self.response or {
            "model": "jev-1.13.0",
            "answers": {
                "justified": {"type": "noul", "noul": 0.88},
                "verdict": {"type": "choice", "choice": "uphold", "confidence": 0.8},
            },
            "usage": {"input_tokens": 210, "output_tokens": 20},
        }, None


class FakeOpenCode:
    def available(self):
        return False

    def ask(self, prompt):
        return None, "unavailable"

    model = "opencode/jev-1.13-free"


def make_chain(*, jev):
    cfg = load_config(env={}, base=__import__("pathlib").Path("."))
    return JudgeChain(cfg, None, jev=jev, opencode=FakeOpenCode())


def test_adjudicate_vote_returns_verdicts():
    chain = make_chain(jev=FakeJev())
    res = chain.adjudicate_vote(target="griefer", reason="spammed slurs",
                               reporter="member1",
                               votes={"mute": 6, "disconnect": 1, "none": 1},
                               total_votes=8)
    assert res.layer == "jev"
    assert res.verdicts["justified"]["noul"] == pytest.approx(0.88)
    assert res.verdicts["verdict"]["choice"] == "uphold"


def test_adjudicate_vote_degrades_gracefully():
    chain = make_chain(jev=FakeJev(error="HTTP 402: billing_error"))
    res = chain.adjudicate_vote(target="t", reason="r", reporter="p",
                               votes={}, total_votes=0)
    assert res.layer == "heuristic"
    assert res.ok is False
    # must NOT contain verdicts — callers hold the outcome for human review
    assert not res.verdicts


def test_friendly_error_translations():
    chain = make_chain(jev=FakeJev())
    assert "credits" in chain.friendly_error('HTTP 402: billing_error')
    assert "paused" in chain.friendly_error("circuit breaker open")
    assert "key was rejected" in chain.friendly_error("HTTP 401: unauthorized")
    assert "did not answer" in chain.friendly_error("request timed out")
    assert chain.friendly_error(None)  # never raises, never empty


def test_cases_store_names_and_voice(tmp_path):
    db = Database(tmp_path / "n.db")
    db.init()
    db.add_case(guild_id=1, kind="moderation", action="timeout", target_id=42,
                reporter_id=7, target_name="griefer42", reporter_name="reporter1",
                reason="test", voice_channel="Field Team")
    db.add_case(guild_id=1, kind="moderation", action="warn", reason="x")
    rows = db.query_all("SELECT * FROM cases ORDER BY id")
    assert rows[0]["target_name"] == "griefer42"
    assert rows[0]["reporter_name"] == "reporter1"
    assert rows[0]["voice_channel"] == "Field Team"


def test_votes_store_names_and_ai_verdict(tmp_path):
    db = Database(tmp_path / "v.db")
    db.init()
    vid = db.create_vote(guild_id=1, target_id=2, reporter_id=3, reason="r",
                         judge=None, deadline_at=None,
                         target_name="griefer42", reporter_name="member1")
    db.close_vote(vid, status="passed", action="mute", ai_verdict="uphold",
                  ai_note="justified 0.88 → uphold (jev-1.13.0)")
    row = db.get_vote(vid)
    assert row["target_name"] == "griefer42"
    assert row["reporter_name"] == "member1"
    assert row["ai_verdict"] == "uphold"
    assert "justified" in row["ai_note"]


def test_schema_migration_adds_columns(tmp_path):
    """A DB created before the enrichment columns must migrate cleanly."""
    import sqlite3
    p = tmp_path / "old.db"
    con = sqlite3.connect(p)
    con.executescript("""
      CREATE TABLE cases (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER,
        kind TEXT, action TEXT, target_id INTEGER, actor_id INTEGER,
        reporter_id INTEGER, reason TEXT, detail_json TEXT,
        dry_run INTEGER DEFAULT 0, created_at TEXT);
      CREATE TABLE votes (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER,
        channel_id INTEGER, message_id INTEGER, target_id INTEGER,
        reporter_id INTEGER, reason TEXT, judge_json TEXT, status TEXT,
        action TEXT, deadline_at TEXT, created_at TEXT, closed_at TEXT);
    """)
    con.commit(); con.close()
    db = Database(p)
    db.init()  # migrates
    cols = {r[1] for r in db.query_all("PRAGMA table_info(cases)")}
    assert {"target_name", "actor_name", "reporter_name", "voice_channel"} <= cols
    vcols = {r[1] for r in db.query_all("PRAGMA table_info(votes)")}
    assert {"target_name", "reporter_name", "ai_verdict", "ai_note"} <= vcols
