"""
Generate a realistic synthetic noon-report dataset for demos and tests.

The data embeds a known fouling signal: fuel consumption drifts ~6% above the
clean baseline over a 120-day voyage series, with weather noise on top. This
lets the performance module demonstrate detecting something real.

Deliberately uses messy, non-canonical column names and injects a few bad rows
so the ingestion / quality-flag layer has something to catch.
"""

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

N = 120
start = pd.Timestamp("2024-01-01")
dates = [start + pd.Timedelta(days=i) for i in range(N)]

# Clean baseline: FOC = 0.015 * speed^3 (typical-ish power law for a tanker)
a_true, b_true = 0.015, 3.0
speeds = rng.uniform(10.5, 14.5, N)

# Fouling: linear growth in excess consumption, 0% -> 6% over the series
fouling_pct = np.linspace(0.0, 6.0, N)

# Weather: Beaufort, with a consumption penalty in heavy weather
beaufort = rng.integers(1, 8, N)
weather_penalty = np.where(beaufort >= 5, rng.uniform(0.05, 0.15, N), 0.0)

clean_foc = a_true * speeds ** b_true
foc = clean_foc * (1 + fouling_pct / 100.0) * (1 + weather_penalty)
foc *= rng.normal(1.0, 0.03, N)  # measurement noise

distance = speeds * 24.0 * rng.normal(1.0, 0.01, N)

df = pd.DataFrame({
    "Date": dates,
    "Obs Speed": np.round(speeds, 2),
    "Distance Obs": np.round(distance, 1),
    "ME FOC": np.round(foc * 0.92, 2),     # main engine portion
    "AE FOC": np.round(foc * 0.08, 2),     # aux portion
    "Bunker Grade": "HFO",
    "Wind Force": beaufort,
    "Mean Draft": np.round(rng.uniform(11.0, 14.0, N), 2),
})

# Inject a few bad rows the quality layer should flag
df.loc[20, "Distance Obs"] = -5          # negative distance
df.loc[50, "ME FOC"] = 999               # implausible FOC
df.loc[80, "Obs Speed"] = 0              # zero speed

df.to_csv("examples/sample_noon_reports.csv", index=False)
print(f"Wrote examples/sample_noon_reports.csv with {len(df)} rows")
print("Embedded fouling: ~6% excess consumption growth over the series.")
