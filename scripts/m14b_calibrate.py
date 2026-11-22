#!/usr/bin/env python3
"""M1.4b — non-destructive soft training-projection calibration.

After merging and running M1.3b:
  py -3 -m pip install -e ".[data,model,explore,dev]"
  py -3 scripts/m14b_calibrate.py

Optionally compare the baseline and the newly calibrated *candidate* on
the three independently withheld publisher projections:
  py -3 scripts/m14b_calibrate.py --validate-only
  py -3 scripts/m14b_calibrate.py --validate

The holdout is strictly evaluation-only and never determines fitting
targets or hyperparameters. No validation result promotes this exploratory
candidate to an approved market population.
"""
from __future__ import annotations

import argparse
import json
import sys

from insurance_market_au.data_foundation.m14b import (
    calibrate, compare_withheld_projections,
)


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rounds",type=int,default=4)
    p.add_argument("--relaxation",type=float,default=0.35)
    p.add_argument("--update-cap",type=float,default=1.6)
    p.add_argument("--relative-weight-cap",type=float,default=8.0)
    p.add_argument("--min-cell",type=int,default=10)
    p.add_argument("--min-scope",type=int,default=100)
    p.add_argument("--min-coverage",type=float,default=0.15)
    p.add_argument("--validate",action="store_true",
                   help="Optional heldout comparison AFTER candidate has been fitted")
    p.add_argument("--validate-only",action="store_true",
                   help="Use withheld sources to compare EXISTING baseline and candidate; never refit")
    args=p.parse_args()
    try:
        if not args.validate_only:
            result=calibrate(
                rounds=args.rounds,relaxation=args.relaxation,
                update_cap=args.update_cap,
                relative_weight_cap=args.relative_weight_cap,
                min_cell=args.min_cell,min_scope=args.min_scope,
                min_coverage=args.min_coverage,
            )
            start=result["calibration"]["training_objectives_before"]
            end=result["calibration"]["training_objectives_after"]
            print(json.dumps({
                "status":result["status"],
                "rows":result["calibrated_rows"],
                "expected_vehicles":round(result["calibrated_expected_mass"],3),
                "original_fourway_max_error":result["max_fourway_mass_residual"],
                "training_source_count":len(result["training_source_ids"]),
                "train_objectives":[{
                    "projection":a["source_id"],
                    "before":a["within_scope_comparable_conditional_MAE_fraction"],
                    "after":b["within_scope_comparable_conditional_MAE_fraction"],
                    "eligible_scopes":a["eligible_scopes"],
                    "source_coverage_on_sample":a["published_scope_mass_fraction_on_sample_support"],
                } for a,b in zip(start,end)],
                "candidate_parquet":result["calibrated_sample"],
                "calibration_report":"data/reports/m14b/calibration.json",
                "warning":"This is a training-soft-calibrated candidate; missing source combinations and disclosure uncertainty remain.",
            },indent=2))
        if args.validate or args.validate_only:
            validation=compare_withheld_projections()
            print(json.dumps({
                "status":validation["status"],
                "comparison":validation["comparison"],
                "report":"data/reports/m14b/heldout-comparison.json",
                "warning":"Published aggregate diagnostics only, not physical-vehicle truth; no automatic population release.",
            },indent=2))
    except (OSError,ValueError,KeyError,RuntimeError,MemoryError) as exc:
        print(f"M1.4b safely stopped: {exc}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
