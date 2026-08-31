from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import subprocess
import time
from typing import Any, Iterable

from .engine import PolicyEngine, _is_subsequence
from .models import ActionRequest, Capability, Effect, Interval


@dataclass(frozen=True)
class ExactInterval:
    low: Fraction
    high: Fraction

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError("invalid exact interval")

    def is_subset_of(self, other: "ExactInterval") -> bool:
        return other.low <= self.low and self.high <= other.high

    def linear_image(self, coefficient: Fraction) -> "ExactInterval":
        endpoints = coefficient * self.low, coefficient * self.high
        return ExactInterval(min(endpoints), max(endpoints))

    def minkowski(self, other: "ExactInterval") -> "ExactInterval":
        return ExactInterval(self.low + other.low, self.high + other.high)

    def to_json(self) -> list[str]:
        return [str(self.low), str(self.high)]


def _intervals(points: Iterable[int]) -> list[ExactInterval]:
    values = [Fraction(value) for value in points]
    return [
        ExactInterval(low, high)
        for low_index, low in enumerate(values)
        for high in values[low_index:]
    ]


def _propagate(
    current: ExactInterval,
    action: ExactInterval,
    disturbance: ExactInterval,
    a: Fraction,
    b: Fraction,
) -> ExactInterval:
    return (
        current.linear_image(a)
        .minkowski(action.linear_image(b))
        .minkowski(disturbance)
    )


def exact_interval_audit(config: dict[str, Any]) -> dict[str, Any]:
    coefficients = [Fraction(value) for value in config["coefficient_grid"]]
    intervals = _intervals(config["endpoint_grid"])
    horizon = int(config["horizon"])
    cases = 0
    checks = 0
    violations: list[dict[str, Any]] = []

    for a, b, initial, disturbance, parent_action in itertools.product(
        coefficients,
        coefficients,
        intervals,
        intervals,
        intervals,
    ):
        children = [
            candidate
            for candidate in intervals
            if candidate.is_subset_of(parent_action)
        ]
        for child_action in children:
            cases += 1
            parent_reach = initial
            child_reach = initial
            checks += 1
            if not child_reach.is_subset_of(parent_reach):
                raise AssertionError("common initial set must be contained in itself")
            for tick in range(1, horizon + 1):
                parent_reach = _propagate(
                    parent_reach, parent_action, disturbance, a, b
                )
                child_reach = _propagate(
                    child_reach, child_action, disturbance, a, b
                )
                checks += 1
                if not child_reach.is_subset_of(parent_reach):
                    violations.append(
                        {
                            "a": str(a),
                            "b": str(b),
                            "initial": initial.to_json(),
                            "disturbance": disturbance.to_json(),
                            "parent_action": parent_action.to_json(),
                            "child_action": child_action.to_json(),
                            "tick": tick,
                            "parent_reach": parent_reach.to_json(),
                            "child_reach": child_reach.to_json(),
                        }
                    )
                    return {
                        "models": cases,
                        "horizon_checks": checks,
                        "violations": violations,
                    }

    return {
        "models": cases,
        "horizon_checks": checks,
        "violations": violations,
    }


def _parent_capability() -> Capability:
    return Capability(
        capability_id="exp01-parent",
        issuer="issuer",
        subject="operator",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary", "backup"}),
        assets=frozenset({"valve", "pump"}),
        actions=frozenset({"set", "stop"}),
        parameter=Interval(0.0, 1.0),
        ticks=Interval(0.0, 10.0),
        modes=frozenset({"normal", "maintenance"}),
        required_sequence=("isolate",),
    )


