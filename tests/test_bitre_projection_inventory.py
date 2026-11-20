"""Validate metadata-only projection structure; no fleet data asserted."""
import json
from pathlib import Path


def test_2026_bitre_inventory_shape() -> None:
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / "catalog/feasibility/bitre_2026_projections.json").read_text())
    entries = inventory["observations"]
    assert inventory["reference_date"] == "2026-01-31"
    assert len(entries) == 17
    assert {x["projection_id"] for x in entries} == {f"B26-{i:02d}" for i in range(1, 18)}
    assert all(len(x["dimensions"]) == len(set(x["dimensions"])) for x in entries)
    assert all(x["downloaded"] is False for x in entries)
    assert all(x["count_handling"] == "unknown_pending_explanatory_notes" for x in entries)


def test_role_specific_postcode_dimension() -> None:
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "catalog/feasibility/bitre_2026_projections.json").read_text())["observations"]
    for x in entries:
        dims = set(x["dimensions"])
        if "registered_postcode" in dims:
            assert x["postcode_role"] == "registered"
        elif "garaging_postcode" in dims:
            assert x["postcode_role"] == "garaging"
        else:
            assert x["postcode_role"] is None
    # No single public catalogue projection observes both registration and garaging postcode.
    assert not any({"registered_postcode", "garaging_postcode"} <= set(x["dimensions"]) for x in entries)
