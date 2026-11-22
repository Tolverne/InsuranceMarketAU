"""M2.0 feature contract and deterministic hypothetical scenarios."""
import pytest

from insurance_market_au.enrichment import EnrichmentProvider, EnrichmentSpec, enrich_batch


def _batch():
    pa = pytest.importorskip("pyarrow")
    return pa.record_batch(
        [pa.array([7, 8], type=pa.int64()),
         pa.array(["pop-20260131-abcdefabcdefabcdefabcdef"] * 2),
         pa.array([3.25, 9.5], type=pa.float64()),
         pa.array(["1998", "Unknown"])],
        names=["synthetic_vehicle_id", "population_release_id",
               "sampling_weight", "manufacture_year"])


def test_contract_and_weight_preservation():
    original = _batch()
    enriched = enrich_batch(original, EnrichmentSpec())
    assert enriched.num_rows == original.num_rows
    for field in original.schema.names:
        assert enriched.column(field).equals(original.column(field))
    assert enriched.column("vehicle_age_years").to_pylist() == [28, None]
    assert enriched.column("cover_scenario").to_pylist() == ["unknown", "unknown"]
    assert enriched.column("enrichment_uncertainty_kind").to_pylist() == [
        "hypothetical_unvalidated_scenario"] * 2


def test_counter_rng_independent_of_batching_and_seed():
    original = _batch()
    a = enrich_batch(original, EnrichmentSpec(seed=1))
    pa = pytest.importorskip("pyarrow")
    fragments = [enrich_batch(original.slice(i, 1), EnrichmentSpec(seed=1))
                 for i in range(original.num_rows)]
    for j, field in enumerate(a.schema.names):
        combined = pa.concat_arrays([f.column(j) for f in fragments])
        assert a.column(j).equals(combined)
    assert enrich_batch(original, EnrichmentSpec(seed=2)).column(
        "vehicle_value_scenario_aud").to_pylist() != a.column(
        "vehicle_value_scenario_aud").to_pylist()


def test_fail_closed_invalid_assumptions_and_weights():
    original = _batch()
    with pytest.raises(ValueError, match="km"):
        EnrichmentSpec(annual_km_min=80000, annual_km_max=1000)
    with pytest.raises(ValueError, match="coverage"):
        EnrichmentSpec(cover_assumption="definitely_insured")
    with pytest.raises(ValueError, match="required"):
        enrich_batch(original.select(["synthetic_vehicle_id"]), EnrichmentSpec())
    import pyarrow as pa
    bad = pa.record_batch([
        original.column(0), original.column(1),
        pa.array([0.0, 9.5]), original.column(3)], names=original.schema.names)
    with pytest.raises(ValueError, match="weight"):
        enrich_batch(bad, EnrichmentSpec())


def test_full_population_pin_is_nested_and_model_changes_version():
    original = _batch()

    class StubPopulation:
        def pin(self):
            return {"population_release_id": "example", "population_asset_sha256": "a"*64}
        def iter_feature_view(self, **kwargs):
            yield original

    provider = EnrichmentProvider(StubPopulation(), EnrichmentSpec(seed=77))
    assert provider.pin()["population"]["population_asset_sha256"] == "a"*64
    assert provider.pin()["commercial_use_approved"] is False
    assert sum(b.num_rows for b in provider.iter_feature_view()) == 2
    assert EnrichmentSpec(seed=77).digest() != EnrichmentSpec(seed=78).digest()
