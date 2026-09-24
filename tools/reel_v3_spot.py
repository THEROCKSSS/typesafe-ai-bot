# Spot-render key frames from demo-reel-v3.html — times derived from window.TL
import sys, json, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    "<scratch>/reel_v3_spot")
OUT.mkdir(parents=True, exist_ok=True)
HTML = pathlib.Path(__file__).parent.parent / "docs" / "demo-reel-v3.html"

errs = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(HTML.resolve().as_uri())
    pg.wait_for_function("typeof window.renderAt === 'function'")
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    pg.wait_for_timeout(1200)
    tl = pg.evaluate("window.TL")
    # render each scene at open+2.6s (reveals done, subs still rolling)
    spots = {k: int(v[0] + 2600) for k, v in tl.items() if isinstance(v, list)}
    for name, t in spots.items():
        pg.evaluate("(t) => window.renderAt(t)", float(t))
        pg.wait_for_timeout(60)
        pg.screenshot(path=str(OUT / f"{name}_{t}.png"))
        print("rendered", name, "@", t)
    b.close()
print("page errors:", errs or "none")
