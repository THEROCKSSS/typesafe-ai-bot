#!/usr/bin/env python
"""Seed demo content into the fresh KDF restructure.

Posts welcome + guide content into the new channels as the bot, so the demo
looks alive the moment someone opens it. Idempotent enough (safe to re-run;
it just posts again).

Usage: python tools/seed_demo_content.py
"""
from __future__ import annotations

import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://discord.com/api/v10"


def load_env() -> dict:
    env: dict = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
TOKEN = ENV["DISCORD_TOKEN"]
GUILD = ENV["DISCORD_GUILD_ID"]


def req(method: str, path: str, body=None, ok404: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header("Authorization", "Bot " + TOKEN)
    r.add_header("User-Agent", "TypeSafeAIBot/1.0")
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        if e.code == 429:
            try:
                wait = float(json.loads(raw or b"{}").get("retry_after", 1.2))
            except Exception:
                wait = 1.2
            time.sleep(wait + 0.4)
            return req(method, path, body, ok404)
        if e.code == 404 and ok404:
            return None
        raise SystemExit(f"{method} {path} -> {e.code}: {raw[:300]!r}")


channels = {c["name"]: c["id"] for c in req("GET", f"/guilds/{GUILD}/channels")}


def post(channel: str, payload: dict) -> None:
    cid = channels.get(channel)
    if not cid:
        print(f"  ! channel #{channel} missing, skipping")
        return
    req("POST", f"/channels/{cid}/messages", payload)
    print(f"  → #{channel}")
    time.sleep(0.8)


# ------------------------------------------------------------------ content
def embed(title, desc, color, fields=None, footer=None):
    e = {"title": title, "description": desc, "color": color}
    if fields:
        e["fields"] = fields
    if footer:
        e["footer"] = {"text": footer}
    return {"embeds": [e]}


print("seeding demo content into fresh KDF…")

# 1. welcome
post("welcome", embed(
    "Welcome to Knox Defense Force",
    "This server runs the **TypeSafe AI Bot** — moderation that reads the rules, "
    "explains every call, and hands real consequences to a community vote.\n\n"
    "**Start here:**\n"
    "• `/help` — see everything your role can do\n"
    "• `/status` — check the bot is online\n"
    "• Head to **#command-guide** for the full walkthrough",
    0x6EE7B7,
    fields=[
        {"name": "For members", "value": "`/report` a rule-breaker (reason required) · "
                                          "`/votes` to see open votes", "inline": False},
        {"name": "How it works", "value": "The AI reviews every message against the server "
                                          "rules and every report's reason. Nothing is "
                                          "enforced on a guess — borderline cases go to "
                                          "the mod team.", "inline": False},
    ],
    footer="TypeSafe AI Bot · judged by TypeSafe Jev",
))

# 2. member guide
post("command-guide", embed(
    "📘 Member guide",
    "**Reporting someone**\n"
    "`/report` → pick the member → **write a real reason** (this is required).\n"
    "The AI checks your reason describes actual behavior. If it's valid, a community "
    "vote opens for **10 minutes** — the community picks the outcome, and the AI reviews "
    "it before anything applies.\n\n"
    "**Seeing what's happening**\n"
    "`/votes` — open votes right now\n"
    "`/case @user` — (mods) full history with names and reasons\n"
    "`/help` — everything your role can use",
    0x67DC88,
    footer="TypeSafe AI Bot · member tier",
))

# 3. moderator guide
post("command-guide", embed(
    "🛡️ Moderator guide",
    "**Acting on a member**\n"
    "`/panel @user` — buttons for warn / voice-mute / disconnect\n"
    "`/warn` — logged warning, no enforcement\n"
    "`/mute` — voice mute for 1h, **the bot lifts it automatically**\n"
    "`/disconnect` — pull them out of voice\n\n"
    "**Votes**\n"
    "`/votes` — open votes · `/veto <id>` — cancel an abused vote\n\n"
    "**Reviewing**\n"
    "Every automated decision lands in **#mod-log** and your DMs. If the AI is unsure, "
    "it asks you instead of acting.",
    0x6D8B9E,
    footer="TypeSafe AI Bot · moderator tier",
))

# 4. owner guide
post("command-guide", embed(
    "👑 Owner guide",
    "`/setup` — role → capability menus (pick a role, tick what it may do)\n"
    "`/owners` — add/remove owners and owner roles\n"
    "`/config` — reports channel, log channel, thresholds\n"
    "`/jev` — AI health, usage, and cost — in plain words\n"
    "`/status` — uptime, mode, latency, cases, open votes\n\n"
    "Thresholds are live-editable; no restart needed.",
    0xD9AA45,
    footer="TypeSafe AI Bot · owner tier",
))

# 5. reports channel explainer
post("member-reports", embed(
    "Community reports",
    "Use `/report` here (or right-click any message → **Report to mods**).\n\n"
    "**A written reason is required.** The AI checks it's a real description of "
    "behavior — vague or spammy reports get closed (and repeat abuse loses "
    "reporting rights).",
    0x818CF8,
    footer="TypeSafe AI Bot · reports",
))

# 6. general — a little life
post("general", embed(
    "Demo server ready",
    "Channels, roles, and the bot are live. Try `/status` or say hi — the bot reads "
    "messages here and only speaks up when the rules are actually at stake.",
    0x6EE7B7,
))

# 7. bot-lab explainer
post("bot-lab", embed(
    "🧪 Bot lab",
    "**This is the demo room.** Run any command here without touching the rest of the "
    "server — `/status`, `/help`, `/jev`, `/case`, `/panel`.\n\n"
    "`#bot-testing` next door is the live webhook feed: messages posted there are "
    "screened by the bot in real time, exactly like real chat.",
    0xF5B95F,
    footer="TypeSafe AI Bot · testing",
))

print("\ndone.")
