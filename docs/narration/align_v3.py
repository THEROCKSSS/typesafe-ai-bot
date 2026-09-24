"""Final timeline: TL = [start,end] pairs matching clip durations; close VO rides s10."""
import json, subprocess, re
from pathlib import Path

D = Path(__file__).parent
html_path = (D / ".." / "demo-reel-v3.html").resolve()

def dur(sid):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=nw=1:nk=1", str(D / f"{sid}.wav")], capture_output=True, text=True)
    return int(round(float(r.stdout.strip()) * 1000))

d = {f"s{i}": dur(f"s{i}") for i in range(1, 10)}
print("durations ms:", d)

GAP = 250      # breathing between scenes
VO_OFF = 900   # clip starts 900ms into its scene window
S9_HOLD = 4600 # silent 'optional vs always-on' beat
TAIL = 1500    # hold after close VO

tl = {}
cur = 0
for i in range(1, 9):           # s1..s8: VO + gap
    end = cur + VO_OFF + d[f"s{i}"] + GAP
    tl[f"s{i}"] = (cur, end)
    cur = end
tl["s9"] = (cur, cur + S9_HOLD) # silent defaults beat
cur += S9_HOLD
tl["s10"] = (cur, cur + VO_OFF + d["s9"] + TAIL)
END = tl["s10"][1]
print("TL:", tl, "END:", END, f"({END/1000:.1f}s)")

html = html_path.read_text(encoding="utf-8")

# close VO rides the close scene
html = html.replace('  s9:"Reads your rules', '  s10:"Reads your rules')

new_tl = "const TL = {\n" + "".join(
    f"  {k}:[{v[0]:>7},{v[1]:>7}],\n" for k, v in tl.items()) + f"  END: {END:>6},\n}};"
old = re.search(r"const TL = \{.*?\n\};", html, re.S).group(0)
html = html.replace(old, new_tl)
html_path.write_text(html, encoding="utf-8")
print("patched", html_path.name)

# scene -> VO clip file (s9 scene is silent; s10 scene uses clip s9.wav)
mapping = {f"s{i}": f"s{i}.wav" for i in range(1, 9)}
mapping["s9"] = None
mapping["s10"] = "s9.wav"
json.dump({"tl": {k: list(v) for k, v in tl.items()}, "vo_off": VO_OFF,
           "dur": d, "scene_clip": mapping, "end": END},
          open(D / "timeline.json", "w"), indent=2)
