# Methodology

This document explains exactly how `noonkit` computes everything it reports, so
that any result can be audited against primary sources. Nothing here is a black
box. If you find a discrepancy with the IMO resolutions, please open an issue —
correctness is the entire point of an open tool in this space.

---

## 1. Carbon Intensity Indicator (CII)

### 1.1 What the regulation requires

The operational CII applies to cargo, RoRo and cruise ships of 5,000 GT and
above. Each ship calculates an **attained** annual CII, which is compared to a
**required** CII to produce an A–E rating. C or better is the minimum standard;
an E in one year, or D in three consecutive years, triggers a corrective action
plan in the ship's SEEMP.

### 1.2 Attained CII

```
attained_CII = total_CO2_emitted / (capacity × distance_sailed)
```

- `total_CO2_emitted` is the sum over all fuels of `fuel_mass × Cf`, where `Cf`
  is the fuel's carbon conversion factor (tonnes CO₂ per tonne fuel).
- `capacity` is **deadweight tonnage (DWT)** for most ship types and **gross
  tonnage (GT)** for RoRo and cruise types (see §1.4).
- `distance_sailed` is total distance over ground for the year, in nautical
  miles.

Internally the library works in grams of CO₂ to avoid floating-point scale
issues, then the ratio is unit-consistent because both attained and required
CII share the same units (g CO₂ per capacity·nm).

### 1.3 Fuel conversion factors (Cf)

Source: **IMO MEPC.364(79)**. These are transcribed verbatim in
`imo_reference.py` and pinned by tests.

| Fuel | Cf (t-CO₂/t-fuel) |
|------|------------------:|
| Diesel / Gas Oil (MGO/MDO) | 3.206 |
| Light Fuel Oil (LFO) | 3.151 |
| Heavy Fuel Oil (HFO/VLSFO) | 3.114 |
| LPG (propane) | 3.000 |
| LPG (butane) | 3.030 |
| Ethane | 2.927 |
| LNG | 2.750 |
| Methanol | 1.375 |
| Ethanol | 1.913 |

Real-world fuel names are messy, so the library maps common aliases (IFO380,
RMG, VLSFO → heavy fuel oil; MGO/MDO → diesel/gas oil, etc.). The alias table is
explicit and editable.

### 1.4 Capacity selection

Source: **IMO MEPC.353(78)**.

- Most ship types use **DWT**.
- Ro-ro cargo (vehicle carrier), ro-ro cargo, ro-ro passenger and cruise
  passenger ships use **GT**.
- Bulk carriers cap the DWT used in the formula at **279,000**.

### 1.5 Reference and required CII

```
reference_CII = a × Capacity^(−c)
required_CII  = reference_CII × (1 − Z/100)
```

- `a` and `c` are ship-type (and sometimes size-band) coefficients from
  **MEPC.353(78)**.
- `Z` is the annual reduction factor from **MEPC.338(76)** / **MEPC.348(78)**:
  0% (2019) rising to 11% (2026).

**Important honesty note:** reduction factors beyond 2026 have **not** been
formally adopted by the IMO. Where the library projects to 2027–2030 it uses a
linear-trend estimate (13/15/17/19%) and flags every such result as an
*unofficial projection*. We would rather under-claim than present an unadopted
number as settled regulation.

### 1.6 Rating boundaries

Source: **IMO MEPC.354(78)**. Each ship type has a `dd` vector
`(d1, d2, d3, d4)`. Boundaries are `required_CII × exp? ` — note the published
guidelines express the boundaries as multipliers `d_i` directly applied to the
required CII (the worked example below confirms the arithmetic). The rating is
assigned by where the **attained/required ratio** falls:

| Rating | Condition on ratio |
|--------|--------------------|
| A | ratio < d1 (superior) |
| B | d1 ≤ ratio < d2 (lower) |
| C | d2 ≤ ratio < d3 (upper) |
| D | d3 ≤ ratio < d4 (inferior) |
| E | ratio ≥ d4 |

**Worked example (from the IMO guidelines).** A bulk carrier with required CII
of 10 gCO₂/(DWT·nm) and `dd = (0.86, 0.94, 1.06, 1.18)` has boundaries at
8.6 / 9.4 / 10.6 / 11.8. An attained CII of 9 → ratio 0.9 → rating **B**; an
attained CII of 11 → ratio 1.1 → rating **D**. This exact case is pinned in
`tests/test_cii.py`.

---

## 2. Vessel performance analysis

### 2.1 Speed–consumption curve

The relationship between speed and fuel consumption is modelled as a power law:

```
FOC = a × speed^b
```

This is the operational form of the classic admiralty relationship; in practice
`b` is usually close to 3 for displacement hulls in steady steaming. The fit is
done by **log-linearisation**:

```
ln(FOC) = ln(a) + b × ln(speed)
```

and ordinary least squares on the logs. We report `R²` on the log fit and the
number of points used, so you can immediately judge whether the curve is
trustworthy or whether the data is too noisy to support conclusions.

### 2.2 Good-weather filtering

Charter-party performance clauses are conventionally assessed in good weather,
because heavy seas inflate consumption independently of hull condition. By
default the fit uses only reports at **Beaufort ≤ 4**. This is configurable.

### 2.3 Clean-hull baseline

To detect fouling or machinery degradation, the baseline curve should represent
the ship in clean condition. The library can fit the baseline on the **first N
days** of the series (default 30) and then measure deviation of all later
reports against that clean reference. Fitting across the whole series instead
would average the fouling signal away and hide exactly what we want to see.

### 2.4 Baseline deviation and fouling trend

For each report:

```
deviation_% = 100 × (actual_FOC − predicted_FOC) / predicted_FOC
```

A persistent positive deviation is the operational signature of hull fouling or
machinery underperformance. The library fits a linear trend of deviation against
time and reports it as **percentage points per 30 days**, giving a simple,
interpretable fouling rate.

### 2.5 Data quality is surfaced, not hidden

Noon data is hand-entered and imperfect. Rather than silently dropping or
"correcting" rows, the ingestion layer attaches quality flags (non-positive or
implausible distance/speed/FOC, unparseable dates, speed–distance mismatch) and
lets the caller decide. The analysis functions accept an exclude mask so flagged
rows can be kept out of fits and trends. A single bad FOC value can otherwise
dominate a trend regression — so excluding flagged rows is recommended and is
the CLI default.

---

## 3. Sources

- MEPC.336(76) — operational CII framework
- MEPC.337(76) — CII calculation guidelines (G1)
- MEPC.338(76) — reference-line / reduction-factor guidelines (G3)
- MEPC.339(76) — CII rating guidelines (G4), dd-vectors
- MEPC.353(78) — 2022 reference-line amendments (a, c coefficients)
- MEPC.354(78) — 2022 rating-guideline amendments (consolidated dd-vectors)
- MEPC.364(79) — fuel mass → CO₂ conversion factors (Cf)
- Smart Maritime Network — Standardised Vessel Dataset (SVD) for Noon Reports

All numeric tables in `imo_reference.py` cite the resolution they come from.
