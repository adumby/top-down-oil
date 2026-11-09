"""Top Down fund: Black-Litterman weights for equity sectors AND bond buckets.

Page of the main app (streamlit run app.py -> sidebar "Portfolio weights").
Inputs: bl_inputs/ (betas, covariances, oil grid) from the daily macro factor
model (Jan 2022 - Oct 2026) and the oil-inflation model.
"""
import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import minimize

st.set_page_config(page_title="Top Down portfolio weights", layout="wide")
IN = next(p for p in (Path(__file__).parent / "bl_inputs", Path(__file__).parent.parent / "bl_inputs",
                      Path(__file__).parent.parent) if (p / "meta.json").exists())

SECTORS = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]
BONDS = ["UST2", "UST5", "UST10", "TIPS10"]
ASSETS = SECTORS + BONDS
NAMES = {"XLK": "Technology", "XLF": "Financials", "XLV": "Health care",
         "XLY": "Consumer discretionary", "XLC": "Communication services",
         "XLI": "Industrials", "XLP": "Consumer staples", "XLE": "Energy",
         "XLU": "Utilities", "XLRE": "Real estate", "XLB": "Materials",
         "UST2": "Bonds: short (2y)", "UST5": "Bonds: intermediate (5y)",
         "UST10": "Bonds: long (10y)", "TIPS10": "Bonds: TIPS (10y)"}
FACTORS = ["oil", "real", "ff12", "be", "term", "hy", "usd", "epu"]
FLABEL = {"oil": "Oil (%)", "real": "Real yield (bp)", "ff12": "Fed expectations (bp)",
          "be": "Breakeven (bp)", "term": "10y-2y spread (bp)", "hy": "HY spread (bp)",
          "usd": "Dollar (%)", "epu": "Policy uncertainty (x100 log)"}

SP500 = {"XLK": 35.718619, "XLF": 12.728703, "XLV": 10.573163, "XLY": 9.465788,
         "XLC": 8.772470, "XLI": 8.128071, "XLP": 5.233176, "XLE": 3.590483,
         "XLU": 2.122525, "XLRE": 1.887814, "XLB": 1.779186}
# Fund weights in % of the whole fund. Bonds: IGSB + IBID + AGZ -> short, VGIT -> intermediate.
CURRENT = {"XLK": 16.47, "XLF": 6.12, "XLV": 6.59, "XLY": 3.70, "XLC": 4.48, "XLI": 3.24,
           "XLP": 6.08, "XLE": 4.99, "XLU": 1.42, "XLRE": 1.14, "XLB": 3.70,
           "UST2": 28.21, "UST5": 6.79, "UST10": 0.0, "TIPS10": 0.0}
PROPOSED = {"XLK": 24.0, "XLF": 5.37, "XLV": 7.13, "XLY": 5.00, "XLC": 5.50, "XLI": 5.71,
            "XLP": 2.03, "XLE": 2.50, "XLU": 2.23, "XLRE": 2.50, "XLB": 1.03,
            "UST2": 28.21, "UST5": 6.79, "UST10": 0.0, "TIPS10": 0.0}
GREEN, BLUE, GREY = "#27532a", "#4b7bb5", "#b5b5b5"


@st.cache_data
def load():
    B = pd.read_csv(IN / "betas_2022_2025.csv", index_col=0).loc[ASSETS, FACTORS]
    B26 = pd.read_csv(IN / "betas_2026.csv", index_col=0).loc[ASSETS, FACTORS]
    bc = pd.read_csv(IN / "beta_covariances.csv")
    V = {s: g.set_index("factor").loc[FACTORS, FACTORS].values for s, g in bc.groupby("sector")}
    Om = pd.read_csv(IN / "factor_covariance_daily.csv", index_col=0).loc[FACTORS, FACTORS]
    D = pd.read_csv(IN / "residual_variance_daily.csv", index_col=0).iloc[:, 0].loc[ASSETS]
    grid = pd.read_csv(IN / "oil_grid_rates.csv").set_index("brent")
    meta = json.load(open(IN / "meta.json"))
    return B, B26, V, Om, D, grid, meta


def factor_moves(grid, meta, brent, rule):
    """Factor moves from the Sep-26 origin to Sep-27 implied by the inflation model."""
    o = meta["origin"]
    gs, fi = ("GS2", "FII10") if rule == "Core" else ("GS2_hawk", "FII10_hawk")
    real = 100 * (grid.loc[brent, fi] - o["FII10"])
    d2 = 100 * (grid.loc[brent, gs] - o["GS2"])
    be = 100 * (grid.loc[brent, "T10YIEM"] - o["T10YIEM"])
    return {"oil": 100 * np.log(brent / o["brent"]), "real": real,
            "ff12": meta["ff12_per_2y"] * d2, "be": be, "term": (real + be) - d2,
            "hy": 0.0, "usd": 0.0, "epu": 0.0}


