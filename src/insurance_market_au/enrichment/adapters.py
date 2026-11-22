"""M2.1 adapter contract: replace model logic without changing consumer columns.

Built-in adapters are deliberately illustrative, NOT valuations or usage
estimates from Australian observations. Registered models must carry an
immutable version and explicit configuration provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Protocol, runtime_checkable

from .provider import _uniform, _age


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelIdentity:
    model_id: str
    version: str
    assumptions: dict
    evidence_status: str = "hypothetical_unvalidated"

    def __post_init__(self):
        if not self.model_id or not self.version or not isinstance(self.assumptions, dict):
            raise ValueError("Model identity/version/assumptions required")
        if self.evidence_status != "hypothetical_unvalidated":
            raise ValueError("Only unvalidated demonstration adapters are supported by M2.1")

    def pin(self) -> dict:
        data = {"model_id": self.model_id, "version": self.version,
                "assumptions": self.assumptions, "evidence_status": self.evidence_status}
        return {**data, "configuration_sha256": _digest(data)}


@runtime_checkable
class VehicleValueModel(Protocol):
    @property
    def identity(self) -> ModelIdentity: ...
    def predict(self, rows: list[dict], *, seed: int) -> list[float | None]: ...


@runtime_checkable
class VehicleUsageModel(Protocol):
    @property
    def identity(self) -> ModelIdentity: ...
    def predict(self, rows: list[dict], *, seed: int) -> list[int | None]: ...


@dataclass(frozen=True)
class UniformValuePlaceholder:
    low_aud: float = 2000
    high_aud: float = 75000

    def __post_init__(self):
        if not (math.isfinite(self.low_aud) and math.isfinite(self.high_aud)
                and 0 < self.low_aud <= self.high_aud <= 10_000_000):
            raise ValueError("Invalid illustrative AUD range")

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity("placeholder.vehicle_value.uniform",
                             "1.0.0", {"low_aud": self.low_aud, "high_aud": self.high_aud})

    def predict(self, rows: list[dict], *, seed: int) -> list[float]:
        return [round(self.low_aud + (self.high_aud - self.low_aud) *
                      _uniform(r["population_release_id"], r["synthetic_vehicle_id"],
                               seed, "m21-value"), 2) for r in rows]


@dataclass(frozen=True)
class UniformUsagePlaceholder:
    low_km: int = 4000
    high_km: int = 22000

    def __post_init__(self):
        if not (0 <= self.low_km <= self.high_km <= 200000):
            raise ValueError("Invalid illustrative kilometre range")

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity("placeholder.vehicle_usage.uniform",
                             "1.0.0", {"low_km": self.low_km, "high_km": self.high_km})

    def predict(self, rows: list[dict], *, seed: int) -> list[int]:
        return [self.low_km + round((self.high_km - self.low_km) *
                _uniform(r["population_release_id"], r["synthetic_vehicle_id"],
                         seed, "m21-usage")) for r in rows]
