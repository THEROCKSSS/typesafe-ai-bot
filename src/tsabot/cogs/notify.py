"""Quality-of-life commands — everything a moderator needs inside Discord,
no dashboard required.

  /notify            check or change how THIS server routes bot notifications
                     (log = routine events land in the mod-log channel only,
                      dm = owners get DMs like before, both = DM + channel)
  /recent            newest cases as an ephemeral card (kind filter optional)
  /me                what can I actually do? shows my capabilities and the
                     commands each one unlocks — no guessing, no dashboard
"""
from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ..caps import CAPABILITY_GROUPS
from ..notifier import NOTIFY_MODES
from .cases import member_caps  # shared capability resolution

MODE_HELP = {
    "log": "📁 **Log channel only** — routine reports/votes/actions post to the "
           "mod-log channel; owners are DM'd only for critical alerts "
           "(nuke lockdown, spam timeout, config change).",
    "dm": "📬 **DMs** — every event DMs all owners (channel still mirrors "
          "critical alerts).",
    "both": "📁📬 **Both** — every event DMs owners AND posts in the mod-log channel.",
}

CAP_COMMANDS = {
    "warn": "/warn", "mute_1h": "/mute", "disconnect": "/disconnect",
    "case_view": "/case · /panel · /recent",
    "review_reports": "report-review buttons", "override_votes": "/veto",
    "vote_start": "opens the vote flow",
    "config_spam": "/config spam_*", "config_nuke": "/config nuke_*",
    "config_jev": "/config · /jev", "config_vote": "/config vote_*",
    "spam_exempt": "(exempt from spam auto-timeout)",
    "nuke_trusted": "(trusted during anti-nuke lockdown)",
    "vote_immune": "(immune to community votes)",
}


class Notify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---- /notify ------------------------------------------------------
    @app_commands.command(name="notify",
                          description="Check or change notification routing "
                                      "(log / dm / both) for this server")
    @app_commands.describe(mode="log | dm | both (omit to just check)")
    async def notify(self, interaction: discord.Interaction,
                     mode: Literal["log", "dm", "both"] | None = None):
        db = self.bot.db
        if mode is None:
            current = self.bot.notifier.mode_for(interaction.guild)
            embed = discord.Embed(
                title="Notification routing", color=0x6EE7B7,
                description=(f"**Current mode:** `{current}`\n{MODE_HELP[current]}\n\n"
                             "Change it with `/notify <mode>` — owners only, or grant "
                             "the `config_jev` capability.\n"
                             "_Routine case flow (reports, votes, verdicts) is a "
                             "notification you can silence; critical alerts always "
                             "reach owners + the log._"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        caps = await member_caps(self.bot, interaction.user)
        if not (self.bot.is_owner(interaction.user.id) or "config_jev" in caps):
            await interaction.response.send_message(
                "Only owners (or `config_jev` holders) can change notification routing.",
                ephemeral=True)
            return
        if mode not in NOTIFY_MODES:  # Literal guards this, belt + braces
            await interaction.response.send_message("Mode must be log, dm or both.",
                                                    ephemeral=True)
            return
        db.kv_set(interaction.guild.id, "notify_mode", mode)
        log_set = bool(self.bot.cfg.mod_log_channel_id
                       or db.kv_get(interaction.guild.id, "mod_log_channel"))
        note = "" if log_set or mode == "dm" else \
            "\n\n⚠️ No mod-log channel is set yet — set one with " \
            "`/config mod_log_channel <channel id>` or routine events have nowhere to go."
        await interaction.response.send_message(
            f"Notification routing set to **`{mode}`** — {MODE_HELP[mode]}{note}",
            ephemeral=True)
        await self.bot.notifier.alert_owners(
            interaction.guild, title="Notification routing changed",
            body=f"{interaction.user} set notify_mode → `{mode}`",
            color=0x818CF8, key=f"notify-mode-{mode}")

    # ---- /recent ------------------------------------------------------
    @app_commands.command(name="recent",
                          description="Newest moderation cases (ephemeral — no dashboard needed)")
    @app_commands.describe(kind="Filter: report · automod · spam · moderation · antinuke")
    async def recent(self, interaction: discord.Interaction,
                     kind: Literal[
                         "report", "automod", "spam", "moderation",
                         "antinuke"] | None = None):
        caps = await member_caps(self.bot, interaction.user)
        if "case_view" not in caps and not self.bot.is_owner(interaction.user.id):
            await interaction.response.send_message(
                "You need the `case_view` capability (ask an owner to grant it in `/setup`).",
                ephemeral=True)
            return
        rows = self.bot.db.list_recent(guild_id=interaction.guild.id, kind=kind, limit=10)
        if not rows:
            await interaction.response.send_message(
                f"No cases yet{f' for kind `{kind}`' if kind else ''}.", ephemeral=True)
            return
        lines = []
        for r in rows:
            when = (r["created_at"] or "")[:16].replace("T", " ")
            dry = " *(dry)*" if r["dry_run"] else ""
            tgt = r["target_name"] or "?"
            lines.append(f"`#{r['id']}` **{r['action']}** · {r['kind']} · "
                         f"{tgt}{dry}\n> {(r['reason'] or '—')[:110]} · `{when}`")
        embed = discord.Embed(
            title=f"Recent cases{' — ' + kind if kind else ''}",
            description="\n".join(lines)[:4000], color=0xF59E0B)
        embed.set_footer(text="TypeSafe AI Bot · /case @user for one member's history")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- /me ------------------------------------------------------------
    @app_commands.command(name="me",
                          description="Show my capabilities and the commands they unlock")
    async def me(self, interaction: discord.Interaction):
        caps = sorted(await member_caps(self.bot, interaction.user))
        is_owner = self.bot.is_owner(interaction.user.id)
        if is_owner:
            desc = "👑 **Owner** — every capability, plus `/setup`, `/owners`, `/notify set`.\n"
        elif not caps:
            desc = ("No moderation capabilities yet. Any member can still `/report` "
                    "and vote on open cases. Ask an owner to grant you a role in "
                    "`/setup` — then re-run `/me`.")
        else:
            lines = []
            for group, group_caps in CAPABILITY_GROUPS.items():
                mine = [c for c in group_caps if c in caps]
                if mine:
                    lines.append(f"**{group}**\n" + "\n".join(
                        f"• `{c}` → {CAP_COMMANDS.get(c, '—')}" for c in mine))
            desc = "\n".join(lines)
        embed = discord.Embed(
            title=f"Your powers — {interaction.user.display_name}",
            description=desc[:4000], color=0x818CF8 if is_owner else 0x6EE7B7)
        embed.set_footer(text="TypeSafe AI Bot · everything works from Discord — no dashboard login needed")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Notify(bot))
