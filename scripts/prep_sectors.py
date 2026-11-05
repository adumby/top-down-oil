"""Turn the sector-ETF spreadsheet export (date/price column pairs, one pair per ETF) into
data/raw/market/sectors_daily.csv (one Date column, one column per ETF).

    python scripts/prep_sectors.py path/to/export.csv
XLK is kept separately in XLK_daily.csv and merged in by the loader.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def tidy(path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=0)
    cols, out = list(raw.columns), {}
    for i in range(1, len(cols), 2):
        name = cols[i]
        d = pd.to_datetime(raw.iloc[:, i - 1], format="%m/%d/%Y", errors="coerce")
        p = pd.to_numeric(raw.iloc[:, i], errors="coerce")
        s = pd.Series(p.values, index=d).dropna()
        s = s[~s.index.isna()]
        out[name] = s[~s.index.duplicated()]
    return pd.DataFrame(out).sort_index()


if __name__ == "__main__":
    df = tidy(sys.argv[1])
    df.index.name = "Date"
    dest = ROOT / "data" / "raw" / "market" / "sectors_daily.csv"
    df.round(4).to_csv(dest)
    print(dest, df.shape)
    print(df.apply(lambda s: (s.first_valid_index().date(), s.last_valid_index().date())))
