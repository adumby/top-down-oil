"""Scenario paths, point forecasts and bootstrap fan charts for the inflation block."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .anchor import with_anchor
from .model import ARDL, block_bootstrap, design, simulate
import statsmodels.api as sm


# ----------------------------------------------------------- driver paths --
def build_path(origin_level: float, origin: pd.Timestamp, horizon: int, steps: list[dict]) -> pd.Series:
    """Future driver levels (t0 = origin + 1 month ... origin + horizon).

    Each step applies from ``from`` onward and is one of
      {from, mult}           level = mult * origin_level
      {from, level}          level = $ value
      {from, to, glide, level}  log-linear move from the previous level to ``level``
                                ending at ``to``, then held
    Steps are applied in order, so later steps override earlier ones.
    """
    idx = pd.date_range(origin + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    path = pd.Series(float(origin_level), index=idx)
    for st in steps:
        f = pd.Timestamp(st["from"])
        if st.get("glide"):
            t = pd.Timestamp(st["to"])
            start_level = path.loc[:f - pd.offsets.MonthBegin(1)].iloc[-1] if f > idx[0] else origin_level
            seg = pd.date_range(f, t, freq="MS")
            w = np.arange(1, len(seg) + 1) / len(seg)
            vals = np.exp(np.log(start_level) + w * (np.log(st["level"]) - np.log(start_level)))
            path.loc[seg[seg <= idx[-1]]] = vals[: (seg <= idx[-1]).sum()]
            path.loc[path.index > t] = st["level"]
        elif "mult" in st:
            path.loc[path.index >= f] = origin_level * st["mult"]
        elif "level" in st:
            path.loc[path.index >= f] = st["level"]
        else:
            raise ValueError(f"bad scenario step {st}")
    return path


def driver_logchange(history_levels: pd.Series, future_levels: pd.Series) -> pd.Series:
    full = pd.concat([history_levels.dropna(), future_levels])
    return 100.0 * np.log(full).diff()


# --------------------------------------------------------- residual carry --
def recent_error(model: ARDL, y: pd.Series, x: pd.Series, origin: pd.Timestamp, window: int,
                 mu: float | None = None) -> tuple[float, pd.Series]:
    """Mean one-step forecast error over the last ``window`` months up to the origin.

    Uses the same (possibly anchored) parameters as the forecast itself.
    """
    dates = pd.date_range(origin - pd.offsets.MonthBegin(window - 1), origin, freq="MS")
    X = sm.add_constant(design(y, x, model.p, model.q), has_constant="add")[model.names]
    pred = X.loc[dates] @ with_anchor(model.params, model.p, mu)
    err = (y.loc[dates] - pred).rename("error")
    return float(err.mean()), err


def carry_path(mean_err: float, horizon: int, mode: str, halflife: float) -> np.ndarray:
    h = np.arange(1, horizon + 1)
    if mode == "fades":
        return np.zeros(horizon)
    if mode == "persists":
        return np.full(horizon, mean_err)
    if mode == "decay":
        return mean_err * 0.5 ** (h / halflife)
    raise ValueError(mode)


# ------------------------------------------------------------- forecasting --
@dataclass
class Forecast:
    target: str
    scenario: str
    mode: str
    dates: pd.DatetimeIndex
    mom_log: np.ndarray            # (R, H) simulated monthly log-percent (R = 1 for point)
    hist: pd.Series                # actual monthly log-percent up to origin

    def _stack(self) -> np.ndarray:
        """(R, 12 + H) history tail + simulation, for 12-month windows."""
        tail = np.repeat(self.hist.iloc[-12:].values[None, :], self.mom_log.shape[0], axis=0)
        return np.concatenate([tail, self.mom_log], axis=1)

    def yoy(self) -> np.ndarray:
        S = self._stack()
        cs = np.cumsum(S, axis=1)
        roll = cs[:, 12:] - cs[:, :-12]
        return 100.0 * np.expm1(roll / 100.0)

    def annualized(self, months: int) -> np.ndarray:
        S = self._stack()
        cs = np.concatenate([np.zeros((S.shape[0], 1)), np.cumsum(S, axis=1)], axis=1)
        # window of `months` months ending at each simulated month
        n = S.shape[1]
        ends = np.arange(12, n)
        win = cs[:, ends + 1] - cs[:, ends + 1 - months]
        return 100.0 * np.expm1(win * (12.0 / months) / 100.0)

    def mom_pct(self) -> np.ndarray:
        return 100.0 * np.expm1(self.mom_log / 100.0)


def point_forecast(model: ARDL, y: pd.Series, x_hist: pd.Series, future_x: pd.Series,
                   origin: pd.Timestamp, carry: np.ndarray, target: str, scenario: str, mode: str,
                   mu: float | None = None) -> Forecast:
    q, p = model.q, model.p
    xall = pd.concat([x_hist.loc[:origin], future_x])
    x_path = xall.iloc[-(q + len(future_x)):].values
    y_hist = y.loc[:origin].iloc[-p:].values
    sim = simulate(with_anchor(model.params, p, mu), p, q, y_hist, x_path, carry=carry)
    return Forecast(target, scenario, mode, future_x.index, sim, y.loc[:origin].dropna())


def bootstrap_forecast(model: ARDL, y: pd.Series, x_hist: pd.Series, future_x: pd.Series,
                       origin: pd.Timestamp, carry: np.ndarray, reps: int, block: int,
                       rng: np.random.Generator, target: str, scenario: str, mode: str,
                       mu: float | None = None) -> Forecast:
    """Fan chart draws: coefficients ~ N(beta, HAC cov) and moving-block residual shocks."""
    q, p = model.q, model.p
    H = len(future_x)
    xall = pd.concat([x_hist.loc[:origin], future_x])
    x_path = xall.iloc[-(q + H):].values
    y_hist = y.loc[:origin].iloc[-p:].values
    draws = rng.multivariate_normal(model.params, model.cov, size=reps, method="cholesky")
    # keep draws stationary: shrink any draw whose AR sum >= 0.98 back to the point estimate
    bad = draws[:, 1:1 + p].sum(axis=1) >= 0.98
    draws[bad] = model.params
    draws = with_anchor(draws, p, mu)
    shocks = block_bootstrap(model.resid.values, reps, H, block, rng)
    sim = simulate(draws, p, q, y_hist, x_path, shocks=shocks, carry=carry)
    return Forecast(target, scenario, mode, future_x.index, sim, y.loc[:origin].dropna())
