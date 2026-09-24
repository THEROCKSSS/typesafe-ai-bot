"""Generate all narration clips via Voicebox (chatterbox_turbo, cloned Owen voice).

For each scene in narration.json: POST /generate, poll /history/<id> until
completed (loading_model counts as progress), GET /audio/<id> -> docs/narration/<id>.wav.
Idempotent: skips clips already on disk unless --force. Appends durations to
durations.json for the v3 timeline build.
"""
import json, sys, time, pathlib
import httpx

HERE = pathlib.Path(__file__).parent
spec = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
force = "--force" in sys.argv
h = httpx.Client(base_url="http://127.0.0.1:17493", timeout=30)

durations = {}
if (HERE / "durations.json").exists():
    durations = json.loads((HERE / "durations.json").read_text())

for sc in spec["scenes"]:
    sid = sc["id"]
    out = HERE / f"{sid}.wav"
    if out.exists() and not force:
        print(f"[skip] {sid} already on disk")
        if sid not in durations:
            import subprocess
            d = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(out)],
                capture_output=True, text=True).stdout.strip()
            durations[sid] = round(float(d), 2)
            print(f"       probed {sid}: {durations[sid]}s")
        continue

    print(f"[gen ] {sid}: {sc['line'][:60]}...")
    r = h.post("/generate", json={
        "profile_id": spec["profile_id"], "text": sc["line"],
        "engine": spec["engine"], "language": spec["language"]}).json()
    gid = r.get("id")
    if not gid:
        print("  !! generate failed:", r)
        sys.exit(1)
    deadline = time.time() + 420
    st = None
    while time.time() < deadline:
        rr = h.get(f"/history/{gid}").json()
        st = rr.get("status")
        if st == "completed":
            dur = rr.get("duration") or 0
            a = h.get(f"/audio/{gid}")
            if a.content[:4] != b"RIFF":
                print("  !! not RIFF audio:", a.content[:40])
                sys.exit(1)
            out.write_bytes(a.content)
            durations[sid] = dur
            print(f"  ok: {out.name} ({dur}s, {len(a.content)} bytes)")
            break
        if st in ("failed", "error"):
            print("  !! generation failed:", rr.get("error"))
            sys.exit(1)
        time.sleep(3)
    else:
        print(f"  !! timeout; last status {st}")
        sys.exit(1)
    (HERE / "durations.json").write_text(
        json.dumps(durations, indent=2), encoding="utf-8")

(HERE / "durations.json").write_text(json.dumps(durations, indent=2), encoding="utf-8")
print("durations.json:", json.dumps(durations, indent=2))
total = sum(durations.get(s["id"], 0) for s in spec["scenes"])
print(f"total speech: {total:.1f}s across {len(spec['scenes'])} scenes")
