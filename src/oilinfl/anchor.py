"""Expectations anchor for the long-run inflation level.

An ARDL's intercept implies a steady-state inflation rate c / (1 - sum a). Left
alone, that is the 1988-2025 sample average (about 2.8% for CPI), which sits
above where inflation has settled since expectations were anchored around 2%.
The anchor replaces the intercept at forecast time so that, with oil flat, the
model converges to:

    CPI series : the 10-year breakeven (market expected CPI inflation)
    PCE series : the breakeven minus the trailing 10-year average CPI-PCE gap

Slopes (own lags and oil lags) are untouched. Out-of-sample tests
(robust_oos.csv) compare anchored and unanchored versions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def anchor_mu(levels: pd.DataFrame, inflation: pd.DataFrame, acfg: dict, target: str, T) -> float | None:
    """Annual steady-state inflation (%) for ``target`` using information up to date ``T``."""
    if acfg.get("mode", "sample") == "sample" or target not in acfg["targets"]:
        return None
    be = levels[acfg["series"]].loc[:T].dropna()
    if be.empty:
        return None
    mu = float(be.iloc[-1])
    ref = acfg["targets"][target]
    if ref is not None:
        gap = (inflation[ref] - inflation[target]).loc[:T].dropna().iloc[-acfg["wedge_months"]:]
        mu -= float(gap.mean() * 12.0)
    return mu


def anchored_const(params: np.ndarray, p: int, mu: float) -> np.ndarray:
    """Intercept(s) giving steady-state monthly inflation mu/12 (log-percent)."""
    P = np.atleast_2d(params)
    return (1.0 - P[:, 1:1 + p].sum(axis=1)) * mu / 12.0


def with_anchor(params: np.ndarray, p: int, mu: float | None) -> np.ndarray:
    if mu is None:
        return params
    out = np.array(params, dtype=float, copy=True)
    if out.ndim == 1:
        out[0] = anchored_const(out, p, mu)[0]
    else:
        out[:, 0] = anchored_const(out, p, mu)
    return out
