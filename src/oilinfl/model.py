"""Autoregressive distributed-lag (ARDL) model and its simulator.

    y_t = c + sum_{j=1..p} a_j y_{t-j} + sum_{k=0..q} b_k x_{t-k} + e_t

y is monthly inflation (log-percent), x is the monthly log-percent change in
the driver (Brent unless stated otherwise). Standard errors are Newey-West
(HAC). The simulator is vectorised over draws so the same code produces the
point forecast (one draw, no shocks) and the bootstrap fan (many draws).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .data import mask_windows

TEN_PCT = 100.0 * np.log(1.10)   # a +10% level move in log-percent units


def design(y: pd.Series, x: pd.Series | dict, p: int, q: int | dict) -> pd.DataFrame:
    """Lag matrix [y_1..y_p, x_0..x_q] (no constant). ``x`` may be a dict of drivers."""
    cols = [y.shift(j).rename(f"y{j}") for j in range(1, p + 1)]
    xs = x if isinstance(x, dict) else {"x": x}
    qs = q if isinstance(q, dict) else {k: q for k in xs}
    for name, s in xs.items():
        cols += [s.shift(k).rename(f"{name}{k}") for k in range(qs[name] + 1)]
    return pd.concat(cols, axis=1, sort=True)


@dataclass
class ARDL:
    p: int
    q: int
    names: list[str]
    params: np.ndarray
    cov: np.ndarray
    resid: pd.Series
    fitted: pd.Series
    nobs: int
    r2: float
    r2_adj: float
    aic: float
    bic: float
    sample: tuple[str, str]
    result: object = None            # statsmodels result, for diagnostics
    drivers: tuple[str, ...] = ("x",)

    # ---------------------------------------------------------- summaries --
    def _idx(self, prefix: str) -> list[int]:
        return [i for i, n in enumerate(self.names) if n.startswith(prefix) and n[len(prefix):].isdigit()]

    @property
    def ar_sum(self) -> float:
        return float(self.params[self._idx("y")].sum())

    def long_run(self, driver: str = "x", scale: float = TEN_PCT) -> tuple[float, float]:
        """Long-run effect on the price level of a permanent driver move, with delta-method SE.

        Returned in percent of the price level per ``scale`` (default: a +10% move).
        """
        ia, ib = self._idx("y"), self._idx(driver)
        a, b = self.params[ia].sum(), self.params[ib].sum()
        lr = b / (1.0 - a)
        g = np.zeros(len(self.params))
        g[ia] = b / (1.0 - a) ** 2
        g[ib] = 1.0 / (1.0 - a)
        se = float(np.sqrt(g @ self.cov @ g))
        return float(lr * scale), float(se * scale)

    def wald_driver(self, driver: str = "x") -> float:
        """p-value that all driver coefficients are jointly zero (HAC)."""
        ib = self._idx(driver)
        R = np.zeros((len(ib), len(self.params)))
        for r, i in enumerate(ib):
            R[r, i] = 1.0
        return float(self.result.f_test(R).pvalue)

    def irf(self, driver: str = "x", shock: float = TEN_PCT, horizon: int = 36) -> np.ndarray:
        """Cumulative response of the price level (percent) to a one-time permanent driver move."""
        a = self.params[self._idx("y")]
        b = self.params[self._idx(driver)]
        y = np.zeros(horizon + len(a))
        for h in range(horizon):
            v = b[h] * shock if h < len(b) else 0.0
            for j, aj in enumerate(a, start=1):
                v += aj * y[len(a) + h - j]
            y[len(a) + h] = v
        return np.cumsum(y[len(a):])


def fit_ardl(y: pd.Series, x: pd.Series | dict, p: int, q: int | dict,
             start: str, end: str, exclude=None, hac_lags: int = 12) -> ARDL:
    X = design(y, x, p, q)
    z = pd.concat([y.rename("_y"), X], axis=1, sort=True).loc[start:end].dropna()
    z = z[~mask_windows(z.index, exclude)]
    Xc = sm.add_constant(z.drop(columns="_y"), has_constant="add")
    res = sm.OLS(z["_y"], Xc).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    drivers = tuple(x.keys()) if isinstance(x, dict) else ("x",)
    return ARDL(p=p, q=q if isinstance(q, int) else max(q.values()), names=list(Xc.columns),
                params=res.params.values.astype(float), cov=res.cov_params().values.astype(float),
                resid=res.resid, fitted=res.fittedvalues, nobs=int(res.nobs), r2=float(res.rsquared),
                r2_adj=float(res.rsquared_adj), aic=float(res.aic), bic=float(res.bic),
                sample=(z.index[0].strftime("%Y-%m"), z.index[-1].strftime("%Y-%m")),
                result=res, drivers=drivers)


def one_step(model: ARDL, y: pd.Series, x: pd.Series, dates) -> pd.Series:
    """One-step-ahead predictions using actual lagged y and x (single driver)."""
    X = sm.add_constant(design(y, x, model.p, model.q), has_constant="add")[model.names]
    return (X.loc[dates] @ model.params).rename("pred")


def simulate(params: np.ndarray, p: int, q: int, y_hist: np.ndarray, x_path: np.ndarray,
             shocks: np.ndarray | None = None, carry: np.ndarray | None = None) -> np.ndarray:
    """Dynamic simulation of the single-driver ARDL, vectorised over draws.

    params : (k,) or (R, k) in the order [const, y1..yp, x0..xq]
    y_hist : (p,) last p actual values, oldest first
    x_path : (q + H,) driver values from t0-q .. t0+H-1, where t0 is the first simulated month
    shocks : (R, H) additive innovations (bootstrap), optional
    carry  : (H,) deterministic add-on (persisting recent forecast errors), optional
    returns: (R, H) simulated y
    """
    P = np.atleast_2d(params)
    R = P.shape[0]
    H = len(x_path) - q
    if shocks is not None:
        R = max(R, shocks.shape[0])
    if P.shape[0] == 1 and R > 1:
        P = np.repeat(P, R, axis=0)
    const, a, b = P[:, 0], P[:, 1:1 + p], P[:, 1 + p:2 + p + q]
    Y = np.zeros((R, p + H))
    Y[:, :p] = y_hist[-p:]
    for h in range(H):
        v = const.copy()
        for j in range(1, p + 1):
            v += a[:, j - 1] * Y[:, p + h - j]
        xw = x_path[q + h - np.arange(q + 1)]          # x_{t}, x_{t-1}, ..., x_{t-q}
        v += b @ xw
        if carry is not None:
            v += carry[h]
        if shocks is not None:
            v += shocks[:, h]
        Y[:, p + h] = v
    return Y[:, p:]


def months_to_share(cum: np.ndarray, share: float) -> int:
    """First month (0 = impact month) at which the cumulative response reaches ``share`` of its final value."""
    final = cum[-1]
    if abs(final) < 1e-12:
        return -1
    hit = np.where(np.abs(cum) >= share * abs(final))[0]
    return int(hit[0]) if len(hit) else -1


def block_bootstrap(resid: np.ndarray, reps: int, horizon: int, block: int,
                    rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap of (demeaned) residuals -> (reps, horizon)."""
    e = resid - resid.mean()
    n = len(e)
    nb = int(np.ceil(horizon / block))
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    out = np.concatenate([e[s[:, None] + np.arange(block)] for s in starts.T], axis=1)
    return out[:, :horizon]
