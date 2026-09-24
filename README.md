# TypeSafe AI Bot

**Sanitized public copy.** Built from the private working repo: personal
config, ops notes, and demo media removed; Discord IDs replaced with
placeholders; `DRY_RUN` defaults to **watch-first** here.

## Status — v1 built, DRY-RUN by default

| | |
|---|---|
| **Code** | ✅ complete (bot + dashboard + docs) |
| **Tests** | ✅ 89 passing (`python -m pytest tests/ -q`) |
| **Dashboard** | ✅ verified rendering live (6 views, no JS errors) |
| **Judge chain** | ✅ built + fallback-tested; live AI judging needs your own TypeSafe API key with credits — without one the bot degrades safely (heuristics + human review, never auto-punishes) |
| **Not done** | Discord app token (yours to create — see below), real rules text, live-server validation |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # prove the install
cp .env.example .env                # fill in DISCORD_TOKEN / DISCORD_GUILD_ID / OWNER_IDS
python src/main.py                  # bot (DRY-RUN default: nothing enforced)
python src/dashboard_main.py        # dashboard → http://127.0.0.1:8788
```

Full walkthrough: **[docs/SETUP.md](docs/SETUP.md)** (Discord app creation → review
week → going live → long-term hosting → troubleshooting).

## What it does

- **Chat automod** — every message screened against `policy/rules.json` in ONE
  batched Jev call; high-confidence violations timeout, everything else routes to
  owners for review.
- **Member reports + community votes** — `/report` (mandatory written reason) → Jev
  validates the reason → vote opens in a dedicated channel: *[Mute 1h] [Disconnect]
  [No action]* → passing outcomes execute automatically. Anti-abuse built in.
- **Spam / rate-limit protection** — burst, duplicate, mass-mention, and link-flood
  windows → timeout + channel notice + owner DMs.
- **Nuke protection** — audit-log watcher; rogue mass-deletes/bans/kicks/webhooks →
  privilege strip + lockdown + owner alerts.
- **Role → capability permissions** — select-menu `/setup` panel.
- **Multiple owners, DM alerts** — `/owners`; every critical event reaches all owners.
- **Fail-safe judge chain** — Jev → OpenCode CLI (free Jev) → heuristics + review.
  Circuit breaker with auto-recovery; outages are visible, never silent.

## Layout

```
src/tsabot/              bot: cogs, judge chain, policy, actions, scheduler, antinuke
src/tsabot/dashboard/    FastAPI + no-build frontend (dark control panel)
policy/rules.json        the machine-readable rulebook (replace with your rules)
tools/judge_selftest.py  live Jev API evidence tool
tests/                   89 unit + mocked-Discord integration tests
docs/SETUP.md            self-hosting guide (start here)
docs/SPEC.md             spec (37 user stories) · docs/briefing.html visual briefing
```

## Documentation

- **[docs/SETUP.md](docs/SETUP.md)** — the complete self-hosting guide
- [docs/SPEC.md](docs/SPEC.md) — the spec with user stories + testing decisions
- [docs/briefing.html](docs/briefing.html) — visual architecture briefing

## Secrets

`.env` (gitignored) holds every secret — Discord token and API keys. Never commit
it, never copy its contents elsewhere. The dashboard binds `127.0.0.1` only. The
bot operates in a single configured guild. Nothing enforces until you set
`DRY_RUN=0` deliberately.

## Configuration

Copy `.env.example` to `.env` and fill in your bot token, guild ID, and owner
IDs. Everything runs locally: `python src/main.py` for the bot,
`python src/dashboard_main.py` for the read-only dashboard on
`http://127.0.0.1:8788`. See `docs/SETUP.md` for the full walkthrough.

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).
