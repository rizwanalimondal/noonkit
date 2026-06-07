"""
Carbon Intensity Indicator (CII) calculation engine.

This module implements the IMO operational CII calculation as defined in
MEPC.336(76) and the associated guidelines. The implementation is deliberately
explicit and returns a full breakdown of intermediate values so results can be
audited rather than taken on trust.

Definitions used here
----------------------
- Attained CII  = total CO2 emitted (g) / (capacity * distance sailed (nm))
- Reference CII = a * Capacity ** (-c)            [MEPC.353(78)]
- Required CII  = Reference CII * (1 - Z/100)      [MEPC.338(76)]
- Rating        = comparison of attained/required against exp(d_i) boundaries

Units: emissions internally in grams, distance in nautical miles, capacity in
the metric (DWT or GT) prescribed for the ship type. The public API accepts
fuel in tonnes (the unit used in real noon reports / DCS reporting) and converts.

DISCLAIMER: Results are estimates and guidance for planning. They are NOT a
substitute for a verified Statement of Compliance issued by an Administration
or Recognized Organisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .imo_reference import (
    DD_VECTORS,
    REDUCTION_FACTORS,
    REFERENCE_LINE_PARAMS,
    CapacityMetric,
    Rating,
    ReferenceLineParams,
    ShipType,
    resolve_fuel,
)


@dataclass
class FuelConsumption:
    """A quantity of a single fuel consumed over the reporting period."""

    fuel_type: str
    tonnes: float

    def co2_grams(self) -> float:
        factor = resolve_fuel(self.fuel_type)
        # Cf is t-CO2 / t-fuel; convert tonnes CO2 -> grams
        return self.tonnes * factor.cf * 1_000_000.0


@dataclass
class CIIResult:
    year: int
    ship_type: ShipType
    attained_cii: float
    reference_cii: float
    required_cii: float
    rating: Rating
    ar_ratio: float  # attained / required
    boundaries: dict[str, float]
    capacity_used: float
    capacity_metric: CapacityMetric
    co2_grams: float
    transport_work: float
    reduction_factor_pct: float
    reduction_factor_official: bool
    notes: list[str] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        """C or better is the minimum standard under the regulation."""
        return self.rating in (Rating.A, Rating.B, Rating.C)

    def summary(self) -> str:
        flag = "" if self.reduction_factor_official else "  (UNOFFICIAL projection)"
        return (
            f"{self.year} {self.ship_type.value}: rating {self.rating.value} "
            f"(attained {self.attained_cii:.4g}, required {self.required_cii:.4g}, "
            f"A/R {self.ar_ratio:.3f}){flag}"
        )


def _select_reference_params(
    ship_type: ShipType, dwt: float, gt: float = 0.0
) -> ReferenceLineParams:
    candidates = REFERENCE_LINE_PARAMS[ship_type]
    if len(candidates) == 1:
        return candidates[0]
    for params in candidates:
        if params.dwt_threshold is None:
            return params
        # The threshold applies to whichever capacity metric the ship type uses.
        value = gt if params.capacity_metric == CapacityMetric.GT else dwt
        above = value >= params.dwt_threshold
        if params.applies_above_threshold == above:
            return params
    return candidates[-1]


def _select_dd_vector(
    ship_type: ShipType, dwt: float
) -> tuple[float, float, float, float]:
    table = DD_VECTORS[ship_type]
    if "default" in table:
        return table["default"]
    if ship_type == ShipType.GAS_CARRIER:
        return table["ge_65000"] if dwt >= 65000 else table["lt_65000"]
    if ship_type == ShipType.LNG_CARRIER:
        return table["ge_100000"] if dwt >= 100000 else table["lt_100000"]
    # fallback: first entry
    return next(iter(table.values()))


def resolve_capacity(
    ship_type: ShipType, dwt: float, gt: float
) -> tuple[float, CapacityMetric]:
    """Return the capacity value and metric used in the CII formula.

    Per MEPC.353(78): most ship types use DWT; ro-ro/cruise types use GT.
    Bulk carriers cap the DWT used at 279,000.
    """
    params = _select_reference_params(ship_type, dwt, gt)
    if params.capacity_metric == CapacityMetric.GT:
        if gt <= 0:
            raise ValueError(f"{ship_type.value} requires a positive GT value")
        capacity = gt
        if params.gt_cap is not None:
            capacity = min(capacity, params.gt_cap)
        return capacity, CapacityMetric.GT
    if dwt <= 0:
        raise ValueError(f"{ship_type.value} requires a positive DWT value")
    capacity = dwt
    if params.dwt_cap is not None:
        capacity = min(capacity, params.dwt_cap)
    return capacity, CapacityMetric.DWT


def reference_cii(ship_type: ShipType, dwt: float, gt: float) -> float:
    params = _select_reference_params(ship_type, dwt, gt)
    capacity, _ = resolve_capacity(ship_type, dwt, gt)
    return params.a * capacity ** (-params.c)


def required_cii(ship_type: ShipType, dwt: float, gt: float, year: int) -> float:
    if year not in REDUCTION_FACTORS:
        raise ValueError(
            f"No reduction factor available for year {year}. "
            f"Supported years: {min(REDUCTION_FACTORS)}-{max(REDUCTION_FACTORS)}."
        )
    z = REDUCTION_FACTORS[year].z_percent
    return reference_cii(ship_type, dwt, gt) * (1 - z / 100.0)


def rate_from_ratio(
    ar_ratio: float, dd_vector: tuple[float, float, float, float]
) -> Rating:
    """Map an attained/required ratio to a letter rating.

    A: ratio below superior boundary (exp(d1))
    B: between superior and lower (exp(d2))
    C: between lower and upper (exp(d3))
    D: between upper and inferior (exp(d4))
    E: above inferior boundary
    """
    d1, d2, d3, d4 = dd_vector
    if ar_ratio < d1:
        return Rating.A
    if ar_ratio < d2:
        return Rating.B
    if ar_ratio < d3:
        return Rating.C
    if ar_ratio < d4:
        return Rating.D
    return Rating.E


def calculate_cii(
    ship_type: ShipType,
    dwt: float,
    gt: float,
    distance_nm: float,
    fuels: list[FuelConsumption],
    year: int,
) -> CIIResult:
    """Compute the attained CII, required CII and rating for one ship-year.

    Parameters
    ----------
    ship_type : ShipType
    dwt, gt   : deadweight and gross tonnage (provide both; the correct one is
                selected per ship type)
    distance_nm : total distance sailed in the period, nautical miles
    fuels     : list of FuelConsumption (tonnes per fuel type)
    year      : calendar year (selects the reduction factor)
    """
    if distance_nm <= 0:
        raise ValueError("distance_nm must be positive")
    if not fuels:
        raise ValueError("at least one fuel consumption entry is required")
    if year not in REDUCTION_FACTORS:
        raise ValueError(
            f"No reduction factor available for year {year}. "
            f"Supported years: {min(REDUCTION_FACTORS)}-{max(REDUCTION_FACTORS)}."
        )

    notes: list[str] = []
    co2_g = sum(f.co2_grams() for f in fuels)
    capacity, metric = resolve_capacity(ship_type, dwt, gt)
    transport_work = capacity * distance_nm
    attained = co2_g / transport_work

    ref = reference_cii(ship_type, dwt, gt)
    rf = REDUCTION_FACTORS[year]
    required = ref * (1 - rf.z_percent / 100.0)
    if not rf.is_official:
        notes.append(
            f"Reduction factor for {year} ({rf.z_percent}%) is an unofficial "
            "projection not yet adopted by the IMO."
        )

    dd = _select_dd_vector(ship_type, dwt)
    ar = attained / required
    rating = rate_from_ratio(ar, dd)
    boundaries = {
        "superior": required * dd[0],
        "lower": required * dd[1],
        "upper": required * dd[2],
        "inferior": required * dd[3],
    }

    return CIIResult(
        year=year,
        ship_type=ship_type,
        attained_cii=attained,
        reference_cii=ref,
        required_cii=required,
        rating=rating,
        ar_ratio=ar,
        boundaries=boundaries,
        capacity_used=capacity,
        capacity_metric=metric,
        co2_grams=co2_g,
        transport_work=transport_work,
        reduction_factor_pct=rf.z_percent,
        reduction_factor_official=rf.is_official,
        notes=notes,
    )
