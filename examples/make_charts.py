"""
Generate publication-quality charts from noonkit's analysis output.

This script runs the real noonkit pipeline on the demo dataset and plots the
results. It is a *visualisation built on top of* the library — not part of the
core toolkit — so it lives in examples/. Run it after generating the sample
data:

    python examples/generate_sample_data.py
    python examples/make_charts.py

Outputs two PNGs into examples/charts/:
    1. speed_consumption.png  — clean-hull baseline vs actual reports
    2. fouling_trend.png      — deviation from baseline over time

Requires matplotlib (pip install matplotlib).
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # no display needed; write straight to file
import matplotlib.pyplot as plt
import numpy as np

from noonkit import baseline_deviation, fit_speed_consumption, ingest_csv

# ---- house style: clean, restrained, navy accent ----
NAVY = "#1b2a4a"
ACCENT = "#c2410c"   # burnt orange for the "actual" / problem signal
GRID = "#e6e8ec"
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": "#9aa0a6",
    "axes.linewidth": 0.8,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "figure.dpi": 160,
})

HERE = os.path.dirname(__file__)
CSV = os.path.join(HERE, "sample_noon_reports.csv")
OUT = os.path.join(HERE, "charts")
os.makedirs(OUT, exist_ok=True)


def main() -> None:
    if not os.path.exists(CSV):
        raise SystemExit(
            "sample_noon_reports.csv not found. Run "
            "`python examples/generate_sample_data.py` first."
        )

    data = ingest_csv(CSV)
    excl = data.exclude_mask()
    model = fit_speed_consumption(
        data.df, baseline_days=30, exclude_mask=excl, good_weather_only=True
    )
    dev = baseline_deviation(data.df, model, exclude_mask=excl)
    df = dev.per_report

    # ---------------------------------------------------------------
    # Chart 1: speed-consumption curve
    # ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(
        df["speed_kn"], df["total_foc_t"],
        s=28, color=ACCENT, alpha=0.55, edgecolor="white", linewidth=0.5,
        label="Actual noon reports", zorder=3,
    )
    xs = np.linspace(df["speed_kn"].min(), df["speed_kn"].max(), 100)
    ax.plot(
        xs, model.predict(xs),
        color=NAVY, linewidth=2.5,
        label="Clean-hull baseline (fitted)", zorder=4,
    )
    ax.set_xlabel("Speed (knots)")
    ax.set_ylabel("Fuel consumption (tonnes/day)")
    ax.set_title("Speed–consumption curve")
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    eq = (f"$FOC = {model.a:.4g}\\times speed^{{{model.b:.3f}}}$   "
          f"($R^2 = {model.r_squared:.3f}$)")
    ax.text(0.98, 0.04, eq, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=10, color=NAVY,
            bbox=dict(boxstyle="round,pad=0.4", fc="#f4f6f9", ec="#d6dae0"))
    fig.text(0.99, 0.005, "Generated with noonkit · demo data",
             ha="right", fontsize=8, color="#9aa0a6")
    fig.tight_layout()
    p1 = os.path.join(OUT, "speed_consumption.png")
    fig.savefig(p1, bbox_inches="tight")
    plt.close(fig)

    # ---------------------------------------------------------------
    # Chart 2: fouling trend (deviation over time)
    # ---------------------------------------------------------------
    dated = df.dropna(subset=["report_date"]).sort_values("report_date")
    days = (dated["report_date"] - dated["report_date"].min()).dt.days

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(0, color="#9aa0a6", linewidth=1, zorder=1)
    ax.scatter(days, dated["deviation_pct"], s=26, color=ACCENT, alpha=0.5,
               edgecolor="white", linewidth=0.5, zorder=3,
               label="Per-report deviation")
    # trend line
    if len(days) >= 2:
        slope, intercept = np.polyfit(days, dated["deviation_pct"], 1)
        ax.plot(days, slope * days + intercept, color=NAVY, linewidth=2.5,
                zorder=4,
                label=f"Trend: {dev.trend_pct_per_30d:+.2f} pp / 30 days")
    ax.set_xlabel("Days into voyage series")
    ax.set_ylabel("Fuel consumption vs clean baseline (%)")
    ax.set_title("Hull-fouling signal: consumption drift over time")
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.99, 0.005, "Generated with noonkit · demo data",
             ha="right", fontsize=8, color="#9aa0a6")
    fig.tight_layout()
    p2 = os.path.join(OUT, "fouling_trend.png")
    fig.savefig(p2, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote:\n  {p1}\n  {p2}")
    print(f"\nModel: {model.summary()}")
    print(f"Mean deviation: {dev.mean_deviation_pct:+.2f}%   "
          f"Trend: {dev.trend_pct_per_30d:+.2f} pp/30d")


if __name__ == "__main__":
    main()
