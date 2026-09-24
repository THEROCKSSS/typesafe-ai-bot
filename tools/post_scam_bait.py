import re, httpx
env = dict(re.findall(r'^([A-Z_]+)=(.*)$', open(".env", encoding="utf-8").read(), re.M))
tok = env["DISCORD_TOKEN"]; wh = env["TEST_WEBHOOK_ID"]; wht = env["TEST_WEBHOOK_TOKEN"]
r = httpx.post(f"https://discord.com/api/v10/webhooks/{wh}/{wht}?wait=true",
               json={"username": "SGT_Flash",
                     "content": "FREE NITRO everyone 🎉🎉 claim your gift at https://discord-nitro-gift.example.com before it expires"},
               timeout=30)
print("post:", r.status_code, r.json().get("id"))
