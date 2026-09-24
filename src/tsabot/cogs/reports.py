"""Reports + community votes — the headline system.

/report → mandatory written reason (modal) → posts card to the reports channel
→ Jev judges the reason (validity + recommended action) → vote opens when valid
→ members vote [Mute 1h] [Disconnect] [No action] → at deadline the vote closes
AND the AI reviews the outcome (uphold / reduce / overturn) before it applies.

Anti-abuse: one active report per reporter per target, daily caps, invalid-
report tracking, voter eligibility, staff veto.
"""
from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from ..caps import has_cap, resolve_caps
from ..db import utcnow
from ..vote_logic import verdict


class ReportModal(discord.ui.Modal, title="Report a member"):
    reason = discord.ui.TextInput(
        label="Reason (required)",
        style=discord.TextStyle.paragraph,
        placeholder="Describe what they did and when. Be specific — vague reports are dismissed.",
        required=True,
        min_length=12,
        max_length=1000,
    )

    def __init__(self, target: discord.Member, message_ref: str | None = None):
        super().__init__()
        self.target = target
        self.message_ref = message_ref
        if message_ref:
            self.reason.placeholder = f"Linked message: {message_ref[:80]}"

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Reports")
        if cog is None:
            await interaction.response.send_message("Reports system unavailable.",
                                                    ephemeral=True)
            return
        await cog.handle_report_submission(interaction, self.target, str(self.reason),
                                           self.message_ref)


class VoteButton(discord.ui.Button):
    def __init__(self, choice: str):
        style = {"mute": discord.ButtonStyle.primary,
                 "disconnect": discord.ButtonStyle.danger,
                 "none": discord.ButtonStyle.secondary}[choice]
        label = {"mute": "Mute 1h", "disconnect": "Disconnect", "none": "No action"}[choice]
        super().__init__(label=label, style=style, custom_id=f"tsabot:vote:{choice}")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Reports")
        await cog.handle_vote(interaction, self.custom_id.rsplit(":", 1)[-1])


class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent — survives restarts
        for choice in ("mute", "disconnect", "none"):
            self.add_item(VoteButton(choice))


