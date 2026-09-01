from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Iterable

from .effects import EffectBinding, EffectContractError, PhysicalAction
from .engine import PolicyEngine
from .exp07 import _compile_scopes
from .exp07_generator import expand_scopes
from .models import ActionRequest, Capability, Effect, Interval


ALPHABET = ("narrow", "defer", "valid", "rewrite", "deny")
EXPECTED_EFFECT = {
    "narrow": Effect.ATTENUATE,
    "defer": Effect.DEFER,
    "valid": Effect.ALLOW,
    "rewrite": Effect.REWRITE,
    "deny": Effect.DENY,
}
HANDPICKED_PATH = ALPHABET


@dataclass(frozen=True)
class ModelState:
    active: Capability
    physical_state: float = 0.0
    defer_pending: bool = False


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


def _state_key(state: ModelState) -> tuple[Any, ...]:
    return (
        state.active.parameter.low,
        state.active.parameter.high,
        state.physical_state,
        state.defer_pending,
    )


def _base_request(capability: Capability) -> ActionRequest:
    operation = "write" if "write" in capability.actions else "read"
    return ActionRequest(
        subject=capability.subject,
        source_zone=capability.source_zone,
        target_zone=capability.target_zone,
        conduit=sorted(capability.conduits)[0],
        asset=sorted(capability.assets)[0],
        action=operation,
        value=capability.parameter.low
        + (capability.parameter.high - capability.parameter.low) / 2,
        tick=int(capability.ticks.low + (capability.ticks.high - capability.ticks.low) / 2),
        mode=sorted(capability.modes)[0],
        history=capability.required_sequence,
    )


def _symbol_request(capability: Capability, symbol: str) -> ActionRequest:
    request = _base_request(capability)
    if symbol == "narrow":
        midpoint = request.value
        return replace(
            request,
            runtime_parameter=Interval(capability.parameter.low, midpoint),
        )
    if symbol == "defer":
        return replace(request, context_complete=False)
    if symbol == "valid":
        return request
    if symbol == "rewrite":
        return replace(request, value=capability.parameter.high + 1.0)
    if symbol == "deny":
        return replace(request, action="outside_action")
    raise ValueError(f"unknown sequence symbol: {symbol}")


def _plant_step(state: float, action: PhysicalAction) -> float:
    return state if action.operation == "read" else state + action.value


def _parent_realizes(
    engine: PolicyEngine,
    parent: Capability,
    context: ActionRequest,
    action: PhysicalAction,
) -> bool:
    identity = replace(
        context,
        subject=parent.subject,
        action=action.operation,
        value=action.value,
        context_complete=True,
        high_risk=False,
        runtime_parameter=None,
    )
    return (
        engine.evaluate(parent, identity, rewrite_out_of_range=False).effect
        is Effect.ALLOW
    )


def transition(
    state: ModelState,
    symbol: str,
    *,
    parent: Capability | None,
) -> tuple[ModelState, dict[str, Any]]:
    engine = PolicyEngine()
    request = _symbol_request(state.active, symbol)
    decision = engine.evaluate(state.active, request)
    expected = EXPECTED_EFFECT[symbol]
    binding = EffectBinding("read", state.active.parameter.low)
    contract_error: str | None = None
    try:
        action = binding.emitted_action(state.active, request, decision)
    except EffectContractError as error:
        action = None
        contract_error = str(error)

    authority_violation = contract_error is not None or (
        action is not None
        and (
            action.operation not in state.active.actions
            or not state.active.parameter.contains(action.value)
        )
    )
    before = state.physical_state
    after = before if action is None else _plant_step(before, action)
    nonstutter = decision.effect is Effect.DEFER and (
        action is None or action.operation != "read" or before != after
    )
    parent_realizable = (
        True
        if parent is None or action is None
        else _parent_realizes(engine, parent, request, action)
    )

    active = state.active
    attenuation_violation = False
    if decision.effect is Effect.ATTENUATE:
        child = decision.derived_capability
        if child is None:
            attenuation_violation = True
        else:
            try:
                child.assert_attenuates(active)
            except ValueError:
                attenuation_violation = True
            attenuation_violation = attenuation_violation or child.parameter == active.parameter
            active = child

    pending = state.defer_pending
    if decision.effect is Effect.DEFER:
        pending = True
    elif decision.effect in {Effect.ALLOW, Effect.REWRITE}:
        pending = False
    next_state = ModelState(active=active, physical_state=after, defer_pending=pending)
    record = {
        "symbol": symbol,
        "expected_effect": expected.value,
        "effect": decision.effect.value,
        "effect_violation": decision.effect is not expected,
        "attenuation_violation": attenuation_violation,
        "authority_violation": authority_violation,
        "nonstutter_violation": nonstutter,
        "parent_realizability_violation": not parent_realizable,
        "physical_transition": action is not None,
        "emitted": (
            None
            if action is None
            else {"operation": action.operation, "value": action.value}
        ),
    }
    return next_state, record


