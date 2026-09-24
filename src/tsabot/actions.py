"""The single actions executor. EVERY enforcement flows through here.

DRY-RUN support: when on, enforcement calls are recorded as would-have-happened
(log + case + DM) but not performed. When off (default), they execute.

Action kinds:
  timeout(member, minutes)     - Discord native timeout (text+voice)
  voice_mute(member, minutes)  - server voice mute, auto-lifted via scheduler
  voice_unmute(member)         - lifts a voice mute
  disconnect(member)           - removes from voice channel
  warn(member, reason)         - logged warning, no enforcement
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .db import utcnow


@dataclass
class ActionResult:
    kind: str
    executed: bool          # True if actually applied to Discord
    dry_run: bool
    detail: str = ""


def _display_name(obj) -> str | None:
    """Best display name for a member/user-like object."""
    if obj is None:
        return None
    for attr in ("display_name", "global_name", "name", "username"):
        v = getattr(obj, attr, None)
        if v:
            return str(v)
    text = str(obj)
    return text if text else None


def _oid(obj) -> int | None:
    return getattr(obj, "id", None) if obj is not None else None


class Executor:
    def __init__(self, *, db, notify=None, dry_run: bool = False):
        self.db = db
        self.notify = notify
        self.dry_run = dry_run

    # ---- helpers ----------------------------------------------------
    def _case(self, *, guild_id: int, kind: str, action: str, target=None,
              actor=None, reporter=None, reason=None, detail=None,
              voice=None) -> int:
        return self.db.add_case(
            guild_id=guild_id, kind=kind, action=action,
            target_id=_oid(target), actor_id=_oid(actor), reporter_id=_oid(reporter),
            target_name=_display_name(target), actor_name=_display_name(actor),
            reporter_name=_display_name(reporter), voice_channel=voice,
            reason=reason, detail=detail, dry_run=self.dry_run)

    async def _dm_owners(self, guild, *, title: str, body: str, color: int = 0xE8A33D):
        if self.notify is not None:
            await self.notify.alert_owners(guild, title=title, body=body, color=color,
                                           severity="case")

    @staticmethod
    def _voice_of(member) -> str | None:
        vc = getattr(getattr(member, "voice", None), "channel", None)
        return getattr(vc, "name", None) if vc else None

    @staticmethod
    def _label(obj) -> str:
        name = _display_name(obj) or "unknown"
        oid = _oid(obj)
        return f"{name} (`{oid}`)" if oid else name

    # ---- actions ----------------------------------------------------
    async def timeout(self, member, *, minutes: int, reason: str, guild_id: int,
                      reporter=None, actor=None, kind: str = "moderation") -> ActionResult:
        detail = f"timeout {minutes}m on {_display_name(member)}#{_oid(member)}"
        self._case(guild_id=guild_id, kind=kind, action="timeout", target=member,
                   actor=actor, reporter=reporter, reason=reason,
                   detail={"minutes": minutes}, voice=self._voice_of(member))
        if not self.dry_run:
            try:
                await member.timeout(timedelta(minutes=minutes), reason=reason)
            except Exception as e:  # noqa: BLE001
                return ActionResult("timeout", False, self.dry_run,
                                    f"could not apply: {e}")
        await self._dm_owners(
            getattr(member, "guild", None),
            title=("DRY-RUN: timeout (suppressed)" if self.dry_run else "Timeout applied"),
            body=f"**{self._label(member)}** — {minutes} min\nReason: {reason}",
            color=0xE8A33D)
        return ActionResult("timeout", not self.dry_run, self.dry_run, detail)

    async def voice_mute(self, member, *, minutes: int, reason: str, guild_id: int,
                         reporter=None, actor=None, kind: str = "moderation") -> ActionResult:
        """Voice server-mute; schedules the auto-lift job."""
        detail = f"voice mute {minutes}m on {_display_name(member)}#{_oid(member)}"
        self._case(guild_id=guild_id, kind=kind, action="voice_mute", target=member,
                   actor=actor, reporter=reporter, reason=reason,
                   detail={"minutes": minutes}, voice=self._voice_of(member))
        if not self.dry_run:
            try:
                await member.edit(mute=True, reason=reason)
            except Exception as e:  # noqa: BLE001
                return ActionResult("voice_mute", False, self.dry_run,
                                    f"could not apply: {e}")
            self.db.add_job(guild_id=guild_id, kind="voice_unmute",
                            payload={"member_id": member.id, "reason": reason},
                            due_at=utcnow() + timedelta(minutes=minutes))
        await self._dm_owners(
            getattr(member, "guild", None),
            title=("DRY-RUN: voice mute (suppressed)" if self.dry_run else "Voice mute applied"),
            body=f"**{self._label(member)}** — voice muted {minutes} min "
                 f"(auto-lifts)\nReason: {reason}",
            color=0xE8A33D)
        return ActionResult("voice_mute", not self.dry_run, self.dry_run, detail)

    async def voice_unmute(self, member, *, guild_id: int,
                           reason: str = "auto-lift after voice mute") -> ActionResult:
        self._case(guild_id=guild_id, kind="moderation", action="voice_unmute",
                   target=member, reason=reason)
        if not self.dry_run:
            try:
                await member.edit(mute=False, reason=reason)
            except Exception as e:  # noqa: BLE001
                return ActionResult("voice_unmute", False, self.dry_run,
                                    f"could not apply: {e}")
        return ActionResult("voice_unmute", not self.dry_run, self.dry_run,
                            f"unmuted {_display_name(member)}")

    async def disconnect(self, member, *, reason: str, guild_id: int,
                         reporter=None, actor=None) -> ActionResult:
        detail = f"disconnect {_display_name(member)}#{_oid(member)}"
        voice = self._voice_of(member)
        self._case(guild_id=guild_id, kind="moderation", action="disconnect",
                   target=member, actor=actor, reporter=reporter, reason=reason,
                   voice=voice)
        if not self.dry_run:
            try:
                await member.move_to(None, reason=reason)
            except Exception as e:  # noqa: BLE001
                return ActionResult("disconnect", False, self.dry_run,
                                    f"could not apply: {e}")
        await self._dm_owners(
            getattr(member, "guild", None),
            title=("DRY-RUN: disconnect (suppressed)" if self.dry_run
                   else "Disconnected from voice"),
            body=f"**{self._label(member)}**"
                 + (f"\nFrom: {voice}" if voice else "")
                 + f"\nReason: {reason}",
            color=0xE8A33D)
        return ActionResult("disconnect", not self.dry_run, self.dry_run, detail)

    async def warn(self, member, *, reason: str, guild_id: int, actor=None) -> ActionResult:
        self._case(guild_id=guild_id, kind="moderation", action="warn",
                   target=member, actor=actor, reason=reason)
        return ActionResult("warn", True, self.dry_run,
                            f"warned {_display_name(member)}")

    async def lockdown(self, member, *, reason: str, guild_id: int,
                       evidence: str, stripped: list[str]) -> ActionResult:
        self._case(guild_id=guild_id, kind="antinuke", action="lockdown",
                   target=member, reason=reason,
                   detail={"evidence": evidence, "stripped": stripped})
        return ActionResult("lockdown", not self.dry_run, self.dry_run,
                            f"lockdown on {_display_name(member)}")
