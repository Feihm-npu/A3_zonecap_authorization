from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .concurrency import ConcurrentState, PendingCommand, transition


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _ordinary(holder: int) -> PendingCommand:
    return PendingCommand(
        holder=holder,
        action=f"action_{holder}",
        value=10 * (holder + 1),
        high_risk=False,
    )


def case_specs() -> tuple[tuple[str, ConcurrentState, tuple[str, ...]], ...]:
    return (
        (
            "immediate_revoke",
            ConcurrentState(),
            ("submit_1", "revoke_1", "resolve"),
        ),
        (
            "duplicate_revoke",
            ConcurrentState(),
            ("submit_1", "revoke_1", "revoke_1", "resolve"),
        ),
        (
            "simultaneous_equal_priority",
            ConcurrentState(pending=(_ordinary(1), _ordinary(2))),
            ("resolve", "resolve"),
        ),
        (
            "permanent_missing_approval",
            ConcurrentState(),
            ("submit_0", "tick", "tick", "resolve"),
        ),
    )


def evaluate_case(
    name: str,
    initial: ConcurrentState,
    events: tuple[str, ...],
    *,
    holders: int,
    timeout_ticks: int,
) -> dict[str, Any]:
    state = initial
    records = []
    execution_order = []
    timeout_count = 0
    for event in events:
        state, record = transition(
            state,
            event,
            holders=holders,
            timeout_ticks=timeout_ticks,
        )
        if record["executed"] is not None:
            execution_order.append(record["executed"]["holder"])
        timeout_count += record["timeout_count"]
        records.append(record)
    return {
        "name": name,
        "events": list(events),
        "changed": [record["changed"] for record in records],
        "execution_order": execution_order,
        "timeouts": timeout_count,
        "final_revoked": sorted(state.revoked),
        "final_pending_holders": [command.holder for command in state.pending],
        "post_revocation_executions": sum(
            record["post_revocation_violation"] for record in records
        ),
        "permission_union_violations": sum(
            record["permission_union_violation"] for record in records
        ),
        "deterministic_resolution_violations": sum(
            record["deterministic_resolution_violation"] for record in records
        ),
        "deadlocks": sum(record["deadlock"] for record in records),
        "conflict_candidate_counts": [
            record["conflict_candidates"]
            for record in records
            if record["event"] == "resolve"
        ],
    }


def evaluate(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = [
        evaluate_case(
            name,
            initial,
            events,
            holders=config["holders"],
            timeout_ticks=config["approval_timeout_ticks"],
        )
        for name, initial, events in case_specs()
    ]
    expected = config["expected_cases"]
    mismatches = {}
    for record in records:
        case_expected = expected[record["name"]]
        differences = {
            field: {"expected": value, "observed": record.get(field)}
            for field, value in case_expected.items()
            if record.get(field) != value
        }
        if differences:
            mismatches[record["name"]] = differences
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "cases": len(records),
        "cases_matching_expected_terminal_state": len(records) - len(mismatches),
        "case_mismatches": mismatches,
        "executions": sum(len(record["execution_order"]) for record in records),
        "timeouts": sum(record["timeouts"] for record in records),
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
    }
    return records, metrics


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-21 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    records, metrics = evaluate(config)
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": metrics.get(key)}
        for key, expected in config["expected_counts"].items()
        if metrics.get(key) != expected
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "cases.json", records)
    _write_json(output_dir / "metrics.json", metrics)
    (output_dir / "log.txt").write_text(
        "\n".join(
            [
                f"experiment={config['exp']}",
                "seed=none",
                f"cases={metrics['cases']}",
                "cases_matching_expected_terminal_state="
                f"{metrics['cases_matching_expected_terminal_state']}",
                f"executions={metrics['executions']}",
                f"timeouts={metrics['timeouts']}",
                f"post_revocation_executions={metrics['post_revocation_executions']}",
                f"deadlocks={metrics['deadlocks']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    input_paths = [config_path, *[root / path for path in config["frozen_hashes"]]]
    output_paths = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
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
        "case_mismatches": bool(metrics["case_mismatches"]),
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
    }
    if any(failures.values()):
        raise AssertionError(f"exp-21 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()

