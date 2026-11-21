"""M1.1 authoritative publisher-level registration benchmarks from BITRE Table 1.

Read-only source extraction: no workbook edits or invented vehicle records.
The workbook reports *estimates*, not observed microdata. Keep its totals
distinct from confidentialised detail-extract marginal counts.
"""
from __future__ import annotations

import csv
from datetime import date
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from insurance_market_au.data_foundation.m1 import REFERENCE_DATE, ROOT, sha256_file

WORKBOOK_SHA256 = "e35996e412c58cdfd8ecf30d686bb852e4efd56b5cfbb9521af9b7cbda307e81"
WORKBOOK_URL = (
    "https://www.bitre.gov.au/sites/default/files/documents/"
    "bitre-road-vehicles-australia-january-2026.xlsx"
)
EXPECTED_NATIONAL_TOTAL = 22771150
PUBLICATION_DATE = "2026-10-12"
ALL_MOTOR_VEHICLES = "Total motor vehicles"
STATE_HEADERS = {
    "New South Wales": "NSW",
    "Victoria": "Vic",
    "Queensland": "Qld",
    "South Australia": "SA",
    "Western Australia": "WA",
    "Tasmania": "Tas",
    "Northern Territory": "NT",
    "Australian Capital Territory": "ACT",
    "Australia": "AUS",
}
VEHICLE_TYPES = (
    "Passenger vehicles",
    "Campervans",
    "Light commercial vehicles",
    "Light rigid trucks",
    "Heavy rigid trucks",
    "Articulated trucks",
    "Non-freight-carrying vehicles",
    "Light buses",
    "Heavy buses",
    "Motorcycles",
)
ALL_SECTIONS = (*VEHICLE_TYPES, ALL_MOTOR_VEHICLES)


def find_workbook(root: Path = ROOT) -> Path:
    directory = root / "data/raw/bitre" / REFERENCE_DATE
    matches = sorted(directory.glob(f"bitre-summary--{WORKBOOK_SHA256[:12]}.xlsx"))
    if len(matches) != 1:
        raise FileNotFoundError(
            "Official BITRE January 2026 workbook not found at "
            f"{directory}/bitre-summary--{WORKBOOK_SHA256[:12]}.xlsx. "
            "Run: py -3 scripts/download_vehicle_sources.py --groups bitre "
            "--only bitre_summary --download"
        )
    if sha256_file(matches[0]).lower() != WORKBOOK_SHA256:
        raise ValueError("BITRE summary workbook checksum mismatch; do not use different publication bytes")
    return matches[0]


