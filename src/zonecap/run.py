from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any

from .baselines import ContextABAC, StaticRBAC
from .compiler import Architecture
from .engine import PolicyEngine
from .models import ActionRequest, Effect, Interval
from .reachability import monotonicity_violations, randomized_counterexample_search


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _request_from_dict(doc: dict[str, Any]) -> ActionRequest:
    runtime = doc.get("runtime_parameter")
    return ActionRequest(
        subject=doc["subject"],
        source_zone=doc["source_zone"],
        target_zone=doc["target_zone"],
        conduit=doc["conduit"],
        asset=doc["asset"],
        action=doc["action"],
        value=float(doc["value"]),
        tick=int(doc["tick"]),
        mode=doc["mode"],
        history=tuple(doc.get("history", [])),
        context_complete=bool(doc.get("context_complete", True)),
        high_risk=bool(doc.get("high_risk", False)),
        runtime_parameter=Interval.from_pair(runtime) if runtime is not None else None,
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def execute(config_path: Path, output: Path, seed: int) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing run directory: {output}")
    output.mkdir(parents=True)
    config = _read_json(config_path)
    base = config_path.parent
    architectures = [Architecture.load((base / item).resolve()) for item in config["architectures"]]
    engine = PolicyEngine()

    compiled: list[tuple[Architecture, Any]] = []
    for architecture in architectures:
        compiled.extend((architecture, cap) for cap in architecture.compile_all())

    decisions: list[dict[str, Any]] = []
    agreement = 0
    rbac_errors = 0
    abac_errors = 0
    effect_counts: Counter[str] = Counter()
    for architecture, capability in compiled:
        rbac = StaticRBAC(
            {(capability.subject, asset, action) for asset in capability.assets for action in capability.actions}
        )
        source_policy = next(
            policy
            for policy in architecture.policies
            if capability.capability_id.startswith(f"{architecture.name}:{policy['id']}:")
        )
        abac = ContextABAC([source_policy])
        for fixture in architecture.requests:
            if fixture["capability"] != source_policy["id"]:
                continue
            request = _request_from_dict(fixture)
            decision = engine.evaluate(capability, request)
            expected_effect = fixture["expected_effect"]
            agreement += int(decision.effect.value == expected_effect)
            effect_counts[decision.effect.value] += 1
            should_execute_raw = expected_effect == Effect.ALLOW.value
            rbac_errors += int(rbac.allows(request) != should_execute_raw)
            abac_errors += int(abac.allows(request) != should_execute_raw)
            decisions.append(
                {
                    "architecture": architecture.name,
                    "request_id": fixture["id"],
                    "expected_effect": expected_effect,
                    "decision": decision.to_dict(),
                    "rbac_allows_raw": rbac.allows(request),
                    "abac_allows_raw": abac.allows(request),
                }
            )

    reachability_checks = 0
    reachability_violations: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    for architecture, parent in compiled:
        width = parent.parameter.high - parent.parameter.low
        child_one = parent.attenuate(
            capability_id=f"{parent.capability_id}:d1",
            subject=f"{parent.subject}.agent1",
            parameter=Interval(parent.parameter.low + 0.1 * width, parent.parameter.high - 0.1 * width),
        )
        child_two = child_one.attenuate(
            capability_id=f"{parent.capability_id}:d2",
            subject=f"{parent.subject}.agent2",
            parameter=Interval(parent.parameter.low + 0.2 * width, parent.parameter.high - 0.2 * width),
        )
        for child in (child_one, child_two):
            found = monotonicity_violations(
                architecture.plant,
                architecture.initial_state,
                parent,
                child,
                int(config["reachability_horizon"]),
            )
            reachability_checks += int(config["reachability_horizon"]) + 1
            if found:
                reachability_violations.append(
                    {"parent": parent.capability_id, "child": child.capability_id, "details": found}
                )
            derived.append(child.to_dict())

    random_search = randomized_counterexample_search(
        compiled[0][1],
        seed=seed,
        cases=int(config["random_cases"]),
        horizon=int(config["reachability_horizon"]),
    )

    benchmark_request_doc = next(
        fixture
        for architecture in architectures
        for fixture in architecture.requests
        if fixture["expected_effect"] == Effect.ALLOW.value
    )
    benchmark_arch, benchmark_cap = compiled[0]
    if benchmark_request_doc["capability"] not in benchmark_cap.capability_id:
        benchmark_arch, benchmark_cap = next(
            (architecture, capability)
            for architecture, capability in compiled
            if benchmark_request_doc["capability"] in capability.capability_id
        )
    del benchmark_arch
    benchmark_request = _request_from_dict(benchmark_request_doc)
    iterations = int(config["latency_iterations"])
    samples_us: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        engine.evaluate(benchmark_cap, benchmark_request)
        samples_us.append((time.perf_counter_ns() - start) / 1_000.0)

    metrics = {
        "run_kind": "S1 smoke only; not confirmatory evidence",
        "seed": seed,
        "architectures_loaded": len(architectures),
        "capabilities_compiled": len(compiled),
        "delegated_capabilities": len(derived),
        "decision_cases": len(decisions),
        "decision_expected_effect_agreement": agreement / len(decisions),
        "effect_counts": dict(sorted(effect_counts.items())),
        "rbac_raw_decision_errors": rbac_errors,
        "abac_raw_decision_errors": abac_errors,
        "reachability_inclusion_checks": reachability_checks,
        "reachability_inclusion_violations": len(reachability_violations),
        "random_counterexample_cases": random_search["cases"],
        "random_counterexample_violations": len(random_search["violations"]),
        "latency_iterations": iterations,
        "latency_us": {
            "p50": statistics.median(samples_us),
            "p99": _percentile(samples_us, 0.99),
            "maximum": max(samples_us),
        },
    }

    _write_json(output / "config.json", config)
    (output / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")
    (output / "seed.txt").write_text(f"{seed}\n", encoding="utf-8")
    _write_json(output / "metrics.json", metrics)
    _write_json(output / "compiled_capabilities.json", [cap.to_dict() for _, cap in compiled])
    _write_json(output / "derived_capabilities.json", derived)
    _write_json(output / "decisions.json", decisions)
    _write_json(output / "reachability_violations.json", reachability_violations)
    _write_json(output / "random_counterexample_search.json", random_search)
    (output / "log.txt").write_text(
        "ZoneCap S1 smoke pipeline completed successfully.\n"
        "Outputs are development checks only and must not be cited as evidence.\n",
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    metrics = execute(args.config.resolve(), args.output.resolve(), args.seed)
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

