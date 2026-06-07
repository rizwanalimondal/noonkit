"""
noonkit command-line interface.

Usage:
    noonkit analyze reports.csv --ship-type tanker --dwt 100000 --year 2024
    noonkit analyze reports.csv --no-cii            # performance only

Designed to give a useful, honest one-page readout from a single CSV.
"""

from __future__ import annotations

import argparse
import sys

from . import (
    FuelConsumption,
    calculate_cii,
    fit_speed_consumption,
    baseline_deviation,
    ingest_csv,
)
from .imo_reference import ShipType


def _print_quality(ingest_result) -> None:
    print(f"  Rows ingested: {ingest_result.n_rows}")
    print(f"  Mapped fields: {', '.join(sorted(ingest_result.column_map))}")
    if ingest_result.unmapped_sources:
        print(f"  Unmapped columns: {', '.join(ingest_result.unmapped_sources)}")
    qs = ingest_result.quality_summary()
    flagged = {k: v for k, v in qs.items() if v > 0}
    if flagged:
        print("  Data-quality flags:")
        for k, v in flagged.items():
            print(f"    - {k}: {v} row(s)")
    else:
        print("  Data-quality flags: none")
    for note in ingest_result.notes:
        print(f"  Note: {note}")


def cmd_analyze(args: argparse.Namespace) -> int:
    print(f"\n=== noonkit analysis: {args.csv} ===\n")
    result = ingest_csv(args.csv)
    print("[ Ingestion ]")
    _print_quality(result)

    print("\n[ Performance ]")
    try:
        excl = result.exclude_mask()
        baseline = args.baseline_days if args.baseline_days and args.baseline_days > 0 else None
        model = fit_speed_consumption(
            result.df,
            bf_threshold=args.bf_threshold,
            good_weather_only=not args.all_weather,
            exclude_mask=excl,
            baseline_days=baseline,
        )
        print(f"  Speed-consumption model: {model.summary()}")
        dev = baseline_deviation(result.df, model, exclude_mask=excl)
        print(f"  Reports analysed: {dev.n_reports}")
        print(f"  Mean deviation from baseline: {dev.mean_deviation_pct:+.2f}%")
        if dev.trend_pct_per_30d is not None:
            print(f"  Fouling trend: {dev.trend_pct_per_30d:+.2f} pp / 30 days")
        for note in dev.notes:
            print(f"  Note: {note}")
    except ValueError as e:
        print(f"  Could not fit performance model: {e}")

    if not args.no_cii:
        print("\n[ CII compliance ]")
        try:
            total_dist = float(result.df["distance_nm"].clip(lower=0).sum())
            total_foc = float(result.df["total_foc_t"].clip(lower=0).sum())
            cii = calculate_cii(
                ship_type=ShipType(args.ship_type),
                dwt=args.dwt,
                gt=args.gt,
                distance_nm=total_dist,
                fuels=[FuelConsumption(args.fuel_type, total_foc)],
                year=args.year,
            )
            print(f"  {cii.summary()}")
            print(f"  Compliant (C or better): {cii.is_compliant}")
            print(f"  Total distance: {total_dist:,.0f} nm   "
                  f"Total fuel: {total_foc:,.1f} t ({args.fuel_type})")
            for note in cii.notes:
                print(f"  Note: {note}")
        except (ValueError, KeyError) as e:
            print(f"  Could not compute CII: {e}")

    print("\nNote: outputs are estimates for planning, not verified compliance.\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="noonkit",
        description="Open analysis of ship noon reports: performance + IMO CII.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="Analyze a noon-report CSV")
    p.add_argument("csv", help="Path to noon-report CSV")
    p.add_argument("--ship-type", default="tanker",
                   choices=[s.value for s in ShipType])
    p.add_argument("--dwt", type=float, default=0.0, help="Deadweight tonnage")
    p.add_argument("--gt", type=float, default=0.0, help="Gross tonnage")
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--fuel-type", default="HFO")
    p.add_argument("--bf-threshold", type=float, default=4.0,
                   help="Max Beaufort for good-weather fit")
    p.add_argument("--baseline-days", type=int, default=30,
                   help="Fit clean-hull baseline on first N days (0 = whole series)")
    p.add_argument("--all-weather", action="store_true",
                   help="Fit on all weather, not just good-weather days")
    p.add_argument("--no-cii", action="store_true",
                   help="Skip CII calculation")
    p.set_defaults(func=cmd_analyze)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
