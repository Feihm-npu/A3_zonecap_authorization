from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .models import Capability, Interval, Plant1D


class CompilationError(ValueError):
    pass


@dataclass(frozen=True)
class Architecture:
    name: str
    zones: frozenset[str]
    conduits: dict[str, dict[str, Any]]
    policies: tuple[dict[str, Any], ...]
    requests: tuple[dict[str, Any], ...]
    plant: Plant1D
    initial_state: Interval
    source_basis: str
    evidence_scope: str

    @classmethod
    def load(cls, path: str | Path) -> "Architecture":
        with Path(path).open("r", encoding="utf-8") as handle:
            doc = json.load(handle)
        required = {"name", "zones", "conduits", "policies", "plant_1d"}
        missing = sorted(required - doc.keys())
        if missing:
            raise CompilationError(f"missing architecture keys: {missing}")
        conduits = {item["id"]: item for item in doc["conduits"]}
        if len(conduits) != len(doc["conduits"]):
            raise CompilationError("duplicate conduit id")
        plant_doc = doc["plant_1d"]
        return cls(
            name=doc["name"],
            zones=frozenset(doc["zones"]),
            conduits=conduits,
            policies=tuple(doc["policies"]),
            requests=tuple(doc.get("requests", [])),
            plant=Plant1D(
                a=float(plant_doc["a"]),
                b=float(plant_doc["b"]),
                disturbance=Interval.from_pair(plant_doc["disturbance"]),
            ),
            initial_state=Interval.from_pair(plant_doc["initial_state"]),
            source_basis=doc.get("source_basis", "unspecified"),
            evidence_scope=doc.get("evidence_scope", "unspecified"),
        )

    def compile_all(self) -> list[Capability]:
        return [self.compile_policy(policy) for policy in self.policies]

    def compile_policy(self, policy: dict[str, Any]) -> Capability:
        policy_id = str(policy.get("id", "<missing>"))
        source = policy.get("source_zone")
        target = policy.get("target_zone")
        if source not in self.zones or target not in self.zones:
            raise CompilationError(f"{policy_id}: unknown source or target zone")

        conduit_id = policy.get("conduit")
        conduit = self.conduits.get(conduit_id)
        if conduit is None:
            raise CompilationError(f"{policy_id}: unknown conduit {conduit_id!r}")
        if (conduit["source"], conduit["target"]) != (source, target):
            raise CompilationError(f"{policy_id}: conduit endpoints do not match policy")

        assets = frozenset(policy["assets"])
        actions = frozenset(policy["actions"])
        if not assets.issubset(frozenset(conduit["assets"])):
            raise CompilationError(f"{policy_id}: asset not carried by conduit")
        if not actions.issubset(frozenset(conduit["actions"])):
            raise CompilationError(f"{policy_id}: action not permitted by conduit")

        parameter = Interval.from_pair(policy["parameter"])
        conduit_parameter = Interval.from_pair(conduit["parameter"])
        if not parameter.is_subset_of(conduit_parameter):
            raise CompilationError(f"{policy_id}: parameter exceeds conduit envelope")

        return Capability(
            capability_id=f"{self.name}:{policy_id}:root",
            issuer=str(policy["issuer"]),
            subject=str(policy["subject"]),
            source_zone=str(source),
            target_zone=str(target),
            conduits=frozenset({str(conduit_id)}),
            assets=assets,
            actions=actions,
            parameter=parameter,
            ticks=Interval.from_pair(policy["ticks"]),
            modes=frozenset(policy["modes"]),
            required_sequence=tuple(policy.get("required_sequence", [])),
        )

