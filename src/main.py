"""Entrypoint: python -m tsabot  (or `python src/main.py` for the packaged run)."""
from __future__ import annotations

import pathlib
import sys

# allow running as `python src/main.py` from the project root
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tsabot.bot import run  # noqa: E402

if __name__ == "__main__":
    # resolve the project root (one level above src/) for config + rules
    project_root = ROOT.parent
    import os
    os.chdir(project_root)
    run()
