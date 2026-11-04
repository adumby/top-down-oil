import argparse

from .pipeline import run

ap = argparse.ArgumentParser(description="Run the oil-inflation model end to end.")
ap.add_argument("--config", default="config.yaml")
ap.add_argument("--skip-robustness", action="store_true", help="skip the (slower) robustness suite")
ap.add_argument("--fast", action="store_true", help="fewer bootstrap/placebo draws, for quick checks")
a = ap.parse_args()
run(a.config, skip_robustness=a.skip_robustness, fast=a.fast)
