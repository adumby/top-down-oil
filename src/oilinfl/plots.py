"""Static figures (PNG) for the paper and README."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
HIST = "#52514e"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 9.5, "axes.titlesize": 10.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True,
    "lines.linewidth": 1.6, "legend.frameon": False, "legend.fontsize": 8.5,
})


def _dates(ax, months=(1, 7)):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=list(months)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(axis="x", labelrotation=0)


def _finish(fig, path, note=None):
    if note:
        fig.text(0.01, 0.005, note, fontsize=7.5, color=INK2, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fan_grid(hist_yoy: dict, central: dict, lo: dict, hi: dict, labels: dict, keys: list, title_suffix: str, path,
             since="2024-01", note=None):
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.4), sharex=True)
    for ax, k in zip(axes.flat, keys):
        h = hist_yoy[k].loc[since:]
        ax.plot(h.index, h.values, color=HIST, label="Actual")
        c = central[k]
        ax.fill_between(c.index, lo[k].values, hi[k].values, color=SERIES[0], alpha=0.16, lw=0, label="10-90% band")
        cx = [h.index[-1]] + list(c.index)
        ax.plot(cx, [h.values[-1]] + list(c.values), color=SERIES[0], label="Central")
        ax.axhline(2, color=INK2, lw=0.8, ls=":")
        ax.set_title(labels[k])
        ax.set_ylabel("YoY %")
        _dates(ax)
        ax.annotate(f"{c.values[-1]:.1f}%", (c.index[-1], c.values[-1]), xytext=(4, 0), textcoords="offset points",
                    fontsize=8.5, color=INK, va="center")
    axes[0, 0].legend(loc="upper left")
    fig.suptitle(f"Inflation outlook, {title_suffix}", x=0.01, ha="left", fontweight="bold")
    _finish(fig, path, note)


def scenario_lines(hist: dict, paths: dict, labels: dict, keys: list, scen_labels: dict, ylabel: str, title: str,
                   path, since="2025-01", note=None):
    fig, axes = plt.subplots(1, len(keys), figsize=(5.0 * len(keys), 3.8), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, k in zip(axes, keys):
        h = hist[k].loc[since:]
        ax.plot(h.index, h.values, color=HIST, label="Actual")
        for i, (s, ser) in enumerate(paths[k].items()):
            cx = [h.index[-1]] + list(ser.index)
            ax.plot(cx, [h.values[-1]] + list(ser.values), color=SERIES[i], label=scen_labels[s])
            ax.annotate(f"{ser.values[-1]:.1f}", (ser.index[-1], ser.values[-1]), xytext=(4, 0),
                        textcoords="offset points", fontsize=8, color=INK2, va="center")
        ax.set_title(labels[k])
        ax.set_ylabel(ylabel)
        _dates(ax)
    axes[0].legend(loc="best")
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    _finish(fig, path, note)


def mom_panels(hist: dict, central: dict, lo: dict, hi: dict, labels: dict, keys: list, path, since="2025-10", note=None):
    fig, axes = plt.subplots(1, len(keys), figsize=(5.0 * len(keys), 3.6), sharey=True)
    for ax, k in zip(np.atleast_1d(axes), keys):
        h = hist[k].loc[since:]
        ax.plot(h.index, h.values, color=HIST, marker="o", ms=3.5, label="Actual")
        c = central[k]
        ax.fill_between(c.index, lo[k].values, hi[k].values, color=SERIES[0], alpha=0.16, lw=0, label="10-90% band")
        ax.plot(c.index, c.values, color=SERIES[0], marker="o", ms=3.5, label="Central")
        ax.axhline(2 / 12 * 1.0, color=INK2, lw=0.8, ls=":")
        ax.set_title(labels[k])
        ax.set_ylabel("MoM %")
        _dates(ax, (1, 4, 7, 10))
    np.atleast_1d(axes)[0].legend(loc="upper right")
    fig.suptitle("Month-over-month path (dotted line = pace consistent with 2% a year)", x=0.01, ha="left",
                 fontweight="bold")
    _finish(fig, path, note)


def small_multiples(frames: dict, cols: dict, scen_labels: dict, title: str, path, origin_vals: dict, note=None):
    keys = list(cols)
    fig, axes = plt.subplots(1, len(keys), figsize=(3.4 * len(keys), 3.4))
    for ax, c in zip(axes, keys):
        for i, (s, df) in enumerate(frames.items()):
            x = [df.index[0] - pd.offsets.MonthBegin(1)] + list(df.index)
            ax.plot(x, [origin_vals[c]] + list(df[c].values), color=SERIES[i], label=scen_labels[s])
        ax.set_title(cols[c])
        _dates(ax, (1, 4, 7, 10))
    axes[0].legend(loc="best", fontsize=7.5)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold")
    _finish(fig, path, note)


def bars_h(df: pd.DataFrame, cols: dict, title: str, xlabel: str, path, ref=None, note=None):
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(df) + 1.4))
    n = len(cols)
    hgt = 0.8 / n
    y = np.arange(len(df))
    for i, (c, lab) in enumerate(cols.items()):
        ax.barh(y + (i - (n - 1) / 2) * hgt, df[c].values, height=hgt * 0.9, color=SERIES[i], label=lab)
    ax.set_yticks(y)
    ax.set_yticklabels(df.index)
    ax.invert_yaxis()
    if ref is not None:
        ax.axvline(ref, color=INK2, lw=0.9, ls="--")
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=n, fontsize=8)
    ax.set_title(title, pad=26)
    _finish(fig, path, note)


def rolling_lr(rolls: dict, labels: dict, path, note=None):
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for i, (k, r) in enumerate(rolls.items()):
        ax.fill_between(r.index, r.lo, r.hi, color=SERIES[i], alpha=0.12, lw=0)
        ax.plot(r.index, r.lr10, color=SERIES[i], label=labels[k])
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylabel("Long-run effect of +10% Brent (% of price level)")
    ax.legend(loc="upper left")
    ax.set_title("Pass-through over time (rolling 12-year windows, 95% band)")
    _finish(fig, path, note)


def irf_lines(irfs: dict, labels: dict, path, note=None):
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for i, (k, cum) in enumerate(irfs.items()):
        share = cum / cum[-1] * 100
        ax.plot(np.arange(len(cum)), share, color=SERIES[i], label=labels[k])
    ax.axhline(50, color=INK2, lw=0.8, ls=":")
    ax.axhline(90, color=INK2, lw=0.8, ls=":")
    ax.set_xlabel("Months after a one-time permanent Brent move")
    ax.set_ylabel("% of 36-month effect reached")
    ax.legend(loc="lower right")
    ax.set_title("How fast an oil shock reaches each price measure")
    _finish(fig, path, note)


def brent_paths(hist: pd.Series, paths: dict, scen_labels: dict, path, since="2025-06", note=None):
    fig, ax = plt.subplots(figsize=(8, 3.8))
    h = hist.loc[since:]
    ax.plot(h.index, h.values, color=HIST, label="Actual")
    for i, (s, ser) in enumerate(paths.items()):
        cx = [h.index[-1]] + list(ser.index)
        ax.plot(cx, [h.values[-1]] + list(ser.values), color=SERIES[i], label=scen_labels[s])
    ax.set_ylabel("$ per barrel")
    _dates(ax, (1, 4, 7, 10))
    ax.set_title("Brent scenarios (monthly average)")
    ax.legend(loc="upper left", fontsize=7.5)
    _finish(fig, path, note)
