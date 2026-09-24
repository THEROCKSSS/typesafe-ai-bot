"""Antinuke cog: audit-log watcher → lockdown + owner alerts."""
from __future__ import annotations

import discord
from discord.ext import commands

from ..antinuke import DANGEROUS_PERMS


class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _trusted(self, member: discord.Member) -> bool:
        if self.bot.is_owner(member.id):
            return True
        # nuke_trusted capability
        from ..caps import has_cap, resolve_caps
        stored = self.bot.db.role_caps(guild_id=member.guild.id,
                                       role_ids=[r.id for r in member.roles])
        caps = resolve_caps(role_caps=stored, is_owner=False)
        return has_cap(caps, "nuke_trusted")

    async def _act_on(self, actor: discord.Member, kind: str, evidence: str):
        if self._trusted(actor):
            return
        reason = self.bot.nuke_watcher.record(actor.id, kind)
        if reason is None:
            return
        self.bot.nuke_watcher.reset(actor.id)
        await self.lockdown(actor, reason=reason, evidence=evidence)

    async def lockdown(self, actor: discord.Member, *, reason: str, evidence: str) -> None:
        guild = actor.guild
        dry = self.bot.cfg.dry_run
        stripped: list[str] = []
        if not dry:
            for role in actor.roles:
                if role.is_default() or role.managed or role >= guild.me.top_role:
                    continue
                overwrite = {p: False for p in DANGEROUS_PERMS
                             if getattr(role.permissions, p, False)}
                if not overwrite:
                    continue
                try:
                    new_perms = discord.Permissions(role.permissions.value)
                    for p in overwrite:
                        setattr(new_perms, p, False)
                    await role.edit(permissions=new_perms,
                                    reason=f"antinuke lockdown: {reason}")
                    stripped.append(role.name)
                except Exception:
                    pass
        self.bot.db.add_case(guild_id=guild.id, kind="antinuke", action="lockdown",
                             target_id=actor.id, target_name=str(actor),
                             reason=reason,
                             detail={"evidence": evidence, "stripped": stripped})
        await self.bot.notifier.alert_owners(
            guild, title=("DRY-RUN: nuke lockdown (suppressed)" if dry else "🚨 NUKE LOCKDOWN"),
            body=f"**Actor:** {actor}\n**Trip:** {reason}\n**Evidence:** {evidence}\n"
                 f"**Roles stripped:** {', '.join(stripped) or '(dry-run: none)'}",
            color=0xB91C1C, key=f"nuke-{actor.id}-{reason}")

    # ---- audit listeners --------------------------------------------
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        actor = await self._audit_actor(channel.guild,
                                        discord.AuditLogAction.channel_delete,
                                        channel.id)
        if actor:
            await self._act_on(actor, "channel_delete", f"deleted #{channel.name}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        actor = await self._audit_actor(role.guild, discord.AuditLogAction.role_delete,
                                        role.id)
        if actor:
            await self._act_on(actor, "role_delete", f"deleted role {role.name}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        actor = await self._audit_actor(guild, discord.AuditLogAction.ban, user.id)
        if actor:
            await self._act_on(actor, "ban", f"banned {user}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        actor = await self._audit_actor(member.guild, discord.AuditLogAction.kick,
                                        member.id)
        if actor:
            await self._act_on(actor, "kick", f"kicked {member}")

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        # newer discord.py delivers entries here too; only webhook creates need care
        if entry.action == discord.AuditLogAction.webhook_create:
            actor = entry.user
            if isinstance(actor, discord.Member):
                await self._act_on(actor, "webhook_create",
                                   f"created webhook {getattr(entry.target, 'name', '?')}")

    async def _audit_actor(self, guild: discord.Guild,
                           action: discord.AuditLogAction, target_id: int):
        try:
            async for entry in guild.audit_logs(limit=6, action=action):
                if entry.target and getattr(entry.target, "id", None) == target_id:
                    return entry.user if isinstance(entry.user, discord.Member) else None
        except Exception:
            return None
        return None


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