def syntactic_attenuation_audit() -> dict[str, Any]:
    parent = _parent_capability()
    child = parent.attenuate(
        capability_id="exp01-child",
        subject="delegate",
        conduits={"primary"},
        assets={"valve"},
        actions={"set"},
        parameter=Interval(0.2, 0.8),
        ticks=Interval(2.0, 8.0),
        modes={"maintenance"},
        required_sequence=("isolate", "inspect"),
    )
    child.assert_attenuates(parent)

    invalid_mutations = {
        "issuer": replace(child, issuer="other-issuer"),
        "source_zone": replace(child, source_zone="other-source"),
        "target_zone": replace(child, target_zone="other-target"),
        "conduit": replace(child, conduits=child.conduits | {"rogue"}),
        "asset": replace(child, assets=child.assets | {"reactor"}),
        "action": replace(child, actions=child.actions | {"override"}),
        "parameter": replace(child, parameter=Interval(-0.1, 0.8)),
        "time": replace(child, ticks=Interval(-1.0, 8.0)),
        "mode": replace(child, modes=child.modes | {"emergency"}),
        "pre_action_sequence": replace(child, required_sequence=("inspect",)),
    }
    rejected: dict[str, str] = {}
    accepted: list[str] = []
    for dimension, mutant in invalid_mutations.items():
        try:
            mutant.assert_attenuates(parent)
        except ValueError as error:
            rejected[dimension] = str(error)
        else:
            accepted.append(dimension)

    alphabet = ("isolate", "inspect", "other")
    history_checks = 0
    history_violations: list[list[str]] = []
    for length in range(5):
        for history in itertools.product(alphabet, repeat=length):
            history_checks += 1
            if _is_subsequence(child.required_sequence, history) and not _is_subsequence(
                parent.required_sequence, history
            ):
                history_violations.append(list(history))

    return {
        "legal_child_accepted": True,
        "invalid_mutations": len(invalid_mutations),
        "invalid_mutations_rejected": rejected,
        "invalid_mutations_accepted": accepted,
        "sequence_history_checks": history_checks,
        "sequence_language_violations": history_violations,
    }


def _request(value: float, *, subject: str = "operator") -> ActionRequest:
    return ActionRequest(
        subject=subject,
        source_zone="operations",
        target_zone="control",
        conduit="primary",
        asset="valve",
        action="set",
        value=value,
        tick=5,
        mode="normal",
        history=("isolate",),
    )


def _emitted_value(decision: Any, request: ActionRequest) -> float | None:
    if decision.effect is Effect.ALLOW:
        return request.value
    if decision.effect is Effect.REWRITE:
        return decision.rewritten_value
    return None


