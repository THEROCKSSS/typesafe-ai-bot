"""Nuke protection: audit-log watcher + lockdown.

Correlates destructive events per actor in a sliding window. Actors outside
the trusted set tripping thresholds get locked down via the executor:
  - dangerous perms stripped from their roles (manage_guild, ban, kick, etc.)
  - invites paused (audit for new invites is manual in v1; we lock the actor)
Thresholds configurable; `nuke_trusted` exemption capability exists.
DRY-RUN records would-have-lockdowns without stripping anything.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class NukeThresholds:
    channel_deletes: int = 3
    role_deletes: int = 2
    bans_kicks: int = 5
    webhook_creates: int = 2
    window_seconds: float = 30.0


DANGEROUS_PERMS = (
    "manage_guild", "ban_members", "kick_members", "manage_roles",
    "manage_channels", "mention_everyone", "administrator",
)


class NukeWatcher:
    def __init__(self, thresholds: NukeThresholds | None = None):
        self.th = thresholds or NukeThresholds()
        self._events: dict[int, list[tuple[float, str]]] = defaultdict(list)

    def record(self, actor_id: int, event_kind: str, *, ts: float | None = None) -> str | None:
        """Record one destructive event; return a trip reason if thresholds break."""
        ts = ts if ts is not None else time.time()
        events = self._events[actor_id]
        events.append((ts, event_kind))
        cutoff = ts - self.th.window_seconds
        self._events[actor_id] = [e for e in events if e[0] >= cutoff]

        counts: dict[str, int] = defaultdict(int)
        for _, kind in self._events[actor_id]:
            counts[kind] += 1

        if counts["channel_delete"] >= self.th.channel_deletes:
            return f"{counts['channel_delete']} channel deletes in {self.th.window_seconds:.0f}s"
        if counts["role_delete"] >= self.th.role_deletes:
            return f"{counts['role_delete']} role deletes in {self.th.window_seconds:.0f}s"
        if counts["ban"] + counts["kick"] >= self.th.bans_kicks:
            return f"{counts['ban'] + counts['kick']} bans/kicks in {self.th.window_seconds:.0f}s"
        if counts["webhook_create"] >= self.th.webhook_creates:
            return f"{counts['webhook_create']} webhook creates in {self.th.window_seconds:.0f}s"
        return None

    def reset(self, actor_id: int) -> None:
        self._events.pop(actor_id, None)


AUDIT_EVENT_KINDS = {
    "channel_delete": "channel_delete",
    "role_delete": "role_delete",
    "ban": "ban",
    "kick": "kick",
    "webhook_create": "webhook_create",
}
