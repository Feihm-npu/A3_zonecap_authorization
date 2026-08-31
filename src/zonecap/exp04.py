from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .effects import EffectBinding
from .engine import PolicyEngine
from .models import ActionRequest, Capability, Effect, Interval


def _capabilities() -> tuple[Capability, Capability]:
    parent = Capability(
        capability_id="exp04-parent",
        issuer="issuer",
        subject="operator",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary"}),
        assets=frozenset({"valve"}),
        actions=frozenset({"set"}),
        parameter=Interval(0.0, 1.0),
        ticks=Interval(0.0, 10.0),
        modes=frozenset({"normal"}),
    )
    child = parent.attenuate(
        capability_id="exp04-child", parameter=Interval(0.0, 0.4)
    )
    return parent, child


def _request(**updates: Any) -> ActionRequest:
    values: dict[str, Any] = {
        "subject": "operator",
        "source_zone": "operations",
        "target_zone": "control",
        "conduit": "primary",
        "asset": "valve",
        "action": "set",
        "value": 0.2,
        "tick": 5,
        "mode": "normal",
    }
    values.update(updates)
    return ActionRequest(**values)


def audit_concrete_effect_binding() -> dict[str, Any]:
    _, child = _capabilities()
    engine = PolicyEngine()
    binding = EffectBinding(hold_operation="set", hold_value=0.0)
    cases = {
        "allow": _request(),
        "deny": _request(mode="shutdown"),
        "attenuate": _request(
            value=0.2, runtime_parameter=Interval(0.0, 0.3)
        ),
        "rewrite": _request(value=0.8),
        "defer": _request(high_risk=True),
    }
    observed: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    for expected_effect, request in cases.items():
        decision = engine.evaluate(child, request)
        try:
            emitted = binding.emitted_action(child, request, decision)
        except ValueError as error:
            violations.append(
                {
                    "expected_effect": expected_effect,
                    "observed_effect": decision.effect.value,
                    "error": str(error),
                }
            )
            emitted = None
        observed[expected_effect] = {
            "effect": decision.effect.value,
            "emitted": (
                None
                if emitted is None
                else {"operation": emitted.operation, "value": emitted.value}
            ),
        }
        if decision.effect.value != expected_effect:
            violations.append(
                {
                    "expected_effect": expected_effect,
                    "observed_effect": decision.effect.value,
                }
            )
    return {
        "effects_expected": len(cases),
        "effects_observed": len({entry["effect"] for entry in observed.values()}),
        "observed": observed,
        "contract_violations": violations,
    }


def _trace_frontier(alphabet: tuple[Fraction, ...], horizon: int) -> set[tuple[Fraction, ...]]:
    return set(itertools.product(alphabet, repeat=horizon))


def _state_code(
    trace: tuple[Fraction, ...], symbol_codes: dict[Fraction, int], radix: int
) -> int:
    state = 0
    for action in trace:
        state = state * radix + symbol_codes[action]
    return state


def _evaluate_configuration(
    *,
    name: str,
    parent_alphabet: tuple[Fraction, ...],
    child_alphabet: tuple[Fraction, ...],
    horizon: int,
    expected_violation: bool,
) -> dict[str, Any]:
    universe = tuple(sorted(set(parent_alphabet) | set(child_alphabet)))
    symbol_codes = {value: index + 1 for index, value in enumerate(universe)}
    radix = len(universe) + 1
    per_horizon: list[dict[str, Any]] = []
    minimal_counterexample: dict[str, Any] | None = None
    total_trace_violations = 0
    total_state_violations = 0
    for tick in range(horizon + 1):
        parent_traces = _trace_frontier(parent_alphabet, tick)
        child_traces = _trace_frontier(child_alphabet, tick)
        child_only_traces = child_traces - parent_traces
        parent_states = {
            _state_code(trace, symbol_codes, radix) for trace in parent_traces
        }
        child_states = {
            _state_code(trace, symbol_codes, radix) for trace in child_traces
        }
        child_only_states = child_states - parent_states
        total_trace_violations += len(child_only_traces)
        total_state_violations += len(child_only_states)
        if child_only_traces and minimal_counterexample is None:
            trace = min(child_only_traces, key=lambda item: (len(item), item))
            minimal_counterexample = {
                "horizon": tick,
                "child_only_trace": [str(value) for value in trace],
                "child_only_state": _state_code(trace, symbol_codes, radix),
            }
        per_horizon.append(
            {
                "horizon": tick,
                "parent_traces": len(parent_traces),
                "child_traces": len(child_traces),
                "trace_inclusion_violations": len(child_only_traces),
                "reachable_state_inclusion_violations": len(child_only_states),
            }
        )
    observed_violation = total_trace_violations > 0 or total_state_violations > 0
    return {
        "configuration": name,
        "expected_violation": expected_violation,
        "observed_violation": observed_violation,
        "expectation_matched": observed_violation == expected_violation,
        "parent_action_alphabet": [str(value) for value in parent_alphabet],
        "child_action_alphabet": [str(value) for value in child_alphabet],
        "trace_inclusion_violations": total_trace_violations,
        "reachable_state_inclusion_violations": total_state_violations,
        "minimal_counterexample": minimal_counterexample,
        "per_horizon": per_horizon,
    }


