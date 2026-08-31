from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .engine import PolicyEngine
from .exp07 import _compile_scopes, _relation_for_capability
from .exp07_generator import expand_scopes
from .exp07_oracle import allows as oracle_allows
from .models import ActionRequest, Capability, Effect, Interval


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


def _request_for_scope(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject": scope["subject"],
        "source_zone": scope["source_zone"],
        "target_zone": scope["target_zone"],
        "conduit": scope["conduits"][0],
        "asset": scope["assets"][0],
        "action": scope["actions"][0],
        "value": (scope["parameter"][0] + scope["parameter"][1]) / 2,
        "tick": (scope["ticks"][0] + scope["ticks"][1]) / 2,
        "mode": scope["modes"][0],
        "history": list(scope["required_sequence"]),
    }


def _action_request(document: dict[str, Any]) -> ActionRequest:
    values = dict(document)
    values["history"] = tuple(values["history"])
    return ActionRequest(**values)


def _widened_candidate(parent: Capability, dimension: str, child_depth: int) -> Capability:
    updates: dict[str, Any] = {
        "capability_id": f"{parent.capability_id}:attempted-{dimension}-d{child_depth}",
        "parent_id": parent.capability_id,
        "delegation_depth": child_depth,
    }
    if dimension == "zone":
        updates["target_zone"] = f"{parent.target_zone}:unauthorized"
    elif dimension == "conduit":
        updates["conduits"] = parent.conduits | {"unauthorized_conduit"}
    elif dimension == "asset":
        updates["assets"] = parent.assets | {"unauthorized_asset"}
    elif dimension == "action":
        updates["actions"] = parent.actions | {"unauthorized_action"}
    elif dimension == "parameter":
        updates["parameter"] = Interval(parent.parameter.low - 1, parent.parameter.high + 1)
    elif dimension == "time":
        updates["ticks"] = Interval(parent.ticks.low - 1, parent.ticks.high + 1)
    elif dimension == "mode":
        updates["modes"] = parent.modes | {"unauthorized_mode"}
    elif dimension == "pre_action_sequence":
        updates["required_sequence"] = parent.required_sequence[:-1]
    else:
        raise KeyError(f"unknown widening dimension: {dimension}")
    return replace(parent, **updates)


