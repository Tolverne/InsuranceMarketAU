#!/usr/bin/env python3
"""M1.4a — evidence-first synthetic population diagnostics.

Run after M1.3b:
  py -3 scripts/m14_validate.py

Optionally measure Monte Carlo sampling sensitivity to predeclared seeds and
sample sizes, WITHOUT changing the current M1.3b explorer files:
  py -3 scripts/m14_validate.py --sensitivity --sizes 85000,220000 --seeds 17,53,91

The first command uses staged B26-14 from M1.0. This pipeline never tunes the
M1.3a/B model to B26-14 (or B26-16/B26-17) and never claims vehicle-level
truth. Metrics apply only to independently published B26-14 counts >= 100.
"""
from __future__ import annotations

import argparse
import json
import sys

from insurance_market_au.data_foundation.m14 import audit_current, sensitivity


def _integers(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(v.strip()) for v in value.split(",") if v.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("At least one integer is needed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-published", type=int, default=100,
                        help="At least 100; exclude smaller confidentialised publication cells")
    parser.add_argument("--sensitivity", action="store_true",
                        help="Additionally generate independent local seed/sample-size replications")
    parser.add_argument("--sensitivity-only", action="store_true",
                        help="Run sensitivity without rebuilding current sample diagnostics")
    parser.add_argument("--sizes", type=_integers, default=(85000, 220000))
    parser.add_argument("--seeds", type=_integers, default=(17, 53, 91))
    parser.add_argument("--retain-replicates", action="store_true",
                        help="Retain separate synthetic replicate Parquet files under local data/")
    args = parser.parse_args()
    try:
        if not args.sensitivity_only:
            result = audit_current(minimum_published=args.minimum_published)
            s = result["metrics"]["overall"]
            print(json.dumps({
                "pipeline": result["pipeline"],
                "status": result["status"],
                "independent_holdout": result["heldout_source"]["id"],
                "source_published_count_threshold": result["heldout_source"]["threshold"],
                "synthetic_sample_rows": result["sample"]["sample_rows"],
                "fourway_max_count_error": result["sample"]["max_four_way_mass_residual"],
                "published_cell_WAPE": s["published_cell_WAPE"],
                "published_cell_coverage": s["sample_support_fraction"],
                "pre_1980_WAPE": result["metrics"]["cohorts_overlap_do_not_add_them"]["before_1980"]["published_cell_WAPE"],
                "report": "data/reports/m14/current-diagnostics.json",
                "warning": "Publisher-projection diagnostic only; not physical vehicle truth",
            }, indent=2))
        if args.sensitivity or args.sensitivity_only:
            sensitivity_report = sensitivity(
                sizes=args.sizes, seeds=args.seeds,
                minimum_published=args.minimum_published,
                retain_samples=args.retain_replicates,
            )
            print(json.dumps({
                "status": sensitivity_report["status"],
                "replicate_runs": len(sensitivity_report["runs"]),
                "sample_sizes": sensitivity_report["sample_sizes"],
                "seed_count": len(sensitivity_report["predeclared_seeds"]),
                "report": "data/reports/m14/sampling-sensitivity.json",
                "warning": "Across-seed standard deviation measures Monte Carlo variance only",
            }, indent=2))
    except (OSError, ValueError, KeyError, RuntimeError, MemoryError) as exc:
        print(f"M1.4a diagnostics stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
