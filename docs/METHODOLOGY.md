# Methodology — every formula, worked through

This document explains exactly what noonkit computes and why each design choice was made. It claims nothing the library does not produce; the test suite pins the CII arithmetic to IMO worked examples and the performance logic to hand-verifiable cases.

noonkit answers two questions from the same daily noon-report data: **is this ship drifting off its clean-hull performance?** and **what is its IMO carbon-intensity rating?** The two share an ingestion layer and a philosophy — surface data problems, cite every constant, separate estimate from regulation — but the methods are different in kind: performance analysis is *statistical inference from noisy data*; CII is *regulation arithmetic with no degrees of freedom*. The document treats them in that order.

---

## 1. Ingestion — messy reality onto a canonical schema

Noon reports are hand-entered. The ingestion layer maps real-world column-name variations onto a canonical schema (shaped after the Smart Maritime Network's Standardised Vessel Dataset) and attaches **quality flags** instead of silently dropping or "correcting" rows:

- non-positive or implausible distance, speed, or fuel consumption;
- unparseable dates;
- speed–distance mismatch (the reported speed and 24-hour distance disagree beyond tolerance).

The analysis functions accept an exclude mask so flagged rows can be kept out of fits and trends. This matters statistically, not just hygienically: a single fat-fingered FOC value can dominate a least-squares trend regression. Excluding flagged rows is the recommended and default behaviour; the choice — and the flags themselves — remain visible to the user.

## 2. Vessel performance — the fouling signal

### 2.1 The physical idea

A ship's resistance through water grows steeply with speed (classically near the cube), so daily fuel consumption against speed traces a characteristic curve for a given hull condition, draft regime and trim practice. Marine growth on the hull adds frictional resistance; the operational consequence is that the ship burns more fuel *at the same speed* than its clean self did. That gap, trended over time, is the fouling signal — extractable from data the ship already files every day, with no extra sensors.

### 2.2 The speed–consumption fit and weather filtering

The library fits a power-law curve `FOC = a × speed^b` by log-linear regression — taking logs linearises the power law (`ln FOC = ln a + b·ln speed`), and the goodness-of-fit (R²) is reported on the log-scale fit. Weather is the dominant confounder — heavy weather inflates consumption regardless of hull condition — so by default the fit uses only reports at **Beaufort ≤ 4**. This is filtering rather than "weather correction" by design: proper correction needs wave/wind direction and response data that noon reports don't reliably carry, and a filtered like-for-like comparison is more defensible than a corrected one built on missing inputs. The threshold is configurable.

### 2.3 Clean-hull baseline

To detect fouling or machinery degradation, the baseline curve must represent the ship in clean condition. The library fits the baseline on the **first N days** of the series (default 30) and measures deviation of all later reports against that clean reference. Fitting across the whole series instead would average the fouling signal into the baseline and hide exactly what we want to see. Choose the window to follow a known clean event (dry dock, hull clean) where possible.

### 2.4 Baseline deviation and fouling trend

For each report:

```
deviation_% = 100 × (actual_FOC − predicted_FOC) / predicted_FOC
```

A persistent positive deviation in good weather is the operational signature of hull fouling or machinery underperformance. The library fits a linear trend of deviation against time and reports it as **percentage points per 30 days** — a single, interpretable fouling rate a superintendent can act on. (Why a linear trend and not something fancier: fouling growth over the horizon that matters operationally is close enough to linear that the simpler model is more robust to noon-report noise, and its slope has an immediate physical meaning.)

### 2.5 What the signal can and cannot tell you

The deviation conflates everything that moves the ship off its curve: hull fouling, propeller fouling, machinery degradation, persistent draft/trim changes. noonkit tells you the ship is off its baseline and how fast it's drifting; attributing the drift to a specific cause is an inspection and engineering judgement. That boundary is deliberate.

## 3. IMO CII — regulation arithmetic

In contrast to section 2, nothing here is estimated. Every quantity is a closed-form calculation from IMO resolutions, and every numeric table in `imo_reference.py` cites the resolution it came from.

```
Attained CII = total CO₂ [g] / (Capacity × distance sailed [nm])
```

- Total CO₂ = Σ (fuel mass × Cf) over fuel types, with the Cf conversion factors of **MEPC.364(79)** (e.g. HFO 3.114, MDO/MGO 3.206 t CO₂/t fuel).
- Capacity = DWT for most cargo types, GT for ro-ro passenger / cruise (per the G1 guidelines).

```
Reference CII = a × Capacity^(−c)            (per ship type — MEPC.353(78))
Required CII  = (1 − Z/100) × Reference      (yearly reduction factor — G3 guidelines)
```

The A–E rating places the attained value among boundaries formed by multiplying the Required CII by the ship-type **dd-vectors** of **MEPC.354(78)** (e.g. tanker exp(d1..d4) = 0.82 / 0.93 / 1.08 / 1.28). C is the regulatory minimum; three consecutive D years or a single E triggers a mandatory corrective action plan under SEEMP Part III.

**Reduction factors.** Z values for 2023–2026 (5 / 7 / 9 / 11 %) come from the G3 guidelines; **MEPC.400(83)** (adopted 11 April 2025) extends the table to 2030: 13.625 % (2027), 16.25 % (2028), 18.875 % (2029), 21.5 % (2030) — a linear +2.625 pp/year. Beyond 2030 the factors are undefined pending the IMO's Phase-2 review; any projection past 2030 is labelled as an assumption, never presented as regulation.

**Scope honesty.** noonkit does not apply the voyage correction factors and adjustments of MEPC.355(78); its attained CII is the conservative, uncorrected estimate from your raw noon data. Compliance ratings are issued by Administrations and ROs against verified DCS data — noonkit is decision support, not a regulatory authority.

## 4. Architecture as methodology

All calculation lives in the Python library; the Streamlit dashboard performs **no maritime calculation of its own**. This is a methodological choice, not a stylistic one: it means the UI can never silently disagree with the tested engine, and anyone auditing the numbers has exactly one place to look.

## 5. Testing

The repository ships with an automated test suite covering both halves: the CII engine validated against IMO worked examples (including the rating-boundary example), and the performance logic against hand-constructed series with known baselines, injected fouling trends, and deliberately corrupted rows that the quality flags must catch. Run `python -m pytest -v`.

## 6. Sources

- MEPC.336(76) — operational CII framework
- MEPC.337(76) — CII calculation guidelines (G1)
- MEPC.338(76) — reference-line / reduction-factor guidelines (G3)
- MEPC.400(83) — amendments to G3: reduction factors 2027–2030
- MEPC.339(76) — CII rating guidelines (G4), dd-vectors
- MEPC.353(78) — 2022 reference-line amendments (a, c coefficients)
- MEPC.354(78) — 2022 rating-guideline amendments (consolidated dd-vectors)
- MEPC.364(79) — fuel mass → CO₂ conversion factors (Cf)
- Smart Maritime Network — Standardised Vessel Dataset (SVD) for Noon Reports

All numeric tables in `imo_reference.py` cite the resolution they come from. For the constant-by-constant audit — including the two transcription errors the verification pass caught in circulating secondary sources — see [VERIFICATION.md](VERIFICATION.md).

---

*Maintained by [Navallogic Solutions](https://navallogic.com) — independent maritime advisory for vessel-performance analytics and decarbonisation compliance. Companion tools: [FuelEU Pool Optimiser](https://github.com/rizwanalimondal/fueleu-pool-optimiser) · [Maritime GHG Compliance Navigator](https://github.com/rizwanalimondal/ghg-compliance-navigator).*
