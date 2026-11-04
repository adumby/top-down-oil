## Latest data (Sep 2026)

| Series | MoM % | YoY % | 3m ann. % |
|---|---|---|---|
| Headline CPI | 0.65 | 3.72 | 4.56 |
| Core CPI | 0.33 | 2.57 | 3.41 |
| Headline PCE | 0.49 | 3.65 | 3.56 |
| Core PCE | 0.32 | 3.12 | 2.90 |
| PCE energy | 5.40 | 21.47 | 27.75 |
| PCE gasoline | 9.20 | 35.45 | 51.41 |
| PCE transportation svcs | 2.10 | 9.36 | 14.44 |

## Model summary

| Series | R2 | Long-run, +10% Brent | After 12m | 50% by month | 90% by month | Oil joint p | Placebo p |
|---|---|---|---|---|---|---|---|
| Headline CPI | 0.52 | 0.39 (0.09) | 0.35 | 1 | 12 | 0.000 | 0.000 |
| Core CPI | 0.50 | 0.10 (0.08) | 0.02 | 13 | 29 | 0.109 | 0.238 |
| Headline PCE | 0.51 | 0.31 (0.08) | 0.26 | 1 | 14 | 0.000 | 0.000 |
| Core PCE | 0.42 | 0.07 (0.07) | 0.04 | 6 | 26 | 0.000 | 0.188 |
| PCE energy | 0.57 | 3.36 (0.31) | 3.42 | 1 | 4 | 0.000 | 0.000 |
| PCE gasoline | 0.61 | 4.95 (0.38) | 5.05 | 0 | 2 | 0.000 | 0.000 |
| PCE transportation svcs | 0.08 | 0.35 (0.12) | 0.31 | 3 | 12 | 0.001 | 0.000 |

## Backtest 2026 (Jan-Sep, dynamic from Dec 2025, actual Brent)

| Series | Actual YoY Sep-26 | Model | Model, oil flat | Oil contribution (pp, Jan-Sep) | Unexplained (pp) |
|---|---|---|---|---|---|
| Headline CPI | 3.72 | 4.05 | 2.41 | 1.59 | -0.32 |
| Core CPI | 2.57 | 2.35 | 2.22 | 0.13 | 0.21 |
| Headline PCE | 3.65 | 3.60 | 2.41 | 1.15 | 0.05 |
| Core PCE | 3.12 | 2.63 | 2.45 | 0.18 | 0.47 |
| PCE energy | 21.47 | 18.36 | 0.55 | 16.30 | 2.59 |
| PCE gasoline | 35.45 | 26.97 | -1.21 | 25.09 | 6.47 |
| PCE transportation svcs | 9.36 | 3.51 | 2.37 | 1.11 | 5.50 |

## Out-of-sample, 12-month horizon

| Series | RMSE model | vs AR | vs random walk | Flat-oil vs RW | Unanchored RMSE | Carry 'decay' RMSE | n |
|---|---|---|---|---|---|---|---|
| Headline CPI | 1.13 | 0.67 (p 0.02) | 0.56 (p 0.04) | 0.80 (p 0.14) | 1.23 | 1.41 | 213 |
| Core CPI | 0.56 | 0.98 (p 0.40) | 0.76 (p 0.23) | 0.78 (p 0.27) | 0.58 | 0.84 | 213 |
| Headline PCE | 0.90 | 0.68 (p 0.03) | 0.58 (p 0.06) | 0.83 (p 0.20) | 0.94 | 1.13 | 213 |
| Core PCE | 0.58 | 0.99 (p 0.66) | 0.87 (p 0.49) | 0.92 (p 0.66) | 0.57 | 0.81 | 213 |
| PCE energy | 5.09 | 0.39 (p 0.01) | 0.25 (p 0.01) | 0.63 (p 0.03) | 5.09 | 6.89 | 213 |
| PCE gasoline | 6.85 | 0.35 (p 0.01) | 0.22 (p 0.02) | 0.63 (p 0.05) | 6.85 | 8.99 | 213 |
| PCE transportation svcs | 2.44 | 0.93 (p 0.12) | 0.83 (p 0.38) | 0.86 (p 0.51) | 2.44 | 2.46 | 213 |

## Robustness: pass-through stability (long-run % per +10% Brent)

