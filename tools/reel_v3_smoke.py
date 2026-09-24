"""Smoke-check demo-reel-v3.html: render at TL-driven timestamps, catch JS errors."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "demo-reel-v3.html").resolve()
URL = DOC.as_uri()

JS = ("(t)=>{renderAt(t);"
      "let best='?',bo=-1;document.querySelectorAll('.scene').forEach(s=>{"
      "const o=parseFloat(s.style.opacity||'0');if(o>bo){bo=o;best=s.id}});"
      "return {t,scene:best,op:bo,sub:(document.getElementById('subs').textContent||'').slice(0,40)}}")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.wait_for_timeout(1500)
    tl = pg.evaluate("window.TL")
    probes = []
    for k, v in tl.items():
        if k == "END" or not isinstance(v, list):
            continue
        a, z = v
        probes += [a + 1500, (a + z) // 2, z - 500]
    for t in probes:
        st = pg.evaluate(JS, int(t))
        print(f"{int(t):>7} {st['scene']:>4} op={st['op']:.2f} | {st['sub']}")
    print("TL.END", tl["END"], "| errors:", errs or "none")
    b.close()
