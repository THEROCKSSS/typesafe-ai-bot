# TypeSafe AI Bot — v1 Spec

Status: ready-for-agent · Drafted 2026-09-20 · Source: plan + grilling session with Owen
Seams confirmed by Owen 2026-09-20 (single AI boundary · pure decision modules · DRY-RUN
live verification · mocked Discord integration tests requested).

## Problem Statement

The community runs a growing multi-game Discord server. Moderation today is
fully manual: there is a bot (Jeeves) for server operations, but nothing that watches
chat for rule breaks, nothing that stops spam floods when mods are offline, nothing
that detects a compromised admin nuking channels, and no structured way for members to
escalate serious behavior. Owen wants AI-assisted moderation — but not an LLM with a
loose leash: every AI judgment must be typed, cheap, auditable, and always combined
with code-owned policy. He also wants member-driven accountability (reports with
mandated reasons, community votes on serious actions), scoped staff permissions per
role, and multi-owner alerting so control never rests on one person.

## Solution

**TypeSafe AI Bot**: a standalone Discord bot whose judgment layer is **Jev**
(TypeSafe System One). Jev reads messages and reports and returns typed verdicts
(probabilities, choices) against the server's written rules; plain code owns every
threshold, decision, and action. The bot covers:

- **Chat automod** — every message screened against `policy/rules.json`, one batched
  Jev call per message, high-confidence violations acted on (configurable), medium/low
  routed to humans, all failures failing *safe* (never punish on uncertainty).
- **Spam / rate-limit protection** — sliding-window detectors (burst, duplicates, mass
  mentions, link floods) → automatic timeout (default 10 min) + a notice + DM to all
  owners.
- **Nuke protection** — audit-log watcher for mass deletes/bans/kicks/webhook creates
  → locks the actor down (strip risky perms, pause invites), alerts all owners.
- **Member reports** — `/report` with a **mandated written reason** (modal-enforced),
  posted as a report card in a dedicated channel; **Jev judges the reason's validity
  and recommends no-action / mute / disconnect** via typed outputs.
- **Community votes** — substantiated reports open a vote on the card ([Mute 1h]
  [Disconnect] [No action]); thresholds + deadline configurable; passing outcomes are
  executed automatically: **voice server-mute for 1h** (bot lifts it when the hour is
  up) or **disconnect from voice**. Anti-abuse guards on reporting and voting.
- **Role → capability permissions** — a capability matrix assigned to roles via
  select-menu panels (`/setup`), scoping exactly what each role may do.
- **Multiple owners + owner DMs** — every critical event (spam timeout, nuke trip,
  vote result, report needing review, judge outage) is DM'd to **all** owners.
- **Fail-safe judge chain** — Jev direct API (primary, verified live) → OpenCode CLI
  running free Jev (fallback) → local heuristics + human-review queue (last resort,
  never auto-punishes). Outages are visible (`/jev` status, owner DMs) and recoverable.

v1 ships with **DRY-RUN default on**: everything logs and DMs, nothing is enforced,
until Owen flips it live after a review week.

## User Stories

1. As a server owner, I want Jev to screen messages against my server's written rules,
   so that rule-breaking chat gets flagged without me reading every line.
2. As a server owner, I want to add and remove multiple owners, so that alerts and
   control never depend on a single person.
3. As a server owner, I want every critical moderation event DM'd to all owners, so
   that nothing happens silently.
4. As a server owner, I want to configure which roles hold which capabilities, so that
   staff trust is scoped precisely (moderate, review reports, configure modules,
   exemptions).
5. As a server owner, I want a dry-run mode, so that I can watch the bot's real
   decisions before it enforces anything.
6. As a server owner, I want spam bursts to trigger an automatic timeout plus a DM, so
   that floods stop even when mods are asleep.
7. As a server owner, I want nuke protection to lock down a rogue admin mid-attack, so
   that damage stops immediately.
8. As a server owner, I want the rulebook to be one machine-readable file, so that I
   can paste and edit rules (with examples) without touching code.
9. As a server owner, I want judge outages to fail safe — no auto-punishment, review
   queue instead — so that a down AI never arbitrarily punishes members.
10. As a server owner, I want a status command showing judge model, spend, and outage
    state, so that I can trust the judge layer is alive.
11. As a server owner, I want to run the whole thing on my own PC beside the existing
    bot without side effects, so that nothing I already run breaks.

12. As a moderator with the right capability, I want warn / mute / disconnect / timeout
    commands that log reasons, so that manual moderation is consistent and auditable.
13. As a moderator, I want a quick moderation panel and right-click context menus, so
    that acting on a message takes one click.
14. As a moderator, I want to look up a member's case history, so that repeat
    offenders are visible in one place.
15. As a moderator, I want to veto an in-progress vote, so that obvious bad-faith or
    abused votes don't pass.
16. As a moderator, I want medium-confidence Jev verdicts routed to a review queue, so
    that uncertain cases get human eyes instead of automated action.

17. As a member, I want to report a message or user with a required written reason, so
    that every report is substantiated by construction.
