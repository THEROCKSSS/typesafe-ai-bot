"""Capability registry + checks. Pure logic, unit-tested."""
from __future__ import annotations

CAPABILITY_GROUPS: dict[str, list[str]] = {
    "Moderation": ["warn", "mute_1h", "disconnect", "case_view"],
    "Reports & votes": ["review_reports", "override_votes", "vote_start"],
    "Configuration": ["config_spam", "config_nuke", "config_jev", "config_vote"],
    "Exemptions": ["spam_exempt", "nuke_trusted", "vote_immune"],
}

ALL_CAPS: tuple[str, ...] = tuple(c for group in CAPABILITY_GROUPS.values() for c in group)


def has_cap(member_caps: set[str], needed: str) -> bool:
    return needed in member_caps


def resolve_caps(*, role_caps: set[str], is_owner: bool, owner_role: bool = False) -> set[str]:
    """Effective capability set for a member."""
    if is_owner or owner_role:
        return set(ALL_CAPS)
    return set(role_caps)
