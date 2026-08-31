from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Protocol

from .engine import PolicyEngine
from .models import ActionRequest, Capability, Effect, Interval


@dataclass(frozen=True)
class CommonRequest:
    resource: str
    action: str
    value: Fraction


class CommonAdapter(Protocol):
    name: str

    def permits(self, level: str, request: CommonRequest) -> bool: ...

    def max_value(self, level: str) -> Fraction: ...


class ZoneCapAdapter:
    name = "ZoneCap"

    def __init__(self) -> None:
        self.parent = Capability(
            capability_id="exp05-zonecap-parent",
            issuer="issuer",
            subject="operator",
            source_zone="operations",
            target_zone="control",
            conduits=frozenset({"primary"}),
            assets=frozenset({"modbus://cell/valve"}),
            actions=frozenset({"set", "read"}),
            parameter=Interval(0.0, 1.0),
            ticks=Interval(0.0, 10.0),
            modes=frozenset({"normal"}),
        )
        self.child = self.parent.attenuate(
            capability_id="exp05-zonecap-child",
            actions={"set"},
            parameter=Interval(0.0, 0.4),
        )
        self.engine = PolicyEngine()

    def _token(self, level: str) -> Capability:
        return self.parent if level == "parent" else self.child

    def permits(self, level: str, request: CommonRequest) -> bool:
        token = self._token(level)
        decision = self.engine.evaluate(
            token,
            ActionRequest(
                subject="operator",
                source_zone="operations",
                target_zone="control",
                conduit="primary",
                asset=request.resource,
                action=request.action,
                value=float(request.value),
                tick=5,
                mode="normal",
            ),
            rewrite_out_of_range=False,
        )
        return decision.effect is Effect.ALLOW

    def max_value(self, level: str) -> Fraction:
        return Fraction(str(self._token(level).parameter.high))


class MacaroonAdapter:
    name = "Dodson_CHERI_Macaroons_schema_adapter"

    def __init__(self) -> None:
        self.parent_caveats = (
            lambda request: request.resource == "modbus://cell/valve",
            lambda request: request.action in {"set", "read"},
            lambda request: Fraction(0) <= request.value <= Fraction(1),
        )
        self.child_caveats = self.parent_caveats + (
            lambda request: request.action in {"set"},
            lambda request: Fraction(0) <= request.value <= Fraction(2, 5),
        )

    def permits(self, level: str, request: CommonRequest) -> bool:
        caveats = self.parent_caveats if level == "parent" else self.child_caveats
        return all(caveat(request) for caveat in caveats)

    def max_value(self, level: str) -> Fraction:
        return Fraction(1) if level == "parent" else Fraction(2, 5)


class SintAdapter:
    name = "SINT_v0_2_pinned"

    def __init__(self, instance: dict[str, Any]) -> None:
        self.instance = instance

    def _token(self, level: str) -> dict[str, Any]:
        return self.instance[level]

    def permits(self, level: str, request: CommonRequest) -> bool:
        token = self._token(level)
        return (
            request.resource == token["resource"]
            and request.action in token["actions"]
            and Fraction(0) <= request.value
            <= Fraction(str(token["maxVelocityMps"]))
        )

    def max_value(self, level: str) -> Fraction:
        return Fraction(str(self._token(level)["maxVelocityMps"]))


@dataclass(frozen=True)
class ExactInterval:
    low: Fraction
    high: Fraction

    def image(self, coefficient: Fraction) -> "ExactInterval":
        endpoints = coefficient * self.low, coefficient * self.high
        return ExactInterval(min(endpoints), max(endpoints))

    def add(self, other: "ExactInterval") -> "ExactInterval":
        return ExactInterval(self.low + other.low, self.high + other.high)

    def subset_of(self, other: "ExactInterval") -> bool:
        return other.low <= self.low and self.high <= other.high

    def json(self) -> list[str]:
        return [str(self.low), str(self.high)]


def _reach(
    *,
    a: Fraction,
    b: Fraction,
    initial: ExactInterval,
    action: ExactInterval,
    disturbance: ExactInterval,
    horizon: int,
) -> list[ExactInterval]:
    result = [initial]
    current = initial
    for _ in range(horizon):
        current = current.image(a).add(action.image(b)).add(disturbance)
        result.append(current)
    return result


