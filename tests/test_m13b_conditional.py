"""M1.3b regression fixtures for source-conditioned weighted synthetic output.

No real person, QLD VIN prefix, licensed microdata or 2026 flows are loaded.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from insurance_market_au.data_foundation import m13b
from insurance_market_au.data_foundation.m1 import _schema


def install_fixtures(tmp_path: Path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    source_inventory = {}
    sample_rows = [
        dict(registered_state="NSW", vehicle_type="Passenger vehicles",
             manufacture_year="1965", motive_power="Petrol",
             make="HOLDEN", model="EH", registered_postcode="2000",
             garaging_postcode="2080"),
        dict(registered_state="Vic", vehicle_type="Passenger vehicles",
             manufacture_year="2020", motive_power="Electric",
             make="TESLA", model="MODEL 3", registered_postcode="3000",
             garaging_postcode="3050"),
    ]
    values = [1_000_000, 21_771_150]
    for source_id, (key_fields, outcome_fields) in m13b.TRAIN_SPECS.items():
        sha = ("a" if source_id == "B26-15" else "b") * 64
        # Use distinct UUID-like source IDs to check the lineage contract.
        resource_id = f"fixture-{source_id}"
        records = []
        for i, (row, mass) in enumerate(zip(sample_rows, values), 1):
            record = {
                "source_row": i,
                "projection_id": source_id,
                "source_release_id": f"bitre-2026:{resource_id}:{sha[:12]}",
                "observation_date": "2026-01-31",
                "vehicle_count": mass,
                "count_status": "published_confidentialised_numeric",
                "is_published_total": False,
                "source_dimensions_json": "{}",
            }
            record.update(row)
            records.append(record)
        desc = {
            "projection_id": source_id,
            "resource_id": resource_id,
            "sha256": sha,
            "expected_rows": len(records),
            "expected_detail_numeric_total": sum(values),
            "expected_published_total_rows": 0,
        }
        source_inventory[source_id] = desc
        path = m13b._stage_path(tmp_path, desc)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(records, schema=_schema()), path)

    monkeypatch.setattr(m13b, "load_bitre_catalog", lambda root: list(source_inventory.values()))
    base = {
        "registered_state": ["NSW", "Vic"],
        "vehicle_type": ["Passenger vehicles", "Passenger vehicles"],
        "manufacture_year": ["1965", "2020"],
        "motive_power": ["Petrol", "Electric"],
        "expected_synthetic_vehicles": values,
        "reference_date": ["2026-01-31", "2026-01-31"],
    }
    file = tmp_path/"data/processed/m13/joint-state-type-year-fuel.parquet"
    file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pydict(base), file)
    report = tmp_path/"data/reports/m13/pilot-validation.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "published_total_operational_anchor": m13b.TOTAL,
        "reference_date": "2026-01-31",
        "holdout_source": "B26-10",
        "joint_support_cells": 2,
    }), encoding="utf-8")
    return source_inventory


def test_pps_allocation_covers_every_positive_base_support_cell():
    rng = np.random.default_rng(2)
    values = np.array([0.5, 5.0, 25.0, 100.0])
    counts = m13b._allocations(values, 101, rng)
    assert int(counts.sum()) == 101
    assert all(counts > 0)
    assert counts[-1] > counts[0]
    with pytest.raises(ValueError, match="at least"):
        m13b._allocations(values, 3, rng)


def test_conditional_source_contract_and_holdout_source_isolation(tmp_path, monkeypatch):
    sources = install_fixtures(tmp_path, monkeypatch)
    assert not (set(m13b.TRAIN_SPECS) & set(m13b.HOLDOUT_SPECS))
    report = m13b.prepare_conditionals(tmp_path)
    assert set(report["sources"]) == set(m13b.TRAIN_SPECS)
    assert set(report["heldout_sources_excluded"]) == set(m13b.HOLDOUT_SPECS)
    assert Path(report["local_db_file"]).is_file()
    assert m13b.prepare_conditionals(tmp_path) == report
    # Failure on bad source lineage instead of falling back to unverified rows.
    other = sources["B26-15"].copy()
    other["resource_id"] = "tampered"
    sources["B26-15"] = other
    with pytest.raises(ValueError, match="lineage"):
        m13b.prepare_conditionals(tmp_path, rebuild=True)


def test_weighted_sample_preserves_original_fourway_exactly(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    install_fixtures(tmp_path, monkeypatch)
    report = m13b.build_weighted_sample(tmp_path, rows=101, seed=13)
    assert report["rows"] == 101
    assert report["training_projections"] == list(m13b.TRAIN_SPECS)
    assert report["heldout_projections_excluded_from_sampling"] == list(m13b.HOLDOUT_SPECS)
    assert report["source_microdata_linkage_performed"] is False
    data = pq.read_table(report["sample_file"]).to_pylist()
    assert len(data) == 101
    assert all(x["is_synthetic"] for x in data)
    assert set(x["make"] for x in data) == {"HOLDEN", "TESLA"}
    assert set(x["model"] for x in data) == {"EH", "MODEL 3"}
    assert set(x["registered_postcode"] for x in data) == {"2000", "3000"}
    assert set(x["garaging_postcode"] for x in data) == {"2080", "3050"}
    assert not any("VIN" in k.upper() for k in data[0])
    assert sum(x["expected_vehicle_weight"] for x in data) == pytest.approx(m13b.TOTAL)
    grouped = defaultdict(float)
    for x in data:
        grouped[x["registered_state"], x["vehicle_type"],
                x["manufacture_year"], x["motive_power"]] += x["expected_vehicle_weight"]
    assert grouped["NSW", "Passenger vehicles", "1965", "Petrol"] == pytest.approx(1_000_000)
    assert grouped["Vic", "Passenger vehicles", "2020", "Electric"] == pytest.approx(21_771_150)
    # Reg vs garage postcode roles are distinct and never forcibly equal.
    assert all(x["registered_postcode"] != x["garaging_postcode"] for x in data)


def test_weighted_sample_is_reproducible(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    install_fixtures(tmp_path, monkeypatch)
    a = m13b.build_weighted_sample(tmp_path, rows=25, seed=11)
    first = pq.read_table(a["sample_file"])
    b = m13b.build_weighted_sample(tmp_path, rows=25, seed=11)
    second = pq.read_table(b["sample_file"])
    assert first.equals(second)


def test_published_zero_is_not_structural_zero(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    install_fixtures(tmp_path, monkeypatch)
    m13b.prepare_conditionals(tmp_path)
    sampler = m13b.ConditionalSampler(tmp_path/m13b.PATH_DB, 13)
    try:
        choices, mass = sampler.lookup("B26-15", ("NSW", "Passenger vehicles", "1965"))
        assert choices == (("HOLDEN", "EH"),)
        assert mass.tolist() == [1_000_000.5]
        assert sampler.model("NSW", "Passenger vehicles", "1965", "Petrol", 1)[0] == ("HOLDEN", "EH")
        assert sampler.postcode("NSW", "Passenger vehicles", "1965",
                                "Petrol", "HOLDEN", "EH") == "2000"
    finally:
        sampler.close()


def test_missing_exact_conditional_falls_back_without_fake_record_join(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    install_fixtures(tmp_path, monkeypatch)
    m13b.prepare_conditionals(tmp_path)
    sampler = m13b.ConditionalSampler(tmp_path/m13b.PATH_DB, 23)
    try:
        model = sampler.model("ACT", "Passenger vehicles", "1965", "Petrol", 3)
        assert model == [("HOLDEN", "EH")] * 3
        assert sampler.fallbacks["model_fallback_B26-07"] == 3
        assert sampler.garage("ACT", "Passenger vehicles", "Petrol") == "UNSPECIFIED"
    finally:
        sampler.close()