class Reports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---- eligibility ------------------------------------------------
    def _voter_eligible(self, member: discord.Member, target_id: int) -> tuple[bool, str]:
        if member.bot:
            return False, "bots can't vote"
        if member.id == target_id:
            return False, "the reported member can't vote"
        if self.bot.is_owner(member.id):
            return True, ""
        role_id = self.bot.cfg.vote_role_id or self.bot.db.kv_get(member.guild.id, "vote_role")
        if role_id and not any(r.id == int(role_id) for r in member.roles):
            return False, "you need the verified member role to vote"
        return True, ""

    async def _staff_override(self, interaction: discord.Interaction) -> bool:
        stored = self.bot.db.role_caps(guild_id=interaction.guild.id,
                                       role_ids=[r.id for r in interaction.user.roles])
        caps = resolve_caps(role_caps=stored, is_owner=self.bot.is_owner(interaction.user.id))
        return has_cap(caps, "override_votes") or self.bot.is_owner(interaction.user.id)

    # ---- /report -----------------------------------------------------
    @app_commands.command(name="report",
                          description="Report a member (a written reason is required)")
    @app_commands.describe(user="The member to report",
                           detail="Optional: link the message or add detail")
    async def report(self, interaction: discord.Interaction, user: discord.Member,
                     detail: str | None = None):
        if user.bot:
            await interaction.response.send_message("Bots can't be reported.", ephemeral=True)
            return
        await interaction.response.send_modal(ReportModal(user, detail))

    # ---- submission pipeline ----------------------------------------
    async def handle_report_submission(self, interaction: discord.Interaction,
                                       target: discord.Member, reason: str,
                                       message_ref: str | None):
        guild = interaction.guild
        db = self.bot.db
        reporter = interaction.user

        # anti-abuse
        if db.active_vote_exists(guild_id=guild.id, reporter_id=reporter.id,
                                 target_id=target.id):
            await interaction.followup.send(
                "You already have an open report on that member.", ephemeral=True)
            return
        cap = self.bot.cfg.report_daily_cap
        if db.reports_since(guild_id=guild.id, reporter_id=reporter.id, hours=24) >= cap:
            await interaction.followup.send(
                f"Daily report limit reached ({cap}/24h).", ephemeral=True)
            return
        if db.invalid_report_count(guild_id=guild.id, reporter_id=reporter.id) >= \
                self.bot.cfg.report_invalid_limit:
            await interaction.followup.send(
                "Your reporting rights are suspended (too many unfounded reports). "
                "Talk to an owner.", ephemeral=True)
            return

        await interaction.followup.send(
            "Report received — reviewing the reason now.", ephemeral=True)

        result = await self.bot.loop.run_in_executor(
            None,
            lambda: self.bot.judge.ask_report_reason(
                reporter=str(reporter), target=str(target), reason=reason,
                context=message_ref))

        v = result.verdicts
        valid_p = float((v.get("reason_valid") or {}).get("noul", 0.0))
        rec_action = (v.get("recommended_action") or {}).get("choice", "none_of_above")

        channel_id = (self.bot.cfg.reports_channel_id
                      or db.kv_get(guild.id, "reports_channel"))
        channel = guild.get_channel(int(channel_id)) if channel_id else None

        # Judge degraded: heuristics must NEVER drive a vote or a dismissal.
        if result.layer != "jev":
            hits = ", ".join((v.get("_heuristic") or {}).get("hits", [])) or "—"
            db.add_case(guild_id=guild.id, kind="report", action="review",
                        target=target, reporter=reporter, reason=reason,
                        detail={"layer": result.layer, "error": result.error,
                                "hits": hits})
            if channel:
                embed = discord.Embed(
                    title=f"Report queued for human review — {target.display_name}",
                    description=(f"**Reporter:** {reporter.mention}\n"
                                 f"**Reason:** {reason[:500]}\n\n"
                                 f"The AI judge is currently offline. An owner will "
                                 f"review this report manually — no vote opens "
                                 f"automatically while the judge is down."),
                    color=0xF59E0B)
                await channel.send(embed=embed)
            await self.bot.notifier.alert_owners(
                guild, title="Report needs manual review (judge offline)",
                body=(f"{reporter} → {target}\nReason: {reason[:300]}\n"
                      f"Judge: {self.bot.judge.friendly_error(result.error)}"),
                color=0xF59E0B, key=f"report-degraded-{reporter.id}-{target.id}",
                severity="case")
            return

        # gate bands (Jev layer only)
        if valid_p >= self.bot.cfg.report_valid_high:
            band = "vote"
        elif valid_p >= self.bot.cfg.report_valid_medium:
            band = "flag"
        else:
            band = "dismissed"

        if band == "dismissed":
            db.add_case(guild_id=guild.id, kind="report", action="invalid",
                        target=target, reporter=reporter, reason=reason,
                        detail={"judge": v, "layer": result.layer})
            if channel:
                embed = discord.Embed(
                    title=f"Report dismissed — {target.display_name}",
                    description=(f"**Reporter:** {reporter.mention}\n"
                                 f"**Reason given:** {reason[:500]}\n\n"
                                 f"The AI judge did not find a concrete rule-breaking "
                                 f"behavior (validity {valid_p:.2f}). No vote opened."),
                    color=0x6B7280)
                await channel.send(embed=embed)
            await self.bot.notifier.alert_owners(
                guild, title="Report dismissed",
                body=f"{reporter} → {target}: {reason[:200]} (validity {valid_p:.2f})",
                color=0x6B7280, key=f"dismissed-{reporter.id}-{target.id}",
                severity="case")
            return

        # create the vote — the deadline job closes it AND triggers AI review
        deadline = utcnow() + timedelta(minutes=self.bot.cfg.vote_minutes)
        vote_id = db.create_vote(guild_id=guild.id, target_id=target.id,
                                 reporter_id=reporter.id, reason=reason,
                                 judge=v, deadline_at=deadline,
                                 target_name=target.display_name,
                                 reporter_name=str(reporter))
        db.add_job(guild_id=guild.id, kind="vote_deadline",
                   payload={"vote_id": vote_id}, due_at=deadline)

        verdict_line = {"mute_1h": "suggests: 1h voice mute",
                        "disconnect": "suggests: disconnect",
                        "none_of_above": "suggests: no action"}.get(
            rec_action, "suggests: review")
        embed = discord.Embed(
            title=f"Community vote — {target.display_name}",
            description=(f"**Reporter:** {reporter.mention} (`{reporter.id}`)\n"
                         f"**Accused:** {target.mention} (`{target.id}`)\n"
                         f"**Reason:** {reason[:800]}\n\n"
                         f"**AI review:** reason validity **{valid_p:.2f}** — {verdict_line}\n\n"
                         f"Vote below. Passes at **≥{self.bot.cfg.vote_min} votes** and "
                         f"**≥{int(self.bot.cfg.vote_pct * 100)}%** agreement within "
                         f"**{self.bot.cfg.vote_minutes} minutes** — when the timer ends, "
                         f"the AI reviews the outcome before it applies."),
            color=0xEF4444 if band == "vote" else 0xF59E0B)
        embed.set_footer(text=f"vote #{vote_id} · staff may veto with /veto {vote_id}")

        if channel:
            msg = await channel.send(embed=embed, view=VoteView())
            db.set_vote_message(vote_id, channel_id=channel.id, message_id=msg.id)
        else:
            await self.bot.notifier.alert_owners(
                guild, title="Report needs review (no reports channel set)",
                body=f"{reporter} → {target}\n{reason[:300]}\nValid {valid_p:.2f} — set "
                     f"a reports channel with `/config reports_channel #channel`.",
                color=0xF59E0B, key=f"noreports-{vote_id}", severity="case")

        await self.bot.notifier.alert_owners(
            guild, title=f"Vote opened — {target.display_name}",
            body=f"Reason: {reason[:200]}\nValidity {valid_p:.2f} · band: {band} · "
                 f"vote #{vote_id}, closes in {self.bot.cfg.vote_minutes} min.\n"
                 f"Staff can veto with `/veto {vote_id}`.",
            color=0xEF4444, key=f"vote-open-{vote_id}", severity="case")

    # ---- voting ------------------------------------------------------
    async def handle_vote(self, interaction: discord.Interaction, choice: str):
        db = self.bot.db
        row = db.query_one(
            "SELECT * FROM votes WHERE message_id=? AND status='open'",
            (interaction.message.id,))
        if row is None:
            await interaction.response.send_message("This vote is closed.", ephemeral=True)
            return
        vote = dict(row)
        ok, why = self._voter_eligible(interaction.user, vote["target_id"])
        if not ok:
            await interaction.response.send_message(f"You can't vote — {why}.", ephemeral=True)
            return
        db.add_ballot(vote_id=vote["id"], user_id=interaction.user.id, choice=choice)
        counts = db.ballot_counts(vote["id"])
        total = sum(counts.values())
        await interaction.response.send_message(
            f"Vote recorded: **{choice}** (total {total}).", ephemeral=True)
        await self.refresh_card(vote, counts)

    async def refresh_card(self, vote: dict, counts: dict[str, int]) -> None:
        guild = self.bot.get_guild(vote["guild_id"])
        ch = guild.get_channel(vote["channel_id"]) if guild and vote["channel_id"] else None
        if ch is None or not vote["message_id"]:
            return
        try:
            msg = await ch.fetch_message(vote["message_id"])
        except Exception:
            return
        embed = msg.embeds[0] if msg.embeds else discord.Embed()
        total = sum(counts.values())
        tally_line = " · ".join(
            f"**{k}**: {counts.get(k, 0)}" for k in ("mute", "disconnect", "none"))
        embed.clear_fields()
        embed.add_field(name="Live tally", value=f"{tally_line} (total {total})", inline=False)
        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

    # ---- closing (+ AI adjudication) ---------------------------------
    async def close_expired_vote(self, vote_id: int) -> None:
        """Deadline reached: close the vote, then let the AI review the outcome."""
        db = self.bot.db
        row = db.get_vote(vote_id)
        if row is None or row["status"] != "open":
            return
        vote = dict(row)
        counts = db.ballot_counts(vote_id)
        status, action = verdict(counts, min_votes=self.bot.cfg.vote_min,
                                 pct=self.bot.cfg.vote_pct)
        guild = self.bot.get_guild(vote["guild_id"])
        target = guild.get_member(vote["target_id"]) if guild and vote["target_id"] else None
        target_name = vote.get("target_name") or (target.display_name if target else "member")

        # --- AI adjudication: was the community's decision justified? ---
        adj = await self.bot.loop.run_in_executor(
            None,
            lambda: self.bot.judge.adjudicate_vote(
                target=target_name, reason=vote["reason"] or "",
                reporter=vote.get("reporter_name") or "a member",
                votes=counts, total_votes=sum(counts.values())))

        ai_verdict, ai_note = None, None
        if adj.layer == "jev":
            justified = float((adj.verdicts.get("justified") or {}).get("noul", 0.0))
            ai_verdict = (adj.verdicts.get("verdict") or {}).get("choice", "uphold")
            if justified < 0.5 and ai_verdict == "uphold":
                ai_verdict = "overturn"
            ai_note = f"justified {justified:.2f} → {ai_verdict} ({adj.model or 'jev'})"
        else:
            ai_note = ("AI review unavailable — " + self.bot.judge.friendly_error(adj.error)
                       + "; outcome applied with human-review flag.")

        executed_action = None
        if status == "passed" and action and ai_verdict != "overturn":
            if ai_verdict == "reduce" and action == "disconnect":
                action = "mute"  # reduce: milder, time-bounded action
            executed_action = action
            if target is not None:
                if action == "mute":
                    await self.bot.executor.voice_mute(
                        target, minutes=60, reason=f"community vote #{vote_id}",
                        guild_id=vote["guild_id"], kind="vote")
                elif action == "disconnect":
                    await self.bot.executor.disconnect(
                        target, reason=f"community vote #{vote_id}",
                        guild_id=vote["guild_id"])
            db.close_vote(vote_id, status="passed", action=executed_action,
                          ai_verdict=ai_verdict, ai_note=ai_note)
        elif status == "passed" and ai_verdict == "overturn":
            db.close_vote(vote_id, status="overturned", action=None,
                          ai_verdict=ai_verdict, ai_note=ai_note)
        else:
            db.close_vote(vote_id, status="failed", ai_verdict=ai_verdict, ai_note=ai_note)

        db.add_case(guild_id=vote["guild_id"], kind="vote",
                    action=executed_action or "no_action",
                    target_id=vote["target_id"], reporter_id=vote["reporter_id"],
                    target_name=target_name, reporter_name=vote.get("reporter_name"),
                    reason=f"vote #{vote_id}: {status} → {executed_action or 'no action'}",
                    detail={"counts": counts, "status": status,
                            "ai_verdict": ai_verdict, "ai_note": ai_note})

        if guild:
            result_line = {
                "passed": f"Passed — **{executed_action}** applied.",
                "overturned": "Passed the vote, but the AI review overturned it.",
                "failed": "Failed — no action.",
            }.get(status, status)
            await self.bot.notifier.alert_owners(
                guild, title=f"Vote #{vote_id} closed — {status}",
                body=f"**Tally:** {counts}\n**Result:** {result_line}\n"
                     f"**AI review:** {ai_note or '—'}",
                color=0x6EE7B7 if status == "passed" else 0x6B7280,
                key=f"vote-close-{vote_id}", severity="case")
            ch = guild.get_channel(vote["channel_id"]) if vote["channel_id"] else None
            if ch and vote["message_id"]:
                try:
                    msg = await ch.fetch_message(vote["message_id"])
                    embed = msg.embeds[0] if msg.embeds else discord.Embed()
                    embed.color = 0x6B7280
                    embed.add_field(name="Result",
                                    value=f"{result_line}\nAI review: {ai_note or '—'} "
                                          f"(votes: {sum(counts.values())})",
                                    inline=False)
                    await msg.edit(embed=embed, view=None)
                except Exception:
                    pass

    @app_commands.command(name="veto", description="Veto an open vote (staff)")
    async def veto(self, interaction: discord.Interaction, vote_id: int):
        if not await self._staff_override(interaction):
            await interaction.response.send_message("Staff only.", ephemeral=True)
            return
        row = self.bot.db.get_vote(vote_id)
        if row is None or row["status"] != "open":
            await interaction.response.send_message("That vote is not open.", ephemeral=True)
            return
        self.bot.db.close_vote(vote_id, status="vetoed")
        await interaction.response.send_message(f"Vote #{vote_id} vetoed.", ephemeral=True)
        await self.bot.notifier.alert_owners(
            interaction.guild, title=f"Vote #{vote_id} vetoed",
            body=f"Vetoed by {interaction.user}", color=0x6B7280,
            key=f"veto-{vote_id}", severity="case")

    @app_commands.command(name="votes", description="List open community votes")
    async def votes(self, interaction: discord.Interaction):
        rows = self.bot.db.list_open_votes(interaction.guild.id)
        if not rows:
            await interaction.response.send_message("No open votes.", ephemeral=True)
            return
        lines = []
        for r in rows:
            counts = self.bot.db.ballot_counts(r["id"])
            total = sum(counts.values())
            lines.append(f"`#{r['id']}` → **{r.get('target_name') or r['target_id']}** "
                         f"({total} votes) — {(r['reason'] or '')[:60]}")
        embed = discord.Embed(title="Open votes",
                              description="\n".join(lines)[:4000], color=0xF59E0B)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Module-level context menu (discord.py requires context menus at module scope).
@app_commands.context_menu(name="Report to mods")
async def report_message_ctx(interaction: discord.Interaction, message: discord.Message):
    if message.author.bot:
        await interaction.response.send_message("Bots can't be reported.", ephemeral=True)
        return
    if not isinstance(message.author, discord.Member):
        await interaction.response.send_message("Cannot resolve that member.", ephemeral=True)
        return
    await interaction.response.send_modal(
        ReportModal(message.author, f"{message.jump_url} :: {message.content[:200]}"))


async def setup(bot):
    await bot.add_cog(Reports(bot))
    bot.tree.add_command(report_message_ctx)
    bot.add_view(VoteView())  # persistent vote buttons across restarts