def decision_audit(adapters: list[CommonAdapter], config: dict[str, Any]) -> dict[str, Any]:
    requests = [
        CommonRequest(resource, action, Fraction(value))
        for resource, action, value in itertools.product(
            config["request_resources"],
            config["request_actions"],
            config["request_values"],
        )
    ]
    records: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    child_parent_violations: list[dict[str, Any]] = []
    for level, request in itertools.product(("parent", "child"), requests):
        decisions = {adapter.name: adapter.permits(level, request) for adapter in adapters}
        record = {
            "level": level,
            "request": {
                "resource": request.resource,
                "action": request.action,
                "value": str(request.value),
            },
            "decisions": decisions,
        }
        records.append(record)
        if len(set(decisions.values())) != 1:
            mismatches.append(record)
    for adapter in adapters:
        for request in requests:
            if adapter.permits("child", request) and not adapter.permits(
                "parent", request
            ):
                child_parent_violations.append(
                    {
                        "adapter": adapter.name,
                        "request": {
                            "resource": request.resource,
                            "action": request.action,
                            "value": str(request.value),
                        },
                    }
                )
    return {
        "requests_per_level": len(requests),
        "level_request_pairs": len(records),
        "records": records,
        "cross_adapter_decision_mismatches": mismatches,
        "child_parent_permission_violations": child_parent_violations,
    }


def reachability_audit(adapters: list[CommonAdapter], config: dict[str, Any]) -> dict[str, Any]:
    plants = [
        {
            "name": plant["name"],
            "a": Fraction(plant["a"]),
            "b": Fraction(plant["b"]),
            "initial": ExactInterval(*(Fraction(value) for value in plant["initial"])),
            "disturbance": ExactInterval(
                *(Fraction(value) for value in plant["disturbance"])
            ),
        }
        for plant in config["plants"]
    ]
    horizon = int(config["horizon"])
    records: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    cross_adapter_mismatches: list[dict[str, Any]] = []
    by_plant_level: dict[tuple[str, str], list[list[str]]] = {}
    for adapter, plant in itertools.product(adapters, plants):
        parent_action = ExactInterval(Fraction(0), adapter.max_value("parent"))
        child_action = ExactInterval(Fraction(0), adapter.max_value("child"))
        parent_sets = _reach(
            a=plant["a"],
            b=plant["b"],
            initial=plant["initial"],
            action=parent_action,
            disturbance=plant["disturbance"],
            horizon=horizon,
        )
        child_sets = _reach(
            a=plant["a"],
            b=plant["b"],
            initial=plant["initial"],
            action=child_action,
            disturbance=plant["disturbance"],
            horizon=horizon,
        )
        by_plant_level[(plant["name"], f"{adapter.name}:parent")] = [
            interval.json() for interval in parent_sets
        ]
        by_plant_level[(plant["name"], f"{adapter.name}:child")] = [
            interval.json() for interval in child_sets
        ]
        for tick, (parent_set, child_set) in enumerate(zip(parent_sets, child_sets)):
            included = child_set.subset_of(parent_set)
            record = {
                "adapter": adapter.name,
                "plant": plant["name"],
                "horizon": tick,
                "parent": parent_set.json(),
                "child": child_set.json(),
                "included": included,
            }
            records.append(record)
            if not included:
                violations.append(record)
    for plant in plants:
        for level in ("parent", "child"):
            series = [
                by_plant_level[(plant["name"], f"{adapter.name}:{level}")]
                for adapter in adapters
            ]
            if any(candidate != series[0] for candidate in series[1:]):
                cross_adapter_mismatches.append(
                    {"plant": plant["name"], "level": level, "series": series}
                )
    return {
        "plants": len(plants),
        "horizon": horizon,
        "records": records,
        "inclusion_violations": violations,
        "cross_adapter_reachable_set_mismatches": cross_adapter_mismatches,
    }


