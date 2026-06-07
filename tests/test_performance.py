"""
Tests for ingestion and performance analysis.

These build a tiny synthetic dataset with a KNOWN power-law and a KNOWN fouling
trend, then assert the analysis recovers them within tolerance.
"""

import numpy as np
import pandas as pd
import pytest

from noonkit.ingest import ingest_dataframe
from noonkit.performance import baseline_deviation, fit_speed_consumption


def _make_clean_dataset(n=60, a=0.015, b=3.0, seed=1):
    rng = np.random.default_rng(seed)
    speeds = rng.uniform(11, 14, n)
    foc = a * speeds ** b
    return pd.DataFrame({
        "Date": [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(n)],
        "Speed": np.round(speeds, 2),
        "Distance": np.round(speeds * 24, 1),
        "Total FOC": np.round(foc, 3),
        "Wind Force": rng.integers(1, 4, n),
    })


class TestIngestion:
    def test_messy_columns_are_mapped(self):
        df = _make_clean_dataset()
        res = ingest_dataframe(df)
        assert "speed_kn" in res.column_map
        assert "distance_nm" in res.column_map
        assert "total_foc_t" in res.column_map

    def test_quality_flags_catch_bad_rows(self):
        df = _make_clean_dataset()
        df.loc[5, "Distance"] = -1
        df.loc[10, "Total FOC"] = 999
        res = ingest_dataframe(df)
        mask = res.exclude_mask()
        assert mask.sum() >= 2

    def test_no_mappable_columns_warns(self):
        df = pd.DataFrame({"foo": [1, 2], "bar": [3, 4]})
        res = ingest_dataframe(df)
        assert any("no columns" in n.lower() for n in res.notes)


class TestPerformanceFit:
    def test_recovers_known_power_law(self):
        df = _make_clean_dataset(a=0.015, b=3.0, n=80)
        res = ingest_dataframe(df)
        model = fit_speed_consumption(res.df, good_weather_only=False)
        assert model.b == pytest.approx(3.0, abs=0.05)
        assert model.a == pytest.approx(0.015, rel=0.1)
        assert model.r_squared > 0.95

    def test_detects_positive_fouling_trend(self):
        # Build data with a deliberate +6% drift over 100 days
        rng = np.random.default_rng(7)
        n = 100
        speeds = rng.uniform(11, 14, n)
        clean = 0.015 * speeds ** 3.0
        drift = np.linspace(0, 6, n)  # percent
        foc = clean * (1 + drift / 100.0)
        df = pd.DataFrame({
            "Date": [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(n)],
            "Speed": speeds,
            "Distance": speeds * 24,
            "Total FOC": foc,
            "Wind Force": np.ones(n, dtype=int),
        })
        res = ingest_dataframe(df)
        model = fit_speed_consumption(res.df, good_weather_only=False, baseline_days=20)
        dev = baseline_deviation(res.df, model)
        assert dev.trend_pct_per_30d is not None
        assert dev.trend_pct_per_30d > 0  # fouling detected
        assert dev.mean_deviation_pct > 0

    def test_too_few_points_raises(self):
        df = pd.DataFrame({
            "Speed": [12.0, 13.0],
            "Total FOC": [25.0, 30.0],
        })
        res = ingest_dataframe(df)
        with pytest.raises(ValueError):
            fit_speed_consumption(res.df, good_weather_only=False)
