"""Dashboard entrypoint: python src/dashboard_main.py"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tsabot.dashboard.app import run  # noqa: E402

if __name__ == "__main__":
    import os
    os.chdir(ROOT.parent)
    run()