| Series | Baseline | 1988-2007 | 2008-2019 | 2010-2025 | 25 lag specs (min-max) | Covid included | Rise / fall (p equal) | Chow 2008 p |
|---|---|---|---|---|---|---|---|---|
| Headline CPI | 0.39 | 0.30 | 0.33 | 0.34 | 0.32 to 0.54 | 0.41 | 0.34 / 0.42 (0.62) | 0.000 |
| Core CPI | 0.10 | 0.21 | -0.03 | 0.07 | 0.03 to 0.22 | 0.25 | 0.07 / 0.11 (0.75) | 0.000 |
| Headline PCE | 0.31 | 0.24 | 0.27 | 0.33 | 0.25 to 0.41 | 0.32 | 0.30 / 0.30 (0.97) | 0.000 |
| Core PCE | 0.07 | 0.04 | 0.06 | 0.20 | 0.06 to 0.14 | 0.17 | 0.14 / -0.00 (0.24) | 0.002 |
| PCE energy | 3.36 | 2.97 | 3.56 | 3.39 | 3.16 to 4.11 | 3.23 | 3.08 / 3.55 (0.34) | 0.000 |
| PCE gasoline | 4.95 | 4.43 | 5.25 | 5.07 | 4.86 to 6.01 | 4.85 | 4.56 / 5.17 (0.32) | 0.000 |
| PCE transportation svcs | 0.35 | 0.19 | 0.28 | 0.44 | 0.21 to 0.59 | 0.46 | 0.46 / 0.26 (0.31) | 0.165 |

## Residual diagnostics (p-values)

| Series | DW | BG(12) | ARCH(12) | JB | RESET |
|---|---|---|---|---|---|
| Headline CPI | 2.02 | 0.000 | 0.000 | 0.000 | 0.001 |
| Core CPI | 2.06 | 0.000 | 0.070 | 0.465 | 0.142 |
| Headline PCE | 2.03 | 0.000 | 0.000 | 0.000 | 0.020 |
| Core PCE | 2.01 | 0.000 | 0.000 | 0.000 | 0.058 |
| PCE energy | 2.01 | 0.362 | 0.072 | 0.000 | 0.000 |
| PCE gasoline | 2.04 | 0.130 | 0.019 | 0.000 | 0.000 |
| PCE transportation svcs | 2.03 | 0.000 | 0.000 | 0.000 | 0.008 |

## Scenarios: Headline CPI YoY %

| Scenario | Dec-26 | Mar-27 | Sep-27 | Sep-27 10-90% | Avg MoM, next 6m | Avg MoM, 12m |
|---|---|---|---|---|---|---|
| Flat $114 | 4.1 | 3.6 | 3.1 | 1.9-4.3 | 0.29 | 0.25 |
| Flat $105 | 3.9 | 3.3 | 2.8 | 1.6-4.0 | 0.25 | 0.23 |
| +20% Nov | 4.6 | 4.2 | 3.7 | 2.4-5.0 | 0.38 | 0.30 |
| +20% Apr | 4.1 | 3.6 | 3.7 | 2.4-4.9 | 0.29 | 0.30 |
| -25% Nov | 3.4 | 2.7 | 2.1 | 0.9-3.3 | 0.15 | 0.17 |
| -25% Apr | 4.1 | 3.6 | 2.2 | 1.0-3.4 | 0.29 | 0.18 |
| Up-down-up | 4.7 | 3.7 | 3.7 | 2.5-5.0 | 0.30 | 0.31 |
| $125 from Nov | 4.3 | 3.9 | 3.4 | 2.2-4.7 | 0.33 | 0.28 |
| Glide to $75 | 3.4 | 2.4 | 1.6 | 0.4-2.8 | 0.09 | 0.13 |

## Scenarios: Core CPI YoY %

| Scenario | Dec-26 | Mar-27 | Sep-27 | Sep-27 10-90% | Avg MoM, next 6m | Avg MoM, 12m |
|---|---|---|---|---|---|---|
| Flat $114 | 2.7 | 2.8 | 2.7 | 2.0-3.4 | 0.22 | 0.22 |
| Flat $105 | 2.7 | 2.8 | 2.7 | 2.0-3.4 | 0.22 | 0.22 |
| +20% Nov | 2.7 | 2.8 | 2.8 | 2.0-3.5 | 0.23 | 0.23 |
| +20% Apr | 2.7 | 2.8 | 2.7 | 2.0-3.5 | 0.22 | 0.23 |
| -25% Nov | 2.7 | 2.7 | 2.6 | 1.9-3.4 | 0.22 | 0.22 |
| -25% Apr | 2.7 | 2.8 | 2.7 | 1.9-3.4 | 0.22 | 0.22 |
| Up-down-up | 2.8 | 2.8 | 2.7 | 2.0-3.5 | 0.22 | 0.23 |
| $125 from Nov | 2.7 | 2.8 | 2.7 | 2.0-3.5 | 0.22 | 0.23 |
| Glide to $75 | 2.7 | 2.7 | 2.6 | 1.9-3.3 | 0.21 | 0.21 |

