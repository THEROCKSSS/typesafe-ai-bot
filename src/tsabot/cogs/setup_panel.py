"""`/setup` — the role → capability panel.

Pick a role in the select menu, then multi-select its capabilities and Apply.
Includes: view current mappings, remove a mapping.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..caps import CAPABILITY_GROUPS, ALL_CAPS

SEP = "::"


class CapSelect(discord.ui.Select):
    def __init__(self, role: discord.Role, current: set[str]):
        options = []
        for group, caps in CAPABILITY_GROUPS.items():
            for cap in caps:
                options.append(discord.SelectOption(
                    label=cap, description=group,
                    value=cap, default=cap in current))
        super().__init__(placeholder=f"Capabilities for @{role.name}",
                         min_values=0, max_values=len(options), options=options)
        self.role = role

    async def callback(self, interaction: discord.Interaction):
        db = self.bot.db  # type: ignore[attr-defined]
        guild_id = interaction.guild.id
        db.clear_caps(guild_id=guild_id, role_id=self.role.id)
        for cap in self.values:
            db.set_cap(guild_id=guild_id, role_id=self.role.id, capability=cap)
        caps = ", ".join(sorted(self.values)) or "(none)"
        await interaction.response.send_message(
            f"Updated **@{self.role.name}** → {caps}", ephemeral=True)


class RoleSelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role], caps_by_role: dict[int, set[str]]):
        options = [discord.SelectOption(label=r.name, value=str(r.id),
                                        description=f"{len(caps_by_role.get(r.id, set()))} caps")
                   for r in roles[:25]]
        super().__init__(placeholder="Choose a role…", min_values=1, max_values=1, options=options)
        self._roles = {str(r.id): r for r in roles}

    async def callback(self, interaction: discord.Interaction):
        role = self._roles[self.values[0]]
        db = self.bot.db  # type: ignore[attr-defined]
        caps = {row["capability"] for row in db.list_caps(interaction.guild.id)
                if row["role_id"] == role.id}
        await interaction.response.edit_message(
            content=f"Editing **@{role.name}** — pick capabilities, then it applies instantly.",
            view=CapEditorView(role, caps))


class CapEditorView(discord.ui.View):
    def __init__(self, role: discord.Role, caps: set[str]):
        super().__init__(timeout=180)
        self.add_item(CapSelect(role, caps))


class SetupRootView(discord.ui.View):
    def __init__(self, roles: list[discord.Role], caps_by_role: dict[int, set[str]]):
        super().__init__(timeout=180)
        self.add_item(RoleSelect(roles, caps_by_role))


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure role → capability permissions")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction):
        guild = interaction.guild
        caps_by_role: dict[int, set[str]] = {}
        for row in self.bot.db.list_caps(guild.id):
            caps_by_role.setdefault(row["role_id"], set()).add(row["capability"])
        roles = [r for r in guild.roles if not r.is_default() and not r.managed
                 and r < guild.me.top_role]
        if not roles:
            await interaction.response.send_message(
                "No assignable roles (role hierarchy — the bot's role must sit above "
                "the roles you want to configure).", ephemeral=True)
            return
        embed = discord.Embed(
            title="Role → Capability setup",
            description=("Pick a role below, then multi-select what it may do.\n\n"
                         "**Groups:**\n" +
                         "\n".join(f"• **{g}**: {', '.join(c)}"
                                   for g, c in CAPABILITY_GROUPS.items()) +
                         "\n\nOwners implicitly hold every capability."),
            color=0x818CF8)
        lines = []
        for role in roles:
            if role.id in caps_by_role:
                lines.append(f"**@{role.name}** — {', '.join(sorted(caps_by_role[role.id]))}")
        if lines:
            embed.add_field(name="Current mappings", value="\n".join(lines[:15])[:1024], inline=False)
        await interaction.response.send_message(embed=embed,
                                                view=SetupRootView(roles, caps_by_role),
                                                ephemeral=True)

    @app_commands.command(name="perms", description="Show the current role → capability matrix")
    async def perms(self, interaction: discord.Interaction):
        rows = self.bot.db.list_caps(interaction.guild.id)
        if not rows:
            await interaction.response.send_message("No role mappings yet — run `/setup`.", ephemeral=True)
            return
        by_role: dict[int, list[str]] = {}
        for r in rows:
            by_role.setdefault(r["role_id"], []).append(r["capability"])
        lines = []
        for role_id, caps in by_role.items():
            role = interaction.guild.get_role(role_id)
            lines.append(f"**@{role.name if role else role_id}** — {', '.join(sorted(caps))}")
        embed = discord.Embed(title="Permission matrix", description="\n".join(lines)[:4000], color=0x818CF8)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Setup(bot))
