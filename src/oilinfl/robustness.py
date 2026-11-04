"""Robustness and validation tests for the inflation block.

Every function returns a tidy DataFrame so results can be saved and quoted.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_arch, linear_reset
from statsmodels.stats.stattools import durbin_watson, jarque_bera

from .anchor import with_anchor
from .data import mask_windows
from .forecast import carry_path
from .model import TEN_PCT, design, fit_ardl, simulate


# ----------------------------------------------------------------- helpers --
def _xy(y, x, p, q, start, end, exclude):
    X = design(y, x, p, q)
    z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
    z = z[~mask_windows(z.index, exclude)]
    Xm = np.column_stack([np.ones(len(z)), z.drop(columns="_y").values])
    return z["_y"].values, Xm, z.index


def _lstsq(yv, Xm):
    return np.linalg.lstsq(Xm, yv, rcond=None)[0]


def _lr(beta, p, q, scale=TEN_PCT):
    a = beta[1:1 + p].sum()
    b = beta[1 + p:2 + p + q].sum()
    return scale * b / (1.0 - a)


# ------------------------------------------------------------ 1. lag grid --
def lag_grid(y, x, grid, start, end, exclude) -> pd.DataFrame:
    rows = []
    for p in grid["p"]:
        for q in grid["q"]:
            m = fit_ardl(y, x, p, q, start, end, exclude)
            lr, se = m.long_run()
            rows.append(dict(p=p, q=q, nobs=m.nobs, aic=m.aic, bic=m.bic, r2_adj=m.r2_adj, lr10=lr, lr10_se=se))
    df = pd.DataFrame(rows)
    df["bic_rank"] = df["bic"].rank().astype(int)
    df["aic_rank"] = df["aic"].rank().astype(int)
    return df


# ---------------------------------------------- 2. out-of-sample forecasts --
def dm_test(e1: np.ndarray, e2: np.ndarray, h: int) -> tuple[float, float]:
    """Diebold-Mariano with Harvey-Leybourne-Newbold correction; squared loss.

    Negative statistic = model 1 more accurate. Returns (stat, two-sided p).
    """
    d = e1 ** 2 - e2 ** 2
    n = len(d)
    dbar = d.mean()
    gamma = [np.sum((d[k:] - dbar) * (d[:n - k] - dbar)) / n for k in range(h)]
    var = gamma[0] + 2 * sum(gamma[1:])
    if var <= 0:
        return np.nan, np.nan
    dm = dbar / np.sqrt(var / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = dm * hln
    return float(stat), float(2 * stats.t.sf(abs(stat), df=n - 1))


def oos_forecasts(y, x, p, q, start, exclude, first, last, H=12, anchor_fn=None) -> pd.DataFrame:
    """Expanding-window pseudo out-of-sample forecasts of the next-12-month inflation.

    Models: ARDL with actual future oil (conditional), ARDL with flat oil
    (unconditional), the same ARDL with its estimated (unanchored) intercept,
    AR(p) without oil, and a random walk on YoY. ``anchor_fn(T)`` returns the
    expectations anchor known at origin T (or None). Forecast windows that
    overlap an excluded period are dropped.
    """
    rows = []
    origins = pd.date_range(first, last, freq="MS")
    for T in origins:
        fut = pd.date_range(T + pd.offsets.MonthBegin(1), periods=H, freq="MS")
        if fut[-1] > y.dropna().index[-1] or mask_windows(fut, exclude).any():
            continue
        yv, Xm, _ = _xy(y, x, p, q, start, T.strftime("%Y-%m"), exclude)
        b = _lstsq(yv, Xm)
        # AR only
        Xa = design(y, x, p, 0).drop(columns="x0")
        za = pd.concat([y.rename("_y"), Xa], axis=1, sort=True).loc[start:T].dropna()
        za = za[~mask_windows(za.index, exclude)]
        ba = _lstsq(za["_y"].values, np.column_stack([np.ones(len(za)), za.drop(columns="_y").values]))
        y_hist = y.loc[:T].iloc[-p:].values
        xp = x.loc[:fut[-1]].iloc[-(q + H):].values
        x_flat = xp.copy()
        x_flat[q:] = 0.0
        mu = anchor_fn(T) if anchor_fn is not None else None
        ba_ = with_anchor(b, p, mu)
        f_oil = simulate(ba_, p, q, y_hist, xp)[0]
        f_flat = simulate(ba_, p, q, y_hist, x_flat)[0]
        f_sample = simulate(b, p, q, y_hist, xp)[0]
        # carry recent one-step errors forward (tests the decay / persists settings)
        w0 = T - pd.DateOffset(months=5)
        Xr = design(y, x, p, q).loc[w0:T]
        if mask_windows(Xr.index, exclude).any() or Xr.isna().any().any():
            err = 0.0
        else:
            err = float((y.loc[w0:T].values - np.column_stack([np.ones(len(Xr)), Xr.values]) @ ba_).mean())
        f_decay = simulate(ba_, p, q, y_hist, xp, carry=carry_path(err, H, "decay", 6))[0]
        f_persist = simulate(ba_, p, q, y_hist, xp, carry=carry_path(err, H, "persists", 6))[0]
        f_ar = simulate(np.r_[ba, np.zeros(q + 1)], p, q, y_hist, x_flat)[0]
        actual = y.loc[fut].values
        yoy_T = y.loc[:T].iloc[-12:].sum()
        rows.append(dict(origin=T, actual_12m=actual.sum(), ardl_oil=f_oil.sum(), ardl_flat=f_flat.sum(),
                         ardl_sample=f_sample.sum(), ardl_decay=f_decay.sum(), ardl_persists=f_persist.sum(),
                         ar=f_ar.sum(), rw=yoy_T, actual_1m=actual[0],
                         ardl_oil_1m=f_oil[0], ardl_flat_1m=f_flat[0], ardl_sample_1m=f_sample[0],
                         ardl_decay_1m=f_decay[0], ardl_persists_1m=f_persist[0],
                         ar_1m=f_ar[0], rw_1m=y.loc[T]))
    return pd.DataFrame(rows).set_index("origin")


def oos_summary(fc: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for hz, suf, h in (("12m", "", 12), ("1m", "_1m", 1)):
        act = fc[f"actual_{hz}"].values
        errs = {m: fc[f"{m}{suf}"].values - act
                for m in ("ardl_oil", "ardl_flat", "ardl_sample", "ardl_decay", "ardl_persists", "ar", "rw")}
        rm = {m: float(np.sqrt(np.mean(e ** 2))) for m, e in errs.items()}
        out[(hz, "rmse_ardl_oil")] = rm["ardl_oil"]
        out[(hz, "rmse_ardl_flat")] = rm["ardl_flat"]
        out[(hz, "rmse_ardl_sample_intercept")] = rm["ardl_sample"]
        out[(hz, "rmse_ardl_carry_decay")] = rm["ardl_decay"]
        out[(hz, "rmse_ardl_carry_persists")] = rm["ardl_persists"]
        out[(hz, "dm_p_oil_vs_sample_intercept")] = dm_test(errs["ardl_oil"], errs["ardl_sample"], h)[1]
        out[(hz, "dm_p_decay_vs_oil")] = dm_test(errs["ardl_decay"], errs["ardl_oil"], h)[1]
        out[(hz, "rmse_ar")] = rm["ar"]
        out[(hz, "rmse_rw")] = rm["rw"]
        out[(hz, "ratio_oil_vs_ar")] = rm["ardl_oil"] / rm["ar"]
        out[(hz, "ratio_oil_vs_rw")] = rm["ardl_oil"] / rm["rw"]
        out[(hz, "ratio_flat_vs_rw")] = rm["ardl_flat"] / rm["rw"]
        out[(hz, "dm_p_oil_vs_ar")] = dm_test(errs["ardl_oil"], errs["ar"], h)[1]
        out[(hz, "dm_p_oil_vs_rw")] = dm_test(errs["ardl_oil"], errs["rw"], h)[1]
        out[(hz, "dm_p_flat_vs_rw")] = dm_test(errs["ardl_flat"], errs["rw"], h)[1]
        out[(hz, "n")] = len(act)
    return pd.Series(out)


# --------------------------------------------- 3. subsamples and stability --
def subsamples(y, x, p, q, windows: dict, exclude) -> pd.DataFrame:
    rows = []
    for name, (a, b) in windows.items():
        m = fit_ardl(y, x, p, q, a, b, exclude)
        lr, se = m.long_run()
        rows.append(dict(window=name, nobs=m.nobs, r2=m.r2, lr10=lr, lr10_se=se, oil_wald_p=m.wald_driver()))
    return pd.DataFrame(rows)


def chow_test(y, x, p, q, start, end, exclude, brk: str) -> float:
    """HAC Wald test that all slope coefficients shift at ``brk`` (p-value)."""
    X = design(y, x, p, q)
    z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
    z = z[~mask_windows(z.index, exclude)]
    D = (z.index >= pd.Timestamp(brk)).astype(float)
    Xs = z.drop(columns="_y")
    inter = Xs.mul(D, axis=0).add_suffix("_post")
    Xf = sm.add_constant(pd.concat([Xs, inter, pd.Series(D, index=z.index, name="post")], axis=1, sort=True))
    r = sm.OLS(z["_y"], Xf).fit(cov_type="HAC", cov_kwds={"maxlags": 12})
    names = list(inter.columns) + ["post"]
    R = np.zeros((len(names), len(Xf.columns)))
    for i, n in enumerate(names):
        R[i, list(Xf.columns).index(n)] = 1.0
    return float(r.f_test(R).pvalue)


def rolling_long_run(y, x, p, q, exclude, years: int, first_end: str, last_end: str) -> pd.DataFrame:
    rows = []
    for end in pd.date_range(first_end, last_end, freq="12MS"):
        start = end - pd.DateOffset(years=years) + pd.offsets.MonthBegin(1)
        m = fit_ardl(y, x, p, q, start.strftime("%Y-%m"), end.strftime("%Y-%m"), exclude)
        lr, se = m.long_run()
        rows.append(dict(window_end=end, lr10=lr, lo=lr - 1.96 * se, hi=lr + 1.96 * se, nobs=m.nobs))
    return pd.DataFrame(rows).set_index("window_end")


# ------------------------------------------------------------ 4. asymmetry --
def asymmetry(y, x, p, q, start, end, exclude) -> dict:
    xp, xn = x.clip(lower=0), x.clip(upper=0)
    m = fit_ardl(y, {"up": xp, "dn": xn}, p, q, start, end, exclude)
    a = m.params[m._idx("y")].sum()
    iu, idn = m._idx("up"), m._idx("dn")
    lr_up = TEN_PCT * m.params[iu].sum() / (1 - a)
    lr_dn = TEN_PCT * m.params[idn].sum() / (1 - a)
    R = np.zeros((1, len(m.params)))
    R[0, iu] = 1.0
    R[0, idn] = -1.0
    pval = float(m.result.f_test(R).pvalue)
    return dict(lr_rise10=lr_up, lr_fall10=lr_dn, equal_p=pval)


# -------------------------------------------------------- 5. diagnostics --
def residual_diagnostics(y, x, p, q, start, end, exclude) -> dict:
    X = design(y, x, p, q)
    z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
    z = z[~mask_windows(z.index, exclude)]
    r = sm.OLS(z["_y"], sm.add_constant(z.drop(columns="_y"))).fit()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        bg = acorr_breusch_godfrey(r, nlags=12)[1]
        arch = het_arch(r.resid, nlags=12)[1]
    jb = jarque_bera(r.resid)[1]
    try:
        reset = float(linear_reset(r, power=[2, 3], use_f=True).pvalue)
    except Exception:  # pragma: no cover
        reset = np.nan
    return dict(nobs=int(r.nobs), r2=float(r.rsquared), r2_adj=float(r.rsquared_adj), dw=float(durbin_watson(r.resid)),
                bg12_p=float(bg), arch12_p=float(arch), jb_p=float(jb), reset_p=reset)


# ------------------------------------------------------ 6. placebo test --
def placebo(y, x, p, q, start, end, exclude, reps: int, rng) -> dict:
    """Circularly shift the oil series by a random offset (>= 24 months) and re-estimate.

    Keeps oil's own time-series properties but breaks its timing link to inflation.
    """
    yv, Xm, idx = _xy(y, x, p, q, start, end, exclude)
    actual = _lr(_lstsq(yv, Xm), p, q)
    xs = x.dropna()
    n = len(xs)
    vals = []
    for _ in range(reps):
        k = int(rng.integers(24, n - 24))
        xr = pd.Series(np.roll(xs.values, k), index=xs.index)
        yv2, Xm2, _ = _xy(y, xr, p, q, start, end, exclude)
        vals.append(_lr(_lstsq(yv2, Xm2), p, q))
    vals = np.array(vals)
    return dict(lr10=actual, placebo_mean=float(vals.mean()), placebo_p95=float(np.percentile(np.abs(vals), 95)),
                p_value=float((np.abs(vals) >= abs(actual)).mean()))


# --------------------------------------------------- 7. 2026 backtest ----
def backtest_2026(model, y, x, start="2026-01", end="2026-09", mu=None) -> dict:
    """Dynamic simulation over 2026 from Dec-2025 actuals, with actual and flat oil."""
    dates = pd.date_range(start, end, freq="MS")
    t0 = dates[0] - pd.offsets.MonthBegin(1)
    y_hist = y.loc[:t0].iloc[-model.p:].values
    xp = x.loc[:dates[-1]].iloc[-(model.q + len(dates)):].values
    xf = xp.copy()
    xf[model.q:] = 0.0
    params = with_anchor(model.params, model.p, mu)
    sim = simulate(params, model.p, model.q, y_hist, xp)[0]
    flat = simulate(params, model.p, model.q, y_hist, xf)[0]
    act = y.loc[dates].values
    prev = y.loc[:t0].iloc[-(12 - len(dates)):].sum() if len(dates) < 12 else 0.0
    to_yoy = lambda s: 100 * np.expm1((prev + s.sum()) / 100)
    return dict(actual_cum=float(act.sum()), model_cum=float(sim.sum()), flat_oil_cum=float(flat.sum()),
                oil_contrib=float(sim.sum() - flat.sum()), unexplained=float(act.sum() - sim.sum()),
                actual_yoy=float(to_yoy(act)), model_yoy=float(to_yoy(sim)), flat_oil_yoy=float(to_yoy(flat)))
