"""Streamlit viewer for the oil-inflation model. Reads the precomputed files in outputs/tables.

    streamlit run app.py
Re-run `python -m oilinfl` first if you change config.yaml or the data.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

T = Path(__file__).parent / "outputs" / "tables"
F = Path(__file__).parent / "outputs" / "figures"
LAB = {"headline_cpi": "Headline CPI", "core_cpi": "Core CPI", "headline_pce": "Headline PCE", "core_pce": "Core PCE",
       "energy_pce": "PCE energy", "gasoline_pce": "PCE gasoline", "transport_pce": "PCE transportation services"}
SC = {"flat_114": "Brent flat $114", "flat_105": "Brent flat $105", "up20_nov": "+20% in Nov", "up20_apr": "+20% in Apr",
      "down25_nov": "-25% in Nov", "down25_apr": "-25% in Apr", "up_down_up": "Up-down-up", "higher_longer": "$125 from Nov",
      "normalize_75": "Glide to $75"}

st.set_page_config(page_title="Oil → inflation model", layout="wide")
st.title("Oil shock → inflation → real yields")
st.caption("Top Down Fund. Data through Sep 2026. Research tool, not investment advice.")


@st.cache_data
def load(name):
    return pd.read_csv(T / name)


hist, yoy, mom, summ, rates = (load("history.csv"), load("scenarios_yoy_wide.csv"), load("scenarios_mom_wide.csv"),
                               load("scenario_summary.csv"), load("rates_scenarios.csv"))
hist["date"] = pd.to_datetime(hist["date"])

tab1, tab2, tab3, tab4 = st.tabs(["Scenarios", "Rates and XLK", "Robustness", "Charts"])

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
    st.write("Path of breakevens, the 2-year yield, the 10-year real yield and implied XLK move under each scenario "
             "(core-PCE Fed rule, and a hawkish headline rule).")
    s2 = st.selectbox("Scenario", list(SC), index=1, format_func=SC.get, key="rs")
    r = rates[rates.scenario == s2].copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r.set_index("date")
    a, b = st.columns(2)
    a.line_chart(r[["T5YIEM", "T10YIEM"]].rename(columns={"T5YIEM": "5y breakeven", "T10YIEM": "10y breakeven"}))
    b.line_chart(r[["FII10", "FII10_hawk"]].rename(columns={"FII10": "10y real (core rule)", "FII10_hawk": "10y real (hawkish)"}))
    end = rates[rates.date == rates.date.max()].copy()
    end["Scenario"] = end.scenario.map(SC)
    end = end.set_index("Scenario")[["GS2", "FII10", "XLK_implied_pct", "GS2_hawk", "FII10_hawk", "XLK_implied_pct_hawk"]]
    end.columns = ["2y (core rule)", "10y real (core)", "XLK % (core)", "2y (hawkish)", "10y real (hawkish)", "XLK % (hawkish)"]
    st.dataframe(end.round(2), width="stretch")

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
