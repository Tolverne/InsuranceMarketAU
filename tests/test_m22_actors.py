"""M2.2 adapter swap, conservative defaults, scenario conservation and batch parity."""
import pytest

from insurance_market_au.enrichment.actors import (
    ActorFeatures, ScenarioActorModel, UnknownActorModel)
from insurance_market_au.enrichment.market_view import ExtendedMarketProvider, ExtendedMarketSpec
from insurance_market_au.enrichment.workbench import MarketFeatureSpec


def _population():
    pa = pytest.importorskip("pyarrow")
    batch = pa.record_batch([
        pa.array([0, 1, 2, 3], type=pa.int64()),
        pa.array(["pop-demo"] * 4),
        pa.array([1., 2., 3., 4.], type=pa.float64()),
        pa.array(["1995", "2001", "Unknown", "1980"]),
        pa.array(["Qld", "Qld", "Vic", "Vic"]),
    ], names=["synthetic_vehicle_id", "population_release_id", "sampling_weight",
              "manufacture_year", "registered_state"])

    class Population:
        def pin(self):
            return {"population_release_id": "pop-demo", "population_asset_sha256": "a" * 64}
        def iter_feature_view(self, *, filters=None, batch_size=25000):
            for pos in range(0, batch.num_rows, batch_size):
                yield batch.slice(pos, batch_size)
    return Population()


def test_unknown_default_and_registered_mass():
    provider = ExtendedMarketProvider(_population())
    result = provider.summarize(group_by=("registered_state",))
    assert result["total_estimated_registered_vehicles"] == pytest.approx(10.)
    assert result["total_scenario_insured_vehicle_mass"] == 0
    assert result["total_scenario_not_insured_vehicle_mass"] == 0
    assert result["total_participation_unknown_vehicle_mass"] == pytest.approx(10.)
    assert result["is_empirically_validated_insured_market"] is False
    assert next(provider.iter_feature_view()).column(
        "insurance_participation_scenario").to_pylist() == ["unknown"] * 4


def test_full_scenario_and_adapter_swappability():
    all_insured = ExtendedMarketProvider(_population(), ExtendedMarketSpec(
        features=MarketFeatureSpec(seed=9),
        actors=ScenarioActorModel(insured_probability=1., comprehensive_given_insured=1.)))
    all_uninsured = ExtendedMarketProvider(_population(), ExtendedMarketSpec(
        features=MarketFeatureSpec(seed=9),
        actors=ScenarioActorModel(insured_probability=0.)))
    a, b = next(all_insured.iter_feature_view()), next(all_uninsured.iter_feature_view())
    assert a.schema == b.schema
    assert a.column("sampling_weight").equals(b.column("sampling_weight"))
    assert a.column("vehicle_value_scenario_aud").equals(b.column("vehicle_value_scenario_aud"))
    assert all_insured.summarize()["total_scenario_insured_vehicle_mass"] == pytest.approx(10)
    assert all_uninsured.summarize()["total_scenario_not_insured_vehicle_mass"] == pytest.approx(10)
    assert all_insured.pin()["selection_sha256"] != all_uninsured.pin()["selection_sha256"]


def test_streaming_batch_independence():
    import pyarrow as pa
    provider = ExtendedMarketProvider(_population(), ExtendedMarketSpec(
        actors=ScenarioActorModel(insured_probability=.5)))
    full = next(provider.iter_feature_view(batch_size=100))
    tiny = list(provider.iter_feature_view(batch_size=1))
    for j in range(full.num_columns):
        assert full.column(j).equals(pa.concat_arrays([b.column(j) for b in tiny]))


def test_reject_invalid_categories_and_conflicting_states():
    with pytest.raises(ValueError, match="coverage"):
        ActorFeatures(coverage_type="comprehensive")
    with pytest.raises(ValueError, match="conflict"):
        ActorFeatures(insurance_participation="insured", coverage_type="uninsured")
    with pytest.raises(ValueError, match="probability"):
        ScenarioActorModel(insured_probability=1.2)
    with pytest.raises(ValueError, match="segmentation"):
        ExtendedMarketProvider(_population()).summarize(group_by=("policy_id",))


def test_invalid_adapter_fails_closed():
    class BadActors:
        identity = UnknownActorModel().identity
        def predict(self, rows, *, seed):
            return [ActorFeatures()]
    provider = ExtendedMarketProvider(_population(), ExtendedMarketSpec(actors=BadActors()))
    with pytest.raises(ValueError, match="one validated"):
        list(provider.iter_feature_view())


def test_nested_pins_retain_m1_m21_dependencies():
    pin = ExtendedMarketProvider(_population()).pin()
    assert pin["base_features"]["population"]["population_release_id"] == "pop-demo"
    assert pin["actors_model"]["version"] == "1.0.0"
    assert pin["commercial_use_approved"] is False