def _run_path_cases(
    path_specs: dict[str, Any],
    scope_by_id: dict[str, dict[str, Any]],
    capability_by_scope: dict[str, Capability],
    root_scopes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    engine = PolicyEngine()
    root_pairs = {
        (scope["architecture"], scope["source_zone"], scope["target_zone"])
        for scope in root_scopes
    }
    records: list[dict[str, Any]] = []
    for path in path_specs["paths"]:
        direct_pair_absent = (
            path["architecture"],
            path["source_zone"],
            path["target_zone"],
        ) not in root_pairs
        if path["direct_pair_must_be_absent"] and not direct_pair_absent:
            raise AssertionError(f"path unexpectedly has a direct grant: {path['id']}")
        for depth in (0, 1, 2):
            scope_ids = [
                f"{path['architecture']}:{grant_id}:d{depth}"
                for grant_id in path["hop_grant_ids"]
            ]
            scopes = [scope_by_id[scope_id] for scope_id in scope_ids]
            if scopes[0]["source_zone"] != path["source_zone"]:
                raise AssertionError("first hop does not start at the registered source")
            if scopes[-1]["target_zone"] != path["target_zone"]:
                raise AssertionError("last hop does not end at the registered target")
            for left, right in zip(scopes, scopes[1:]):
                if left["target_zone"] != right["source_zone"]:
                    raise AssertionError("registered hop chain is discontinuous")
            base_requests = [_request_for_scope(scope) for scope in scopes]
            cases: list[tuple[str, int | None, list[dict[str, Any]], bool]] = [
                ("all_hops_valid", None, base_requests, True)
            ]
            for failed_hop in range(len(scopes)):
                requests = [dict(request) for request in base_requests]
                requests[failed_hop]["conduit"] = "unauthorized_path_conduit"
                cases.append(("one_hop_conduit_invalid", failed_hop, requests, False))
            for kind, failed_hop, requests, expected_allow in cases:
                oracle_hops = [
                    oracle_allows(scope, request)
                    for scope, request in zip(scopes, requests)
                ]
                compiler_results = [
                    engine.evaluate(
                        capability_by_scope[scope_id],
                        _action_request(request),
                        rewrite_out_of_range=False,
                    )
                    for scope_id, request in zip(scope_ids, requests)
                ]
                compiler_hops = [result.effect is Effect.ALLOW for result in compiler_results]
                oracle_path_allow = all(oracle_hops)
                compiler_path_allow = all(compiler_hops)
                records.append(
                    {
                        "case_id": f"{path['id']}:d{depth}:{kind}:{failed_hop}",
                        "path_id": path["id"],
                        "architecture": path["architecture"],
                        "depth": depth,
                        "direct_pair_absent": direct_pair_absent,
                        "kind": kind,
                        "failed_hop": failed_hop,
                        "scope_ids": scope_ids,
                        "requests": requests,
                        "expected_allow": expected_allow,
                        "oracle_hops": oracle_hops,
                        "compiler_hops": compiler_hops,
                        "compiler_effects": [result.effect.value for result in compiler_results],
                        "compiler_reasons": [result.reason for result in compiler_results],
                        "oracle_path_allow": oracle_path_allow,
                        "compiler_path_allow": compiler_path_allow,
                        "compiler_oracle_match": compiler_path_allow == oracle_path_allow,
                        "expectation_match": oracle_path_allow == expected_allow,
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
        raise RuntimeError("exp-09 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")
    table = json.loads((root / config["policy_table"]).read_text(encoding="utf-8"))
    path_specs = json.loads((root / config["path_specs"]).read_text(encoding="utf-8"))
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

    path_records = _run_path_cases(
        path_specs, scope_by_id, capability_by_scope, roots
    )
    _write_json(output_dir / "path_cases.json", path_records)

    dimensions = path_specs["widening_dimensions"]
    widening_records: list[dict[str, Any]] = []
    for architecture in table["architectures"]:
        root_scope_id = f"{architecture['id']}:g000:d0"
        legal_depth1_id = f"{architecture['id']}:g000:d1"
        transitions = [
            (capability_by_scope[root_scope_id], 1),
            (capability_by_scope[legal_depth1_id], 2),
        ]
        for parent, child_depth in transitions:
            for dimension in dimensions:
                candidate = _widened_candidate(parent, dimension, child_depth)
                relation = _relation_for_capability(parent, candidate)
                accepted = True
                error = None
                try:
                    candidate.assert_attenuates(parent)
                except ValueError as caught:
                    accepted = False
                    error = str(caught)
                failed_dimensions = [name for name, passed in relation.items() if not passed]
                widening_records.append(
                    {
                        "architecture": architecture["id"],
                        "parent_capability_id": parent.capability_id,
                        "attempted_child_depth": child_depth,
                        "dimension": dimension,
                        "accepted": accepted,
                        "error": error,
                        "failed_dimensions": failed_dimensions,
                        "target_dimension_failed": dimension in failed_dimensions,
                    }
                )
    _write_json(output_dir / "widening_attempts.json", widening_records)
    _write_json(output_dir / "legal_delegation_checks.json", relation_records)

    path_mismatches = sum(not record["compiler_oracle_match"] for record in path_records)
    path_expectation_mismatches = sum(not record["expectation_match"] for record in path_records)
    accepted_widenings = sum(record["accepted"] for record in widening_records)
    mislocalized_widenings = sum(
        not record["target_dimension_failed"] for record in widening_records
    )
    legal_relation_failures = sum(not record["passed"] for record in relation_records)
    legal_dimension_failures = sum(
        not item["passed"]
        for record in relation_records
        for item in record["dimensions"].values()
    )
    depth0_path_cases = sum(record["depth"] == 0 for record in path_records)
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "multi_conduit_paths": len(path_specs["paths"]),
        "multi_conduit_path_cases": len(path_records),
        "multi_conduit_path_happy_cases": sum(
            record["kind"] == "all_hops_valid" for record in path_records
        ),
        "multi_conduit_path_negative_cases": sum(
            record["kind"] != "all_hops_valid" for record in path_records
        ),
        "path_compiler_oracle_mismatches": path_mismatches,
        "path_expectation_mismatches": path_expectation_mismatches,
        "depth0_baseline_path_cases": depth0_path_cases,
        "depth0_baseline_delegation_dimension_checks": 0,
        "legal_delegation_edges": len(relation_records),
        "legal_delegation_dimension_checks": sum(
            len(record["dimensions"]) for record in relation_records
        ),
        "legal_delegation_relation_failures": legal_relation_failures,
        "legal_delegation_dimension_failures": legal_dimension_failures,
        "widening_attempts": len(widening_records),
        "accepted_widenings": accepted_widenings,
        "widening_dimensions": len(dimensions),
        "widening_attempts_with_wrong_failed_dimension": mislocalized_widenings,
    }
    metrics["expected_count_mismatches"] = {
        name: {"expected": expected, "observed": metrics.get(name)}
        for name, expected in config["expected_counts"].items()
        if metrics.get(name) != expected
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"multi_conduit_paths={metrics['multi_conduit_paths']}",
        f"multi_conduit_path_cases={metrics['multi_conduit_path_cases']}",
        f"path_compiler_oracle_mismatches={path_mismatches}",
        f"widening_attempts={metrics['widening_attempts']}",
        f"accepted_widenings={accepted_widenings}",
        f"legal_delegation_dimension_failures={legal_dimension_failures}",
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
        "path_compiler_oracle_mismatches": path_mismatches,
        "path_expectation_mismatches": path_expectation_mismatches,
        "accepted_widenings": accepted_widenings,
        "widening_attempts_with_wrong_failed_dimension": mislocalized_widenings,
        "legal_delegation_relation_failures": legal_relation_failures,
        "legal_delegation_dimension_failures": legal_dimension_failures,
    }
    if any(failures.values()):
        raise AssertionError(f"exp-09 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
