# Full frame capture for demo-reel-v3 (resumable, JPEG q=92, forward or reverse worker)
# N derived from window.TL.END in the page itself.
import sys, pathlib, time
from playwright.sync_api import sync_playwright

FPS = 30
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    "<scratch>/reel_v3_frames")
REVERSE = len(sys.argv) > 2 and sys.argv[2] == "rev"
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
    pg.wait_for_timeout(1500)
    END = pg.evaluate("window.TL.END")
    N = int(END * FPS / 1000) + 1
    print(f"TL.END={END}ms -> N={N} frames", flush=True)
    done = skipped = 0
    t0 = time.time()
    order = range(N - 1, -1, -1) if REVERSE else range(N)
    for i in order:
        p = OUT / f"f_{i:05d}.jpg"
        if p.exists():
            skipped += 1
            continue
        pg.evaluate("(t) => window.renderAt(t)", i * 1000.0 / FPS)
        pg.screenshot(path=str(p), type="jpeg", quality=92)
        done += 1
        if done % 100 == 0:
            rate = done / (time.time() - t0)
            rem = N - done - skipped
            print(f"{'rev' if REVERSE else 'fwd'} {done}/{N} · {rate:.1f} fps · eta {rem/rate:.0f}s", flush=True)
    b.close()
print(f"capture complete: {done} new, {skipped} skipped, N={N}")
print("page errors:", errs[:5] or "none")
