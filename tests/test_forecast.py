import numpy as np
import pandas as pd
import pytest

from oilinfl.forecast import Forecast, build_path, carry_path
from oilinfl.robustness import dm_test

O = pd.Timestamp("2026-09-01")


def test_build_path_mult_level_and_order():
    p = build_path(100.0, O, 12, [{"from": "2026-11", "mult": 1.25}, {"from": "2027-01", "mult": 1.0},
                                  {"from": "2027-04", "level": 90}])
    assert p.index[0] == pd.Timestamp("2026-10-01") and len(p) == 12
    assert p.loc["2026-10-01"] == 100 and p.loc["2026-11-01"] == 125 and p.loc["2027-02-01"] == 100
    assert p.loc["2027-09-01"] == 90


def test_build_path_glide():
    p = build_path(100.0, O, 12, [{"from": "2026-10", "to": "2027-01", "glide": True, "level": 75}])
    assert p.loc["2027-01-01"] == pytest.approx(75)
    assert p.loc["2027-09-01"] == pytest.approx(75)
    assert 75 < p.loc["2026-11-01"] < 100
    steps = np.diff(np.log(p.loc[:"2027-01-01"].values))
    assert np.allclose(steps, steps[0])                   # log-linear


def test_carry_modes():
    assert np.all(carry_path(0.1, 12, "fades", 6) == 0)
    assert np.all(carry_path(0.1, 12, "persists", 6) == 0.1)
    d = carry_path(0.1, 12, "decay", 6)
    assert d[5] == pytest.approx(0.05) and np.all(np.diff(d) < 0)


def test_forecast_yoy_uses_history():
    hist = pd.Series(100 * np.log(1.002), index=pd.date_range("2025-10-01", "2026-09-01", freq="MS"))
    sim = np.full((1, 12), 100 * np.log(1.004))
    f = Forecast("t", "s", "fades", pd.date_range("2026-10-01", periods=12, freq="MS"), sim, hist)
    yoy = f.yoy()[0]
    assert yoy[0] == pytest.approx(100 * (1.002 ** 11 * 1.004 - 1))
    assert yoy[-1] == pytest.approx(100 * (1.004 ** 12 - 1))
    assert f.annualized(3)[0][2] == pytest.approx(100 * (1.004 ** 12 - 1))


def test_dm_test_detects_better_model():
    rng = np.random.default_rng(3)
    e_good = rng.normal(0, 1, 300)
    e_bad = rng.normal(0, 2, 300)
    stat, p = dm_test(e_good, e_bad, 1)
    assert stat < 0 and p < 0.01
