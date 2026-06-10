# Verification — every constant, audited against its source

This is the audit trail behind noonkit's regulation tables. Each hard-coded number in `imo_reference.py` was checked against the primary IMO resolution PDF, not against secondary summaries. Status legend: **Verified** = matches the in-force instrument · **Assumed/Input** = not defined by regulation; flagged in-tool · **Out of scope** = deliberately not implemented.

## Why this document exists: two real errors caught

During the original verification pass against the MEPC resolution PDFs, two transcription errors that circulate in secondary sources were caught and corrected before release:

1. **LNG carrier reference-line coefficients** — the values commonly reproduced in secondary material did not match MEPC.353(78); the resolution's own table (with its size-band split at 100,000 DWT) is what ships in the code.
2. **Ro-ro cargo (vehicle carrier) coefficient** — a widely-circulated value of **a = 5739** is wrong; the correct MEPC.353(78) value is **a = 3627**.

Both errors would have produced wrong required-CII values — and therefore wrong ratings — for those ship types. This is the concrete case for auditing against primary text rather than trusting summaries, and it is the standing invitation of this repo: if you find a discrepancy against a resolution, open an issue quoting the instrument and paragraph.

## 1. CII reference lines (`imo_reference.py`)

| Constant | Source | Status |
|---|---|---|
| Reference-line (a, c) per ship type, incl. size bands and capacity clamps (e.g. tanker a=5247 c=0.610; bulk carrier a=4745 c=0.622 with the ≥279,000 DWT clamp; ro-ro vehicle carrier a=3627) | Resolution MEPC.353(78), Table 1 (IMO PDF) | Verified |
| Capacity basis per ship type (DWT vs GT) | MEPC.337(76)/G1 and MEPC.352(78) | Verified |

## 2. Reduction factors Z

| Years | Values | Source | Status |
|---|---|---|---|
| 2023–2026 | 5 / 7 / 9 / 11 % | G3 guidelines (MEPC.338(76) as amended) | Verified |
| 2027–2030 | 13.625 / 16.25 / 18.875 / 21.5 % | Resolution MEPC.400(83), adopted 11 Apr 2025 (MEPC 83/17/Add.1 Annex 4) | Verified |
| Beyond 2030 | any continuation is a user projection, flagged non-regulatory | Phase-2 review pending | Assumed |

## 3. Rating boundaries

| Constant | Source | Status |
|---|---|---|
| dd-vectors exp(d1..d4) per ship type (e.g. tanker 0.82/0.93/1.08/1.28; bulk 0.86/0.94/1.06/1.18), incl. gas/LNG size-band splits | Resolution MEPC.354(78), Table 1 | Verified |
| Rating logic (A–E placement; C minimum; 3×D or 1×E → corrective plan) | MARPOL Annex VI reg. 28; MEPC.339(76)/G4 | Verified |
| Worked boundary example reproduced in tests (required 10 → 8.6/9.4/10.6/11.8 → attained 9 = B, bulk carrier) | MEPC published example | Cross-check |

## 4. Emissions conversion

| Constant | Source | Status |
|---|---|---|
| Cf fuel-mass → CO₂ factors (HFO 3.114, MDO/MGO 3.206, LNG 2.750 …) | Resolution MEPC.364(79) | Verified |

## 5. Performance analysis (no regulatory constants)

| Element | Status |
|---|---|
| Good-weather threshold (default Beaufort ≤ 4) | Analytical default, configurable — Assumed |
| Clean-baseline window (default first 30 days) | Analytical default, configurable — Assumed |
| Deviation and trend definitions | Documented in [METHODOLOGY.md](METHODOLOGY.md) §2; pinned by tests |
| Voyage correction factors (MEPC.355(78)) | Out of scope — attained CII is the uncorrected estimate |

## 6. How the audit was performed

1. Primary text first: the MEPC resolution PDFs from the IMO document index.
2. Each table cross-checked against at least one independent authoritative source — and where they disagreed, the resolution won (see the two caught errors above).
3. Worked examples reproduced inside the automated test suite, so the verification is executable, not just documented.
4. Anything regulation does not define is implemented as a flagged, configurable assumption — never silently invented.

---

*Maintained by [Navallogic Solutions](https://navallogic.com).*
