"""Owner notifications with severity routing and log-channel-first delivery.

Events carry a severity:
  - "alert"  (critical: nuke trips, spam timeouts, judge outages, config changes)
  - "case"   (routine case flow: reports, votes, verdicts)

Routing follows notify_mode ("log" default | "dm" | "both"; per-guild override
via kv `notify_mode`, changed live with /notify set):
  - log    routine events post to the mod-log channel ONLY — owners are DM'd
           just for "alert" severity
  - dm     every event DMs all owners (legacy behaviour); alerts are also
           mirrored to the log channel
  - both   every event DMs all owners AND lands in the log channel
"alert" severity always lands in the log channel too — the log is the durable
record even when DMs are on.
Closed DMs fall back to the log channel with a visible mention.
Bursts coalesce: duplicate alerts within `coalesce_window` are folded into one.
"""
from __future__ import annotations

import time
from collections import defaultdict

import discord

NOTIFY_MODES = ("dm", "log", "both")


class Notifier:
    def __init__(self, bot, *, db, coalesce_window: float = 20.0):
        self.bot = bot
        self.db = db
        self.coalesce_window = coalesce_window
        self._recent: dict[str, float] = defaultdict(float)

    # ---- owner resolution ------------------------------------------
    def owner_ids_for(self, guild) -> set[int]:
        ids: set[int] = set(self.bot.cfg.owner_ids)
        try:
            for row in self.db.list_owners(guild.id):
                if row["kind"] == "user":
                    ids.add(int(row["subject_id"]))
                elif row["kind"] == "role":
                    role = guild.get_role(int(row["subject_id"]))
                    if role:
                        ids.update(m.id for m in role.members)
        except Exception:
            pass
        return ids

    # ---- routing ------------------------------------------------------
    def mode_for(self, guild) -> str:
        """Effective notify mode: per-guild DB override beats env config."""
        try:
            mode = self.db.kv_get(guild.id, "notify_mode")
        except Exception:
            mode = None
        mode = (mode or getattr(self.bot.cfg, "notify_mode", "log") or "log").strip().lower()
        return mode if mode in NOTIFY_MODES else "log"

    # ---- core send --------------------------------------------------
    async def alert_owners(self, guild, *, title: str, body: str,
                           color: int = 0xE8A33D, key: str | None = None,
                           severity: str = "alert") -> None:
        """Deliver an embed following notify_mode + severity (see module doc)."""
        now = time.time()
        dedup_key = key or f"{title}:{body[:80]}"
        if now - self._recent.get(dedup_key, 0) < self.coalesce_window:
            return
        self._recent[dedup_key] = now

        embed = discord.Embed(title=title, description=body[:3800],
                              color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text="TypeSafe AI Bot")

        mode = self.mode_for(guild) if guild is not None else "dm"
        is_alert = severity == "alert"
        dm = is_alert or mode in ("dm", "both")
        log = is_alert or mode in ("log", "both")

        delivered = 0
        if dm and guild is not None:
            for uid in self.owner_ids_for(guild):
                try:
                    user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                    if user:
                        await user.send(embed=embed)
                        delivered += 1
                except Exception:
                    pass
        if guild is not None and (log or (dm and not delivered)):
            await self._post_log(guild, embed, mention=(dm and not delivered))

    async def _post_log(self, guild, embed: discord.Embed, *,
                        mention: bool = False) -> None:
        ch_id = self.bot.cfg.mod_log_channel_id or self.db.kv_get(guild.id, "mod_log_channel")
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if ch:
            try:
                await ch.send(content="⚠️ Owner DMs unreachable — alert posted here:"
                              if mention else None, embed=embed)
            except Exception:
                pass
