"""Refresh data/raw from public sources.

    python scripts/update_data.py            # FRED series + 3-2-1 crack spread
    python scripts/update_data.py --bea KEY  # also BEA Table 2.8.7 via the BEA API

FRED needs no API key (it uses the public fredgraph CSV endpoint). Files are
written in the same `observation_date,<ID>` format the loader expects, so a
refresh never requires code changes.

Two inputs are manual:
  * XLK daily prices -> data/raw/market/XLK_daily.csv
    (any export with Date, Open, High, Low, Close columns, e.g. from WSJ/Barron's;
    dates as MM/DD/YY). Not on FRED.
  * BEA Table 2.8.7 if you have no BEA API key: download "Table 2.8.7. Percent
    Change From Preceding Period in Prices for Personal Consumption Expenditures
    by Major Type of Product, Monthly" from apps.bea.gov/iTable, transpose it so
    dates are rows, and save as data/raw/bea/table_2_8_7_pct_change.csv.

After refreshing, move `forecast.origin` in config.yaml to the last month of
data and re-run `python -m oilinfl`. The pipeline refuses to run if a target
ends before the origin.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

FRED_SERIES = [
    # prices
    "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE",
    # oil and refined products
    "MCOILBRENTEU", "GASREGW", "GASDESW", "WJFUELUSGULF", "WPU0571", "WPU057203", "WPU057303",
    # CPI transportation detail
    "CUSR0000SETA", "CUSR0000SETD", "CUSR0000SETG", "CUSR0000SETG01",
    # labour market and rates
    "UNRATE", "FEDFUNDS", "GS2", "FII5", "FII10", "T5YIEM", "T10YIEM",
]
# NY Harbor conventional gasoline and NY Harbor ULSD; swap IDs here if FRED renames them
CRACK_INPUTS = {"wti": "DCOILWTICO", "gasoline": "DGASNYH", "distillate": "DDFUELNYH"}


def fetch_fred(sid: str) -> pd.Series:
    with urllib.request.urlopen(FRED_URL.format(sid=sid), timeout=60) as r:
        df = pd.read_csv(io.BytesIO(r.read()), na_values=["."])
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(df.iloc[:, 0]), name=sid)
    return s


def write_fred(s: pd.Series, sid: str) -> None:
    out = pd.DataFrame({"observation_date": s.index.strftime("%Y-%m-%d"), sid: s.values})
    out.to_csv(RAW / "fred" / f"{sid}.csv", index=False)


def crack_spread() -> pd.DataFrame:
    """3-2-1 crack spread, $/bbl: (2 x gasoline + 1 x distillate) x 42 - 3 x WTI, divided by 3."""
    parts = {k: fetch_fred(v) for k, v in CRACK_INPUTS.items()}
    df = pd.DataFrame(parts).dropna()
    df["crack_321"] = (2 * df.gasoline * 42 + df.distillate * 42 - 3 * df.wti) / 3
    df.index.name = "date"
    return df.round(4)


def fetch_bea(key: str) -> pd.DataFrame:
    url = ("https://apps.bea.gov/api/data?UserID={k}&method=GetData&DataSetName=NIPA&TableName=T20807"
           "&Frequency=M&Year=ALL&ResultFormat=JSON").format(k=key)
    with urllib.request.urlopen(url, timeout=120) as r:
        data = json.load(r)["BEAAPI"]["Results"]["Data"]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["TimePeriod"].str.replace("M", "-") + "-01")
    df["value"] = pd.to_numeric(df["DataValue"].str.replace(",", ""), errors="coerce")
    wide = df.pivot_table(index="date", columns="LineDescription", values="value", aggfunc="first")
    return wide.sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bea", metavar="API_KEY", help="BEA API key (optional)")
    a = ap.parse_args()
    failed = []
    for sid in FRED_SERIES:
        try:
            s = fetch_fred(sid)
            write_fred(s, sid)
            print(f"{sid:14s} {s.first_valid_index():%Y-%m-%d} .. {s.last_valid_index():%Y-%m-%d}")
        except Exception as e:  # keep going; report at the end
            failed.append((sid, str(e)))
    try:
        c = crack_spread()
        c.to_csv(RAW / "eia" / "crack_321_daily.csv")
        print(f"crack_321      {c.index[0]:%Y-%m-%d} .. {c.index[-1]:%Y-%m-%d}")
    except Exception as e:
        failed.append(("crack_321", str(e)))
    if a.bea:
        try:
            # Column names from the API can differ slightly from the shipped file
            # (footnote digits); check config.yaml target columns after refreshing.
            fetch_bea(a.bea).to_csv(RAW / "bea" / "table_2_8_7_pct_change.csv")
            print("BEA table 2.8.7 updated")
        except Exception as e:
            failed.append(("BEA", str(e)))
    for sid, err in failed:
        print(f"FAILED {sid}: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
