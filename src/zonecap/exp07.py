from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .compiler import Architecture
from .engine import PolicyEngine
from .exp07_generator import architecture_document, expand_scopes, generate_cases
from .exp07_oracle import allows as oracle_allows
from .exp07_oracle import allows_with_ignored_check
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


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return sorted(names)


def _request(document: dict[str, Any]) -> ActionRequest:
    values = dict(document)
    values["history"] = tuple(values["history"])
    return ActionRequest(**values)


def _relation_for_scope(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, bool]:
    return {
        "zone": (child["source_zone"], child["target_zone"])
        == (parent["source_zone"], parent["target_zone"]),
        "conduit": set(child["conduits"]).issubset(parent["conduits"]),
        "asset": set(child["assets"]).issubset(parent["assets"]),
        "action": set(child["actions"]).issubset(parent["actions"]),
        "parameter": parent["parameter"][0]
        <= child["parameter"][0]
        <= child["parameter"][1]
        <= parent["parameter"][1],
        "time": parent["ticks"][0]
        <= child["ticks"][0]
        <= child["ticks"][1]
        <= parent["ticks"][1],
        "mode": set(child["modes"]).issubset(parent["modes"]),
        "pre_action_sequence": child["required_sequence"][: len(parent["required_sequence"])]
        == parent["required_sequence"],
    }


def _relation_for_capability(parent: Capability, child: Capability) -> dict[str, bool]:
    return {
        "zone": (child.source_zone, child.target_zone)
        == (parent.source_zone, parent.target_zone),
        "conduit": child.conduits.issubset(parent.conduits),
        "asset": child.assets.issubset(parent.assets),
        "action": child.actions.issubset(parent.actions),
        "parameter": child.parameter.is_subset_of(parent.parameter),
        "time": child.ticks.is_subset_of(parent.ticks),
        "mode": child.modes.issubset(parent.modes),
        "pre_action_sequence": child.required_sequence[: len(parent.required_sequence)]
        == parent.required_sequence,
    }


def _relation_kind(parent: dict[str, Any], child: dict[str, Any], dimension: str) -> str:
    keys = {
        "zone": ("source_zone", "target_zone"),
        "conduit": ("conduits",),
        "asset": ("assets",),
        "action": ("actions",),
        "parameter": ("parameter",),
        "time": ("ticks",),
        "mode": ("modes",),
        "pre_action_sequence": ("required_sequence",),
    }[dimension]
    return "preserved" if all(parent[key] == child[key] for key in keys) else "narrowed"


def _compile_scopes(
    table: dict[str, Any],
    roots: list[dict[str, Any]],
    delegations: list[dict[str, Any]],
    compiled_input_dir: Path,
) -> tuple[dict[str, Capability], list[dict[str, Any]]]:
    compiled_input_dir.mkdir(parents=True, exist_ok=False)
    capability_by_scope: dict[str, Capability] = {}
    for architecture in table["architectures"]:
        selected = [scope for scope in roots if scope["architecture"] == architecture["id"]]
        document = architecture_document(architecture, roots)
        document_path = compiled_input_dir / f"{architecture['id']}.json"
        _write_json(document_path, document)
        capabilities = Architecture.load(document_path).compile_all()
        if len(capabilities) != len(selected):
            raise AssertionError("compiler did not return one root capability per frozen grant")
        capability_by_scope.update(
            {scope["scope_id"]: capability for scope, capability in zip(selected, capabilities)}
        )

    scope_by_id = {scope["scope_id"]: scope for scope in [*roots, *delegations]}
    relation_records: list[dict[str, Any]] = []
    for child_scope in delegations:
        parent_scope = scope_by_id[child_scope["parent_scope_id"]]
        parent_capability = capability_by_scope[parent_scope["scope_id"]]
        child_capability = parent_capability.attenuate(
            capability_id=child_scope["scope_id"],
            subject=child_scope["subject"],
            conduits=child_scope["conduits"],
            assets=child_scope["assets"],
            actions=child_scope["actions"],
            parameter=Interval.from_pair(child_scope["parameter"]),
            ticks=Interval.from_pair(child_scope["ticks"]),
            modes=child_scope["modes"],
            required_sequence=child_scope["required_sequence"],
        )
        capability_by_scope[child_scope["scope_id"]] = child_capability
        table_checks = _relation_for_scope(parent_scope, child_scope)
        compiler_checks = _relation_for_capability(parent_capability, child_capability)
        dimensions = {}
        for dimension in table_checks:
            dimensions[dimension] = {
                "relation": _relation_kind(parent_scope, child_scope, dimension),
                "table_check": table_checks[dimension],
                "compiled_check": compiler_checks[dimension],
                "passed": table_checks[dimension] and compiler_checks[dimension],
            }
        relation_records.append(
            {
                "architecture": child_scope["architecture"],
                "parent_scope_id": parent_scope["scope_id"],
                "child_scope_id": child_scope["scope_id"],
                "child_depth": child_scope["depth"],
                "dimensions": dimensions,
                "passed": all(item["passed"] for item in dimensions.values()),
            }
        )
    return capability_by_scope, relation_records


