"""Top Down fund: Black-Litterman sector weights from the macro factor model.

Page of the main app (streamlit run app.py -> sidebar "Portfolio weights")
Inputs:        bl_inputs/ (betas, covariances, oil grid), produced from the
               daily macro factor model (2022-2025) and the inflation model.
"""
import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.optimize import minimize

st.set_page_config(page_title="Top Down sector weights", layout="wide")
IN = next(p for p in (Path(__file__).parent / "bl_inputs", Path(__file__).parent.parent / "bl_inputs", Path(__file__).parent.parent) if (p / "meta.json").exists())
SECTORS = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]
NAMES = {"XLK": "Technology", "XLF": "Financials", "XLV": "Health care",
         "XLY": "Consumer discretionary", "XLC": "Communication services",
         "XLI": "Industrials", "XLP": "Consumer staples", "XLE": "Energy",
         "XLU": "Utilities", "XLRE": "Real estate", "XLB": "Materials"}
FACTORS = ["oil", "real", "ff12", "be", "term", "hy", "usd", "epu"]
FLABEL = {"oil": "Oil (%)", "real": "Real yield (bp)", "ff12": "Fed expectations (bp)",
          "be": "Breakeven (bp)", "term": "10y-2y spread (bp)", "hy": "HY spread (bp)",
          "usd": "Dollar (%)", "epu": "Policy uncertainty (x100 log)"}

# Default weights, % of the equity sleeve
SP500 = {"XLK": 35.718619, "XLF": 12.728703, "XLV": 10.573163, "XLY": 9.465788,
         "XLC": 8.772470, "XLI": 8.128071, "XLP": 5.233176, "XLE": 3.590483,
         "XLU": 2.122525, "XLRE": 1.887814, "XLB": 1.779186}
CURRENT = {"XLK": 16.47, "XLF": 6.12, "XLV": 6.59, "XLY": 3.70, "XLC": 4.48, "XLI": 3.24,
           "XLP": 6.08, "XLE": 4.99, "XLU": 1.42, "XLRE": 1.14, "XLB": 3.70}
PROPOSED = {"XLK": 24.0, "XLF": 5.37, "XLV": 7.13, "XLY": 5.00, "XLC": 5.50, "XLI": 5.71,
            "XLP": 2.03, "XLE": 2.50, "XLU": 2.23, "XLRE": 2.50, "XLB": 1.03}


# ---------------------------------------------------------------- data
@st.cache_data
def load():
    B = pd.read_csv(IN / "betas_2022_2025.csv", index_col=0).loc[SECTORS, FACTORS]
    B26 = pd.read_csv(IN / "betas_2026.csv", index_col=0).loc[SECTORS, FACTORS]
    bc = pd.read_csv(IN / "beta_covariances.csv")
    V = {s: g.set_index("factor").loc[FACTORS, FACTORS].values for s, g in bc.groupby("sector")}
    Om = pd.read_csv(IN / "factor_covariance_daily.csv", index_col=0).loc[FACTORS, FACTORS]
    D = pd.read_csv(IN / "residual_variance_daily.csv", index_col=0).iloc[:, 0].loc[SECTORS]
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


def norm(d):
    s = pd.Series(d, dtype=float).reindex(SECTORS).fillna(0)
    return s / s.sum()


def black_litterman(B, B26, V, Om, D, grid, meta, wb, df, delta, tau, use_scen, use_drift):
    Bv = B.values
    Sig = (Bv @ Om.values @ Bv.T + np.diag(D.values)) * 252 / 1e4      # annual, decimals
    pi = delta * Sig @ wb.values
    dfv = np.array([df[f] for f in FACTORS])
    shock = Bv @ dfv / 100
    var = np.array([dfv @ V[s] @ dfv for s in SECTORS]) / 1e4          # beta standard errors
    if use_scen:                                                        # spread across oil/Fed scenarios
        pts = [factor_moves(grid, meta, b, r) for b in (75, 90, 105, 115) for r in ("Core", "Hawkish")]
        G = np.array([[p[f] for f in FACTORS] for p in pts])
        var = var + np.var(G @ Bv.T / 100, axis=0)
    if use_drift:                                                       # 2026 vs 2022-25 beta drift
        var = var + ((B26.values - Bv) @ dfv / 100) ** 2
    Omg = np.diag(np.maximum(var, 1e-10))
    tS = tau * Sig
    iT, iO = np.linalg.inv(tS), np.linalg.inv(Omg)
    mu = np.linalg.solve(iT + iO, iT @ pi + iO @ (pi + shock))
    conf = np.diag(tS) / (np.diag(tS) + np.diag(Omg))
    return pd.DataFrame(Sig, SECTORS, SECTORS), pi, mu, shock, np.sqrt(np.diag(Omg)), conf


