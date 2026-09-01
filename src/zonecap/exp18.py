from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .concurrency import (
    ConcurrentState,
    PendingCommand,
    deadlocked,
    event_alphabet,
    symmetry_key,
    transition,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _classification(
    state: ConcurrentState, holders: int, timeout_ticks: int
) -> tuple[bool, bool, bool]:
    conflict = len(state.pending) >= 2
    approval_wait = any(
        command.high_risk and len(command.approvals) < min(2, holders)
        for command in state.pending
    )
    return deadlocked(state, holders, timeout_ticks), conflict, approval_wait


def converge(holders: int, max_depth: int, timeout_ticks: int) -> dict[str, Any]:
    alphabet = event_alphabet(holders)
    initial = ConcurrentState()
    reachable = {initial}
    frontier = {initial}
    layers = [{"depth": 0, "new_states": 1, "reachable_states": 1}]
    counters: Counter[str] = Counter()
    violation_examples: list[dict[str, Any]] = []
    convergence_depth: int | None = None

    for depth in range(1, max_depth + 1):
        new_states: set[ConcurrentState] = set()
        for state in frontier:
            for event in alphabet:
                next_state, record = transition(
                    state, event, holders=holders, timeout_ticks=timeout_ticks
                )
                counters["edges"] += 1
                counters["cycle_edges"] += next_state in reachable
                counters["executions"] += record["executed"] is not None
                counters["timeouts"] += record["timeout_count"]
                for key in (
                    "post_revocation_violation",
                    "permission_union_violation",
                    "deterministic_resolution_violation",
                    "deadlock",
                ):
                    counters[key] += record[key]
                if next_state not in reachable:
                    new_states.add(next_state)
                if any(
                    record[key]
                    for key in (
                        "post_revocation_violation",
                        "permission_union_violation",
                        "deterministic_resolution_violation",
                        "deadlock",
                    )
                ) and len(violation_examples) < 10:
                    violation_examples.append(
                        {"depth": depth, "event": event, "record": record}
                    )
        new_states -= reachable
        reachable.update(new_states)
        layers.append(
            {
                "depth": depth,
                "new_states": len(new_states),
                "reachable_states": len(reachable),
            }
        )
        if not new_states:
            convergence_depth = depth
            break
        frontier = new_states

    closure_missing: set[ConcurrentState] = set()
    for state in reachable:
        for event in alphabet:
            next_state, _ = transition(
                state, event, holders=holders, timeout_ticks=timeout_ticks
            )
            if next_state not in reachable:
                closure_missing.add(next_state)

    buckets: dict[tuple[Any, ...], list[ConcurrentState]] = defaultdict(list)
    for state in reachable:
        buckets[symmetry_key(state, holders)].append(state)
    classification_mismatches = []
    for key, states in buckets.items():
        classifications = {
            _classification(state, holders, timeout_ticks) for state in states
        }
        if len(classifications) != 1:
            classification_mismatches.append(
                {
                    "canonical_key": repr(key),
                    "classifications": [list(item) for item in classifications],
                }
            )

    return {
        "holders": holders,
        "max_depth": max_depth,
        "converged": convergence_depth is not None,
        "convergence_depth": convergence_depth,
        "layers": layers,
        "exact_reachable_states": len(reachable),
        "canonical_reachable_states": len(buckets),
        "symmetry_reduction_fraction": 1 - len(buckets) / len(reachable),
        "expanded_edges": counters["edges"],
        "cycle_edges": counters["cycle_edges"],
        "executions": counters["executions"],
        "timeouts": counters["timeouts"],
        "closure_missing_states": len(closure_missing),
        "post_revocation_executions": counters["post_revocation_violation"],
        "permission_union_violations": counters["permission_union_violation"],
        "deterministic_resolution_violations": counters[
            "deterministic_resolution_violation"
        ],
        "deadlocks": counters["deadlock"],
        "symmetry_classification_mismatches": len(classification_mismatches),
        "classification_mismatch_examples": classification_mismatches[:10],
        "violation_examples": violation_examples,
    }


def negative_control(timeout_ticks: int) -> dict[str, Any]:
    impossible = ConcurrentState(
        pending=(
            PendingCommand(
                holder=0,
                action="action_0",
                value=10,
                high_risk=True,
                approvals=frozenset(),
                age=timeout_ticks,
            ),
        )
    )
    detected = deadlocked(impossible, holders=2, timeout_ticks=timeout_ticks)
    return {
        "mutant": "retain_timed_out_high_risk_pending_state",
        "detected": detected,
        "state": repr(impossible),
    }


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-18 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    records = [
        converge(
            holders,
            max_depth=config["max_depth"],
            timeout_ticks=config["approval_timeout_ticks"],
        )
        for holders in config["holder_counts"]
    ]
    for record in records:
        bound_five_states = config["bound_five_exact_states"][str(record["holders"])]
        record["bound_five_exact_states"] = bound_five_states
        record["new_exact_states_after_bound_five"] = (
            record["exact_reachable_states"] - bound_five_states
        )
    control = negative_control(config["approval_timeout_ticks"])
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "holder_configurations": len(records),
        "converged_configurations": sum(record["converged"] for record in records),
        "maximum_convergence_depth": max(
            record["convergence_depth"] or config["max_depth"] + 1
            for record in records
        ),
        "exact_reachable_states_sum": sum(
            record["exact_reachable_states"] for record in records
        ),
        "canonical_reachable_states_sum": sum(
            record["canonical_reachable_states"] for record in records
        ),
        "new_exact_states_after_bound_five_sum": sum(
            record["new_exact_states_after_bound_five"] for record in records
        ),
        "expanded_edges": sum(record["expanded_edges"] for record in records),
        "cycle_edges": sum(record["cycle_edges"] for record in records),
        "closure_missing_states": sum(
            record["closure_missing_states"] for record in records
        ),
        "post_revocation_executions": sum(
            record["post_revocation_executions"] for record in records
        ),
        "permission_union_violations": sum(
            record["permission_union_violations"] for record in records
        ),
        "deterministic_resolution_violations": sum(
            record["deterministic_resolution_violations"] for record in records
        ),
        "deadlocks": sum(record["deadlocks"] for record in records),
        "symmetry_classification_mismatches": sum(
            record["symmetry_classification_mismatches"] for record in records
        ),
        "negative_control_detected": control["detected"],
    }
    observed = {key: metrics.get(key) for key in config["expected_counts"]}
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": observed[key]}
        for key, expected in config["expected_counts"].items()
        if observed[key] != expected
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "per_holder.json", records)
    _write_json(output_dir / "negative_control.json", control)
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"converged_configurations={metrics['converged_configurations']}",
        f"maximum_convergence_depth={metrics['maximum_convergence_depth']}",
        f"exact_reachable_states_sum={metrics['exact_reachable_states_sum']}",
        f"canonical_reachable_states_sum={metrics['canonical_reachable_states_sum']}",
        "new_exact_states_after_bound_five_sum="
        f"{metrics['new_exact_states_after_bound_five_sum']}",
        f"cycle_edges={metrics['cycle_edges']}",
        f"closure_missing_states={metrics['closure_missing_states']}",
        f"deadlocks={metrics['deadlocks']}",
        f"negative_control_detected={str(metrics['negative_control_detected']).lower()}",
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
        "not_converged": len(records) - metrics["converged_configurations"],
        "closure_missing_states": metrics["closure_missing_states"],
        "post_revocation_executions": metrics["post_revocation_executions"],
        "permission_union_violations": metrics["permission_union_violations"],
        "deterministic_resolution_violations": metrics[
            "deterministic_resolution_violations"
        ],
        "deadlocks": metrics["deadlocks"],
        "symmetry_classification_mismatches": metrics[
            "symmetry_classification_mismatches"
        ],
        "canonical_larger_than_exact": metrics["canonical_reachable_states_sum"]
        > metrics["exact_reachable_states_sum"],
        "bound_five_state_regression": any(
            record["new_exact_states_after_bound_five"] < 0 for record in records
        ),
        "no_cycle_edges": metrics["cycle_edges"] == 0,
        "no_symmetry_reduction": metrics["canonical_reachable_states_sum"]
        >= metrics["exact_reachable_states_sum"],
        "negative_control_missed": not metrics["negative_control_detected"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-18 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
