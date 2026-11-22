"""M2.0 — reproducible, assumption-labelled insurance enrichment feature port.

This is NOT an empirical insurance/household model. It supplies a safe typed
interface for subsequent M2 research and avoids coupling insurance assumptions
to M1's independently versioned registration-population reconstruction.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Iterator

MODEL_VERSION = "m2-0-exploratory-assumptions-v1"
CONTRACT_VERSION = "market_insurance_features_v1"
COVER_OPTIONS = ("unknown", "comprehensive", "third_party_property", "uninsured")


@dataclass(frozen=True)
class EnrichmentSpec:
    """Explicit hypothetical scenario parameters; never observed estimates."""
    seed: int = 20261122
    reference_year: int = 2026
    annual_km_min: int = 4000
    annual_km_max: int = 22000
    vehicle_value_min_aud: int = 2000
    vehicle_value_max_aud: int = 75000
    # Keep coverage unknown by default. Scenario-specific cover probabilities
    # require evidence and a separately documented model revision.
    cover_assumption: str = "unknown"

    def __post_init__(self):
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if not 1900 <= self.reference_year <= 2200:
            raise ValueError("reference_year outside supported bounds")
        if not (0 <= self.annual_km_min <= self.annual_km_max <= 200000):
            raise ValueError("invalid annual km assumptions")
        if not (0 < self.vehicle_value_min_aud <= self.vehicle_value_max_aud <= 10_000_000):
            raise ValueError("invalid vehicle value assumptions")
        if self.cover_assumption not in COVER_OPTIONS:
            raise ValueError("unsupported coverage scenario category")

    def as_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    def digest(self) -> str:
        payload = json.dumps({"model_version": MODEL_VERSION, "parameters": self.as_dict()},
                             sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _uniform(release_id: str, row_id: int, seed: int, feature: str) -> float:
    # Independent feature substreams; independent of streaming batch size/order.
    msg = json.dumps([MODEL_VERSION, release_id, row_id, seed, feature],
                     separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return int.from_bytes(hashlib.sha256(msg).digest()[:8], "big") / 2**64


def _age(year: object, reference_year: int) -> int | None:
    if not isinstance(year, str) or len(year) != 4 or not year.isdigit():
        return None
    y = int(year)
    return reference_year - y if 1886 <= y <= reference_year else None


def enrich_batch(batch, spec: EnrichmentSpec):
    """Append typed scenario features to an M1.5 Arrow RecordBatch.

    Row count, original fields and mass are retained. All enrichment outputs
    are explicitly hypothetical, and unknown values are not filled with fake
    household/driver records.
    """
    import pyarrow as pa

    required = {"synthetic_vehicle_id", "population_release_id", "sampling_weight",
                "manufacture_year"}
    if not required.issubset(batch.schema.names):
        raise ValueError(f"Missing required M1.5 feature columns: {sorted(required - set(batch.schema.names))}")
    if len(batch.schema.names) != len(set(batch.schema.names)):
        raise ValueError("Duplicate upstream feature names")
    if any(x in batch.schema.names for x in ("annual_km_scenario", "vehicle_value_scenario_aud",
                                           "cover_scenario", "enrichment_model_digest")):
        raise ValueError("Batch already contains M2 enrichment columns")
    data = batch.to_pydict()
    ids = data["synthetic_vehicle_id"]
    releases = data["population_release_id"]
    weights = data["sampling_weight"]
    if len(set(zip(releases, ids))) != len(ids):
        raise ValueError("Duplicate release-local synthetic IDs within batch")
    if any(not isinstance(r, str) or not r for r in releases):
        raise ValueError("Missing population release provenance")
    if any(type(i) is not int or i < 0 for i in ids):
        raise ValueError("Invalid synthetic identifier")
    if any(w is None or not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError("Invalid population sampling weight")
    n = batch.num_rows
    km = [spec.annual_km_min + round(_uniform(r, i, spec.seed, "km") *
          (spec.annual_km_max - spec.annual_km_min)) for r, i in zip(releases, ids)]
    val = [round(spec.vehicle_value_min_aud + _uniform(r, i, spec.seed, "value") *
           (spec.vehicle_value_max_aud - spec.vehicle_value_min_aud), 2)
           for r, i in zip(releases, ids)]
    appended = [
        ("vehicle_age_years", pa.array([_age(y, spec.reference_year)
                                        for y in data["manufacture_year"]], type=pa.int16())),
        ("annual_km_scenario", pa.array(km, type=pa.int32())),
        ("vehicle_value_scenario_aud", pa.array(val, type=pa.float64())),
        ("cover_scenario", pa.array([spec.cover_assumption] * n, type=pa.string())),
        ("enrichment_model_digest", pa.array([spec.digest()] * n, type=pa.string())),
        ("enrichment_uncertainty_kind", pa.array(
            ["hypothetical_unvalidated_scenario"] * n, type=pa.string())),
    ]
    return pa.record_batch([*batch.columns, *(arr for _, arr in appended)],
                           names=[*batch.schema.names, *(name for name, _ in appended)])


class EnrichmentProvider:
    """A pinned enrichment view; does not publish/alter any M1 release."""

    def __init__(self, population, spec: EnrichmentSpec):
        if not hasattr(population, "pin") or not hasattr(population, "iter_feature_view"):
            raise TypeError("Expected a verified M1.5 PopulationStore-like provider")
        self.population = population
        self.spec = spec

    def pin(self) -> dict:
        return {
            "contract_version": "enrichment-selection-v1",
            "feature_view": CONTRACT_VERSION,
            "model_version": MODEL_VERSION,
            "model_digest": self.spec.digest(),
            "parameters": self.spec.as_dict(),
            "population": self.population.pin(),
            "evidence_status": "hypothetical_unvalidated",
            "commercial_use_approved": False,
        }

    def iter_feature_view(self, *, filters=None, batch_size: int = 25000) -> Iterator:
        for batch in self.population.iter_feature_view(filters=filters,
                                                      batch_size=batch_size):
            yield enrich_batch(batch, self.spec)
