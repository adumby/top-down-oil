"""Print the paper's tables as Markdown from outputs/ (so the paper never drifts from the model).

    python scripts/paper_tables.py > docs/tables_generated.md
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
R = json.loads((ROOT / "outputs" / "results.json").read_text())
LAB = {"headline_cpi": "Headline CPI", "core_cpi": "Core CPI", "headline_pce": "Headline PCE", "core_pce": "Core PCE",
       "energy_pce": "PCE energy", "gasoline_pce": "PCE gasoline", "transport_pce": "PCE transportation svcs"}
ORDER = ["flat_114", "flat_105", "up20_nov", "up20_apr", "down25_nov", "down25_apr", "up_down_up", "higher_longer",
         "normalize_75"]
cfg_labels = {"flat_114": "Flat $114", "flat_105": "Flat $105", "up20_nov": "+20% Nov", "up20_apr": "+20% Apr",
              "down25_nov": "-25% Nov", "down25_apr": "-25% Apr", "up_down_up": "Up-down-up",
              "higher_longer": "$125 from Nov", "normalize_75": "Glide to $75"}


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(out)


def f(x, d=2):
    return f"{x:.{d}f}"


print("## Latest data (Sep 2026)\n")
rows = []
for k, v in R["latest"].items():
    rows.append({"Series": LAB[k], "MoM %": f(v["mom_pct"]), "YoY %": f(v["yoy"]), "3m ann. %": f(v["saar3"])})
print(md(pd.DataFrame(rows)))

print("\n## Model summary\n")
m = pd.read_csv(T / "model_summary.csv")
oth = pd.read_csv(T / "robust_other.csv").set_index("target")
rows = []
for r in m.itertuples():
    rows.append({"Series": LAB[r.target], "R2": f(r.r2), "Long-run, +10% Brent": f"{f(r.lr10)} ({f(r.lr10_se)})",
                 "After 12m": f(r.effect_12m), "50% by month": r.months_to_50, "90% by month": r.months_to_90,
                 "Oil joint p": f(r.oil_wald_p, 3), "Placebo p": f(oth.loc[r.target, "placebo_p"], 3)})
print(md(pd.DataFrame(rows)))

print("\n## Backtest 2026 (Jan-Sep, dynamic from Dec 2025, actual Brent)\n")
b = pd.read_csv(T / "backtest_2026.csv")
rows = [{"Series": LAB[r.target], "Actual YoY Sep-26": f(r.actual_yoy), "Model": f(r.model_yoy), "Model, oil flat": f(r.flat_oil_yoy),
         "Oil contribution (pp, Jan-Sep)": f(r.oil_contrib), "Unexplained (pp)": f(r.unexplained)} for r in b.itertuples()]
print(md(pd.DataFrame(rows)))

print("\n## Out-of-sample, 12-month horizon\n")
o = pd.read_csv(T / "robust_oos.csv", index_col=0)
rows = []
for k, r in o.iterrows():
    rows.append({"Series": LAB[k], "RMSE model": f(r["12m_rmse_ardl_oil"]), "vs AR": f"{f(r['12m_ratio_oil_vs_ar'])} (p {f(r['12m_dm_p_oil_vs_ar'])})",
                 "vs random walk": f"{f(r['12m_ratio_oil_vs_rw'])} (p {f(r['12m_dm_p_oil_vs_rw'])})",
                 "Flat-oil vs RW": f"{f(r['12m_ratio_flat_vs_rw'])} (p {f(r['12m_dm_p_flat_vs_rw'])})",
                 "Unanchored RMSE": f(r["12m_rmse_ardl_sample_intercept"]),
                 "Carry 'decay' RMSE": f(r["12m_rmse_ardl_carry_decay"]), "n": int(r["12m_n"])})
print(md(pd.DataFrame(rows)))

print("\n## Robustness: pass-through stability (long-run % per +10% Brent)\n")
s = pd.read_csv(T / "robust_subsamples.csv").pivot(index="target", columns="window", values="lr10")
g = pd.read_csv(T / "robust_lag_grid.csv").groupby("target")["lr10"].agg(["min", "max"])
rows = []
for k in LAB:
    rows.append({"Series": LAB[k], "Baseline": f(oth.loc[k, "baseline_lr10"]), "1988-2007": f(s.loc[k, "1988-2007"]),
                 "2008-2019": f(s.loc[k, "2008-2019"]), "2010-2025": f(s.loc[k, "2010-2025"]),
                 "25 lag specs (min-max)": f"{f(g.loc[k, 'min'])} to {f(g.loc[k, 'max'])}",
                 "Covid included": f(oth.loc[k, "covid_included_lr10"]),
                 "Rise / fall (p equal)": f"{f(oth.loc[k, 'lr_rise10'])} / {f(oth.loc[k, 'lr_fall10'])} ({f(oth.loc[k, 'equal_p'])})",
                 "Chow 2008 p": f(oth.loc[k, "chow_2008_p"], 3)})
print(md(pd.DataFrame(rows)))

print("\n## Residual diagnostics (p-values)\n")
rows = [{"Series": LAB[r.target], "DW": f(r.dw), "BG(12)": f(r.bg12_p, 3), "ARCH(12)": f(r.arch12_p, 3), "JB": f(r.jb_p, 3),
         "RESET": f(r.reset_p, 3)} for r in m.itertuples()]
print(md(pd.DataFrame(rows)))

sc = pd.read_csv(T / "scenario_summary.csv")
for k in ["headline_cpi", "core_cpi", "headline_pce", "core_pce", "transport_pce"]:
    print(f"\n## Scenarios: {LAB[k]} YoY %\n")
    d = sc[sc.target == k].set_index("scenario").loc[ORDER]
    rows = [{"Scenario": cfg_labels[s], "Dec-26": f(r.yoy_dec26, 1), "Mar-27": f(r.yoy_mar27, 1), "Sep-27": f(r.yoy_sep27, 1),
             "Sep-27 10-90%": f"{f(r.yoy_sep27_lo, 1)}-{f(r.yoy_sep27_hi, 1)}", "Avg MoM, next 6m": f(r.avg_mom_6m),
             "Avg MoM, 12m": f(r.avg_mom_12m)} for s, r in d.iterrows()]
    print(md(pd.DataFrame(rows)))

print("\n## Monthly path, Brent flat at $105 (MoM %)\n")
w = pd.read_csv(T / "scenarios_mom_wide.csv", index_col=[0, 1])
sub = w.xs("flat_105", level="scenario").loc[["headline_cpi", "core_cpi", "headline_pce", "core_pce"]].round(2)
sub.index = [LAB[i] for i in sub.index]
sub.columns = [pd.Timestamp(c).strftime("%b-%y") for c in sub.columns]
print(md(sub.reset_index().rename(columns={"index": "Series"})))

print("\n## Regime sensitivity: Sep-27 YoY with 2010-2025 coefficients\n")
rg = pd.read_csv(T / "robust_regime_scenarios.csv")
rows = []
for s in ["flat_105", "up20_nov", "down25_nov", "higher_longer", "normalize_75"]:
    row = {"Scenario": cfg_labels[s]}
    for k in ["headline_pce", "core_pce", "headline_cpi", "core_cpi"]:
        r = rg[(rg.target == k) & (rg.scenario == s)].iloc[0]
        row[LAB[k]] = f"{f(r.yoy_sep27_full, 1)} -> {f(r.yoy_sep27_recent, 1)}"
    rows.append(row)
print(md(pd.DataFrame(rows)))

print("\n## Rates models\n")
print(md(pd.read_csv(T / "rates_models.csv").round(3).fillna("")))

print("\n## Rates and XLK by scenario (Sep-27; origin Sep-26)\n")
rs = pd.read_csv(T / "rates_scenarios.csv")
end = rs[rs.date == rs.date.max()].set_index("scenario").loc[ORDER]
o = R["rates_origin"]
rows = [{"Scenario": "Sep-26 actual", "5y BE": f(o["T5YIEM"]), "10y BE": f(o["T10YIEM"]), "2y (core rule)": f(o["GS2"]),
         "10y real (core rule)": f(o["FII10"]), "XLK % (core rule)": "", "2y (hawkish)": f(o["GS2"]),
         "10y real (hawkish)": f(o["FII10"]), "XLK % (hawkish)": ""}]
for s, r in end.iterrows():
    rows.append({"Scenario": cfg_labels[s], "5y BE": f(r.T5YIEM), "10y BE": f(r.T10YIEM), "2y (core rule)": f(r.GS2),
                 "10y real (core rule)": f(r.FII10), "XLK % (core rule)": f"{r.XLK_implied_pct:+.1f}",
                 "2y (hawkish)": f(r.GS2_hawk), "10y real (hawkish)": f(r.FII10_hawk),
                 "XLK % (hawkish)": f"{r.XLK_implied_pct_hawk:+.1f}"})
print(md(pd.DataFrame(rows)))

print("\n## Refined fuels\n")
fv = pd.read_csv(T / "fuel_variants.csv")
rows = [{"Series": LAB[r.target], "Driver": r.fuel, "R2": f(r.r2), "Long-run +10%": f(r.lr10),
         "Share of 2026 rise": f"{r.share_pct:.0f}%"} for r in fv.itertuples()]
print(md(pd.DataFrame(rows)))

print("\n## Transportation attribution (Jan-Sep 2026, pp)\n")
ta = pd.read_csv(T / "transport_attribution.csv")
rows = [{"Model": r.model, "Adj. R2": f(r.r2_adj), "Actual": f(r.actual_pp), "Fuels": f(r.fuel_pp),
         "General inflation": f(r.core_inflation_pp), "Own lags + const": f(r.own_and_const_pp),
         "Unexplained": f(r.unexplained_pp)} for r in ta.itertuples()]
print(md(pd.DataFrame(rows)))
print("\nanchors:", {k: (round(v, 2) if v is not None else None) for k, v in R["anchors"].items()})
print("rates latest:", R["rates_latest"])

print("\n## Sector sensitivity to the 10y real yield (% move per +50bp)\n")
sb = pd.read_csv(T / "sector_betas.csv")
raw, rel = sb[sb.version == "raw"].set_index("sector"), sb[sb.version == "relative"].set_index("sector")
rows = []
for k in raw.sort_values("pct_per_50bp").index:
    rows.append({"Sector": raw.loc[k, "name"], "Raw": f"{raw.loc[k, 'pct_per_50bp']:+.1f} ({raw.loc[k, 'pct_per_50bp_se']:.1f})",
                 "Raw R2": f(raw.loc[k, "r2"]), "Relative to all sectors": f"{rel.loc[k, 'pct_per_50bp']:+.1f} ({rel.loc[k, 'pct_per_50bp_se']:.1f})",
                 "Relative p": f(rel.loc[k, "p"], 3), "Months": int(raw.loc[k, "nobs"])})
print(md(pd.DataFrame(rows)))
