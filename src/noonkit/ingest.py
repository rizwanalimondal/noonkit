"""
Noon report ingestion.

Real noon reports arrive as messy spreadsheets: every operator names columns
differently, units vary, and human entry produces gaps and outliers. This
module maps arbitrary input columns onto a canonical schema, coerces units,
and attaches data-quality flags rather than silently dropping or "fixing" bad
rows. Transparency about data quality is the whole point — performance and
compliance numbers are only as trustworthy as the noon data behind them.

The canonical field names are aligned with the spirit of the Smart Maritime
Network Standardised Vessel Dataset (SVD) for Noon Reports, which is the open,
non-proprietary industry reference. This library does not redistribute the SVD;
it provides an analysis layer that consumes SVD-shaped data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

# Canonical schema: field -> list of accepted source-column aliases (lowercased).
CANONICAL_FIELDS: dict[str, list[str]] = {
    "report_date": ["date", "report_date", "reportdate", "datetime", "timestamp", "utc"],
    "distance_nm": ["distance", "distance_nm", "dist", "steamed_distance",
                    "distance_sailed", "distance_observed", "distance_obs",
                    "obs_distance", "dist_obs", "distance_run"],
    "speed_kn": ["speed", "speed_kn", "speed_over_ground", "sog", "obs_speed",
                 "observed_speed", "avg_speed"],
    "me_foc_t": ["me_foc", "me_consumption", "main_engine_foc", "me_fuel",
                 "me_foc_t", "me_hfo", "main_engine_consumption"],
    "aux_foc_t": ["ae_foc", "aux_foc", "auxiliary_consumption", "ae_consumption",
                  "ge_foc", "aux_fuel", "ae_foc_t"],
    "total_foc_t": ["total_foc", "total_consumption", "foc", "total_fuel",
                    "total_foc_t", "tot_cons"],
    "fuel_type": ["fuel", "fuel_type", "fuel_grade", "bunker_grade", "grade"],
    "wind_force_bf": ["wind", "wind_force", "beaufort", "wind_bf", "bf",
                      "wind_force_bf"],
    "draft_mean_m": ["draft", "mean_draft", "draught", "draft_mean", "draft_m",
                     "mean_draught"],
    "rpm": ["rpm", "me_rpm", "shaft_rpm", "engine_rpm"],
    "slip_pct": ["slip", "slip_pct", "propeller_slip", "apparent_slip"],
}


@dataclass
class IngestResult:
    df: pd.DataFrame
    column_map: dict[str, str]  # canonical -> source column actually used
    unmapped_sources: list[str]
    quality_flags: pd.DataFrame  # same index as df, boolean columns
    notes: list[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.df)

    def quality_summary(self) -> dict[str, int]:
        return {col: int(self.quality_flags[col].sum())
                for col in self.quality_flags.columns}

    def exclude_mask(self, columns: "list[str] | None" = None) -> "pd.Series":
        """Combine quality flags into one boolean mask (True == exclude row).

        By default uses flags that indicate the row is unusable for analysis
        (non-positive / implausible distance, speed or FOC). Pass `columns` to
        choose which flags count.
        """
        if columns is None:
            columns = [
                "distance_nonpositive", "distance_implausible",
                "speed_implausible", "foc_nonpositive", "foc_implausible",
            ]
        present = [c for c in columns if c in self.quality_flags.columns]
        if not present:
            return pd.Series(False, index=self.df.index)
        return self.quality_flags[present].any(axis=1)


def _normalise(name: str) -> str:
    """Normalise a column name for alias matching: lowercase, collapse
    spaces/underscores/hyphens to a single underscore, strip stray chars."""
    s = name.strip().lower()
    for ch in (" ", "-", ".", "/"):
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def _build_reverse_map(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    lowered = {_normalise(c): c for c in columns}
    column_map: dict[str, str] = {}
    used_sources: set[str] = set()
    for canonical, aliases in CANONICAL_FIELDS.items():
        for alias in aliases:
            norm_alias = _normalise(alias)
            if norm_alias in lowered:
                column_map[canonical] = lowered[norm_alias]
                used_sources.add(lowered[norm_alias])
                break
    unmapped = [c for c in columns if c not in used_sources]
    return column_map, unmapped


def ingest_dataframe(raw: pd.DataFrame) -> IngestResult:
    """Map a raw noon-report DataFrame onto the canonical schema.

    Returns the canonicalised frame plus a parallel quality-flag frame.
    No rows are dropped; suspicious rows are flagged for the caller to decide.
    """
    notes: list[str] = []
    column_map, unmapped = _build_reverse_map(list(raw.columns))

    out = pd.DataFrame(index=raw.index)
    for canonical, source in column_map.items():
        out[canonical] = raw[source]

    # --- type coercion ---
    if "report_date" in out:
        out["report_date"] = pd.to_datetime(out["report_date"], errors="coerce")
    numeric_fields = [
        "distance_nm", "speed_kn", "me_foc_t", "aux_foc_t", "total_foc_t",
        "wind_force_bf", "draft_mean_m", "rpm", "slip_pct",
    ]
    for f in numeric_fields:
        if f in out:
            out[f] = pd.to_numeric(out[f], errors="coerce")

    # Derive total_foc if missing but components present
    if "total_foc_t" not in out and {"me_foc_t", "aux_foc_t"} <= set(out.columns):
        out["total_foc_t"] = out["me_foc_t"].fillna(0) + out["aux_foc_t"].fillna(0)
        notes.append("Derived total_foc_t from me_foc_t + aux_foc_t.")

    # --- quality flags (do not mutate data) ---
    flags = pd.DataFrame(index=out.index)
    if "distance_nm" in out:
        flags["distance_nonpositive"] = ~(out["distance_nm"] > 0)
        flags["distance_implausible"] = out["distance_nm"] > 1000  # >1000nm/day
    if "speed_kn" in out:
        flags["speed_implausible"] = (out["speed_kn"] < 0) | (out["speed_kn"] > 40)
    if "total_foc_t" in out:
        flags["foc_nonpositive"] = ~(out["total_foc_t"] > 0)
        flags["foc_implausible"] = out["total_foc_t"] > 400  # >400 t/day
    if "report_date" in out:
        flags["date_unparseable"] = out["report_date"].isna()

    # cross-field consistency: implied speed vs reported speed
    if {"distance_nm", "speed_kn"} <= set(out.columns):
        implied_speed = (out["distance_nm"] / 24.0).replace([float("inf"), float("-inf")], pd.NA)
        deviation = (implied_speed - out["speed_kn"]).abs()
        flags["speed_distance_mismatch"] = deviation > 3.0  # >3 kn discrepancy

    if not column_map:
        notes.append(
            "WARNING: no columns could be mapped to the canonical schema. "
            "Check that the input has recognisable noon-report headers."
        )

    return IngestResult(
        df=out,
        column_map=column_map,
        unmapped_sources=unmapped,
        quality_flags=flags,
        notes=notes,
    )


def ingest_csv(path: str) -> IngestResult:
    raw = pd.read_csv(path)
    return ingest_dataframe(raw)
