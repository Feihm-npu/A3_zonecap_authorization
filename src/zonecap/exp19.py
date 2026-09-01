from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .concurrency import ConcurrentState, PendingCommand, transition


@dataclass(frozen=True)
class Scenario:
    name: str
    state: ConcurrentState
    revoke_holder: int


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _command(holder: int, *, approvals: frozenset[int] = frozenset()) -> PendingCommand:
    return PendingCommand(
        holder=holder,
        action=f"action_{holder}",
        value=10 * (holder + 1),
        high_risk=holder == 0,
        approvals=approvals,
    )


def scenarios() -> tuple[Scenario, ...]:
    approved = frozenset({0, 1})
    return (
        Scenario("ordinary_pending", ConcurrentState(pending=(_command(1),)), 1),
        Scenario(
            "approved_high_risk",
            ConcurrentState(pending=(_command(0, approvals=approved),)),
            0,
        ),
        Scenario(
            "conflict_revoked_winner",
            ConcurrentState(pending=(_command(1), _command(2))),
            1,
        ),
        Scenario(
            "conflict_revoked_loser",
            ConcurrentState(pending=(_command(1), _command(2))),
            2,
        ),
        Scenario(
            "mixed_revoked_high_risk_winner",
            ConcurrentState(
                pending=(_command(0, approvals=approved), _command(1))
            ),
            0,
        ),
    )


def fair_schedule(revoke_holder: int, delay: int, maximum_delay: int) -> tuple[str, ...]:
    if delay < 0 or delay > maximum_delay or maximum_delay != 2:
        raise ValueError("registered scheduler requires an exact delay in 0..2")
    later = ["resolve", "tick"]
    later.insert(delay, f"revoke_{revoke_holder}")
    return tuple(later)


def evaluate_schedule(
    scenario: Scenario,
    *,
    delay: int,
    maximum_delay: int,
    holders: int,
    timeout_ticks: int,
) -> dict[str, Any]:
    schedule = fair_schedule(scenario.revoke_holder, delay, maximum_delay)
    state = scenario.state
    records = []
    post_issuance_executions = 0
    post_delivery_executions = 0
    permission_union_violations = 0
    deterministic_resolution_violations = 0
    deadlocks = 0
    stale_executions_blocked_by_epoch_fence = 0

    for step, event in enumerate(schedule):
        next_state, record = transition(
            state,
            event,
            holders=holders,
            timeout_ticks=timeout_ticks,
        )
        executed_holder = (
            None if record["executed"] is None else record["executed"]["holder"]
        )
        post_issuance = executed_holder == scenario.revoke_holder
        post_issuance_executions += post_issuance
        post_delivery_executions += record["post_revocation_violation"]
        permission_union_violations += record["permission_union_violation"]
        deterministic_resolution_violations += record[
            "deterministic_resolution_violation"
        ]
        deadlocks += record["deadlock"]
        if post_issuance:
            fenced_state, _ = transition(
                state,
                f"revoke_{scenario.revoke_holder}",
                holders=holders,
                timeout_ticks=timeout_ticks,
            )
            _, fenced_record = transition(
                fenced_state,
                "resolve",
                holders=holders,
                timeout_ticks=timeout_ticks,
            )
            if (
                fenced_record["executed"] is None
                or fenced_record["executed"]["holder"] != scenario.revoke_holder
            ):
                stale_executions_blocked_by_epoch_fence += 1
        records.append(
            {
                "step": step,
                "event": event,
                "executed_holder": executed_holder,
                "post_issuance_revocation_execution": post_issuance,
                "local_revoked_before": sorted(state.revoked),
                "local_revoked_after": sorted(next_state.revoked),
            }
        )
        state = next_state

    target_pending = any(
        command.holder == scenario.revoke_holder for command in state.pending
    )
    return {
        "scenario": scenario.name,
        "revoke_holder": scenario.revoke_holder,
        "delay": delay,
        "schedule": list(schedule),
        "fair_delivery": Counter(schedule)
        == Counter((f"revoke_{scenario.revoke_holder}", "resolve", "tick")),
        "revocation_delivered": scenario.revoke_holder in state.revoked,
        "revoked_target_pending_at_end": target_pending,
        "post_issuance_revocation_executions": post_issuance_executions,
        "post_delivery_revocation_executions": post_delivery_executions,
        "permission_union_violations": permission_union_violations,
        "deterministic_resolution_violations": deterministic_resolution_violations,
        "deadlocks": deadlocks,
        "stale_executions_blocked_by_epoch_fence": (
            stale_executions_blocked_by_epoch_fence
        ),
        "records": records,
    }


