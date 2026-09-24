# TypeSafe AI Bot — Setup & Self-Hosting Guide

Everything you need to run this bot on your own machine and your own Discord server.
Follow the sections in order; each ends with a **Verify** step so you always know the
previous stage actually worked before moving on.

---

## 0. What you're setting up

| Piece | What it does | Default port |
|---|---|---|
| **Bot** | Discord moderation: Jev-judged chat screening, spam + nuke protection, reports/votes | — |
| **Dashboard** | Local read-only control panel (cases, votes, judge health, rulebook) | `127.0.0.1:8788` |

The bot talks to:
- **Discord** (your server)
- **TypeSafe Jev** (`api.typesafe.ai`) — the AI judge — *optional but recommended*
- **OpenCode CLI** — free-Jev fallback judge — *optional*

If either AI path is unavailable the bot **degrades safely**: it flags things for
human review and never auto-punishes.

**Requirements:** Python 3.11+, a Discord account, ~5 minutes.

---

## 1. Clone / copy the project

```bash
cd path/to/your/projects
git clone <this-repo> typesafe-ai-bot
cd typesafe-ai-bot
```

**Verify:** `ls` shows `src/`, `tests/`, `policy/`, `docs/`.

---

## 2. Install Python dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

**Verify:**

```bash
python -c "import discord, fastapi; print('deps ok')"
```

---

## 3. Run the test suite (proves the install is sane)

```bash
python -m pytest tests/ -q
```

**Verify:** `71 passed` (or similar — everything must pass before you go further).

---

## 4. Create your Discord bot

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. Name it (e.g. "TypeSafe AI Bot") → **Create**.
3. Left sidebar → **Bot**:
   - Click **Reset Token** → copy it. This is your `DISCORD_TOKEN`. *(Shown once.)*
   - Under **Privileged Gateway Intents**, enable:
     - ✅ **Server Members Intent** (required — member lookups)
     - ✅ **Message Content Intent** (required — reading messages to screen them)
4. Left sidebar → **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: **View Channels, Send Messages, Embed Links, Read Message
     History, Manage Roles, Moderate Members, Kick Members** *(for antinuke lockdown),
     View Audit Log** *(for antinuke detection), Connect, Mute Members*
   - Copy the generated URL, open it, and invite the bot to your server.
5. In Discord (Settings → Advanced → **Developer Mode ON**):
   - Right-click your server name → **Copy Server ID** → this is `DISCORD_GUILD_ID`.
   - Right-click your own name → **Copy User ID** → this is your owner ID.

**Verify:** the bot appears in your server's member list (offline is fine).

---

## 5. Configure `.env`

Copy the example and fill it in:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# --- required ---
DISCORD_TOKEN=your-bot-token
DISCORD_GUILD_ID=your-server-id
OWNER_IDS=your-user-id              # comma-separated; these get DM alerts

# --- safe defaults (change later) ---
DRY_RUN=1                            # 1 = log only, nothing enforced (start here)
DASHBOARD_PORT=8788

# --- AI judge (optional but recommended) ---
TYPESAFE_API_KEY=                    # from https://console.typesafe.ai/settings/keys
OPENCODE_ZEN_API_KEY=                # optional free-Jev fallback (opencode.ai)

# --- channels (optional; can be set later with /config) ---
REPORTS_CHANNEL_ID=                  # where /report cards + votes post
MOD_LOG_CHANNEL_ID=                  # mirror of owner alerts

