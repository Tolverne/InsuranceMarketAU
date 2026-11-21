"""M1.4a tests: independent published holdout, audit gates and Monte Carlo isolation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from insurance_market_au.data_foundation import m13b, m14
from insurance_market_au.data_foundation.m1 import _schema

# The neighbouring M1.3b test uses a deliberately tiny, non-identifying,
# synthetic two-vehicle-attribute fixture and source-specific pinned hashes.
from test_m13b_conditional import install_fixtures


def prepared(tmp_path: Path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    inventory = install_fixtures(tmp_path, monkeypatch)
    source = {
        "projection_id": "B26-14",
        "resource_id": "fixture-holdout-B26-14",
        "sha256": "c"*64,
        "expected_rows": 2,
        "expected_detail_numeric_total": 22_771_150,
        "expected_published_total_rows": 0,
    }
    inventory["B26-14"] = source
    cases = [
        ("NSW", "Passenger vehicles", "1965", "Petrol", "HOLDEN", "EH", 1_000_000),
        ("Vic", "Passenger vehicles", "2020", "Electric", "TESLA", "MODEL 3", 21_771_150),
    ]
    items = []
    for i, (state, klass, year, fuel, make, model, amount) in enumerate(cases, 1):
        items.append({
            "source_row": i,
            "projection_id": "B26-14",
            "source_release_id": "bitre-2026:fixture-holdout-B26-14:cccccccccccc",
            "observation_date": "2026-01-31",
            "vehicle_count": amount,
            "count_status": "published_confidentialised_numeric",
            "is_published_total": False,
            "source_dimensions_json": "{}",
            "registered_state": state, "vehicle_type": klass,
            "manufacture_year": year, "motive_power": fuel,
            "make": make, "model": model,
        })
    source_file = m13b._stage_path(tmp_path, source)
    source_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(items, schema=_schema()), source_file)
    monkeypatch.setattr(m14, "load_bitre_catalog", lambda root: list(inventory.values()))
    return inventory


def test_audit_current_is_independent_and_preserves_viewer_output(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    m13b.build_weighted_sample(tmp_path, rows=21, seed=11)
    sample_path = tmp_path / m13b.PATH_ROWS
    original_bytes = sample_path.read_bytes()
    original_report = (tmp_path / m13b.PATH_REPORT).read_bytes()
    r = m14.audit_current(tmp_path)
    assert r["heldout_source"]["id"] == "B26-14"
    assert r["heldout_source"]["holdout_used_for_sampler"] is False
    assert r["sample"]["sample_rows"] == 21
    assert r["sample"]["four_way_support_cells"] == 2
    assert r["sample"]["max_four_way_mass_residual"] < 1e-5
    assert r["metrics"]["overall"]["published_cell_WAPE"] == pytest.approx(0, abs=1e-8)
    assert r["metrics"]["overall"]["sample_support_fraction"] == 1.0
    assert r["metrics"]["cohorts_overlap_do_not_add_them"]["before_1980"]["published_reference_mass"] == 1_000_000
    assert sample_path.read_bytes() == original_bytes
    assert (tmp_path / m13b.PATH_REPORT).read_bytes() == original_report
    assert (tmp_path / m14.CURRENT_REPORT).exists()


def test_baseline_fourway_invariant_detects_corrupted_sample(tmp_path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    prepared(tmp_path, monkeypatch)
    m13b.build_weighted_sample(tmp_path, rows=30, seed=12)
    file = tmp_path / m13b.PATH_ROWS
    records = pq.read_table(file).to_pylist()
    records[0]["expected_vehicle_weight"] *= 2
    pq.write_table(pa.Table.from_pylist(records, schema=m13b._sample_schema(pa)), file)
    with pytest.raises(ValueError, match="Four-way synthetic mass"):
        m14.audit_current(tmp_path)


def test_publication_threshold_requires_100_and_lineage_is_verified(tmp_path, monkeypatch):
    inventory = prepared(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="threshold >=100"):
        m14.read_heldout_reference(tmp_path, minimum_published=20)
    observed, metadata = m14.read_heldout_reference(tmp_path, minimum_published=100)
    assert len(observed) == 2
    assert metadata["excluded_below_threshold_rows"] == 0
    tampered = dict(inventory["B26-14"])
    tampered["resource_id"] = "wrong-release"
    inventory["B26-14"] = tampered
    with pytest.raises(ValueError, match="lineage"):
        m14.read_heldout_reference(tmp_path)


def test_zero_support_is_not_confused_with_a_true_zero():
    p = {
        ("Passenger vehicles","1965","Petrol","HOLDEN","EH"): 100,
        ("Passenger vehicles","1995","Petrol","HOLDEN","COMMODORE"): 300,
        ("Motorcycles","2020","Electric","TEST","BIKE"): 200,
    }
    fitted = {
        ("Passenger vehicles","1965","Petrol","HOLDEN","EH"): 50.0,
        ("Passenger vehicles","1995","Petrol","HOLDEN","COMMODORE"): 200.0,
        # Missing supported make/model is measured as a missed *published*
        # cell, not a physically absent vehicle.
        ("Motorcycles","2021","Electric","TEST","BIKE"): 400.0,
    }
    r = m14.compare_reference(p, fitted)
    assert r["overall"]["published_reference_mass"] == 600
    assert r["overall"]["sample_supported_source_cells"] == 2
    assert r["overall"]["published_cell_WAPE"] == pytest.approx(350/600)
    assert r["cohorts_overlap_do_not_add_them"]["before_1980"]["published_cell_WAPE"] == pytest.approx(.5)
    assert r["modelled_mass_on_non_comparable_keys"] == 400
    assert r["tuning_with_holdout"] is False
    assert r["segments"]["historic_make"] == []  # one source cell: small-group suppression


def test_seed_size_study_is_isolated_and_reports_monte_carlo_only(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    m13b.build_weighted_sample(tmp_path, rows=20, seed=7)
    baseline = (tmp_path / m13b.PATH_ROWS).read_bytes()
    baseline_manifest = (tmp_path / m13b.PATH_REPORT).read_bytes()
    result = m14.sensitivity(tmp_path, sizes=(20, 40), seeds=(7, 13))
    assert result["sample_sizes"] == [20, 40]
    assert len(result["runs"]) == 4
    assert len(result["summaries"]) == 10
    assert all(r["max_four_way_mass_residual"] < 1e-5 for r in result["runs"])
    assert all(r["heldout_B26_14_WAPE"] == pytest.approx(0,abs=1e-8) for r in result["runs"])
    assert all(s["independent_seeds"] == 2 for s in result["summaries"])
    assert all(s["sd_is_Monte_Carlo_only_not_model_confidence_interval"] for s in result["summaries"])
    assert (tmp_path / m13b.PATH_ROWS).read_bytes() == baseline
    assert (tmp_path / m13b.PATH_REPORT).read_bytes() == baseline_manifest
    assert (tmp_path / m14.SENSITIVITY_REPORT).is_file()
    assert not list((tmp_path/"data/processed/m14/replicates").glob("*.parquet"))


def test_rejects_duplicate_seeds_or_excessive_runs(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="1–12"):
        m14.sensitivity(tmp_path, sizes=(20,), seeds=(1, 1))
    with pytest.raises(ValueError, match="1–12"):
        m14.sensitivity(tmp_path, sizes=(20, 30, 40, 50, 60), seeds=(1,2,3))


def test_diagnostics_refuse_leaking_holdout_into_training(tmp_path, monkeypatch):
    prepared(tmp_path, monkeypatch)
    unsafe = dict(m14.TRAIN_SPECS)
    unsafe["B26-14"] = (("vehicle_type",), ("make",))
    monkeypatch.setattr(m14, "TRAIN_SPECS", unsafe)
    with pytest.raises(ValueError, match="Heldout"):
        m14.read_heldout_reference(tmp_path)


def test_pinned_m14_governance_matches_code():
    from insurance_market_au.data_foundation.m1 import ROOT
    policy = json.loads(
        (ROOT / "catalog/validation/m14-diagnostics-policy.json").read_text(encoding="utf-8")
    )
    assert policy["validation"]["independent_source"] == m14.HELDOUT_ID
    assert policy["validation"]["minimum_original_published_cell_count"] == m14.MIN_PUBLISHED
    assert policy["validation"]["fourway_max_count_error_tolerance"] == 1e-5
    assert set(policy["validation"]["excluded_training_source_ids"]) == set(m13b.HOLDOUT_SPECS)
    assert set(policy["sensitivity_predeclared"]["sizes"]) == {85000,220000}
    assert policy["market_release_gate"]["high_dimensional_model_validated"] is False
    assert policy["market_release_gate"]["commercial_addressable_market_approved"] is False