def evaluate(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = scenarios()
    records = [
        evaluate_schedule(
            scenario,
            delay=delay,
            maximum_delay=config["maximum_delivery_delay"],
            holders=config["holders"],
            timeout_ticks=config["approval_timeout_ticks"],
        )
        for scenario in cases
        for delay in config["delivery_delays"]
    ]
    by_delay = {
        str(delay): {
            "schedules": sum(record["delay"] == delay for record in records),
            "post_issuance_revocation_executions": sum(
                record["post_issuance_revocation_executions"]
                for record in records
                if record["delay"] == delay
            ),
            "post_delivery_revocation_executions": sum(
                record["post_delivery_revocation_executions"]
                for record in records
                if record["delay"] == delay
            ),
        }
        for delay in config["delivery_delays"]
    }
    post_issuance = sum(
        record["post_issuance_revocation_executions"] for record in records
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "scenarios": len(cases),
        "fair_schedules": len(records),
        "central_fifo_schedules": sum(record["delay"] == 0 for record in records),
        "delayed_schedules": sum(record["delay"] > 0 for record in records),
        "all_schedules_fair": all(record["fair_delivery"] for record in records),
        "all_revocations_delivered": all(
            record["revocation_delivered"] for record in records
        ),
        "terminal_revoked_targets_pending": sum(
            record["revoked_target_pending_at_end"] for record in records
        ),
        "central_fifo_post_issuance_revocation_executions": sum(
            record["post_issuance_revocation_executions"]
            for record in records
            if record["delay"] == 0
        ),
        "adversarial_post_issuance_revocation_executions": post_issuance,
        "post_delivery_revocation_executions": sum(
            record["post_delivery_revocation_executions"] for record in records
        ),
        "permission_union_violations": sum(
            record["permission_union_violations"] for record in records
        ),
        "deterministic_resolution_violations": sum(
            record["deterministic_resolution_violations"] for record in records
        ),
        "deadlocks": sum(record["deadlocks"] for record in records),
        "stale_executions_blocked_by_epoch_fence": sum(
            record["stale_executions_blocked_by_epoch_fence"] for record in records
        ),
        "violations_by_delay": by_delay,
        "claim_supported_under_delayed_delivery": post_issuance == 0,
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
        raise RuntimeError("exp-19 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    records, metrics = evaluate(config)
    infrastructure = {
        "expected_counts": {
            key: {"expected": expected, "observed": metrics.get(key)}
            for key, expected in config["expected_counts"].items()
            if metrics.get(key) != expected
        },
        "unfair_schedule": not metrics["all_schedules_fair"],
        "undelivered_revocation": not metrics["all_revocations_delivered"],
        "terminal_revoked_target_pending": metrics[
            "terminal_revoked_targets_pending"
        ],
        "post_delivery_revocation_executions": metrics[
            "post_delivery_revocation_executions"
        ],
        "permission_union_violations": metrics["permission_union_violations"],
        "deterministic_resolution_violations": metrics[
            "deterministic_resolution_violations"
        ],
        "deadlocks": metrics["deadlocks"],
    }
    metrics["infrastructure_failures"] = infrastructure

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "schedules.json", records)
    _write_json(output_dir / "metrics.json", metrics)
    (output_dir / "log.txt").write_text(
        "\n".join(
            [
                f"experiment={config['exp']}",
                "seed=none",
                f"fair_schedules={metrics['fair_schedules']}",
                "central_fifo_post_issuance_revocation_executions="
                f"{metrics['central_fifo_post_issuance_revocation_executions']}",
                "adversarial_post_issuance_revocation_executions="
                f"{metrics['adversarial_post_issuance_revocation_executions']}",
                "post_delivery_revocation_executions="
                f"{metrics['post_delivery_revocation_executions']}",
                "claim_supported_under_delayed_delivery="
                f"{str(metrics['claim_supported_under_delayed_delivery']).lower()}",
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
    if any(infrastructure.values()):
        raise AssertionError(f"exp-19 infrastructure failure: {infrastructure}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