18. As a member, I want my report judged by Jev for validity before any vote opens, so
    that frivolous reports don't waste the community's time.
19. As a member, I want to vote mute / disconnect / no-action on substantiated reports,
    so that the community has a say in serious moderation.
20. As a member, I want vote outcomes executed automatically (1h voice mute that lifts
    itself, or a disconnect), so that consequences are timely and don't need a mod.
21. As a member, I want reports and votes to live in one dedicated channel, so that
    moderation is transparent and organized rather than scattered.
22. As a member, I want a channel notice when someone is auto-timeoutted for spam, so
    that everyone knows why the room went quiet.
23. As a trusted member, I want my roles to exempt me from spam filters where
    configured, so that normal enthusiastic conversation isn't punished.

24. As a reported member, I want every action against me logged with its reason, so
    that decisions are accountable.
25. As a reported member, I want my voice mute to lift automatically after exactly one
    hour, so that the punishment is bounded.
26. As a reported member, I want Jev's verdict and the vote record attached to my case,
    so that I can see exactly why the action happened.
27. As a reported member, I want vote eligibility rules (members only, not the target,
    not bots), so that I'm not judged by drive-by strangers.

28. As the bot operator, I want a live selftest that hits the real Jev API with known
    hostile/benign examples, so that judge health is provable, not assumed.
29. As the bot operator, I want a fallback judge (OpenCode CLI running free Jev; then
    heuristics + review queue), so that moderation continues during TypeSafe outages.
30. As the bot operator, I want vote deadlines and mute lifts to survive bot restarts,
    so that scheduled outcomes still fire after a crash.
31. As the bot operator, I want a single judge interface where every AI call is cached,
    rate-capped, and circuit-broken, so that costs and failure modes stay controlled.
32. As the bot operator, I want mocked Discord integration tests covering the full
    report → gate → vote → action path, so that flows are regression-tested without a
    live server.
33. As the bot operator, I want an auto-restart wrapper and clear logs, so that the bot
    returns after crashes and incidents are diagnosable.
34. As the bot operator, I want per-call Jev token/latency/cost tracking, so that the
    judge layer's economics stay visible.

35. As the bot operator, I want one active report per reporter per target, daily
    report caps, and false-report tracking, so that reporting can't be weaponized.
36. As the bot operator, I want vote buttons to keep working on old messages after a
    restart (persistent components), so that deadlines are never lost.
37. As the bot operator, I want a fail-safe degradation chain with visible outage
    state, so that a judge outage is loud, not silent.

## Implementation Decisions

