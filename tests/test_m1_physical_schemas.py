"""Pinned BITRE 2026 observed physical headers and row-count evidence."""
from insurance_market_au.data_foundation.m1 import ROOT
import json


def test_pinned_2026_physical_contract() -> None:
    c = json.loads((ROOT / "catalog/acquisition/bitre-2026-physical-schemas.json").read_text())
    projections = c["projection_schemas"]
    assert len(projections) == 17
    assert {x["projection_id"] for x in projections} == {
        f"B26-{i:02d}" for i in range(1, 18)
    }
    assert sum(x["rows"] for x in projections) == 12181645
    assert all(x["detail_numeric_total"] == c["population_control"] for x in projections)
    assert all(x["published_total_rows"] == 1 for x in projections)
    assert all(x["nonnumeric_count_tokens"] == 0 for x in projections)
    assert all("no_vehicles" in x["headers"] for x in projections)
    assert all("vehicle_type" in x["headers"] for x in projections)
    assert c["population_control"] == 22771150