def optimize(mu, Sig, wb, delta, te, band, floor):
    S_, w0 = Sig.values, wb.values
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1},
            {"type": "ineq", "fun": lambda w: te ** 2 - (w - w0) @ S_ @ (w - w0)}]
    bnds = [(min(max(floor, x - band), x), x + band) for x in w0]
    r = minimize(lambda w: -(w @ mu - delta / 2 * w @ S_ @ w), w0, bounds=bnds,
                 constraints=cons, method="SLSQP", options={"ftol": 1e-12, "maxiter": 1000})
    return pd.Series(r.x, SECTORS), r.success


# ---------------------------------------------------------------- UI
B, B26, V, Om, D, grid, meta = load()
st.title("Top Down fund: sector weights from the macro model")
st.caption("Black-Litterman: start at S&P 500 sector weights, tilt toward what the inflation model's "
           "rate and oil path implies, sized by how confident the data lets us be.")

with st.sidebar:
    st.header("Scenario (to Sep-27)")
    brent = st.select_slider("Brent held flat at ($)", options=list(grid.index), value=105)
    rule = st.radio("Fed reaction", ["Core", "Hawkish"], horizontal=True,
                    help="Core: Fed reacts to core PCE. Hawkish: Fed reacts to headline PCE.")
    df = factor_moves(grid, meta, brent, rule)
    if st.toggle("Override factor moves"):
        for f in FACTORS:
            df[f] = st.number_input(FLABEL[f], value=float(round(df[f], 1)), step=5.0, key=f"ov_{f}")
    st.header("Risk limits")
    te = st.slider("Tracking error budget vs S&P (%)", 0.5, 6.0, 3.0, 0.5) / 100
    band = st.slider("Max over/underweight per sector (pp)", 1, 15, 5) / 100
    floor = st.slider("Minimum weight per sector (%)", 0.0, 3.0, 0.0, 0.5) / 100
    sleeve = st.number_input("Equity share of the fund (%)", 0.0, 100.0, 63.0, 1.0)
    with st.expander("Model settings"):
        delta = st.number_input("Risk aversion (delta)", 0.5, 10.0, 2.5, 0.5)
        tau = st.number_input("Prior uncertainty (tau)", 0.01, 1.0, 0.05, 0.01)
        use_scen = st.checkbox("Count scenario spread as view uncertainty", True)
        use_drift = st.checkbox("Count 2026 beta drift as view uncertainty", True)

tab_w, tab_in = st.tabs(["Weights", "Inputs and weights to compare"])
with tab_in:
    st.write("Edit any column (% of the equity sleeve; each is rescaled to 100).")
    base_tbl = pd.DataFrame({"Sector": [NAMES[s] for s in SECTORS],
                             "S&P 500": [SP500[s] for s in SECTORS],
                             "Team current": [CURRENT[s] for s in SECTORS],
                             "Team proposed": [PROPOSED[s] for s in SECTORS]}, index=SECTORS)
    ed = st.data_editor(base_tbl, disabled=["Sector"], width="stretch", key="weights_editor")
    st.subheader("Factor moves used")
    st.dataframe(pd.DataFrame({"Factor": [FLABEL[f] for f in FACTORS],
                               "Move to Sep-27": [round(df[f], 1) for f in FACTORS]}),
                 hide_index=True, width="stretch")
    st.caption(meta["estimation"])

wb, cur, prop = norm(ed["S&P 500"]), norm(ed["Team current"]), norm(ed["Team proposed"])
Sig, pi, mu, shock, vsd, conf = black_litterman(B, B26, V, Om, D, grid, meta, wb, df, delta, tau, use_scen, use_drift)
w, ok = optimize(mu, Sig, wb, delta, te, band, floor)
te_of = lambda x: 100 * float(np.sqrt((x - wb) @ Sig.values @ (x - wb)))
exp_of = lambda x: 100 * float((x - wb) @ (mu - pi))

