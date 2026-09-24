"""Automod: screen every guild message against the rulebook via ONE batched
Jev call. DRY-RUN default: logs + DMs, enforcement suppressed until live."""
from __future__ import annotations

import hashlib

import discord
from discord.ext import commands

from ..policy import decide, RulebookError


class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache: dict[str, str] = {}

    def _ignored_channel(self, channel_id: int) -> bool:
        raw = self.bot.db.kv_get(0, f"ignore_channel_{channel_id}")
        return raw == "1"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        # Webhook messages from the configured TEST webhook are screened like
        # member messages (this is the real-time detection test feed).
        is_test_webhook = (message.webhook_id is not None
                           and self.bot.cfg.test_webhook_id is not None
                           and message.webhook_id == self.bot.cfg.test_webhook_id)
        if message.author.bot and not is_test_webhook:
            return
        if message.guild.id != self.bot.cfg.guild_id:
            return
        if not is_test_webhook and self.bot.is_owner(message.author.id):
            return
        if self._ignored_channel(message.channel.id):
            return
        content = message.content or ""
        if len(content) < 3:
            return
        # dedupe identical consecutive content per channel (cheap cache)
        h = hashlib.sha1(content.encode("utf-8", "replace")).hexdigest()
        ck = f"{message.channel.id}:{message.author.id}"
        if self._cache.get(ck) == h:
            return
        self._cache[ck] = h
        if len(self._cache) > 5000:
            self._cache.clear()

        try:
            rules = self.bot.rules()
        except RulebookError as e:
            print(f"[automod] rulebook error: {e}")
            return

        result = await self.bot.loop.run_in_executor(
            None,
            lambda: self.bot.judge.ask_message(
                content=content, author=str(message.author),
                channel=str(getattr(message.channel, "name", message.channel.id)),
                rules=rules))
        if result.layer != "jev":
            # Judge degraded. Heuristics may ONLY route obvious severe content to
            # humans as a review flag — never auto-enforce on a guess.
            heuristic = (result.verdicts or {}).get("_heuristic") or {}
            if not heuristic.get("flagged"):
                return
            hits = ", ".join(heuristic.get("hits", [])) or "—"
            author_name = getattr(message.author, "display_name", None) or str(message.author)
            self.bot.db.add_case(
                guild_id=message.guild.id, kind="automod", action="review",
                target_id=message.author.id, target_name=author_name,
                reason=f"heuristic: {hits}",
                detail={"layer": result.layer, "error": result.error,
                        "message_id": message.id, "content": content[:200],
                        "channel_id": message.channel.id})
            await self.bot.notifier.alert_owners(
                message.guild, title="Possible rule break — judge offline (heuristic)",
                body=(f"**Channel:** {message.channel.mention}\n**Author:** {message.author}\n"
                      f"**Heuristic hits:** {hits}\n"
                      f"**Judge layer:** {result.layer} — {result.error or 'degraded'}\n"
                      f"**Content:** {content[:300]}\n[Jump]({message.jump_url})\n\n"
                      f"_No automatic action taken — human review required._"),
                color=0xF59E0B, key=f"heur-{message.id}", severity="case")
            return

        decisions = decide(rules, result.verdicts, high=self.bot.cfg.automod_high,
                           medium=self.bot.cfg.automod_medium)
        if not decisions:
            return
        top = decisions[0]

        if top.outcome == "action" and top.action == "timeout":
            rule = next((r for r in rules if r["id"] == top.rule_id), {})
            minutes = int(rule.get("timeout_minutes", 10))
            is_member = isinstance(message.author, discord.Member)
            if is_member:
                res = await self.bot.executor.timeout(
                    message.author, minutes=minutes, reason=top.reason,
                    guild_id=message.guild.id, kind="automod")
                footer = " *(dry-run: not enforced)*" if res.dry_run else ""
            else:
                # webhook/test author — no Member to time out; record the decision only
                self.bot.db.add_case(
                    guild_id=message.guild.id, kind="automod", action="timeout",
                    target_id=message.author.id,
                    target_name=getattr(message.author, "display_name", None)
                    or str(message.author),
                    reason=f"[webhook feed] {top.reason}",
                    detail={"rule": top.rule_id, "p": top.probability,
                            "webhook": True, "message_id": message.id,
                            "content": content[:200]}, dry_run=self.bot.cfg.dry_run)
                footer = " *(test-feed author — logged, no timeout target)*"
            try:
                await message.channel.send(
                    f"⚠️ auto-timeout matched — {top.rule_title} "
                    f"(p={top.probability:.2f}){footer}")
            except Exception:
                pass
        else:
            # review path: DM owners, nothing enforced
            await self.bot.notifier.alert_owners(
                message.guild, title="Message flagged for review",
                body=f"**Channel:** {message.channel.mention}\n**Author:** {message.author}\n"
                     f"**Rule:** {top.rule_title} (p={top.probability:.2f})\n"
                     f"**Content:** {content[:300]}\n"
                     f"[Jump]({message.jump_url})",
                color=0xF59E0B, key=f"review-{message.id}", severity="case")


async def setup(bot):
    await bot.add_cog(Automod(bot))
