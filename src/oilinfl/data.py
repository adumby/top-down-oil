"""Data loading and transformations.

Conventions used everywhere in the package
------------------------------------------
* Every series is put on a complete month-start (``MS``) index before any
  lag or difference is taken. Shifting by rows on an index with a missing
  month silently misaligns dates (e.g. a 12-row shift is no longer 12
  months), so :func:`full_monthly` is applied first, always.
* Inflation is carried as **monthly log-percent**: ``100 * dln(P)``.
  Log changes add up over time, so a 12-month change is a rolling sum and
  the YoY rate is ``100 * (exp(sum/100) - 1)`` exactly.
* BEA percent changes (``kind: pct``) are converted with
  ``100 * ln(1 + x/100)`` so they live on the same log scale.
* Short gaps (at most 3 months, e.g. the Oct-2025 CPI that was never
  published) are filled log-linearly and reported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

MAX_GAP = 3


# ---------------------------------------------------------------- readers --
def read_fred_csv(path: str | Path) -> pd.Series:
    """Read a FRED-style CSV (``observation_date,<ID>`` or ``date,<ID>``).

    Blank cells and FRED's "." placeholder become NaN.
    """
    df = pd.read_csv(path, na_values=[".", ""], keep_default_na=True)
    date_col = df.columns[0]
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(df[date_col]), name=df.columns[1])
    return s.sort_index()


def read_xlk(path: str | Path) -> pd.Series:
    """Daily close from a WSJ/Barron's-style export (Date, Open, High, Low, Close)."""
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    idx = pd.to_datetime(df["Date"], format="%m/%d/%y")
    return pd.Series(df["Close"].astype(float).values, index=idx, name="XLK").sort_index()