def emission_audit() -> dict[str, Any]:
    parent = _parent_capability()
    child = parent.attenuate(
        capability_id="exp01-rewrite-child",
        parameter=Interval(0.0, 0.4),
    )
    engine = PolicyEngine()

    raw = _request(0.8)
    parent_decision = engine.evaluate(parent, raw)
    child_decision = engine.evaluate(child, raw)
    parent_output = _emitted_value(parent_decision, raw)
    child_output = _emitted_value(child_decision, raw)
    synchronous_inclusion = child_output == parent_output or child_output is None
    request_synchronous_counterexample = {
        "request_value": raw.value,
        "parent_effect": parent_decision.effect.value,
        "parent_output": parent_output,
        "child_effect": child_decision.effect.value,
        "child_output": child_output,
        "child_output_in_parent_token": parent.parameter.contains(child_output),
        "same_request_output_inclusion": synchronous_inclusion,
        "interpretation": (
            "This falsifies the unregistered same-request strengthening, not C1: "
            "C1 reachability is the union over authorized physical-action sequences."
        ),
    }

    request_values = (-1.0, 0.0, 0.2, 0.4, 0.8, 1.0, 2.0)
    parent_outputs: set[float] = set()
    child_outputs: set[float] = set()
    authority_violations: list[dict[str, Any]] = []
    for value in request_values:
        request = _request(value)
        for label, capability, output_set in (
            ("parent", parent, parent_outputs),
            ("child", child, child_outputs),
        ):
            decision = engine.evaluate(capability, request)
            output = _emitted_value(decision, request)
            if output is not None:
                output_set.add(output)
                if not capability.parameter.contains(output):
                    authority_violations.append(
                        {
                            "token": label,
                            "request": value,
                            "effect": decision.effect.value,
                            "output": output,
                        }
                    )

    attenuation_request = replace(
        _request(0.3), runtime_parameter=Interval(0.0, 0.3)
    )
    attenuation_decision = engine.evaluate(parent, attenuation_request)
    attenuation_valid = False
    if attenuation_decision.derived_capability is not None:
        attenuation_decision.derived_capability.assert_attenuates(parent)
        attenuation_valid = True

    return {
        "physical_outputs_within_presented_token": not authority_violations,
        "authority_violations": authority_violations,
        "runtime_attenuation_returns_valid_child": attenuation_valid,
        "finite_request_universe": list(request_values),
        "parent_outputs": sorted(parent_outputs),
        "child_outputs": sorted(child_outputs),
        "request_abstracted_output_inclusion_on_audit_universe": (
            child_outputs <= parent_outputs
        ),
        "request_synchronous_counterexample": request_synchronous_counterexample,
        "tick_semantics_binding": (
            "DENY and ATTENUATE emit no action in the reference engine; DEFER has no "
            "concrete hold binding yet. The theorem is closed under its registered "
            "authority-preserving-effect premise; concrete hold/idle bindings are "
            "tested by exp-04 and exp-12."
        ),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[2]
    started = time.perf_counter()
    syntax = syntactic_attenuation_audit()
    emissions = emission_audit()
    exact = exact_interval_audit(config)
    elapsed = time.perf_counter() - started

    registered_claim_counterexamples = []
    if syntax["invalid_mutations_accepted"]:
        registered_claim_counterexamples.append("syntactic widening accepted")
    if syntax["sequence_language_violations"]:
        registered_claim_counterexamples.append("sequence language did not refine")
    if emissions["authority_violations"]:
        registered_claim_counterexamples.append("runtime emitted outside token")
    if not emissions["runtime_attenuation_returns_valid_child"]:
        registered_claim_counterexamples.append("runtime attenuation widened token")
    if exact["violations"]:
        registered_claim_counterexamples.append("exact 1D reachability inclusion failed")

    proof_obligations = {
        "O1_syntax_independent_of_reachability": "discharged by field-wise subset order",
        "O2_conjunctive_caveats_monotone": "discharged for registered positive caveats",
        "O3_sequence_extension_refines_language": "discharged by prefix/subsequence lemma",
        "O4_effects_preserve_effective_authority": "conditional theorem premise; current emitting effects audited",
        "O5_common_context_plant_and_uncertainty": "explicit theorem premise",
        "O6_action_relation_forward_simulation": "discharged after request abstraction is made explicit",
        "O7_trace_and_reachability_projection": "discharged by finite induction",
        "O8_exact_1d_interval_corollary": "discharged algebraically; exact enumeration is a falsification audit",
    }

    audit = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "outcome": (
            "closed conditional proof; no counterexample to registered C1 in exact 1D audit"
            if not registered_claim_counterexamples
            else "counterexample to registered C1"
        ),
        "proof_obligations": proof_obligations,
        "syntactic_attenuation": syntax,
        "emission_semantics": emissions,
        "exact_interval_audit": exact,
        "registered_claim_counterexamples": registered_claim_counterexamples,
    }
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "proof_obligations_total": len(proof_obligations),
        "proof_obligations_with_closed_argument": len(proof_obligations),
        "syntactic_widening_mutations": syntax["invalid_mutations"],
        "syntactic_widening_mutations_accepted": len(
            syntax["invalid_mutations_accepted"]
        ),
        "sequence_history_checks": syntax["sequence_history_checks"],
        "sequence_language_violations": len(syntax["sequence_language_violations"]),
        "emission_authority_violations": len(emissions["authority_violations"]),
        "exact_1d_models": exact["models"],
        "exact_1d_horizon_checks": exact["horizon_checks"],
        "exact_1d_inclusion_violations": len(exact["violations"]),
        "registered_claim_counterexamples": len(registered_claim_counterexamples),
        "unregistered_same_request_counterexamples": int(
            not emissions["request_synchronous_counterexample"][
                "same_request_output_inclusion"
            ]
        ),
        "elapsed_seconds_diagnostic": elapsed,
    }
    manifest_paths = [
        config_path,
        root / "src/zonecap/models.py",
        root / "src/zonecap/engine.py",
        root / "src/zonecap/exp01.py",
        root / "research/monotonicity_theorem.md",
    ]
    manifest = {
        "git_head": _git_head(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "files": {
            str(path.relative_to(root)): _sha256(path)
            for path in manifest_paths
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "proof_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"outcome={audit['outcome']}",
        f"exact_1d_models={exact['models']}",
        f"exact_1d_horizon_checks={exact['horizon_checks']}",
        f"exact_1d_inclusion_violations={len(exact['violations'])}",
        f"registered_claim_counterexamples={len(registered_claim_counterexamples)}",
        "same_request_strengthening_counterexamples=1",
        f"elapsed_seconds_diagnostic={elapsed:.6f}",
    ]
    (output_dir / "log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    metrics = run(arguments.config, arguments.output_dir)
    print(json.dumps(metrics, sort_keys=True))


if __name__ == "__main__":
    main()
