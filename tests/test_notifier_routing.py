"""Notifier routing tests: log-channel-first defaults, severity overrides,
mode precedence (kv > env), and the /recent DB helper."""
import pytest

from tsabot.db import Database
from tsabot.notifier import Notifier


class FakeUser:
    def __init__(self, uid):
        self.id = uid

    async def send(self, embed=None):
        SENDS.append(("dm", self.id, embed.title))


class FakeChannel:
    def __init__(self, cid):
        self.id = cid

    async def send(self, content=None, embed=None):
        SENDS.append(("log", self.id, embed.title))


SENDS: list = []


class FakeDB:
    def __init__(self):
        self.kv = {}
        self.owners = []

    def kv_get(self, guild_id, key, default=None):
        return self.kv.get(key, default)

    def kv_set(self, guild_id, key, value):
        self.kv[key] = value

    def list_owners(self, guild_id):
        return self.owners


class FakeCfg:
    def __init__(self, mode="log"):
        self.owner_ids = frozenset({7})
        self.notify_mode = mode
        self.mod_log_channel_id = 555


class FakeBot:
    def __init__(self, mode="log", dm_ok=True):
        self.cfg = FakeCfg(mode)
        self.db = FakeDB()
        self.dm_ok = dm_ok

    def get_user(self, uid):
        if not self.dm_ok:
            return None
        return FakeUser(uid)

    async def fetch_user(self, uid):
        if not self.dm_ok:
            raise RuntimeError("closed DMs")
        return FakeUser(uid)


class Guild:
    id = 42

    @staticmethod
    def get_channel(cid):
        return FakeChannel(cid)


@pytest.fixture(autouse=True)
def clear_sends():
    SENDS.clear()
    yield
    SENDS.clear()


def make(mode="log", dm_ok=True, log_channel=True):
    bot = FakeBot(mode=mode, dm_ok=dm_ok)
    if log_channel:
        bot.db.kv["mod_log_channel"] = "555"
    return Notifier(bot, db=bot.db, coalesce_window=0)


def titles(kind):
    return [t for (k, _i, t) in SENDS if k == kind]


@pytest.mark.asyncio
async def test_log_mode_case_is_channel_only():
    n = make(mode="log")
    await n.alert_owners(Guild(), title="Routine", body="b", severity="case")
    assert titles("dm") == []
    assert titles("log") == ["Routine"]


@pytest.mark.asyncio
async def test_log_mode_alert_still_dms_and_logs():
    n = make(mode="log")
    await n.alert_owners(Guild(), title="NUKE", body="b", severity="alert")
    assert titles("dm") == ["NUKE"]
    assert titles("log") == ["NUKE"]


@pytest.mark.asyncio
async def test_dm_mode_case_dms_only():
    n = make(mode="dm")
    await n.alert_owners(Guild(), title="Routine", body="b", severity="case")
    assert titles("dm") == ["Routine"]
    assert titles("log") == []


@pytest.mark.asyncio
async def test_both_mode_case_dms_and_logs():
    n = make(mode="both")
    await n.alert_owners(Guild(), title="Routine", body="b", severity="case")
    assert titles("dm") == ["Routine"]
    assert titles("log") == ["Routine"]


@pytest.mark.asyncio
async def test_kv_override_beats_env():
    n = make(mode="dm")
    n.db.kv_set(42, "notify_mode", "log")
    await n.alert_owners(Guild(), title="Routine", body="b", severity="case")
    assert titles("dm") == []
    assert titles("log") == ["Routine"]


@pytest.mark.asyncio
async def test_closed_dms_fall_back_to_log():
    n = make(mode="dm", dm_ok=False)
    await n.alert_owners(Guild(), title="Routine", body="b", severity="case")
    assert titles("dm") == []
    assert titles("log") == ["Routine"]


def test_default_mode_is_log():
    from tsabot.config import load_config
    cfg = load_config(env_file="nonexistent.env", env={"DISCORD_TOKEN": "x",
                                                       "DISCORD_GUILD_ID": "1"})
    assert cfg.notify_mode == "log"
    cfg2 = load_config(env_file="nonexistent.env", env={"DISCORD_TOKEN": "x",
                                                        "DISCORD_GUILD_ID": "1",
                                                        "NOTIFY_MODE": "both"})
    assert cfg2.notify_mode == "both"
    cfg3 = load_config(env_file="nonexistent.env", env={"DISCORD_TOKEN": "x",
                                                        "DISCORD_GUILD_ID": "1",
                                                        "NOTIFY_MODE": "garbage"})
    assert cfg3.notify_mode == "log"


def test_list_recent_orders_newest_first_and_filters(tmp_path):
    db = Database(tmp_path / "r.db")
    db.init()
    for i in range(12):
        db.add_case(guild_id=1, kind="report" if i % 2 else "vote", action="a",
                    target_id=9, reason=f"r{i}")
    rows = db.list_recent(guild_id=1, limit=5)
    assert len(rows) == 5
    assert [r["id"] for r in rows] == sorted([r["id"] for r in rows], reverse=True)
    votes = db.list_recent(guild_id=1, kind="vote", limit=20)
    assert votes and all(r["kind"] == "vote" for r in votes)
    assert db.list_recent(guild_id=2, limit=5) == []
