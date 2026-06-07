"""
Tests for the CII engine.

These tests pin the implementation to the IMO worked examples and the published
reference tables. If a future edit changes a coefficient or the rating logic,
these tests should fail loudly.
"""

import math

import pytest

from noonkit.cii import (
    FuelConsumption,
    calculate_cii,
    rate_from_ratio,
    reference_cii,
    required_cii,
    resolve_capacity,
)
from noonkit.imo_reference import (
    CapacityMetric,
    Rating,
    ShipType,
    resolve_fuel,
)


# ---------------------------------------------------------------------------
# Worked example from the IMO CII rating guidelines (MEPC.354(78)).
# A bulk carrier with required CII = 10 gCO2/(DWT.nm) has rating boundaries:
#   superior 8.6, lower 9.4, upper 10.6, inferior 11.8
# (required * exp(d_i) with bulk dd-vector 0.86/0.94/1.06/1.18).
# ---------------------------------------------------------------------------
class TestBulkCarrierWorkedExample:
    DD = (0.86, 0.94, 1.06, 1.18)

    def test_boundaries_match_worked_example(self):
        required = 10.0
        boundaries = [required * d for d in self.DD]
        assert boundaries == pytest.approx([8.6, 9.4, 10.6, 11.8])

    def test_attained_9_is_rating_B(self):
        # attained 9 vs required 10 -> ratio 0.9, between 0.86 and 0.94 -> B
        assert rate_from_ratio(9.0 / 10.0, self.DD) == Rating.B

    def test_attained_11_is_rating_D(self):
        # attained 11 vs required 10 -> ratio 1.1, between 1.06 and 1.18 -> D
        assert rate_from_ratio(11.0 / 10.0, self.DD) == Rating.D

    def test_boundary_edges(self):
        assert rate_from_ratio(0.85, self.DD) == Rating.A
        assert rate_from_ratio(0.86, self.DD) == Rating.B  # at superior edge
        assert rate_from_ratio(0.93, self.DD) == Rating.B
        assert rate_from_ratio(0.94, self.DD) == Rating.C
        assert rate_from_ratio(1.05, self.DD) == Rating.C
        assert rate_from_ratio(1.06, self.DD) == Rating.D
        assert rate_from_ratio(1.18, self.DD) == Rating.E


class TestFuelFactors:
    """CO2 conversion factors must match MEPC.364(79) exactly."""

    def test_hfo_factor(self):
        assert resolve_fuel("HFO").cf == pytest.approx(3.114)

    def test_mgo_alias(self):
        # MGO is an alias for diesel/gas oil -> 3.206
        assert resolve_fuel("MGO").cf == pytest.approx(3.206)

    def test_lng_factor(self):
        assert resolve_fuel("LNG").cf == pytest.approx(2.750)

    def test_one_tonne_hfo_co2(self):
        fc = FuelConsumption("HFO", 1.0)
        # 1 t HFO -> 3.114 t CO2 -> 3,114,000 g
        assert fc.co2_grams() == pytest.approx(3_114_000.0)

    def test_unknown_fuel_raises(self):
        with pytest.raises(KeyError):
            resolve_fuel("rocket_fuel")


class TestCapacityResolution:
    def test_tanker_uses_dwt(self):
        cap, metric = resolve_capacity(ShipType.TANKER, dwt=100000, gt=50000)
        assert metric == CapacityMetric.DWT
        assert cap == 100000

    def test_cruise_uses_gt(self):
        cap, metric = resolve_capacity(
            ShipType.CRUISE_PASSENGER_SHIP, dwt=20000, gt=90000
        )
        assert metric == CapacityMetric.GT
        assert cap == 90000

    def test_bulk_carrier_capacity_capped(self):
        cap, metric = resolve_capacity(
            ShipType.BULK_CARRIER, dwt=320000, gt=160000
        )
        assert metric == CapacityMetric.DWT
        assert cap == 279000  # capped

    def test_missing_dwt_raises(self):
        with pytest.raises(ValueError):
            resolve_capacity(ShipType.TANKER, dwt=0, gt=50000)


class TestReferenceLine:
    def test_tanker_reference_line_positive(self):
        ref = reference_cii(ShipType.TANKER, dwt=100000, gt=50000)
        assert ref > 0

    def test_reference_line_decreases_with_size(self):
        # Larger ships have a lower (better) reference CII per the a*Cap^-c form
        small = reference_cii(ShipType.TANKER, dwt=50000, gt=0)
        large = reference_cii(ShipType.TANKER, dwt=150000, gt=0)
        assert large < small

    def test_required_cii_tightens_over_years(self):
        # 2026 (11% reduction) must be stricter than 2023 (5%)
        r2023 = required_cii(ShipType.TANKER, 100000, 0, 2023)
        r2026 = required_cii(ShipType.TANKER, 100000, 0, 2026)
        assert r2026 < r2023
        # ratio should match the relative reduction factors
        ref = reference_cii(ShipType.TANKER, 100000, 0)
        assert r2023 == pytest.approx(ref * 0.95)
        assert r2026 == pytest.approx(ref * 0.89)


class TestEndToEnd:
    def test_full_calculation_runs_and_is_internally_consistent(self):
        result = calculate_cii(
            ship_type=ShipType.TANKER,
            dwt=100000,
            gt=55000,
            distance_nm=60000,
            fuels=[FuelConsumption("HFO", 8000), FuelConsumption("MGO", 500)],
            year=2024,
        )
        # attained = co2_g / (capacity * distance)
        expected_co2 = 8000 * 3.114e6 + 500 * 3.206e6
        assert result.co2_grams == pytest.approx(expected_co2)
        assert result.transport_work == pytest.approx(100000 * 60000)
        assert result.attained_cii == pytest.approx(
            expected_co2 / (100000 * 60000)
        )
        # A/R ratio and rating must be consistent
        assert result.ar_ratio == pytest.approx(
            result.attained_cii / result.required_cii
        )
        assert result.rating in set(Rating)

    def test_projection_year_flagged(self):
        result = calculate_cii(
            ship_type=ShipType.TANKER, dwt=100000, gt=55000,
            distance_nm=60000, fuels=[FuelConsumption("HFO", 8000)], year=2028,
        )
        assert result.reduction_factor_official is False
        assert any("unofficial" in n.lower() for n in result.notes)

    def test_unsupported_year_raises(self):
        with pytest.raises(ValueError):
            calculate_cii(
                ship_type=ShipType.TANKER, dwt=100000, gt=55000,
                distance_nm=60000, fuels=[FuelConsumption("HFO", 8000)],
                year=2035,
            )

    def test_zero_distance_raises(self):
        with pytest.raises(ValueError):
            calculate_cii(
                ship_type=ShipType.TANKER, dwt=100000, gt=55000,
                distance_nm=0, fuels=[FuelConsumption("HFO", 8000)], year=2024,
            )