def proof_obligation_coverage() -> dict[str, Any]:
    obligations = (
        "resource_binding_or_invariance",
        "action_subset_delegation",
        "numeric_upper_bound_attenuation",
        "authority_preserving_rewrite_hold_contract",
        "physical_trace_reachable_set_refinement",
        "iec_62443_zone_conduit_compilation",
    )
    coverage = {
        "ZoneCap": (True, True, True, True, True, True),
        "Dodson_CHERI_Macaroons_schema_adapter": (True, True, True, None, None, False),
        "SINT_v0_2_pinned": (True, True, True, None, None, False),
    }
    return {
        "legend": {
            "true": "covered in the instantiated schema/system",
            "false": "not provided",
            "null": "not attributed without a corresponding proof/artifact",
        },
        "obligations": list(obligations),
        "systems": {
            name: dict(zip(obligations, values)) for name, values in coverage.items()
        },
        "common_subset_obligations": list(obligations[:3]),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run(config_path: Path, sint_instance_path: Path, output_dir: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    sint_instance_path = sint_instance_path.resolve()
    output_dir = output_dir.resolve()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sint_instance = json.loads(sint_instance_path.read_text(encoding="utf-8"))
    if sint_instance["commit"] != config["sint_commit"]:
        raise ValueError("SINT instance commit does not match the fixed baseline")
    adapters: list[CommonAdapter] = [
        ZoneCapAdapter(),
        MacaroonAdapter(),
        SintAdapter(sint_instance),
    ]
    decisions = decision_audit(adapters, config)
    reachability = reachability_audit(adapters, config)
    coverage = proof_obligation_coverage()
    widening = sint_instance["widening_request_normalized_to"]
    sint_widening_safe = (
        set(widening["actions"]) <= set(sint_instance["parent"]["actions"])
        and widening["maxVelocityMps"]
        <= sint_instance["parent"]["maxVelocityMps"]
        and widening["expiresAt"] <= sint_instance["parent"]["expiresAt"]
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "systems": len(adapters),
        "common_subset_dimensions": len(coverage["common_subset_obligations"]),
        "decision_level_request_pairs": decisions["level_request_pairs"],
        "cross_adapter_decision_mismatches": len(
            decisions["cross_adapter_decision_mismatches"]
        ),
        "child_parent_permission_violations": len(
            decisions["child_parent_permission_violations"]
        ),
        "plants": reachability["plants"],
        "per_adapter_per_plant_horizon_checks": len(reachability["records"]),
        "reachable_set_inclusion_violations": len(
            reachability["inclusion_violations"]
        ),
        "cross_adapter_reachable_set_mismatches": len(
            reachability["cross_adapter_reachable_set_mismatches"]
        ),
        "sint_widening_request_normalized_without_amplification": sint_widening_safe,
        "sint_unauthorized_only_action_request_rejected": not sint_instance[
            "unauthorized_only_action_request_ok"
        ],
        "registered_c1_counterexamples": 0,
    }
    manifest_paths = [
        config_path,
        sint_instance_path,
        root / "scripts/exp05_sint_runner.mjs",
        root / "src/zonecap/exp05.py",
        root / "research/common_subset_baseline.md",
    ]
    manifest = {
        "git_head": _git_head(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sint_commit": sint_instance["commit"],
        "sint_source_hashes": sint_instance["source_hashes"],
        "files": {
            str(path.relative_to(root)): _sha256(path) for path in manifest_paths
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in (
        ("metrics.json", metrics),
        ("decisions.json", decisions),
        ("reachability.json", reachability),
        ("proof_obligations.json", coverage),
        ("manifest.json", manifest),
    ):
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    log = [
        f"experiment={config['exp']}",
        "seed=none",
        f"systems={metrics['systems']}",
        f"common_subset_dimensions={metrics['common_subset_dimensions']}",
        f"cross_adapter_decision_mismatches={metrics['cross_adapter_decision_mismatches']}",
        f"child_parent_permission_violations={metrics['child_parent_permission_violations']}",
        f"reachable_set_inclusion_violations={metrics['reachable_set_inclusion_violations']}",
        f"cross_adapter_reachable_set_mismatches={metrics['cross_adapter_reachable_set_mismatches']}",
        f"sint_widening_request_normalized_without_amplification={str(sint_widening_safe).lower()}",
        "registered_c1_counterexamples=0",
    ]
    (output_dir / "log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sint-instance", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run(arguments.config, arguments.sint_instance, arguments.output_dir),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
