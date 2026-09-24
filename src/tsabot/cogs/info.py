"""`/jev`, `/config`, `/help` — judge status, configuration, help."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..caps import resolve_caps, has_cap


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="jev", description="Judge chain status: model, spend, outage state")
    async def jev(self, interaction: discord.Interaction):
        stats = self.bot.db.judge_stats(hours=24)
        status = self.bot.judge.status() if self.bot.judge else {}
        embed = discord.Embed(title="Jev judge chain", color=0x818CF8)
        embed.add_field(name="Layer 1 (primary)",
                        value=f"TypeSafe Jev `{self.bot.cfg.jev_model}`\n"
                              f"{'⚠️ outage — fallback active' if status.get('outage') else 'healthy'}",
                        inline=False)
        embed.add_field(name="24h calls", value=str(stats["calls"]), inline=True)
        embed.add_field(name="Success", value=f"{stats['ok']}/{stats['calls']}", inline=True)
        embed.add_field(name="Tokens (in)", value=f"{stats['tokens']:,}", inline=True)
        embed.add_field(name="Est. cost", value=f"${stats['est_cost_usd']:.4f}", inline=True)
        embed.add_field(name="Avg latency", value=f"{stats['avg_latency_ms']} ms", inline=True)
        by_layer = ", ".join(f"{k}: {v}" for k, v in stats["by_layer"].items()) or "—"
        embed.add_field(name="By layer", value=by_layer, inline=False)
        err = self.bot.db.last_judge_error()
        if err:
            embed.add_field(name="Last error", value=err[:200], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="config", description="View or set bot configuration")
    @app_commands.describe(key="Setting name", value="New value")
    async def config(self, interaction: discord.Interaction, key: str | None = None,
                     value: str | None = None):
        db = self.bot.db
        if key and value is not None:
            stored = db.role_caps(guild_id=interaction.guild.id,
                                  role_ids=[r.id for r in interaction.user.roles])
            caps = resolve_caps(role_caps=stored, is_owner=self.bot.is_owner(interaction.user.id))
            if not (has_cap(caps, "config_jev") or self.bot.is_owner(interaction.user.id)):
                await interaction.response.send_message("You lack the config capability.",
                                                        ephemeral=True)
                return
            db.kv_set(interaction.guild.id, key, value)
            await interaction.response.send_message(f"Set `{key}` = `{value}`.", ephemeral=True)
            await self.bot.notifier.alert_owners(
                interaction.guild, title="Config changed",
                body=f"{interaction.user}: `{key}` → `{value}`", color=0x818CF8,
                key=f"cfg-{key}-{value}")
            return
        kv = db.kv_all(interaction.guild.id)
        cfg = self.bot.cfg
        lines = [
            f"`dry_run` = **{cfg.dry_run}** (env: DRY_RUN)",
            f"`reports_channel` = {kv.get('reports_channel', cfg.reports_channel_id or '—')}",
            f"`mod_log_channel` = {kv.get('mod_log_channel', cfg.mod_log_channel_id or '—')}",
            f"`vote_role` = {kv.get('vote_role', cfg.vote_role_id or '—')}",
            f"`spam_timeout_minutes` = {cfg.spam_timeout_minutes}",
            f"`vote_min` = {cfg.vote_min} · `vote_pct` = {cfg.vote_pct} · `vote_minutes` = {cfg.vote_minutes}",
        ]
        embed = discord.Embed(title="Configuration",
                              description="\n".join(lines) +
                              "\n\nSet with `/config <key> <value>` (e.g. "
                              "`/config reports_channel 123456789`).",
                              color=0x818CF8)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="What this bot does and how to use it")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="TypeSafe AI Bot", color=0x6EE7B7,
                              description="AI-assisted moderation, judged by TypeSafe Jev.")
        embed.add_field(name="Members", value=(
            "`/report @user` — report someone (a written reason is required)\n"
            "Right-click a message → **Report to mods**\n"
            "`/votes` — see open votes"), inline=False)
        embed.add_field(name="Moderators", value=(
            "`/case @user` — history · `/panel @user` — quick actions\n"
            "`/warn` `/mute` `/disconnect` · `/veto <id>` — cancel a vote\n"
            "`/recent` — newest cases · `/me` — what can I do?"), inline=False)
        embed.add_field(name="Owners", value=(
            "`/setup` — role → capability permissions\n"
            "`/owners add|remove|list` — owner management\n"
            "`/notify` — log-only vs DM alerts (default: log channel)\n"
            "`/jev` — judge status · `/config` — settings\n"
            "`/status` — bot health"), inline=False)
        embed.set_footer(text="TypeSafe AI Bot — DRY-RUN until you flip DRY_RUN=0 in .env")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot))
