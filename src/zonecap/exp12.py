from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .effects import EffectBinding, EffectContractError, PhysicalAction
from .engine import PolicyEngine
from .exp07 import _compile_scopes
from .exp07_generator import expand_scopes
from .models import ActionRequest, Capability, Effect, Interval


EXPECTED_COMPOSED_ORDER = (
    Effect.ATTENUATE,
    Effect.DEFER,
    Effect.ALLOW,
    Effect.REWRITE,
    Effect.DENY,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _request(document: dict[str, Any]) -> ActionRequest:
    values = dict(document)
    values["history"] = tuple(values.get("history", ()))
    return ActionRequest(**values)


def _strict_runtime_envelope(capability: Capability, value: float) -> Interval:
    low = capability.parameter.low
    high = capability.parameter.high
    if low == high:
        raise ValueError("exp-12 requires a non-degenerate parameter interval")
    midpoint = low + (high - low) / 2
    if value <= low:
        envelope = Interval(low, midpoint)
    elif value >= high:
        envelope = Interval(midpoint, high)
    else:
        envelope = Interval(value, value)
    if envelope == capability.parameter or not envelope.contains(value):
        raise AssertionError("runtime envelope must be strict and contain the request value")
    return envelope


def _authorized(capability: Capability, action: PhysicalAction) -> bool:
    return (
        action.operation in capability.actions
        and capability.parameter.contains(action.value)
    )


def _plant_step(state: float, action: PhysicalAction) -> float:
    if action.operation == "read":
        return state
    return state + action.value


def _parent_realizes(
    engine: PolicyEngine,
    parent: Capability,
    context: ActionRequest,
    action: PhysicalAction,
) -> bool:
    identity_request = replace(
        context,
        subject=parent.subject,
        action=action.operation,
        value=action.value,
        context_complete=True,
        high_risk=False,
        runtime_parameter=None,
    )
    return (
        engine.evaluate(parent, identity_request, rewrite_out_of_range=False).effect
        is Effect.ALLOW
    )


def _bind(
    binding: EffectBinding,
    capability: Capability,
    request: ActionRequest,
    decision: Any,
) -> tuple[PhysicalAction | None, str | None]:
    try:
        return binding.emitted_action(capability, request, decision), None
    except EffectContractError as error:
        return None, str(error)


def _bounded_deadlocks(
    effects: list[Effect], resolution_bound: int
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    progress_effects = {Effect.ALLOW, Effect.REWRITE}
    for index, effect in enumerate(effects):
        if effect not in {Effect.ATTENUATE, Effect.DEFER}:
            continue
        future = next(
            (
                candidate
                for candidate in range(index + 1, len(effects))
                if effects[candidate] in progress_effects
            ),
            None,
        )
        if future is None or future - index > resolution_bound:
            violations.append(
                {
                    "effect": effect.value,
                    "policy_step": index,
                    "first_progress_step": future,
                    "resolution_bound": resolution_bound,
                }
            )
    return violations


def compose_trace(
    capability: Capability,
    request: ActionRequest,
    *,
    resolution_bound: int,
) -> dict[str, Any]:
    engine = PolicyEngine()
    active = capability
    binding = EffectBinding(hold_operation="read", hold_value=request.value)
    steps: list[dict[str, Any]] = []
    effects: list[Effect] = []
    physical_trace: list[dict[str, Any]] = []
    effect_order_violations: list[dict[str, Any]] = []
    attenuation_violations: list[str] = []
    authority_violations: list[dict[str, Any]] = []
    nonstutter_violations: list[dict[str, Any]] = []
    physical_state = 0.0

    requests = (
        (
            "attenuate",
            replace(
                request,
                runtime_parameter=_strict_runtime_envelope(active, request.value),
            ),
        ),
        ("defer", replace(request, context_complete=False)),
        ("allow", request),
        ("rewrite", replace(request, value=capability.parameter.high + 1.0)),
        ("deny", replace(request, action="outside_action")),
    )

    for index, (label, candidate) in enumerate(requests):
        if label == "rewrite":
            candidate = replace(candidate, value=active.parameter.high + 1.0)
        decision = engine.evaluate(active, candidate)
        expected = EXPECTED_COMPOSED_ORDER[index]
        effects.append(decision.effect)
        if decision.effect is not expected:
            effect_order_violations.append(
                {
                    "policy_step": index,
                    "expected": expected.value,
                    "observed": decision.effect.value,
                }
            )

        action, contract_error = _bind(binding, active, candidate, decision)
        before_state = physical_state
        if contract_error is not None:
            authority_violations.append(
                {"policy_step": index, "effect": decision.effect.value, "error": contract_error}
            )
        if action is not None:
            if not _authorized(active, action):
                authority_violations.append(
                    {
                        "policy_step": index,
                        "effect": decision.effect.value,
                        "operation": action.operation,
                        "value": action.value,
                    }
                )
            physical_state = _plant_step(physical_state, action)
            physical_trace.append(
                {
                    "policy_step": index,
                    "effect": decision.effect.value,
                    "operation": action.operation,
                    "value": action.value,
                    "state_before": before_state,
                    "state_after": physical_state,
                }
            )
        if decision.effect is Effect.DEFER and (
            action is None
            or action.operation != "read"
            or physical_state != before_state
        ):
            nonstutter_violations.append(
                {
                    "policy_step": index,
                    "operation": None if action is None else action.operation,
                    "state_before": before_state,
                    "state_after": physical_state,
                }
            )

        if decision.effect is Effect.ATTENUATE:
            child = decision.derived_capability
            if child is None:
                attenuation_violations.append("ATTENUATE returned no capability")
            else:
                try:
                    child.assert_attenuates(active)
                except ValueError as error:
                    attenuation_violations.append(str(error))
                if child.parameter == active.parameter:
                    attenuation_violations.append("runtime attenuation was not strict")
                if not child.parameter.contains(request.value):
                    attenuation_violations.append("runtime attenuation removed the safe request")
                active = child

        steps.append(
            {
                "policy_step": index,
                "label": label,
                "expected_effect": expected.value,
                "effect": decision.effect.value,
                "active_capability_id_after": active.capability_id,
                "emitted": (
                    None
                    if action is None
                    else {"operation": action.operation, "value": action.value}
                ),
            }
        )

    deadlocks = _bounded_deadlocks(effects, resolution_bound)
    return {
        "scope_id": capability.capability_id,
        "effect_order": [effect.value for effect in effects],
        "steps": steps,
        "physical_trace": physical_trace,
        "effect_order_violations": effect_order_violations,
        "attenuation_violations": attenuation_violations,
        "authority_violations": authority_violations,
        "nonstutter_violations": nonstutter_violations,
        "deadlocks": deadlocks,
    }


def negative_control_audit(
    parent: Capability,
    child: Capability,
    request: ActionRequest,
    resolution_bound: int,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    unsafe_rewrite = PhysicalAction(request.action, child.parameter.high + 1.0)
    checks.append(
        {
            "mutant": "rewrite_outside_effective_capability",
            "detected": not _authorized(child, unsafe_rewrite),
        }
    )

    nonstutter = PhysicalAction("write", parent.parameter.low)
    before = 0.0
    after = _plant_step(before, nonstutter)
    checks.append(
        {
            "mutant": "defer_nonstutter_operation",
            "detected": nonstutter.operation != "read" or before != after,
        }
    )

    checks.append(
        {
            "mutant": "defer_without_resolution",
            "detected": bool(_bounded_deadlocks([Effect.DEFER], resolution_bound)),
        }
    )

    deny_output = PhysicalAction("outside_action", child.parameter.low)
    checks.append(
        {
            "mutant": "deny_emits_unauthorized_action",
            "detected": not _authorized(child, deny_output),
        }
    )

    widened = replace(
        child,
        parameter=Interval(parent.parameter.low - 1.0, parent.parameter.high + 1.0),
    )
    try:
        widened.assert_attenuates(parent)
        widening_detected = False
    except ValueError:
        widening_detected = True
    checks.append(
        {"mutant": "attenuate_widens_parameter", "detected": widening_detected}
    )

    return {
        "mutants": len(checks),
        "killed": sum(check["detected"] for check in checks),
        "checks": checks,
    }


def _expected_corpus_effect(record: dict[str, Any]) -> Effect:
    if record["kind"] == "valid":
        return Effect.ALLOW
    if record["mutation"] in {"parameter_low", "parameter_high"}:
        return Effect.REWRITE
    return Effect.DENY


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-12 requires a clean, committed pre-run freeze")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if tuple(config["composed_effect_order"]) != tuple(
        effect.value for effect in EXPECTED_COMPOSED_ORDER
    ):
        raise RuntimeError("configured composed effect order differs from the frozen automaton")
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    table = json.loads((root / config["policy_table"]).read_text(encoding="utf-8"))
    roots, delegations = expand_scopes(table)
    scopes = [*roots, *delegations]
    scope_by_id = {scope["scope_id"]: scope for scope in scopes}
    if len(scope_by_id) != len(scopes):
        raise AssertionError("duplicate generated scope id")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    capability_by_scope, relation_records = _compile_scopes(
        table, roots, delegations, output_dir / "compiled_inputs"
    )
    _write_json(output_dir / "delegation_checks.json", relation_records)
    parent_by_scope = {
        scope["scope_id"]: capability_by_scope[scope["parent_scope_id"]]
        for scope in delegations
    }

    engine = PolicyEngine()
    corpus_effects: Counter[str] = Counter()
    composed_effects: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    violation_examples: dict[str, list[dict[str, Any]]] = {
        "effect_order": [],
        "attenuation": [],
        "authority": [],
        "nonstutter": [],
        "parent_realizability": [],
        "trace_inclusion": [],
        "deadlock": [],
    }
    valid_records: list[dict[str, Any]] = []
    case_path = root / config["exp07_cases"]
    case_audit_path = output_dir / "case_audit.jsonl.gz"
    with gzip.open(case_path, "rt", encoding="utf-8") as source, gzip.open(
        case_audit_path, "wt", encoding="utf-8"
    ) as sink:
        for line in source:
            record = json.loads(line)
            counters["heldout_traces"] += 1
            capability = capability_by_scope[record["scope_id"]]
            request = _request(record["request"])
            decision = engine.evaluate(capability, request)
            expected = _expected_corpus_effect(record)
            corpus_effects[decision.effect.value] += 1
            counters["effect_expectation_violations"] += decision.effect is not expected
            binding = EffectBinding("read", capability.parameter.low)
            action, contract_error = _bind(binding, capability, request, decision)
            unauthorized = contract_error is not None or (
                action is not None and not _authorized(capability, action)
            )
            counters["authority_violations"] += unauthorized

            parent = parent_by_scope.get(record["scope_id"])
            parent_realizable = True
            if parent is not None:
                counters["heldout_delegated_trace_checks"] += 1
                if action is not None:
                    counters["parent_physical_transition_checks"] += 1
                    parent_realizable = _parent_realizes(engine, parent, request, action)
                    counters["parent_realizability_violations"] += not parent_realizable
                counters["trace_inclusion_violations"] += not parent_realizable
            if record["kind"] == "valid":
                valid_records.append(record)
                counters["valid_cases"] += 1
            else:
                counters["mutation_cases"] += 1
            sink.write(
                json.dumps(
                    {
                        "case_id": record["case_id"],
                        "scope_id": record["scope_id"],
                        "expected_effect": expected.value,
                        "effect": decision.effect.value,
                        "emitted": (
                            None
                            if action is None
                            else {"operation": action.operation, "value": action.value}
                        ),
                        "authority_violation": unauthorized,
                        "parent_realizable": parent_realizable,
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    trace_path = output_dir / "composed_traces.jsonl.gz"
    with gzip.open(trace_path, "wt", encoding="utf-8") as sink:
        for record in valid_records:
            capability = capability_by_scope[record["scope_id"]]
            request = _request(record["request"])
            trace = compose_trace(
                capability,
                request,
                resolution_bound=config["resolution_bound_policy_steps"],
            )
            counters["composed_traces"] += 1
            counters["composed_policy_steps"] += len(trace["steps"])
            counters["composed_physical_transitions"] += len(trace["physical_trace"])
            composed_effects.update(trace["effect_order"])
            for key, metric in (
                ("effect_order", "effect_order_violations"),
                ("attenuation", "attenuation_violations"),
                ("authority", "authority_violations"),
                ("nonstutter", "nonstutter_violations"),
                ("deadlock", "deadlocks"),
            ):
                values = trace[metric]
                counters[f"{key}_violations"] += len(values)
                if values and len(violation_examples[key]) < 10:
                    violation_examples[key].append(
                        {"case_id": record["case_id"], "violations": values}
                    )

            parent = parent_by_scope.get(record["scope_id"])
            parent_trace_ok = True
            if parent is not None:
                counters["composed_delegated_trace_checks"] += 1
                for output in trace["physical_trace"]:
                    action = PhysicalAction(output["operation"], output["value"])
                    counters["parent_physical_transition_checks"] += 1
                    realized = _parent_realizes(engine, parent, request, action)
                    counters["parent_realizability_violations"] += not realized
                    parent_trace_ok = parent_trace_ok and realized
                    if not realized and len(violation_examples["parent_realizability"]) < 10:
                        violation_examples["parent_realizability"].append(
                            {
                                "case_id": record["case_id"],
                                "scope_id": record["scope_id"],
                                "output": output,
                            }
                        )
                counters["trace_inclusion_violations"] += not parent_trace_ok
                if not parent_trace_ok and len(violation_examples["trace_inclusion"]) < 10:
                    violation_examples["trace_inclusion"].append(
                        {"case_id": record["case_id"], "scope_id": record["scope_id"]}
                    )
            trace["case_id"] = record["case_id"]
            trace["parent_trace_realizable"] = parent_trace_ok
            sink.write(json.dumps(trace, sort_keys=True) + "\n")

    first_delegation = delegations[0]
    first_child = capability_by_scope[first_delegation["scope_id"]]
    first_parent = capability_by_scope[first_delegation["parent_scope_id"]]
    first_valid = next(
        record for record in valid_records if record["scope_id"] == first_delegation["scope_id"]
    )
    mutation_audit = negative_control_audit(
        first_parent,
        first_child,
        _request(first_valid["request"]),
        config["resolution_bound_policy_steps"],
    )
    _write_json(output_dir / "mutation_audit.json", mutation_audit)
    _write_json(output_dir / "violation_examples.json", violation_examples)

    total_effects = corpus_effects + composed_effects
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "heldout_traces": counters["heldout_traces"],
        "heldout_delegated_trace_checks": counters["heldout_delegated_trace_checks"],
        "valid_cases": counters["valid_cases"],
        "mutation_cases": counters["mutation_cases"],
        "composed_traces": counters["composed_traces"],
        "composed_delegated_trace_checks": counters["composed_delegated_trace_checks"],
        "composed_policy_steps": counters["composed_policy_steps"],
        "composed_physical_transitions": counters["composed_physical_transitions"],
        "parent_physical_transition_checks": counters["parent_physical_transition_checks"],
        "corpus_effect_counts": dict(sorted(corpus_effects.items())),
        "composed_effect_counts": dict(sorted(composed_effects.items())),
        "total_effect_counts": dict(sorted(total_effects.items())),
        "all_five_effects_reached": set(total_effects) == {effect.value for effect in Effect},
        "effect_expectation_violations": counters["effect_expectation_violations"],
        "effect_order_violations": counters["effect_order_violations"],
        "attenuation_violations": counters["attenuation_violations"],
        "authority_safety_violations": counters["authority_violations"],
        "defer_nonstutter_violations": counters["nonstutter_violations"],
        "parent_realizability_violations": counters["parent_realizability_violations"],
        "trace_inclusion_violations": counters["trace_inclusion_violations"],
        "bounded_deadlocks": counters["deadlock_violations"],
        "resolution_bound_policy_steps": config["resolution_bound_policy_steps"],
        "negative_control_mutants": mutation_audit["mutants"],
        "negative_control_mutants_killed": mutation_audit["killed"],
        "lanotte_roop_runtime_baseline": "N/A in exp-12; registered for exp-15",
        "sint_tier_baseline": "N/A in exp-12; registered for exp-15",
    }
    observed_counts = {
        "heldout_traces": metrics["heldout_traces"],
        "valid_cases": metrics["valid_cases"],
        "mutation_cases": metrics["mutation_cases"],
        "composed_traces": metrics["composed_traces"],
        "composed_policy_steps": metrics["composed_policy_steps"],
        "composed_physical_transitions": metrics["composed_physical_transitions"],
    }
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": observed_counts.get(key)}
        for key, expected in config["expected_counts"].items()
        if observed_counts.get(key) != expected
    }
    metrics["expected_effect_count_mismatches"] = {
        key: {"expected": expected, "observed": total_effects.get(key, 0)}
        for key, expected in config["expected_total_effect_counts"].items()
        if total_effects.get(key, 0) != expected
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"heldout_traces={metrics['heldout_traces']}",
        f"composed_traces={metrics['composed_traces']}",
        f"composed_policy_steps={metrics['composed_policy_steps']}",
        f"composed_physical_transitions={metrics['composed_physical_transitions']}",
        f"all_five_effects_reached={str(metrics['all_five_effects_reached']).lower()}",
        f"authority_safety_violations={metrics['authority_safety_violations']}",
        f"trace_inclusion_violations={metrics['trace_inclusion_violations']}",
        f"bounded_deadlocks={metrics['bounded_deadlocks']}",
        f"negative_control_mutants_killed={metrics['negative_control_mutants_killed']}/{metrics['negative_control_mutants']}",
    ]
    (output_dir / "log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    input_paths = [config_path, *[root / path for path in config["frozen_hashes"]]]
    output_paths = sorted(
        path for path in output_dir.rglob("*") if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "git_head": _git(root, "rev-parse", "HEAD"),
        "git_status_before_run": dirty_before_run,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "inputs": {str(path.relative_to(root)): _sha256(path) for path in input_paths},
        "outputs": {
            str(path.relative_to(output_dir)): _sha256(path) for path in output_paths
        },
    }
    _write_json(output_dir / "manifest.json", manifest)

    failures = {
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
        "expected_effect_count_mismatches": bool(
            metrics["expected_effect_count_mismatches"]
        ),
        "missing_effect": not metrics["all_five_effects_reached"],
        "effect_expectation_violations": metrics["effect_expectation_violations"],
        "effect_order_violations": metrics["effect_order_violations"],
        "attenuation_violations": metrics["attenuation_violations"],
        "authority_safety_violations": metrics["authority_safety_violations"],
        "defer_nonstutter_violations": metrics["defer_nonstutter_violations"],
        "parent_realizability_violations": metrics["parent_realizability_violations"],
        "trace_inclusion_violations": metrics["trace_inclusion_violations"],
        "bounded_deadlocks": metrics["bounded_deadlocks"],
        "negative_control_survivors": mutation_audit["mutants"] - mutation_audit["killed"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-12 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
