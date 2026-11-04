import numpy as np
import pandas as pd
import pytest

from oilinfl.anchor import anchored_const, with_anchor
from oilinfl.model import TEN_PCT, block_bootstrap, fit_ardl, months_to_share, simulate


def synthetic(n=900, a=(0.4, 0.2), b=(0.05, 0.03, 0.02), c=0.1, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 8, n)
    y = np.zeros(n)
    for t in range(max(len(a), len(b)), n):
        y[t] = c + sum(a[j] * y[t - 1 - j] for j in range(len(a))) + sum(b[k] * x[t - k] for k in range(len(b))) \
            + rng.normal(0, 0.1)
    idx = pd.date_range("1940-01-01", periods=n, freq="MS")
    return pd.Series(y, idx), pd.Series(x, idx)


def test_fit_recovers_coefficients_and_long_run():
    a, b = (0.4, 0.2), (0.05, 0.03, 0.02)
    y, x = synthetic(a=a, b=b)
    m = fit_ardl(y, x, p=2, q=2, start="1941-01", end="2014-12")
    est = dict(zip(m.names, m.params))
    for j, aj in enumerate(a, 1):
        assert est[f"y{j}"] == pytest.approx(aj, abs=0.05)
    for k, bk in enumerate(b):
        assert est[f"x{k}"] == pytest.approx(bk, abs=0.01)
    true_lr = TEN_PCT * sum(b) / (1 - sum(a))
    lr, se = m.long_run()
    assert abs(lr - true_lr) < 3 * se + 1e-6


def test_irf_converges_to_long_run():
    y, x = synthetic()
    m = fit_ardl(y, x, p=2, q=2, start="1941-01", end="2014-12")
    cum = m.irf(horizon=200)
    assert cum[-1] == pytest.approx(m.long_run()[0], rel=1e-6)
    assert 0 <= months_to_share(cum, 0.5) <= months_to_share(cum, 0.9)


def test_simulation_with_actual_residuals_reproduces_data():
    """Feeding the in-sample residuals back as shocks must give the actual series exactly."""
    y, x = synthetic(n=300)
    m = fit_ardl(y, x, p=2, q=2, start="1941-01", end="1964-12")
    dates = m.resid.index[-24:]
    t0 = dates[0]
    y_hist = y.loc[:t0 - pd.offsets.MonthBegin(1)].iloc[-2:].values
    x_path = x.loc[:dates[-1]].iloc[-(2 + len(dates)):].values
    sim = simulate(m.params, 2, 2, y_hist, x_path, shocks=m.resid.loc[dates].values[None, :])[0]
    assert np.allclose(sim, y.loc[dates].values)


def test_simulate_vectorised_matches_loop():
    params = np.array([0.1, 0.5, 0.1, 0.03, 0.02])
    x_path = np.linspace(-5, 5, 1 + 10)
    single = simulate(params, 2, 1, np.array([0.2, 0.3]), x_path)
    many = simulate(np.vstack([params] * 3), 2, 1, np.array([0.2, 0.3]), x_path)
    assert np.allclose(many, single)


def test_anchor_sets_steady_state():
    params = np.array([0.5, 0.6, 0.1, 0.0])           # const, y1, y2, x0
    mu = 2.0
    anc = with_anchor(params, 2, mu)
    sim = simulate(anc, 2, 0, np.array([1.0, 1.0]), np.zeros(600))[0]
    assert sim[-1] * 12 == pytest.approx(mu, rel=1e-6)
    assert anchored_const(np.vstack([params, params]), 2, mu).shape == (2,)
    assert with_anchor(params, 2, None) is params


def test_block_bootstrap_shape_and_mean():
    rng = np.random.default_rng(0)
    out = block_bootstrap(np.arange(100, dtype=float), reps=50, horizon=12, block=6, rng=rng)
    assert out.shape == (50, 12)
    assert abs(out.mean()) < 10   # demeaned
