from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .concurrency import ConcurrentState, event_alphabet, transition


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def explore(holders: int, horizon: int, timeout_ticks: int) -> dict[str, Any]:
    alphabet = event_alphabet(holders)
    counters: Counter[str] = Counter(words=1)
    states = {ConcurrentState()}
    conflict_states: set[ConcurrentState] = set()
    approval_wait_states: set[ConcurrentState] = set()
    revocation_after_submit = False
    violation_examples: list[dict[str, Any]] = []
    resolution_depths: Counter[int] = Counter()
    seen_patterns: set[tuple[str, ...]] = set()

    def visit(state: ConcurrentState, path: tuple[str, ...], depth: int) -> None:
        nonlocal revocation_after_submit
        if depth == horizon:
            return
        for event in alphabet:
            next_state, record = transition(
                state, event, holders=holders, timeout_ticks=timeout_ticks
            )
            new_path = (*path, event)
            counters["words"] += 1
            counters["transitions"] += 1
            counters["changed_transitions"] += record["changed"]
            counters["executions"] += record["executed"] is not None
            counters["timeouts"] += record["timeout_count"]
            counters["conflict_resolutions"] += record["conflict_candidates"] >= 2
            for key in (
                "post_revocation_violation",
                "permission_union_violation",
                "deterministic_resolution_violation",
                "deadlock",
            ):
                counters[key] += record[key]
            if record["executed"] is not None:
                resolution_depths[depth + 1] += 1
            if len(new_path) >= 2:
                seen_patterns.add(new_path[-2:])
            states.add(next_state)
            if len(next_state.pending) >= 2:
                conflict_states.add(next_state)
            if any(command.high_risk and len(command.approvals) < min(2, holders) for command in next_state.pending):
                approval_wait_states.add(next_state)
            if event.startswith("revoke_"):
                holder = event.rsplit("_", 1)[1]
                revocation_after_submit = revocation_after_submit or f"submit_{holder}" in path
            violations = {
                key: record[key]
                for key in (
                    "post_revocation_violation",
                    "permission_union_violation",
                    "deterministic_resolution_violation",
                    "deadlock",
                )
                if record[key]
            }
            if violations and len(violation_examples) < 10:
                violation_examples.append(
                    {"path": list(new_path), "record": record, "violations": violations}
                )
            visit(next_state, new_path, depth + 1)

    visit(ConcurrentState(), tuple(), 0)
    return {
        "holders": holders,
        "alphabet_size": len(alphabet),
        "horizon": horizon,
        "words": counters["words"],
        "transitions": counters["transitions"],
        "changed_transitions": counters["changed_transitions"],
        "unique_states": len(states),
        "unique_conflict_states": len(conflict_states),
        "unique_approval_wait_states": len(approval_wait_states),
        "executions": counters["executions"],
        "timeouts": counters["timeouts"],
        "conflict_resolutions": counters["conflict_resolutions"],
        "revocation_after_submit_reachable": revocation_after_submit,
        "post_revocation_executions": counters["post_revocation_violation"],
        "permission_union_violations": counters["permission_union_violation"],
        "deterministic_resolution_violations": counters[
            "deterministic_resolution_violation"
        ],
        "deadlocks": counters["deadlock"],
        "resolution_depths": dict(sorted(resolution_depths.items())),
        "seen_event_pairs": [list(pair) for pair in sorted(seen_patterns)],
        "violation_examples": violation_examples,
    }


def mutation_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = {
        tuple(pair)
        for record in records
        for pair in record["seen_event_pairs"]
    }
    checks = [
        {
            "mutant": "retain_and_execute_revoked_command",
            "detected": ("submit_0", "revoke_0") in pairs,
        },
        {
            "mutant": "union_action_0_with_value_1",
            "detected": any(record["unique_conflict_states"] > 0 for record in records),
        },
        {
            "mutant": "choose_maximum_id_winner",
            "detected": any(record["conflict_resolutions"] > 0 for record in records),
        },
        {
            "mutant": "remove_approval_and_timeout_progress",
            "detected": any(record["unique_approval_wait_states"] > 0 for record in records),
        },
    ]
    return {
        "mutants": len(checks),
        "killed": sum(check["detected"] for check in checks),
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
        raise RuntimeError("exp-17 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    records = [
        explore(holders, config["horizon"], config["approval_timeout_ticks"])
        for holders in config["holder_counts"]
    ]
    mutation = mutation_audit(records)
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "holder_configurations": len(records),
        "holder_counts": config["holder_counts"],
        "horizon": config["horizon"],
        "words": sum(record["words"] for record in records),
        "transitions": sum(record["transitions"] for record in records),
        "unique_states_sum": sum(record["unique_states"] for record in records),
        "unique_conflict_states_sum": sum(
            record["unique_conflict_states"] for record in records
        ),
        "unique_approval_wait_states_sum": sum(
            record["unique_approval_wait_states"] for record in records
        ),
        "executions": sum(record["executions"] for record in records),
        "timeouts": sum(record["timeouts"] for record in records),
        "conflict_resolutions": sum(
            record["conflict_resolutions"] for record in records
        ),
        "revocation_after_submit_configurations": sum(
            record["revocation_after_submit_reachable"] for record in records
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
        "mutants": mutation["mutants"],
        "mutants_killed": mutation["killed"],
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
    _write_json(output_dir / "mutation_audit.json", mutation)
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"words={metrics['words']}",
        f"transitions={metrics['transitions']}",
        f"executions={metrics['executions']}",
        f"timeouts={metrics['timeouts']}",
        f"conflict_resolutions={metrics['conflict_resolutions']}",
        f"post_revocation_executions={metrics['post_revocation_executions']}",
        f"permission_union_violations={metrics['permission_union_violations']}",
        f"deadlocks={metrics['deadlocks']}",
        f"mutants_killed={metrics['mutants_killed']}/{metrics['mutants']}",
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
        "no_conflicts": metrics["conflict_resolutions"] == 0,
        "no_conflict_states": metrics["unique_conflict_states_sum"] == 0,
        "no_approval_wait_states": metrics["unique_approval_wait_states_sum"] == 0,
        "no_timeouts": metrics["timeouts"] == 0,
        "post_revocation_executions": metrics["post_revocation_executions"],
        "permission_union_violations": metrics["permission_union_violations"],
        "deterministic_resolution_violations": metrics[
            "deterministic_resolution_violations"
        ],
        "deadlocks": metrics["deadlocks"],
        "mutant_survivors": mutation["mutants"] - mutation["killed"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-17 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
