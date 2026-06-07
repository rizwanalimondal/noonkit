# noonkit

**Open, methodology-transparent analysis of ship noon reports — vessel
performance and IMO CII compliance, in one toolkit.**

Every shipping company collects noon reports daily. The analysis of that data —
speed–consumption curves, hull-fouling detection, carbon-intensity compliance —
is locked inside expensive proprietary platforms. The open ecosystem has a data
*standard* (the Smart Maritime Network's [SVD for Noon
Reports](https://smartmaritimenetwork.com/standardised-vessel-dataset-for-noon-reports/))
and academic ML models, but no open, auditable *analysis tool* that sits between
them. `noonkit` fills that gap.

It does two things, both with fully documented methodology:

1. **Vessel performance** — fits speed–consumption curves, establishes a
   clean-hull baseline, and quantifies fouling / degradation as a trend over
   time, with good-weather filtering as standard.
2. **IMO CII** — computes attained and required Carbon Intensity Indicator and
   the A–E rating, implemented straight from the MEPC resolutions with a full
   audit trail and explicit handling of the not-yet-adopted post-2026 factors.

> **Scope and honesty.** Outputs are **estimates for planning and insight**,
> not a verified Statement of Compliance. Compliance ratings are issued by
> Administrations and Recognized Organisations against verified DCS data.
> `noonkit` is built to be correct against the published formulae (see the test
> suite), but it is a decision-support tool, not a regulatory authority.

---

## Why this exists / how it differs

- The one existing open CII implementation is single-language, lightly
  maintained, and CII-only. `noonkit` combines CII with the performance
  analysis that operators actually run day to day, in Python, with a real test
  suite validated against the IMO worked examples.
- It consumes data shaped like the **open industry standard** (SVD), rather than
  inventing yet another schema. The ingestion layer maps real-world messy column
  names onto a canonical schema and **surfaces data-quality problems instead of
  hiding them**.
- The [methodology](docs/METHODOLOGY.md) is written out formula by formula, each
  tied to the MEPC resolution it comes from. You can audit every number.

## Install

```bash
pip install -e .          # from a clone
# or, once published:
# pip install noonkit
```

Requires Python ≥ 3.10, `pandas`, `numpy`.

## Quick start (CLI)

```bash
# Generate a demo dataset (with an embedded fouling signal)
python examples/generate_sample_data.py

# Analyze it: performance + CII
noonkit analyze examples/sample_noon_reports.csv \
    --ship-type tanker --dwt 110000 --gt 60000 --year 2024
```

Example output:

```
[ Performance ]
  Speed-consumption model: FOC = 0.01524 * speed^2.995  (R^2=0.984, n=17, ...)
  Mean deviation from baseline: +6.81%
  Fouling trend: +1.81 pp / 30 days

[ CII compliance ]
  2024 tanker: rating C (attained 3.831, required 4.103, A/R 0.934)
  Compliant (C or better): True
```

## Quick start (library)

```python
from noonkit import (
    ingest_csv, fit_speed_consumption, baseline_deviation,
    calculate_cii, FuelConsumption, ShipType,
)

# --- performance ---
data = ingest_csv("reports.csv")
excl = data.exclude_mask()                       # drop implausible rows
model = fit_speed_consumption(data.df, baseline_days=30, exclude_mask=excl)
dev = baseline_deviation(data.df, model, exclude_mask=excl)
print(model.summary(), dev.mean_deviation_pct, dev.trend_pct_per_30d)

# --- CII ---
result = calculate_cii(
    ship_type=ShipType.TANKER,
    dwt=110_000, gt=60_000,
    distance_nm=35_654,
    fuels=[FuelConsumption("HFO", 4_825)],
    year=2024,
)
print(result.summary(), "compliant:", result.is_compliant)
```

## Data format

`noonkit` maps common noon-report column names automatically (e.g. `Obs Speed`,
`Distance Obs`, `ME FOC`, `AE FOC`, `Wind Force`). The canonical fields follow
the spirit of the SVD standard. See `examples/sample_noon_reports.csv` for a
working example and `src/noonkit/ingest.py` for the full alias table.

## Tests

```bash
pytest
```

The suite pins the CII engine to the IMO worked examples and the published
reference tables, and verifies the performance fit recovers a known power law
and a known fouling trend from synthetic data.

## Roadmap

- EU MRV / IMO DCS report export
- EEXI (design index) calculation alongside operational CII
- Trim/draft correction in the performance baseline
- Multi-fuel voyage aggregation directly from per-leg noon data
- Optional local web dashboard (charts + uploads) on top of this library

## Contributing

Issues and PRs welcome — especially corrections traced to a primary IMO source.
If a coefficient is wrong, cite the resolution and it gets fixed with a test.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This software is provided as-is. Results are estimates and guidance and must not
be treated as proof of regulatory compliance. Always verify against official
sources and your Administration / Recognized Organisation.
