"""`/owners` — manage the owner registry (users and roles). Owners only."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


def _is_owner(interaction: discord.Interaction, bot) -> bool:
    return bot.is_owner(interaction.user.id)


class Owners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    group = app_commands.Group(name="owners", description="Manage bot owners")

    @group.command(name="add", description="Add an owner (user)")
    async def add_user(self, interaction: discord.Interaction, user: discord.User):
        if not _is_owner(interaction, self.bot):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        self.bot.db.add_owner(guild_id=interaction.guild.id, subject_id=user.id,
                              kind="user", added_by=interaction.user.id)
        await interaction.response.send_message(f"Added **{user}** as owner.", ephemeral=True)
        await self.bot.notifier.alert_owners(
            interaction.guild, title="Owner added",
            body=f"{user} added as owner by {interaction.user}",
            color=0x6EE7B7, key=f"owner-add-{user.id}")

    @group.command(name="add_role", description="Add an owner role (all members with it count as owners)")
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        if not _is_owner(interaction, self.bot):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        self.bot.db.add_owner(guild_id=interaction.guild.id, subject_id=role.id,
                              kind="role", added_by=interaction.user.id)
        await interaction.response.send_message(f"Role **@{role.name}** now counts as owners.", ephemeral=True)

    @group.command(name="remove", description="Remove an owner (user or role id)")
    async def remove(self, interaction: discord.Interaction, subject_id: str):
        if not _is_owner(interaction, self.bot):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        if not subject_id.isdigit():
            await interaction.response.send_message("Give a numeric user or role ID.", ephemeral=True)
            return
        sid = int(subject_id)
        removed = False
        for kind in ("user", "role"):
            self.bot.db.remove_owner(guild_id=interaction.guild.id, subject_id=sid, kind=kind)
            removed = True
        await interaction.response.send_message(
            f"Removed `{sid}` from owners." if removed else "Nothing to remove.", ephemeral=True)

    @group.command(name="list", description="List current owners")
    async def list_owners(self, interaction: discord.Interaction):
        rows = self.bot.db.list_owners(interaction.guild.id)
        boot = ", ".join(f"<@{i}>" for i in sorted(self.bot.cfg.owner_ids)) or "(none)"
        lines = [f"**Bootstrap (env):** {boot}"]
        for r in rows:
            if r["kind"] == "user":
                lines.append(f"• user <@{r['subject_id']}>")
            else:
                role = interaction.guild.get_role(int(r["subject_id"]))
                lines.append(f"• role @{role.name if role else r['subject_id']}")
        await interaction.response.send_message("\n".join(lines)[:4000], ephemeral=True)


async def setup(bot):
    await bot.add_cog(Owners(bot))
