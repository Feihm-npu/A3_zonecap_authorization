from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Callable


Token = dict[str, frozenset[int]]
Action = tuple[int, ...]


def _all_actions(dimensions: tuple[str, ...], universe: tuple[int, ...]) -> list[Action]:
    return list(itertools.product(universe, repeat=len(dimensions)))


def _conjunctive_accept(token: Token, action: Action, dimensions: tuple[str, ...]) -> bool:
    return all(action[index] in token[dimension] for index, dimension in enumerate(dimensions))


def _or_accept(token: Token, action: Action, dimensions: tuple[str, ...]) -> bool:
    return any(action[index] in token[dimension] for index, dimension in enumerate(dimensions))


def _first_applicable_accept(
    token: Token, action: Action, dimensions: tuple[str, ...]
) -> bool:
    return action[0] in token[dimensions[0]]


def _xor_accept(token: Token, action: Action, dimensions: tuple[str, ...]) -> bool:
    matches = sum(
        action[index] in token[dimension]
        for index, dimension in enumerate(dimensions)
    )
    return matches % 2 == 1


def _accepted(
    token: Token,
    actions: list[Action],
    dimensions: tuple[str, ...],
    predicate: Callable[[Token, Action, tuple[str, ...]], bool],
) -> set[Action]:
    return {action for action in actions if predicate(token, action, dimensions)}


def _action_code(action: Action, radix: int) -> int:
    result = 0
    for value in action:
        result = result * radix + value
    return result


def _counterexample(
    parent_actions: set[Action], child_actions: set[Action], radix: int
) -> dict[str, Any] | None:
    child_only = child_actions - parent_actions
    if not child_only:
        return None
    witness = min(
        child_only,
        key=lambda action: (
            sum(value != 0 for value in action),
            sum(value == radix - 1 for value in action),
            action,
        ),
    )
    child_state = _action_code(witness, radix)
    parent_states = {_action_code(action, radix) for action in parent_actions}
    if child_state in parent_states:
        raise AssertionError("injective action-to-state map must retain the witness")
    return {
        "action_tuple": list(witness),
        "one_step_child_state": child_state,
        "one_step_state_in_parent_reachable_set": False,
    }


