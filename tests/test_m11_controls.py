"""M1.1 workbook and cross-projection diagnostics, fully synthetic fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_market_au.data_foundation.m11_controls import (
    ALL_MOTOR_VEHICLES, ALL_SECTIONS, STATE_HEADERS,
    extract_workbook_controls, write_controls,
)
from insurance_market_au.data_foundation.m11_marginals import (
    MARGINS, aggregate_source_marginals, available_margins,
    compare_groups, workbook_state_type_anchor,
)


def fake_workbook(path: Path, *, change_header: bool = False, mismatch: bool = False) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Table 1"
    sheet["B3"] = "Road vehicles Australia, 31 January 2026"
    sheet["B4"] = "Released: 12 October 2026"
    sheet["B8"] = "Year"
    for i, name in enumerate(STATE_HEADERS, 3):
        sheet.cell(row=8, column=i, value=name)
    if change_header:
        sheet["C8"] = "Another place"
    for index, name in enumerate(ALL_SECTIONS):
        row = 10 + index * 2
        sheet.cell(row=row, column=3, value=name)
        sheet.cell(row=row + 1, column=2, value=2026)
        for col in range(3, 12):
            # Ten vehicle categories × eight states → 80 vehicles total.
            # Each class cell is 1, each national class total is 8,
            # and the overall grand total is 80.
            value = (10 if col < 11 else 80) if name == ALL_MOTOR_VH else (
                1 if col < 11 else 8
            )
            if mismatch and name == "Passenger vehicles" and col == 11:
                value = 9
            sheet.cell(row=row + 1, column=col, value=value)
    wb.save(path)


ALL_MOTOR_VH = ALL_MOTOR_VEHICLES


def test_workbook_controls_are_state_class_specific(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    fake_workbook(path)
    controls = extract_workbook_controls(path, expected_sha=None, expected_national_total=80)
    assert controls["national_total"] == 80
    assert len(controls["controls"]) == 99
    assert controls["state_count"] == 8
    assert controls["vehicle_type_count"] == 10
    assert len(workbook_state_type_anchor(controls)) == 80
    assert all(x["delta_sum_minus_published"] == 0 for x in controls["internal_consistency"])
    passenger_nsw = next(c for c in controls["controls"]
                         if c["state"] == "NSW" and c["vehicle_type"] == "Passenger vehicles")
    assert passenger_nsw["source_cell"] == "C11"
    assert passenger_nsw["vehicles"] == 1
    output, csv = write_controls(controls, tmp_path / "out")
    assert json.loads(output.read_text())["national_total"] == 80
    assert len(csv.read_text().splitlines()) == 100  # header + 99 cells


def test_workbook_wrong_header_or_sha_fails(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    fake_workbook(path, change_header=True)
    with pytest.raises(ValueError, match="heading drift"):
        extract_workbook_controls(path, expected_sha=None, expected_national_total=80)
    fake_workbook(path)
    with pytest.raises(ValueError, match="SHA-256"):
        extract_workbook_controls(path, expected_sha="1" * 64, expected_national_total=80)


def test_workbook_internal_residual_retained_not_forced(tmp_path: Path) -> None:
    path = tmp_path / "test.xlsx"
    fake_workbook(path, mismatch=True)
    controls = extract_workbook_controls(path, expected_sha=None, expected_national_total=80)
    item = next(x for x in controls["internal_consistency"]
                if x["axis"] == "states" and x["vehicle_type"] == "Passenger vehicles")
    assert item["delta_sum_minus_published"] == -1
    assert controls["national_total"] == 80


def test_missing_group_not_mistaken_for_zero() -> None:
    state_type = next(x for x in MARGINS if x.name == "state_vehicle_type")
    original = {("NSW", "Passenger vehicles"): [100, 0, 0],
                ("Vic", "Passenger vehicles"): [10, 0, 0]}
    candidate = {("NSW", "Passenger vehicles"): [101, 0, 0],
                 ("Tas", "Passenger vehicles"): [0, 0, 1]}
    r = compare_groups(state_type, original, candidate,
                       reference="workbook_table1", candidate_id="B26-01")
    assert r["matched_comparable_groups"] == 1
    assert r["nonzero_differences"] == 1
    assert r["signed_sum_candidate_minus_anchor"] == 1
    assert r["anchor_only_groups_not_assumed_zero"] == 1
    assert r["candidate_only_groups_not_assumed_zero"] == 1
    assert r["constraint_policy"] == "diagnostic_publisher_anchored"


def test_suppressed_comparison_is_incomparable() -> None:
    state_type = next(x for x in MARGINS if x.name == "state_vehicle_type")
    k = ("NSW", "Passenger vehicles")
    r = compare_groups(state_type, {k: [100, 0, 0]},
                       {k: [0, 1, 0]}, reference="workbook_table1", candidate_id="B26-01")
    assert r["matched_comparable_groups"] == 0
    assert r["matched_groups_with_missing_values"] == 1
    assert r["maximum_abs_difference"] is None


def test_registered_and_garaging_postcodes_are_distinct() -> None:
    specs = {x.name: x for x in MARGINS}
    r = specs["type_registered_postcode"]
    g = specs["type_garaging_postcode"]
    assert r.fields != g.fields
    assert r.geography_role != g.geography_role
    headers = ["vehicle_type", "state_abb", "registered_postcode",
               "garaging_postcode", "no_vehicles"]
    names = {m.name for m in available_margins(headers)}
    assert r.name in names and g.name in names
    assert "type_motive_power" not in names


def test_source_marginal_parquet_lineage_and_total_exclusion(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    from insurance_market_au.data_foundation.m1 import _schema

    meta = {
        "projection_id": "B26-03",
        "resource_id": "fake-source",
        "sha256": "f" * 64,
        "expected_rows": 3,
        "expected_published_total_rows": 1,
        "expected_detail_numeric_total": 10,
        "expected_headers": [
            "state_abb", "vehicle_type", "motive_power", "no_vehicles",
        ],
    }
    lineage = "bitre-2026:fake-source:ffffffffffff"
    common = dict(
        source_release_id=lineage, projection_id="B26-03",
        observation_date="2026-01-31", published_count_raw="",
        count_status="published_confidentialised_numeric",
        registered_postcode=None, garaging_postcode=None,
        manufacture_year=None, make=None, model=None,
        source_dimensions_json="{}",
    )
    entries = [
        dict(common, source_row=1, vehicle_count=10, is_published_total=False,
             vehicle_type="Passenger vehicles", registered_state="NSW", motive_power="Petrol"),
        dict(common, source_row=2, vehicle_count=0, is_published_total=False,
             vehicle_type="Passenger vehicles", registered_state="NSW", motive_power="Diesel"),
        dict(common, source_row=3, vehicle_count=10, is_published_total=True,
             vehicle_type="Total", registered_state="Total", motive_power="-"),
    ]
    path = tmp_path / "sample.parquet"
    pq.write_table(pa.Table.from_pylist(entries, schema=_schema()), path)
    margins, info = aggregate_source_marginals(path, meta, batch_size=1)
    assert info["published_detail_numeric_total"] == 10
    assert info["published_total_rows_excluded"] == 1
    assert info["published_zero_rows"] == 1
    assert margins["state_vehicle_type"][("NSW", "Passenger vehicles")] == [10, 0, 1]
    assert margins["type_motive_power"][("Passenger vehicles", "Diesel")] == [0, 0, 1]
    meta["resource_id"] = "other"
    with pytest.raises(ValueError, match="source release lineage"):
        aggregate_source_marginals(path, meta, batch_size=2)


def test_parquet_reference_date_drift_fails(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    from insurance_market_au.data_foundation.m1 import _schema
    meta = {
        "projection_id": "B26-03", "resource_id": "source", "sha256": "a" * 64,
        "expected_rows": 1, "expected_published_total_rows": 0,
        "expected_detail_numeric_total": 7,
        "expected_headers": ["vehicle_type", "state_abb", "no_vehicles"],
    }
    row = {
        "source_release_id": "bitre-2026:source:aaaaaaaaaaaa",
        "projection_id": "B26-03", "source_row": 1,
        "observation_date": "2025-01-31",
        "count_status": "published_confidentialised_numeric",
        "vehicle_count": 7, "is_published_total": False,
        "vehicle_type": "Passenger vehicles", "registered_state": "NSW",
    }
    f = tmp_path / "source.parquet"
    pq.write_table(pa.Table.from_pylist([row], schema=_schema()), f)
    with pytest.raises(ValueError, match="reference date drift"):
        aggregate_source_marginals(f, meta)