def black_litterman(B, B26, V, Om, D, grid, meta, wb, df, delta, tau, use_scen, use_drift):
    Bv = B.values
    Sig = (Bv @ Om.values @ Bv.T + np.diag(D.values)) * 252 / 1e4      # annual, decimals
    pi = delta * Sig @ wb.values
    dfv = np.array([df[f] for f in FACTORS])
    shock = Bv @ dfv / 100
    var = np.array([dfv @ V[s] @ dfv for s in ASSETS]) / 1e4            # beta standard errors
    if use_scen:                                                        # spread across oil/Fed scenarios
        pts = [factor_moves(grid, meta, b, r) for b in (75, 90, 105, 115) for r in ("Core", "Hawkish")]
        G = np.array([[p[f] for f in FACTORS] for p in pts])
        var = var + np.var(G @ Bv.T / 100, axis=0)
    if use_drift:                                                       # 2026 vs full-window beta drift
        var = var + ((B26.values - Bv) @ dfv / 100) ** 2
    Omg = np.diag(np.maximum(var, 1e-8))
    tS = tau * Sig
    iT, iO = np.linalg.inv(tS), np.linalg.inv(Omg)
    mu = np.linalg.solve(iT + iO, iT @ pi + iO @ (pi + shock))
    conf = np.diag(tS) / (np.diag(tS) + np.diag(Omg))
    return pd.DataFrame(Sig, ASSETS, ASSETS), pi, mu, shock, np.sqrt(np.diag(Omg)), conf


def optimize(mu, Sig, wb, delta, te, sec_band, bond_band, eq_lo, eq_hi, floor):
    S_, w0 = Sig.values, wb.values
    eq = np.array([a in SECTORS for a in ASSETS], float)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - w0.sum()},
            {"type": "ineq", "fun": lambda w: te ** 2 - (w - w0) @ S_ @ (w - w0)},
            {"type": "ineq", "fun": lambda w: eq @ w - eq_lo},
            {"type": "ineq", "fun": lambda w: eq_hi - eq @ w}]
    bnds = []
    for a, x in zip(ASSETS, w0):
        b = sec_band if a in SECTORS else bond_band
        lo = max(0.0, x - b)
        if a in SECTORS:
            lo = min(max(floor, lo), x)
        bnds.append((lo, x + b))
    x0 = np.clip(w0, [b[0] for b in bnds], [b[1] for b in bnds])
    r = minimize(lambda w: -(w @ mu - delta / 2 * w @ S_ @ w), x0, bounds=bnds,
                 constraints=cons, method="SLSQP", options={"ftol": 1e-12, "maxiter": 2000})
    return pd.Series(r.x, ASSETS), r.success


# ---------------------------------------------------------------- UI
B, B26, V, Om, D, grid, meta = load()
st.title("Top Down fund: portfolio weights from the macro model")
st.caption("Black-Litterman across equity sectors and bond buckets: start at the benchmark, tilt toward "
           "what the inflation model's rate and oil path implies, sized by how confident the data lets us be.")

with st.sidebar:
    st.header("Scenario (to Sep-27)")
    brent = st.select_slider("Brent held flat at ($)", options=list(grid.index), value=105)
    rule = st.radio("Fed reaction", ["Core", "Hawkish"], horizontal=True,
                    help="Core: Fed reacts to core PCE. Hawkish: Fed reacts to headline PCE.")
    df = factor_moves(grid, meta, brent, rule)
    if st.toggle("Override factor moves"):
        for f in FACTORS:
            df[f] = st.number_input(FLABEL[f], value=float(round(df[f], 1)), step=5.0, key=f"ov_{f}")
    st.header("Benchmark")
    bench_eq = st.slider("Equity share of benchmark (%)", 0, 100, 63)
    cash = st.number_input("Cash, held fixed (%)", 0.0, 20.0, 2.0, 0.5)
    st.caption("Bonds in the benchmark follow the fund's current bond mix (edit on the Inputs tab).")
    st.header("Risk limits")
    te = st.slider("Tracking error budget vs benchmark (%)", 0.5, 6.0, 3.0, 0.5) / 100
    sec_band = st.slider("Max over/underweight per equity sector (pp of fund)", 1, 10, 3) / 100
    bond_band = st.slider("Max over/underweight per bond bucket (pp of fund)", 1, 25, 10) / 100
    eq_rng = st.slider("Allowed equity share of fund (%)", 0, 100, (55, 75))
    floor = st.slider("Minimum weight per equity sector (% of fund)", 0.0, 2.0, 0.0, 0.25) / 100
    with st.expander("Model settings"):
        delta = st.number_input("Risk aversion (delta)", 0.5, 10.0, 2.5, 0.5)
        tau = st.number_input("Prior uncertainty (tau)", 0.01, 1.0, 0.05, 0.01)
        use_scen = st.checkbox("Count scenario spread as view uncertainty", True)
        use_drift = st.checkbox("Count 2026 beta drift as view uncertainty", True)

