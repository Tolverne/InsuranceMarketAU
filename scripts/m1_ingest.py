#!/usr/bin/env python3
"""M1.0 — profile official BITRE 2026 aggregate resources and optionally stage Parquet.

Run from the repository root (after the M1 PR is merged):
  py -3 -m pip install -e ".[data,dev]"
  py -3 scripts/m1_ingest.py --profile-only
  py -3 scripts/m1_ingest.py --parquet

Optional pilot: --selected B26-01,B26-02,B26-03
Nothing is uploaded, committed, joined into microdata or called a calibrated release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from insurance_market_au.data_foundation.m1 import ROOT, run_m1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--profile-only", action="store_true",
                       help="Stream CSVs into local JSON profile report without PyArrow")
    flags.add_argument("--parquet", action="store_true",
                       help="Also create Parquet staging files with full raw source dimensions")
    parser.add_argument("--selected", type=str, default=None,
                        help="Comma-separated projection IDs for a partial pilot, e.g. B26-01,B26-03")
    parser.add_argument("--batch-rows", type=int, default=50000)
    parser.add_argument("--raw-dir", type=Path, help="Override location of data/raw folder")
    args = parser.parse_args()
    selected = ({x.strip().upper() for x in args.selected.split(",") if x.strip()}
                if args.selected else None)
    try:
        result = run_m1(ROOT, raw_root=args.raw_dir, parquet=args.parquet,
                        selected=selected, verify=True, batch_rows=args.batch_rows)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"M1 ingestion failed safely: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "projection_count": result["projection_count"],
        "complete_17": result["complete_17"],
        "outputs": result["outputs"],
        "total_rows": sum(p["rows"] for p in result["profiles"]),
        "suppressed_rows": sum(p["suppressed_rows"] for p in result["profiles"]),
        "unrecognised_count_rows": sum(p["unrecognized_count_rows"] for p in result["profiles"]),
        "reconciliation_checks": len(result["reconciliation"]["checks"]),
        "reconciliation_nonzero": result["reconciliation"]["checks_with_nonzero_delta"],
        "report": str(ROOT / "data/reports/m1/bitre-2026-profile.json"),
        "important": "Independent confidentialised aggregate projections only; NOT a synthetic population",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
