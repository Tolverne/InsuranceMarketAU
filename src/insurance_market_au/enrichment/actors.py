"""M2.2: interchangeable, cautious market actor and participation models.

No household identities, people or policies are inferred from registrations.
Unknown is the safe default. Hypothetical scenario participation is permitted
but never represented as empirically calibrated insured market volume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Protocol, runtime_checkable

from .adapters import ModelIdentity, _digest
from .provider import _uniform

OWNER = ("unknown", "private", "business", "fleet", "other")
DRIVER = ("unknown", "owner", "named_other", "multiple")
PURPOSE = ("unknown", "private", "commuting", "business", "recreational")
COVER = ("unknown", "comprehensive", "third_party_property", "uninsured")
PARTICIPATION = ("unknown", "insured", "not_insured")


@dataclass(frozen=True)
class ActorFeatures:
    owner_type: str = "unknown"
    driver_relationship: str = "unknown"
    vehicle_purpose: str = "unknown"
    insurance_participation: str = "unknown"
    coverage_type: str = "unknown"

    def __post_init__(self):
        for name, valid in (("owner_type", OWNER), ("driver_relationship", DRIVER),
                            ("vehicle_purpose", PURPOSE),
                            ("insurance_participation", PARTICIPATION),
                            ("coverage_type", COVER)):
            if getattr(self, name) not in valid:
                raise ValueError(f"Invalid {name}")
        if self.insurance_participation == "not_insured" and self.coverage_type not in ("unknown", "uninsured"):
            raise ValueError("Uninsured vehicles cannot carry an insured cover classification")
        if self.insurance_participation == "insured" and self.coverage_type == "uninsured":
            raise ValueError("Insured participation and uninsured cover conflict")
        if self.insurance_participation == "unknown" and self.coverage_type != "unknown":
            raise ValueError("Unknown insurance participation must have unknown coverage")


@runtime_checkable
class MarketActorModel(Protocol):
    @property
    def identity(self) -> ModelIdentity: ...
    def predict(self, rows: list[dict], *, seed: int) -> list[ActorFeatures]: ...


@dataclass(frozen=True)
class UnknownActorModel:
    """Default: explicitly no household/driver/insurance inference."""

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity("placeholder.market_actors.unknown", "1.0.0", {})

    def predict(self, rows: list[dict], *, seed: int) -> list[ActorFeatures]:
        return [ActorFeatures() for _ in rows]


@dataclass(frozen=True)
class ScenarioActorModel:
    """Opt-in, purely hypothetical independent per-vehicle assumptions.

    The per-sample simulated participation is not a policy probability derived
    from Australian data. Model assumptions and seed are always recorded.
    """
    private_owner_probability: float = 0.8
    insured_probability: float = 0.7
    comprehensive_given_insured: float = 0.6
    recreational_probability: float = 0.1

    def __post_init__(self):
        for field_name in ("private_owner_probability", "insured_probability",
                           "comprehensive_given_insured", "recreational_probability"):
            n = getattr(self, field_name)
            if type(n) not in (float, int) or not math.isfinite(n) or not 0 <= n <= 1:
                raise ValueError(f"Invalid scenario probability: {field_name}")

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity("placeholder.market_actors.scenario", "1.0.0", {
            name: getattr(self, name) for name in self.__dataclass_fields__})

    def predict(self, rows: list[dict], *, seed: int) -> list[ActorFeatures]:
        result = []
        for row in rows:
            release_id = row["population_release_id"]
            row_id = row["synthetic_vehicle_id"]
            def u(feature: str) -> float:
                return _uniform(release_id, row_id, seed, "m22-" + feature)
            owner = "private" if u("owner") < self.private_owner_probability else "business"
            purpose = ("recreational" if u("purpose") < self.recreational_probability
                       else "private" if owner == "private" else "business")
            insured = u("insured") < self.insured_probability
            cover = ("comprehensive" if u("cover") < self.comprehensive_given_insured
                     else "third_party_property") if insured else "uninsured"
            result.append(ActorFeatures(
                owner_type=owner, driver_relationship="unknown",
                vehicle_purpose=purpose,
                insurance_participation="insured" if insured else "not_insured",
                coverage_type=cover,
            ))
        return result
