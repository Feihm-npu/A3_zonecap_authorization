from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .engine import PolicyEngine
from .exp07 import _compile_scopes
from .exp07_generator import expand_scopes, generate_cases
from .exp07_oracle import allows as oracle_allows
from .exp07_oracle import allows_with_ignored_check
from .models import ActionRequest, Effect


IGNORED_CHECKS = (
    "subject",
    "source_zone",
    "target_zone",
    "conduit",
    "asset",
    "action",
    "parameter",
    "time",
    "mode",
    "sequence",
)


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


def _request(document: dict[str, Any]) -> ActionRequest:
    values = dict(document)
    values["history"] = tuple(values["history"])
    return ActionRequest(**values)


def _case_count(scopes: list[dict[str, Any]]) -> int:
    return sum(1 for scope in scopes for _ in generate_cases(scope))


def provenance_probes(table: dict[str, Any]) -> list[dict[str, Any]]:
    base_roots, base_delegations = expand_scopes(table)
    base_case_count = _case_count([*base_roots, *base_delegations])
    records: list[dict[str, Any]] = []
    for architecture_index, architecture in enumerate(table["architectures"]):
        removed = deepcopy(table)
        removed_grant = removed["architectures"][architecture_index]["grants"].pop()
        removed_roots, removed_delegations = expand_scopes(removed)
        removed_case_count = _case_count([*removed_roots, *removed_delegations])
        remove_observed = {
            "root_delta": len(base_roots) - len(removed_roots),
            "delegated_delta": len(base_delegations) - len(removed_delegations),
            "case_delta": base_case_count - removed_case_count,
            "removed_conduit_absent": all(
                removed_grant["conduit"] not in scope["conduits"]
                for scope in [*removed_roots, *removed_delegations]
                if scope["architecture"] == architecture["id"]
            ),
        }
        records.append(
            {
                "architecture": architecture["id"],
                "probe": "remove_last_source_grant",
                "observed": remove_observed,
                "expected": {
                    "root_delta": 1,
                    "delegated_delta": 2,
                    "case_delta": 1404,
                    "removed_conduit_absent": True,
                },
                "passed": remove_observed
                == {
                    "root_delta": 1,
                    "delegated_delta": 2,
                    "case_delta": 1404,
                    "removed_conduit_absent": True,
                },
            }
        )

        added = deepcopy(table)
        selected = added["architectures"][architecture_index]
        sentinel_zone = f"sentinel_zone_{architecture['id']}"
        sentinel_asset = f"sentinel_asset_{architecture['id']}"
        sentinel_conduit = f"sentinel_conduit_{architecture['id']}"
        selected["zones"].append({"id": sentinel_zone, "asset": sentinel_asset})
        selected["grants"].append(
            {
                "source_zone": sentinel_zone,
                "target_zone": sentinel_zone,
                "conduit": sentinel_conduit,
            }
        )
        added_roots, added_delegations = expand_scopes(added)
        added_case_count = _case_count([*added_roots, *added_delegations])
        sentinel_scopes = [
            scope
            for scope in [*added_roots, *added_delegations]
            if sentinel_conduit in scope["conduits"]
        ]
        add_observed = {
            "root_delta": len(added_roots) - len(base_roots),
            "delegated_delta": len(added_delegations) - len(base_delegations),
            "case_delta": added_case_count - base_case_count,
            "sentinel_depths": sorted(scope["depth"] for scope in sentinel_scopes),
            "sentinel_asset_propagated": all(
                sentinel_asset in scope["assets"] for scope in sentinel_scopes
            ),
        }
        records.append(
            {
                "architecture": architecture["id"],
                "probe": "add_sentinel_source_grant",
                "observed": add_observed,
                "expected": {
                    "root_delta": 1,
                    "delegated_delta": 2,
                    "case_delta": 1404,
                    "sentinel_depths": [0, 1, 2],
                    "sentinel_asset_propagated": True,
                },
                "passed": add_observed
                == {
                    "root_delta": 1,
                    "delegated_delta": 2,
                    "case_delta": 1404,
                    "sentinel_depths": [0, 1, 2],
                    "sentinel_asset_propagated": True,
                },
            }
        )
    return records


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-08 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    table_path = root / config["policy_table"]
    fixture_path = root / config["handwritten_fixtures"]
    for relative_path, expected_hash in config["frozen_hashes"].items():
        path = root / relative_path
        if _sha256(path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    table = json.loads(table_path.read_text(encoding="utf-8"))
    fixture_document = json.loads(fixture_path.read_text(encoding="utf-8"))
    roots, delegations = expand_scopes(table)
    scopes = [*roots, *delegations]
    scope_by_id = {scope["scope_id"]: scope for scope in scopes}

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    capability_by_scope, relation_records = _compile_scopes(
        table, roots, delegations, output_dir / "compiled_inputs"
    )
    engine = PolicyEngine()

    full_counters: Counter[str] = Counter()
    mutation_categories: dict[str, Counter[str]] = defaultdict(Counter)
    generated_mutant_detections: Counter[str] = Counter()
    for scope in scopes:
        capability = capability_by_scope[scope["scope_id"]]
        for case in generate_cases(scope):
            oracle_decision = oracle_allows(scope, case["request"])
            compiler_decision = (
                engine.evaluate(
                    capability,
                    _request(case["request"]),
                    rewrite_out_of_range=False,
                ).effect
                is Effect.ALLOW
            )
            full_counters["cases"] += 1
            full_counters["valid_cases"] += case["kind"] == "valid"
            full_counters["mutation_cases"] += case["kind"] == "mutation"
            full_counters["oracle_expectation_mismatches"] += (
                oracle_decision != case["expected_allow"]
            )
            full_counters["compiler_oracle_mismatches"] += (
                compiler_decision != oracle_decision
            )
            if case["mutation"]:
                mutation_categories[case["mutation"]]["cases"] += 1
                mutation_categories[case["mutation"]]["oracle_allows"] += oracle_decision
                mutation_categories[case["mutation"]]["compiler_allows"] += compiler_decision
            for ignored in IGNORED_CHECKS:
                generated_mutant_detections[ignored] += (
                    allows_with_ignored_check(scope, case["request"], ignored)
                    != case["expected_allow"]
                )

    fixture_decisions: list[dict[str, Any]] = []
    fixture_mutant_detections: Counter[str] = Counter()
    fixture_mismatches = 0
    fixture_expectation_mismatches = 0
    for case in fixture_document["cases"]:
        scope = scope_by_id[case["scope_id"]]
        capability = capability_by_scope[case["scope_id"]]
        oracle_decision = oracle_allows(scope, case["request"])
        compiler_result = engine.evaluate(
            capability,
            _request(case["request"]),
            rewrite_out_of_range=False,
        )
        compiler_decision = compiler_result.effect is Effect.ALLOW
        fixture_mismatches += compiler_decision != oracle_decision
        fixture_expectation_mismatches += oracle_decision != case["expected_allow"]
        for ignored in IGNORED_CHECKS:
            fixture_mutant_detections[ignored] += (
                allows_with_ignored_check(scope, case["request"], ignored)
                != case["expected_allow"]
            )
        fixture_decisions.append(
            {
                **case,
                "oracle_allow": oracle_decision,
                "compiler_allow": compiler_decision,
                "compiler_effect": compiler_result.effect.value,
                "compiler_reason": compiler_result.reason,
                "compiler_oracle_match": compiler_decision == oracle_decision,
                "oracle_expectation_match": oracle_decision == case["expected_allow"],
            }
        )
    _write_json(output_dir / "fixture_decisions.json", fixture_decisions)

    probes = provenance_probes(table)
    _write_json(output_dir / "provenance_ablation.json", probes)
    coverage = {
        "generated_cross_product": {
            name: {
                "detecting_cases": generated_mutant_detections[name],
                "killed": generated_mutant_detections[name] > 0,
            }
            for name in IGNORED_CHECKS
        },
        "handwritten_happy_paths": {
            name: {
                "detecting_cases": fixture_mutant_detections[name],
                "killed": fixture_mutant_detections[name] > 0,
            }
            for name in IGNORED_CHECKS
        },
    }
    _write_json(output_dir / "mutation_coverage.json", coverage)
    generated_kills = sum(
        item["killed"] for item in coverage["generated_cross_product"].values()
    )
    fixture_kills = sum(
        item["killed"] for item in coverage["handwritten_happy_paths"].values()
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "source_table_root_grants": len(roots),
        "source_table_delegated_scopes": len(delegations),
        "generated_cases": full_counters["cases"],
        "generated_valid_cases": full_counters["valid_cases"],
        "generated_mutation_cases": full_counters["mutation_cases"],
        "generated_oracle_expectation_mismatches": full_counters[
            "oracle_expectation_mismatches"
        ],
        "generated_compiler_oracle_mismatches": full_counters[
            "compiler_oracle_mismatches"
        ],
        "generated_mutation_categories": len(mutation_categories),
        "generated_check_removal_mutants_killed": generated_kills,
        "registered_check_removal_mutants": len(IGNORED_CHECKS),
        "handwritten_fixture_cases": len(fixture_document["cases"]),
        "handwritten_fixture_oracle_expectation_mismatches": fixture_expectation_mismatches,
        "handwritten_fixture_compiler_oracle_mismatches": fixture_mismatches,
        "handwritten_fixture_check_removal_mutants_killed": fixture_kills,
        "provenance_probes": len(probes),
        "provenance_probe_failures": sum(not record["passed"] for record in probes),
        "delegation_relation_failures": sum(not record["passed"] for record in relation_records),
    }
    metrics["expected_count_mismatches"] = {
        name: {"expected": expected_value, "observed": metrics.get(name)}
        for name, expected_value in config["expected_counts"].items()
        if metrics.get(name) != expected_value
    }
    _write_json(
        output_dir / "generated_summary.json",
        {
            "counters": dict(full_counters),
            "mutation_categories": {
                name: dict(counter) for name, counter in mutation_categories.items()
            },
        },
    )
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"generated_cases={metrics['generated_cases']}",
        f"generated_compiler_oracle_mismatches={metrics['generated_compiler_oracle_mismatches']}",
        f"generated_check_removal_mutants_killed={generated_kills}/{len(IGNORED_CHECKS)}",
        f"handwritten_fixture_cases={metrics['handwritten_fixture_cases']}",
        f"handwritten_fixture_compiler_oracle_mismatches={fixture_mismatches}",
        f"handwritten_fixture_check_removal_mutants_killed={fixture_kills}/{len(IGNORED_CHECKS)}",
        f"provenance_probe_failures={metrics['provenance_probe_failures']}",
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
        "inputs": {
            str(path.relative_to(root)): _sha256(path) for path in input_paths
        },
        "outputs": {
            str(path.relative_to(output_dir)): _sha256(path) for path in output_paths
        },
    }
    _write_json(output_dir / "manifest.json", manifest)

    failures = {
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
        "generated_oracle_expectation_mismatches": metrics[
            "generated_oracle_expectation_mismatches"
        ],
        "generated_compiler_oracle_mismatches": metrics[
            "generated_compiler_oracle_mismatches"
        ],
        "generated_mutants_not_killed": len(IGNORED_CHECKS) - generated_kills,
        "handwritten_fixture_expectation_mismatches": fixture_expectation_mismatches,
        "handwritten_fixture_compiler_oracle_mismatches": fixture_mismatches,
        "unexpected_handwritten_fixture_mutant_kills": fixture_kills,
        "provenance_probe_failures": metrics["provenance_probe_failures"],
        "delegation_relation_failures": metrics["delegation_relation_failures"],
    }
    if any(failures.values()):
        raise AssertionError(f"exp-08 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
