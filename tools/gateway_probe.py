"""Standalone gateway probe: what does the bot ACTUALLY receive?

Connects with the real token, logs every message/raw event for 45s.
Run while posting messages to the test channel to see what arrives.
"""
import asyncio, json, pathlib, sys

sys.path.insert(0, "src")
import discord

TOKEN = [l.split("=", 1)[1].strip() for l in
         pathlib.Path(".env").read_text(encoding="utf-8").splitlines()
         if l.startswith("DISCORD_TOKEN=")][0]

intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"[probe] connected as {client.user} | latency={client.latency*1000:.0f}ms")
    print(f"[probe] intents: message_content={client.intents.message_content} "
          f"members={client.intents.members} guilds={client.intents.guilds}")
    print("[probe] listening 45s for message events...")


@client.event
async def on_message(message: discord.Message):
    print(f"[MSG] ch={message.channel.id} webhook={message.webhook_id} "
          f"author={message.author} (bot={message.author.bot}) "
          f"content_len={len(message.content or '')} content={message.content[:60]!r}")


@client.event
async def on_error(event, *args, **kwargs):
    print(f"[ERR] {event}: {args} {kwargs}")


@client.event
async def on_disconnect():
    print("[probe] DISCONNECTED")


async def main():
    try:
        await asyncio.wait_for(client.start(TOKEN), timeout=50)
    except asyncio.TimeoutError:
        await client.close()
        print("[probe] 45s elapsed — done")


asyncio.run(main())
