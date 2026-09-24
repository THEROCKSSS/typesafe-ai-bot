#!/usr/bin/env python
"""KDF demo restructure — wipe all channels/categories/roles, rebuild the demo layout.

DESTRUCTIVE when run with --execute. Default (no flag) = dry run that prints the plan.

Safety:
  * Run tools/guild_backup.py first (full JSON backup incl. messages).
  * STOP THE BOT before executing — mass channel deletes would trip its antinuke.
  * @everyone and any managed role (the bot's own) are NEVER deleted.

What it does (execute mode):
  1. nulls the system channel pointer
  2. deletes every channel (children first, then categories)
  3. deletes every unmanaged role below the bot's top role
  4. creates the demo roles (Command / Moderator / Member / Muted)
  5. creates the demo categories + channels with permission overwrites
  6. recreates the test webhook in #bot-testing
  7. points the system channel at the new #announcements
  8. creates a permanent invite in #welcome
  9. rewires .env (REPORTS_CHANNEL_ID, MOD_LOG_CHANNEL_ID, TEST_CHANNEL_ID,
     TEST_WEBHOOK_ID, TEST_WEBHOOK_TOKEN) and saves data/restructure_result.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://discord.com/api/v10"
UA = "TypeSafeAIBot/1.0 (ops)"


def load_env() -> dict:
    out: dict = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


ENV = load_env()
TOKEN = ENV["DISCORD_TOKEN"]
GUILD = ENV["DISCORD_GUILD_ID"]


def req(method: str, path: str, body=None, ok404: bool = False, retries: int = 6):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        r = urllib.request.Request(API + path, data=data, method=method)
        r.add_header("Authorization", "Bot " + TOKEN)
        r.add_header("User-Agent", UA)
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
                    wait = float(json.loads(raw or b"{}").get("retry_after", 1.0))
                except Exception:
                    wait = 1.0
                time.sleep(wait + 0.4)
                continue
            if e.code == 404 and ok404:
                return None
            if e.code in (500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise SystemExit(f"{method} {path} -> HTTP {e.code}: {raw[:400]!r}")
    raise SystemExit(f"{method} {path}: retries exhausted")


# ---------------------------------------------------------------- bits
BIT = {
    "ADMINISTRATOR": 1 << 3,
    "ADD_REACTIONS": 1 << 6,
    "VIEW_CHANNEL": 1 << 10,
    "SEND_MESSAGES": 1 << 11,
    "MANAGE_MESSAGES": 1 << 13,
    "EMBED_LINKS": 1 << 14,
    "ATTACH_FILES": 1 << 15,
    "READ_MESSAGE_HISTORY": 1 << 16,
    "CONNECT": 1 << 20,
    "SPEAK": 1 << 21,
    "USE_APPLICATION_COMMANDS": 1 << 31,
    "CREATE_PUBLIC_THREADS": 1 << 34,
    "CREATE_PRIVATE_THREADS": 1 << 36,
    "SEND_MESSAGES_IN_THREADS": 1 << 38,
}


def bits(*names: str) -> int:
    v = 0
    for n in names:
        v |= BIT[n]
    return v


# ---------------------------------------------------------------- spec
ROLE_SPEC = [
    # created low→high order below; positions are set explicitly after creation
    {"name": "Muted", "color": 0x565B62, "hoist": False, "mentionable": False, "permissions": 0},
    {"name": "Member", "color": 0x67DC88, "hoist": False, "mentionable": False, "permissions": 0},
    {"name": "Moderator", "color": 0x6D8B9E, "hoist": True, "mentionable": True, "permissions": 0},
    {"name": "Command", "color": 0xD9AA45, "hoist": True, "mentionable": True,
     "permissions": bits("ADMINISTRATOR")},
]

CATEGORY_SPEC = ["📢 START HERE", "💬 COMMUNITY", "🛡️ MODERATION", "🧪 BOT LAB", "🔊 VOICE"]

# (name, type, category, mode, topic)   type: 0 text, 2 voice
CHANNEL_SPEC = [
    ("welcome", 0, "📢 START HERE", "ro",
     "Start here — what this server is and how the demo works."),
    ("announcements", 0, "📢 START HERE", "ro", "Server updates."),
    ("command-guide", 0, "📢 START HERE", "ro",
     "Every command, explained. Post guides to any channel from the dashboard."),
    ("general", 0, "💬 COMMUNITY", "chat",
     "Main chat — the bot reads messages here."),
    ("clips", 0, "💬 COMMUNITY", "chat", "Screenshots and clips."),
    ("member-reports", 0, "💬 COMMUNITY", "reports",
     "File a report with /report — AI reviews the reason, the community votes on the outcome."),
    ("mod-desk", 0, "🛡️ MODERATION", "staff", "Moderator coordination."),
    ("mod-log", 0, "🛡️ MODERATION", "staff", "Every moderation action, logged automatically."),
    ("bot-testing", 0, "🧪 BOT LAB", "staff",
     "Live test feed — messages posted here are screened in real time."),
    ("bot-lab", 0, "🧪 BOT LAB", "staff", "Run /status, /help, /jev, /case here during demos."),
    ("General Operations", 2, "🔊 VOICE", "voice_open", None),
    ("Command Briefing", 2, "🔊 VOICE", "voice_staff", None),
    ("Field Team", 2, "🔊 VOICE", "voice_open", None),
]

STAFF_ROLES = ("Command", "Moderator")
RO_ALLOW = bits("VIEW_CHANNEL", "READ_MESSAGE_HISTORY", "ADD_REACTIONS", "USE_APPLICATION_COMMANDS")
RO_DENY = bits("SEND_MESSAGES", "CREATE_PUBLIC_THREADS", "CREATE_PRIVATE_THREADS",
               "SEND_MESSAGES_IN_THREADS")
CHAT_ALLOW = bits("VIEW_CHANNEL", "SEND_MESSAGES", "READ_MESSAGE_HISTORY", "ADD_REACTIONS",
                  "ATTACH_FILES", "EMBED_LINKS", "USE_APPLICATION_COMMANDS")
STAFF_ALLOW = CHAT_ALLOW | bits("MANAGE_MESSAGES")
VOICE_ALLOW = bits("VIEW_CHANNEL", "CONNECT", "SPEAK")


def overwrites(mode: str, everyone: str, staff_ids: list[str]) -> list:
    def ow(rid, allow=0, deny=0):
        return {"id": str(rid), "type": 0, "allow": str(allow), "deny": str(deny)}

    if mode in ("ro", "reports"):
        out = [ow(everyone, RO_ALLOW, RO_DENY)]
        out += [ow(r, STAFF_ALLOW, 0) for r in staff_ids]
        return out
    if mode == "chat":
        return [ow(everyone, CHAT_ALLOW, 0)]
    if mode == "staff":
        out = [ow(everyone, 0, BIT["VIEW_CHANNEL"])]
        out += [ow(r, STAFF_ALLOW, 0) for r in staff_ids]
        return out
    if mode == "voice_open":
        return [ow(everyone, VOICE_ALLOW, 0)]
    if mode == "voice_staff":
        out = [ow(everyone, 0, BIT["VIEW_CHANNEL"] | BIT["CONNECT"])]
        out += [ow(r, VOICE_ALLOW, 0) for r in staff_ids]
        return out
    raise ValueError(mode)


def env_set(path: pathlib.Path, updates: dict) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    seen = set()
    out = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="actually perform the restructure")
    args = ap.parse_args()

    guild = req("GET", f"/guilds/{GUILD}")
    channels = req("GET", f"/guilds/{GUILD}/channels")
    roles = req("GET", f"/guilds/{GUILD}/roles")
    me = req("GET", "/users/@me")
    me_member = req("GET", f"/guilds/{GUILD}/members/{me['id']}")

    bot_roles = {r["id"] for r in roles if r["id"] in set(me_member.get("roles", []))}
    bot_top = max((r["position"] for r in roles if r["id"] in bot_roles), default=0)

    del_channels = [c for c in channels if c["type"] != 4] + [c for c in channels if c["type"] == 4]
    del_roles = [r for r in roles
                 if r["name"] != "@everyone" and not r.get("managed") and r["position"] < bot_top]

    print(f"guild: {guild['name']} ({GUILD}) | bot top role position: {bot_top}")
    print(f"to DELETE: {len(del_channels)} channels "
          f"({sum(1 for c in channels if c['type'] == 4)} categories + "
          f"{sum(1 for c in channels if c['type'] != 4)} normal) and {len(del_roles)} roles")
    print("  channels:", ", ".join(f"#{c['name']}" for c in del_channels))
    print("  roles   :", ", ".join(r["name"] for r in del_roles))
    print()
    print(f"to CREATE: {len(ROLE_SPEC)} roles, {len(CATEGORY_SPEC)} categories, "
          f"{len(CHANNEL_SPEC)} channels:")
    for name, ctype, cat, mode, _ in CHANNEL_SPEC:
        kind = "voice" if ctype == 2 else "text"
        print(f"  [{kind:5}] {cat} → #{name}  ({mode})")
    print(f"  roles: {', '.join(r['name'] for r in ROLE_SPEC)}")
    print()

    # read-only extras
    try:
        automod = req("GET", f"/guilds/{GUILD}/automod/rules")
    except SystemExit:
        automod = []
    try:
        events = req("GET", f"/guilds/{GUILD}/scheduled-events")
    except SystemExit:
        events = []
    print(f"automod rules: {len(automod)} | scheduled events: {len(events)}")
    if automod:
        for a in automod:
            print("  automod:", a.get("name"))
    if events:
        for e in events:
            print("  event:", e.get("name"))

    if not args.execute:
        print()
        print("DRY RUN — nothing changed. Re-run with --execute to perform the restructure.")
        return

    # ------------------------------------------------------------------ execute
    print("== executing ==")
    print("1) system channel -> null")
    req("PATCH", f"/guilds/{GUILD}", {"system_channel_id": None})

    print(f"2) deleting {len(del_channels)} channels")
    for c in del_channels:
        req("DELETE", f"/channels/{c['id']}", ok404=True)
        print("   -", c["name"])
        time.sleep(0.35)

    print(f"3) deleting {len(del_roles)} roles")
    for r in del_roles:
        req("DELETE", f"/guilds/{GUILD}/roles/{r['id']}", ok404=True)
        print("   -", r["name"])
        time.sleep(0.35)

    print("4) creating roles")
    made_roles: dict[str, str] = {}
    for spec in ROLE_SPEC:
        r = req("POST", f"/guilds/{GUILD}/roles",
                {"name": spec["name"], "color": spec["color"], "hoist": spec["hoist"],
                 "mentionable": spec["mentionable"], "permissions": str(spec["permissions"])})
        made_roles[spec["name"]] = r["id"]
        print("   +", spec["name"])
        time.sleep(0.3)

    roles_now = req("GET", f"/guilds/{GUILD}/roles")
    bot_pos = max(r["position"] for r in roles_now if r.get("managed"))
    order = ["Command", "Moderator", "Member", "Muted"]
    for i, name in enumerate(order):
        pos = max(1, bot_pos - 1 - i)
        req("PATCH", f"/guilds/{GUILD}/roles/{made_roles[name]}", {"position": pos})
        time.sleep(0.25)
    print("   positions set:", {n: max(1, bot_pos - 1 - i) for i, n in enumerate(order)})

    print("5) creating categories + channels")
    cat_ids: dict[str, str] = {}
    for i, name in enumerate(CATEGORY_SPEC):
        r = req("POST", f"/guilds/{GUILD}/channels", {"name": name, "type": 4, "position": i})
        cat_ids[name] = r["id"]
        print("   +", name)
        time.sleep(0.3)

    ch_ids: dict[str, str] = {}
    pos_in: dict[str, int] = {}
    staff_ids = [made_roles[n] for n in STAFF_ROLES]
    for name, ctype, cat, mode, topic in CHANNEL_SPEC:
        p = pos_in.get(cat, 0)
        pos_in[cat] = p + 1
        body = {"name": name, "type": ctype, "parent_id": cat_ids[cat], "position": p,
                "permission_overwrites": overwrites(mode, str(GUILD), staff_ids)}
        if ctype == 0 and topic:
            body["topic"] = topic
        r = req("POST", f"/guilds/{GUILD}/channels", body)
        ch_ids[name] = r["id"]
        print("   +", name)
        time.sleep(0.35)

    print("6) recreating test webhook in #bot-testing")
    wh = req("POST", f"/channels/{ch_ids['bot-testing']}/webhooks", {"name": "tsabot-test-feed"})
    print("   webhook:", wh["id"])

    print("7) system channel -> #announcements")
    req("PATCH", f"/guilds/{GUILD}", {"system_channel_id": ch_ids["announcements"]})

    print("8) invite in #welcome")
    inv = req("POST", f"/channels/{ch_ids['welcome']}/invites",
              {"max_age": 0, "max_uses": 0, "unique": False})
    print("   invite: https://discord.gg/" + inv["code"])

    print("9) rewiring .env")
    env_set(ROOT / ".env", {
        "REPORTS_CHANNEL_ID": ch_ids["member-reports"],
        "MOD_LOG_CHANNEL_ID": ch_ids["mod-log"],
        "TEST_CHANNEL_ID": ch_ids["bot-testing"],
        "TEST_WEBHOOK_ID": wh["id"],
        "TEST_WEBHOOK_TOKEN": wh["token"],
    })

    result = {
        "guild_id": GUILD,
        "deleted": {"channels": [c["name"] for c in del_channels],
                    "roles": [r["name"] for r in del_roles]},
        "roles": made_roles,
        "categories": cat_ids,
        "channels": ch_ids,
        "webhook": {"id": wh["id"], "channel": "bot-testing"},
        "invite": inv["code"],
    }
    out = ROOT / "data" / "restructure_result.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print()
    print("DONE. result:", out)
    print("invite:      https://discord.gg/" + inv["code"])
    print("next: post demo content, then restart the bot + dashboard.")


if __name__ == "__main__":
    main()