# --- tuning (defaults shown) ---
SPAM_TIMEOUT_MINUTES=10
VOTE_MIN=5
VOTE_PCT=0.6
VOTE_MINUTES=60
```

**Notes on the AI keys:**
- `TYPESAFE_API_KEY` powers the primary judge. Without it the bot runs heuristics +
  review only (no auto-actions).
- TypeSafe charges ~$0.042 per million **input** tokens; a message check is ~300
  tokens, so thousands of checks cost pennies. If your TypeSafe credit runs out the
  chain falls back automatically — you'll see it in `/jev` and the dashboard.
- Never commit `.env`. It's gitignored by default.

**Verify:** `python -c "from tsabot.config import load_config; c=load_config(); print(c.bot_errors() or 'config ok')"`
(run from the repo root with `src` on `PYTHONPATH`, or just continue — step 6 checks it).

---

## 6. First boot (DRY-RUN)

```bash
python src/main.py
```

**Verify, in order:**
1. Console prints `[bot] <name> ready — guilds: ['Your Server'] — DRY_RUN=True`.
2. In Discord: `/status` → embed shows version, uptime, **DRY-RUN ON**, database ok.
3. `/help` → lists every command.

Leave it running for now.

---

## 7. Configure the server (in Discord)

Run as the server owner:

1. `/setup` — the role → capability panel. Pick a role, multi-select its capabilities
   (e.g. give your **Moderator** role `warn, mute_1h, disconnect, case_view`), apply.
2. `/config reports_channel #your-reports-channel` — where report cards land.
3. `/config mod_log_channel #your-mod-log` — alert mirror.
4. `/owners add @yourself` — register runtime owners (env `OWNER_IDS` also counts).
5. Drop a test message in a public channel; watch the bot's console.

**Verify:** `/perms` shows your role mappings; `/owners list` shows the registry.

---

## 8. The review week (DRY-RUN)

Everything now runs for real **except enforcement** — timeouts, mutes, and
disconnects are logged, cased, and DM'd to owners, but not applied.

Exercise it:

- Have someone post an insult → owners should get a *flagged for review* DM.
- `/report @someone` with a real reason → a report card appears; Jev judges it; if
  valid, a vote opens. Have 5 members vote (or lower `VOTE_MIN` temporarily).
- Spam a channel quickly → owners get a spam DM (dry-run labeled).
- Try `/panel`, `/case`, `/mute`, `/disconnect` → all appear as dry-run cases.

When you're satisfied, flip to live:

```ini
DRY_RUN=0
```

Restart the bot. `/status` now shows **LIVE**.

---

## 9. The dashboard

In a second terminal (bot can keep running):

```bash
python src/dashboard_main.py
```

Open <http://127.0.0.1:8788>.

**Views:**
| Page | What it shows |
|---|---|
| **Overview** | KPIs (cases, votes, judge calls, spend), cases-by-action chart, judge trend |
| **Judge chain** | Every judge call: layer (jev/opencode/heuristic), tokens, latency, errors |
| **Cases** | Browsable case log — click any case for full detail |
| **Votes** | Live vote cards with tallies |
| **Rulebook** | Your rules as the machine reads them |
| **Scheduler & owners** | Pending timed jobs (mute lifts, deadlines), owners, capabilities |

Every page is a real URL — bookmark and refresh safely.

**Verify:** the sidebar pill says *DRY-RUN — not enforcing* (or *LIVE*) matching your
config; the status line bottom-left reads `db ok · tsabot.db`.

---

## 10. Running it long-term

### Windows (recommended: Task Scheduler, or a simple keep-alive script)

Write `run_bot.bat`:

```bat
@echo off
cd /d %~dp0
call .venv\Scripts\activate
:loop
python src\main.py
echo Bot exited — restarting in 10s...
timeout /t 10 /nobreak >nul
goto loop
```

Double-click to run, or register it in Task Scheduler at logon.

### Linux / macOS (systemd)

`/etc/systemd/system/tsabot.service`:

```ini
[Unit]
Description=TypeSafe AI Bot
After=network-online.target

[Service]
WorkingDirectory=/opt/typesafe-ai-bot
ExecStart=/opt/typesafe-ai-bot/.venv/bin/python src/main.py
Restart=always
RestartSec=10
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now tsabot
```

**Verify:** `systemctl status tsabot` shows active; kill the process (`pkill -f main.py`)
and watch it come back within 10 s.