tab_w, tab_in = st.tabs(["Weights", "Inputs and weights to compare"])
with tab_in:
    st.write("S&P 500 column: % of the equity sleeve. Team columns and the bond rows: % of the whole fund.")
    base = pd.DataFrame({"Asset": [NAMES[a] for a in ASSETS],
                         "S&P 500 (equity sleeve)": [SP500.get(a, np.nan) for a in ASSETS],
                         "Team current (fund)": [CURRENT[a] for a in ASSETS],
                         "Team proposed (fund)": [PROPOSED[a] for a in ASSETS]}, index=ASSETS)
    ed = st.data_editor(base, disabled=["Asset"], width="stretch", key="weights_editor")
    st.subheader("Factor moves used")
    st.dataframe(pd.DataFrame({"Factor": [FLABEL[f] for f in FACTORS],
                               "Move to Sep-27": [round(df[f], 1) for f in FACTORS]}),
                 hide_index=True, width="stretch")
    st.caption(meta["estimation"])
    st.caption(meta.get("bonds", ""))

invest = (100 - cash) / 100
sp = ed["S&P 500 (equity sleeve)"].reindex(SECTORS).astype(float)
sp = sp / sp.sum()
cb = ed["Team current (fund)"].reindex(BONDS).astype(float)
cb = cb / cb.sum() if cb.sum() > 0 else pd.Series(1 / len(BONDS), BONDS)
eq_b = min(bench_eq / 100, invest)
wb = pd.concat([sp * eq_b, cb * (invest - eq_b)]).reindex(ASSETS)


def fund(col):
    s = ed[col].reindex(ASSETS).astype(float).fillna(0)
    return s / s.sum() * invest


cur, prop = fund("Team current (fund)"), fund("Team proposed (fund)")
Sig, pi, mu, shock, vsd, conf = black_litterman(B, B26, V, Om, D, grid, meta, wb, df, delta, tau, use_scen, use_drift)
w, ok = optimize(mu, Sig, wb, delta, te, sec_band, bond_band, eq_rng[0] / 100, eq_rng[1] / 100, floor)
te_of = lambda x: 100 * float(np.sqrt((x - wb) @ Sig.values @ (x - wb)))
exp_of = lambda x: 100 * float((x - wb) @ (mu - pi))
eqs = lambda x: 100 * float(x[SECTORS].sum())
dur = pd.Series({"UST2": 1.9, "UST5": 4.6, "UST10": 8.5, "TIPS10": 8.7})
dur_of = lambda x: float((x[BONDS] * dur).sum() / max(x[BONDS].sum(), 1e-9))

