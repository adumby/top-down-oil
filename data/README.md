# Data

Everything the model reads is in `data/raw/`. All series are public except the XLK price export.
Data run through **September 2026** (rates and breakevens through October 2026).
`scripts/update_data.py` refreshes the FRED series and the crack spread. It writes the same file
format, so no code changes are needed after a refresh.

| File | ID | What it is | Source | Freq. | Starts | Used for |
|---|---|---|---|---|---|---|
| `fred/CPIAUCSL.csv` | CPIAUCSL | CPI, all items, SA | BLS via FRED | M | 1985 | Target: headline CPI |
| `fred/CPILFESL.csv` | CPILFESL | CPI less food & energy, SA | BLS via FRED | M | 1985 | Target: core CPI |
| `fred/PCEPI.csv` | PCEPI | PCE price index | BEA via FRED | M | 1985 | Target: headline PCE |
| `fred/PCEPILFE.csv` | PCEPILFE | PCE ex food & energy | BEA via FRED | M | 1987 | Target: core PCE |
| `bea/table_2_8_7_pct_change.csv` | NIPA 2.8.7 | % change from prior month, PCE prices by product | BEA | M | 1971 | Targets: energy, gasoline, transportation services |
| `fred/MCOILBRENTEU.csv` | MCOILBRENTEU | Brent crude, $/bbl, monthly avg | EIA via FRED | M | 1987-05 | Main driver |
| `fred/GASREGW.csv` | GASREGW | Retail regular gasoline, $/gal | EIA via FRED | W | 1990 | Refined-fuel driver |
| `fred/GASDESW.csv` | GASDESW | Retail diesel, $/gal | EIA via FRED | W | 1994 | Refined-fuel driver |
| `fred/WJFUELUSGULF.csv` | WJFUELUSGULF | Gulf Coast jet fuel spot, $/gal | EIA via FRED | W | 1990 | Refined-fuel driver |
| `fred/WPU0571.csv` | WPU0571 | PPI refined petroleum products | BLS via FRED | M | 1980 | Refined-fuel driver |
| `fred/WPU057203.csv`, `WPU057303.csv` | | PPI jet fuel, PPI diesel | BLS via FRED | M | 1973+ | Reference |
| `fred/CUSR0000SET*.csv` | SETA, SETD, SETG, SETG01 | CPI vehicles, repair, public transport, airfares | BLS via FRED | M | 1967+ | Reference (transportation detail) |
| `eia/crack_321_daily.csv` | | WTI, NY Harbor gasoline & distillate, 3-2-1 crack spread | EIA (computed) | D | 1986 | Refining-margin context |
| `fred/T5YIEM.csv`, `T10YIEM.csv` | | 5y and 10y breakeven inflation | FRB via FRED | M | 2003 | Expectations link |
| `fred/FII5.csv`, `FII10.csv` | | 5y and 10y TIPS real yields | FRB via FRED | M | 2003 | Real-yield link |
| `fred/GS2.csv` | GS2 | 2y Treasury yield | FRB via FRED | M | 1990 | Fed reaction function |
| `fred/FEDFUNDS.csv` | FEDFUNDS | Effective fed funds rate | FRB via FRED | M | 1987 | Context |
| `fred/UNRATE.csv` | UNRATE | Unemployment rate | BLS via FRED | M | 1987 | Fed reaction function |
| `market/XLK_daily.csv` | XLK | Technology Select Sector SPDR, daily OHLC | user export | D | 1998 | Equity link |

## How the data are formatted, and why

1. **One calendar.** Every series is put on a complete month-start index *before* any lag or difference.
   Shifting rows on an index with a missing month misaligns dates without any error (a 12-row shift
   stops being 12 months). `tests/test_data.py::test_shift_alignment_after_missing_month` guards this.
2. **Inflation in log-percent.** Monthly inflation is `100 x dln(index)`. Log changes add, so a
   12-month change is a rolling sum and YoY is `100 x (exp(sum/100) - 1)` exactly. The YoY figures match
   the published index ratios to machine precision (tested).
3. **BEA percent changes converted.** Table 2.8.7 reports simple % changes rounded to 0.1. They are
   converted with `100 x ln(1 + x/100)`. Headline and core PCE use the FRED indexes instead, which are
   unrounded. Every month 1990–2026 matches the BEA table after rounding (checked).
4. **Weekly and daily to monthly averages.** Retail fuels, jet fuel and the crack spread are averaged
   within the month to match Brent (a monthly average) and the monthly CPI/PCE price collection.
   Market rates are FRED monthly averages for the same reason.
5. **Short gaps filled.** The October 2025 CPI was never published (government shutdown). Gaps of up to
   3 months are filled log-linearly, so the change is split evenly across the two months; longer gaps
   stay empty. Every filled month is listed in `outputs/results.json` under `filled_gaps`.
6. **Covid excluded from estimation.** March 2020 to June 2021 is dropped from estimation (not from
   history). Lockdown and reopening moved prices for reasons unrelated to oil, and leaving them in would
   bend the oil coefficients. Including them changes the long-run pass-through little
   (`robust_other.csv`, `covid_included_lr10`).
7. **Validation.** `FII10 + T10YIEM` reproduces the nominal 10-year yield to within 0.01pp in every
   month. The September 2026 YoY rates for CPI and core PCE are checked against the published index
   levels in `tests/test_pipeline.py`.

## Notes on specific series

- Jet fuel's last weekly print is 4 Sep 2026, so its September monthly value is a single week.
- The XLK file comes from a market-data export. Check its terms before publishing it in a public
  repository, or add `data/raw/market/` to `.gitignore` and ask users to supply their own.
