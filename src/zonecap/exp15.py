from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .models import Effect


ALLOWED_EFFECT_STATUS = {"exact", "partial", "absent"}


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


def validate_mapping(mapping: dict[str, Any]) -> None:
    expected_effects = {effect.value for effect in Effect}
    expected_systems = set(mapping["systems"])
    for system, document in mapping["systems"].items():
        effects = document["effects"]
        if set(effects) != expected_effects:
            raise ValueError(f"{system}: effect mapping is incomplete")
        for effect, record in effects.items():
            if record["status"] not in ALLOWED_EFFECT_STATUS:
                raise ValueError(f"{system}/{effect}: invalid coverage status")
            if not record["projection"]:
                raise ValueError(f"{system}/{effect}: missing projection")
    for record in mapping["properties"]:
        if set(record) - {"property"} != expected_systems:
            raise ValueError(f"property row has incomplete systems: {record['property']}")
        if any(record[system] not in ALLOWED_EFFECT_STATUS for system in expected_systems):
            raise ValueError(f"property row has invalid status: {record['property']}")


def summarize_effect_coverage(
    mapping: dict[str, Any], effect_counts: dict[str, int]
) -> dict[str, Any]:
    total_steps = sum(effect_counts.values())
    summaries: dict[str, Any] = {}
    for system, document in mapping["systems"].items():
        type_counts: Counter[str] = Counter()
        weighted: Counter[str] = Counter()
        projections: Counter[str] = Counter()
        for effect, count in effect_counts.items():
            record = document["effects"][effect]
            type_counts[record["status"]] += 1
            weighted[record["status"]] += count
            projections[record["projection"]] += count
        summaries[system] = {
            "effect_type_coverage": dict(type_counts),
            "weighted_policy_steps": dict(weighted),
            "exact_effect_type_rate": type_counts["exact"] / len(effect_counts),
            "exact_policy_step_rate": weighted["exact"] / total_steps,
            "partial_policy_step_rate": weighted["partial"] / total_steps,
            "absent_policy_step_rate": weighted["absent"] / total_steps,
            "strict_nonexact_policy_steps": weighted["partial"] + weighted["absent"],
            "unmapped_policy_steps": weighted["absent"],
            "projected_outcomes": dict(sorted(projections.items())),
        }
    return summaries


def summarize_properties(mapping: dict[str, Any]) -> dict[str, Any]:
    counters = {system: Counter() for system in mapping["systems"]}
    for record in mapping["properties"]:
        for system in counters:
            counters[system][record[system]] += 1
    return {
        system: {"property_status_counts": dict(counter), "properties": len(mapping["properties"])}
        for system, counter in counters.items()
    }


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-15 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    mapping = json.loads((root / config["effect_mapping"]).read_text(encoding="utf-8"))
    exp12 = json.loads((root / config["exp12_metrics"]).read_text(encoding="utf-8"))
    sint = json.loads((root / config["sint_instance"]).read_text(encoding="utf-8"))
    validate_mapping(mapping)
    if sint["commit"] != config["sint_commit"]:
        raise RuntimeError("SINT instance is not from the pinned baseline commit")
    effect_counts = exp12["total_effect_counts"]
    if set(effect_counts) != {effect.value for effect in Effect}:
        raise RuntimeError("exp-12 input does not contain all five effects")

    effects = summarize_effect_coverage(mapping, effect_counts)
    properties = summarize_properties(mapping)
    comparison = {
        "effect_counts_input": effect_counts,
        "effect_coverage": effects,
        "property_coverage": properties,
        "mapping": mapping,
        "execution_boundary": {
            "ZoneCap": "exp-12 executed",
            "Lanotte_Roop_edit_automata": mapping["sources"]["lanotte_roop"]["runtime_status"],
            "SINT_v0_2_pinned": mapping["sources"]["sint_v0_2"]["runtime_status"],
        },
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "comparison.json", comparison)
    _write_json(output_dir / "source_audit.json", mapping["sources"])

    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "policy_steps": sum(effect_counts.values()),
        "effect_types": len(effect_counts),
        "properties": len(mapping["properties"]),
        "systems": len(mapping["systems"]),
        "lanotte_exact_effect_types": effects["Lanotte_Roop_edit_automata"][
            "effect_type_coverage"
        ]["exact"],
        "lanotte_unmapped_policy_steps": effects["Lanotte_Roop_edit_automata"][
            "unmapped_policy_steps"
        ],
        "sint_exact_effect_types": effects["SINT_v0_2_pinned"][
            "effect_type_coverage"
        ]["exact"],
        "sint_partial_effect_types": effects["SINT_v0_2_pinned"][
            "effect_type_coverage"
        ]["partial"],
        "sint_absent_effect_types": effects["SINT_v0_2_pinned"][
            "effect_type_coverage"
        ]["absent"],
        "sint_strict_nonexact_policy_steps": effects["SINT_v0_2_pinned"][
            "strict_nonexact_policy_steps"
        ],
        "sint_unmapped_policy_steps": effects["SINT_v0_2_pinned"][
            "unmapped_policy_steps"
        ],
        "sint_rewrites_projected_to_constraint_violation_deny": effects[
            "SINT_v0_2_pinned"
        ]["projected_outcomes"]["constraint violation/deny"],
        "zonecap_exact_effect_types": effects["ZoneCap"]["effect_type_coverage"]["exact"],
        "lanotte_runtime_metrics_status": "N/A",
        "sint_commit": sint["commit"],
    }
    observed = {
        key: metrics[key]
        for key in config["expected_counts"]
        if key in metrics
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
        f"policy_steps={metrics['policy_steps']}",
        f"lanotte_exact_effect_types={metrics['lanotte_exact_effect_types']}/5",
        f"lanotte_unmapped_policy_steps={metrics['lanotte_unmapped_policy_steps']}",
        f"sint_exact_partial_absent_effect_types={metrics['sint_exact_effect_types']}/{metrics['sint_partial_effect_types']}/{metrics['sint_absent_effect_types']}",
        f"sint_strict_nonexact_policy_steps={metrics['sint_strict_nonexact_policy_steps']}",
        f"sint_rewrites_projected_to_constraint_violation_deny={metrics['sint_rewrites_projected_to_constraint_violation_deny']}",
        "lanotte_runtime_metrics_status=N/A",
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
    if metrics["expected_count_mismatches"]:
        raise AssertionError(
            f"exp-15 expectation mismatch: {metrics['expected_count_mismatches']}"
        )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
