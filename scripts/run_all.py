"""Convenience wrapper: python scripts/run_all.py [--fast] [--skip-robustness]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oilinfl.__main__ import *  # noqa: E402,F401,F403  (runs the CLI)
