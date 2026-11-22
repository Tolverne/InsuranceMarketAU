#!/usr/bin/env python3
"""M1.5 — freeze and query versioned synthetic population research releases.

  py -3 scripts/m15_release.py --publish baseline
  py -3 scripts/m15_release.py --publish candidate
  py -3 scripts/m15_release.py --publish both
  py -3 scripts/m15_release.py --list
  py -3 scripts/m15_release.py --verify pop-20260131-<24 hex chars>
  py -3 scripts/m15_release.py --pin pop-20260131-<24 hex chars>
  py -3 scripts/m15_release.py --aggregate pop-20260131-<24 hex chars> --group-by registered_state
  py -3 scripts/m15_release.py --aggregate pop-20260131-<24 hex chars> --group-by make --filter registered_state=QLD

"Published" means FROZEN LOCAL RESEARCH ASSET, NOT approved market truth.
No AWS/S3 upload, pricing-platform mutation or production market release.
"""
from __future__ import annotations

import argparse
import json
import sys

from insurance_market_au.data_foundation.m1 import ROOT
from insurance_market_au.population import (
    PopulationStore, list_populations, publish_population, verify_population,
)
from insurance_market_au.population.provider import FILTER_DIMS


def _filters(specs: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for value in specs:
        if "=" not in value:
            raise ValueError("Filters must use field=value")
        key, option = value.split("=", 1)
        if key not in FILTER_DIMS or not option:
            raise ValueError(f"Invalid population filter: {value}")
        result.setdefault(key, []).append(option)
    return result


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument("--publish", choices=("baseline","candidate","both"))
    action.add_argument("--list", action="store_true")
    action.add_argument("--verify", metavar="RELEASE_ID")
    action.add_argument("--pin", metavar="RELEASE_ID")
    action.add_argument("--aggregate", metavar="RELEASE_ID")
    action.add_argument("--preview", metavar="RELEASE_ID")
    p.add_argument("--group-by", default="", help="Comma-separated geographic/vehicle dimensions (max 3)")
    p.add_argument("--filter", action="append", default=[],
                   help="Exact category filter field=value; repeat to allow multiple values")
    p.add_argument("--max-groups", type=int, default=20)
    p.add_argument("--limit", type=int, default=25)
    args=p.parse_args()
    try:
        if args.publish:
            kinds=("baseline","candidate") if args.publish=="both" else (args.publish,)
            results=[]
            for kind in kinds:
                result=publish_population(kind=kind)
                results.append({
                    "model_kind":kind,
                    "release_id":result["release_id"],
                    "created":result["created"],
                    "rows":result["physical_checks"]["synthetic_rows"],
                    "expected_vehicles":result["physical_checks"]["expected_vehicles"],
                    "fourway_max_count_difference":result["physical_checks"]["maximum_fourway_count_residual"],
                    "storage_directory":result["directory"],
                    "commercial_use_approved":False,
                })
            print(json.dumps(results,indent=2,allow_nan=False))
        elif args.list:
            print(json.dumps(list_populations(),indent=2,allow_nan=False))
        elif args.verify:
            result=verify_population(ROOT,args.verify)
            print(json.dumps({
                "release_id":result["release_id"],
                "verified":result["verified"],
                "model_version":result["manifest"]["synthesis"]["model_version"],
                "row_count":result["physical_checks"]["synthetic_rows"],
                "expected_vehicles":result["physical_checks"]["expected_vehicles"],
                "commercial_use_approved":False,
            },indent=2,allow_nan=False))
        else:
            release_id=args.pin or args.aggregate or args.preview
            store=PopulationStore(release_id)
            if args.pin:
                result=store.pin()
            elif args.preview:
                result=store.preview(limit=args.limit,filters=_filters(args.filter))
            else:
                dimensions=tuple(s for s in args.group_by.split(",") if s)
                result=store.aggregate(
                    group_by=dimensions,filters=_filters(args.filter),
                    max_groups=args.max_groups,
                )
            print(json.dumps(result,indent=2,allow_nan=False))
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,MemoryError,ImportError) as exc:
        print(f"M1.5 release manager stopped safely: {exc}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
