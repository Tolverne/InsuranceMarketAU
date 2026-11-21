"""M1.0 synthetic fixtures: independent dimensions, suppression and exact provenance."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from insurance_market_au.data_foundation.m1 import (
    count_value, is_published_total, mapped_columns, profile_projection, reconcile_profiles, sha256_file,
)


def _resource(path: Path, id: str, dimensions: list[str]) -> dict:
    return {
        "projection_id": id, "resource_id": "invented-fixture",
        "sha256": sha256_file(path), "postcode_role": None,
        "expected_dimensions": dimensions,
    }


def test_count_tokens_and_numeric_zero() -> None:
    assert count_value("0") == ("published_confidentialised_numeric", 0)
    assert count_value("1,200") == ("published_confidentialised_numeric", 1200)
    assert count_value("..") == ("suppressed_or_not_numeric", None)
    assert count_value("") == ("suppressed_or_not_numeric", None)
    assert count_value("UNDISCLOSED") == ("unrecognized_count_token", None)
    with pytest.raises(ValueError, match="negative"):
        count_value("-4")


def test_expected_physical_aliases() -> None:
    mapping, extra = mapped_columns(
        ["state_abb", "vehicle_type", "year_of_manufacture", "no_vehicles", "unmapped"])
    assert mapping["registered_state"] == "state_abb"
    assert mapping["manufacture_year"] == "year_of_manufacture"
    assert extra == ["unmapped"]


def test_profile_retains_unrecognized_tokens_not_zero(tmp_path: Path) -> None:
    f = tmp_path / "fake.csv"
    with f.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["state_abb", "vehicle_type", "year_of_manufacture", "no_vehicles"])
        writer.writerow(["NSW", "Passenger vehicles", "1971", "11"])
        writer.writerow(["NSW", "Passenger vehicles", "1972", "0"])
        writer.writerow(["NSW", "Passenger vehicles", "1973", ".."])
        writer.writerow(["NSW", "Passenger vehicles", "1974", "???"])
    out = profile_projection(f, _resource(f, "B26-01", ["vehicle_type","registered_state","manufacture_year"]))
    assert out["rows"] == 4
    assert out["numeric_rows"] == 2
    assert out["numeric_total"] == 11
    assert out["zero_numeric_rows"] == 1
    assert out["suppressed_rows"] == 1
    assert out["unrecognized_count_rows"] == 1
    key = json.dumps(["NSW", "Passenger vehicles"])
    assert out["state_vehicle_type_controls"][key] == {"sum_numeric": 11, "suppressed_cells": 2}


def test_no_count_header_fails(tmp_path: Path) -> None:
    file = tmp_path / "unrecognised.csv"
    file.write_text("vehicle_type,not_a_count\nPassenger,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown count field"):
        profile_projection(file, _resource(file, "B26-02", []))


def test_reconciliation_is_diagnostic() -> None:
    key = json.dumps(["NSW", "Passenger vehicles"])
    profiles = [
        {"projection_id": "B26-01", "status": "profiled",
         "state_vehicle_type_controls": {key: {"sum_numeric": 100, "suppressed_cells": 2}}},
        {"projection_id": "B26-03", "status": "profiled",
         "state_vehicle_type_controls": {key: {"sum_numeric": 99, "suppressed_cells": 0}}},
    ]
    result = reconcile_profiles(profiles)
    assert len(result["checks"]) == 1
    assert result["checks"][0]["delta"] == -1
    assert result["checks"][0]["suppressed_cells"] == 2
    assert result["checks"][0]["interpretable_as_exact_error"] is False


def test_parquet_preserves_original_raw_dimensions(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    file = tmp_path / "sample.csv"
    file.write_text(
        'vehicle_type,state_abb,year_of_manufacture,no_vehicles\n'
        'Passenger vehicles,NSW,1901,3\n'
        'Passenger vehicles,NSW,1902,..\n',
        encoding="utf-8",
    )
    target = tmp_path / "stage.parquet"
    result = profile_projection(file, _resource(file, "B26-01", []),
                                parquet_path=target, batch_rows=1)
    data = pq.read_table(target).to_pylist()
    assert result["rows"] == len(data) == 2
    assert data[0]["registered_state"] == "NSW"
    assert data[0]["manufacture_year"] == "1901"
    assert data[0]["vehicle_count"] == 3
    assert data[1]["vehicle_count"] is None
    assert data[1]["count_status"] == "suppressed_or_not_numeric"
    assert json.loads(data[1]["source_dimensions_json"]) == {
        "vehicle_type": "Passenger vehicles", "state_abb": "NSW",
        "year_of_manufacture": "1902",
    }
    assert not list(tmp_path.glob("*.partial"))


def test_total_categories_excluded_from_leaf_counts(tmp_path: Path) -> None:
    assert is_published_total({"vehicle_type": "Total", "state_abb": "-"}) is True
    assert is_published_total({"vehicle_type": "-", "motive_power": "-"}) is True
    assert is_published_total({"vehicle_type": "Passenger vehicles", "state_abb": "Total"}) is True
    assert is_published_total({"vehicle_type": "Passenger vehicles", "state_abb": "-"}) is False
    f = tmp_path / "with-grand-total.csv"
    f.write_text(
        "vehicle_type,state_abb,year_of_manufacture,no_vehicles\n"
        "Passenger vehicles,NSW,2020,11\n"
        "Total,-,-,11\n", encoding="utf-8"
    )
    p = profile_projection(f, _resource(f, "B26-01", []))
    assert p["numeric_total"] == 22  # Unfiltered source sum has duplication!
    assert p["detail_numeric_total"] == 11
    assert p["published_total_rows"] == 1
    assert p["published_total_numeric_total"] == 11
    assert len(p["state_vehicle_type_controls"]) == 1
