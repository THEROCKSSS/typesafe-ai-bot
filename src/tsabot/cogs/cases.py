"""`/case`, `/warn`, `/mute`, `/disconnect`, `/panel` — manual moderation.

All enforcement flows through the shared executor (DRY-RUN aware).
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..caps import has_cap, resolve_caps


async def member_caps(bot, member: discord.Member) -> set[str]:
    db = bot.db
    role_ids = [r.id for r in member.roles]
    stored = db.role_caps(guild_id=member.guild.id, role_ids=role_ids)
    return resolve_caps(role_caps=stored, is_owner=bot.is_owner(member.id))


async def require_cap(interaction: discord.Interaction, bot, cap: str) -> bool:
    caps = await member_caps(bot, interaction.user)
    if has_cap(caps, cap):
        return True
    await interaction.response.send_message(
        f"You need the `{cap}` capability (ask an owner to grant it in `/setup`).",
        ephemeral=True)
    return False


class Cases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="case", description="Look up a member's moderation history")
    @app_commands.describe(user="Member to look up", page="Page number (default 1)")
    async def case(self, interaction: discord.Interaction, user: discord.Member, page: int = 1):
        if not await require_cap(interaction, self.bot, "case_view"):
            return
        page = max(1, page)
        per = 8
        rows = self.bot.db.list_cases(guild_id=interaction.guild.id, target_id=user.id,
                                      limit=per, offset=(page - 1) * per)
        if not rows:
            await interaction.response.send_message(f"No cases for {user}.", ephemeral=True)
            return
        lines = []
        for r in rows:
            when = r["created_at"][:16].replace("T", " ")
            dry = " *(dry-run)*" if r["dry_run"] else ""
            who = ""
            if r["actor_name"] or r["reporter_name"]:
                who = (f"\n> by {r['actor_name'] or r['reporter_name']}"
                       f" (`{r['actor_id'] or r['reporter_id']}`)")
            voice = f"\n> voice: {r['voice_channel']}" if r["voice_channel"] else ""
            lines.append(
                f"`#{r['id']}` **{r['action']}** ({r['kind']}) — {when}{dry}\n"
                f"> {(r['reason'] or '—')[:150]}{who}{voice}")
        embed = discord.Embed(
            title=f"Cases — {user.display_name}",
            description=f"**Target:** {user.mention} (`{user.id}`)\n\n"
                        + "\n".join(lines)[:3800],
            color=0xF59E0B)
        embed.set_footer(text=f"page {page} · /case {user} {page + 1} for older")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---- manual actions --------------------------------------------
    @app_commands.command(name="warn", description="Warn a member (logged)")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await require_cap(interaction, self.bot, "warn"):
            return
        await self.bot.executor.warn(user, reason=reason, guild_id=interaction.guild.id,
                                     actor=interaction.user)
        await interaction.response.send_message(f"Warned {user} — logged.", ephemeral=True)

    @app_commands.command(name="mute", description="Voice-mute a member for 1 hour (auto-lifts)")
    async def mute(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await require_cap(interaction, self.bot, "mute_1h"):
            return
        await self.bot.executor.voice_mute(user, minutes=60, reason=reason,
                                           guild_id=interaction.guild.id,
                                           actor=interaction.user)
        await interaction.response.send_message(
            f"Voice mute on {user} for 1h (auto-lifts).", ephemeral=True)

    @app_commands.command(name="disconnect", description="Disconnect a member from voice")
    async def disconnect(self, interaction: discord.Interaction, user: discord.Member, reason: str):
        if not await require_cap(interaction, self.bot, "disconnect"):
            return
        await self.bot.executor.disconnect(user, reason=reason,
                                           guild_id=interaction.guild.id,
                                           actor=interaction.user)
        await interaction.response.send_message(f"Disconnected {user} from voice.", ephemeral=True)

    @app_commands.command(name="panel", description="Quick moderation panel")
    async def panel(self, interaction: discord.Interaction, user: discord.Member):
        if not await require_cap(interaction, self.bot, "case_view"):
            return
        caps = await member_caps(self.bot, interaction.user)
        view = ModPanel(user, caps)
        embed = discord.Embed(title=f"Moderation — {user}",
                              description="Choose an action (all actions are logged)",
                              color=0xEF4444)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ModPanel(discord.ui.View):
    def __init__(self, user: discord.Member, caps: set[str]):
        super().__init__(timeout=120)
        self.user = user
        if "mute_1h" not in caps:
            self.mute_btn.disabled = True
        if "disconnect" not in caps:
            self.dc_btn.disabled = True

    @discord.ui.button(label="Voice mute 1h", style=discord.ButtonStyle.danger)
    async def mute_btn(self, interaction: discord.Interaction, _):
        await interaction.client.executor.voice_mute(
            self.user, minutes=60, reason=f"panel action by {interaction.user}",
            guild_id=interaction.guild.id)
        await interaction.response.send_message(f"Muted {self.user} for 1h.", ephemeral=True)

    @discord.ui.button(label="Disconnect", style=discord.ButtonStyle.danger)
    async def dc_btn(self, interaction: discord.Interaction, _):
        await interaction.client.executor.disconnect(
            self.user, reason=f"panel action by {interaction.user}",
            guild_id=interaction.guild.id)
        await interaction.response.send_message(f"Disconnected {self.user}.", ephemeral=True)

    @discord.ui.button(label="View cases", style=discord.ButtonStyle.secondary)
    async def cases_btn(self, interaction: discord.Interaction, _):
        rows = interaction.client.db.list_cases(guild_id=interaction.guild.id,
                                                target_id=self.user.id, limit=5)
        if not rows:
            await interaction.response.send_message("No cases.", ephemeral=True)
            return
        lines = [f"`#{r['id']}` {r['action']} — {(r['reason'] or '')[:80]}" for r in rows]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Cases(bot))
