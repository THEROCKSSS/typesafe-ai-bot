# Spot-render key frames from demo-reel-v2.html at deterministic times
import sys, pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("<scratch>/reel_v2_spot")
OUT.mkdir(parents=True, exist_ok=True)
HTML = pathlib.Path(__file__).parent.parent / "docs" / "demo-reel-v2.html"

# mid-scene times (ms) — chosen after reveals complete
SPOTS = {
    "s1_hook": 4200,
    "s2_jobs": 13500,
    "s3_pipeline": 27500,
    "s4_feed": 40500,
    "s5_vote": 52500,
    "s6_setup": 64500,
    "s7_close": 70800,
}
errs = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(HTML.resolve().as_uri())
    pg.wait_for_function("typeof window.renderAt === 'function'")
    pg.evaluate("() => document.fonts.ready.then(() => true)")
    pg.wait_for_timeout(1200)
    for name, t in SPOTS.items():
        pg.evaluate("(t) => window.renderAt(t)", float(t))
        pg.wait_for_timeout(60)
        pg.screenshot(path=str(OUT / f"{name}.png"))
        print("rendered", name, "@", t)
    b.close()
print("page errors:", errs or "none")
