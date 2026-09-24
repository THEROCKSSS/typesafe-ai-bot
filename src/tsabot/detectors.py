"""Sliding-window spam detectors. Pure in-memory math, unit-tested."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class SpamThresholds:
    burst_count: int = 6
    burst_window: float = 5.0
    duplicate_count: int = 4
    duplicate_window: float = 30.0
    mention_count: int = 6
    mention_window: float = 10.0
    link_count: int = 4
    link_window: float = 20.0


@dataclass
class Trip:
    kind: str
    detail: str


@dataclass
class _Event:
    ts: float
    content_hash: str
    mentions: int
    has_link: bool


class SpamDetector:
    """Records per-user message events and reports trips.

    After a trip fires, that window's events are dropped so the same burst
    does not re-trip on every subsequent message (cooldown behaviour).
    """

    def __init__(self, thresholds: SpamThresholds | None = None):
        self.th = thresholds or SpamThresholds()
        self._events: dict[int, deque[_Event]] = {}

    def record(self, user_id: int, *, content_hash: str, mentions: int = 0,
               has_link: bool = False, ts: float | None = None) -> list[Trip]:
        ts = ts if ts is not None else time.time()
        q = self._events.setdefault(user_id, deque())
        q.append(_Event(ts=ts, content_hash=content_hash, mentions=mentions, has_link=has_link))
        self._prune(q, ts, max_window=self._max_window())

        trips: list[Trip] = []

        burst = [e for e in q if ts - e.ts <= self.th.burst_window]
        if len(burst) >= self.th.burst_count:
            trips.append(Trip("burst", f"{len(burst)} messages in {self.th.burst_window:.0f}s"))
            self._drop(q, ts, self.th.burst_window)

        dup = [e for e in q if ts - e.ts <= self.th.duplicate_window
               and e.content_hash == content_hash]
        if len(dup) >= self.th.duplicate_count:
            trips.append(Trip("duplicate", f"{len(dup)} identical messages in "
                                          f"{self.th.duplicate_window:.0f}s"))
            self._drop(q, ts, self.th.duplicate_window)

        mentions_sum = sum(e.mentions for e in q if ts - e.ts <= self.th.mention_window)
        if mentions_sum >= self.th.mention_count:
            trips.append(Trip("mass_mention", f"{mentions_sum} mentions in "
                                              f"{self.th.mention_window:.0f}s"))
            self._drop(q, ts, self.th.mention_window)

        links = sum(1 for e in q if ts - e.ts <= self.th.link_window and e.has_link)
        if links >= self.th.link_count:
            trips.append(Trip("link_flood", f"{links} links in {self.th.link_window:.0f}s"))
            self._drop(q, ts, self.th.link_window)

        return trips

    # ---- helpers ----------------------------------------------------
    def _max_window(self) -> float:
        return max(self.th.burst_window, self.th.duplicate_window,
                   self.th.mention_window, self.th.link_window)

    @staticmethod
    def _prune(q: deque[_Event], now: float, max_window: float) -> None:
        while q and now - q[0].ts > max_window:
            q.popleft()

    @staticmethod
    def _drop(q: deque[_Event], now: float, window: float) -> None:
        keep = deque(e for e in q if now - e.ts > window)
        q.clear()
        q.extend(keep)


import re

_LINK_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def has_link(content: str) -> bool:
    return bool(_LINK_RE.search(content))


def count_mentions(content: str, mention_ids: list[int] | None = None,
                   everyone: bool = False) -> int:
    n = len(mention_ids or [])
    if "@everyone" in content or "@here" in content or everyone:
        n += 3
    if "<@&" in content:  # role mentions
        n += content.count("<@&")
    return n
