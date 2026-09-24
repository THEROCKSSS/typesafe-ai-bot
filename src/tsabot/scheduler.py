"""Persisted scheduler: vote deadlines + voice-mute lifts survive restarts.

Jobs live in SQLite (`scheduled_jobs`). On startup the bot re-arms outstanding
jobs (they are simply due-checked on the loop), so nothing is lost.
"""
from __future__ import annotations

import asyncio
import contextlib
import json

from .db import utcnow


class Scheduler:
    def __init__(self, bot, *, db, interval: float = 10.0):
        self.bot = bot
        self.db = db
        self.interval = interval
        self._task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(self._loop(), name="tsabot-scheduler")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self.tick()
            except Exception as e:  # noqa: BLE001
                print(f"[scheduler] tick error: {e}")
            await asyncio.sleep(self.interval)

    async def tick(self) -> int:
        """Process due jobs. Returns count processed."""
        n = 0
        for row in self.db.due_jobs():
            payload = json.loads(row["payload_json"] or "{}")
            try:
                await self._handle(row["kind"], row["guild_id"], payload)
                self.db.mark_job(row["id"], "done")
            except Exception as e:  # noqa: BLE001
                self.db.mark_job(row["id"], "failed", error=str(e)[:300])
            n += 1
        return n

    async def _handle(self, kind: str, guild_id: int, payload: dict) -> None:
        if kind == "voice_unmute":
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            member = guild.get_member(int(payload["member_id"]))
            if member is None:
                member = await guild.fetch_member(int(payload["member_id"]))
            executor = getattr(self.bot, "executor", None)
            if member is not None and executor is not None:
                await executor.voice_unmute(member, guild_id=guild_id,
                                            reason="auto-lift after 1h voice mute")
        elif kind == "vote_deadline":
            votes_cog = self.bot.get_cog("Votes")
            if votes_cog is not None:
                await votes_cog.close_expired_vote(int(payload["vote_id"]))
        elif kind == "judge_recovery_probe":
            judge = getattr(self.bot, "judge", None)
            if judge is not None and judge.breaker_open is False:
                pass  # probing happens implicitly on next call tick