---

## 11. Customizing the rulebook

Edit `policy/rules.json`:

```json
{
  "rules": [
    {
      "id": "harassment",
      "title": "No harassment or personal attacks",
      "description": "Insulting, demeaning, or targeting another member...",
      "severity": "high",
      "enabled": true,
      "auto_action": "timeout",
      "timeout_minutes": 30
    }
  ]
}
```

| Field | Values | Meaning |
|---|---|---|
| `severity` | `low` / `medium` / `high` / `critical` | critical rules act at lower confidence |
| `auto_action` | `timeout` / `review` / `none` | what happens at high confidence |
| `timeout_minutes` | number | length of native timeout (text+voice) |

Reload: restart the bot (or just edit — automod reads the file per message).
The Dashboard → Rulebook view shows exactly how the bot reads it.

---

## 12. How the judge chain works (so you can reason about failures)

```
message → [1] TypeSafe Jev  ──ok──→ verdicts → code applies thresholds
               │ fail
               ▼
          [2] OpenCode CLI (free Jev) ──ok──→ verdicts (marked degraded)
               │ fail
               ▼
          [3] local heuristics → REVIEW FLAG ONLY (never auto-punishes)
```

- 5 consecutive primary failures **open the breaker**; a probe auto-recovers it.
- Every call is recorded (layer, tokens, latency) — visible at `/jev` and on the
  dashboard's Judge page.
- While degraded: no auto-actions, everything routes to owner DMs; the bot posts an
  outage banner state until recovery.

**Verify:** `/jev` shows the current layer health and 24 h spend.

---

## 13. Commands reference

| Command | Who | Does |
|---|---|---|
| `/status` | everyone | bot health + DRY-RUN state |
| `/help` | everyone | command overview |
| `/report @user` (+ right-click a message → *Report to mods*) | members | file a report (reason required) |
| `/votes` | everyone | list open votes |
| `/case @user` | case_view | paginated moderation history |
| `/panel @user` | case_view | quick actions |
| `/warn` `/mute` `/disconnect` | capabilities | manual actions (logged, DRY-RUN aware) |
| `/veto <id>` | override_votes | cancel an open vote |
| `/setup` `/perms` | manage_guild | role → capability configuration |
| `/owners add\|add_role\|remove\|list` | owners | owner registry |
| `/config [key value]` | config caps | settings |
| `/jev` | everyone | judge chain health + spend |

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Configuration is incomplete — cannot start` | missing token/guild | finish `.env` (the bot names every missing field) |
| Bot online, no slash commands | commands not synced | wait ~1 min; check console `[bot] synced N app commands` |
| `/setup` says "No assignable roles" | role hierarchy | drag the bot's role **above** the roles you want to configure |
| No messages screened | Message Content intent off | enable it in the Developer Portal, restart |
| Dashboard pages empty | bot never ran | expected — run the bot once (`/status`) and data appears |
| `HTTP 402 billing_error` in judge errors | TypeSafe credits exhausted | add credits at console.typesafe.ai, or run degraded (safe) |
| Owner DMs not arriving | owner closed DMs | bot falls back to the mod-log channel automatically |
| Spam detector too aggressive | thresholds | raise `SPAM_TIMEOUT_MINUTES`; tune `SpamThresholds` in `src/tsabot/detectors.py` |
| Vote can't pass in a small server | `VOTE_MIN` too high | `/config` or lower `VOTE_MIN` in `.env` |

---

## 15. Security notes

- `.env` holds every secret — gitignored; never copy it into issues, notes, or chat.
- The dashboard binds `127.0.0.1` only (local machine). To expose it on a LAN, put
  it behind a reverse proxy with auth — never bind it publicly as-is.
- The bot only operates in the single configured guild.
- All enforcement is DRY-RUN until you deliberately set `DRY_RUN=0`.
- Owner alerts contain message excerpts; owners should treat the alert channel as
  staff-only.
