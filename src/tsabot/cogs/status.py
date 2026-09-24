"""`/status` — rich bot state: version, uptime, DRY-RUN, judge health, activity."""
from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from .. import __version__


def _uptime_str(seconds: float) -> str:
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status",
                          description="Bot status: uptime, mode, judge health, activity")
    async def status(self, interaction: discord.Interaction):
        now = time.time()
        uptime = _uptime_str(now - getattr(self.bot, "start_epoch", now))
        guild = self.bot.target_guild
        db = self.bot.db

        stats = {"cases": 0, "open_votes": 0, "jobs": 0}
        js = {"calls": 0, "ok": 0, "avg_latency_ms": 0, "est_cost_usd": 0}
        try:
            if guild:
                stats["cases"] = db.count_cases(guild_id=guild.id)
                stats["open_votes"] = len(db.list_open_votes(guild.id))
            stats["jobs"] = db.pending_job_count()
            js = db.judge_stats(hours=24)
        except Exception:  # noqa: BLE001
            pass

        judge = self.bot.judge
        jstatus = judge.status() if judge else {}
        last_err = None
        try:
            last_err = db.last_judge_error()
        except Exception:  # noqa: BLE001
            pass

        embed = discord.Embed(title="TypeSafe AI Bot — status", color=0x6EE7B7)
        embed.add_field(name="Version", value=f"`{__version__}`", inline=True)
        embed.add_field(name="Uptime", value=uptime, inline=True)
        embed.add_field(
            name="Mode",
            value=("🟢 **LIVE** — actions enforced" if not self.bot.cfg.dry_run
                   else "🧪 **DRY-RUN** — recorded, not enforced"),
            inline=True)
        embed.add_field(name="Guild", value=guild.name if guild else "not found", inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f} ms", inline=True)
        embed.add_field(
            name="Judge",
            value=(("⚠️ degraded — " + judge.friendly_error(last_err)) if jstatus.get("outage")
                   else "healthy" if js.get("calls") else "idle (no calls yet)"),
            inline=True)
        embed.add_field(
            name="Activity",
            value=(f"cases: **{stats['cases']}** · open votes: **{stats['open_votes']}** · "
                   f"scheduled jobs: **{stats['jobs']}**"),
            inline=False)
        embed.add_field(
            name="Judge calls · 24h",
            value=(f"{js.get('calls', 0)} calls · {js.get('ok', 0)} ok · "
                   f"avg {js.get('avg_latency_ms', 0)} ms · ~${js.get('est_cost_usd', 0):.4f}"),
            inline=False)
        embed.set_footer(text="TypeSafe AI Bot · /help for commands")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Status(bot))
