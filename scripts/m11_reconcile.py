#!/usr/bin/env python3
"""M1.1 — authoritative BITRE Table 1 controls and marginal diagnostics.

Run from repository root after M1.0 has produced local Parquet staging:
  py -3 scripts/m11_reconcile.py --selected B26-01,B26-02,B26-03
  py -3 scripts/m11_reconcile.py

Full run streams all 17 already staged local Parquet files. It does not
download files, publish any raw bytes or generate synthetic vehicles.
"""
from __future__ import annotations

import argparse
import json
import sys

from insurance_market_au.data_foundation.m11_marginals import run_m11


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", help="Comma-separated subset of B26-01,...,B26-17")
    parser.add_argument("--batch-size", type=int, default=32768)
    parser.add_argument("--no-detailed-csv", action="store_true",
                        help="Write compact JSON report only, omitting detailed paired CSV residuals")
    args = parser.parse_args()
    selected = ({x.strip().upper() for x in args.selected.split(",") if x.strip()}
                if args.selected else None)
    try:
        controls, report = run_m11(
            selected=selected, batch_size=args.batch_size,
            with_details=not args.no_detailed_csv,
        )
    except (FileNotFoundError, ValueError, RuntimeError, OSError, KeyError) as exc:
        print(f"M1.1 stopped without claiming calibration: {exc}", file=sys.stderr)
        return 1
    label = "full" if report["complete_17"] else "pilot"
    print(json.dumps({
        "status": report["status"],
        "national_workbook_control": controls["national_total"],
        "workbook_control_cells": len(controls["controls"]),
        "book_internal_checks_nonzero": sum(
            x["delta_sum_minus_published"] != 0
            for x in controls["internal_consistency"]
        ),
        "sources_analysed": report["sources_analysed"],
        "marginal_comparisons": report["comparison_count"],
        "comparisons_with_discrepancies": report["comparison_nonzero_count"],
        "report": f"data/reports/m1/bitre-2026-m11-{label}-reconciliation.json",
        "controls": "data/processed/m1/controls/bitre-2026-table1-controls.json",
        "detailed_residuals": report["local_detail_comparisons_csv"],
        "IMPORTANT": "Diagnostics only. Confidentialised counts are not exact vehicle microdata.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
