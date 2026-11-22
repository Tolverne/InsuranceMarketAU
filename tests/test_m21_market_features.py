"""M2.1 interchangeable market-feature model contracts."""
import pytest

from insurance_market_au.enrichment.adapters import (
    ModelIdentity, UniformUsagePlaceholder, UniformValuePlaceholder)
from insurance_market_au.enrichment.workbench import MarketFeatureProvider, MarketFeatureSpec


def _population():
    pa = pytest.importorskip("pyarrow")
    base = pa.record_batch([
        pa.array([1, 2, 3], type=pa.int64()),
        pa.array(["pop-demo"] * 3),
        pa.array([2., 3., 5.], type=pa.float64()),
        pa.array(["1985", "2000", "Unknown"]),
        pa.array(["Qld", "Qld", "NSW"])],
        names=["synthetic_vehicle_id", "population_release_id",
               "sampling_weight", "manufacture_year", "registered_state"])

    class Population:
        def pin(self):
            return {"population_release_id": "pop-demo", "population_asset_sha256": "a"*64}
        def iter_feature_view(self, *, filters=None, batch_size=25000):
            for offset in range(0, base.num_rows, batch_size):
                yield base.slice(offset, batch_size)
    return Population()


def test_streaming_segmentation_and_lineage():
    p = MarketFeatureProvider(_population())
    batches = list(p.iter_feature_view(batch_size=2))
    assert sum(b.num_rows for b in batches) == 3
    assert sum(sum(b.column("sampling_weight").to_pylist()) for b in batches) == 10
    report = p.summarize(group_by=("registered_state",))
    assert report["total_estimated_registered_vehicles"] == pytest.approx(10.)
    qld = next(g for g in report["groups"] if g["dimensions"]["registered_state"] == "Qld")
    assert qld["estimated_registered_vehicles"] == pytest.approx(5.)
    assert qld["scenario_mean_value_aud"] > 0
    assert report["is_insured_market"] is False
    assert p.pin()["population"]["population_release_id"] == "pop-demo"


def test_swapping_value_adapter_keeps_schema_usage_and_m1_weights():
    class ConstantValue:
        identity = ModelIdentity("demo.constant", "1.0.0", {"aud": 8500.})
        def predict(self, rows, *, seed):
            return [8500.] * len(rows)

    old = MarketFeatureProvider(_population(), MarketFeatureSpec(seed=5))
    new = MarketFeatureProvider(_population(), MarketFeatureSpec(
        seed=5, value_model=ConstantValue()))
    a, b = next(old.iter_feature_view()), next(new.iter_feature_view())
    assert a.schema == b.schema
    assert a.column("sampling_weight").equals(b.column("sampling_weight"))
    assert a.column("annual_km_scenario").equals(b.column("annual_km_scenario"))
    assert b.column("vehicle_value_scenario_aud").to_pylist() == [8500.] * 3
    assert old.pin()["selection_sha256"] != new.pin()["selection_sha256"]


def test_batching_does_not_change_results():
    p = MarketFeatureProvider(_population())
    a = next(p.iter_feature_view(batch_size=100))
    fragments = list(p.iter_feature_view(batch_size=1))
    import pyarrow as pa
    for j in range(a.num_columns):
        assert a.column(j).equals(pa.concat_arrays([f.column(j) for f in fragments]))


def test_invalid_model_result_is_rejected():
    class BadModel:
        identity = ModelIdentity("demo.bad", "1", {})
        def predict(self, rows, *, seed):
            return [-1] * len(rows)

    p = MarketFeatureProvider(_population(), MarketFeatureSpec(value_model=BadModel()))
    with pytest.raises(ValueError, match="invalid AUD"):
        list(p.iter_feature_view())


def test_invalid_assumptions_and_groups():
    with pytest.raises(ValueError, match="AUD"):
        UniformValuePlaceholder(low_aud=-1)
    with pytest.raises(ValueError, match="kilometre"):
        UniformUsagePlaceholder(low_km=30000, high_km=100)
    p = MarketFeatureProvider(_population())
    with pytest.raises(ValueError, match="segment"):
        p.summarize(group_by=("driver_id",))
    with pytest.raises(ValueError, match="max_groups"):
        p.summarize(max_groups=0)
