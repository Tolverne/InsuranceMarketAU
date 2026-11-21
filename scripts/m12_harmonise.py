#!/usr/bin/env python3
"""Profile or stage all existing state-level vehicle sources without downloading.

Example PowerShell:
  py -3 scripts/m12_harmonise.py --groups vic,sa,act --profile-only
  py -3 scripts/m12_harmonise.py --groups nsw --only-source nsw_usage_2026 --sample-rows 50 --profile-only
  py -3 scripts/m12_harmonise.py --groups vic,sa,act --parquet
"""
from __future__ import annotations
import argparse
import json
import sys
from insurance_market_au.data_foundation.m12 import run_m12


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--profile-only",action="store_true")
    modes.add_argument("--parquet",action="store_true")
    parser.add_argument("--groups",default="vic,nsw,sa,act,qld,qld_flows")
    parser.add_argument("--only-source")
    parser.add_argument("--sample-rows",type=int)
    parser.add_argument("--batch-rows",type=int,default=50000)
    parser.add_argument("--strict",action="store_true")
    args=parser.parse_args()
    groups={g.strip().lower() for g in args.groups.split(",") if g.strip()}
    try:
        result=run_m12(groups=groups,parquet=args.parquet,
                       limit_rows=args.sample_rows,batch_rows=args.batch_rows,
                       only_source=args.only_source,fail_on_error=args.strict)
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print(f"M1.2 failed safely: {exc}",file=sys.stderr)
        return 1
    print(json.dumps({
        "status":result["status"],"sources_processed":len(result["source_profiles"]),
        "failures":result["source_failures"],
        "notices":result["notices"],
        "rows_processed":result["all_source_rows_processed"],
        "stock_sources":result["stock_sources"],
        "flow_sources_excluded_from_stock":result["flow_sources_excluded_from_stock"],
        "partial_sample":result["sampled_partial_run"],
        "report":"data/reports/m12/source-profile-sample.json" if args.sample_rows else
                 "data/reports/m12/source-profile.json",
        "warning":"No automatic state-to-BITRE stock calibration or synthetic vehicle release"
    },ensure_ascii=False,indent=2))
    return 1 if result["source_failures"] else 0


if __name__=="__main__":
    raise SystemExit(main())