def read_bea_table(path: str | Path) -> pd.DataFrame:
    """BEA NIPA Table 2.8.7 (percent change from preceding month), one column per line."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.sort_index()


# --------------------------------------------------------- transformations --
def to_monthly(s: pd.Series, how: str = "mean") -> pd.Series:
    """Collapse daily/weekly data to month-start frequency."""
    r = s.dropna().resample("MS")
    return getattr(r, how)()


def full_monthly(s: pd.Series, max_gap: int = MAX_GAP, log: bool = True) -> pd.Series:
    """Reindex to a complete monthly index and fill interior gaps of <= max_gap months.

    Gaps are filled linearly in logs (``log=True``, for prices) or levels.
    Longer gaps are left as NaN so they cannot be mistaken for data.
    """
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    s = s[~s.index.duplicated(keep="last")]
    if s.dropna().empty:
        return s
    idx = pd.date_range(s.first_valid_index(), s.last_valid_index(), freq="MS")
    s = s.reindex(idx)
    work = np.log(s) if log and (s.dropna() > 0).all() else s
    filled = work.interpolate(limit=max_gap, limit_area="inside")
    # interpolate(limit=...) partially fills long gaps; undo that
    isna = s.isna()
    run_id = (~isna).cumsum()
    run_len = isna.groupby(run_id).transform("sum")
    filled[isna & (run_len > max_gap)] = np.nan
    out = np.exp(filled) if work is not s else filled
    out.name = s.name
    return out


def gaps_filled(s_raw: pd.Series, s_full: pd.Series) -> list[str]:
    """Months that were interpolated by :func:`full_monthly`."""
    raw = s_raw.copy()
    raw.index = pd.DatetimeIndex(raw.index).to_period("M").to_timestamp()
    raw = raw[~raw.index.duplicated(keep="last")]
    miss = s_full.index[raw.reindex(s_full.index).isna() & s_full.notna()]
    return [d.strftime("%Y-%m") for d in miss]


def logpct_from_index(p: pd.Series) -> pd.Series:
    """Monthly inflation in log-percent from a price index."""
    return 100.0 * np.log(p).diff()


def logpct_from_pct(x: pd.Series) -> pd.Series:
    """Convert simple percent changes (BEA) to log-percent."""
    return 100.0 * np.log1p(x / 100.0)


def pct_from_logpct(m: pd.Series | np.ndarray):
    """Simple percent change from log-percent (for reporting MoM)."""
    return 100.0 * np.expm1(np.asarray(m) / 100.0) if not isinstance(m, pd.Series) \
        else 100.0 * np.expm1(m / 100.0)


def yoy_from_logpct(m: pd.Series) -> pd.Series:
    """Exact year-over-year percent change from monthly log-percent changes."""
    return 100.0 * np.expm1(m.rolling(12).sum() / 100.0)


def annualized_from_logpct(m: pd.Series, months: int) -> pd.Series:
    """Annualized rate over the last ``months`` months (3m, 6m saar)."""
    return 100.0 * np.expm1(m.rolling(months).sum() * (12.0 / months) / 100.0)


def mask_windows(index: pd.DatetimeIndex, windows) -> np.ndarray:
    """Boolean array, True for dates inside any [start, end] window (inclusive)."""
    m = np.zeros(len(index), dtype=bool)
    for a, b in windows or []:
        m |= (index >= pd.Timestamp(a)) & (index <= pd.Timestamp(b))
    return m


# ---------------------------------------------------------------- dataset --
@dataclass
class Dataset:
    """Everything the models need, on monthly month-start indices."""
    inflation: pd.DataFrame            # targets, monthly log-percent
    levels: pd.DataFrame               # Brent, fuels, yields, unemployment (levels)
    labels: dict[str, str]
    xlk_daily: pd.Series | None = None
    bea: pd.DataFrame | None = None
    filled: dict[str, list[str]] = field(default_factory=dict)

    @property
    def last_actual(self) -> pd.Timestamp:
        return self.inflation.dropna(how="all").index.max()


FRED_LEVELS = ["MCOILBRENTEU", "UNRATE", "GS2", "FEDFUNDS", "FII5", "FII10",
               "T5YIEM", "T10YIEM", "WPU0571", "WPU057203", "WPU057303",
               "CUSR0000SETA", "CUSR0000SETD", "CUSR0000SETG", "CUSR0000SETG01"]
FRED_WEEKLY = ["GASREGW", "GASDESW", "WJFUELUSGULF"]
NOT_PRICES = {"UNRATE", "GS2", "FEDFUNDS", "FII5", "FII10", "T5YIEM", "T10YIEM"}


def load(cfg: dict, root: str | Path = ".") -> Dataset:
    """Load and transform every input listed in the config."""
    root = Path(root)
    d = root / cfg["data_dir"]
    filled: dict[str, list[str]] = {}

    bea = read_bea_table(d / "bea" / "table_2_8_7_pct_change.csv")
    bea.index = bea.index.to_period("M").to_timestamp()

    infl, labels = {}, {}
    for key, t in cfg["targets"].items():
        labels[key] = t["label"]
        if t["source"] == "fred":
            raw = read_fred_csv(d / "fred" / f"{t['id']}.csv")
            full = full_monthly(raw)
            filled[t["id"]] = gaps_filled(raw, full)
            infl[key] = logpct_from_index(full)
        elif t["source"] == "bea":
            col = bea[t["column"]].astype(float)
            full = col.reindex(pd.date_range(col.first_valid_index(),
                                             col.last_valid_index(), freq="MS"))
            infl[key] = logpct_from_pct(full)
        else:
            raise ValueError(f"unknown source {t['source']}")
    inflation = pd.DataFrame(infl)

    lv = {}
    for sid in FRED_LEVELS:
        f = d / "fred" / f"{sid}.csv"
        if f.exists():
            raw = read_fred_csv(f)
            full = full_monthly(raw, log=sid not in NOT_PRICES)
            filled[sid] = gaps_filled(raw, full)
            lv[sid] = full
    for sid in FRED_WEEKLY:
        f = d / "fred" / f"{sid}.csv"
        if f.exists():
            lv[sid] = full_monthly(to_monthly(read_fred_csv(f)))
    crack = d / "eia" / "crack_321_daily.csv"
    if crack.exists():
        c = pd.read_csv(crack, parse_dates=["date"], index_col="date")["crack_321"]
        lv["CRACK321"] = full_monthly(to_monthly(c), log=False)
    levels = pd.DataFrame(lv)

    xlk = None
    xf = d / cfg["rates"]["equity"]["file"]
    if xf.exists():
        xlk = read_xlk(xf)

    labels["brent"] = cfg["driver"]["label"]
    return Dataset(inflation=inflation, levels=levels, labels=labels,
                   xlk_daily=xlk, bea=bea, filled={k: v for k, v in filled.items() if v})


def brent_logchange(ds: Dataset, driver_id: str) -> pd.Series:
    return 100.0 * np.log(ds.levels[driver_id]).diff()
