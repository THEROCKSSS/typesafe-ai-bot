"""Executor + capability tests."""
import pytest

from tsabot.actions import Executor
from tsabot.caps import ALL_CAPS, has_cap, resolve_caps
from tsabot.db import Database


class FakeMember:
    def __init__(self, uid=5, guild=None):
        self.id = uid
        self.guild = guild
        self.timeouts = []
        self.edits = []
        self.moves = []

    async def timeout(self, delta, reason=None):
        self.timeouts.append((delta, reason))

    async def edit(self, **kw):
        self.edits.append(kw)

    async def move_to(self, channel, reason=None):
        self.moves.append((channel, reason))

    def __str__(self):
        return f"<member {self.id}>"


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "a.db")
    d.init()
    return d


@pytest.mark.asyncio
async def test_dry_run_suppresses_timeout(db):
    ex = Executor(db=db, dry_run=True)
    m = FakeMember()
    res = await ex.timeout(m, minutes=10, reason="spam", guild_id=1)
    assert res.dry_run is True
    assert m.timeouts == []                      # NOT enforced
    rows = db.list_cases(guild_id=1)
    assert rows and rows[0]["dry_run"] == 1      # but recorded


@pytest.mark.asyncio
async def test_live_executes_timeout(db):
    ex = Executor(db=db, dry_run=False)
    m = FakeMember()
    res = await ex.timeout(m, minutes=10, reason="spam", guild_id=1)
    assert res.executed is True
    assert len(m.timeouts) == 1


@pytest.mark.asyncio
async def test_voice_mute_schedules_lift_only_when_live(db):
    ex = Executor(db=db, dry_run=False)
    m = FakeMember()
    await ex.voice_mute(m, minutes=60, reason="vote", guild_id=1)
    assert m.edits and m.edits[0]["mute"] is True
    assert db.pending_job_count() == 1           # auto-lift scheduled

    db2 = Database(db.path)
    m2 = FakeMember(uid=6)
    ex_dry = Executor(db=db2, dry_run=True)
    await ex_dry.voice_mute(m2, minutes=60, reason="vote", guild_id=1)
    assert m2.edits == []                        # not enforced in dry run


@pytest.mark.asyncio
async def test_disconnect(db):
    ex = Executor(db=db, dry_run=False)
    m = FakeMember()
    await ex.disconnect(m, reason="vote", guild_id=1)
    assert m.moves and m.moves[0][0] is None


def test_caps_resolution():
    assert resolve_caps(role_caps={"case_view"}, is_owner=True) == set(ALL_CAPS)
    assert resolve_caps(role_caps={"case_view"}, is_owner=False) == {"case_view"}
    assert has_cap({"warn"}, "warn")
    assert not has_cap({"warn"}, "disconnect")
