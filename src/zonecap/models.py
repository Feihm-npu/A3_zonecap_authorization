from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import math
from typing import Any, Iterable


@dataclass(frozen=True)
class Interval:
    low: float
    high: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.low) and math.isfinite(self.high)):
            raise ValueError("interval endpoints must be finite")
        if self.low > self.high:
            raise ValueError(f"invalid interval [{self.low}, {self.high}]")

    @classmethod
    def from_pair(cls, pair: Iterable[float]) -> "Interval":
        values = list(pair)
        if len(values) != 2:
            raise ValueError("an interval needs exactly two endpoints")
        return cls(float(values[0]), float(values[1]))

    def contains(self, value: float, *, atol: float = 1e-12) -> bool:
        return self.low - atol <= value <= self.high + atol

    def is_subset_of(self, other: "Interval", *, atol: float = 1e-12) -> bool:
        return other.low - atol <= self.low and self.high <= other.high + atol

    def intersection(self, other: "Interval") -> "Interval | None":
        low = max(self.low, other.low)
        high = min(self.high, other.high)
        return None if low > high else Interval(low, high)

    def clamp(self, value: float) -> float:
        return min(max(value, self.low), self.high)

    def linear_image(self, coefficient: float) -> "Interval":
        endpoints = (coefficient * self.low, coefficient * self.high)
        return Interval(min(endpoints), max(endpoints))

    def minkowski(self, other: "Interval") -> "Interval":
        return Interval(self.low + other.low, self.high + other.high)

    def to_list(self) -> list[float]:
        return [self.low, self.high]


@dataclass(frozen=True)
class Capability:
    capability_id: str
    issuer: str
    subject: str
    source_zone: str
    target_zone: str
    conduits: frozenset[str]
    assets: frozenset[str]
    actions: frozenset[str]
    parameter: Interval
    ticks: Interval
    modes: frozenset[str]
    required_sequence: tuple[str, ...] = ()
    parent_id: str | None = None
    delegation_depth: int = 0

    def attenuate(
        self,
        *,
        capability_id: str,
        subject: str | None = None,
        conduits: Iterable[str] | None = None,
        assets: Iterable[str] | None = None,
        actions: Iterable[str] | None = None,
        parameter: Interval | None = None,
        ticks: Interval | None = None,
        modes: Iterable[str] | None = None,
        required_sequence: Iterable[str] | None = None,
    ) -> "Capability":
        child = replace(
            self,
            capability_id=capability_id,
            subject=subject or self.subject,
            conduits=frozenset(conduits) if conduits is not None else self.conduits,
            assets=frozenset(assets) if assets is not None else self.assets,
            actions=frozenset(actions) if actions is not None else self.actions,
            parameter=parameter or self.parameter,
            ticks=ticks or self.ticks,
            modes=frozenset(modes) if modes is not None else self.modes,
            required_sequence=(
                tuple(required_sequence)
                if required_sequence is not None
                else self.required_sequence
            ),
            parent_id=self.capability_id,
            delegation_depth=self.delegation_depth + 1,
        )
        child.assert_attenuates(self)
        return child

    def assert_attenuates(self, parent: "Capability") -> None:
        violations: list[str] = []
        if self.issuer != parent.issuer:
            violations.append("issuer changed")
        if (self.source_zone, self.target_zone) != (
            parent.source_zone,
            parent.target_zone,
        ):
            violations.append("zone binding changed")
        if not self.conduits.issubset(parent.conduits):
            violations.append("conduit scope widened")
        if not self.assets.issubset(parent.assets):
            violations.append("asset scope widened")
        if not self.actions.issubset(parent.actions):
            violations.append("action scope widened")
        if not self.parameter.is_subset_of(parent.parameter):
            violations.append("parameter interval widened")
        if not self.ticks.is_subset_of(parent.ticks):
            violations.append("time window widened")
        if not self.modes.issubset(parent.modes):
            violations.append("mode scope widened")
        prefix = self.required_sequence[: len(parent.required_sequence)]
        if prefix != parent.required_sequence:
            violations.append("pre-action sequence does not refine parent")
        if violations:
            raise ValueError("invalid attenuation: " + "; ".join(violations))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["conduits"] = sorted(self.conduits)
        result["assets"] = sorted(self.assets)
        result["actions"] = sorted(self.actions)
        result["modes"] = sorted(self.modes)
        result["required_sequence"] = list(self.required_sequence)
        result["parameter"] = self.parameter.to_list()
        result["ticks"] = self.ticks.to_list()
        return result


@dataclass(frozen=True)
class ActionRequest:
    subject: str
    source_zone: str
    target_zone: str
    conduit: str
    asset: str
    action: str
    value: float
    tick: int
    mode: str
    history: tuple[str, ...] = ()
    context_complete: bool = True
    high_risk: bool = False
    runtime_parameter: Interval | None = None


class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ATTENUATE = "attenuate"
    REWRITE = "rewrite"
    DEFER = "defer"


@dataclass(frozen=True)
class Decision:
    effect: Effect
    reason: str
    rewritten_value: float | None = None
    derived_capability: Capability | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "reason": self.reason,
            "rewritten_value": self.rewritten_value,
            "derived_capability": (
                self.derived_capability.to_dict() if self.derived_capability else None
            ),
        }


@dataclass(frozen=True)
class Plant1D:
    a: float
    b: float
    disturbance: Interval