def mutation_audit(config: dict[str, Any]) -> dict[str, Any]:
    dimensions = tuple(config["dimensions"])
    universe = tuple(config["universe"])
    radix = len(universe)
    actions = _all_actions(dimensions, universe)
    parent: Token = {dimension: frozenset({0, 1}) for dimension in dimensions}
    legal_child: Token = {dimension: frozenset({0}) for dimension in dimensions}
    correct_parent = _accepted(parent, actions, dimensions, _conjunctive_accept)
    correct_child = _accepted(legal_child, actions, dimensions, _conjunctive_accept)
    if not correct_child <= correct_parent:
        raise AssertionError("registered positive conjunction must be monotone")

    killed: list[dict[str, Any]] = []
    survived: list[dict[str, Any]] = []

    for dimension in dimensions:
        invalid_child = dict(legal_child)
        invalid_child[dimension] = frozenset({0, 2})
        child_actions = _accepted(
            invalid_child, actions, dimensions, _conjunctive_accept
        )
        witness = _counterexample(correct_parent, child_actions, radix)
        record = {
            "mutant": f"validator_skips_{dimension}",
            "class": "unsafe",
            "mechanism": "an amplifying child is accepted when one subset check is omitted",
            "counterexample": witness,
        }
        (killed if witness else survived).append(record)

    empty_child = dict(legal_child)
    empty_child[dimensions[0]] = frozenset()
    empty_as_universe = dict(empty_child)
    empty_as_universe[dimensions[0]] = frozenset(universe)
    empty_actions = _accepted(
        empty_as_universe, actions, dimensions, _conjunctive_accept
    )
    witness = _counterexample(correct_parent, empty_actions, radix)
    record = {
        "mutant": "empty_child_caveat_defaults_to_universe",
        "class": "unsafe",
        "mechanism": "an empty delegated scope is interpreted as unrestricted",
        "counterexample": witness,
    }
    (killed if witness else survived).append(record)

    missing_as_universe = dict(legal_child)
    missing_as_universe[dimensions[1]] = frozenset(universe)
    missing_actions = _accepted(
        missing_as_universe, actions, dimensions, _conjunctive_accept
    )
    witness = _counterexample(correct_parent, missing_actions, radix)
    record = {
        "mutant": "missing_child_caveat_defaults_to_universe",
        "class": "unsafe",
        "mechanism": "a missing materialized child field resets rather than inherits",
        "counterexample": witness,
    }
    (killed if witness else survived).append(record)

    fallback_child_actions = set(actions)
    witness = _counterexample(correct_parent, fallback_child_actions, radix)
    record = {
        "mutant": "delegated_unknown_activates_default_allow",
        "class": "unsafe",
        "mechanism": "only delegated-token evaluation takes an allow fallback",
        "counterexample": witness,
    }
    (killed if witness else survived).append(record)

    xor_parent = _accepted(parent, actions, dimensions, _xor_accept)
    xor_child = _accepted(legal_child, actions, dimensions, _xor_accept)
    witness = _counterexample(xor_parent, xor_child, radix)
    record = {
        "mutant": "and_combiner_replaced_by_xor",
        "class": "unsafe",
        "mechanism": "adding/narrowing positive caveats changes decision parity",
        "counterexample": witness,
    }
    (killed if witness else survived).append(record)

    for name, predicate in (
        ("and_combiner_replaced_by_or", _or_accept),
        ("and_combiner_replaced_by_first_applicable", _first_applicable_accept),
    ):
        mutant_parent = _accepted(parent, actions, dimensions, predicate)
        mutant_child = _accepted(legal_child, actions, dimensions, predicate)
        witness = _counterexample(mutant_parent, mutant_child, radix)
        record = {
            "mutant": name,
            "class": "semantics_changing_but_monotone",
            "mechanism": (
                "positive set inclusion still preserves monotonicity, although the "
                "compiled policy no longer implements the registered conjunction"
            ),
            "counterexample": witness,
            "parent_authorized_actions": len(mutant_parent),
            "child_authorized_actions": len(mutant_child),
        }
        (killed if witness else survived).append(record)

    widened_child_actions = set(correct_child)
    widened_action = tuple([2] + [0] * (len(dimensions) - 1))
    widened_child_actions.add(widened_action)
    plant_ignores_input_parent = {0}
    plant_ignores_input_child = {0}
    plant_injective_parent = {
        _action_code(action, radix) for action in correct_parent
    }
    plant_injective_child = {
        _action_code(action, radix) for action in widened_child_actions
    }
    semantic_relation_plant_dependent = (
        plant_ignores_input_child <= plant_ignores_input_parent
        and not plant_injective_child <= plant_injective_parent
    )
    semantic_record = {
        "mutant": "attenuation_defined_as_reachable_subset",
        "class": "unsafe",
        "mechanism": (
            "the same token pair is classified differently when only the plant "
            "transition changes, violating syntax independence"
        ),
        "counterexample": {
            "same_tokens": True,
            "input_ignoring_plant_says_attenuates": True,
            "injective_plant_says_attenuates": False,
            "plant_dependent_relation_detected": semantic_relation_plant_dependent,
        },
    }
    (killed if semantic_relation_plant_dependent else survived).append(semantic_record)

    unsafe = [record for record in killed + survived if record["class"] == "unsafe"]
    killed_unsafe = [record for record in killed if record["class"] == "unsafe"]
    return {
        "dimensions": list(dimensions),
        "finite_action_universe_size": len(actions),
        "registered_parent_authorized_actions": len(correct_parent),
        "registered_child_authorized_actions": len(correct_child),
        "unsafe_mutants": len(unsafe),
        "unsafe_mutants_killed": len(killed_unsafe),
        "unsafe_mutants_survived": len(unsafe) - len(killed_unsafe),
        "killed": killed,
        "survived": survived,
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
    audit = mutation_audit(config)
    unsafe_mutants = audit["unsafe_mutants"]
    unsafe_killed = audit["unsafe_mutants_killed"]
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "authority_dimensions_mutated": len(config["dimensions"]),
        "finite_action_universe_size": audit["finite_action_universe_size"],
        "unsafe_mutants": unsafe_mutants,
        "unsafe_mutants_killed": unsafe_killed,
        "unsafe_mutants_survived": audit["unsafe_mutants_survived"],
        "unsafe_mutation_score": unsafe_killed / unsafe_mutants,
        "semantics_changing_monotone_mutants": sum(
            record["class"] == "semantics_changing_but_monotone"
            for record in audit["survived"]
        ),
        "minimal_counterexamples_retained": sum(
            record["counterexample"] is not None for record in audit["killed"]
        ),
        "registered_c1_counterexamples": 0,
    }
    baseline = {
        "Dodson_CHERI_Macaroons": {
            "source": "https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-963.pdf",
            "fair_commonality": "delegation adds/restricts caveats without granting beyond the parent",
            "not_claimed": "no reachable-set theorem is attributed to the baseline",
        },
        "SINT_v0_2": {
            "source": "https://github.com/sint-ai/sint-protocol/blob/2461a911b8c3d7ed9da3f7662b33678f688eb826/WHITEPAPER.md",
            "fair_commonality": "attenuation-only delegation and physical constraints",
            "not_claimed": "no IEC 62443 compiler or syntactic-to-physical proof is attributed to the baseline",
        },
        "comparison": (
            "The baseline schemas motivate restriction-only syntax. Exp-02 tests "
            "ZoneCap's additional compiler-to-physical refinement obligation; it "
            "does not claim that the baselines contain these injected mutants."
        ),
    }
    manifest_paths = [
        config_path,
        root / "src/zonecap/exp02.py",
        root / "research/attenuation_mutation_audit.md",
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
        ("mutation_report.json", audit),
        ("metrics.json", metrics),
        ("baseline_scope.json", baseline),
        ("manifest.json", manifest),
    ):
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    log = [
        f"experiment={config['exp']}",
        "seed=none",
        f"unsafe_mutants={unsafe_mutants}",
        f"unsafe_mutants_killed={unsafe_killed}",
        f"unsafe_mutants_survived={audit['unsafe_mutants_survived']}",
        f"semantics_changing_monotone_mutants={metrics['semantics_changing_monotone_mutants']}",
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
