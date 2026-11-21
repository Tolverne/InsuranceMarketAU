#!/usr/bin/env python3
"""M1.3b weighted make/model + registered and garaging postcode explorer build.

Already completed M1.0 / M1.3a provide all the required local Parquet.
  py -3 scripts/m13b_expand.py --rows 220000 --seed 42
  py -3 scripts/m13b_expand.py --prepare-only
Rebuild source conditionals after a publisher revision (pinned M1.0 SHA first):
  py -3 scripts/m13b_expand.py --rows 220000 --rebuild-conditionals

Unlike the four-way base joint, additional make/model/postcode filters are
stochastic conditional estimates; no source row-level linkage is asserted.
"""
from __future__ import annotations

import argparse
import json
import sys

from insurance_market_au.data_foundation.m13b import build_weighted_sample, prepare_conditionals, validate_holdout_margins


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=220000,
                        help="Number of weighted synthetic POC rows, minimum 64,008 for official release")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validate-only", action="store_true", help="Read completed weighted synthetic sample and check three independent BITRE holdout projections")
    parser.add_argument("--validate", action="store_true", help="After rebuilding the sample, validate against heldout B26-14/16/17")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Build verified conditional source index without sampling")
    parser.add_argument("--rebuild-conditionals", action="store_true",
                        help="Re-read and verify all pinned M1.0 source files into a new SQLite index")
    args = parser.parse_args()
    try:
        if args.validate_only:
            result = validate_holdout_margins()
            print(json.dumps({"status": result["validation_status"],
                              "holdout_checks": result["heldout_validation"],
                              "report": "data/reports/m13b/validation.json"}, indent=2))
        elif args.prepare_only:
            record = prepare_conditionals(rebuild=args.rebuild_conditionals)
            print(json.dumps({
                "status": "conditional_index_ready",
                "training_projections": list(record["sources"]),
                "heldout_projections": record["heldout_sources_excluded"],
                "local_db_file": record["local_db_file"],
            }, indent=2))
        else:
            report = build_weighted_sample(rows=args.rows, seed=args.seed,
                                           rebuild_conditionals=args.rebuild_conditionals)
            if args.validate:
                report = validate_holdout_margins()
            print(json.dumps({
                "status": report["status"],
                "weighted_rows": report["rows"],
                "national_expected_registration_count": round(report["weighted_total_expected"], 3),
                "fourway_support_preserved": report["exact_fourway_control_in_sample"],
                "make_model_fallbacks": report["quality"]["fallback_counts"],
                "sample_file": report["sample_file"],
                "report": "data/reports/m13b/validation.json",
                "warning": "Estimated filters, NOT joined vehicle records; registered and garaging postcode relationships unobserved.",
            }, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError, MemoryError) as exc:
        # A failed preparation must exit non-zero rather than claim a passed
        # calibration; atomic .partial outputs are removed by the model.
        print(f"M1.3b safely stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