def model_check(config: dict[str, Any]) -> dict[str, Any]:
    parent = tuple(Fraction(value) for value in config["parent_action_alphabet"])
    child = tuple(Fraction(value) for value in config["child_action_alphabet"])
    safe_rewrite = Fraction(config["safe_rewrite"])
    unsafe_rewrite = Fraction(config["unsafe_rewrite"])
    safe_hold = Fraction(config["safe_hold"])
    unsafe_hold = Fraction(config["unsafe_hold"])
    horizon = int(config["horizon"])
    configurations = (
        ("suppression_only", child, False),
        ("rewrite_obligation_removed", tuple(sorted(set(child) | {unsafe_rewrite})), True),
        ("rewrite_obligation_restored", tuple(sorted(set(child) | {safe_rewrite})), False),
        ("defer_stutter_obligation_removed", tuple(sorted(set(child) | {unsafe_hold})), True),
        ("defer_stutter_obligation_restored", tuple(sorted(set(child) | {safe_hold})), False),
        ("all_five_effects_restored", tuple(sorted(set(child) | {safe_rewrite, safe_hold})), False),
    )
    records = [
        _evaluate_configuration(
            name=name,
            parent_alphabet=parent,
            child_alphabet=alphabet,
            horizon=horizon,
            expected_violation=expected,
        )
        for name, alphabet, expected in configurations
    ]
    return {
        "horizon": horizon,
        "configurations": records,
        "expectation_mismatches": [
            record["configuration"]
            for record in records
            if not record["expectation_matched"]
        ],
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


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    effect_audit = audit_concrete_effect_binding()
    check = model_check(config)
    removed = [
        record
        for record in check["configurations"]
        if record["expected_violation"]
    ]
    restored = [
        record
        for record in check["configurations"]
        if "restored" in record["configuration"]
    ]
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "configurations": len(check["configurations"]),
        "removed_obligations": len(removed),
        "removed_obligation_counterexamples_detected": sum(
            record["observed_violation"] for record in removed
        ),
        "minimal_counterexamples_retained": sum(
            record["minimal_counterexample"] is not None for record in removed
        ),
        "restored_configurations": len(restored),
        "restored_trace_inclusion_violations": sum(
            record["trace_inclusion_violations"] for record in restored
        ),
        "restored_reachable_state_inclusion_violations": sum(
            record["reachable_state_inclusion_violations"] for record in restored
        ),
        "suppression_only_inclusion_violations": next(
            record["trace_inclusion_violations"]
            + record["reachable_state_inclusion_violations"]
            for record in check["configurations"]
            if record["configuration"] == "suppression_only"
        ),
        "effect_kinds_expected": effect_audit["effects_expected"],
        "effect_kinds_observed": effect_audit["effects_observed"],
        "effect_binding_contract_violations": len(
            effect_audit["contract_violations"]
        ),
        "expectation_mismatches": len(check["expectation_mismatches"]),
        "registered_c1_counterexamples": 0,
    }
    manifest_paths = [
        config_path,
        root / "src/zonecap/effects.py",
        root / "src/zonecap/exp04.py",
        root / "tests/test_effects.py",
        root / "research/effect_refinement_audit.md",
    ]
    manifest = {
        "git_head": _git_head(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "files": {
            str(path.relative_to(root)): _sha256(path) for path in manifest_paths
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in (
        ("metrics.json", metrics),
        ("effect_binding.json", effect_audit),
        ("model_check.json", check),
        ("manifest.json", manifest),
    ):
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    log = [
        f"experiment={config['exp']}",
        "seed=none",
        f"removed_obligations={metrics['removed_obligations']}",
        f"removed_obligation_counterexamples_detected={metrics['removed_obligation_counterexamples_detected']}",
        f"restored_trace_inclusion_violations={metrics['restored_trace_inclusion_violations']}",
        f"restored_reachable_state_inclusion_violations={metrics['restored_reachable_state_inclusion_violations']}",
        f"effect_kinds_observed={metrics['effect_kinds_observed']}",
        f"effect_binding_contract_violations={metrics['effect_binding_contract_violations']}",
        f"expectation_mismatches={metrics['expectation_mismatches']}",
        "registered_c1_counterexamples=0",
    ]
    (output_dir / "log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
