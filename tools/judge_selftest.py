#!/usr/bin/env python3
"""Live judge selftest — hits the REAL Jev API with known hostile/benign samples.

Evidence tool: exits 0 only when the primary judge answers correctly.
Run:  python tools/judge_selftest.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tsabot.config import load_config          # noqa: E402
from tsabot.judge import JudgeChain            # noqa: E402

HOSTILE = "everyone here is trash lol, uninstall — nobody likes you"
BENIGN = "gg that was a great raid tonight, thanks for the help everyone!"

SAMPLE_RULES = [
    {"id": "harassment", "title": "No harassment", "description":
     "Insulting, demeaning, or targeting another member with hostile language.",
     "severity": "high", "enabled": True, "auto_action": "timeout"},
    {"id": "spam_advertising", "title": "No spam", "description":
     "Repeated posting, invite links, or advertising without permission.",
     "severity": "medium", "enabled": True, "auto_action": "review"},
]

SAMPLE_REASON = "They kept screaming slurs at people in the voice channel and wouldn't stop after warnings."


def main() -> int:
    cfg = load_config(base=ROOT)
    if not cfg.typesafe_api_key:
        print("FAIL: TYPESAFE_API_KEY not configured in .env")
        return 2

    chain = JudgeChain(cfg, db=None)
    failures = []

    print("=" * 62)
    print("JUDGE SELFTEST — live TypeSafe Jev API")
    print("=" * 62)

    # 1. hostile message
    print(f"\n[1] HOSTILE sample: {HOSTILE[:60]!r}")
    res = chain.ask_message(content=HOSTILE, author="griefer42", channel="general",
                            rules=SAMPLE_RULES)
    print(f"    layer={res.layer} model={res.model} ok={res.ok} "
          f"tokens={res.input_tokens} latency={res.latency_ms}ms")
    p = float((res.verdicts.get("harassment") or {}).get("noul", 0.0))
    print(f"    harassment noul = {p:.3f}")
    if res.layer != "jev":
        failures.append(f"hostile: expected layer 'jev', got '{res.layer}' ({res.error})")
    if p < 0.5:
        failures.append(f"hostile: harassment probability {p:.2f} < 0.5 — model did not flag")

    # 2. benign message
    print(f"\n[2] BENIGN sample: {BENIGN[:60]!r}")
    res2 = chain.ask_message(content=BENIGN, author="friendly", channel="general",
                             rules=SAMPLE_RULES)
    print(f"    layer={res2.layer} ok={res2.ok} tokens={res2.input_tokens}")
    p2 = float((res2.verdicts.get("harassment") or {}).get("noul", 0.0))
    print(f"    harassment noul = {p2:.3f}")
    if p2 > 0.5:
        failures.append(f"benign: harassment probability {p2:.2f} > 0.5 — false positive")

    # 3. report reason gate
    print(f"\n[3] REPORT REASON: {SAMPLE_REASON[:60]!r}")
    res3 = chain.ask_report_reason(reporter="member1", target="griefer42",
                                   reason=SAMPLE_REASON)
    print(f"    layer={res3.layer} ok={res3.ok}")
    valid = float((res3.verdicts.get("reason_valid") or {}).get("noul", 0.0))
    action = (res3.verdicts.get("recommended_action") or {}).get("choice", "?")
    print(f"    reason_valid = {valid:.3f} · recommended_action = {action}")
    if valid < 0.5:
        failures.append(f"reason gate: validity {valid:.2f} < 0.5 for an obviously valid reason")

    print("\n" + "=" * 62)
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("PASSED — live Jev answered all three probes correctly:")
    print("  ✓ hostile message flagged")
    print("  ✓ benign message not flagged")
    print("  ✓ valid report reason accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
