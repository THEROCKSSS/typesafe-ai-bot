/** The command guide: copy-paste ready messages for teaching members.
 *  Each entry can be posted to a Discord channel or DM'd to a member
 *  through the dashboard (the bot does the sending). */

export const GUIDE = [
  {
    id: "member-report",
    audience: "Members",
    title: "How to report someone",
    blurb: "Reports need a written reason — vague reports get dismissed.",
    message: `**📋 How to report a member**

Spotted someone breaking the rules? Here's the honest way to escalate it:

**Option 1 — report a specific message**
• Right-click (or long-press) the message
• Choose **Apps → Report to mods**
• A form pops up — describe what they did and when
• The reason is **required**: "they were annoying" gets dismissed, "they spammed slurs in voice at 9pm" doesn't

**Option 2 — /report**
• Type \`/report\` and pick the member
• Add detail if you have it (a link helps a lot)

**What happens next**
1. Jev (the AI judge) reads your reason and scores whether it describes real misconduct
2. If it's valid → a community vote opens in this channel: **Mute 1h / Disconnect / No action**
3. Members vote; passing outcomes apply automatically
4. If your reason isn't concrete, the report is closed with an explanation — repeated junk reports pause your reporting rights

**One rule for the system:** reports should be about behavior, not grudges. The vote is your community's, and staff can veto anything abused.`,
  },
  {
    id: "member-vote",
    audience: "Members",
    title: "How voting works",
    blurb: "The thresholds, the window, and what each button actually does.",
    message: `**🗳️ How community votes work**

When a report passes the AI check, a vote card appears here.

**The buttons**
• **Mute 1h** — voice-mutes the member for one hour; the bot lifts it automatically, they cannot lift it themselves
• **Disconnect** — pulls them out of the voice channel right now (they can rejoin)
• **No action** — you think the report doesn't warrant a consequence

**What passes**
• At least **5 votes** AND at least **60% agreement** on one option
• Vote window: **60 minutes** from when the card is posted
• You cannot vote on your own report or on yourself; bots can't vote

**After it closes**
• Passing **Mute** → applied within seconds, auto-lifts after an hour
• Passing **Disconnect** → applied immediately
• Failing → nothing happens; the case is logged and closed

Staff can veto an open vote at any time (the card shows the result either way).`,
  },
  {
    id: "member-spam",
    audience: "Members",
    title: "Why you got timed out (spam)",
    blurb: "Explain the auto-timeout so it doesn't feel mysterious.",
    message: `**⏱️ About automatic timeouts**

The bot watches for spam patterns so mods don't have to:
• **6+ messages in 5 seconds** (burst)
• **4+ identical messages** within 30 seconds
• **6+ mentions** in 10 seconds (counting role pings harder)
• **4+ links** within 20 seconds

Trip one of those and you get an automatic timeout — the channel gets a notice saying why, and owners are notified.

**It's not permanent, and it's not personal.** The timer is short by design (default 10 minutes). Slow down, come back, no hard feelings.

Staff roles with the spam-exempt capability skip these filters entirely.`,
  },
  {
    id: "mod-quickstart",
    audience: "Moderators",
    title: "Moderator quickstart",
    blurb: "The five commands a new moderator actually needs.",
    message: `**🛡️ Moderator quickstart**

**Look before you act**
• \`/case @member\` — their full moderation history
• \`/panel @member\` — quick action buttons + recent cases

**Act**
• \`/warn @member reason\` — logged warning, no enforcement
• \`/mute @member reason\` — voice mute for 1h, auto-lifts
• \`/disconnect @member reason\` — pull them from voice
• \`/veto <vote-id>\` — cancel a community vote that's being abused

**Everything is logged.** Every action you take writes a case with your name, the reason, and a timestamp. \`/case\` is the receipt — if you can't write a reason a stranger would accept, reconsider the action.

**DRY-RUN note:** while the server is in trial mode, actions are *recorded* but not applied. You'll see the case entry and the owners get notified — that's the audit trail working.`,
  },
  {
    id: "mod-perms",
    audience: "Moderators",
    title: "Roles and capabilities",
    blurb: "What each capability unlocks, and who can grant it.",
    message: `**🔑 How permissions work here**

The bot doesn't use Discord's built-in permissions for its commands — it uses **capabilities** mapped to your server roles.

**Capability groups**
• **Moderation**: warn · mute_1h · disconnect · case_view
• **Reports & votes**: review_reports · override_votes · vote_start
• **Configuration**: config_spam · config_nuke · config_jev · config_vote
• **Exemptions**: spam_exempt · nuke_trusted · vote_immune

**Who can change them:** anyone with Manage Server — they run \`/setup\`, pick a role from the menu, multi-select its capabilities, and hit apply. Changes take effect immediately (no restart).

**Check your own access:** run \`/help\` — if a command is listed for your tier, the bot will accept it; if you try something you don't have, you get a private "you need the X capability" message instead of silence.

Owners (the people listed with \`/owners list\`) implicitly hold every capability.`,
  },
  {
    id: "owner-setup",
    audience: "Owners",
    title: "Owner setup checklist",
    blurb: "The first ten minutes of a fresh install.",
    message: `**⚙️ Owner setup checklist**

1. **\`/setup\`** — map your roles to capabilities. Minimum viable: give your Moderator role \`warn, mute_1h, disconnect, case_view\`.
2. **\`/config reports_channel #your-channel\`** — where report cards and votes appear. Without this, reports go to owner DMs instead.
3. **\`/config mod_log_channel #your-logs\`** — mirrors every owner alert.
4. **\`/owners add @co-owner\`** — add every person who should receive alerts. \`/owners add_role\` works for whole roles.
5. **Test everything in DRY-RUN first** — set \`DRY_RUN=1\` in \`.env\` (the default). Post a test rule-break in a quiet channel and watch the owner DM arrive.
6. **Go live when satisfied** — set \`DRY_RUN=0\` and restart. \`/status\` should show LIVE.

**Daily operations:** \`/jev\` for judge health and spend, \`/votes\` for open votes, \`/case\` for any member's history. The dashboard at \`http://127.0.0.1:8788\` shows everything in one place.`,
  },
  {
    id: "owner-judge",
    audience: "Owners",
    title: "Understanding the judge chain",
    blurb: "Why the AI sometimes says it's degraded, and what that means.",
    message: `**🧠 How the AI judge works (and fails)**

Every message is screened by a chain of three layers:

**1. TypeSafe Jev (primary)** — reads the message, returns probability scores against each of your rules. Fast, cheap, and the only layer allowed to trigger automatic actions.

**2. OpenCode fallback** — if Jev is unreachable, the bot can route through a free model instead.

**3. Local heuristics (last resort)** — a conservative pattern scan. It can only **flag for human review** — it can never time anyone out, open a vote, or dismiss a report. If all three layers fail, nothing is punished; owners simply get "possible rule break, judge offline" DMs.

**When Jev is out of credits**, the dashboard's Judge view shows it plainly, and \`/jev\` reports the outage. Everything keeps running in degraded mode — safe, just noisier for you.

**The key safety property:** the AI never acts alone. Code owns every threshold; the model only supplies the probability. That's why a bad day for the API is an inconvenience, not a moderation incident.`,
  },
];

export const GUIDE_BY_AUDIENCE = GUIDE.reduce((acc, g) => {
  (acc[g.audience] ||= []).push(g);
  return acc;
}, {});
