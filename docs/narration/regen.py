import json, subprocess, time, httpx
from pathlib import Path

base = "http://127.0.0.1:17493"
c = httpx.Client(base_url=base, timeout=30)
prof = "00000000-0000-0000-0000-000000000000"
lines = json.loads(Path("regen.json").read_text(encoding="utf-8"))
dur = json.loads(Path("durations.json").read_text())

def probe(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(o.stdout.strip())

for sid, text in lines.items():
    out = Path(sid + ".wav")
    if out.exists():
        out.unlink()
    r = c.post("/generate", json={"profile_id": prof, "text": text,
                                  "engine": "chatterbox_turbo", "language": "en"})
    r.raise_for_status()
    gen_id = r.json().get("generation_id") or r.json().get("id")
    t0 = time.time()
    while time.time() - t0 < 300:
        time.sleep(2)
        hh = c.get(f"/history/{gen_id}").json()
        st = hh.get("status")
        if st == "completed":
            out.write_bytes(c.get(f"/audio/{gen_id}").content)
            dur[sid] = round(probe(out), 2)
            print(f"ok: {sid}.wav ({dur[sid]}s)")
            break
        if st == "failed":
            raise SystemExit(f"FAILED {sid}: {hh.get('error')}")
    else:
        raise SystemExit(f"timeout {sid}")

Path("durations.json").write_text(json.dumps(dur, indent=2))
print("durations:", dur)
