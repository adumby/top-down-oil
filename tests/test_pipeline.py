"""End-to-end checks on the real data shipped in data/raw."""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oilinfl import robustness as rb
from oilinfl.data import brent_logchange, load, yoy_from_logpct
from oilinfl.pipeline import load_config, run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT / "config.yaml")


@pytest.fixture(scope="module")
def ds(cfg):
    return load(cfg, ROOT)


def test_data_ends_at_origin(cfg, ds):
    origin = pd.Timestamp(cfg["forecast"]["origin"])
    for k in cfg["targets"]:
        assert ds.inflation[k].last_valid_index() == origin
    assert ds.levels[cfg["driver"]["id"]].last_valid_index() >= origin


def test_known_values(ds):
    """Spot-check published figures so a bad data refresh is caught."""
    cpi = yoy_from_logpct(ds.inflation["headline_cpi"])
    pce = yoy_from_logpct(ds.inflation["core_pce"])
    assert cpi.loc["2026-09-01"] == pytest.approx(100 * (336.298 / 324.245 - 1), abs=1e-6)
    assert pce.loc["2026-09-01"] == pytest.approx(100 * (130.902 / 126.940 - 1), abs=1e-6)
    real_plus_be = ds.levels["FII10"] + ds.levels["T10YIEM"]
    assert np.isfinite(real_plus_be.loc["2026-09-01"])


def test_oil_matters_for_headline_not_core(cfg, ds):
    from oilinfl.model import fit_ardl
    x = brent_logchange(ds, cfg["driver"]["id"])
    e = cfg["estimation"]
    head = fit_ardl(ds.inflation["headline_cpi"], x, e["p"], e["q"], e["start"], e["end"], e["exclude"])
    core = fit_ardl(ds.inflation["core_pce"], x, e["p"], e["q"], e["start"], e["end"], e["exclude"])
    assert head.long_run()[0] > 3 * core.long_run()[0] > 0
    assert head.wald_driver() < 0.01


def test_placebo_and_oos_run(cfg, ds):
    x = brent_logchange(ds, cfg["driver"]["id"])
    y = ds.inflation["energy_pce"]
    e = cfg["estimation"]
    pl = rb.placebo(y, x, e["p"], e["q"], e["start"], e["end"], e["exclude"], 30, np.random.default_rng(0))
    assert pl["p_value"] < 0.05
    fc = rb.oos_forecasts(y, x, e["p"], e["q"], e["start"], e["exclude"], "2015-01", "2016-12")
    s = rb.oos_summary(fc)
    assert s[("12m", "rmse_ardl_oil")] < s[("12m", "rmse_rw")]


def test_pipeline_smoke(cfg, tmp_path):
    c = copy.deepcopy(cfg)
    c["output_dir"] = str(tmp_path / "out")
    c["forecast"]["bootstrap_reps"] = 50
    c["scenarios"] = {k: cfg["scenarios"][k] for k in ["flat_114", "flat_105", "higher_longer", "up_down_up",
                                                         "normalize_75"]}
    res = run(c, root=ROOT, skip_robustness=True, fast=True)
    out = Path(c["output_dir"]) if Path(c["output_dir"]).is_absolute() else ROOT / c["output_dir"]
    summ = pd.read_csv(out / "tables" / "scenario_summary.csv")
    assert summ[["yoy_dec26", "yoy_sep27"]].notna().all().all()
    # higher oil -> higher headline inflation; ordering must hold
    h = summ[summ.target == "headline_pce"].set_index("scenario")["yoy_sep27"]
    assert h["normalize_75"] < h["flat_105"] < h["flat_114"] < h["higher_longer"]
    # bands bracket the central path
    assert (summ.yoy_sep27_lo <= summ.yoy_sep27 + 1e-9).all() and (summ.yoy_sep27 <= summ.yoy_sep27_hi + 1e-9).all()
    assert (out / "figures" / "fan_yoy.png").exists()
    assert json.loads((out / "results.json").read_text())["brent_origin"] == pytest.approx(114.16)
    assert res["anchors"]["headline_cpi"] == pytest.approx(2.35)
