"""Database: idempotent schema, cases, votes, jobs, ballots."""
from datetime import timedelta

import pytest

from tsabot.db import Database, utcnow


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    d.init()
    return d


def test_init_idempotent(tmp_path):
    d = Database(tmp_path / "t.db")
    d.init()
    d.init()  # second init must not raise
    assert d.pending_job_count() == 0


def test_case_roundtrip_and_history(db):
    db.add_case(guild_id=1, kind="moderation", action="warn", target_id=9,
                actor_id=2, reason="test")
    db.add_case(guild_id=1, kind="moderation", action="timeout", target_id=9,
                reason="second")
    rows = db.list_cases(guild_id=1, target_id=9)
    assert len(rows) == 2
    assert rows[0]["action"] == "timeout"          # newest first
    assert db.count_cases(guild_id=1, kind="moderation") == 2


def test_invalid_report_tracking(db):
    for _ in range(3):
        db.add_case(guild_id=1, kind="report", action="invalid", reporter_id=5, reason="x")
    assert db.invalid_report_count(guild_id=1, reporter_id=5) == 3
    # older than window is excluded
    assert db.invalid_report_count(guild_id=1, reporter_id=5, days=0) == 0


def test_reports_since_window(db):
    db.create_vote(guild_id=1, target_id=2, reporter_id=5, reason="r", judge=None,
                   deadline_at=None)
    assert db.reports_since(guild_id=1, reporter_id=5, hours=24) == 1
    assert db.reports_since(guild_id=1, reporter_id=5, hours=0) == 0


def test_votes_and_ballots(db):
    vid = db.create_vote(guild_id=1, target_id=2, reporter_id=5, reason="reason",
                         judge={"x": 1}, deadline_at=utcnow() + timedelta(minutes=60))
    db.set_vote_message(vid, channel_id=10, message_id=11)
    db.add_ballot(vote_id=vid, user_id=1, choice="mute")
    db.add_ballot(vote_id=vid, user_id=2, choice="mute")
    db.add_ballot(vote_id=vid, user_id=3, choice="none")
    # duplicate ballot replaces (upsert)
    db.add_ballot(vote_id=vid, user_id=3, choice="disconnect")
    counts = db.ballot_counts(vid)
    assert counts == {"mute": 2, "disconnect": 1}
    assert db.ballot_total(vid) == 3
    db.close_vote(vid, status="passed", action="mute")
    assert db.list_open_votes(1) == []
    row = db.get_vote(vid)
    assert row["status"] == "passed" and row["action"] == "mute"
    assert db.active_vote_exists(guild_id=1, reporter_id=5, target_id=2) is False


def test_active_vote_exists(db):
    vid = db.create_vote(guild_id=1, target_id=2, reporter_id=5, reason="r",
                         judge=None, deadline_at=None)
    assert db.active_vote_exists(guild_id=1, reporter_id=5, target_id=2) is True
    db.close_vote(vid, status="vetoed")
    assert db.active_vote_exists(guild_id=1, reporter_id=5, target_id=2) is False


def test_scheduled_jobs_due_and_mark(db):
    past = utcnow() - timedelta(minutes=1)
    future = utcnow() + timedelta(hours=1)
    j1 = db.add_job(guild_id=1, kind="voice_unmute", payload={"member_id": 3}, due_at=past)
    db.add_job(guild_id=1, kind="vote_deadline", payload={"vote_id": 1}, due_at=future)
    due = db.due_jobs()
    assert [r["id"] for r in due] == [j1]
    db.mark_job(j1, "done")
    assert db.due_jobs() == []
    assert db.pending_job_count() == 1


def test_caps_and_exemptions(db):
    db.set_cap(guild_id=1, role_id=10, capability="moderate")
    db.set_cap(guild_id=1, role_id=11, capability="case_view")
    assert db.role_caps(guild_id=1, role_ids=[10, 11]) == {"moderate", "case_view"}
    assert db.role_caps(guild_id=1, role_ids=[99]) == set()
    db.clear_caps(guild_id=1, role_id=10)
    assert db.role_caps(guild_id=1, role_ids=[10]) == set()


def test_owners_registry(db):
    db.add_owner(guild_id=1, subject_id=7, kind="user", added_by=1)
    db.add_owner(guild_id=1, subject_id=8, kind="role", added_by=1)
    rows = db.list_owners(1)
    assert {(r["subject_id"], r["kind"]) for r in rows} == {(7, "user"), (8, "role")}
    db.remove_owner(guild_id=1, subject_id=7, kind="user")
    assert len(db.list_owners(1)) == 1


def test_judge_stats(db):
    db.record_judge_call(layer="jev", model="jev-1.13.0", ok=True,
                         input_tokens=300, latency_ms=120)
    db.record_judge_call(layer="hevristic", model=None, ok=False, error="boom")
    stats = db.judge_stats()
    assert stats["calls"] == 2
    assert stats["ok"] == 1
    assert stats["tokens"] == 300
    assert stats["est_cost_usd"] > 0
    assert db.last_judge_error() == "boom"
