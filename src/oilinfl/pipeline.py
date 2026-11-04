"""End-to-end pipeline: data -> models -> scenarios -> rates -> robustness -> figures."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import diagnostics as dg
from . import plots
from . import robustness as rb
from .anchor import anchor_mu
from .data import annualized_from_logpct, brent_logchange, load, yoy_from_logpct
from .forecast import bootstrap_forecast, build_path, carry_path, point_forecast, recent_error
from .model import fit_ardl, months_to_share
from .rates import fit_rates, project

MODES = ("fades", "decay", "persists")
HEADLINE_KEYS = ["headline_cpi", "core_cpi", "headline_pce", "core_pce"]
KEY_SCENARIOS = ["flat_105", "higher_longer", "up_down_up", "normalize_75"]


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(config: str | Path = "config.yaml", root: str | Path = ".", skip_robustness: bool = False,
        fast: bool = False) -> dict:
    root = Path(root)
    cfg = load_config(root / config) if not isinstance(config, dict) else config
    out = root / cfg["output_dir"]
    tdir, fdir = out / "tables", out / "figures"
    tdir.mkdir(parents=True, exist_ok=True)
    fdir.mkdir(parents=True, exist_ok=True)
    est, fc = cfg["estimation"], cfg["forecast"]
    p, q, ex = est["p"], est["q"], est["exclude"]
    reps = 200 if fast else fc["bootstrap_reps"]
    results: dict = {"config": {"p": p, "q": q, "sample": [est["start"], est["end"]], "exclude": ex}}

    # ------------------------------------------------------------- data --
    _log("loading data")
    ds = load(cfg, root)
    x = brent_logchange(ds, cfg["driver"]["id"])
    origin = pd.Timestamp(fc["origin"])
    for k in cfg["targets"]:
        last = ds.inflation[k].last_valid_index()
        if last < origin:
            raise ValueError(f"{k} ends {last:%Y-%m}, before forecast origin {origin:%Y-%m}")
    results["filled_gaps"] = ds.filled
    brent0 = float(ds.levels[cfg["driver"]["id"]].loc[origin])
    results["brent_origin"] = brent0

    hist = pd.DataFrame({k: ds.inflation[k] for k in cfg["targets"]})
    hist_tab = []
    for k in cfg["targets"]:
        m = hist[k]
        hist_tab.append(pd.DataFrame({"target": k, "mom_pct": 100 * np.expm1(m / 100), "yoy": yoy_from_logpct(m),
                                      "saar3": annualized_from_logpct(m, 3), "saar6": annualized_from_logpct(m, 6)}))
    hist_tab = pd.concat(hist_tab).loc["2023-01":]
    hist_tab.round(3).to_csv(tdir / "history.csv", index_label="date")
    results["latest"] = {k: {"mom_pct": float(100 * np.expm1(hist[k].loc[origin] / 100)),
                             "yoy": float(yoy_from_logpct(hist[k]).loc[origin]),
                             "saar3": float(annualized_from_logpct(hist[k], 3).loc[origin])} for k in cfg["targets"]}

    # ----------------------------------------------------------- models --
    _log("estimating inflation models")
    models = {k: fit_ardl(hist[k], x, p, q, est["start"], est["end"], ex, est["hac_lags"]) for k in cfg["targets"]}
    mrows = []
    for k, m in models.items():
        lr, se = m.long_run()
        cum = m.irf(horizon=36)
        d = rb.residual_diagnostics(hist[k], x, p, q, est["start"], est["end"], ex)
        mrows.append(dict(target=k, label=ds.labels[k], nobs=m.nobs, sample=f"{m.sample[0]}..{m.sample[1]}",
                          r2=m.r2, r2_adj=m.r2_adj, ar_sum=m.ar_sum, lr10=lr, lr10_se=se, oil_wald_p=m.wald_driver(),
                          effect_12m=cum[11], months_to_50=months_to_share(cum, .5), months_to_90=months_to_share(cum, .9),
                          dw=d["dw"], bg12_p=d["bg12_p"], arch12_p=d["arch12_p"], jb_p=d["jb_p"], reset_p=d["reset_p"]))
        pd.DataFrame({"term": m.names, "coef": m.params, "se_hac": np.sqrt(np.diag(m.cov))}).to_csv(
            tdir / f"coefficients_{k}.csv", index=False)
    mtab = pd.DataFrame(mrows)
    mtab.round(4).to_csv(tdir / "model_summary.csv", index=False)
    results["models"] = mtab.set_index("target").round(4).to_dict(orient="index")

    # -------------------------------------------------------- scenarios --
    _log(f"running {len(cfg['scenarios'])} scenarios x {len(models)} series ({reps} bootstrap draws)")
    H = fc["horizon"]
    long_rows, fan = [], {}
    acfg = est.get("anchor", {"mode": "sample"})
    anchors = {k: anchor_mu(ds.levels, hist, acfg, k, origin) for k in models}
    results["anchors"] = anchors
    errors = {}
    for k, m in models.items():
        mean_err, err = recent_error(m, hist[k], x, origin, fc["residual_window"], anchors[k])
        errors[k] = mean_err
    results["recent_error_mean"] = errors
    for s, spec in cfg["scenarios"].items():
        path = build_path(brent0, origin, H, spec["steps"])
        fx = 100.0 * np.log(pd.concat([pd.Series([brent0], index=[origin]), path])).diff().iloc[1:]
        for k, m in models.items():
            for mode in MODES:
                carry = carry_path(errors[k], H, mode, fc["residual_halflife"])
                f = point_forecast(m, hist[k], x, fx, origin, carry, k, s, mode, anchors[k])
                df = pd.DataFrame({"scenario": s, "target": k, "mode": mode, "brent": path.values,
                                   "mom_pct": f.mom_pct()[0], "yoy": f.yoy()[0], "saar3": f.annualized(3)[0],
                                   "saar6": f.annualized(6)[0]}, index=f.dates)
                if mode == fc["residual_mode"]:
                    rng = np.random.default_rng(fc["seed"] + list(models).index(k))   # common random numbers
                    b = bootstrap_forecast(m, hist[k], x, fx, origin, carry, reps, fc["block_length"], rng, k, s, mode,
                                           anchors[k])
                    lo, hi = fc["bands"]
                    yy, mm = b.yoy(), b.mom_pct()
                    df["yoy_lo"], df["yoy_hi"] = np.percentile(yy, lo, axis=0), np.percentile(yy, hi, axis=0)
                    df["mom_lo"], df["mom_hi"] = np.percentile(mm, lo, axis=0), np.percentile(mm, hi, axis=0)
                    df["p_yoy_below_prev"] = (yy[:, -1] < yoy_from_logpct(hist[k]).loc[origin]).mean()
                long_rows.append(df)
    scen = pd.concat(long_rows)
    scen.round(4).to_csv(tdir / "scenarios_long.csv", index_label="date")
    central = scen[scen["mode"] == fc["residual_mode"]]
    piv = central.pivot_table(index=["target", "scenario"], columns=central.index.strftime("%Y-%m"), values="yoy")
    piv.round(2).to_csv(tdir / "scenarios_yoy_wide.csv")
    pivm = central.pivot_table(index=["target", "scenario"], columns=central.index.strftime("%Y-%m"), values="mom_pct")
    pivm.round(3).to_csv(tdir / "scenarios_mom_wide.csv")
    end_m, mid_m = central.index.max(), central.index.min() + pd.DateOffset(months=5)
    summ = []
    for (k, s), g in central.groupby(["target", "scenario"]):
        sens = scen[(scen.target == k) & (scen.scenario == s)]
        summ.append(dict(target=k, scenario=s, yoy_dec26=g.loc["2026-12-01", "yoy"], yoy_mar27=g.loc[mid_m, "yoy"],
                         yoy_sep27=g.loc[end_m, "yoy"], yoy_sep27_lo=g.loc[end_m, "yoy_lo"], yoy_sep27_hi=g.loc[end_m, "yoy_hi"],
                         yoy_peak=g["yoy"].max(), avg_mom_6m=g["mom_pct"].iloc[:6].mean(), avg_mom_12m=g["mom_pct"].mean(),
                         yoy_sep27_fades=sens[(sens["mode"] == "fades")].loc[end_m, "yoy"],
                         yoy_sep27_persists=sens[(sens["mode"] == "persists")].loc[end_m, "yoy"]))
    summ = pd.DataFrame(summ)
    summ.round(3).to_csv(tdir / "scenario_summary.csv", index=False)
    results["scenario_summary"] = {f"{r.target}|{r.scenario}": {c: round(float(getattr(r, c)), 3) for c in summ.columns[2:]}
                                   for r in summ.itertuples()}

    # ------------------------------------------------- rates & equities --
    _log("estimating expectations / rates / equity links")
    core_yoy = yoy_from_logpct(hist["core_pce"])
    head_yoy = yoy_from_logpct(hist["headline_pce"])
    rm = fit_rates(ds.levels, core_yoy, x, ds.xlk_daily, cfg, headline_yoy=head_yoy)
    rrows = []
    for sid, m in rm.breakeven.items():
        lr, se = m.long_run()
        rrows.append(dict(link=f"Breakeven {sid}", coef="long-run pp per +10% Brent", value=lr, se=se,
                          r2=m.r2, nobs=m.nobs, sample=f"{m.sample[0]}..{m.sample[1]}"))
    for lf, terms in ((rm.reaction, ["lag", "core_yoy", "unrate"]), (rm.reaction_headline, ["lag", "core_yoy", "unrate"]),
                      (rm.reaction_changes, ["d_core_yoy", "d_unrate"]),
                      (rm.passthrough, ["d_gs2", "d_be10"]),
                      (rm.equity, ["d_real_bp"]), (rm.equity_full, ["d_real_bp"])):
        if lf is None:
            continue
        for t in terms:
            rrows.append(dict(link=lf.name, coef=t, value=float(lf.params[t]), se=float(lf.bse[t]), r2=lf.r2,
                              nobs=lf.nobs, sample=f"{lf.sample[0]}..{lf.sample[1]}", p=float(lf.pvalues[t])))
    rho = float(rm.reaction.params["lag"])
    rrows.append(dict(link="reaction", coef="long-run core_yoy (b/(1-rho))", value=float(rm.reaction.params["core_yoy"]) / (1 - rho),
                      se=np.nan, r2=rm.reaction.r2, nobs=rm.reaction.nobs, sample=f"{rm.reaction.sample[0]}..{rm.reaction.sample[1]}"))
    rho_h = float(rm.reaction_headline.params["lag"])
    rrows.append(dict(link="reaction_headline", coef="long-run headline_yoy (b/(1-rho))",
                      value=float(rm.reaction_headline.params["core_yoy"]) / (1 - rho_h), se=np.nan, r2=rm.reaction_headline.r2,
                      nobs=rm.reaction_headline.nobs, sample=f"{rm.reaction_headline.sample[0]}..{rm.reaction_headline.sample[1]}"))
    rtab = pd.DataFrame(rrows)
    rtab.round(4).to_csv(tdir / "rates_models.csv", index=False)
    results["rates_models"] = rtab.round(4).to_dict(orient="records")
    lv = ds.levels
    origin_rates = {c: float(lv[c].loc[origin]) for c in ["T5YIEM", "T10YIEM", "GS2", "FII10", "FII5", "FEDFUNDS"]}
    latest_rates = {c: (lv[c].last_valid_index().strftime("%Y-%m"), float(lv[c].dropna().iloc[-1]))
                    for c in ["T5YIEM", "T10YIEM", "GS2", "FII10", "FII5", "FEDFUNDS"]}
    results["rates_origin"], results["rates_latest"] = origin_rates, latest_rates
    proj_rows, proj = [], {}
    core_origin = float(core_yoy.loc[origin])
    for s, spec in cfg["scenarios"].items():
        path = build_path(brent0, origin, H, spec["steps"])
        fx = 100.0 * np.log(pd.concat([pd.Series([brent0], index=[origin]), path])).diff().iloc[1:]
        cpath = central[(central.target == "core_pce") & (central.scenario == s)]["yoy"].values
        hpath = central[(central.target == "headline_pce") & (central.scenario == s)]["yoy"].values
        pr = project(rm, lv, origin, x, fx, cpath, core_origin, cfg, hpath, float(head_yoy.loc[origin]))
        pr.insert(0, "scenario", s)
        proj[s] = pr
        proj_rows.append(pr)
    ptab = pd.concat(proj_rows)
    ptab.round(4).to_csv(tdir / "rates_scenarios.csv", index_label="date")
    results["rates_scenarios"] = {s: {c: round(float(df[c].iloc[-1]), 3) for c in df.columns if c != "scenario"}
                                  for s, df in proj.items()}
    results["rates_scenarios_mid"] = {s: {c: round(float(df[c].iloc[5]), 3) for c in df.columns if c != "scenario"}
                                      for s, df in proj.items()}

    # ------------------------------------------------- supporting work --
    _log("supporting diagnostics (refined fuels, transportation, timing)")
    fv = dg.fuel_variants(hist, lv, ["headline_pce", "core_pce", "energy_pce", "transport_pce"], p, q, ex)
    fv.round(4).to_csv(tdir / "fuel_variants.csv", index=False)
    ta = dg.transport_attribution(hist, lv, ex)
    ta.round(4).to_csv(tdir / "transport_attribution.csv", index=False)
    results["fuel_variants"] = fv.round(3).to_dict(orient="records")
    results["transport_attribution"] = ta.round(3).to_dict(orient="records")

    # ------------------------------------------------------- robustness --
    if not skip_robustness:
        rc = cfg["robustness"]
        rng = np.random.default_rng(fc["seed"])
        preps = 100 if fast else rc["placebo_reps"]
        _log("robustness: lag grid, subsamples, asymmetry, Covid, placebo, 2026 backtest")
        grid, subs, other, bts, oos_rows, oos_raw, rolls = [], [], [], [], [], {}, {}
        for k in cfg["targets"]:
            y = hist[k]
            g = rb.lag_grid(y, x, rc["lag_grid"], "1989-01", est["end"], ex)
            g.insert(0, "target", k)
            grid.append(g)
            sb = rb.subsamples(y, x, p, q, rc["subsamples"], ex)
            sb.insert(0, "target", k)
            subs.append(sb)
            asy = rb.asymmetry(y, x, p, q, est["start"], est["end"], ex)
            inc = fit_ardl(y, x, p, q, est["start"], est["end"], [], est["hac_lags"])
            plc = rb.placebo(y, x, p, q, est["start"], est["end"], ex, preps, rng)
            other.append(dict(target=k, chow_2008_p=rb.chow_test(y, x, p, q, est["start"], est["end"], ex, rc["chow_break"]),
                              covid_included_lr10=inc.long_run()[0], covid_included_r2=inc.r2,
                              baseline_lr10=models[k].long_run()[0], **asy,
                              placebo_p=plc["p_value"], placebo_abs_p95=plc["placebo_p95"]))
            bt = rb.backtest_2026(models[k], y, x, mu=anchor_mu(ds.levels, hist, acfg, k, "2025-12"))
            bts.append(dict(target=k, **bt))
            _log(f"  out-of-sample forecasts: {k}")
            afn = (lambda T, k=k: anchor_mu(ds.levels, hist, acfg, k, T)) if k in acfg.get("targets", {}) else None
            fcs = rb.oos_forecasts(y, x, p, q, est["start"], ex, rc["oos_first_origin"], rc["oos_last_origin"],
                                   rc["oos_horizon"], anchor_fn=afn)
            oos_raw[k] = fcs
            sm_ = rb.oos_summary(fcs)
            sm_.name = k
            oos_rows.append(sm_)
            if k in ("headline_cpi", "core_pce", "headline_pce", "transport_pce"):
                rolls[k] = rb.rolling_long_run(y, x, p, q, ex, rc["rolling_window_years"], "2001-12-01", "2025-12-01")
        grid = pd.concat(grid)
        grid.round(4).to_csv(tdir / "robust_lag_grid.csv", index=False)
        subs = pd.concat(subs)
        subs.round(4).to_csv(tdir / "robust_subsamples.csv", index=False)
        other = pd.DataFrame(other)
        other.round(4).to_csv(tdir / "robust_other.csv", index=False)
        bts = pd.DataFrame(bts)
        bts.round(4).to_csv(tdir / "backtest_2026.csv", index=False)
        oos = pd.DataFrame(oos_rows)
        oos.columns = [f"{a}_{b}" for a, b in oos.columns]
        oos.round(4).to_csv(tdir / "robust_oos.csv", index_label="target")
        pd.concat(oos_raw, names=["target"]).round(4).to_csv(tdir / "robust_oos_forecasts.csv")
        for k, r in rolls.items():
            r.round(4).to_csv(tdir / f"robust_rolling_lr_{k}.csv")
        # regime sensitivity: same scenarios, coefficients from the recent sample only
        ra, rbnd = rc["regime_sample"]
        reg_rows = []
        for k in cfg["targets"]:
            mr = fit_ardl(hist[k], x, p, q, ra, rbnd, ex, est["hac_lags"])
            for s_ in cfg["scenarios"]:
                path = build_path(brent0, origin, H, cfg["scenarios"][s_]["steps"])
                fx = 100.0 * np.log(pd.concat([pd.Series([brent0], index=[origin]), path])).diff().iloc[1:]
                fr = point_forecast(mr, hist[k], x, fx, origin, np.zeros(H), k, s_, "fades", anchors[k])
                base = central[(central.target == k) & (central.scenario == s_)]["yoy"].values
                reg_rows.append(dict(target=k, scenario=s_, lr10_recent=mr.long_run()[0], lr10_full=models[k].long_run()[0],
                                     yoy_sep27_recent=fr.yoy()[0][-1], yoy_sep27_full=base[-1]))
        regime = pd.DataFrame(reg_rows)
        regime.round(3).to_csv(tdir / "robust_regime_scenarios.csv", index=False)
        results["robust_regime"] = regime.round(3).to_dict(orient="records")
        results["robust"] = {
            "lag_grid_best_bic": grid.loc[grid["bic_rank"] == 1, ["target", "p", "q", "lr10"]].to_dict(orient="records"),
            "lag_grid_lr_range": grid.groupby("target")["lr10"].agg(["min", "max"]).round(3).to_dict(orient="index"),
            "subsamples": subs.round(3).to_dict(orient="records"),
            "other": other.round(4).to_dict(orient="records"),
            "backtest_2026": bts.round(3).to_dict(orient="records"),
            "oos": oos.round(4).to_dict(orient="index"),
        }

    # ---------------------------------------------------------- figures --
    _log("figures")
    lab = ds.labels
    hyoy = {k: yoy_from_logpct(hist[k]) for k in cfg["targets"]}
    hmom = {k: 100 * np.expm1(hist[k] / 100) for k in cfg["targets"]}
    cs = cfg["central_scenario"]
    cen = {k: central[(central.target == k) & (central.scenario == cs)] for k in cfg["targets"]}
    src = "Source: BLS, BEA, EIA via FRED; model estimates. Band = 10th-90th percentile of 1,000 parameter + shock draws."
    plots.fan_grid(hyoy, {k: v["yoy"] for k, v in cen.items()}, {k: v["yoy_lo"] for k, v in cen.items()},
                   {k: v["yoy_hi"] for k, v in cen.items()}, lab, HEADLINE_KEYS,
                   cfg["scenarios"][cs]["label"], fdir / "fan_yoy.png", note=src)
    plots.mom_panels(hmom, {k: v["mom_pct"] for k, v in cen.items()}, {k: v["mom_lo"] for k, v in cen.items()},
                     {k: v["mom_hi"] for k, v in cen.items()}, lab, ["headline_pce", "core_pce"], fdir / "mom_pce.png", note=src)
    plots.mom_panels(hmom, {k: v["mom_pct"] for k, v in cen.items()}, {k: v["mom_lo"] for k, v in cen.items()},
                     {k: v["mom_hi"] for k, v in cen.items()}, lab, ["headline_cpi", "core_cpi"], fdir / "mom_cpi.png", note=src)
    sl = {s: cfg["scenarios"][s]["label"] for s in cfg["scenarios"]}
    src_c = "Source: BLS, BEA, EIA via FRED; model estimates (central case, forecast errors fade)."
    paths = {k: {s: central[(central.target == k) & (central.scenario == s)]["yoy"] for s in KEY_SCENARIOS}
             for k in cfg["targets"]}
    plots.scenario_lines(hyoy, paths, lab, ["headline_pce", "core_pce"], sl, "YoY %",
                         "PCE inflation under four oil paths", fdir / "scenarios_pce.png", note=src_c)
    plots.scenario_lines(hyoy, paths, lab, ["headline_cpi", "core_cpi"], sl, "YoY %",
                         "CPI inflation under four oil paths", fdir / "scenarios_cpi.png", note=src_c)
    plots.small_multiples({s: proj[s] for s in KEY_SCENARIOS},
                          {"T5YIEM": "5y breakeven, %", "GS2": "2y Treasury, %", "FII10": "10y real (TIPS), %",
                           "XLK_implied_pct": "XLK, % from real-yield channel"},
                          sl, "From oil to expectations, rates and tech", fdir / "rates_chain.png",
                          {**origin_rates, "XLK_implied_pct": 0.0},
                          note="Origin = Sep-2026 monthly averages. XLK line is only the part explained by the real-yield beta.")
    bpaths = {s: build_path(brent0, origin, H, cfg["scenarios"][s]["steps"]) for s in ["flat_114"] + KEY_SCENARIOS}
    plots.brent_paths(lv[cfg["driver"]["id"]], bpaths, sl, fdir / "brent_scenarios.png", note="Source: EIA via FRED (MCOILBRENTEU); scenario paths from config.yaml.")
    xb = pd.DataFrame({sl[s]: {"core": proj[s]["XLK_implied_pct"].iloc[-1], "hawk": proj[s]["XLK_implied_pct_hawk"].iloc[-1]}
                       for s in cfg["scenarios"]}).T
    plots.bars_h(xb, {"core": "Fed reacts to core PCE (estimated)", "hawk": "Fed reacts to headline PCE (hawkish)"},
                 "XLK move from the real-yield channel alone, Oct-26 to Sep-27", "% change in XLK", fdir / "xlk_channel.png",
                 ref=0.0, note="Real-yield beta of -0.10% per bp (2016-2025). Excludes earnings, AI demand and everything else that moves tech.")
    irfs = {k: models[k].irf(horizon=36) for k in ["headline_pce", "core_pce", "transport_pce", "energy_pce"]}
    plots.irf_lines(irfs, lab, fdir / "irf_timing.png")
    if not skip_robustness:
        o = oos.copy()
        o.index = [lab[k] for k in o.index]
        plots.bars_h(o, {"12m_ratio_oil_vs_ar": "vs AR without oil", "12m_ratio_oil_vs_rw": "vs random walk on YoY",
                         "12m_ratio_flat_vs_rw": "flat-oil version vs random walk"},
                     "Out-of-sample 12-month forecast error (RMSE ratio; < 1 = model better)", "RMSE ratio",
                     fdir / "oos_rmse.png", ref=1.0, note="Expanding-window forecasts, origins 2005-2024, windows overlapping Covid dropped.")
        plots.rolling_lr(rolls, lab, fdir / "rolling_passthrough.png")

    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    _log(f"done -> {out}")
    return results
