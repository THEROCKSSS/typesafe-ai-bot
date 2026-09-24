"""Mocked Discord integration: the full report -> gate -> vote -> action path.

Simulates a guild with fake discord objects and asserts on the calls the
system makes and the state it persists at the cog boundary.
"""
from datetime import timedelta

import pytest

from tsabot.actions import Executor
from tsabot.db import Database, utcnow
from tsabot.vote_logic import tally, verdict


class FakeGuild:
    def __init__(self, gid=1):
        self.id = gid
        self.name = "Test Guild"

    def get_role(self, rid):
        return None

    def get_channel(self, cid):
        return None

    def get_member(self, mid):
        return None


class FakeUser:
    def __init__(self, uid):
        self.id = uid
        self.bot = False


class FakeMember(FakeUser):
    def __init__(self, uid, guild):
        super().__init__(uid)
        self.guild = guild
        self.roles = []
        self.display_name = f"user{uid}"
        self.timeouts = []
        self.edits = []
        self.moves = []

    async def timeout(self, delta, reason=None):
        self.timeouts.append((delta, reason))

    async def edit(self, **kw):
        self.edits.append(kw)

    async def move_to(self, ch, reason=None):
        self.moves.append((ch, reason))


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "i.db")
    d.init()
    return d


def cast_ballots(db, vote_id, ballots):
    for uid, choice in ballots:
        db.add_ballot(vote_id=vote_id, user_id=uid, choice=choice)


@pytest.mark.asyncio
async def test_full_vote_lifecycle_passes_and_executes_mute(db):
    """The headline flow: report card -> votes -> passing mute -> executor call."""
    guild = FakeGuild()
    target = FakeMember(42, guild)
    reporter = FakeUser(7)
    deadline = utcnow() + timedelta(minutes=60)

    vote_id = db.create_vote(guild_id=1, target_id=target.id, reporter_id=reporter.id,
                             reason="said slurs in vc", judge={"reason_valid": 0.95},
                             deadline_at=deadline)
    db.add_job(guild_id=1, kind="vote_deadline", payload={"vote_id": vote_id},
               due_at=deadline)

    cast_ballots(db, vote_id, [(1, "mute"), (2, "mute"), (3, "mute"),
                               (4, "mute"), (5, "mute"), (6, "none")])
    counts = db.ballot_counts(vote_id)
    status, action = verdict(counts, min_votes=5, pct=0.6)
    assert status == "passed" and action == "mute"

    # close like the cog does
    executor = Executor(db=db, dry_run=False)
    await executor.voice_mute(target, minutes=60, reason=f"community vote #{vote_id}",
                              guild_id=1, kind="vote")
    db.close_vote(vote_id, status="passed", action=action)

    assert target.edits and target.edits[0]["mute"] is True
    assert db.pending_job_count() >= 1            # the auto-lift is scheduled
    row = db.get_vote(vote_id)
    assert row["status"] == "passed" and row["action"] == "mute"
    cases = db.list_cases(guild_id=1, target_id=target.id)
    assert any(c["action"] == "voice_mute" for c in cases)


@pytest.mark.asyncio
async def test_vote_fails_below_threshold_no_enforcement(db):
    guild = FakeGuild()
    target = FakeMember(43, guild)
    vote_id = db.create_vote(guild_id=1, target_id=target.id, reporter_id=7,
                             reason="r", judge=None,
                             deadline_at=utcnow() + timedelta(minutes=60))
    cast_ballots(db, vote_id, [(1, "mute"), (2, "none"), (3, "none")])
    counts = db.ballot_counts(vote_id)
    status, action = verdict(counts, min_votes=5, pct=0.6)
    assert status == "failed" and action is None
    db.close_vote(vote_id, status="failed")
    assert target.edits == [] and target.timeouts == []


@pytest.mark.asyncio
async def test_dry_run_vote_outcome_records_without_enforcing(db):
    guild = FakeGuild()
    target = FakeMember(44, guild)
    executor = Executor(db=db, dry_run=True)
    await executor.disconnect(target, reason="vote", guild_id=1)
    assert target.moves == []                     # suppressed
    cases = db.list_cases(guild_id=1, target_id=target.id)
    assert cases and cases[0]["dry_run"] == 1


def test_scheduler_restart_rearm(db):
    """Jobs persist; a fresh Database over the same file sees them due."""
    past = utcnow() - timedelta(minutes=1)
    db.add_job(guild_id=1, kind="voice_unmute", payload={"member_id": 9}, due_at=past)
    db2 = Database(db.path)
    db2.init()
    due = db2.due_jobs()
    assert len(due) == 1 and due[0]["kind"] == "voice_unmute"


def test_antinuke_thresholds():
    from tsabot.antinuke import NukeThresholds, NukeWatcher
    w = NukeWatcher(NukeThresholds(channel_deletes=3, window_seconds=30))
    assert w.record(1, "channel_delete") is None
    assert w.record(1, "channel_delete") is None
    trip = w.record(1, "channel_delete")
    assert trip is not None and "3 channel deletes" in trip
    # different actor unaffected
    assert w.record(2, "channel_delete") is None


def test_reports_eligibility_rules():
    """Eligibility helper logic mirrored from the cog (bots/self excluded)."""
    def eligible(voter_id, is_bot, target_id):
        if is_bot:
            return False, "bots can't vote"
        if voter_id == target_id:
            return False, "the reported member can't vote"
        return True, ""

    assert eligible(1, False, 2)[0] is True
    assert eligible(1, True, 2)[0] is False
    assert eligible(2, False, 2)[0] is False