with tab_w:
    if not ok:
        st.warning("The optimizer did not fully converge; loosen the limits.")
    c = st.columns(5)
    c[0].metric("Expected vs benchmark (model)", f"{exp_of(w):+.2f}%")
    c[1].metric("Tracking error (model)", f"{te_of(w):.2f}%")
    c[2].metric("Equity share (model)", f"{eqs(w):.1f}%")
    c[3].metric("Bond duration (model)", f"{dur_of(w):.1f} yrs", f"{dur_of(w) - dur_of(wb):+.1f} vs benchmark",
                delta_color="off")
    c[4].metric("Expected vs benchmark (team proposed)", f"{exp_of(prop):+.2f}%")

    tbl = pd.DataFrame({"Asset": [NAMES[a] for a in ASSETS], "Benchmark": 100 * wb, "Model": 100 * w,
                        "Model vs benchmark (pp)": 100 * (w - wb), "Team current": 100 * cur,
                        "Team proposed": 100 * prop}, index=ASSETS)
    order = list(tbl.loc[SECTORS].sort_values("Model vs benchmark (pp)", ascending=False).Asset) + \
        [NAMES[b] for b in BONDS]
    long = tbl.melt(id_vars="Asset", value_vars=["Model", "Team proposed", "Team current"],
                    var_name="Portfolio", value_name="w")
    long["Over/underweight vs benchmark (pp of fund)"] = long.w - long.Asset.map(dict(zip(tbl.Asset, tbl.Benchmark)))
    enc = dict(yOffset=alt.YOffset("Portfolio:N", sort=["Model", "Team proposed", "Team current"]),
               color=alt.Color("Portfolio:N", sort=["Model", "Team proposed", "Team current"],
                               scale=alt.Scale(range=[GREEN, BLUE, GREY]), legend=alt.Legend(orient="bottom")))
    st.subheader("Over/underweight vs benchmark")
    st.altair_chart(alt.Chart(long).mark_bar().encode(
        y=alt.Y("Asset:N", sort=order, title=None), x=alt.X("Over/underweight vs benchmark (pp of fund):Q"),
        tooltip=["Asset", "Portfolio", alt.Tooltip("Over/underweight vs benchmark (pp of fund):Q", format="+.1f")],
        **enc).properties(height=600), width="stretch")
    tbl = tbl.set_index("Asset").loc[order].reset_index()
    tot = pd.DataFrame([{"Asset": "Total equity", **{k: tbl.iloc[:11][k].sum() for k in tbl.columns[1:]}},
                        {"Asset": "Total bonds", **{k: tbl.iloc[11:][k].sum() for k in tbl.columns[1:]}},
                        {"Asset": "Cash", **{k: (cash if k != "Model vs benchmark (pp)" else 0.0) for k in tbl.columns[1:]}}])
    full = pd.concat([tbl, tot], ignore_index=True)
    st.dataframe(full.round(2), hide_index=True, width="stretch")
    st.download_button("Download weights (CSV)", full.round(3).to_csv(index=False), "portfolio_weights.csv")

    st.subheader("Stress tests: return vs benchmark from macro moves")
    scen = {f"${b} {r.lower()}": factor_moves(grid, meta, b, r)
            for b in (75, 90, 105, 115) for r in ("Core", "Hawkish")}
    scen["Shock: real +50bp, Fed +75bp"] = dict(oil=0, real=50, ff12=75, be=0, term=-25, hy=25, usd=0, epu=0)
    scen["Shock: oil to $140"] = dict(oil=100 * np.log(140 / meta["origin"]["brent"]), real=10, ff12=30,
                                      be=15, term=-5, hy=30, usd=0, epu=0)
    scen["Shock: growth scare (stocks down, yields down)"] = dict(oil=-20, real=-40, ff12=-100, be=-25,
                                                                 term=40, hy=150, usd=0, epu=0)
    rows = []
    for k, v in scen.items():
        r = B.values @ np.array([v[f] for f in FACTORS]) / 100
        rows.append({"Scenario": k, **{n: 100 * float((x - wb) @ r) for n, x in
                                      [("Model", w), ("Team proposed", prop), ("Team current", cur)]}})
    stt = pd.DataFrame(rows)
    sl = stt.melt(id_vars="Scenario", var_name="Portfolio", value_name="Return vs benchmark (%)")
    st.altair_chart(alt.Chart(sl).mark_bar().encode(
        y=alt.Y("Scenario:N", sort=list(stt.Scenario), title=None), x=alt.X("Return vs benchmark (%):Q"),
        tooltip=["Scenario", "Portfolio", alt.Tooltip("Return vs benchmark (%):Q", format="+.2f")],
        **enc).properties(height=460), width="stretch")
    st.caption("Macro moves only: sector-specific news (earnings, AI) and bond carry differences are not included.")

    st.subheader("Views and confidence")
    st.dataframe(pd.DataFrame({
        "Asset": [NAMES[a] for a in ASSETS],
        "Equilibrium return (%)": 100 * pi, "Macro view (%)": 100 * shock,
        "View uncertainty, sd (%)": 100 * vsd, "Weight on view (0-1)": conf,
        "Posterior return (%)": 100 * mu}).round(2), hide_index=True, width="stretch")
    with st.expander("How this works"):
        st.markdown(
            "- **Benchmark (prior):** S&P 500 sector weights for the equity share, the fund's current bond mix "
            "for the rest, cash fixed. It implies equilibrium returns, pi = delta x Sigma x w.\n"
            "- **Risk (Sigma):** factor model, B x factor covariance x B' + each asset's own variance, from "
            "daily data Jan 2022 - Oct 2026. Bond buckets are built from Treasury and TIPS yields, so stock-bond "
            "correlation comes through the shared rate factors.\n"
            "- **Views:** each asset's factor betas x the factor moves the inflation model gives for the "
            "chosen oil price and Fed rule. For bonds that is mostly duration x the yield change.\n"
            "- **Confidence:** beta standard errors, the spread of each view across 8 oil/Fed scenarios, and "
            "2026 beta drift. Nothing is set by hand.\n"
            "- **Weights:** maximize expected return minus delta/2 x variance within the tracking-error budget, "
            "per-asset bands and the allowed equity range, long only.")
