"""
noonkit dashboard — a visual face on the noonkit engine.

This app does NO maritime calculation of its own. Every number it shows comes
straight from the noonkit library (the same verified, tested engine used by the
CLI). The dashboard's only job is to let a non-programmer upload a CSV, see the
results, and read them clearly. Keeping the math in the library — not in the UI
— is deliberate: it means the dashboard can never silently disagree with the
tested engine.

Run locally:   streamlit run app.py
Deploy free:   push to GitHub, connect at share.streamlit.io
"""

from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from noonkit import (
    FuelConsumption,
    baseline_deviation,
    calculate_cii,
    fit_speed_consumption,
    ingest_dataframe,
)
from noonkit.imo_reference import ShipType

# ---------------------------------------------------------------------------
# Page config + light styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="noonkit · noon-report analysis",
    page_icon="🚢",
    layout="wide",
)

NAVY = "#1b2a4a"
ACCENT = "#c2410c"
GRID = "#e6e8ec"

st.markdown(
    """
    <style>
    .stApp { background: #fbfcfd; }
    h1, h2, h3 { color: #1b2a4a; }
    .rating-badge {
        display:inline-block; padding:6px 18px; border-radius:8px;
        font-size:28px; font-weight:700; color:white;
    }
    .small-note { color:#6b7280; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

RATING_COLORS = {
    "A": "#15803d", "B": "#65a30d", "C": "#ca8a04",
    "D": "#ea580c", "E": "#dc2626",
}


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🚢 noonkit")
st.markdown(
    "**Open, methodology-transparent analysis of ship noon reports.** "
    "Upload your noon-report CSV to see hull-fouling signal and IMO CII rating. "
    "Every number is computed by the [open-source noonkit engine]"
    "(https://github.com/rizwanalimondal/noonkit) — nothing is calculated in "
    "this page."
)
st.caption(
    "Decision-support and planning estimates only — not a verified Statement of "
    "Compliance. See the methodology and FAQ in the repository."
)

# ---------------------------------------------------------------------------
# Sidebar: vessel particulars + data source
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Vessel particulars")
    ship_type = st.selectbox(
        "Ship type",
        options=[s.value for s in ShipType],
        index=[s.value for s in ShipType].index("tanker"),
        format_func=lambda s: s.replace("_", " ").title(),
    )
    dwt = st.number_input("Deadweight tonnage (DWT)", min_value=0, value=110000, step=1000)
    gt = st.number_input("Gross tonnage (GT)", min_value=0, value=60000, step=1000)
    year = st.selectbox("CII year", options=list(range(2023, 2031)), index=1)
    fuel_type = st.selectbox(
        "Primary fuel",
        options=["HFO", "VLSFO", "LFO", "MGO", "MDO", "LNG", "Methanol"],
        index=0,
    )
    st.divider()
    st.header("Analysis settings")
    good_weather = st.checkbox("Good-weather fit only (Beaufort ≤ 4)", value=True)
    bf_threshold = st.slider("Beaufort threshold", 1, 8, 4)
    baseline_days = st.slider("Clean-hull baseline window (days)", 0, 90, 30,
                              help="Fit the clean baseline on the first N days. "
                                   "0 uses the whole series.")

st.divider()

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
st.subheader("1 · Load noon reports")
col_a, col_b = st.columns([2, 1])
with col_a:
    uploaded = st.file_uploader(
        "Upload a noon-report CSV (any common column names — they're auto-mapped)",
        type=["csv"],
    )
with col_b:
    use_demo = st.button("Use demo data instead", use_container_width=True)

raw_df = None
source_label = None

# Build demo data inline (mirrors examples/generate_sample_data.py) so the
# deployed app is self-contained and needs no bundled file.
def build_demo() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 120
    start = pd.Timestamp("2024-01-01")
    speeds = rng.uniform(10.5, 14.5, n)
    fouling = np.linspace(0.0, 6.0, n)
    bf = rng.integers(1, 8, n)
    penalty = np.where(bf >= 5, rng.uniform(0.05, 0.15, n), 0.0)
    foc = 0.015 * speeds ** 3 * (1 + fouling / 100) * (1 + penalty)
    foc *= rng.normal(1.0, 0.03, n)
    dist = speeds * 24 * rng.normal(1.0, 0.01, n)
    df = pd.DataFrame({
        "Date": [start + pd.Timedelta(days=i) for i in range(n)],
        "Obs Speed": np.round(speeds, 2),
        "Distance Obs": np.round(dist, 1),
        "ME FOC": np.round(foc * 0.92, 2),
        "AE FOC": np.round(foc * 0.08, 2),
        "Bunker Grade": "HFO",
        "Wind Force": bf,
        "Mean Draft": np.round(rng.uniform(11, 14, n), 2),
    })
    df.loc[20, "Distance Obs"] = -5
    df.loc[50, "ME FOC"] = 999
    df.loc[80, "Obs Speed"] = 0
    return df

if uploaded is not None:
    raw_df = pd.read_csv(uploaded)
    source_label = f"uploaded file: {uploaded.name}"
elif use_demo or st.session_state.get("demo_loaded"):
    st.session_state["demo_loaded"] = True
    raw_df = build_demo()
    source_label = "demo data (synthetic, with an embedded fouling signal)"

if raw_df is None:
    st.info("Upload a CSV or click **Use demo data** to see noonkit in action.")
    st.stop()

st.success(f"Loaded {len(raw_df)} rows from {source_label}.")

# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
result = ingest_dataframe(raw_df)
excl = result.exclude_mask()

with st.expander("Ingestion & data quality", expanded=False):
    st.write("**Mapped fields:**", ", ".join(sorted(result.column_map)) or "none")
    if result.unmapped_sources:
        st.write("**Unmapped columns:**", ", ".join(result.unmapped_sources))
    qs = {k: v for k, v in result.quality_summary().items() if v > 0}
    if qs:
        st.warning("Data-quality flags raised (rows kept, not deleted):")
        st.json(qs)
    else:
        st.write("No data-quality flags raised.")
    for note in result.notes:
        st.caption(note)

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
st.subheader("2 · Performance — hull-fouling signal")
try:
    model = fit_speed_consumption(
        result.df,
        bf_threshold=bf_threshold,
        good_weather_only=good_weather,
        exclude_mask=excl,
        baseline_days=baseline_days if baseline_days > 0 else None,
    )
    dev = baseline_deviation(result.df, model, exclude_mask=excl)

    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline fit R²", f"{model.r_squared:.3f}")
    m2.metric("Mean deviation", f"{dev.mean_deviation_pct:+.1f}%")
    trend_str = (f"{dev.trend_pct_per_30d:+.2f} pp/30d"
                 if dev.trend_pct_per_30d is not None else "n/a")
    m3.metric("Fouling trend", trend_str)
    st.caption(f"Model: {model.summary()}")

    c1, c2 = st.columns(2)

    with c1:
        fig, ax = plt.subplots(figsize=(6, 4))
        d = dev.per_report
        ax.scatter(d["speed_kn"], d["total_foc_t"], s=22, color=ACCENT,
                   alpha=0.55, edgecolor="white", linewidth=0.4, zorder=3)
        xs = np.linspace(d["speed_kn"].min(), d["speed_kn"].max(), 100)
        ax.plot(xs, model.predict(xs), color=NAVY, linewidth=2.4, zorder=4)
        ax.set_xlabel("Speed (knots)"); ax.set_ylabel("Fuel (t/day)")
        ax.set_title("Speed–consumption curve")
        ax.grid(True, color=GRID, linewidth=0.7); ax.set_axisbelow(True)
        st.pyplot(fig)

    with c2:
        d = dev.per_report.dropna(subset=["report_date"]).sort_values("report_date")
        if len(d) >= 2:
            days = (d["report_date"] - d["report_date"].min()).dt.days
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.axhline(0, color="#9aa0a6", linewidth=1)
            ax.scatter(days, d["deviation_pct"], s=20, color=ACCENT, alpha=0.5,
                       edgecolor="white", linewidth=0.4, zorder=3)
            slope, intercept = np.polyfit(days, d["deviation_pct"], 1)
            ax.plot(days, slope * days + intercept, color=NAVY, linewidth=2.4)
            ax.set_xlabel("Days into series"); ax.set_ylabel("Deviation vs baseline (%)")
            ax.set_title("Fouling signal over time")
            ax.grid(True, color=GRID, linewidth=0.7); ax.set_axisbelow(True)
            st.pyplot(fig)
        else:
            st.info("Not enough dated reports to plot a trend.")
except ValueError as e:
    st.error(f"Could not fit performance model: {e}")

# ---------------------------------------------------------------------------
# CII
# ---------------------------------------------------------------------------
st.subheader("3 · IMO Carbon Intensity Indicator")
try:
    total_dist = float(result.df["distance_nm"].clip(lower=0).sum())
    total_foc = float(result.df["total_foc_t"].clip(lower=0).sum())
    cii = calculate_cii(
        ship_type=ShipType(ship_type),
        dwt=dwt, gt=gt,
        distance_nm=total_dist,
        fuels=[FuelConsumption(fuel_type, total_foc)],
        year=year,
    )
    cc1, cc2, cc3 = st.columns([1, 2, 2])
    with cc1:
        color = RATING_COLORS[cii.rating.value]
        st.markdown(
            f"<div class='rating-badge' style='background:{color}'>"
            f"Rating {cii.rating.value}</div>",
            unsafe_allow_html=True,
        )
        st.caption("C or better = compliant")
    cc2.metric("Attained CII", f"{cii.attained_cii:.3g}")
    cc2.metric("Required CII", f"{cii.required_cii:.3g}")
    cc3.metric("Attained / Required", f"{cii.ar_ratio:.3f}")
    cc3.metric("Total distance / fuel",
               f"{total_dist:,.0f} nm / {total_foc:,.0f} t")
    for note in cii.notes:
        st.warning(note)
except (ValueError, KeyError) as e:
    st.error(f"Could not compute CII: {e}")

st.divider()
st.caption(
    "noonkit is open source (MIT). Coefficients verified against IMO MEPC "
    "resolution PDFs. This dashboard calls the library directly and performs no "
    "calculation of its own."
)
