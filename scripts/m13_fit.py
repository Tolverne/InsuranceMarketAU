#!/usr/bin/env python3
"""M1.3a — synthetic four-way national fleet pilot, January 2026.

Prerequisites (existing local data):
  py -3 -m pip install -e ".[data,model,dev]"
  py -3 scripts/m1_ingest.py --parquet           # already done in M1.0
  py -3 scripts/m11_reconcile.py                  # already done in M1.1

Run:
  py -3 scripts/m13_fit.py
  py -3 scripts/m13_fit.py --sample-size 25000 --seed 42

Outputs never go into public Git: data/processed/m13, data/reports/m13.
The sample is illustrative simulated attribute data, not verified vehicles.
"""
from __future__ import annotations
import argparse
import json
import sys

from insurance_market_au.data_foundation.m13 import run_m13


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--iterations",type=int,default=32)
    p.add_argument("--relaxation",type=float,default=0.35)
    p.add_argument("--pseudocount",type=float,default=2.0)
    p.add_argument("--max-support",type=int,default=500000)
    p.add_argument("--seed",type=int,default=20261121)
    p.add_argument("--sample-size",type=int,default=0,
                   help="Optional local simulated records, maximum 200000. No PII.")
    args=p.parse_args()
    try:
        result=run_m13(iterations=args.iterations,relaxation=args.relaxation,
                       pseudocount=args.pseudocount,max_support=args.max_support,
                       seed=args.seed,sample_size=args.sample_size)
    except (OSError,ValueError,RuntimeError,KeyError,MemoryError) as exc:
        print(f"M1.3a safely stopped: {exc}",file=sys.stderr)
        return 1
    print(json.dumps({
        "status":result["status"],
        "national_accounting_control":result["published_total_operational_anchor"],
        "joint_support_cells":result["joint_support_cells"],
        "training_sources":result["training_sources"],
        "excluded_holdout":result["holdout_source"],
        "baseline_holdout_WAPE":result["initial_holdout"]["overall_published_cell_wape"],
        "fitted_holdout_WAPE":result["fitted_holdout"]["overall_published_cell_wape"],
        "fitted_holdout_published_ge100_WAPE":result["fitted_holdout"]["wape_for_published_ge_100"],
        "report":"data/reports/m13/pilot-validation.json",
        "distribution":result["expected_joint_parquet"],
        "synthetic_sample":result["synthetic_sample_parquet"],
        "warning":"Partial four-attribute distribution; not a full make/model/location synthetic population."
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