with tab_w:
    if not ok:
        st.warning("The optimizer did not fully converge; loosen the limits.")
    c = st.columns(4)
    c[0].metric("Expected return vs S&P (model)", f"{exp_of(w):+.2f}%")
    c[1].metric("Tracking error (model)", f"{te_of(w):.2f}%")
    c[2].metric("Expected vs S&P (team proposed)", f"{exp_of(prop):+.2f}%")
    c[3].metric("Tracking error (team proposed)", f"{te_of(prop):.2f}%")

    tbl = pd.DataFrame({"Sector": [NAMES[s] for s in SECTORS], "S&P 500": 100 * wb,
                        "Model": 100 * w, "Model vs S&P (pp)": 100 * (w - wb),
                        f"Model, fund weight at {sleeve:.0f}% equity": w * sleeve,
                        "Team current": 100 * cur, "Team proposed": 100 * prop},
                       index=SECTORS).sort_values("Model vs S&P (pp)", ascending=False)

    long = tbl.melt(id_vars="Sector", value_vars=["Model", "Team proposed", "Team current"],
                    var_name="Portfolio", value_name="w")
    long["Over/underweight vs S&P (pp)"] = long.w - long.Sector.map(dict(zip(tbl.Sector, tbl["S&P 500"])))
    chart = alt.Chart(long).mark_bar().encode(
        y=alt.Y("Sector:N", sort=list(tbl.Sector), title=None),
        x=alt.X("Over/underweight vs S&P (pp):Q"),
        yOffset=alt.YOffset("Portfolio:N", sort=["Model", "Team proposed", "Team current"]),
        color=alt.Color("Portfolio:N", sort=["Model", "Team proposed", "Team current"],
                        scale=alt.Scale(range=["#27532a", "#4b7bb5", "#b5b5b5"]),
                        legend=alt.Legend(orient="bottom")),
        tooltip=["Sector", "Portfolio", alt.Tooltip("Over/underweight vs S&P (pp):Q", format="+.1f")],
    ).properties(height=480)
    st.subheader("Over/underweight vs S&P 500")
    st.altair_chart(chart, width="stretch")
    st.dataframe(tbl.round(2), hide_index=True, width="stretch")
    st.download_button("Download weights (CSV)", tbl.round(3).to_csv(index=False), "sector_weights.csv")

    st.subheader("Stress tests: return vs S&P from macro moves")
    scen = {f"${b} {r.lower()}": factor_moves(grid, meta, b, r)
            for b in (75, 90, 105, 115) for r in ("Core", "Hawkish")}
    scen["Shock: real +50bp, Fed +75bp"] = dict(oil=0, real=50, ff12=75, be=0, term=-25, hy=25, usd=0, epu=0)
    scen["Shock: oil to $140"] = dict(oil=100 * np.log(140 / meta["origin"]["brent"]), real=10, ff12=30,
                                      be=15, term=-5, hy=30, usd=0, epu=0)
    rows = []
    for k, v in scen.items():
        r = B.values @ np.array([v[f] for f in FACTORS]) / 100
        rows.append({"Scenario": k, **{n: 100 * float((x - wb) @ r) for n, x in
                                      [("Model", w), ("Team proposed", prop), ("Team current", cur)]}})
    stt = pd.DataFrame(rows)
    sl = stt.melt(id_vars="Scenario", var_name="Portfolio", value_name="Return vs S&P (%)")
    st.altair_chart(alt.Chart(sl).mark_bar().encode(
        y=alt.Y("Scenario:N", sort=list(stt.Scenario), title=None),
        x=alt.X("Return vs S&P (%):Q"),
        yOffset=alt.YOffset("Portfolio:N", sort=["Model", "Team proposed", "Team current"]),
        color=alt.Color("Portfolio:N", sort=["Model", "Team proposed", "Team current"],
                        scale=alt.Scale(range=["#27532a", "#4b7bb5", "#b5b5b5"]),
                        legend=alt.Legend(orient="bottom")),
        tooltip=["Scenario", "Portfolio", alt.Tooltip("Return vs S&P (%):Q", format="+.2f")],
    ).properties(height=420), width="stretch")
    st.caption("Macro moves only: sector-specific news (earnings, AI) is not included.")

    st.subheader("Views and confidence")
    st.dataframe(pd.DataFrame({
        "Sector": [NAMES[s] for s in SECTORS],
        "Equilibrium return (%)": 100 * pi, "Macro view (%)": 100 * shock,
        "View uncertainty, sd (%)": 100 * vsd, "Weight on view (0-1)": conf,
        "Posterior return (%)": 100 * mu}).round(2), hide_index=True, width="stretch")
    with st.expander("How this works"):
        st.markdown(
            "- **Prior:** the S&P 500 sector weights imply equilibrium returns, pi = delta x Sigma x w.\n"
            "- **Risk (Sigma):** factor model, B x factor covariance x B' + each sector's own variance, "
            "from daily 2022-25 data.\n"
            "- **Views:** each sector's macro betas x the factor moves the inflation model gives for the "
            "chosen oil price and Fed rule.\n"
            "- **Confidence:** from the betas' standard errors, the spread of the view across 8 oil/Fed "
            "scenarios, and how far 2026 betas drifted from 2022-25. Nothing is set by hand.\n"
            "- **Weights:** maximize expected return minus delta/2 x variance, within the tracking-error "
            "budget, the per-sector band and the minimum weight, long only.")
