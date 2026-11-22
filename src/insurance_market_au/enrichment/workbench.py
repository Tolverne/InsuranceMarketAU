"""M2.1 streaming pluggable enrichment and weighted segment inspection.

Keep M1 population, M2 assumptions and M3 segmentation loosely coupled.
No market-size claim beyond registered weighted vehicles is made here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import math

from .adapters import (VehicleUsageModel, VehicleValueModel,
                       UniformUsagePlaceholder, UniformValuePlaceholder, _digest)
from .provider import EnrichmentSpec, enrich_batch


@dataclass(frozen=True)
class MarketFeatureSpec:
    seed: int = 20261122
    value_model: VehicleValueModel = field(default_factory=UniformValuePlaceholder)
    usage_model: VehicleUsageModel = field(default_factory=UniformUsagePlaceholder)

    def __post_init__(self):
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        for role, model in (("value", self.value_model), ("usage", self.usage_model)):
            if not callable(getattr(model, "predict", None)) or not hasattr(model, "identity"):
                raise TypeError(f"{role} model must implement identity and predict")
            model.identity.pin()  # refuse missing version/provenance early


class MarketFeatureProvider:
    """Stable M2 schema; adapters may be replaced without editing consumers."""

    def __init__(self, population, spec: MarketFeatureSpec | None = None):
        if not callable(getattr(population, "pin", None)) or not callable(
                getattr(population, "iter_feature_view", None)):
            raise TypeError("Expected verified pinned population provider")
        self.population = population
        self.spec = spec or MarketFeatureSpec()

    def pin(self) -> dict:
        manifest = {
            "contract_version": "market-feature-selection-v1",
            "feature_view": "market_insurance_features_v1",
            "population": self.population.pin(),
            "seed": self.spec.seed,
            "value_model": self.spec.value_model.identity.pin(),
            "usage_model": self.spec.usage_model.identity.pin(),
            "evidence_status": "hypothetical_unvalidated",
            "commercial_use_approved": False,
        }
        return {**manifest, "selection_sha256": _digest(manifest)}

    def iter_feature_view(self, *, filters=None, batch_size: int = 25000):
        import pyarrow as pa
        # M2.0 remains supported; its other fields and conservative unknown cover
        # are unchanged. Only the two replaceable adapter columns are swapped.
        legacy_spec = EnrichmentSpec(seed=self.spec.seed)
        configuration_digest = self.pin()["selection_sha256"]
        for base in self.population.iter_feature_view(filters=filters,
                                                     batch_size=batch_size):
            output = enrich_batch(base, legacy_spec)
            rows = base.to_pylist()
            value = self.spec.value_model.predict(rows, seed=self.spec.seed)
            usage = self.spec.usage_model.predict(rows, seed=self.spec.seed)
            if len(value) != base.num_rows or len(usage) != base.num_rows:
                raise ValueError("Model output count must match input rows")
            if any(x is not None and (type(x) not in (float, int)
                       or not math.isfinite(x) or x <= 0) for x in value):
                raise ValueError("Value model returned invalid AUD amount")
            if any(x is not None and (type(x) is not int or not 0 <= x <= 200000)
                   for x in usage):
                raise ValueError("Usage model returned invalid annual kilometres")
            for name, values, arrow_type in (
                ("vehicle_value_scenario_aud", value, pa.float64()),
                ("annual_km_scenario", usage, pa.int32()),
                ("enrichment_model_digest", [configuration_digest] * base.num_rows, pa.string()),
            ):
                pos = output.schema.get_field_index(name)
                output = output.set_column(pos, name, pa.array(values, type=arrow_type))
            yield output

    def summarize(self, *, group_by=("registered_state",), filters=None,
                  batch_size: int = 25000, max_groups: int = 100) -> dict:
        """Stream weighted registered market segments, not insured exposures.

        Keeps population mass unchanged; missing model outputs are excluded
        from conditional feature means but NOT the registered denominator.
        """
        allowed = {"registered_state", "vehicle_type", "manufacture_year",
                   "motive_power", "make", "model", "registered_postcode",
                   "garaging_postcode", "cover_scenario"}
        dims = tuple(group_by)
        if len(dims) > 3 or len(set(dims)) != len(dims) or not set(dims) <= allowed:
            raise ValueError("Invalid market segment dimensions")
        if not 1 <= max_groups <= 1000:
            raise ValueError("Invalid max_groups")
        groups = defaultdict(lambda: [0., 0, 0., 0., 0., 0., 0])
        for batch in self.iter_feature_view(filters=filters, batch_size=batch_size):
            data = batch.to_pydict()
            for i in range(batch.num_rows):
                k = tuple(data[d][i] for d in dims)
                w = data["sampling_weight"][i]
                entry = groups[k]
                entry[0] += w
                entry[1] += 1
                entry[2] += w * w
                v = data["vehicle_value_scenario_aud"][i]
                if v is not None:
                    entry[3] += w * v
                    entry[4] += w
                km = data["annual_km_scenario"][i]
                if km is not None:
                    entry[5] += w * km
                    entry[6] += w
        result = []
        for key, (mass, n, square, value_sum, value_mass, km_sum, km_mass) in groups.items():
            result.append({
                "dimensions": dict(zip(dims, key)),
                "estimated_registered_vehicles": mass,
                "synthetic_sample_rows": n,
                "effective_sample_size": mass * mass / square if square else 0.,
                "scenario_mean_value_aud": value_sum / value_mass if value_mass else None,
                "scenario_mean_annual_km": km_sum / km_mass if km_mass else None,
                "value_known_registered_mass": value_mass,
                "usage_known_registered_mass": km_mass,
                "quality_status": "hypothetical_unvalidated",
            })
        result.sort(key=lambda x: (-x["estimated_registered_vehicles"],
                                   str(x["dimensions"])))
        return {
            "selection": self.pin(),
            "group_by": list(dims),
            "total_estimated_registered_vehicles": sum(x[0] for x in groups.values()),
            "total_synthetic_rows": sum(x[1] for x in groups.values()),
            "groups": result[:max_groups],
            "omitted_group_count": max(0, len(result) - max_groups),
            "is_insured_market": False,
            "is_policy_exposure": False,
            "warning": "Registered-vehicle weights, not insured risks. Value and km are hypothetical.",
        }