## Scenarios: Headline PCE YoY %

| Scenario | Dec-26 | Mar-27 | Sep-27 | Sep-27 10-90% | Avg MoM, next 6m | Avg MoM, 12m |
|---|---|---|---|---|---|---|
| Flat $114 | 3.8 | 3.2 | 2.7 | 1.7-3.7 | 0.25 | 0.22 |
| Flat $105 | 3.6 | 3.0 | 2.5 | 1.5-3.5 | 0.22 | 0.20 |
| +20% Nov | 4.1 | 3.6 | 3.2 | 2.2-4.2 | 0.32 | 0.26 |
| +20% Apr | 3.8 | 3.2 | 3.1 | 2.2-4.2 | 0.25 | 0.26 |
| -25% Nov | 3.3 | 2.6 | 2.0 | 1.0-3.0 | 0.15 | 0.16 |
| -25% Apr | 3.8 | 3.2 | 2.1 | 1.1-3.1 | 0.25 | 0.17 |
| Up-down-up | 4.2 | 3.2 | 3.2 | 2.2-4.2 | 0.26 | 0.26 |
| $125 from Nov | 4.0 | 3.4 | 2.9 | 2.0-3.9 | 0.28 | 0.24 |
| Glide to $75 | 3.3 | 2.3 | 1.6 | 0.6-2.6 | 0.11 | 0.13 |

## Scenarios: Core PCE YoY %

| Scenario | Dec-26 | Mar-27 | Sep-27 | Sep-27 10-90% | Avg MoM, next 6m | Avg MoM, 12m |
|---|---|---|---|---|---|---|
| Flat $114 | 3.1 | 2.8 | 2.6 | 1.8-3.3 | 0.22 | 0.21 |
| Flat $105 | 3.1 | 2.8 | 2.5 | 1.8-3.2 | 0.21 | 0.21 |
| +20% Nov | 3.1 | 2.8 | 2.6 | 1.9-3.4 | 0.22 | 0.22 |
| +20% Apr | 3.1 | 2.8 | 2.6 | 1.9-3.3 | 0.22 | 0.21 |
| -25% Nov | 3.1 | 2.7 | 2.5 | 1.7-3.2 | 0.21 | 0.20 |
| -25% Apr | 3.1 | 2.8 | 2.5 | 1.7-3.2 | 0.22 | 0.20 |
| Up-down-up | 3.1 | 2.8 | 2.6 | 1.9-3.3 | 0.21 | 0.22 |
| $125 from Nov | 3.1 | 2.8 | 2.6 | 1.8-3.3 | 0.22 | 0.21 |
| Glide to $75 | 3.0 | 2.7 | 2.4 | 1.7-3.1 | 0.20 | 0.20 |

## Scenarios: PCE transportation svcs YoY %

| Scenario | Dec-26 | Mar-27 | Sep-27 | Sep-27 10-90% | Avg MoM, next 6m | Avg MoM, 12m |
|---|---|---|---|---|---|---|
| Flat $114 | 9.4 | 7.5 | 3.4 | 0.9-6.2 | 0.32 | 0.28 |
| Flat $105 | 9.3 | 7.3 | 3.1 | 0.7-5.8 | 0.30 | 0.26 |
| +20% Nov | 9.6 | 7.7 | 4.0 | 1.4-7.0 | 0.36 | 0.33 |
| +20% Apr | 9.4 | 7.5 | 3.8 | 1.2-6.6 | 0.32 | 0.31 |
| -25% Nov | 9.2 | 7.1 | 2.5 | 0.1-5.0 | 0.26 | 0.20 |
| -25% Apr | 9.4 | 7.5 | 2.9 | 0.5-5.5 | 0.32 | 0.24 |
| Up-down-up | 9.7 | 7.4 | 3.9 | 1.3-6.9 | 0.31 | 0.32 |
| $125 from Nov | 9.5 | 7.6 | 3.7 | 1.2-6.6 | 0.34 | 0.30 |
| Glide to $75 | 9.1 | 6.7 | 2.1 | -0.2-4.5 | 0.21 | 0.17 |

## Monthly path, Brent flat at $105 (MoM %)

