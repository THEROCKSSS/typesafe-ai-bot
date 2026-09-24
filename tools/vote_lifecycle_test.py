"""End-to-end vote lifecycle verification against the LIVE bot + database.

Simulates what happens when a vote's 10-minute deadline fires:
  1. insert a vote with a deadline in the past (as the scheduler would see)
  2. run the actual close path (Reports.close_expired_vote)
  3. verify: DB status, AI adjudication recorded, case written

Run standalone:  python tools/vote_lifecycle_test.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from datetime import timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tsabot.config import load_config                      # noqa: E402
from tsabot.db import Database, utcnow                      # noqa: E402


class FakeGuild:
    id = 1000000000000000001

    def get_member(self, _):
        return None

    def get_channel(self, _):
        return None


class FakeNotifier:
    def __init__(self):
        self.alerts = []

    async def alert_owners(self, guild, *, title, body, color=0, key=None):
        self.alerts.append((title, body))


class FakeBot:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.notifier = FakeNotifier()
        self.executor = None

        class _Loop:
            async def run_in_executor(self, _ex, fn, *a):
                return fn(*a)
        self.loop = _Loop()

        from tsabot.judge import JudgeChain
        self.judge = JudgeChain(cfg, db)

    def get_guild(self, _):
        return FakeGuild()


async def main() -> int:
    cfg = load_config(base=ROOT)
    db = Database(cfg.effective_db_path(ROOT))
    db.init()
    fails = []

    print("=" * 66)
    print("VOTE LIFECYCLE TEST — 10-minute timer → AI adjudication → enforce")
    print("=" * 66)

    # --- 1. create a vote whose deadline already passed (as the scheduler sees) ---
    deadline = utcnow() - timedelta(minutes=1)
    vote_id = db.create_vote(guild_id=cfg.guild_id, target_id=999999999,
                             reporter_id=111111111,
                             reason="They spammed slurs in the voice channel and ignored warnings",
                             judge={"reason_valid": {"type": "noul", "noul": 0.95}},
                             deadline_at=deadline,
                             target_name="test-griefer", reporter_name="test-reporter")
    db.add_job(guild_id=cfg.guild_id, kind="vote_deadline",
               payload={"vote_id": vote_id}, due_at=deadline)
    # enough ballots to pass: >=5 votes, >=60% mute
    for uid, choice in [(1, "mute"), (2, "mute"), (3, "mute"), (4, "mute"),
                        (5, "mute"), (6, "none")]:
        db.add_ballot(vote_id=vote_id, user_id=uid, choice=choice)
    print(f"\n[1] created vote #{vote_id} (deadline in the past)")
    print(f"    ballots: {db.ballot_counts(vote_id)}")

    # --- 2. the scheduler should see it due ---
    due = db.due_jobs()
    due_match = [j for j in due if j["kind"] == "vote_deadline"
                 and str(vote_id) in (j["payload_json"] or "")]
    print(f"\n[2] scheduler due jobs: {len(due)} (vote_deadline for #{vote_id}: "
          f"{bool(due_match)})")
    if not due_match:
        fails.append("vote_deadline job was not due")

    # --- 3. run the REAL close path from the cog ---
    from tsabot.cogs.reports import Reports
    bot = FakeBot(cfg, db)

    class FakeExecutor:
        def __init__(self):
            self.calls = []

        async def voice_mute(self, member, **kw):
            self.calls.append(("voice_mute", kw))
            return type("R", (), {"dry_run": False})()

        async def disconnect(self, member, **kw):
            self.calls.append(("disconnect", kw))
            return type("R", (), {"dry_run": False})()

        async def timeout(self, member, **kw):
            self.calls.append(("timeout", kw))
            return type("R", (), {"dry_run": False})()

    bot.executor = FakeExecutor()
    cog = Reports(bot)

    print("\n[3] closing vote via the real cog path (close_expired_vote)…")
    await cog.close_expired_vote(vote_id)

    # --- 4. verify outcomes ---
    row = db.get_vote(vote_id)
    print(f"\n[4] vote row after close:")
    print(f"    status      = {row['status']}")
    print(f"    action      = {row['action']}")
    print(f"    ai_verdict  = {row['ai_verdict']}")
    print(f"    ai_note     = {(row['ai_note'] or '')[:90]}")
    print(f"    closed_at   = {row['closed_at']}")

    if row["status"] not in ("passed", "overturned", "failed"):
        fails.append(f"status not resolved: {row['status']}")
    if row["closed_at"] is None:
        fails.append("closed_at not set")
    if row["ai_note"] is None:
        fails.append("AI adjudication was not recorded")

    # executor call (target member is None in the fake guild, so a pass may
    # legitimately skip enforcement — but AI review must still be recorded)
    print(f"\n[5] executor enforcement calls: {bot.executor.calls}")

    # case written with names
    cases = db.list_cases(guild_id=cfg.guild_id, target_id=999999999, limit=3)
    print(f"\n[6] cases written for this vote:")
    for c in cases:
        print(f"    #{c['id']} [{c['kind']}/{c['action']}] target={c['target_name']} "
              f"reason={(c['reason'] or '')[:60]}")
    if not cases:
        fails.append("no case written for the vote")

    print(f"\n[7] owner alerts: {len(bot.notifier.alerts)}")
    for t, b in bot.notifier.alerts:
        print(f"    · {t}: {b[:70]}")

    # clean up this synthetic vote + job so it doesn't pollute the live DB
    db.execute("DELETE FROM vote_ballots WHERE vote_id=?", (vote_id,))
    db.execute("DELETE FROM votes WHERE id=?", (vote_id,))
    db.execute("DELETE FROM scheduled_jobs WHERE payload_json LIKE ?",
               (f'%"vote_id": {vote_id}%',))
    db.execute("DELETE FROM cases WHERE target_id=999999999")
    print("\n[8] synthetic rows cleaned up")

    print("\n" + "=" * 66)
    if fails:
        print("FAILED:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    print("PASSED — vote closed, AI reviewed the outcome, case recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
