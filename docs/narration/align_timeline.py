import json, subprocess, re
from pathlib import Path
DUR = json.loads(Path("durations.json").read_text())
# measured from the wavs actually on disk now (regen may have changed s4/s5)
meas = {}
for sid in ["s1","s2","s3","s4","s5","s6","s7","s8"]:
    d = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1", f"{sid}.wav"], capture_output=True, text=True)
    meas[sid] = round(float(d.stdout.strip()), 3)
print("measured:", meas)
print("in durations.json:", {k: DUR.get(k) for k in meas})
Path("durations.json").write_text(json.dumps(meas, indent=2))
print("durations.json rewritten with measured durations")

# rebuild TL + TLX exactly as in demo-reel-v3.html
LEAD, PAD = 800, 250
GAP0 = 500   # between hook end and s2 start
starts = {}
cur = LEAD
order = ["s1","s2","s3","s4","s5","s6","s7","s8"]
for i, sid in enumerate(order):
    starts[sid] = cur
    cur += int(meas[sid]*1000) + (GAP0 if i == 0 else PAD) + (0 if i == len(order)-1 else 0)
end = cur + 1500
tl = {"s0": LEAD}
for sid in order[1:]:
    tl[sid] = starts[sid]
tl["END"] = end
print("TL:", tl)

src = Path("../../demo-reel-v3.html").resolve()
html = src.read_text(encoding="utf-8")
old = re.search(r"const TL = \{.*?\};", html, re.S).group(0)
new = "const TL = " + json.dumps(tl) + ";"
html = html.replace(old, new)
oldx = re.search(r"const TLX = \{.*?\};", html, re.S).group(0)
newx = "const TLX = " + json.dumps(starts) + ";"
html = html.replace(oldx, newx)
src.write_text(html, encoding="utf-8")
print("patched TL/TLX into", src.name)
