from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def summarize(raw: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    revocation = raw["localRevocationTrace"]
    quorum = raw["quorumConflictTrace"]
    timeout = raw["missingApprovalTrace"]
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "sint_commit": raw["commit"],
        "sint_commit_match": raw["commit"] == config["sint_commit"],
        "source_files_checked": len(config["sint_source_hashes"]),
        "source_hash_mismatches": {
            path: {"expected": expected, "observed": raw["sourceHashes"].get(path)}
            for path, expected in config["sint_source_hashes"].items()
            if raw["sourceHashes"].get(path) != expected
        },
        "pre_revocation_allows": int(revocation["beforeRevocation"] == "allow"),
        "issued_not_delivered_allows": int(
            revocation["issuedButNotDelivered"] == "allow"
        ),
        "post_delivery_revocation_denies": int(
            revocation["afterDelivery"] == "deny"
            and revocation["afterDeliveryPolicy"] == "TOKEN_REVOKED"
        ),
        "initial_escalations": sum(
            action == "escalate" for action in quorum["gatewayInitialActions"]
        ),
        "first_votes_pending": quorum["firstVotesPending"],
        "approval_count_after_duplicate": quorum["approvalCountAfterDuplicate"],
        "revoked_enqueued_request_approved": int(
            quorum["revokedRequestResolution"] == "approved"
        ),
        "same_resource_requests_approved": quorum["approvedSameResourceRequests"],
        "cross_request_winners": int(quorum["crossRequestWinner"] is not None),
        "revoked_gateway_recheck_denies": int(
            quorum["revokedGatewayRecheck"] == "deny"
            and quorum["revokedGatewayRecheckPolicy"] == "TOKEN_REVOKED"
        ),
        "missing_approval_timeouts": int(
            timeout["timedOut"] and timeout["fallbackAction"] == "deny"
        ),
        "timeout_pending_at_end": timeout["pendingAtEnd"],
    }
    comparison = {
        "sint_commit": raw["commit"],
        "trace_results": {
            "delivered_local_revocation": "full",
            "issuance_time_revocation_with_stale_local_store": (
                "absent" if metrics["issued_not_delivered_allows"] else "full"
            ),
            "two_of_three_approval": "full",
            "duplicate_vote_suppression": (
                "full" if metrics["approval_count_after_duplicate"] == 1 else "absent"
            ),
            "missing_approval_timeout": (
                "full" if metrics["missing_approval_timeouts"] == 1 else "absent"
            ),
            "revocation_recheck_after_approval": (
                "full" if metrics["revoked_gateway_recheck_denies"] == 1 else "absent"
            ),
            "revoke_pending_approval_atomically": (
                "absent" if metrics["revoked_enqueued_request_approved"] else "full"
            ),
            "same_asset_deterministic_conflict_winner": (
                "absent" if metrics["cross_request_winners"] == 0 else "full"
            ),
            "atomic_permission_union_property": "N/A: requests and tokens remain independent; no cross-request command tuple exists",
        },
        "interpretation_boundary": (
            "ApprovalQueue resolution is not physical execution. The revoked request "
            "is denied if the consumer performs a fresh PolicyGateway interception; "
            "the pinned API does not make that recheck atomic with queue resolution."
        ),
    }
    return metrics, comparison


def run(config_path: Path, output_dir: Path, sint_repo: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    sint_repo = sint_repo.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-20 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")
    if _git(sint_repo, "rev-parse", "HEAD") != config["sint_commit"]:
        raise RuntimeError("pinned SINT commit mismatch")
    for relative_path, expected_hash in config["sint_source_hashes"].items():
        if _sha256(sint_repo / relative_path) != expected_hash:
            raise RuntimeError(f"SINT source hash mismatch: {relative_path}")

    output_dir.mkdir(parents=True, exist_ok=False)
    raw_path = output_dir / "sint_raw.json"
    completed = subprocess.run(
        [
            "node",
            str(root / "scripts/exp20_sint_runner.mjs"),
            "--sint-repo",
            str(sint_repo),
            "--output",
            str(raw_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    metrics, comparison = summarize(raw, config)
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": metrics.get(key)}
        for key, expected in config["expected_counts"].items()
        if metrics.get(key) != expected
    }

    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "metrics.json", metrics)
    _write_json(output_dir / "decision_state_machine_delta.json", comparison)
    (output_dir / "runner_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "runner_stderr.log").write_text(completed.stderr, encoding="utf-8")
    (output_dir / "log.txt").write_text(
        "\n".join(
            [
                f"experiment={config['exp']}",
                "seed=none",
                f"sint_commit={metrics['sint_commit']}",
                f"issued_not_delivered_allows={metrics['issued_not_delivered_allows']}",
                f"post_delivery_revocation_denies={metrics['post_delivery_revocation_denies']}",
                f"revoked_enqueued_request_approved={metrics['revoked_enqueued_request_approved']}",
                f"same_resource_requests_approved={metrics['same_resource_requests_approved']}",
                f"revoked_gateway_recheck_denies={metrics['revoked_gateway_recheck_denies']}",
                f"missing_approval_timeouts={metrics['missing_approval_timeouts']}",
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
        "node": subprocess.run(
            ["node", "--version"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "sint_commit": _git(sint_repo, "rev-parse", "HEAD"),
        "sint_git_status": _git(sint_repo, "status", "--porcelain"),
        "inputs": {str(path.relative_to(root)): _sha256(path) for path in input_paths},
        "sint_sources": {
            path: _sha256(sint_repo / path) for path in config["sint_source_hashes"]
        },
        "outputs": {
            str(path.relative_to(output_dir)): _sha256(path) for path in output_paths
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    failures = {
        "commit_mismatch": not metrics["sint_commit_match"],
        "source_hash_mismatches": bool(metrics["source_hash_mismatches"]),
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
    }
    if any(failures.values()):
        raise AssertionError(f"exp-20 infrastructure failure: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sint-repo", type=Path, required=True)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run(arguments.config, arguments.output_dir, arguments.sint_repo),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

