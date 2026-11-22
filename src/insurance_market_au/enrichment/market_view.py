"""M2.2 enriched market-feature provider with future M3 market segmentation port."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
import math

from .actors import (MarketActorModel, UnknownActorModel, ActorFeatures,
                     OWNER, DRIVER, PURPOSE, COVER, PARTICIPATION)
from .adapters import _digest
from .workbench import MarketFeatureProvider, MarketFeatureSpec

COLUMNS = (
    "owner_type_scenario", "driver_relationship_scenario",
    "vehicle_purpose_scenario", "insurance_participation_scenario",
    "coverage_type_scenario", "actor_model_digest",
)


@dataclass(frozen=True)
class ExtendedMarketSpec:
    features: MarketFeatureSpec = field(default_factory=MarketFeatureSpec)
    actors: MarketActorModel = field(default_factory=UnknownActorModel)

    def __post_init__(self):
        if not callable(getattr(self.actors, "predict", None)) or not hasattr(self.actors, "identity"):
            raise TypeError("actors must implement identity and predict")
        self.actors.identity.pin()


class ExtendedMarketProvider:
    """Decorator leaves M1+M2.1 unchanged; replace actor adapter independently."""

    def __init__(self, population, spec: ExtendedMarketSpec | None = None):
        self.spec = spec or ExtendedMarketSpec()
        self.base = MarketFeatureProvider(population, self.spec.features)

    def pin(self) -> dict:
        selection = {
            "contract_version": "extended-market-feature-selection-v1",
            "feature_view": "market_insurance_actors_v1",
            "base_features": self.base.pin(),
            "actors_model": self.spec.actors.identity.pin(),
            "evidence_status": "hypothetical_unvalidated",
            "commercial_use_approved": False,
        }
        return {**selection, "selection_sha256": _digest(selection)}

    def iter_feature_view(self, *, filters=None, batch_size: int = 25000):
        import pyarrow as pa
        digest = self.pin()["selection_sha256"]
        for batch in self.base.iter_feature_view(filters=filters, batch_size=batch_size):
            if any(name in batch.schema.names for name in COLUMNS):
                raise ValueError("Duplicate actor feature columns")
            data = batch.to_pylist()
            results = self.spec.actors.predict(data, seed=self.spec.features.seed)
            if len(results) != batch.num_rows or any(
                    not isinstance(item, ActorFeatures) for item in results):
                raise ValueError("Actor model must return one validated ActorFeatures per row")
            fields = (
                [r.owner_type for r in results],
                [r.driver_relationship for r in results],
                [r.vehicle_purpose for r in results],
                [r.insurance_participation for r in results],
                [r.coverage_type for r in results],
                [digest] * batch.num_rows,
            )
            yield pa.record_batch(
                [*batch.columns, *(pa.array(v, type=pa.string()) for v in fields)],
                names=[*batch.schema.names, *COLUMNS],
            )

    def summarize(self, *, group_by=("registered_state",), filters=None,
                  batch_size=25000, max_groups=100) -> dict:
        """Produce registered-vehicle and *scenario* participation denominators.

        Unknown participation must remain separate, never interpreted as
        uninsured. Only group on known categorical/actor attributes.
        """
        allowed = {"registered_state", "vehicle_type", "manufacture_year",
                   "motive_power", "make", "model", "registered_postcode",
                   "garaging_postcode", *COLUMNS[:5]}
        dims = tuple(group_by)
        if len(dims) > 3 or len(set(dims)) != len(dims) or not set(dims) <= allowed:
            raise ValueError("Invalid segmentation dimensions")
        if not 1 <= max_groups <= 1000:
            raise ValueError("Invalid max_groups")
        groups = defaultdict(lambda: [0., 0., 0., 0., 0, 0.])
        for batch in self.iter_feature_view(filters=filters, batch_size=batch_size):
            d = batch.to_pydict()
            for i in range(batch.num_rows):
                k = tuple(d[dim][i] for dim in dims)
                weight = d["sampling_weight"][i]
                if not math.isfinite(weight) or weight <= 0:
                    raise ValueError("Invalid registered vehicle mass")
                acc = groups[k]
                acc[0] += weight
                acc[1] += weight ** 2
                status = d["insurance_participation_scenario"][i]
                if status == "insured":
                    acc[2] += weight
                elif status == "not_insured":
                    acc[3] += weight
                else:
                    acc[5] += weight
                acc[4] += 1
        output = []
        for key, (total, square, insured, not_insured, n, unknown) in groups.items():
            if not math.isclose(total, insured + not_insured + unknown,
                                rel_tol=1e-10, abs_tol=1e-6):
                raise ValueError("Participation mass conservation failed")
            output.append({
                "dimensions": dict(zip(dims, key)),
                "estimated_registered_vehicles": total,
                "scenario_insured_vehicle_mass": insured,
                "scenario_not_insured_vehicle_mass": not_insured,
                "participation_unknown_vehicle_mass": unknown,
                "synthetic_sample_rows": n,
                "effective_sample_size": total ** 2 / square if square else 0.,
                "quality_status": "hypothetical_unvalidated",
            })
        output.sort(key=lambda g: (-g["estimated_registered_vehicles"], str(g["dimensions"])))
        return {
            "selection": self.pin(),
            "group_by": list(dims),
            "total_estimated_registered_vehicles": sum(x["estimated_registered_vehicles"] for x in output),
            "total_scenario_insured_vehicle_mass": sum(x["scenario_insured_vehicle_mass"] for x in output),
            "total_scenario_not_insured_vehicle_mass": sum(x["scenario_not_insured_vehicle_mass"] for x in output),
            "total_participation_unknown_vehicle_mass": sum(x["participation_unknown_vehicle_mass"] for x in output),
            "groups": output[:max_groups],
            "omitted_group_count": max(0, len(output) - max_groups),
            "is_empirically_validated_insured_market": False,
            "is_policy_exposure": False,
            "warning": "Scenario participation reflects assumed model only, not observed insured risks or policies.",
        }
