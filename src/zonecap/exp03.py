from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import subprocess
from typing import Any, Iterable


Point = tuple[Fraction, Fraction]
Matrix2 = tuple[tuple[int, int], tuple[int, int]]
Trace = tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]


def _cross(origin: Point, left: Point, right: Point) -> Fraction:
    return (left[0] - origin[0]) * (right[1] - origin[1]) - (
        left[1] - origin[1]
    ) * (right[0] - origin[0])


def convex_hull(points: Iterable[Point]) -> tuple[Point, ...]:
    ordered = sorted(set(points))
    if len(ordered) <= 1:
        return tuple(ordered)
    lower: list[Point] = []
    for point in ordered:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[Point] = []
    for point in reversed(ordered):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])


def point_in_convex(polytope: tuple[Point, ...], point: Point) -> bool:
    if not polytope:
        return False
    if len(polytope) == 1:
        return point == polytope[0]
    if len(polytope) == 2:
        start, end = polytope
        return (
            _cross(start, end, point) == 0
            and min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
            and min(start[1], end[1]) <= point[1] <= max(start[1], end[1])
        )
    return all(
        _cross(polytope[index], polytope[(index + 1) % len(polytope)], point)
        >= 0
        for index in range(len(polytope))
    )


def polytope_is_subset(
    child: tuple[Point, ...], parent: tuple[Point, ...]
) -> bool:
    return all(point_in_convex(parent, vertex) for vertex in child)


def _mat_vec(matrix: Matrix2, vector: Point) -> Point:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1],
    )


def _add(*vectors: Point) -> Point:
    return (
        sum((vector[0] for vector in vectors), Fraction()),
        sum((vector[1] for vector in vectors), Fraction()),
    )


def propagate_polytope(
    state: tuple[Point, ...],
    action: tuple[Point, ...],
    disturbance: tuple[Point, ...],
    a: Matrix2,
    b: Matrix2,
) -> tuple[Point, ...]:
    return convex_hull(
        _add(_mat_vec(a, x), _mat_vec(b, u), w)
        for x, u, w in itertools.product(state, action, disturbance)
    )


def _box(x_low: Fraction, x_high: Fraction, y_low: Fraction, y_high: Fraction) -> tuple[Point, ...]:
    return convex_hull(
        (
            (x_low, y_low),
            (x_low, y_high),
            (x_high, y_low),
            (x_high, y_high),
        )
    )


def _dense_matrix(rng: random.Random) -> Matrix2:
    values = [rng.randint(-2, 2) for _ in range(4)]
    if values[1] == 0:
        values[1] = rng.choice((-1, 1))
    if values[2] == 0:
        values[2] = rng.choice((-1, 1))
    return ((values[0], values[1]), (values[2], values[3]))


def _fraction_json(value: Fraction) -> str:
    return str(value)


def _polytope_json(polytope: tuple[Point, ...]) -> list[list[str]]:
    return [[_fraction_json(x), _fraction_json(y)] for x, y in polytope]


def _matrix_json(matrix: Matrix2) -> list[list[int]]:
    return [list(row) for row in matrix]


def _mimo_model(rng: random.Random) -> dict[str, Any]:
    a = _dense_matrix(rng)
    b = _dense_matrix(rng)
    x_radius = Fraction(rng.randint(1, 3), 2)
    y_radius = Fraction(rng.randint(1, 3), 2)
    initial = _box(-x_radius, x_radius, -y_radius, y_radius)
    w_x = Fraction(rng.randint(1, 2), 4)
    w_y = Fraction(rng.randint(1, 2), 4)
    disturbance = _box(-w_x, w_x, -w_y, w_y)
    parent_x = Fraction(rng.randint(2, 5))
    parent_y = Fraction(rng.randint(2, 5))
    parent_action = _box(-parent_x, parent_x, -parent_y, parent_y)
    center_x = Fraction(rng.randint(-int(parent_x), int(parent_x)), 4)
    center_y = Fraction(rng.randint(-int(parent_y), int(parent_y)), 4)
    child_x = parent_x / 2
    child_y = parent_y / 2
    child_action = convex_hull(
        (
            (center_x - child_x, center_y),
            (center_x, center_y - child_y),
            (center_x + child_x, center_y),
            (center_x, center_y + child_y),
        )
    )
    if not polytope_is_subset(child_action, parent_action):
        raise AssertionError("generator must create a nested action polytope")
    return {
        "a": a,
        "b": b,
        "initial": initial,
        "disturbance": disturbance,
        "parent_action": parent_action,
        "child_action": child_action,
    }


