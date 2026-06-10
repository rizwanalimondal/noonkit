"""
IMO reference data for Carbon Intensity Indicator (CII) calculations.

All values are transcribed directly from the official IMO MEPC resolutions.
Every table below names the resolution it comes from so the numbers can be
audited against the primary source. These are NOT approximations.

Primary sources
---------------
- MEPC.337(76)  : 2021 Guidelines on operational carbon intensity indicators
                  and the calculation methods (CII Guidelines, G1).
- MEPC.339(76)  : 2021 Guidelines on the operational carbon intensity rating
                  of ships (CII Rating Guidelines, G4). Source of the dd-vectors.
- MEPC.338(76)  : 2021 Guidelines on the reference lines (CII Reference Lines
                  Guidelines, G2). Source of the a / c reference-line params.
- MEPC.353(78)  : 2022 amendments to the reference-line guidelines.
- MEPC.354(78)  : 2022 amendments to the rating guidelines (consolidated
                  dd-vectors used here).
- MEPC.364(79)  : 2022 Guidelines on the method of calculation of the EEDI;
                  source of the fuel-mass -> CO2-mass conversion factors (Cf).
- MEPC.348(78)  : Annual reduction factor (Z%) table through 2026.
- MEPC.400(83)  : Adopted 11 April 2025 — extends the reduction factor (Z%)
                  table through 2030 (13.625 / 16.25 / 18.875 / 21.5 %).

IMPORTANT
---------
Reduction factors are formally adopted through 2030 (MEPC.400(83)). Factors
beyond 2030 are NOT yet defined (IMO Phase-2 review pending); the library
refuses years outside the table rather than inventing values. The
`is_official` flag is retained so any future projection mechanism must label
itself. See `REDUCTION_FACTORS` below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ShipType(str, Enum):
    """The 12 ship types covered by the CII regulation (MEPC.353(78) Table)."""

    BULK_CARRIER = "bulk_carrier"
    GAS_CARRIER = "gas_carrier"
    TANKER = "tanker"
    CONTAINER_SHIP = "container_ship"
    GENERAL_CARGO_SHIP = "general_cargo_ship"
    REFRIGERATED_CARGO_CARRIER = "refrigerated_cargo_carrier"
    COMBINATION_CARRIER = "combination_carrier"
    LNG_CARRIER = "lng_carrier"
    RORO_CARGO_VEHICLE_CARRIER = "roro_cargo_vehicle_carrier"
    RORO_CARGO_SHIP = "roro_cargo_ship"
    RORO_PASSENGER_SHIP = "roro_passenger_ship"
    CRUISE_PASSENGER_SHIP = "cruise_passenger_ship"


class CapacityMetric(str, Enum):
    DWT = "dwt"  # deadweight tonnage
    GT = "gt"  # gross tonnage


class Rating(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


@dataclass(frozen=True)
class ReferenceLineParams:
    """Reference-line parameters: required CII = a * Capacity ** (-c).

    Source: MEPC.353(78). `capacity_metric` indicates whether the capacity
    used in the formula is DWT or GT for this ship type / size band.
    `dwt_cap` (if set) caps the capacity value used in the formula.
    `dwt_threshold` distinguishes size bands within a single ship type.
    """

    a: float
    c: float
    capacity_metric: CapacityMetric
    dwt_cap: float | None = None
    gt_cap: float | None = None
    dwt_threshold: float | None = None
    applies_above_threshold: bool | None = None


# ---------------------------------------------------------------------------
# Reference-line parameters (a, c) per ship type  --  MEPC.353(78)
#
# required_CII_ref = a * Capacity ** (-c)
#
# Some ship types have two size bands keyed on DWT. These are stored as a list
# of candidate ReferenceLineParams; the resolver in cii.py picks the right band.
# ---------------------------------------------------------------------------
REFERENCE_LINE_PARAMS: dict[ShipType, list[ReferenceLineParams]] = {
    ShipType.BULK_CARRIER: [
        # capacity capped at 279,000 DWT for the largest band
        ReferenceLineParams(a=4745.0, c=0.622, capacity_metric=CapacityMetric.DWT,
                            dwt_cap=279000.0),
    ],
    ShipType.GAS_CARRIER: [
        ReferenceLineParams(a=14405e7, c=2.071, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=65000.0, applies_above_threshold=True),
        ReferenceLineParams(a=8104.0, c=0.639, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=65000.0, applies_above_threshold=False),
    ],
    ShipType.TANKER: [
        ReferenceLineParams(a=5247.0, c=0.610, capacity_metric=CapacityMetric.DWT),
    ],
    ShipType.CONTAINER_SHIP: [
        ReferenceLineParams(a=1984.0, c=0.489, capacity_metric=CapacityMetric.DWT),
    ],
    ShipType.GENERAL_CARGO_SHIP: [
        ReferenceLineParams(a=31948.0, c=0.792, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=20000.0, applies_above_threshold=True),
        ReferenceLineParams(a=588.0, c=0.3885, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=20000.0, applies_above_threshold=False),
    ],
    ShipType.REFRIGERATED_CARGO_CARRIER: [
        ReferenceLineParams(a=4600.0, c=0.557, capacity_metric=CapacityMetric.DWT),
    ],
    ShipType.COMBINATION_CARRIER: [
        ReferenceLineParams(a=5119.0, c=0.622, capacity_metric=CapacityMetric.DWT),
    ],
    ShipType.LNG_CARRIER: [
        # Three bands per MEPC.353(78) Table 1.
        ReferenceLineParams(a=9.827, c=0.000, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=100000.0, applies_above_threshold=True),
        ReferenceLineParams(a=14479e10, c=2.673, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=65000.0, applies_above_threshold=True),
        ReferenceLineParams(a=14779e10, c=2.673, capacity_metric=CapacityMetric.DWT,
                            dwt_threshold=65000.0, applies_above_threshold=False),
    ],
    ShipType.RORO_CARGO_VEHICLE_CARRIER: [
        # Per MEPC.353(78): a=3627, c=0.590 for >=30,000 GT (>=57,700 capped
        # at 57,700); a=330, c=0.329 for <30,000 GT.
        ReferenceLineParams(a=3627.0, c=0.590, capacity_metric=CapacityMetric.GT,
                            gt_cap=57700.0, dwt_threshold=30000.0,
                            applies_above_threshold=True),
        ReferenceLineParams(a=330.0, c=0.329, capacity_metric=CapacityMetric.GT,
                            dwt_threshold=30000.0, applies_above_threshold=False),
    ],
    ShipType.RORO_CARGO_SHIP: [
        ReferenceLineParams(a=1967.0, c=0.485, capacity_metric=CapacityMetric.GT),
    ],
    ShipType.RORO_PASSENGER_SHIP: [
        ReferenceLineParams(a=2023.0, c=0.460, capacity_metric=CapacityMetric.GT),
    ],
    ShipType.CRUISE_PASSENGER_SHIP: [
        ReferenceLineParams(a=930.0, c=0.383, capacity_metric=CapacityMetric.GT),
    ],
}


# ---------------------------------------------------------------------------
# dd-vectors (rating boundary multipliers)  --  MEPC.354(78)
#
# Boundaries are: required_CII * exp(d_i), for i in 1..4.
# Order: (d1, d2, d3, d4) = (superior, lower, upper, inferior).
# A ship is rated by where its attained/required ratio sits relative to these.
# ---------------------------------------------------------------------------
DD_VECTORS: dict[ShipType, dict[str, tuple[float, float, float, float]]] = {
    ShipType.BULK_CARRIER: {"default": (0.86, 0.94, 1.06, 1.18)},
    ShipType.GAS_CARRIER: {
        "ge_65000": (0.81, 0.91, 1.12, 1.44),
        "lt_65000": (0.85, 0.95, 1.06, 1.25),
    },
    ShipType.TANKER: {"default": (0.82, 0.93, 1.08, 1.28)},
    ShipType.CONTAINER_SHIP: {"default": (0.83, 0.94, 1.07, 1.19)},
    ShipType.GENERAL_CARGO_SHIP: {"default": (0.83, 0.94, 1.06, 1.19)},
    ShipType.REFRIGERATED_CARGO_CARRIER: {"default": (0.78, 0.91, 1.07, 1.20)},
    ShipType.COMBINATION_CARRIER: {"default": (0.87, 0.96, 1.06, 1.14)},
    ShipType.LNG_CARRIER: {
        "ge_100000": (0.89, 0.98, 1.06, 1.13),
        "lt_100000": (0.78, 0.92, 1.10, 1.37),
    },
    ShipType.RORO_CARGO_VEHICLE_CARRIER: {"default": (0.86, 0.94, 1.06, 1.16)},
    ShipType.RORO_CARGO_SHIP: {"default": (0.76, 0.89, 1.08, 1.27)},
    ShipType.RORO_PASSENGER_SHIP: {"default": (0.76, 0.92, 1.14, 1.30)},
    ShipType.CRUISE_PASSENGER_SHIP: {"default": (0.87, 0.95, 1.06, 1.16)},
}


# ---------------------------------------------------------------------------
# Fuel mass -> CO2 mass conversion factors (Cf)  --  MEPC.364(79)
#
# Cf is in tonnes CO2 per tonne of fuel. Lower calorific value (LCV) in kJ/kg
# is included for completeness / future energy-based metrics.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FuelFactor:
    cf: float  # t-CO2 / t-fuel
    lcv_kj_per_kg: float
    iso_reference: str


FUEL_FACTORS: dict[str, FuelFactor] = {
    "diesel_gas_oil": FuelFactor(3.206, 42700, "ISO 8217 DMX-DMB"),
    "light_fuel_oil": FuelFactor(3.151, 41200, "ISO 8217 RMA-RMD"),
    "heavy_fuel_oil": FuelFactor(3.114, 40200, "ISO 8217 RME-RMK"),
    "lpg_propane": FuelFactor(3.000, 46300, "Propane"),
    "lpg_butane": FuelFactor(3.030, 45700, "Butane"),
    "ethane": FuelFactor(2.927, 46400, "Ethane"),
    "lng": FuelFactor(2.750, 48000, "LNG"),
    "methanol": FuelFactor(1.375, 19900, "Methanol"),
    "ethanol": FuelFactor(1.913, 26800, "Ethanol"),
}

# Common aliases seen in real noon reports / bunker delivery notes.
FUEL_ALIASES: dict[str, str] = {
    "hfo": "heavy_fuel_oil",
    "ifo": "heavy_fuel_oil",
    "ifo380": "heavy_fuel_oil",
    "ifo180": "heavy_fuel_oil",
    "rmg": "heavy_fuel_oil",
    "rmg380": "heavy_fuel_oil",
    "vlsfo": "heavy_fuel_oil",  # treated as RME-RMK band per Cf
    "lsfo": "light_fuel_oil",
    "lfo": "light_fuel_oil",
    "mdo": "diesel_gas_oil",
    "mgo": "diesel_gas_oil",
    "do": "diesel_gas_oil",
    "dmx": "diesel_gas_oil",
    "dma": "diesel_gas_oil",
    "dmb": "diesel_gas_oil",
    "lng": "lng",
    "methanol": "methanol",
}


def resolve_fuel(name: str) -> FuelFactor:
    """Resolve a fuel name (canonical key or common alias) to its factor."""
    key = name.strip().lower().replace(" ", "_").replace("-", "")
    # try a few normalisations
    for candidate in (name.strip().lower().replace(" ", "_"), key):
        if candidate in FUEL_FACTORS:
            return FUEL_FACTORS[candidate]
        if candidate in FUEL_ALIASES:
            return FUEL_FACTORS[FUEL_ALIASES[candidate]]
    raise KeyError(
        f"Unknown fuel type '{name}'. Known types: "
        f"{sorted(set(FUEL_FACTORS) | set(FUEL_ALIASES))}"
    )


# ---------------------------------------------------------------------------
# Annual reduction factor Z%  --  MEPC.338(76) / MEPC.348(78) / MEPC.400(83)
#
# required_CII(year) = reference_CII * (1 - Z/100)
#
# Values 2023-2026 per MEPC.348(78); 2027-2030 formally adopted by
# Resolution MEPC.400(83) on 11 April 2025 (a +2.625 pp/year ramp).
# Beyond 2030 nothing is defined (Phase-2 review pending) and the library
# raises for years outside this table.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReductionFactor:
    z_percent: float
    is_official: bool


REDUCTION_FACTORS: dict[int, ReductionFactor] = {
    2019: ReductionFactor(0.0, True),
    2020: ReductionFactor(1.0, True),
    2021: ReductionFactor(2.0, True),
    2022: ReductionFactor(3.0, True),
    2023: ReductionFactor(5.0, True),
    2024: ReductionFactor(7.0, True),
    2025: ReductionFactor(9.0, True),
    2026: ReductionFactor(11.0, True),
    # ---- Adopted by Resolution MEPC.400(83), 11 April 2025 ----
    2027: ReductionFactor(13.625, True),
    2028: ReductionFactor(16.25, True),
    2029: ReductionFactor(18.875, True),
    2030: ReductionFactor(21.5, True),
}
