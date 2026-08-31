from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .exp07_generator import expand_scopes


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


def sint_profile_allows(scope: dict[str, Any], request: dict[str, Any]) -> bool:
    """Projection of the pinned SINT resource/action/max/expiry profile.

    The non-negative lower domain is invariant. Arbitrary raised lower bounds in
    delegated ZoneCap intervals are intentionally not enforced by this profile.
    """

    return (
        request["subject"] == scope["subject"]
        and request["asset"] in scope["assets"]
        and request["action"] in scope["actions"]
        and 0 <= request["value"] <= scope["parameter"][1]
        and request["tick"] <= scope["ticks"][1]
    )


def _update(counter: Counter[str], decision: bool, oracle: bool, in_fair_subset: bool) -> None:
    counter["cases"] += 1
    counter["agreement"] += decision == oracle
    counter["false_allow"] += decision and not oracle
    counter["false_deny"] += not decision and oracle
    counter["fair_subset_cases"] += in_fair_subset
    counter["fair_subset_mismatches"] += in_fair_subset and decision != oracle


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-10 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")
    table = json.loads((root / config["policy_table"]).read_text(encoding="utf-8"))
    sint_instance = json.loads((root / config["sint_instance"]).read_text(encoding="utf-8"))
    if sint_instance["commit"] != config["sint_commit"]:
        raise RuntimeError("pinned SINT instance commit mismatch")
    roots, delegations = expand_scopes(table)
    scope_by_id = {scope["scope_id"]: scope for scope in [*roots, *delegations]}

    supported_mutations = {
        "opcua_role_projection": {"subject", "asset", "action"},
        "plc_abac_projection": {
            "subject",
            "source_zone",
            "target_zone",
            "asset",
            "action",
            "tick_low",
            "tick_high",
            "mode",
        },
        "sint_pinned_profile": {
            "subject",
            "asset",
            "action",
            "parameter_high",
            "tick_high",
        },
    }
    counters = {name: Counter() for name in supported_mutations}
    scenarios: dict[str, dict[str, Counter[str]]] = {
        name: defaultdict(Counter) for name in supported_mutations
    }
    input_oracle_compiler_mismatches = 0
    input_expectation_mismatches = 0
    case_count = 0
    cases_path = root / config["exp07_cases"]
    with gzip.open(cases_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            case_count += 1
            input_oracle_compiler_mismatches += not record["compiler_oracle_match"]
            input_expectation_mismatches += not record["oracle_expectation_match"]
            scope = scope_by_id[record["scope_id"]]
            request = record["request"]
            oracle = record["oracle_allow"]
            decisions = {
                "opcua_role_projection": record["baselines"]["opcua_role_projection"],
                "plc_abac_projection": record["baselines"]["plc_abac_projection"],
                "sint_pinned_profile": sint_profile_allows(scope, request),
            }
            scenario = record["mutation"] or "valid"
            for name, decision in decisions.items():
                in_fair_subset = scenario == "valid" or scenario in supported_mutations[name]
                _update(counters[name], decision, oracle, in_fair_subset)
                scenario_counter = scenarios[name][scenario]
                scenario_counter["cases"] += 1
                scenario_counter["agreement"] += decision == oracle
                scenario_counter["false_allow"] += decision and not oracle
                scenario_counter["false_deny"] += not decision and oracle

    expressiveness = {
        "dimensions": [
            "zone",
            "conduit",
            "asset",
            "action",
            "parameter",
            "time",
            "mode",
            "pre_action_sequence",
        ],
        "systems": {
            "ZoneCap": {
                "zone": "full",
                "conduit": "full",
                "asset": "full",
                "action": "full",
                "parameter": "full bilateral interval",
                "time": "full bilateral window",
                "mode": "full",
                "pre_action_sequence": "full ordered subsequence",
            },
            "opcua_role_projection": {
                "zone": "N/A",
                "conduit": "N/A",
                "asset": "full node/resource binding",
                "action": "full permission binding",
                "parameter": "N/A",
                "time": "N/A",
                "mode": "N/A",
                "pre_action_sequence": "N/A",
            },
            "plc_abac_projection": {
                "zone": "full source/target attributes",
                "conduit": "N/A",
                "asset": "full",
                "action": "full",
                "parameter": "N/A",
                "time": "full window",
                "mode": "full",
                "pre_action_sequence": "N/A",
            },
            "sint_pinned_profile": {
                "zone": "N/A",
                "conduit": "N/A",
                "asset": "full invariant resource",
                "action": "full subset",
                "parameter": "partial non-negative upper maximum",
                "time": "partial expiry upper bound",
                "mode": "N/A",
                "pre_action_sequence": "N/A",
            },
        },
        "baseline_status": {
            "opcua_role_projection": "functional projection; no server implementation",
            "plc_abac_projection": "functional projection; no complete runnable artifact located",
            "sint_pinned_profile": {
                "status": "schema projection grounded in executable pinned token instance",
                "commit": sint_instance["commit"],
                "source_hashes": sint_instance["source_hashes"],
            },
        },
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "expressiveness.json", expressiveness)
    baseline_metrics = {
        name: {
            **dict(counter),
            "overall_agreement_rate": counter["agreement"] / counter["cases"],
            "fair_subset_agreement_rate": 1
            - counter["fair_subset_mismatches"] / counter["fair_subset_cases"],
            "fully_supported_mutation_categories": sorted(supported_mutations[name]),
            "scenarios": {
                scenario: dict(values) for scenario, values in scenarios[name].items()
            },
        }
        for name, counter in counters.items()
    }
    _write_json(output_dir / "baseline_metrics.json", baseline_metrics)
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "cases": case_count,
        "input_compiler_oracle_mismatches": input_oracle_compiler_mismatches,
        "input_oracle_expectation_mismatches": input_expectation_mismatches,
        "systems": 4,
        "authority_dimensions": 8,
        "baseline_overall_false_allows": {
            name: counter["false_allow"] for name, counter in counters.items()
        },
        "baseline_overall_false_denies": {
            name: counter["false_deny"] for name, counter in counters.items()
        },
        "baseline_fair_subset_mismatches": {
            name: counter["fair_subset_mismatches"] for name, counter in counters.items()
        },
        "sint_commit": sint_instance["commit"],
    }
    observed_flat = {
        "cases": case_count,
        "opcua_false_allows": counters["opcua_role_projection"]["false_allow"],
        "plc_abac_false_allows": counters["plc_abac_projection"]["false_allow"],
        "sint_false_allows": counters["sint_pinned_profile"]["false_allow"],
    }
    metrics["expected_count_mismatches"] = {
        name: {"expected": expected, "observed": observed_flat.get(name)}
        for name, expected in config["expected_counts"].items()
        if observed_flat.get(name) != expected
    }
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"cases={case_count}",
        f"opcua_false_allows={observed_flat['opcua_false_allows']}",
        f"plc_abac_false_allows={observed_flat['plc_abac_false_allows']}",
        f"sint_false_allows={observed_flat['sint_false_allows']}",
        f"input_compiler_oracle_mismatches={input_oracle_compiler_mismatches}",
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
        "input_compiler_oracle_mismatches": input_oracle_compiler_mismatches,
        "input_oracle_expectation_mismatches": input_expectation_mismatches,
        "baseline_false_denies": sum(counter["false_deny"] for counter in counters.values()),
        "fair_subset_mismatches": sum(
            counter["fair_subset_mismatches"] for counter in counters.values()
        ),
    }
    if any(failures.values()):
        raise AssertionError(f"exp-10 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
