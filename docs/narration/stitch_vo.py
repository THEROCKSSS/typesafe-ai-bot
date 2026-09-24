"""Stitch narration clips into one voice track aligned to the TL timeline.

Each clip is placed at its scene's start + vo_off (900ms). Adelay in ffmpeg
is integer ms; we build one filter chain from the 9 wavs onto a silent base.
"""
import json, subprocess
from pathlib import Path

D = Path(__file__).parent
tl = json.loads((D / "timeline.json").read_text())
end = tl["end"]
inputs = []
parts = []
k = 0
for sid, clip in tl["scene_clip"].items():
    if not clip:
        continue
    start = tl["tl"][sid][0] + tl["vo_off"]
    inputs += ["-i", str(D / clip)]
    parts.append(f"[{k + 1}]adelay={start}:all=1[a{k}]")
    k += 1

n = len(parts)
mix = "[0]" + "".join(f"[a{i}]" for i in range(n))
fc = ";".join(parts) + f";{mix}amix=inputs={n + 1}:normalize=0:duration=first[out]"
cmd = ["ffmpeg", "-y", "-f", "lavfi", "-t", f"{end/1000:.3f}", "-i",
       "anullsrc=r=44100:cl=mono"] + inputs + \
      ["-filter_complex", fc, "-map", "[out]", "-c:a", "pcm_s16le", str(D / "vo_full.wav")]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1500:])
    raise SystemExit(1)
dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(D / "vo_full.wav")],
                    capture_output=True, text=True).stdout.strip()
print("vo_full.wav duration:", dur, "| target:", end / 1000)
