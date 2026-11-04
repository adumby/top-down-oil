"""Supporting analysis: refined-fuel drivers, transportation attribution, pass-through timing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .data import mask_windows
from .model import fit_ardl, months_to_share, simulate

FUELS = {"Brent": "MCOILBRENTEU", "Retail gasoline": "GASREGW", "Retail diesel": "GASDESW",
         "Jet fuel (Gulf)": "WJFUELUSGULF", "PPI refined petroleum": "WPU0571"}


def dlog(levels: pd.Series) -> pd.Series:
    return 100.0 * np.log(levels).diff()


def fuel_variants(inflation: pd.DataFrame, levels: pd.DataFrame, targets: list[str], p: int, q: int,
                  exclude, start="1995-01", end="2025-12", y2026=("2026-01", "2026-09")) -> pd.DataFrame:
    """Same ARDL with each fuel as the driver; share of the 2026 move each fuel explains."""
    rows = []
    d0, d1 = pd.Timestamp(y2026[0]), pd.Timestamp(y2026[1])
    dates = pd.date_range(d0, d1, freq="MS")
    for t in targets:
        y = inflation[t]
        for name, sid in FUELS.items():
            if sid not in levels:
                continue
            x = dlog(levels[sid])
            m = fit_ardl(y, x, p, q, start, end, exclude)
            lr, se = m.long_run()
            y_hist = y.loc[:d0 - pd.offsets.MonthBegin(1)].iloc[-p:].values
            xp = x.loc[:d1].iloc[-(q + len(dates)):].values
            if np.isnan(xp).any():
                share = np.nan
                fuel_pp = np.nan
            else:
                xz = xp.copy()
                xz[q:] = 0.0
                with_f = simulate(m.params, p, q, y_hist, xp)[0].sum()
                no_f = simulate(m.params, p, q, y_hist, xz)[0].sum()
                fuel_pp = with_f - no_f
                share = 100 * fuel_pp / y.loc[dates].sum()
            rows.append(dict(target=t, fuel=name, r2=m.r2, lr10=lr, lr10_se=se, oil_wald_p=m.wald_driver(),
                             actual_2026_pp=y.loc[dates].sum(), fuel_attributable_pp=fuel_pp, share_pct=share))
    return pd.DataFrame(rows)


def transport_attribution(inflation: pd.DataFrame, levels: pd.DataFrame, exclude,
                          start="1995-01", end="2025-12", y2026=("2026-01", "2026-09")) -> pd.DataFrame:
    """Decompose the 2026 rise in PCE transportation services.

    Regressors: 3 own lags; 0-12 lags of Brent, retail diesel and jet fuel;
    1-6 lags of core PCE inflation (general inflation). Contributions are
    coefficient x actual regressor, summed over Jan-Sep 2026.
    """
    y = inflation["transport_pce"]
    core = inflation["core_pce"]
    fuels = {"brent": dlog(levels["MCOILBRENTEU"]), "diesel": dlog(levels["GASDESW"]), "jet": dlog(levels["WJFUELUSGULF"])}
    specs = {
        "Fuels only": (True, False),
        "Core inflation only": (False, True),
        "Fuels + core inflation": (True, True),
    }
    rows = []
    for name, (use_f, use_c) in specs.items():
        cols = [y.shift(j).rename(f"own{j}") for j in range(1, 4)]
        if use_f:
            for fn, fx in fuels.items():
                cols += [fx.shift(k).rename(f"fuel_{fn}{k}") for k in range(13)]
        if use_c:
            cols += [core.shift(k).rename(f"core{k}") for k in range(1, 7)]
        X = pd.concat(cols, axis=1, sort=True)
        z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
        z = z[~mask_windows(z.index, exclude)]
        r = sm.OLS(z["_y"], sm.add_constant(z.drop(columns="_y"))).fit()
        w = sm.add_constant(X, has_constant="add").loc[y2026[0]:y2026[1]]
        contrib = lambda pre: float(sum(r.params[c] * w[c] for c in r.params.index if c.startswith(pre)).sum()) \
            if any(c.startswith(pre) for c in r.params.index) else 0.0
        actual = float(y.loc[y2026[0]:y2026[1]].sum())
        fuel_c, core_c = contrib("fuel_"), contrib("core")
        own_c = contrib("own") + r.params["const"] * len(w)
        rows.append(dict(model=name, r2=r.rsquared, r2_adj=r.rsquared_adj, actual_pp=actual, fuel_pp=fuel_c,
                         core_inflation_pp=core_c, own_and_const_pp=own_c,
                         unexplained_pp=actual - fuel_c - core_c - own_c))
    return pd.DataFrame(rows)


def irf_timing(models: dict, labels: dict, horizon: int = 36) -> pd.DataFrame:
    rows = []
    for k, m in models.items():
        cum = m.irf(horizon=horizon)
        lr, se = m.long_run()
        rows.append(dict(target=k, label=labels[k], effect_12m=cum[11], effect_36m=cum[-1], long_run=lr, long_run_se=se,
                         months_to_50=months_to_share(cum, 0.5), months_to_90=months_to_share(cum, 0.9)))
    return pd.DataFrame(rows)