def _mimo_model_json(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "a": _matrix_json(model["a"]),
        "b": _matrix_json(model["b"]),
        "initial": _polytope_json(model["initial"]),
        "disturbance": _polytope_json(model["disturbance"]),
        "parent_action": _polytope_json(model["parent_action"]),
        "child_action": _polytope_json(model["child_action"]),
    }


def run_mimo_seed(
    rng: random.Random, *, models: int, horizon: int
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    per_horizon = [
        {"horizon": tick, "checks": 0, "violations": 0}
        for tick in range(horizon + 1)
    ]
    max_parent_vertices = 0
    max_child_vertices = 0
    for model_index in range(models):
        model = _mimo_model(rng)
        generated.append(_mimo_model_json(model))
        parent = model["initial"]
        child = model["initial"]
        for tick in range(horizon + 1):
            per_horizon[tick]["checks"] += 1
            max_parent_vertices = max(max_parent_vertices, len(parent))
            max_child_vertices = max(max_child_vertices, len(child))
            if not polytope_is_subset(child, parent):
                per_horizon[tick]["violations"] += 1
                violations.append(
                    {
                        "model_index": model_index,
                        "horizon": tick,
                        "model": _mimo_model_json(model),
                        "parent_reachable": _polytope_json(parent),
                        "child_reachable": _polytope_json(child),
                    }
                )
            if tick < horizon:
                parent = propagate_polytope(
                    parent,
                    model["parent_action"],
                    model["disturbance"],
                    model["a"],
                    model["b"],
                )
                child = propagate_polytope(
                    child,
                    model["child_action"],
                    model["disturbance"],
                    model["a"],
                    model["b"],
                )
    return (
        {
            "models": models,
            "horizon_checks": models * (horizon + 1),
            "violations": len(violations),
            "max_parent_vertices": max_parent_vertices,
            "max_child_vertices": max_child_vertices,
        },
        per_horizon,
        violations,
    )


def _history_key(trace: Trace, count_modulus: int) -> tuple[int, int, int]:
    states, actions, _ = trace
    last_action = actions[-1] if actions else -1
    return states[-1], last_action, sum(actions) % count_modulus


def _history_model(
    rng: random.Random, *, states: int, actions: int, disturbances: int, count_modulus: int
) -> dict[str, Any]:
    transition = [
        [
            [rng.randrange(states) for _ in range(disturbances)]
            for _ in range(actions)
        ]
        for _ in range(states)
    ]
    parent_relation: dict[tuple[int, int, int], frozenset[int]] = {}
    child_relation: dict[tuple[int, int, int], frozenset[int]] = {}
    for state, last_action, count_mod in itertools.product(
        range(states), range(-1, actions), range(count_modulus)
    ):
        key = (state, last_action, count_mod)
        parent = {action for action in range(actions) if rng.random() < 0.7}
        if not parent:
            parent.add(rng.randrange(actions))
        child = {action for action in parent if rng.random() < 0.55}
        parent_relation[key] = frozenset(parent)
        child_relation[key] = frozenset(child)
    return {
        "transition": transition,
        "parent_relation": parent_relation,
        "child_relation": child_relation,
        "initial_states": (0, 1),
        "disturbances": tuple(range(disturbances)),
        "count_modulus": count_modulus,
    }


def _relation_json(relation: dict[tuple[int, int, int], frozenset[int]]) -> dict[str, list[int]]:
    return {
        ",".join(map(str, key)): sorted(actions)
        for key, actions in sorted(relation.items())
    }


def _history_model_json(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "transition": model["transition"],
        "parent_relation": _relation_json(model["parent_relation"]),
        "child_relation": _relation_json(model["child_relation"]),
        "initial_states": list(model["initial_states"]),
        "disturbances": list(model["disturbances"]),
        "count_modulus": model["count_modulus"],
    }


def _advance_traces(
    traces: set[Trace],
    relation: dict[tuple[int, int, int], frozenset[int]],
    model: dict[str, Any],
) -> set[Trace]:
    next_traces: set[Trace] = set()
    for states, actions, disturbances in traces:
        trace = (states, actions, disturbances)
        key = _history_key(trace, model["count_modulus"])
        for action, disturbance in itertools.product(
            relation[key], model["disturbances"]
        ):
            next_state = model["transition"][states[-1]][action][disturbance]
            next_traces.add(
                (
                    states + (next_state,),
                    actions + (action,),
                    disturbances + (disturbance,),
                )
            )
    return next_traces


def run_history_seed(
    rng: random.Random,
    *,
    models: int,
    horizon: int,
    states: int,
    actions: int,
    disturbances: int,
    count_modulus: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []
    per_horizon = [
        {
            "horizon": tick,
            "trace_checks": 0,
            "trace_violations": 0,
            "reachable_state_violations": 0,
        }
        for tick in range(horizon + 1)
    ]
    total_parent_traces = 0
    total_child_traces = 0
    for model_index in range(models):
        model = _history_model(
            rng,
            states=states,
            actions=actions,
            disturbances=disturbances,
            count_modulus=count_modulus,
        )
        generated.append(_history_model_json(model))
        parent_traces: set[Trace] = {
            ((state,), (), ()) for state in model["initial_states"]
        }
        child_traces = set(parent_traces)
        for tick in range(horizon + 1):
            child_only_traces = child_traces - parent_traces
            parent_states = {trace[0][-1] for trace in parent_traces}
            child_states = {trace[0][-1] for trace in child_traces}
            child_only_states = child_states - parent_states
            per_horizon[tick]["trace_checks"] += len(child_traces)
            per_horizon[tick]["trace_violations"] += len(child_only_traces)
            per_horizon[tick]["reachable_state_violations"] += len(
                child_only_states
            )
            if child_only_traces or child_only_states:
                violations.append(
                    {
                        "model_index": model_index,
                        "horizon": tick,
                        "model": _history_model_json(model),
                        "child_only_traces": [
                            [list(part) for part in trace]
                            for trace in sorted(child_only_traces)[:10]
                        ],
                        "child_only_states": sorted(child_only_states),
                    }
                )
            total_parent_traces += len(parent_traces)
            total_child_traces += len(child_traces)
            if tick < horizon:
                parent_traces = _advance_traces(
                    parent_traces, model["parent_relation"], model
                )
                child_traces = _advance_traces(
                    child_traces, model["child_relation"], model
                )
    return (
        {
            "models": models,
            "horizon_checks": models * (horizon + 1),
            "child_trace_membership_checks": sum(
                entry["trace_checks"] for entry in per_horizon
            ),
            "trace_violations": sum(
                entry["trace_violations"] for entry in per_horizon
            ),
            "reachable_state_violations": sum(
                entry["reachable_state_violations"] for entry in per_horizon
            ),
            "total_parent_trace_frontier_sizes": total_parent_traces,
            "total_child_trace_frontier_sizes": total_child_traces,
        },
        per_horizon,
        violations,
    )


def negative_controls() -> dict[str, Any]:
    parent_action = _box(Fraction(-1), Fraction(1), Fraction(-1), Fraction(1))
    widened_child = convex_hull(parent_action + ((Fraction(2), Fraction(0)),))
    identity: Matrix2 = ((1, 0), (0, 1))
    zero: Matrix2 = ((0, 0), (0, 0))
    origin = ((Fraction(0), Fraction(0)),)
    parent_reach = propagate_polytope(origin, parent_action, origin, zero, identity)
    child_reach = propagate_polytope(origin, widened_child, origin, zero, identity)
    mimo_detected = not polytope_is_subset(child_reach, parent_reach)

    parent_traces: set[Trace] = {((0,), (), ())}
    parent_relation = {(0, -1, 0): frozenset({0})}
    child_relation = {(0, -1, 0): frozenset({0, 1})}
    model = {
        "transition": [[[1], [2]], [[1], [1]], [[2], [2]]],
        "disturbances": (0,),
        "count_modulus": 1,
    }
    parent_next = _advance_traces(parent_traces, parent_relation, model)
    child_next = _advance_traces(parent_traces, child_relation, model)
    history_detected = bool(child_next - parent_next) and (
        {trace[0][-1] for trace in child_next}
        - {trace[0][-1] for trace in parent_next}
        == {2}
    )
    return {
        "mimo_widening_detected": mimo_detected,
        "mimo_child_only_vertex": ["2", "0"],
        "history_widening_detected": history_detected,
        "history_child_only_state": 2,
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
    seed_records: list[dict[str, Any]] = []
    per_horizon_records: dict[str, Any] = {}
    all_violations: list[dict[str, Any]] = []
    for seed in config["seeds"]:
        mimo_rng = random.Random(seed)
        history_rng = random.Random(seed ^ 0x5A5A5A5A)
        mimo, mimo_horizons, mimo_violations = run_mimo_seed(
            mimo_rng,
            models=config["mimo_models_per_seed"],
            horizon=config["mimo_horizon"],
        )
        history, history_horizons, history_violations = run_history_seed(
            history_rng,
            models=config["history_models_per_seed"],
            horizon=config["history_horizon"],
            states=config["history_states"],
            actions=config["history_actions"],
            disturbances=config["history_disturbances"],
            count_modulus=config["history_count_modulus"],
        )
        seed_records.append({"seed": seed, "mimo": mimo, "history": history})
        per_horizon_records[str(seed)] = {
            "mimo": mimo_horizons,
            "history": history_horizons,
        }
        if mimo_violations or history_violations:
            all_violations.append(
                {
                    "seed": seed,
                    "mimo": mimo_violations,
                    "history": history_violations,
                }
            )

    controls = negative_controls()
    if not all(controls[key] for key in ("mimo_widening_detected", "history_widening_detected")):
        raise AssertionError("registered negative controls must be detected")
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seeds": config["seeds"],
        "seed_count": len(config["seeds"]),
        "mimo_models": sum(record["mimo"]["models"] for record in seed_records),
        "mimo_horizon_checks": sum(
            record["mimo"]["horizon_checks"] for record in seed_records
        ),
        "mimo_inclusion_violations": sum(
            record["mimo"]["violations"] for record in seed_records
        ),
        "history_models": sum(
            record["history"]["models"] for record in seed_records
        ),
        "history_horizon_checks": sum(
            record["history"]["horizon_checks"] for record in seed_records
        ),
        "history_child_trace_membership_checks": sum(
            record["history"]["child_trace_membership_checks"]
            for record in seed_records
        ),
        "history_trace_inclusion_violations": sum(
            record["history"]["trace_violations"] for record in seed_records
        ),
        "history_reachable_state_inclusion_violations": sum(
            record["history"]["reachable_state_violations"]
            for record in seed_records
        ),
        "negative_controls_expected": 2,
        "negative_controls_detected": sum(
            controls[key]
            for key in ("mimo_widening_detected", "history_widening_detected")
        ),
        "registered_c1_counterexamples": len(all_violations),
        "per_seed": seed_records,
    }
    manifest_paths = [
        config_path,
        root / "src/zonecap/exp03.py",
        root / "tests/test_exp03.py",
        root / "research/mimo_history_audit.md",
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
        ("per_horizon.json", per_horizon_records),
        ("violations.json", all_violations),
        ("negative_controls.json", controls),
        ("manifest.json", manifest),
    ):
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    log = [
        f"experiment={config['exp']}",
        "seeds=" + ",".join(map(str, config["seeds"])),
        f"mimo_models={metrics['mimo_models']}",
        f"mimo_horizon_checks={metrics['mimo_horizon_checks']}",
        f"mimo_inclusion_violations={metrics['mimo_inclusion_violations']}",
        f"history_models={metrics['history_models']}",
        f"history_horizon_checks={metrics['history_horizon_checks']}",
        f"history_trace_inclusion_violations={metrics['history_trace_inclusion_violations']}",
        f"history_reachable_state_inclusion_violations={metrics['history_reachable_state_inclusion_violations']}",
        f"negative_controls_detected={metrics['negative_controls_detected']}",
        f"registered_c1_counterexamples={metrics['registered_c1_counterexamples']}",
    ]
    (output_dir / "log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    metrics = run(arguments.config, arguments.output_dir)
    summary = {key: value for key, value in metrics.items() if key != "per_seed"}
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