| Series | Oct-26 | Nov-26 | Dec-26 | Jan-27 | Feb-27 | Mar-27 | Apr-27 | May-27 | Jun-27 | Jul-27 | Aug-27 | Sep-27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Headline CPI | 0.38 | 0.18 | 0.15 | 0.11 | 0.31 | 0.37 | 0.29 | 0.11 | 0.15 | 0.18 | 0.3 | 0.22 |
| Core CPI | 0.23 | 0.2 | 0.15 | 0.22 | 0.23 | 0.29 | 0.25 | 0.22 | 0.17 | 0.2 | 0.23 | 0.26 |
| Headline PCE | 0.3 | 0.18 | 0.19 | 0.11 | 0.28 | 0.28 | 0.23 | 0.13 | 0.17 | 0.15 | 0.26 | 0.18 |
| Core PCE | 0.2 | 0.21 | 0.2 | 0.19 | 0.25 | 0.23 | 0.2 | 0.2 | 0.21 | 0.17 | 0.23 | 0.21 |

## Regime sensitivity: Sep-27 YoY with 2010-2025 coefficients

| Scenario | Headline PCE | Core PCE | Headline CPI | Core CPI |
|---|---|---|---|---|
| Flat $105 | 2.5 -> 2.7 | 2.5 -> 2.9 | 2.8 -> 2.7 | 2.7 -> 2.7 |
| +20% Nov | 3.2 -> 3.3 | 2.6 -> 3.0 | 3.7 -> 3.5 | 2.8 -> 2.8 |
| -25% Nov | 2.0 -> 2.3 | 2.5 -> 2.8 | 2.1 -> 2.1 | 2.6 -> 2.7 |
| $125 from Nov | 2.9 -> 3.1 | 2.6 -> 3.0 | 3.4 -> 3.2 | 2.7 -> 2.8 |
| Glide to $75 | 1.6 -> 2.0 | 2.4 -> 2.7 | 1.6 -> 1.6 | 2.6 -> 2.6 |

## Rates models

| link | coef | value | se | r2 | nobs | sample | p |
|---|---|---|---|---|---|---|---|
| Breakeven T5YIEM | long-run pp per +10% Brent | 0.06 | 0.017 | 0.367 | 238 | 2004-01..2025-12 |  |
| Breakeven T10YIEM | long-run pp per +10% Brent | 0.062 | 0.013 | 0.316 | 238 | 2004-01..2025-12 |  |
| reaction | lag | 0.924 | 0.01 | 0.984 | 95 | 2016-01..2025-12 | 0.0 |
| reaction | core_yoy | 0.101 | 0.02 | 0.984 | 95 | 2016-01..2025-12 | 0.0 |
| reaction | unrate | -0.008 | 0.06 | 0.984 | 95 | 2016-01..2025-12 | 0.898 |
| reaction_headline | lag | 0.945 | 0.012 | 0.984 | 95 | 2016-01..2025-12 | 0.0 |
| reaction_headline | core_yoy | 0.075 | 0.011 | 0.984 | 95 | 2016-01..2025-12 | 0.0 |
| reaction_headline | unrate | 0.021 | 0.051 | 0.984 | 95 | 2016-01..2025-12 | 0.682 |
| reaction_changes | d_core_yoy | -0.011 | 0.298 | 0.498 | 311 | 1991-01..2025-12 | 0.97 |
| reaction_changes | d_unrate | -1.47 | 0.202 | 0.498 | 311 | 1991-01..2025-12 | 0.0 |
| passthrough | d_gs2 | 0.698 | 0.06 | 0.537 | 265 | 2003-02..2025-12 | 0.0 |
| passthrough | d_be10 | -0.503 | 0.114 | 0.537 | 265 | 2003-02..2025-12 | 0.0 |
| equity | d_real_bp | -0.099 | 0.026 | 0.158 | 116 | 2016-01..2025-12 | 0.0 |
| equity_full | d_real_bp | -0.042 | 0.029 | 0.032 | 271 | 2003-02..2025-12 | 0.144 |
| reaction | long-run core_yoy (b/(1-rho)) | 1.33 |  | 0.984 | 95 | 2016-01..2025-12 |  |
| reaction_headline | long-run headline_yoy (b/(1-rho)) | 1.356 |  | 0.984 | 95 | 2016-01..2025-12 |  |

## Rates and XLK by scenario (Sep-27; origin Sep-26)