def _update_ngrams(path: tuple[str, ...], sets: dict[int, set[tuple[str, ...]]]) -> None:
    for width in sets:
        if len(path) >= width:
            sets[width].add(path[-width:])


def _explore_scope(
    capability: Capability,
    parent: Capability | None,
    *,
    horizon: int,
    paths: Iterable[tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    counters: Counter[str] = Counter()
    effect_counts: Counter[str] = Counter()
    states: set[tuple[Any, ...]] = {_state_key(ModelState(capability))}
    signatures: set[tuple[Any, ...]] = set()
    ngrams = {1: set(), 2: set(), 3: set()}
    violation_examples: list[dict[str, Any]] = []

    if paths is None:
        frontier = [(ModelState(capability), tuple())]
        counters["words"] = 1
        for _ in range(horizon):
            next_frontier: list[tuple[ModelState, tuple[str, ...]]] = []
            for state, path in frontier:
                enabled = 0
                for symbol in ALPHABET:
                    next_state, record = transition(state, symbol, parent=parent)
                    enabled += 1
                    new_path = (*path, symbol)
                    next_frontier.append((next_state, new_path))
                    counters["words"] += 1
                    counters["transitions"] += 1
                    counters["physical_transitions"] += record["physical_transition"]
                    effect_counts[record["effect"]] += 1
                    _update_ngrams(new_path, ngrams)
                    states.add(_state_key(next_state))
                    signatures.add(
                        (
                            _state_key(state),
                            symbol,
                            _state_key(next_state),
                            record["effect"],
                            None
                            if record["emitted"] is None
                            else record["emitted"]["operation"],
                        )
                    )
                    violations = {
                        key: record[key]
                        for key in (
                            "effect_violation",
                            "attenuation_violation",
                            "authority_violation",
                            "nonstutter_violation",
                            "parent_realizability_violation",
                        )
                        if record[key]
                    }
                    for key in violations:
                        counters[key] += 1
                    if violations and len(violation_examples) < 10:
                        violation_examples.append({"path": new_path, "violations": violations})
                counters["deadlocks"] += enabled == 0
            frontier = next_frontier
    else:
        for path in paths:
            state = ModelState(capability)
            counters["words"] += 1
            enabled = 0
            for symbol in path:
                next_state, record = transition(state, symbol, parent=parent)
                enabled += 1
                counters["transitions"] += 1
                counters["physical_transitions"] += record["physical_transition"]
                effect_counts[record["effect"]] += 1
                prefix = path[:enabled]
                _update_ngrams(prefix, ngrams)
                states.add(_state_key(next_state))
                signatures.add(
                    (
                        _state_key(state),
                        symbol,
                        _state_key(next_state),
                        record["effect"],
                        None if record["emitted"] is None else record["emitted"]["operation"],
                    )
                )
                for key in (
                    "effect_violation",
                    "attenuation_violation",
                    "authority_violation",
                    "nonstutter_violation",
                    "parent_realizability_violation",
                ):
                    counters[key] += record[key]
                state = next_state
            counters["deadlocks"] += enabled == 0 and bool(path)

    return {
        "words": counters["words"],
        "transitions": counters["transitions"],
        "physical_transitions": counters["physical_transitions"],
        "unique_states": len(states),
        "unique_transition_signatures": len(signatures),
        "effect_counts": dict(sorted(effect_counts.items())),
        "ngram_counts": {str(width): len(values) for width, values in ngrams.items()},
        "ngrams": {
            str(width): [list(value) for value in sorted(values)]
            for width, values in ngrams.items()
        },
        "effect_violations": counters["effect_violation"],
        "attenuation_violations": counters["attenuation_violation"],
        "authority_violations": counters["authority_violation"],
        "nonstutter_violations": counters["nonstutter_violation"],
        "parent_realizability_violations": counters["parent_realizability_violation"],
        "deadlocks": counters["deadlocks"],
        "violation_examples": violation_examples,
    }


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    scalar_keys = (
        "words",
        "transitions",
        "physical_transitions",
        "unique_states",
        "unique_transition_signatures",
        "effect_violations",
        "attenuation_violations",
        "authority_violations",
        "nonstutter_violations",
        "parent_realizability_violations",
        "deadlocks",
    )
    effects: Counter[str] = Counter()
    ngrams = {1: set(), 2: set(), 3: set()}
    result = {key: sum(record[key] for record in records) for key in scalar_keys}
    for record in records:
        effects.update(record["effect_counts"])
        for width in ngrams:
            ngrams[width].update(tuple(item) for item in record["ngrams"][str(width)])
    result["effect_counts"] = dict(sorted(effects.items()))
    result["ngram_counts"] = {str(width): len(values) for width, values in ngrams.items()}
    result["ngrams"] = {
        str(width): [list(value) for value in sorted(values)]
        for width, values in ngrams.items()
    }
    return result


def mutation_coverage(exhaustive_pairs: list[list[str]], handpicked_pairs: list[list[str]]) -> dict[str, Any]:
    exhaustive = {tuple(pair) for pair in exhaustive_pairs}
    handpicked = {tuple(pair) for pair in handpicked_pairs}
    mutants = (
        ("second_defer_is_nonstutter", ("defer", "defer")),
        ("second_attenuation_widens", ("narrow", "narrow")),
        ("attenuation_after_rewrite_emits_unauthorized_output", ("rewrite", "narrow")),
    )
    checks = [
        {
            "mutant": name,
            "trigger": list(trigger),
            "exhaustive_detected": trigger in exhaustive,
            "handpicked_detected": trigger in handpicked,
        }
        for name, trigger in mutants
    ]
    return {
        "mutants": len(checks),
        "exhaustive_killed": sum(check["exhaustive_detected"] for check in checks),
        "handpicked_killed": sum(check["handpicked_detected"] for check in checks),
        "checks": checks,
    }


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-14 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if tuple(config["alphabet"]) != ALPHABET or tuple(config["handpicked_path"]) != HANDPICKED_PATH:
        raise RuntimeError("configured alphabet/path differs from the frozen sequence protocol")
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    table = json.loads((root / config["policy_table"]).read_text(encoding="utf-8"))
    roots, delegations = expand_scopes(table)
    scopes = [*roots, *delegations]
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    capabilities, relations = _compile_scopes(
        table, roots, delegations, output_dir / "compiled_inputs"
    )
    _write_json(output_dir / "delegation_checks.json", relations)
    parent_by_scope = {
        scope["scope_id"]: capabilities[scope["parent_scope_id"]]
        for scope in delegations
    }

    exhaustive_records: list[dict[str, Any]] = []
    handpicked_records: list[dict[str, Any]] = []
    scope_summaries: list[dict[str, Any]] = []
    for scope in scopes:
        capability = capabilities[scope["scope_id"]]
        parent = parent_by_scope.get(scope["scope_id"])
        exhaustive = _explore_scope(
            capability, parent, horizon=config["horizon"], paths=None
        )
        handpicked = _explore_scope(
            capability,
            parent,
            horizon=config["horizon"],
            paths=(HANDPICKED_PATH,),
        )
        exhaustive_records.append(exhaustive)
        handpicked_records.append(handpicked)
        scope_summaries.append(
            {
                "scope_id": scope["scope_id"],
                "depth": scope["depth"],
                "exhaustive": {key: value for key, value in exhaustive.items() if key not in {"ngrams", "violation_examples"}},
                "handpicked": {key: value for key, value in handpicked.items() if key not in {"ngrams", "violation_examples"}},
            }
        )

    exhaustive = _aggregate(exhaustive_records)
    handpicked = _aggregate(handpicked_records)
    mutation = mutation_coverage(exhaustive["ngrams"]["2"], handpicked["ngrams"]["2"])
    _write_json(output_dir / "scope_summaries.json", scope_summaries)
    _write_json(output_dir / "coverage.json", {"exhaustive": exhaustive, "handpicked": handpicked})
    _write_json(output_dir / "mutation_audit.json", mutation)

    violation_keys = (
        "effect_violations",
        "attenuation_violations",
        "authority_violations",
        "nonstutter_violations",
        "parent_realizability_violations",
        "deadlocks",
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "scopes": len(scopes),
        "alphabet_size": len(ALPHABET),
        "horizon": config["horizon"],
        "exhaustive_words": exhaustive["words"],
        "exhaustive_transitions": exhaustive["transitions"],
        "exhaustive_physical_transitions": exhaustive["physical_transitions"],
        "exhaustive_unique_states_sum": exhaustive["unique_states"],
        "exhaustive_unique_transition_signatures_sum": exhaustive[
            "unique_transition_signatures"
        ],
        "exhaustive_effect_counts": exhaustive["effect_counts"],
        "exhaustive_ngram_counts": exhaustive["ngram_counts"],
        "handpicked_words": handpicked["words"],
        "handpicked_transitions": handpicked["transitions"],
        "handpicked_physical_transitions": handpicked["physical_transitions"],
        "handpicked_unique_states_sum": handpicked["unique_states"],
        "handpicked_unique_transition_signatures_sum": handpicked[
            "unique_transition_signatures"
        ],
        "handpicked_effect_counts": handpicked["effect_counts"],
        "handpicked_ngram_counts": handpicked["ngram_counts"],
        "transition_coverage_multiplier": exhaustive["transitions"]
        / handpicked["transitions"],
        **{f"exhaustive_{key}": exhaustive[key] for key in violation_keys},
        **{f"handpicked_{key}": handpicked[key] for key in violation_keys},
        "coverage_mutants": mutation["mutants"],
        "exhaustive_mutants_killed": mutation["exhaustive_killed"],
        "handpicked_mutants_killed": mutation["handpicked_killed"],
    }
    observed = {
        "scopes": metrics["scopes"],
        "exhaustive_words": metrics["exhaustive_words"],
        "exhaustive_transitions": metrics["exhaustive_transitions"],
        "exhaustive_physical_transitions": metrics["exhaustive_physical_transitions"],
        "handpicked_words": metrics["handpicked_words"],
        "handpicked_transitions": metrics["handpicked_transitions"],
        "handpicked_physical_transitions": metrics["handpicked_physical_transitions"],
        "exhaustive_bigrams": metrics["exhaustive_ngram_counts"]["2"],
        "exhaustive_trigrams": metrics["exhaustive_ngram_counts"]["3"],
        "handpicked_bigrams": metrics["handpicked_ngram_counts"]["2"],
        "handpicked_trigrams": metrics["handpicked_ngram_counts"]["3"],
    }
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": observed.get(key)}
        for key, expected in config["expected_counts"].items()
        if observed.get(key) != expected
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"exhaustive_words={metrics['exhaustive_words']}",
        f"exhaustive_transitions={metrics['exhaustive_transitions']}",
        f"exhaustive_ngram_counts={json.dumps(metrics['exhaustive_ngram_counts'], sort_keys=True)}",
        f"handpicked_transitions={metrics['handpicked_transitions']}",
        f"handpicked_ngram_counts={json.dumps(metrics['handpicked_ngram_counts'], sort_keys=True)}",
        f"exhaustive_authority_violations={metrics['exhaustive_authority_violations']}",
        f"exhaustive_parent_realizability_violations={metrics['exhaustive_parent_realizability_violations']}",
        f"exhaustive_deadlocks={metrics['exhaustive_deadlocks']}",
        f"exhaustive_mutants_killed={metrics['exhaustive_mutants_killed']}/{metrics['coverage_mutants']}",
        f"handpicked_mutants_killed={metrics['handpicked_mutants_killed']}/{metrics['coverage_mutants']}",
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
        "outputs": {str(path.relative_to(output_dir)): _sha256(path) for path in output_paths},
    }
    _write_json(output_dir / "manifest.json", manifest)

    failures = {
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
        **{f"exhaustive_{key}": exhaustive[key] for key in violation_keys},
        "exhaustive_mutant_survivors": mutation["mutants"] - mutation["exhaustive_killed"],
        "unexpected_handpicked_kills": mutation["handpicked_killed"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-14 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
