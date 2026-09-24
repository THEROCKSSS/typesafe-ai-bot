"""Spam / rate-limit protection: sliding windows → timeout + notice + owner DMs.
Exempt roles (spam_exempt capability) skip filters."""
from __future__ import annotations

import hashlib

import discord
from discord.ext import commands

from ..caps import has_cap, resolve_caps
from ..detectors import SpamDetector, count_mentions, has_link


class Spam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.detector = SpamDetector()

    def _spam_exempt(self, member: discord.Member) -> bool:
        if self.bot.is_owner(member.id):
            return True
        stored = self.bot.db.role_caps(guild_id=member.guild.id,
                                       role_ids=[r.id for r in member.roles])
        caps = resolve_caps(role_caps=stored, is_owner=False)
        return has_cap(caps, "spam_exempt")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.guild.id != self.bot.cfg.guild_id:
            return
        member = message.author
        if self._spam_exempt(member):
            return
        content = message.content or ""
        if not content and not message.attachments:
            return
        h = hashlib.sha1(content.encode("utf-8", "replace")).hexdigest()
        mentions = count_mentions(content, [m.id for m in message.mentions],
                                  everyone=message.mention_everyone)
        trips = self.detector.record(member.id, content_hash=h, mentions=mentions,
                                     has_link=has_link(content))
        if not trips:
            return
        trip = trips[0]
        minutes = self.bot.cfg.spam_timeout_minutes
        res = await self.bot.executor.timeout(
            member, minutes=minutes,
            reason=f"spam/{trip.kind}: {trip.detail}",
            guild_id=message.guild.id, kind="spam")
        try:
            await message.channel.send(
                f"🛑 {member.mention} auto-timeouted for {minutes}m (spam protection — "
                f"{trip.kind})" + (" *(dry-run: not enforced)*" if res.dry_run else ""))
        except Exception:
            pass
        await self.bot.notifier.alert_owners(
            message.guild, title="Spam timeout",
            body=f"**Member:** {member}\n**Detector:** {trip.kind} — {trip.detail}\n"
                 f"**Timeout:** {minutes}m" + (" **(dry-run)**" if res.dry_run else ""),
            color=0xEF4444, key=f"spam-{member.id}-{trip.kind}")


async def setup(bot):
    await bot.add_cog(Spam(bot))
