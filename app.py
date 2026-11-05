"""Streamlit viewer for the oil-inflation model. Reads the precomputed files in outputs/tables.

    streamlit run app.py
Re-run `python -m oilinfl` first if you change config.yaml or the data.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

T = Path(__file__).parent / "outputs" / "tables"
F = Path(__file__).parent / "outputs" / "figures"
LAB = {"headline_cpi": "Headline CPI", "core_cpi": "Core CPI", "headline_pce": "Headline PCE", "core_pce": "Core PCE",
       "energy_pce": "PCE energy", "gasoline_pce": "PCE gasoline", "transport_pce": "PCE transportation services"}
SC = {"flat_114": "Brent flat $114", "flat_105": "Brent flat $105", "up20_nov": "+20% in Nov", "up20_apr": "+20% in Apr",
      "down25_nov": "-25% in Nov", "down25_apr": "-25% in Apr", "up_down_up": "Up-down-up", "higher_longer": "$125 from Nov",
      "normalize_75": "Glide to $75"}

SEC = {"XLK": "Technology", "XLY": "Consumer discretionary", "XLP": "Consumer staples", "XLE": "Energy",
       "XLF": "Financials", "XLV": "Health care", "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
       "XLRE": "Real estate", "XLC": "Communication services"}
def sector_bars(d, order, xtitle):
    bars = (alt.Chart(d).mark_bar().encode(
        y=alt.Y("Sector:N", sort=order, title=None),
        x=alt.X("effect:Q", title=xtitle),
        color=alt.condition(alt.datum.effect > 0, alt.value("#2a9d8f"), alt.value("#e76f51")),
        tooltip=["Sector:N", alt.Tooltip("effect:Q", format=".2f"), alt.Tooltip("p:Q", format=".3f")]))
    err = alt.Chart(d).mark_rule(color="#888").encode(y=alt.Y("Sector:N", sort=order), x="lo:Q", x2="hi:Q")
    return (bars + err).properties(height=340)


st.set_page_config(page_title="Oil → inflation model", layout="wide")
st.title("Oil shock → inflation → real yields")
st.caption("Top Down Fund. Data through Sep 2026. Research tool, not investment advice.")


@st.cache_data
def load(name):
    return pd.read_csv(T / name)


hist, yoy, mom, summ, rates = (load("history.csv"), load("scenarios_yoy_wide.csv"), load("scenarios_mom_wide.csv"),
                               load("scenario_summary.csv"), load("rates_scenarios.csv"))
hist["date"] = pd.to_datetime(hist["date"])

tab1, tab2, tab5, tab3, tab4 = st.tabs(["Scenarios", "Rates and XLK", "Oil calculator", "Robustness", "Charts"])

with tab1:
    c1, c2, c3 = st.columns(3)
    series = c1.selectbox("Series", list(LAB), format_func=LAB.get)
    scen = c2.multiselect("Scenarios", list(SC), default=["flat_105", "up20_nov", "down25_nov"], format_func=SC.get)
    measure = c3.radio("Measure", ["YoY %", "MoM %"], horizontal=True)
    h = hist[hist.target == series].set_index("date")["yoy" if measure == "YoY %" else "mom_pct"]
    wide = yoy if measure == "YoY %" else mom
    out = pd.DataFrame({"History": h})
    for s in scen:
        r = wide[(wide.target == series) & (wide.scenario == s)].drop(columns=["target", "scenario"]).iloc[0]
        r.index = pd.to_datetime(r.index + "-01")
        out = out.join(pd.Series(r.values, index=r.index, name=SC[s]), how="outer")
    st.line_chart(out)
    st.subheader("Sep-27 summary")
    d = summ[summ.target == series].copy()
    d["Scenario"] = d.scenario.map(SC)
    d = d.set_index("Scenario")[["yoy_dec26", "yoy_mar27", "yoy_sep27", "yoy_sep27_lo", "yoy_sep27_hi", "avg_mom_6m"]]
    d.columns = ["Dec-26 YoY", "Mar-27 YoY", "Sep-27 YoY", "10th pct", "90th pct", "Avg MoM, 6m"]
    st.dataframe(d.round(2), width="stretch")

with tab2:
    rh = load("rates_history.csv")
    rh["date"] = pd.to_datetime(rh["date"])
    rh = rh.set_index("date")
    st.write("Actual history, then the model path for the scenario you pick (core-PCE Fed rule, and a hawkish "
             "headline rule). Axes are zoomed to the data.")
    c1, c2 = st.columns([2, 1])
    s2 = c1.selectbox("Scenario", list(SC), index=1, format_func=SC.get, key="rs")
    since = c2.slider("History from", 2016, 2026, 2022, key="since")
    r = rates[rates.scenario == s2].copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date")
    h = rh.loc[f"{since}-01":]

    def zoom_chart(title, hist_cols, scen_cols, ylabel):
        """hist_cols: {label: column in history}, scen_cols: {label: column in scenario path}."""
        rows = []
        for lab, col in hist_cols.items():
            rows += [dict(date=d, value=v, series=lab, part="Actual") for d, v in h[col].dropna().items()]
        for lab, col in scen_cols.items():
            rows += [dict(date=d, value=v, series=lab, part="Model path") for d, v in r[col].items()]
        df = pd.DataFrame(rows)
        lo, hi = df.value.min(), df.value.max()
        pad = max((hi - lo) * 0.08, 0.05)
        ch = (alt.Chart(df, title=title).mark_line(strokeWidth=2.2)
              .encode(x=alt.X("date:T", title=None),
                      y=alt.Y("value:Q", title=ylabel, scale=alt.Scale(domain=[lo - pad, hi + pad], zero=False)),
                      color=alt.Color("series:N", title=None),
                      strokeDash=alt.StrokeDash("part:N", title=None, scale=alt.Scale(domain=["Actual", "Model path"],
                                                                                    range=[[1, 0], [5, 4]])),
                      tooltip=["date:T", "series:N", alt.Tooltip("value:Q", format=".2f"), "part:N"]))
        return ch.properties(height=300)

    a, b = st.columns(2)
    a.altair_chart(zoom_chart("Breakevens (%)", {"10y breakeven": "T10YIEM", "5y breakeven": "T5YIEM"},
                              {"10y breakeven": "T10YIEM", "5y breakeven": "T5YIEM"}, "%"), width="stretch")
    b.altair_chart(zoom_chart("10-year real yield (%)", {"Actual 10y real": "FII10"},
                              {"Model: core rule": "FII10", "Model: hawkish rule": "FII10_hawk"}, "%"), width="stretch")
    st.altair_chart(zoom_chart("2-year Treasury yield (%)", {"Actual 2y": "GS2"},
                               {"Model: core rule": "GS2", "Model: hawkish rule": "GS2_hawk"}, "%"), width="stretch")

    end = rates[rates.date == rates.date.max()].copy()
    end["Scenario"] = end.scenario.map(SC)
    end = end.set_index("Scenario")[["GS2", "FII10", "XLK_implied_pct", "GS2_hawk", "FII10_hawk", "XLK_implied_pct_hawk"]]
    end.columns = ["2y (core rule)", "10y real (core)", "XLK % (core)", "2y (hawkish)", "10y real (hawkish)", "XLK % (hawkish)"]
    st.dataframe(end.round(2), width="stretch")

    st.divider()
    st.subheader("What a rise in real yields does to each sector")
    st.caption("Monthly sector return regressed on the change in the 10-year real yield, 2016-2025, Covid months out, "
               "HAC errors. Comovement, not causation: stocks and yields respond to the same news.")
    sb = load("sector_betas.csv")
    sb["Sector"] = sb.sector.map(SEC)
    k1, k2, k3 = st.columns([1.3, 1.3, 1.4])
    direction = k1.radio("Direction", ["Real yields fall", "Real yields rise"], horizontal=True)
    size = k2.slider("Size of move (bp)", 10, 150, 50, 10)
    ver = k3.radio("Return measure", ["Raw sector return", "Relative to the all-sector average"])
    sign = -1.0 if direction == "Real yields fall" else 1.0
    v = "raw" if ver.startswith("Raw") else "relative"
    d = sb[sb.version == v].copy()
    d["effect"] = d.beta_per_bp * sign * size
    d["se"] = d.se_per_bp * size
    d["lo"], d["hi"] = d.effect - 1.96 * d.se, d.effect + 1.96 * d.se
    order = d.sort_values("effect", ascending=False).Sector.tolist()
    st.altair_chart(sector_bars(d, order, f"% move if the 10y real yield {'falls' if sign < 0 else 'rises'} {size}bp"),
                    width="stretch")
    tbl = d.set_index("Sector")[["effect", "se", "p", "r2", "nobs", "sample"]]
    tbl.columns = ["% move", "Std. error", "p-value", "R2", "Months", "Sample"]
    st.dataframe(tbl.sort_values("% move", ascending=False).round(3), width="stretch")

    st.subheader("Implied sector moves in the selected scenario")
    si = load("sector_scenarios.csv")
    si = si[(si.scenario == s2) & (si.version == v)]
    pv = si.pivot(index="sector", columns="rule", values="implied_pct").rename(index=SEC)
    dr = si.groupby("rule").d_real_bp.first()
    st.caption(f"Model change in the 10y real yield by Sep-27: core rule {dr['core rule']:+.0f}bp, hawkish rule "
               f"{dr['hawkish']:+.0f}bp. Implied move = sector beta x that change; it ignores every other driver of stocks.")
    st.dataframe(pv.round(2).rename(columns={"core rule": "Core rule, %", "hawkish": "Hawkish rule, %"}), width="stretch")

with tab5:
    grid = load("oil_grid.csv").set_index("brent")
    gs = load("oil_grid_sectors.csv")
    R = json.loads((Path(__file__).parent / "outputs" / "results.json").read_text())
    org = R["rates_origin"]
    st.write("Pick a Brent price held flat from November. The model gives inflation, rates and the real yield for that "
             "price, then converts the real-yield change into sector moves. Brent was about $114 in September.")
    st.session_state.setdefault("brent", 105)
    q = st.columns([1, 1, 1, 4])
    for col, lvl in zip(q[:3], (115, 90, 75)):
        col.button(f"${lvl}", on_click=lambda l=lvl: st.session_state.update(brent=l), width="stretch")
    brent = st.slider("Brent ($/bbl), flat from November", int(grid.index.min()), int(grid.index.max()), step=5, key="brent")
    g = grid.loc[brent]
    st.subheader(f"Brent flat at ${brent}: Sep-27")
    m = st.columns(4)
    m[0].metric("Headline CPI YoY", f"{g.headline_cpi_yoy_sep27:.1f}%")
    m[1].metric("Core CPI YoY", f"{g.core_cpi_yoy_sep27:.1f}%")
    m[2].metric("Headline PCE YoY", f"{g.headline_pce_yoy_sep27:.1f}%")
    m[3].metric("Core PCE YoY", f"{g.core_pce_yoy_sep27:.1f}%")
    rule = st.radio("Fed reaction", ["core rule", "hawkish"], horizontal=True,
                    format_func=lambda s: "Fed follows core PCE (estimated)" if s == "core rule" else "Fed reacts to headline (hawkish)")
    fii = g.FII10 if rule == "core rule" else g.FII10_hawk
    gs2 = g.GS2 if rule == "core rule" else g.GS2_hawk
    n = st.columns(4)
    n[0].metric("10y real yield", f"{fii:.2f}%", f"{100 * (fii - org['FII10']):+.0f}bp vs Sep-26", delta_color="off")
    n[1].metric("2y yield", f"{gs2:.2f}%", f"{100 * (gs2 - org['GS2']):+.0f}bp vs Sep-26", delta_color="off")
    n[2].metric("10y breakeven", f"{g.T10YIEM:.2f}%", f"{100 * (g.T10YIEM - org['T10YIEM']):+.0f}bp vs Sep-26", delta_color="off")
    n[3].metric("5y breakeven", f"{g.T5YIEM:.2f}%", f"{100 * (g.T5YIEM - org['T5YIEM']):+.0f}bp vs Sep-26", delta_color="off")

    st.subheader("Implied sector moves from the real-yield change")
    ver2 = st.radio("Return measure ", ["Raw sector return", "Relative to the all-sector average"], horizontal=True, key="v2")
    v2 = "raw" if ver2.startswith("Raw") else "relative"
    d2 = gs[(gs.brent == brent) & (gs.rule == rule) & (gs.version == v2)].copy()
    d2["Sector"] = d2.sector.map(SEC)
    sbp = load("sector_betas.csv")
    pmap = sbp[sbp.version == v2].set_index("sector")["p"]
    d2["effect"] = d2.implied_pct
    d2["p"] = d2.sector.map(pmap)
    d2["lo"] = d2["hi"] = d2.effect
    order2 = d2.sort_values("effect", ascending=False).Sector.tolist()
    st.altair_chart(sector_bars(d2, order2, "implied % move through the real-yield channel only"), width="stretch")
    st.caption("Implied move = sector beta x the model's change in the 10y real yield (Sep-26 to Sep-27). It covers only "
               "the real-yield channel; earnings, growth and everything else are left out, and the betas explain 10-35% of "
               "monthly moves at best.")
    st.dataframe(grid.loc[[75, 90, 105, 115]][["headline_cpi_yoy_sep27", "core_cpi_yoy_sep27", "headline_pce_yoy_sep27",
                                                 "core_pce_yoy_sep27", "FII10", "FII10_hawk"]].round(2).rename(
        columns={"headline_cpi_yoy_sep27": "Headline CPI", "core_cpi_yoy_sep27": "Core CPI", "headline_pce_yoy_sep27": "Headline PCE",
                 "core_pce_yoy_sep27": "Core PCE", "FII10": "10y real (core rule)", "FII10_hawk": "10y real (hawkish)"}),
        width="stretch")

with tab3:
    st.subheader("Pass-through stability (long-run % per +10% Brent)")
    o = load("robust_other.csv")
    o["target"] = o.target.map(LAB)
    st.dataframe(o.round(3), width="stretch")
    st.subheader("Out-of-sample errors")
    st.dataframe(load("robust_oos.csv").round(3), width="stretch")
    st.subheader("2026 backtest")
    st.dataframe(load("backtest_2026.csv").round(2), width="stretch")

with tab4:
    for f in ["fan_yoy", "scenarios_pce", "scenarios_cpi", "mom_pce", "mom_cpi", "rates_chain", "xlk_channel", "oos_rmse"]:
        if (F / f"{f}.png").exists():
            st.image(str(F / f"{f}.png"), width="stretch")
