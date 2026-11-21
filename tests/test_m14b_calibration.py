"""M1.4b statistical, source-isolation, baseline, and holdout regression tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from insurance_market_au.data_foundation import m13b, m14, m14b
from insurance_market_au.data_foundation import m1
from test_m13b_conditional import install_fixtures
from test_m14_diagnostics import prepared


def fixture(root: Path, monkeypatch):
    inventory = prepared(root, monkeypatch)
    monkeypatch.setattr(m1, "load_bitre_catalog", lambda root: list(inventory.values()))
    # prepared() uses original staged, checksum-identified B26-14 as a
    # holdout; the calibration DB is still generated only from M1.3b.
    m13b.build_weighted_sample(root, rows=100, seed=42)
    return inventory


def test_step_moves_two_supported_source_choices_toward_soft_target():
    m=m14b.Margin(
        pid="B26-15",
        row_to_pair=np.array([0, 1], dtype=np.int32),
        pair_to_scope=np.array([0, 0], dtype=np.int32),
        source_count=np.array([80.0, 20.0]),
        published_scope_total=np.array([100.0]),
        eligible=np.array([True, True]),
        coverage=np.array([1.0]),
        scope_keys=1,
        pairs=2,
        positive_supported_cells=2,
        eligible_scopes=1,
        observed_source_mass_fraction_on_sample_support=1.0,
        eligible_row_count=2,
    )
    weights=np.array([50.0,50.0])
    before=m14b._soft_objective(m,weights)
    m14b._step(m,weights,relaxation=0.5,update_cap=2)
    m14b._reconcile_fourway(weights,np.array([0,0],dtype=np.int32),
                            np.array([100.0]))
    after=m14b._soft_objective(m,weights)
    assert weights[0] > 50.0
    assert weights[1] < 50.0
    assert weights.sum()==pytest.approx(100.0)
    assert (after["within_scope_comparable_conditional_MAE_fraction"] <
            before["within_scope_comparable_conditional_MAE_fraction"])


def test_source_index_forbids_all_heldout_projections(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    m13b.prepare_conditionals(tmp_path)
    import sqlite3
    with sqlite3.connect(f"file:{(tmp_path/m13b.PATH_DB).as_posix()}?mode=ro",uri=True) as con:
        for pid in ("B26-14","B26-16","B26-17"):
            with pytest.raises(ValueError,match="Holdout"):
                m14b._source_targets(con,pid,["[]"],["[]"])
        counts,scope_totals=m14b._source_targets(
            con,"B26-15",
            ['["NSW","Passenger vehicles","1965"]'],
            ['["HOLDEN","EH"]'],
        )
        assert counts.tolist()==[1_000_000.0]
        assert scope_totals.tolist()==[1_000_000.0]


def test_calibrate_retains_baseline_bytes_and_every_base_fourway_cell(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    fixture(tmp_path, monkeypatch)
    baseline_path=tmp_path/m13b.PATH_ROWS
    original=baseline_path.read_bytes()
    before_report=(tmp_path/m13b.PATH_REPORT).read_bytes()
    result=m14b.calibrate(tmp_path,rounds=2)
    assert result["calibrated_rows"]==100
    assert result["training_source_ids"]==list(m14b.ORDER)
    assert set(result["heldout_ids_strictly_excluded"])==set(m13b.HOLDOUT_SPECS)
    assert result["governance"]["automatic_promotion_to_production"] is False
    assert result["max_fourway_mass_residual"]<1e-5
    assert result["original_m13b_sha256"]!= ""
    assert baseline_path.read_bytes()==original
    assert (tmp_path/m13b.PATH_REPORT).read_bytes()==before_report
    baseline=pq.read_table(baseline_path)
    candidate=pq.read_table(result["calibrated_sample"])
    assert baseline.schema==candidate.schema
    assert baseline.num_rows==candidate.num_rows
    for col in baseline.column_names:
        if col!="expected_vehicle_weight":
            assert baseline[col].equals(candidate[col])
    assert sum(candidate["expected_vehicle_weight"].to_pylist())==pytest.approx(m13b.TOTAL)
    for a in result["calibration"]["training_objectives_before"]:
        assert a["not_full_source_WAPE"] is True
    assert all(x["missing_sample_keys_never_set_to_structural_zero"]
               for x in result["calibration"]["training_objectives_after"])


def test_two_calibrations_deterministic_with_identical_training_sources(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    fixture(tmp_path, monkeypatch)
    a=m14b.calibrate(tmp_path,rounds=3,
                     output_path=tmp_path/"candidate-a.parquet",
                     report_path=tmp_path/"candidate-a.json")
    b=m14b.calibrate(tmp_path,rounds=3,
                     output_path=tmp_path/"candidate-b.parquet",
                     report_path=tmp_path/"candidate-b.json")
    assert pq.read_table(a["calibrated_sample"]).equals(pq.read_table(b["calibrated_sample"]))
    assert a["max_fourway_mass_residual"]==pytest.approx(b["max_fourway_mass_residual"])


def test_independent_heldout_comparison_read_only_and_stale_guard(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow")
    inventory=fixture(tmp_path, monkeypatch)
    result=m14b.calibrate(tmp_path,rounds=2)
    candidate=Path(result["calibrated_sample"])
    candidate_bytes=candidate.read_bytes()
    # Only B26-14 is present in this miniature pinned-source fixture; the
    # other withheld sources never enter the model or this test.
    comparison=m14b.compare_withheld_projections(
        tmp_path,source_ids=("B26-14",),
    )
    assert comparison["training_source_ids"]==list(m14b.ORDER)
    assert comparison["independently_reserved_holdouts"]==["B26-14"]
    entry=comparison["comparison"][0]
    assert entry["holdout_never_used_for_fit"]
    assert entry["baseline_published_cell_WAPE"]==pytest.approx(0,abs=1e-8)
    assert entry["candidate_published_cell_WAPE"]==pytest.approx(0,abs=1e-8)
    assert candidate.read_bytes()==candidate_bytes
    m13b.build_weighted_sample(tmp_path,rows=101,seed=42)
    with pytest.raises(ValueError,match="stale"):
        m14b.compare_withheld_projections(tmp_path,source_ids=("B26-14",))


def test_rejects_incorrect_calibration_and_accidental_overwrite(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    baseline=tmp_path/m13b.PATH_ROWS
    with pytest.raises(ValueError,match="Invalid"):
        m14b.calibrate(tmp_path,rounds=0)
    with pytest.raises(ValueError,match="Invalid"):
        m14b.calibrate(tmp_path,min_coverage=1.1)
    with pytest.raises(ValueError,match="overwrite"):
        m14b.calibrate(tmp_path,output_path=baseline)
    with pytest.raises(ValueError,match="overwrit"):
        m14b.calibrate(tmp_path,report_path=tmp_path/m13b.PATH_REPORT)


def test_predeclared_governance_policy_matches_training_only_code():
    from insurance_market_au.data_foundation.m1 import ROOT
    policy=json.loads(
        (ROOT/"catalog/calibration/m14b-policy.json").read_text(encoding="utf-8")
    )
    settings=policy["predeclared_hyperparameters"]
    assert policy["model_version"]==m14b.VERSION
    assert policy["training_projection_order"]==list(m14b.ORDER)
    assert policy["strictly_heldout_projections"]==list(m13b.HOLDOUT_SPECS)
    assert settings["rounds"]==4
    assert settings["relaxation"]==pytest.approx(0.35)
    assert settings["update_cap"]==pytest.approx(1.6)
    assert settings["relative_weight_cap_before_projection"]==pytest.approx(8)
    assert settings["minimum_published_training_cell"]==10
    assert settings["minimum_publisher_scope"]==100
    assert settings["minimum_source_mass_coverage"]==pytest.approx(0.15)
    assert policy["release_gate"]["commercial_synthetic_population_approved"] is False
    assert policy["heldout_policy"]["tune_hyperparameters_to_heldout"] is False
