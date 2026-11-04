import numpy as np
import pandas as pd
import pytest

from oilinfl.data import (annualized_from_logpct, full_monthly, gaps_filled, logpct_from_index, logpct_from_pct,
                          mask_windows, pct_from_logpct, read_fred_csv, to_monthly, yoy_from_logpct)


def test_read_fred_csv_handles_dot_and_blank(tmp_path):
    f = tmp_path / "X.csv"
    f.write_text("observation_date,X\n2020-01-01,1.0\n2020-02-01,.\n2020-03-01,\n2020-04-01,4\n")
    s = read_fred_csv(f)
    assert s.name == "X"
    assert s.isna().sum() == 2
    assert s.iloc[-1] == 4.0


def test_full_monthly_fills_short_gap_log_linearly():
    idx = pd.to_datetime(["2020-01-01", "2020-02-01", "2020-04-01"])
    s = pd.Series([100.0, 110.0, 133.1], index=idx)
    f = full_monthly(s)
    assert list(f.index) == list(pd.date_range("2020-01-01", "2020-04-01", freq="MS"))
    assert f.loc["2020-03-01"] == pytest.approx(np.sqrt(110.0 * 133.1))
    assert gaps_filled(s, f) == ["2020-03"]


def test_full_monthly_leaves_long_gap_empty():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2020-01-01", "2020-07-01"]))
    f = full_monthly(s, max_gap=3)
    assert f.isna().sum() == 5


def test_shift_alignment_after_missing_month():
    """Regression test: a 12-row shift must equal a 12-month shift once the index is complete."""
    idx = pd.date_range("2019-01-01", "2021-12-01", freq="MS").delete(20)   # drop one month
    s = pd.Series(np.arange(len(idx), dtype=float) + 100.0, index=idx)
    f = full_monthly(s)
    lagged = f.shift(12)
    for t in f.index[12:]:
        assert lagged.loc[t] == f.loc[t - pd.DateOffset(months=12)]


def test_yoy_from_constant_monthly_rate():
    m = pd.Series(100 * np.log(1.0025), index=pd.date_range("2020-01-01", periods=24, freq="MS"))
    yoy = yoy_from_logpct(m)
    assert yoy.iloc[-1] == pytest.approx(100 * (1.0025 ** 12 - 1))
    assert annualized_from_logpct(m, 3).iloc[-1] == pytest.approx(100 * (1.0025 ** 12 - 1))


def test_yoy_matches_index_ratio():
    rng = np.random.default_rng(0)
    p = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.002, 0.003, 60))),
                  index=pd.date_range("2015-01-01", periods=60, freq="MS"))
    yoy = yoy_from_logpct(logpct_from_index(p))
    direct = 100 * (p / p.shift(12) - 1)
    assert np.allclose(yoy.dropna(), direct.dropna())


def test_pct_log_roundtrip():
    x = pd.Series([0.3, -1.1, 5.4])
    assert np.allclose(pct_from_logpct(logpct_from_pct(x)), x)


def test_to_monthly_and_masks():
    d = pd.Series(1.0, index=pd.date_range("2020-01-01", "2020-03-31", freq="D"))
    m = to_monthly(d)
    assert len(m) == 3 and (m == 1.0).all()
    msk = mask_windows(m.index, [["2020-02", "2020-02"]])
    assert msk.tolist() == [False, True, False]