**Stack.** Python 3.11 + discord.py 2.7.1 (same house style as the existing Jeeves
bot; runs beside it untouched on Owen's PC). SQLite for state. New Discord
application/bot token created during setup. Configuration via gitignored `.env`.

**Judge chain (single interface).** One judge module exposes message-judging and
reason-judging; every AI call in the product goes through it. Layers: (1) **Jev direct
API** — verified live 2026-09-20 against `jev-1.13.0`; batched questions in ONE call
per message (one yes/no per enabled rule + tone/severity choice + a severity score,
per Jev's parallel-questions guidance); (2) **OpenCode CLI fallback** — shells out to
`opencode run` with the gateway's free Jev id (availability re-tested at build time;
free-tier data may be used for model improvement — that is accepted, primary path is
the direct API); (3) **local heuristics + human-review queue** — last resort, never
auto-punishes. Circuit breaker opens on consecutive failures, auto-recovers with a
probe, and outage state is visible. Per-call token/latency accounting is recorded.

**Policy ownership.** Code owns thresholds and actions; Jev supplies verdict inputs
only. Confidence bands (high → auto-action per rule config; medium → review queue +
owner DM; low → review queue only) are configurable per rule severity. Noul near 0.5
is treated as genuine uncertainty, never as "medium intensity".

**Rulebook.** `policy/rules.json`: id, title, description, severity, enabled,
auto_action (none / review / timeout-minutes) , and optional examples. The automod
screens every message against enabled rules in one batched call. Serious violations
(auto_action=timeout) apply Discord's native timeout (text + voice) for the configured
minutes; everything else routes to human review in v1.

**Action semantics (locked with Owen 2026-09-20).** *Mute* = voice server-mute applied
by the bot (works whether or not the member is currently in voice), lifted
automatically at the 1-hour mark by the persisted scheduler. *Disconnect* = remove the
member from their voice channel (they may rejoin). Config knob: a vote-mute may
*optionally* also apply a 1h text timeout alongside the voice mute (default off,
voice-style only). *Spam timeout* = native Discord timeout for the configured duration
(default 10 min), distinct from vote-mute.

**Votes.** Opens only when Jev judges the report reason valid at sufficient confidence.
Buttons: Mute 1h / Disconnect / No action; persistent custom IDs so restarts don't
break live votes. Defaults: ≥5 votes and ≥60% agreement within a 60-minute window
(all configurable); eligible voters = members with the configured verified role, not
bots, not the target, optional minimum account age. Staff veto possible during the
window. One active report per reporter per target; daily report caps; false-report
tracking that can revoke reporting rights. All vote state persisted.

**Scheduler.** Persisted timed-jobs table for vote deadlines and mute lifts; on
startup the bot re-arms outstanding jobs (restart-safe).

**Permissions.** Capability groups: Moderation (warn, mute_1h, disconnect,
case_view), Reports & votes (review_reports, override_votes, vote_start),
Configuration (config_spam, config_nuke, config_jev, config_vote), Exemptions
(spam_exempt, nuke_trusted, vote_immune). Stored as role-ID → capabilities in SQLite.
Editable through select-menu panels (`/setup` role select → capability multi-select).
Owner role implicitly holds everything. Owner registry supports multiple users and
roles; bootstrap owner from env. `/owners` manages the registry.

**Spam detector.** Sliding windows per user: message burst, duplicate content, mass
mentions, link flooding, caps/emoji floods. Exempt roles skip filters. Trips produce:
timeout action (DRY-RUN aware), a channel notice, a case entry, and owner DMs. The
bot respects Discord's own API rate limits on all outbound calls.

**Nuke protection.** Watches audit-log/gateway events: channel deletes, role deletes,
mass bans/kicks, webhook creation. Actors outside the trusted set tripping thresholds
in a window get locked down (risky permissions stripped, invites paused) with all
owners DM'd and a case written. Restoration of deleted channels/roles is NOT in v1
(documented upgrade path).

**Notifications.** A notifier module DMs **all** owners for: spam timeouts, nuke
trips, vote results, reports needing review, judge outage/recovery, config changes.
Optional mirrored log channels (#mod-log, #auto-mod). Digest scheduling is a later
upgrade.

**DRY-RUN.** A single runtime flag, default ON: every decision executes its logging,
case-writing, and DM path, but enforcement calls (timeouts, mutes, disconnects,
lockdowns) are recorded as would-have-happened. Owen flips live after the review week.

**Deployment.** Host process with an auto-restart wrapper (Jeeves precedent).
Podman-ization and a web dashboard are documented upgrade paths, not v1.

## Testing Decisions

*A good test here asserts externally observable behavior — given this input state,
what did the system decide and what did it call? — never private internals.*

- **One AI seam.** All judge calls go through the single judge interface. Unit and
  integration tests use a scripted fake judge (deterministic verdict fixtures). The
  real API is exercised by a standalone **live selftest** (hostile + benign sample
  messages against the real Jev endpoint) used as build-time and on-demand evidence.
- **Pure decision modules, unit-tested.** Rule→confidence→action mapping, spam window
  math, vote tally/threshold math, scheduler due-job computation, anti-abuse caps,
  capability checks — all plain functions/classes tested exhaustively without Discord.
- **Mocked Discord integration tests (requested by Owen — heavier, accepted).**
  discord.py command/cog flows tested against fake guild/member/interaction objects:
  full report lifecycle (modal reason → card → fake Jev gate → button vote → tally →
  execution call asserted with correct arguments), spam trip → timeout call asserted,
  antinuke trip → lockdown calls asserted, `/setup` menu flows, DRY-RUN suppressing
  enforcement while still logging. pytest + pytest-asyncio; assert on the calls made
  and state persisted at the cog boundary.
- **Hands-on DRY-RUN pass (Owen's).** On the live server in DRY-RUN: run the commands,
  read the cards, fire a test report, watch it reach a vote, check the owner DMs; the
  bot delivers a short checklist for exactly what to exercise. In-game/Discord
  confirmation is Owen's, file-level verification is the bot's.
- **Prior art.** The existing Jeeves bot's status-API and test patterns, and the
  pokemon-agent driver's selftest pattern (known-example live probes).

## Out of Scope

- Multi-guild support (v1 is one guild; KDF assumed).
- Nuke *restoration* (rollback of deleted channels/roles) — alerts + lockdown only.
- Web dashboard, Podman packaging, digest scheduling — documented upgrade paths.
- Raid/coordinated-attack detection beyond nuke thresholds.
- Training/finetuning on case outcomes; cross-server ban lists.
- Any auto-action below high confidence (by design, not a gap).

## Further Notes

- **Live Jev evidence (2026-09-20):** direct probe returned `jev-1.13.0`; a hostile
  sample scored `insults: 0.98`, tone `hostile` at 1.0 confidence; 335 input tokens
  ≈ $0.000014 per check at $0.042/Mtok input (output free). Negligible cost at
  community scale.
- **OpenCode fallback state (honest):** the gateway lists `jev-1.13-free` and paid
  `jev-1.13`; free-tier models currently reject plain REST calls ("can only be used
  from within OpenCode"), the CLI path errors upstream at draft time, and paid Jev
  reports insufficient funds. The fallback is built as specified and re-tested at
  build time; regardless of its state, the bot fails safe (heuristics + review queue)
  and notifies owners of outages.
- **Open items:** the rules text (becomes `policy/rules.json`) is pending from Owen;
  guild confirmation (KDF assumed); new Discord app token created at build time.
- Secrets (Discord token, TypeSafe key, OpenCode key) live only in the gitignored
  `.env`; never in git, notes, or chat.
