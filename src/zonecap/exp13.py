from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Iterator


RICH_EFFECTS = {"allow", "deny", "attenuate", "rewrite", "defer"}
REPLACED_EFFECTS = {"attenuate", "rewrite", "defer"}


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


def deny_only_effect(rich_effect: str) -> str:
    if rich_effect not in RICH_EFFECTS:
        raise ValueError(f"unknown rich effect: {rich_effect}")
    return "allow" if rich_effect == "allow" else "deny"


def _mapping_violation(
    step: dict[str, Any], mapped_effect: str, mapped_emitted: Any
) -> bool:
    rich_effect = step["rich_effect"]
    return (
        not step["input_safe"]
        or (
            rich_effect in REPLACED_EFFECTS
            and (mapped_effect != "deny" or mapped_emitted is not None)
        )
        or (
            rich_effect == "allow"
            and (mapped_effect != "allow" or mapped_emitted != step["rich_emitted"])
        )
        or (
            rich_effect == "deny"
            and (mapped_effect != "deny" or mapped_emitted is not None)
        )
    )


def _case_steps(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            yield {
                "trace_kind": "heldout_one_request",
                "trace_id": row["case_id"],
                "policy_step": 0,
                "rich_effect": row["effect"],
                "rich_emitted": row["emitted"],
                "input_safe": not row["authority_violation"] and row["parent_realizable"],
            }


def _composed_steps(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            input_safe = (
                row["parent_trace_realizable"]
                and not row["effect_order_violations"]
                and not row["attenuation_violations"]
                and not row["authority_violations"]
                and not row["nonstutter_violations"]
                and not row["deadlocks"]
            )
            for step in row["steps"]:
                yield {
                    "trace_kind": "five_effect_composed",
                    "trace_id": row["case_id"],
                    "policy_step": step["policy_step"],
                    "rich_effect": step["effect"],
                    "rich_emitted": step["emitted"],
                    "input_safe": input_safe,
                }


def compare_step(step: dict[str, Any]) -> dict[str, Any]:
    rich_effect = step["rich_effect"]
    ablated_effect = deny_only_effect(rich_effect)
    ablated_emitted = step["rich_emitted"] if ablated_effect == "allow" else None
    safely_served = rich_effect in {"allow", "rewrite"}
    false_block = rich_effect == "rewrite" and ablated_emitted is None
    lost_recovery = rich_effect in {"attenuate", "defer"}
    return {
        **step,
        "deny_only_effect": ablated_effect,
        "deny_only_emitted": ablated_emitted,
        "safely_served_by_rich_semantics": safely_served,
        "deny_only_false_block": false_block,
        "lost_recoverable_decision": lost_recovery,
        "categorical_effect_distance": int(ablated_effect != rich_effect),
        "lost_rewrite_output": rich_effect == "rewrite" and step["rich_emitted"] is not None,
        "lost_defer_stutter": rich_effect == "defer" and step["rich_emitted"] is not None,
        "deny_only_safety_violation": _mapping_violation(
            step, ablated_effect, ablated_emitted
        ),
    }


def mutation_audit() -> dict[str, Any]:
    rewrite_step = {
        "trace_kind": "mutant",
        "trace_id": "rewrite",
        "policy_step": 0,
        "rich_effect": "rewrite",
        "rich_emitted": {"operation": "write", "value": 100.0},
        "input_safe": True,
    }
    allow_step = {
        **rewrite_step,
        "trace_id": "allow",
        "rich_effect": "allow",
        "rich_emitted": {"operation": "read", "value": 50.0},
    }
    checks = [
        {
            "mutant": "pass_through_out_of-range_raw_rewrite_request",
            "detected": _mapping_violation(
                rewrite_step,
                "allow",
                {"operation": "write", "value": "raw_outside_interval"},
            ),
        },
        {
            "mutant": "drop_original_allow_output",
            "detected": _mapping_violation(allow_step, "deny", None),
        },
        {
            "mutant": "emit_on_replaced_defer",
            "detected": _mapping_violation(
                {**rewrite_step, "rich_effect": "defer"},
                "deny",
                rewrite_step["rich_emitted"],
            ),
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
        raise RuntimeError("exp-13 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")

    counters: Counter[str] = Counter()
    effects: Counter[str] = Counter()
    composed_false_block_traces: set[str] = set()
    audit_path = output_dir / "decision_audit.jsonl.gz"
    sources = (
        _case_steps(root / config["exp12_case_audit"]),
        _composed_steps(root / config["exp12_composed_traces"]),
    )
    with gzip.open(audit_path, "wt", encoding="utf-8") as sink:
        for source in sources:
            for step in source:
                result = compare_step(step)
                counters["policy_steps"] += 1
                counters["heldout_steps"] += step["trace_kind"] == "heldout_one_request"
                counters["composed_steps"] += step["trace_kind"] == "five_effect_composed"
                counters["input_safety_violations"] += not step["input_safe"]
                counters["rich_safe_service_opportunities"] += result[
                    "safely_served_by_rich_semantics"
                ]
                counters["false_blocks"] += result["deny_only_false_block"]
                counters["lost_recoverable_decisions"] += result[
                    "lost_recoverable_decision"
                ]
                counters["categorical_effect_distance"] += result[
                    "categorical_effect_distance"
                ]
                counters["lost_rewrite_outputs"] += result["lost_rewrite_output"]
                counters["lost_defer_stutters"] += result["lost_defer_stutter"]
                counters["deny_only_safety_violations"] += result[
                    "deny_only_safety_violation"
                ]
                counters["rich_physical_outputs"] += result["rich_emitted"] is not None
                counters["deny_only_physical_outputs"] += (
                    result["deny_only_emitted"] is not None
                )
                effects[result["rich_effect"]] += 1
                if (
                    step["trace_kind"] == "five_effect_composed"
                    and result["deny_only_false_block"]
                ):
                    composed_false_block_traces.add(step["trace_id"])
                sink.write(json.dumps(result, sort_keys=True) + "\n")

    mutation = mutation_audit()
    _write_json(output_dir / "mutation_audit.json", mutation)
    false_block_rate_all = counters["false_blocks"] / counters["policy_steps"]
    false_block_rate_safe = (
        counters["false_blocks"] / counters["rich_safe_service_opportunities"]
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "policy_steps": counters["policy_steps"],
        "heldout_one_request_steps": counters["heldout_steps"],
        "composed_policy_steps": counters["composed_steps"],
        "rich_effect_counts": dict(sorted(effects.items())),
        "rich_safe_service_opportunities": counters["rich_safe_service_opportunities"],
        "deny_only_false_blocks": counters["false_blocks"],
        "false_block_rate_all_policy_steps": false_block_rate_all,
        "false_block_rate_safe_service_opportunities": false_block_rate_safe,
        "composed_traces_with_false_block": len(composed_false_block_traces),
        "lost_recoverable_decisions": counters["lost_recoverable_decisions"],
        "categorical_effect_distance": counters["categorical_effect_distance"],
        "rich_physical_outputs": counters["rich_physical_outputs"],
        "deny_only_physical_outputs": counters["deny_only_physical_outputs"],
        "lost_physical_outputs": counters["rich_physical_outputs"]
        - counters["deny_only_physical_outputs"],
        "lost_rewrite_outputs": counters["lost_rewrite_outputs"],
        "lost_defer_stutters": counters["lost_defer_stutters"],
        "rich_rewrite_l1_edit_distance_mean": config["registered_rewrite_offset"],
        "rich_rewrite_l1_edit_distance_max": config["registered_rewrite_offset"],
        "deny_only_numeric_edit_distance": "N/A: no emitted value",
        "input_safety_violations": counters["input_safety_violations"],
        "deny_only_safety_violations": counters["deny_only_safety_violations"],
        "negative_control_mutants": mutation["mutants"],
        "negative_control_mutants_killed": mutation["killed"],
    }
    observed_counts = {
        "policy_steps": metrics["policy_steps"],
        "heldout_one_request_steps": metrics["heldout_one_request_steps"],
        "composed_policy_steps": metrics["composed_policy_steps"],
        "deny_only_false_blocks": metrics["deny_only_false_blocks"],
        "composed_traces_with_false_block": metrics["composed_traces_with_false_block"],
        "lost_recoverable_decisions": metrics["lost_recoverable_decisions"],
        "categorical_effect_distance": metrics["categorical_effect_distance"],
        "rich_physical_outputs": metrics["rich_physical_outputs"],
        "deny_only_physical_outputs": metrics["deny_only_physical_outputs"],
        "lost_rewrite_outputs": metrics["lost_rewrite_outputs"],
        "lost_defer_stutters": metrics["lost_defer_stutters"],
    }
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": observed_counts.get(key)}
        for key, expected in config["expected_counts"].items()
        if observed_counts.get(key) != expected
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"policy_steps={metrics['policy_steps']}",
        f"deny_only_false_blocks={metrics['deny_only_false_blocks']}",
        f"false_block_rate_all_policy_steps={metrics['false_block_rate_all_policy_steps']}",
        f"false_block_rate_safe_service_opportunities={metrics['false_block_rate_safe_service_opportunities']}",
        f"lost_recoverable_decisions={metrics['lost_recoverable_decisions']}",
        f"deny_only_safety_violations={metrics['deny_only_safety_violations']}",
        f"negative_control_mutants_killed={metrics['negative_control_mutants_killed']}/{metrics['negative_control_mutants']}",
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
        "outputs": {
            str(path.relative_to(output_dir)): _sha256(path) for path in output_paths
        },
    }
    _write_json(output_dir / "manifest.json", manifest)

    failures = {
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
        "zero_false_blocks": metrics["deny_only_false_blocks"] == 0,
        "input_safety_violations": metrics["input_safety_violations"],
        "deny_only_safety_violations": metrics["deny_only_safety_violations"],
        "negative_control_survivors": mutation["mutants"] - mutation["killed"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-13 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
