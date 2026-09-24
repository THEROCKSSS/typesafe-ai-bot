"""Vote tally + verdict math. Pure functions - no I/O, fully unit-tested."""
from __future__ import annotations

CHOICES = ("mute", "disconnect", "none")
# Tie-break preference (lower wins): mildest first, then the time-bounded
# action (mute auto-lifts after 1h), then disconnect.
_TIE_ORDER = {"none": 0, "mute": 1, "disconnect": 2}


def tally(ballots: list[str]) -> dict[str, int]:
    counts = {c: 0 for c in CHOICES}
    for b in ballots:
        if b in counts:
            counts[b] += 1
    return counts


def winner(counts: dict[str, int]) -> str | None:
    """Highest count wins; ties resolve toward the milder time-bounded action."""
    best = None
    best_count = 0
    for choice in CHOICES:
        n = counts.get(choice, 0)
        if n > best_count or (n == best_count and n > 0 and best is not None
                              and _TIE_ORDER[choice] < _TIE_ORDER[best]):
            best, best_count = choice, n
    if best_count == 0:
        return None
    return best


def verdict(counts: dict[str, int], *, min_votes: int, pct: float) -> tuple[str, str | None]:
    """Return (status, action) where status is 'passed' or 'failed'.

    passes when: total votes >= min_votes AND the winning choice is an
    enforcement action AND its share >= pct of all votes cast.
    """
    total = sum(counts.get(c, 0) for c in CHOICES)
    if total < min_votes:
        return "failed", None
    top = winner(counts)
    if top in (None, "none"):
        return "failed", None
    share = counts.get(top, 0) / total if total else 0.0
    if share >= pct:
        return "passed", top
    return "failed", None