def _coerce_count(value: Any, cell: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{cell}: boolean is not a registration count")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and value.replace(",", "").isdigit():
        number = int(value.replace(",", ""))
    else:
        raise ValueError(f"{cell}: nonnumeric/uncached workbook control {value!r}")
    if number < 0:
        raise ValueError(f"{cell}: negative registration count")
    return number


def _is_year(value: Any, year: int) -> bool:
    return value == year or (isinstance(value, str) and value.strip() == str(year))


def _state_header(row: tuple[Any, ...]) -> list[str]:
    actual = [str(x).strip() if x is not None else "" for x in row[2:11]]
    expected = list(STATE_HEADERS)
    if actual != expected:
        raise ValueError(f"BITRE Table 1 heading drift; got {actual!r}; expected {expected!r}")
    return actual


def extract_workbook_controls(
    path: Path, *, expected_sha: str | None = WORKBOOK_SHA256,
    expected_national_total: int | None = EXPECTED_NATIONAL_TOTAL,
) -> dict[str, Any]:
    """Extract 2026 8-state × 10-class matrix + national/aggregate controls.

    Source cells are retained for audit. Only Table 1 counts enter the stock
    control family: other workbook tables have different units (age, per-capita,
    trailer/plant population, or specific vehicle segments).
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError('Install workbook support: py -3 -m pip install -e ".[data]"') from exc

    digest = sha256_file(path)
    if expected_sha is not None and digest.lower() != expected_sha.lower():
        raise ValueError("BITRE workbook SHA-256 does not match pinned source release")
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        if "Table 1" not in workbook.sheetnames:
            raise ValueError("Missing BITRE Table 1")
        sheet = workbook["Table 1"]
        title = str(sheet["B3"].value or "")
        release = str(sheet["B4"].value or "")
        if "31 January 2026" not in title or "12 October 2026" not in release:
            raise ValueError(f"Unexpected workbook observation/publishing date: {title!r} / {release!r}")
        row8 = next(sheet.iter_rows(min_row=8, max_row=8, values_only=True))
        if str(row8[1]).strip() != "Year":
            raise ValueError("BITRE Table 1 year column no longer at B8")
        _state_header(row8)
        current_section: str | None = None
        seen: set[str] = set()
        controls: list[dict[str, Any]] = []
        for row_index, row in enumerate(sheet.iter_rows(min_row=10, values_only=True), start=10):
            # Table 1 has section labels in C and 2024/25/26 entries in B.
            text = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            yr = row[1] if len(row) > 1 else None
            if text in ALL_SECTIONS and yr is None:
                current_section = text
                continue
            if not _is_year(yr, 2026):
                continue
            if current_section not in ALL_SECTIONS:
                raise ValueError(f"Unexpected Table 1 vehicle-type section at row {row_index}: {current_section}")
            if current_section in seen:
                raise ValueError(f"Repeated Table 1 2026 vehicle-type section: {current_section}")
            seen.add(current_section)
            for i, (original_label, state) in enumerate(STATE_HEADERS.items(), start=3):
                cell = f"{_excel_column(i)}{row_index}"
                count = _coerce_count(row[i - 1], cell)
                controls.append({
                    "state": state,
                    "vehicle_type": current_section,
                    "vehicles": count,
                    "is_state_total": current_section == ALL_MOTOR_VEHICLES,
                    "is_national": state == "AUS",
                    "observation_date": REFERENCE_DATE,
                    "source_sheet": "Table 1",
                    "source_cell": cell,
                    "source_row": row_index,
                    "source_dimension_label": original_label,
                    "basis": "BITRE_published_summary_estimate",
                })
        missing = set(ALL_SECTIONS) - seen
        extra = seen - set(ALL_SECTIONS)
        if missing or extra or len(controls) != 99:
            raise ValueError(f"Missing/invalid 2026 workbook sections: missing={sorted(missing)}, extra={sorted(extra)}")
        keyed = {(c["state"], c["vehicle_type"]): c for c in controls}
        if len(keyed) != 99:
            raise ValueError("Duplicate state/class workbook controls")
        national = keyed[("AUS", ALL_MOTOR_VEHICLES)]["vehicles"]
        if expected_national_total is not None and national != expected_national_total:
            raise ValueError(f"National registration control has changed: {national} != {expected_national_total}")
        consistency = []
        for state in STATE_HEADERS.values():
            reported = keyed[(state, ALL_MOTOR_VEHICLES)]["vehicles"]
            summed = sum(keyed[(state, x)]["vehicles"] for x in VEHICLE_TYPES)
            consistency.append({
                "axis": "vehicle_types", "state": state,
                "reported_total": reported, "sum_categories": summed,
                "delta_sum_minus_published": summed - reported,
                "exact_consistency_not_assumed": True,
            })
        for vehicle_type in ALL_SECTIONS:
            reported = keyed[("AUS", vehicle_type)]["vehicles"]
            summed = sum(keyed[(state, vehicle_type)]["vehicles"]
                         for state in STATE_HEADERS.values() if state != "AUS")
            consistency.append({
                "axis": "states", "vehicle_type": vehicle_type,
                "reported_total": reported, "sum_categories": summed,
                "delta_sum_minus_published": summed - reported,
                "exact_consistency_not_assumed": True,
            })
        return {
            "contract": "bitre_table1_2026_v1",
            "status": "publisher_benchmark_extracted_not_calibrated",
            "source": "BITRE Road vehicles Australia January 2026",
            "source_url": WORKBOOK_URL,
            "source_file_sha256": digest,
            "source_workbook_sheet": "Table 1",
            "reference_date": REFERENCE_DATE,
            "published_date": PUBLICATION_DATE,
            "unit": "registered_motor_vehicles_not_policies",
            "national_total": national,
            "state_count": 8,
            "vehicle_type_count": 10,
            "controls": controls,
            "internal_consistency": consistency,
            "caveat": (
                "Official BITRE estimates, not true exact microdata. "
                "Grand/national and state/class controls are high-priority "
                "published anchors; lower-level projected cells require "
                "disclosure-aware reconciliation before hard calibration."
            ),
        }
    finally:
        workbook.close()


def _excel_column(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def write_controls(report: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "bitre-2026-table1-controls.json"
    temporary = directory / (output.name + ".partial")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    csv_path = directory / "bitre-2026-table1-controls.csv"
    csv_tmp = csv_path.with_name(csv_path.name + ".partial")
    try:
        with csv_tmp.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "state", "vehicle_type", "vehicles", "is_state_total", "is_national",
                "observation_date", "source_sheet", "source_cell", "source_row",
                "source_dimension_label", "basis",
            ])
            writer.writeheader()
            writer.writerows(report["controls"])
        os.replace(csv_tmp, csv_path)
    finally:
        csv_tmp.unlink(missing_ok=True)
    return output, csv_path
