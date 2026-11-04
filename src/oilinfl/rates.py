"""From inflation to expectations, real yields and growth equities.

Four estimated links, each deliberately simple so its weakness is visible:

1. Breakevens   dBE_t   = c + phi dBE_{t-1} + sum_k g_k dln(Brent)_{t-k}        (market expectations)
2. Reaction     GS2_t   = a + rho GS2_{t-1} + b coreYoY_t + c UNRATE_t          (partial-adjustment Taylor rule)
3. Pass-through dFII10  = a + beta dGS2 + gamma dBE10                           (front end -> 10y real)
4. Equity       dln XLK = a + delta dFII10                                       (real yield -> tech)

Scenario projection chains them: oil path -> breakevens (1); oil path -> core
PCE YoY (inflation block) -> 2y yield (2); both -> 10y real yield (3) -> XLK (4).
The 2y response is the scenario-driven deviation d_h = rho d_{h-1} + b (core_h - core_0),
i.e. how much the inflation path alone moves the 2y if markets react to realised core
inflation as they have since 2016. A 12-month-change version of the rule (which finds no
response over 1990-2025) is reported as the lower bound.
Unemployment is held at its last value. Intercepts are not projected forward
(no drift): the projections are changes caused by the scenario.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .data import mask_windows, to_monthly
from .model import ARDL, fit_ardl, simulate


@dataclass
class LinearFit:
    name: str
    params: pd.Series
    bse: pd.Series
    pvalues: pd.Series
    r2: float
    nobs: int
    sample: tuple[str, str]


def _ols(name, y, X, start, end, exclude, hac):
    z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
    z = z[~mask_windows(z.index, exclude)]
    r = sm.OLS(z["_y"], sm.add_constant(z.drop(columns="_y"))).fit(cov_type="HAC", cov_kwds={"maxlags": hac})
    return LinearFit(name, r.params, r.bse, r.pvalues, float(r.rsquared), int(r.nobs),
                     (z.index[0].strftime("%Y-%m"), z.index[-1].strftime("%Y-%m")))


def widen(windows, months: int):
    """Extend exclusion windows forward so no k-month change overlaps them."""
    out = []
    for a, b in windows:
        out.append([a, (pd.Timestamp(b) + pd.DateOffset(months=months)).strftime("%Y-%m")])
    return out


@dataclass
class RatesModels:
    breakeven: dict[str, ARDL]
    reaction: LinearFit
    reaction_headline: LinearFit
    reaction_changes: LinearFit
    passthrough: LinearFit
    equity: LinearFit
    equity_full: LinearFit


def fit_rates(levels: pd.DataFrame, core_yoy: pd.Series, brent_dlog: pd.Series,
              xlk_daily: pd.Series | None, cfg: dict, headline_yoy: pd.Series | None = None) -> RatesModels:
    rc = cfg["rates"]
    be = {}
    for sid in rc["breakeven"]["ids"]:
        dbe = levels[sid].diff()
        a, b = rc["breakeven"]["sample"]
        be[sid] = fit_ardl(dbe, brent_dlog, p=1, q=rc["breakeven"]["oil_lags"], start=a, end=b,
                           exclude=rc["breakeven"]["exclude"], hac_lags=6)

    rr = rc["reaction"]
    g = levels[rr["yield"]]
    X = pd.concat([g.shift(1).rename("lag"), core_yoy.rename("core_yoy"), levels["UNRATE"].rename("unrate")], axis=1, sort=True)
    reaction = _ols("reaction", g, X, rr["sample"][0], rr["sample"][1], rr["exclude"], hac=12)
    Xh = pd.concat([g.shift(1).rename("lag"), headline_yoy.rename("core_yoy"), levels["UNRATE"].rename("unrate")], axis=1, sort=True)
    reaction_headline = _ols("reaction_headline", g, Xh, rr["sample"][0], rr["sample"][1], rr["exclude"], hac=12)
    w = rr["window"]
    X = pd.concat([core_yoy.diff(w).rename("d_core_yoy"), levels["UNRATE"].diff(w).rename("d_unrate")], axis=1, sort=True)
    reaction_changes = _ols("reaction_changes", g.diff(w), X, rr["changes_sample"][0], rr["changes_sample"][1],
                            rr["exclude_long"], hac=w)

    pt = rc["passthrough"]
    X = pd.concat([levels[pt["front"]].diff().rename("d_gs2"), levels[pt["breakeven"]].diff().rename("d_be10")], axis=1, sort=True)
    passthrough = _ols("passthrough", levels[pt["real"]].diff(), X, pt["sample"][0], pt["sample"][1],
                       pt["exclude"], hac=6)

    eq = rc["equity"]
    if xlk_daily is not None:
        xm = to_monthly(xlk_daily)                     # monthly average, matches FRED monthly averages
        r = 100.0 * np.log(xm).diff().rename("xlk")
        dry = (100.0 * levels[eq["real_yield"]].diff()).rename("d_real_bp")
        equity = _ols("equity", r, dry.to_frame(), eq["sample"][0], eq["sample"][1], [["2020-03", "2020-06"]], hac=6)
        equity_full = _ols("equity_full", r, dry.to_frame(), "2003-02", eq["sample"][1], [["2020-03", "2020-06"]], hac=6)
    else:
        equity = equity_full = None
    return RatesModels(be, reaction, reaction_headline, reaction_changes, passthrough, equity, equity_full)


def _rule_path(fit: LinearFit, infl_path: np.ndarray, infl_origin: float) -> np.ndarray:
    rho, b = fit.params["lag"], fit.params["core_yoy"]
    dev = infl_path - infl_origin
    d = np.zeros(len(dev))
    for h in range(len(dev)):
        d[h] = (rho * d[h - 1] if h else 0.0) + b * dev[h]
    return d


def project(rm: RatesModels, levels: pd.DataFrame, origin: pd.Timestamp, brent_dlog_hist: pd.Series,
            brent_dlog_future: pd.Series, core_yoy_path: np.ndarray, core_yoy_origin: float,
            cfg: dict, headline_yoy_path: np.ndarray | None = None, headline_yoy_origin: float | None = None) -> pd.DataFrame:
    """Deterministic projection of breakevens, 2y, 10y real and XLK under one scenario.

    Two Fed rules: the estimated one (responds to core PCE) and a hawkish
    alternative estimated on headline PCE, for a Fed that does not look
    through energy. Columns with suffix ``_hawk`` use the headline rule.
    """
    H = len(brent_dlog_future)
    out = pd.DataFrame(index=brent_dlog_future.index)
    for sid, m in rm.breakeven.items():
        params = m.params.copy()
        params[0] = 0.0                                   # no drift
        xall = pd.concat([brent_dlog_hist.loc[:origin], brent_dlog_future])
        x_path = xall.iloc[-(m.q + H):].values        # includes lags of oil moves already realised
        y0 = levels[sid].diff().loc[:origin].iloc[-1:].values
        sim = simulate(params, 1, m.q, y0, x_path)[0]
        out[sid] = levels[sid].loc[origin] + np.cumsum(sim)
    beta = rm.passthrough.params["d_gs2"]
    gamma = rm.passthrough.params["d_be10"]
    d_be10 = out["T10YIEM"].values - levels["T10YIEM"].loc[origin]
    out["core_pce_yoy"] = core_yoy_path
    rules = {"": (rm.reaction, core_yoy_path, core_yoy_origin)}
    if headline_yoy_path is not None:
        out["headline_pce_yoy"] = headline_yoy_path
        rules["_hawk"] = (rm.reaction_headline, headline_yoy_path, headline_yoy_origin)
    for suf, (fit, path, o) in rules.items():
        d2 = _rule_path(fit, path, o)
        out[f"GS2{suf}"] = levels["GS2"].loc[origin] + d2
        out[f"FII10{suf}"] = levels["FII10"].loc[origin] + beta * d2 + gamma * d_be10
        if rm.equity is not None:
            delta = rm.equity.params["d_real_bp"]          # % per bp
            dbp = 100.0 * (out[f"FII10{suf}"].values - levels["FII10"].loc[origin])
            out[f"XLK_implied_pct{suf}"] = 100.0 * np.expm1(delta * dbp / 100.0)
    return out
