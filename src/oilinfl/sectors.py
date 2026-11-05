"""How a rise in the 10-year real yield has moved each equity sector.

For every sector ETF: dln(monthly-average price) [%] = a + beta * dFII10 [bp] + e, estimated on the
same sample and with the same treatment as the XLK link in rates.py (HAC errors, Covid months out).
Two versions:

  raw       the sector's own return. It contains the market: when real yields rise for
            "good" reasons (growth) stocks tend to rise too.
  relative  the sector minus the equal-weighted average of all sectors. This strips the common
            market move and shows which sectors are rate-sensitive *relative to the market*.

Both are reduced-form comovement, not causal effects. Real yields and stocks respond to the same
news, and the link is unstable across regimes (see paper, section 9).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import to_monthly
from .rates import _ols

NAMES = {"XLK": "Technology", "XLY": "Consumer discretionary", "XLP": "Consumer staples", "XLE": "Energy",
         "XLF": "Financials", "XLV": "Health care", "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
         "XLRE": "Real estate", "XLC": "Communication services"}


def read_sectors(path, xlk: pd.Series | None = None) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
    if xlk is not None:
        df["XLK"] = xlk
    return df[[c for c in NAMES if c in df.columns]]


def monthly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Log change in the monthly-average price, in percent. Matches the FRED monthly-average yields."""
    m = prices.apply(to_monthly)
    return 100.0 * np.log(m).diff()


def fit_sectors(prices: pd.DataFrame, real_yield: pd.Series, start: str, end: str, exclude, hac: int = 6) -> pd.DataFrame:
    r = monthly_returns(prices)
    window = r.loc[start:end]
    market = window.mean(axis=1)                       # equal-weighted sector average = market proxy
    dry = (100.0 * real_yield.diff()).rename("d_real_bp")
    rows = []
    for k in r.columns:
        for kind, y in (("raw", r[k]), ("relative", r[k] - r.mean(axis=1))):
            f = _ols(k, y, dry.to_frame(), start, end, exclude, hac)
            rows.append(dict(sector=k, name=NAMES[k], version=kind, beta_per_bp=float(f.params["d_real_bp"]),
                             se_per_bp=float(f.bse["d_real_bp"]), p=float(f.pvalues["d_real_bp"]), r2=f.r2, nobs=f.nobs,
                             sample=f"{f.sample[0]}..{f.sample[1]}"))
    out = pd.DataFrame(rows)
    out["pct_per_50bp"] = out.beta_per_bp * 50
    out["pct_per_50bp_se"] = out.se_per_bp * 50
    return out


def scenario_impacts(betas: pd.DataFrame, rates_scen: pd.DataFrame, origin_fii10: float, version: str = "raw") -> pd.DataFrame:
    """Implied sector move (%) at the end of the projection for each scenario, using the projected 10y real yield."""
    b = betas[betas.version == version].set_index("sector")["beta_per_bp"]
    end = rates_scen[rates_scen.date == rates_scen.date.max()].set_index("scenario")
    rows = []
    for s, r in end.iterrows():
        for rule, col in (("core rule", "FII10"), ("hawkish", "FII10_hawk")):
            d_bp = 100.0 * (r[col] - origin_fii10)
            for k, beta in b.items():
                rows.append(dict(scenario=s, rule=rule, sector=k, d_real_bp=d_bp, implied_pct=beta * d_bp, version=version))
    return pd.DataFrame(rows)