| Scenario | 5y BE | 10y BE | 2y (core rule) | 10y real (core rule) | XLK % (core rule) | 2y (hawkish) | 10y real (hawkish) | XLK % (hawkish) |
|---|---|---|---|---|---|---|---|---|
| Sep-26 actual | 2.36 | 2.35 | 4.65 | 2.64 |  | 4.65 | 2.64 |  |
| Flat $114 | 2.27 | 2.33 | 4.36 | 2.45 | +1.9 | 4.36 | 2.45 | +1.9 |
| Flat $105 | 2.21 | 2.27 | 4.34 | 2.46 | +1.8 | 4.23 | 2.39 | +2.5 |
| +20% Nov | 2.38 | 2.45 | 4.41 | 2.42 | +2.2 | 4.62 | 2.57 | +0.7 |
| +20% Apr | 2.38 | 2.45 | 4.38 | 2.41 | +2.3 | 4.50 | 2.48 | +1.5 |
| -25% Nov | 2.09 | 2.14 | 4.29 | 2.49 | +1.4 | 3.95 | 2.26 | +3.8 |
| -25% Apr | 2.08 | 2.14 | 4.33 | 2.52 | +1.2 | 4.15 | 2.40 | +2.4 |
| Up-down-up | 2.41 | 2.47 | 4.40 | 2.40 | +2.4 | 4.58 | 2.53 | +1.1 |
| $125 from Nov | 2.32 | 2.39 | 4.38 | 2.44 | +2.0 | 4.49 | 2.51 | +1.3 |
| Glide to $75 | 2.00 | 2.06 | 4.26 | 2.52 | +1.2 | 3.79 | 2.19 | +4.6 |

## Refined fuels

| Series | Driver | R2 | Long-run +10% | Share of 2026 rise |
|---|---|---|---|---|
| Headline PCE | Brent | 0.53 | 0.34 | 42% |
| Headline PCE | Retail gasoline | 0.67 | 0.48 | 53% |
| Headline PCE | Retail diesel | 0.56 | 0.40 | 62% |
| Headline PCE | Jet fuel (Gulf) | 0.52 | 0.29 | 53% |
| Headline PCE | PPI refined petroleum | 0.60 | 0.34 | 57% |
| Core PCE | Brent | 0.35 | 0.09 | 9% |
| Core PCE | Retail gasoline | 0.34 | 0.12 | 5% |
| Core PCE | Retail diesel | 0.34 | 0.08 | 9% |
| Core PCE | Jet fuel (Gulf) | 0.35 | 0.08 | 12% |
| Core PCE | PPI refined petroleum | 0.34 | 0.09 | 6% |
| PCE energy | Brent | 0.61 | 3.62 | 96% |
| PCE energy | Retail gasoline | 0.85 | 6.01 | 138% |
| PCE energy | Retail diesel | 0.70 | 4.87 | 158% |
| PCE energy | Jet fuel (Gulf) | 0.62 | 3.23 | 125% |
| PCE energy | PPI refined petroleum | 0.73 | 4.29 | 153% |
| PCE transportation svcs | Brent | 0.11 | 0.38 | 14% |
| PCE transportation svcs | Retail gasoline | 0.13 | 0.76 | 20% |
| PCE transportation svcs | Retail diesel | 0.15 | 0.75 | 29% |
| PCE transportation svcs | Jet fuel (Gulf) | 0.16 | 0.41 | 25% |
| PCE transportation svcs | PPI refined petroleum | 0.12 | 0.49 | 21% |

## Transportation attribution (Jan-Sep 2026, pp)

| Model | Adj. R2 | Actual | Fuels | General inflation | Own lags + const | Unexplained |
|---|---|---|---|---|---|---|
| Fuels only | 0.11 | 8.25 | 3.69 | 0.00 | 0.56 | 4.00 |
| Core inflation only | 0.08 | 8.25 | 0.00 | 4.95 | -2.34 | 5.64 |
| Fuels + core inflation | 0.15 | 8.25 | 3.11 | 3.97 | -2.37 | 3.54 |

anchors: {'headline_cpi': 2.35, 'core_cpi': 2.35, 'headline_pce': 1.96, 'core_pce': 2.07, 'energy_pce': None, 'gasoline_pce': None, 'transport_pce': None}
rates latest: {'T5YIEM': ['2026-09', 2.36], 'T10YIEM': ['2026-10', 2.35], 'GS2': ['2026-10', 4.74], 'FII10': ['2026-10', 2.78], 'FII5': ['2026-09', 2.44], 'FEDFUNDS': ['2026-10', 3.88]}
