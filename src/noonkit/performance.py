"""
Vessel performance analysis from noon-report data.

The core methods here are deliberately simple, transparent and documented,
because the value of an open tool is that anyone can see exactly how a number
was produced. No black-box models.

Methods
-------
1. Speed-consumption curve: fit FOC = a * speed^b (the standard admiralty-style
   relationship; cubic-ish in practice). Returns the fitted coefficients and
   goodness-of-fit so the user can judge whether the fit is meaningful.
2. Baseline deviation: compare each report's actual FOC against the FOC the
   fitted curve predicts for that speed. Persistent positive deviation is the
   classic signal of hull fouling or machinery degradation.
3. Weather filtering: the curve should be fitted on "good weather" days only
   (Beaufort <= a threshold), per common charter-party performance-clause
   practice, so that fouling signal is not confounded by sea state.

All functions take the canonical DataFrame produced by `ingest`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class SpeedConsumptionModel:
    a: float  # coefficient in FOC = a * speed^b
    b: float  # exponent
    r_squared: float
    n_points: int
    speed_range: tuple[float, float]
    good_weather_only: bool
    bf_threshold: float

    def predict(self, speed_kn: float | np.ndarray):
        return self.a * np.power(speed_kn, self.b)

    def summary(self) -> str:
        return (
            f"FOC = {self.a:.4g} * speed^{self.b:.3f}  "
            f"(R^2={self.r_squared:.3f}, n={self.n_points}, "
            f"speeds {self.speed_range[0]:.1f}-{self.speed_range[1]:.1f} kn)"
        )


def _clean_for_fit(
    df: pd.DataFrame,
    bf_threshold: float,
    good_weather_only: bool,
    exclude_mask: "pd.Series | None" = None,
) -> pd.DataFrame:
    required = {"speed_kn", "total_foc_t"}
    if not required <= set(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"missing required columns for fit: {missing}")
    mask = (df["speed_kn"] > 0) & (df["total_foc_t"] > 0)
    if exclude_mask is not None:
        mask &= ~exclude_mask.reindex(df.index).fillna(False)
    if good_weather_only and "wind_force_bf" in df.columns:
        mask &= df["wind_force_bf"].fillna(99) <= bf_threshold
    return df.loc[mask, ["speed_kn", "total_foc_t"]].dropna()


def fit_speed_consumption(
    df: pd.DataFrame,
    bf_threshold: float = 4.0,
    good_weather_only: bool = True,
    exclude_mask: "pd.Series | None" = None,
    baseline_days: "int | None" = None,
) -> SpeedConsumptionModel:
    """Fit FOC = a * speed^b via log-linear regression.

    Taking logs linearises the power law: ln(FOC) = ln(a) + b*ln(speed).
    R^2 is reported on the log-scale fit. Pass `exclude_mask` (True == drop)
    to keep quality-flagged rows out of the fit.

    If `baseline_days` is given and the data has parseable `report_date`, the
    fit uses only reports within that many days of the earliest report. This
    establishes a *clean-hull baseline* so that later deviation reflects drift
    (fouling / degradation) rather than being averaged away across the series.
    """
    fit_df = df
    if baseline_days is not None and "report_date" in df.columns:
        dated = df.dropna(subset=["report_date"])
        if len(dated) > 0:
            t0 = dated["report_date"].min()
            within = (df["report_date"] - t0).dt.total_seconds() <= baseline_days * 86400
            fit_df = df.loc[within.fillna(False)]
    data = _clean_for_fit(fit_df, bf_threshold, good_weather_only, exclude_mask)
    if len(data) < 3:
        raise ValueError(
            f"need at least 3 valid points to fit; got {len(data)}. "
            "Try good_weather_only=False or check data quality."
        )
    x = np.log(data["speed_kn"].to_numpy())
    y = np.log(data["total_foc_t"].to_numpy())
    b, ln_a = np.polyfit(x, y, 1)
    a = float(np.exp(ln_a))
    # R^2 on the log fit
    y_pred = ln_a + b * x
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return SpeedConsumptionModel(
        a=a,
        b=float(b),
        r_squared=r2,
        n_points=len(data),
        speed_range=(float(data["speed_kn"].min()), float(data["speed_kn"].max())),
        good_weather_only=good_weather_only,
        bf_threshold=bf_threshold,
    )


@dataclass
class DeviationResult:
    per_report: pd.DataFrame  # adds predicted_foc, deviation_t, deviation_pct
    mean_deviation_pct: float
    trend_pct_per_30d: float | None
    n_reports: int
    notes: list[str] = field(default_factory=list)


def baseline_deviation(
    df: pd.DataFrame,
    model: SpeedConsumptionModel,
    exclude_mask: "pd.Series | None" = None,
) -> DeviationResult:
    """Compare actual FOC against the model baseline for each report.

    Positive deviation_pct means burning more fuel than the clean baseline
    predicts for that speed — the operational signature of hull fouling or
    machinery underperformance.

    Parameters
    ----------
    exclude_mask : optional boolean Series aligned to df. True == drop this row
        (e.g. quality-flagged rows). Excluding implausible rows is strongly
        recommended; a single bad FOC value can dominate the trend regression.
    """
    notes: list[str] = []
    work = df.copy()
    valid = (work["speed_kn"] > 0) & (work["total_foc_t"] > 0)
    if exclude_mask is not None:
        em = exclude_mask.reindex(work.index).fillna(False)
        valid &= ~em
        notes.append(f"Excluded {int(em.sum())} quality-flagged row(s).")
    work = work.loc[valid].copy()
    work["predicted_foc_t"] = model.predict(work["speed_kn"].to_numpy())
    work["deviation_t"] = work["total_foc_t"] - work["predicted_foc_t"]
    work["deviation_pct"] = 100.0 * work["deviation_t"] / work["predicted_foc_t"]

    mean_dev = float(work["deviation_pct"].mean())

    trend = None
    if "report_date" in work.columns and work["report_date"].notna().sum() >= 5:
        dated = work.dropna(subset=["report_date"]).sort_values("report_date")
        if len(dated) >= 5:
            days = (
                dated["report_date"] - dated["report_date"].min()
            ).dt.total_seconds() / 86400.0
            slope, _ = np.polyfit(days.to_numpy(), dated["deviation_pct"].to_numpy(), 1)
            trend = float(slope * 30.0)  # %-points per 30 days
            notes.append(
                f"Fouling trend: deviation is changing by {trend:+.2f} "
                "percentage points per 30 days."
            )

    return DeviationResult(
        per_report=work,
        mean_deviation_pct=mean_dev,
        trend_pct_per_30d=trend,
        n_reports=len(work),
        notes=notes,
    )
