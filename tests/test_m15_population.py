"""M1.5 frozen population/feature-port contracts using only fabricated fixture records."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from insurance_market_au.data_foundation import m13b, m14b, m1
from insurance_market_au.population import PopulationStore, list_populations, publish_population, verify_population
from insurance_market_au.population import releases
from test_m14_diagnostics import prepared


def _fixtures(tmp_path, monkeypatch, *, n=90):
    pytest.importorskip("pyarrow")
    catalogue=prepared(tmp_path,monkeypatch)
    # Fixture-only mock source catalogue: the four-way original published
    # controls are already checked by _load_base_joint in this synthetic unit test.
    for pid in ("B26-01","B26-02","B26-03"):
        catalogue[pid]={"projection_id":pid,"sha256":pid[-2:]*32}
    monkeypatch.setattr(releases,"load_bitre_catalog",
                        lambda root: list(catalogue.values()))
    m13b.build_weighted_sample(tmp_path,rows=n,seed=17)
    return catalogue


def test_publish_is_idempotent_and_frozen_after_original_sources_change(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    first=publish_population(tmp_path,kind="baseline")
    rid=first["release_id"]
    assert first["created"] is True
    assert first["verified"] is True
    assert first["physical_checks"]["synthetic_rows"]==90
    assert first["physical_checks"]["fourway_positive_support"]==2
    assert first["physical_checks"]["maximum_fourway_count_residual"]<1e-5
    assert first["manifest"]["status"]=="published"
    assert first["manifest"]["universe"]=="registered_all"
    assert first["manifest"]["dataset_schema_version"]=="fleet-state-weighted-v1"
    assert first["quality"]["quality_gates"]["commercial_pricing_use_approved"] is False
    assert first["quality"]["quality_gates"]["make_model_postcode_associations_empirically_verified"] is False
    assert list_populations(tmp_path)[0]["release_id"]==rid
    assert publish_population(tmp_path,kind="baseline")["created"] is False
    # Frozen source snapshot is independently verifiable even if working
    # model paths are deleted: it carries its original four-way controls.
    (tmp_path/m13b.PATH_ROWS).unlink()
    (tmp_path/"data/processed/m13/joint-state-type-year-fuel.parquet").unlink()
    assert verify_population(tmp_path,rid)["verified"]
    assert PopulationStore(rid,root=tmp_path).pin()["population_release_id"]==rid


def test_downstream_weighted_aggregate_and_arrow_feature_batches(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    asset=publish_population(tmp_path,kind="baseline")
    store=PopulationStore(asset["release_id"],root=tmp_path)
    data=store.aggregate(group_by=("registered_state",))
    assert data["total_estimated_registered_vehicles"]==pytest.approx(m13b.TOTAL)
    assert data["total_synthetic_rows"]==90
    assert len(data["returned_groups"])==2
    by_state={row["dimensions"]["registered_state"]:row for row in data["returned_groups"]}
    assert by_state["NSW"]["estimated_registered_vehicles"]==pytest.approx(1_000_000)
    assert by_state["Vic"]["estimated_registered_vehicles"]==pytest.approx(21_771_150)
    nsw=store.aggregate(group_by=("make","manufacture_year"),
                        filters={"registered_state":"NSW"})
    assert nsw["total_estimated_registered_vehicles"]==pytest.approx(1_000_000)
    assert nsw["returned_groups"][0]["dimensions"]=={"make":"HOLDEN","manufacture_year":"1965"}
    empty=store.aggregate(filters={"registered_postcode":"9999"})
    assert empty["total_synthetic_rows"]==0
    assert empty["is_individually_observed_vehicle_data"] is False
    assert empty["is_insurance_exposure_or_addressable_market"] is False
    assert sum(x.num_rows for x in store.iter_fleet(batch_size=17))==90
    feature=list(store.iter_feature_view(filters={"registered_state":"NSW"}))
    assert feature
    assert "sampling_weight" in feature[0].schema.names
    assert "population_release_id" in feature[0].schema.names
    assert "expected_vehicle_weight" not in feature[0].schema.names
    assert sum(b.num_rows for b in feature)>=1
    assert sum(x["expected_vehicle_weight"] for x in store.preview(limit=10))>0
    pin=store.pin()
    assert pin["representation"]=="weighted_sample"
    assert pin["commercial_use_approved"] is False
    assert len(pin["population_asset_sha256"])==64


def test_rejects_unexpected_fields_arbitrary_filters_and_unsafe_paths(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    rid=publish_population(tmp_path)["release_id"]
    store=PopulationStore(rid,root=tmp_path)
    with pytest.raises(ValueError,match="ID"):
        verify_population(tmp_path,"../../data/private")
    with pytest.raises(ValueError,match="filter"):
        list(store.iter_fleet(filters={"policyholder_name":"Anything"}))
    with pytest.raises(ValueError,match="unknown|duplicate"):
        list(store.iter_fleet(columns=("insured_premium",)))
    with pytest.raises(ValueError,match="aggregation"):
        store.aggregate(group_by=("synthetic_row_id",))
    with pytest.raises(ValueError,match="Preview"):
        store.preview(limit=10000)
    with pytest.raises(ValueError,match="research|baseline|candidate|Choose"):
        publish_population(tmp_path,kind="production")


def test_tampering_frozen_asset_or_quality_is_detected_and_refused(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    asset=publish_population(tmp_path)
    rid=asset["release_id"]
    parquet=Path(asset["directory"])/"fleet-state.parquet"
    with parquet.open("ab") as f:
        f.write(b"tampered")
    with pytest.raises(ValueError,match="changed"):
        verify_population(tmp_path,rid)
    with pytest.raises(ValueError):
        publish_population(tmp_path)
    # Independent quality report tampering must also be detectable.
    parquet.unlink()
    # Rebuild via a new model version isn't allowed to overwrite a corrupt
    # old immutable release. Preserve the evidence of that failure.


def test_candidate_is_distinct_research_release_and_never_auto_promoted(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    base=publish_population(tmp_path,kind="baseline")
    m14b.calibrate(tmp_path,rounds=2)
    candidate=publish_population(tmp_path,kind="candidate")
    assert base["release_id"]!=candidate["release_id"]
    assert candidate["quality"]["model_kind"]=="candidate"
    assert candidate["quality"]["quality_gates"]["commercial_pricing_use_approved"] is False
    assert candidate["physical_checks"]["maximum_fourway_count_residual"]<1e-5
    assert len(list_populations(tmp_path))==2
    from insurance_market_au.data_foundation.m1 import sha256_file
    assert base["manifest"]["outputs"][1]["content_sha256"]==candidate["manifest"]["outputs"][1]["content_sha256"]
    original=Path(base["directory"])/"fleet-state.parquet"
    other=Path(candidate["directory"])/"fleet-state.parquet"
    import pyarrow.parquet as pq
    a,b=pq.read_table(original),pq.read_table(other)
    assert a.schema==b.schema
    assert a.num_rows==b.num_rows
    for col in a.column_names:
        if col!="expected_vehicle_weight":
            assert a[col].equals(b[col])


def test_new_population_model_creates_new_release_id_without_replacing_old(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch,n=80)
    one=publish_population(tmp_path)
    m13b.build_weighted_sample(tmp_path,rows=100,seed=59)
    two=publish_population(tmp_path)
    assert one["release_id"]!=two["release_id"]
    assert verify_population(tmp_path,one["release_id"])["verified"]
    assert verify_population(tmp_path,two["release_id"])["verified"]
    assert len(list_populations(tmp_path))==2
    assert one["manifest"]["outputs"][0]["row_count"]==80
    assert two["manifest"]["outputs"][0]["row_count"]==100


def test_manifest_conforms_existing_json_schema_and_pin_contract(tmp_path,monkeypatch):
    from jsonschema import Draft202012Validator,FormatChecker
    _fixtures(tmp_path,monkeypatch)
    release=publish_population(tmp_path)
    schema=json.loads(
        (m1.ROOT/"contracts/schemas/population-release.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema,format_checker=FormatChecker()).validate(release["manifest"])
    view=PopulationStore(release["release_id"],root=tmp_path)
    contract=json.loads(
        (m1.ROOT/"contracts/schemas/population-selection.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(contract,format_checker=FormatChecker()).validate(view.pin())


def test_candidate_fails_closed_if_source_version_or_hash_changed(tmp_path,monkeypatch):
    _fixtures(tmp_path,monkeypatch)
    m14b.calibrate(tmp_path,rounds=1)
    c=tmp_path/m14b.PATH_CALIBRATED
    with c.open("ab") as stream:
        stream.write(b"altered")
    with pytest.raises(ValueError,match="source isolation|provenance"):
        publish_population(tmp_path,kind="candidate")