def _opcua_role_projection(scope: dict[str, Any], request: dict[str, Any]) -> bool:
    return (
        request["subject"] == scope["subject"]
        and request["asset"] in scope["assets"]
        and request["action"] in scope["actions"]
    )


def _plc_abac_projection(scope: dict[str, Any], request: dict[str, Any]) -> bool:
    return (
        request["subject"] == scope["subject"]
        and request["source_zone"] == scope["source_zone"]
        and request["target_zone"] == scope["target_zone"]
        and request["asset"] in scope["assets"]
        and request["action"] in scope["actions"]
        and scope["ticks"][0] <= request["tick"] <= scope["ticks"][1]
        and request["mode"] in scope["modes"]
    )


def _update_baseline(counter: Counter[str], observed: bool, oracle: bool) -> None:
    counter["cases"] += 1
    counter["agreement"] += observed == oracle
    counter["false_allow"] += observed and not oracle
    counter["false_deny"] += not observed and oracle


def _validate_source_manifest(root: Path, manifest: dict[str, Any], base: Path) -> None:
    for source in manifest["sources"]:
        path = base / source["file"]
        if _sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen source hash mismatch: {path}")


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-07 requires a clean, committed pre-run freeze")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    table_path = (root / config["policy_table"]).resolve()
    source_manifest_path = (root / config["source_manifest"]).resolve()
    protocol_path = (root / config["encoding_protocol"]).resolve()
    if _sha256(table_path) != config["frozen_hashes"]["policy_table_sha256"]:
        raise RuntimeError("policy table differs from the preregistered hash")
    if _sha256(source_manifest_path) != config["frozen_hashes"]["source_manifest_sha256"]:
        raise RuntimeError("source manifest differs from the preregistered hash")
    if _sha256(protocol_path) != config["frozen_hashes"]["encoding_protocol_sha256"]:
        raise RuntimeError("encoding protocol differs from the preregistered hash")
    for relative_path, expected_hash in config["frozen_hashes"]["code"].items():
        code_path = root / relative_path
        if _sha256(code_path) != expected_hash:
            raise RuntimeError(f"frozen code hash mismatch: {relative_path}")
    table = json.loads(table_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    _validate_source_manifest(root, source_manifest, source_manifest_path.parent)

    roots, delegations = expand_scopes(table)
    scopes = [*roots, *delegations]
    scope_by_id = {scope["scope_id"]: scope for scope in scopes}
    if len(scope_by_id) != len(scopes):
        raise AssertionError("duplicate generated scope id")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "delegation_specs.json", delegations)
    capability_by_scope, relation_records = _compile_scopes(
        table, roots, delegations, output_dir / "compiled_inputs"
    )
    _write_json(output_dir / "delegation_checks.json", relation_records)

    engine = PolicyEngine()
    counters: Counter[str] = Counter()
    architecture_counters: dict[str, Counter[str]] = defaultdict(Counter)
    depth_counters: dict[int, Counter[str]] = defaultdict(Counter)
    mutation_counters: dict[str, Counter[str]] = defaultdict(Counter)
    baseline_counters = {
        "opcua_role_projection": Counter(),
        "plc_abac_projection": Counter(),
    }
    ignored_checks = [
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
    ]
    killed_by_corpus: Counter[str] = Counter()
    cases_path = output_dir / "cases.jsonl.gz"
    with gzip.open(cases_path, "wt", encoding="utf-8") as handle:
        for scope in scopes:
            capability = capability_by_scope[scope["scope_id"]]
            for case in generate_cases(scope):
                request_document = case["request"]
                oracle_decision = oracle_allows(scope, request_document)
                compiler_result = engine.evaluate(
                    capability,
                    _request(request_document),
                    rewrite_out_of_range=False,
                )
                compiler_decision = compiler_result.effect is Effect.ALLOW
                opcua_decision = _opcua_role_projection(scope, request_document)
                abac_decision = _plc_abac_projection(scope, request_document)
                expectation_match = oracle_decision == case["expected_allow"]
                compiler_oracle_match = compiler_decision == oracle_decision

                counters["cases"] += 1
                counters["valid_cases"] += case["kind"] == "valid"
                counters["mutation_cases"] += case["kind"] == "mutation"
                counters["oracle_allows"] += oracle_decision
                counters["compiler_allows"] += compiler_decision
                counters["oracle_expectation_mismatches"] += not expectation_match
                counters["compiler_oracle_mismatches"] += not compiler_oracle_match
                arch_counter = architecture_counters[case["architecture"]]
                arch_counter["cases"] += 1
                arch_counter["mismatches"] += not compiler_oracle_match
                arch_counter["oracle_expectation_mismatches"] += not expectation_match
                depth_counter = depth_counters[case["depth"]]
                depth_counter["cases"] += 1
                depth_counter["mismatches"] += not compiler_oracle_match
                if case["mutation"] is not None:
                    mutation_counter = mutation_counters[case["mutation"]]
                    mutation_counter["cases"] += 1
                    mutation_counter["oracle_allows"] += oracle_decision
                    mutation_counter["compiler_allows"] += compiler_decision

                _update_baseline(
                    baseline_counters["opcua_role_projection"], opcua_decision, oracle_decision
                )
                _update_baseline(
                    baseline_counters["plc_abac_projection"], abac_decision, oracle_decision
                )
                if not oracle_decision:
                    for ignored in ignored_checks:
                        killed_by_corpus[ignored] += allows_with_ignored_check(
                            scope, request_document, ignored
                        )

                record = {
                    **case,
                    "oracle_allow": oracle_decision,
                    "compiler_allow": compiler_decision,
                    "compiler_effect": compiler_result.effect.value,
                    "compiler_reason": compiler_result.reason,
                    "compiler_oracle_match": compiler_oracle_match,
                    "oracle_expectation_match": expectation_match,
                    "baselines": {
                        "opcua_role_projection": opcua_decision,
                        "plc_abac_projection": abac_decision,
                    },
                }
                handle.write(json.dumps(record, sort_keys=True) + "\n")

    expected = config["expected_counts"]
    observed_counts = {
        "root_grants": len(roots),
        "delegated_scopes": len(delegations),
        "valid_cases": counters["valid_cases"],
        "mutation_cases": counters["mutation_cases"],
        "total_cases": counters["cases"],
    }
    count_mismatches = {
        key: {"expected": expected[key], "observed": value}
        for key, value in observed_counts.items()
        if expected[key] != value
    }
    dimension_checks = sum(
        len(record["dimensions"]) for record in relation_records
    )
    dimension_failures = sum(
        not item["passed"]
        for record in relation_records
        for item in record["dimensions"].values()
    )
    unsupported_decision_constructs = sum(
        len(architecture["unsupported_decision_constructs"])
        for architecture in table["architectures"]
    )
    excluded_metadata = sum(
        len(architecture["excluded_metadata"])
        for architecture in table["architectures"]
    )

    oracle_path = root / "src/zonecap/exp07_oracle.py"
    generator_path = root / "src/zonecap/exp07_generator.py"
    oracle_imports = _imports(oracle_path)
    generator_imports = _imports(generator_path)
    dependency_audit = {
        "oracle_imports": oracle_imports,
        "generator_imports": generator_imports,
        "oracle_has_implementation_import": any(name.startswith("zonecap") for name in oracle_imports),
        "generator_has_compiler_or_engine_import": any(
            name in {"zonecap.compiler", "zonecap.engine", ".compiler", ".engine"}
            for name in generator_imports
        ),
    }
    check_removal_mutants = {
        name: {
            "cases_that_accept_only_after_check_removal": killed_by_corpus[name],
            "killed": killed_by_corpus[name] > 0,
        }
        for name in ignored_checks
    }
    every_mutation_category_exercised = all(
        counter["cases"] > 0 for counter in mutation_counters.values()
    ) and len(mutation_counters) == len(config["registered_mutations"])
    perfect_agreement_triggered = counters["compiler_oracle_mismatches"] == 0
    too_good_audit = {
        "perfect_agreement_triggered": perfect_agreement_triggered,
        "pre_run_git_tree_clean": not bool(dirty_before_run),
        "frozen_policy_hash_matched": True,
        "frozen_source_hashes_matched": True,
        "oracle_generator_dependency_audit": dependency_audit,
        "all_valid_cases_allowed_by_oracle": counters["oracle_allows"] == counters["valid_cases"],
        "all_mutations_denied_by_oracle": all(
            counter["oracle_allows"] == 0 for counter in mutation_counters.values()
        ),
        "all_mutations_denied_by_compiler": all(
            counter["compiler_allows"] == 0 for counter in mutation_counters.values()
        ),
        "every_mutation_category_exercised": every_mutation_category_exercised,
        "check_removal_mutants": check_removal_mutants,
    }
    too_good_audit["passed"] = all(
        (
            too_good_audit["pre_run_git_tree_clean"],
            too_good_audit["frozen_policy_hash_matched"],
            too_good_audit["frozen_source_hashes_matched"],
            not dependency_audit["oracle_has_implementation_import"],
            not dependency_audit["generator_has_compiler_or_engine_import"],
            too_good_audit["all_valid_cases_allowed_by_oracle"],
            too_good_audit["all_mutations_denied_by_oracle"],
            too_good_audit["all_mutations_denied_by_compiler"],
            too_good_audit["every_mutation_category_exercised"],
            all(item["killed"] for item in check_removal_mutants.values()),
        )
    )
    _write_json(output_dir / "mutation_audit.json", too_good_audit)

    baseline_metrics = {
        name: {
            **dict(counter),
            "agreement_rate": counter["agreement"] / counter["cases"],
            "scope": (
                "functional projection over subject/asset/action; no external OPC UA implementation"
                if name == "opcua_role_projection"
                else "functional PLC-ABAC projection over identity, zones, asset, action, time, and mode"
            ),
        }
        for name, counter in baseline_counters.items()
    }
    _write_json(output_dir / "baseline_metrics.json", baseline_metrics)

    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "architectures": {
            name: dict(counter) for name, counter in architecture_counters.items()
        },
        "depths": {str(depth): dict(counter) for depth, counter in depth_counters.items()},
        "root_grants": len(roots),
        "delegated_scopes": len(delegations),
        "delegation_edges": len(relation_records),
        "delegation_dimension_checks": dimension_checks,
        "delegation_dimension_failures": dimension_failures,
        "valid_cases": counters["valid_cases"],
        "mutation_cases": counters["mutation_cases"],
        "total_cases": counters["cases"],
        "oracle_expectation_mismatches": counters["oracle_expectation_mismatches"],
        "compiler_oracle_mismatches": counters["compiler_oracle_mismatches"],
        "compiler_oracle_agreement_rate": 1
        - counters["compiler_oracle_mismatches"] / counters["cases"],
        "mutation_categories": {
            name: dict(counter) for name, counter in mutation_counters.items()
        },
        "unsupported_decision_constructs": unsupported_decision_constructs,
        "excluded_nondecision_metadata_items": excluded_metadata,
        "expected_count_mismatches": count_mismatches,
        "too_good_audit_passed": too_good_audit["passed"],
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"root_grants={metrics['root_grants']}",
        f"delegated_scopes={metrics['delegated_scopes']}",
        f"total_cases={metrics['total_cases']}",
        f"valid_cases={metrics['valid_cases']}",
        f"mutation_cases={metrics['mutation_cases']}",
        f"compiler_oracle_mismatches={metrics['compiler_oracle_mismatches']}",
        f"delegation_dimension_failures={metrics['delegation_dimension_failures']}",
        f"unsupported_decision_constructs={metrics['unsupported_decision_constructs']}",
        f"too_good_audit_passed={str(metrics['too_good_audit_passed']).lower()}",
    ]
    (output_dir / "log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    input_paths = [
        config_path,
        table_path,
        source_manifest_path,
        protocol_path,
        root / "src/zonecap/models.py",
        root / "src/zonecap/compiler.py",
        root / "src/zonecap/engine.py",
        root / "src/zonecap/exp07_generator.py",
        root / "src/zonecap/exp07_oracle.py",
        root / "src/zonecap/exp07.py",
        root / "tests/test_exp07.py",
    ]
    for source in source_manifest["sources"]:
        input_paths.append(source_manifest_path.parent / source["file"])
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
        "count_mismatches": count_mismatches,
        "oracle_expectation_mismatches": counters["oracle_expectation_mismatches"],
        "compiler_oracle_mismatches": counters["compiler_oracle_mismatches"],
        "delegation_dimension_failures": dimension_failures,
        "unsupported_decision_constructs": unsupported_decision_constructs,
        "too_good_audit_passed": too_good_audit["passed"],
    }
    if (
        count_mismatches
        or counters["oracle_expectation_mismatches"]
        or counters["compiler_oracle_mismatches"]
        or dimension_failures
        or unsupported_decision_constructs
        or not too_good_audit["passed"]
    ):
        raise AssertionError(f"exp-07 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
