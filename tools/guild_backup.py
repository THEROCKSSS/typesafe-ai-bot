#!/usr/bin/env python
"""Read-only guild backup + recon for the TypeSafe AI Bot demo restructure.

Fetches the full server state (guild, channels, roles, members, webhooks,
application commands) plus the last 100 messages per text channel, and saves
everything to data/backups/guild_backup_<ts>.json.

This tool is READ-ONLY. It never deletes or modifies anything.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://discord.com/api/v10"
UA = "TypeSafeAIBot/1.0 (local ops)"


def load_env() -> dict:
    env: dict = {}
    p = ROOT / ".env"
    if not p.is_file():
        sys.exit("no .env at " + str(p))
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
TOKEN = ENV.get("DISCORD_TOKEN")
if not TOKEN:
    sys.exit("DISCORD_TOKEN missing from .env")
GUILD = ENV.get("GUILD_ID") or "1000000000000000001"


def req(method: str, path: str, body=None, retries: int = 5):
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
            if e.code == 429:
                wait = 1.0
                try:
                    wait = float(json.loads(e.read() or b"{}").get("retry_after", 1.0))
                except Exception:
                    pass
                time.sleep(wait + 0.5)
                continue
            if e.code in (500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise SystemExit(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}")
    raise SystemExit(f"{method} {path}: exhausted retries")


def main() -> None:
    guild = req("GET", f"/guilds/{GUILD}?with_counts=true")
    channels = req("GET", f"/guilds/{GUILD}/channels")
    roles = req("GET", f"/guilds/{GUILD}/roles")
    members = req("GET", f"/guilds/{GUILD}/members?limit=1000")
    webhooks = req("GET", f"/guilds/{GUILD}/webhooks")
    me = req("GET", "/users/@me")
    me_member = req("GET", f"/guilds/{GUILD}/members/{me['id']}")
    app = req("GET", "/applications/@me")
    try:
        app_cmds = req("GET", f"/applications/{app['id']}/guilds/{GUILD}/commands")
    except SystemExit:
        app_cmds = []

    msgs: dict = {}
    for ch in channels:
        if ch["type"] in (0, 5):
            try:
                msgs[ch["id"]] = req("GET", f"/channels/{ch['id']}/messages?limit=100")
            except SystemExit as e:
                msgs[ch["id"]] = [{"_error": str(e)}]
            time.sleep(0.25)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = ROOT / "data" / "backups"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"guild_backup_{ts}.json"
    out.write_text(
        json.dumps(
            {
                "guild": guild,
                "channels": channels,
                "roles": roles,
                "members": members,
                "webhooks": webhooks,
                "app_commands": app_cmds,
                "messages": msgs,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------ summary ------------------
    cats = {c["id"]: c for c in channels if c["type"] == 4}
    my_roles = set(me_member.get("roles", []))
    bot_roles = [r for r in roles if r["id"] in my_roles]
    bot_top = max((r["position"] for r in bot_roles), default=0)
    name_of = {c["id"]: c["name"] for c in channels}

    print(f"GUILD  {guild['name']}  id={guild['id']}  owner_id={guild.get('owner_id')}")
    print(
        f"       members~{guild.get('approximate_member_count')} "
        f"online~{guild.get('approximate_presence_count')}  "
        f"features={','.join(guild.get('features', [])) or 'none'}"
    )
    print(f"       system_channel={guild.get('system_channel_id')}  "
          f"afk={guild.get('afk_channel_id')}  verification={guild.get('verification_level')}")
    print()
    print("CATEGORIES:")
    for c in sorted(cats.values(), key=lambda x: x["position"]):
        print(f"   {c['name']}   (id {c['id']})")
    print("CHANNELS:")
    kind = {0: "text", 2: "voice", 5: "announce", 13: "stage", 15: "forum"}
    for c in sorted(
        [c for c in channels if c["type"] != 4],
        key=lambda x: (x.get("parent_id") or "0", x["position"]),
    ):
        parent = cats.get(c.get("parent_id") or "", {}).get("name", "—")
        print(f"   [{kind.get(c['type'], c['type']):>7}] #{c['name']}   under {parent}   (id {c['id']})")
    print()
    print(f"ROLES (bot highest pos = {bot_top}, bot roles: {[r['name'] for r in bot_roles]}):")
    for r in sorted(roles, key=lambda x: -x["position"]):
        tags = []
        if r["name"] == "@everyone":
            tags.append("EVERYONE")
        if r.get("managed"):
            tags.append("MANAGED")
        if r["id"] in my_roles:
            tags.append("BOT")
        if int(r.get("permissions", 0)) & 8:
            tags.append("ADMIN")
        if r["name"] != "@everyone" and not r.get("managed"):
            tags.append("deletable" if r["position"] < bot_top else "ABOVE-BOT")
        print(f"   pos {r['position']:>2}  {r['name']:<26} #{r.get('color', 0):06X}  {' '.join(tags)}")
    print()
    print("MEMBERS:")
    for m in members:
        u = m["user"]
        print(f"   {u['username']}  id={u['id']}  bot={u.get('bot', False)}  roles={m.get('roles')}")
    print()
    print("WEBHOOKS:", [(w["name"], w["channel_id"]) for w in webhooks] or "none")
    print("APP:", app.get("name"), "| guild commands synced:", len(app_cmds))
    print()
    print("message backup:", {name_of.get(k, k): len(v) for k, v in msgs.items()})
    print("BACKUP FILE:", out)


if __name__ == "__main__":
    main()
