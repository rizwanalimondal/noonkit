"""
noonkit — open, methodology-transparent analysis of ship noon reports.

Two things in one toolkit:
1. Vessel performance analysis (speed-consumption curves, fouling/baseline
   deviation, weather-filtered fits) from standard noon-report data.
2. IMO operational Carbon Intensity Indicator (CII) calculation and rating,
   implemented straight from the MEPC resolutions with a full audit trail.

Built on the canonical field structure of the Smart Maritime Network's open
Standardised Vessel Dataset (SVD) for Noon Reports.

DISCLAIMER: All outputs are estimates and planning guidance. They are not a
substitute for verified compliance documentation issued by an Administration
or Recognized Organisation.
"""

from .cii import (
    CIIResult,
    FuelConsumption,
    calculate_cii,
    reference_cii,
    required_cii,
)
from .ingest import IngestResult, ingest_csv, ingest_dataframe
from .imo_reference import Rating, ShipType
from .performance import (
    DeviationResult,
    SpeedConsumptionModel,
    baseline_deviation,
    fit_speed_consumption,
)

__version__ = "0.1.0"

__all__ = [
    "ShipType",
    "Rating",
    "FuelConsumption",
    "CIIResult",
    "calculate_cii",
    "reference_cii",
    "required_cii",
    "ingest_csv",
    "ingest_dataframe",
    "IngestResult",
    "fit_speed_consumption",
    "baseline_deviation",
    "SpeedConsumptionModel",
    "DeviationResult",
]
