from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Callable

from .compiler import Architecture, CompilationError
from .engine import PolicyEngine
from .models import ActionRequest, Effect


def base_document() -> dict[str, Any]:
    return {
        "name": "exp11_sanity",
        "zones": ["source", "target"],
        "conduits": [
            {
                "id": "source_to_target",
                "source": "source",
                "target": "target",
                "assets": ["asset"],
                "actions": ["read"],
                "parameter": [0, 100],
            }
        ],
        "policies": [
            {
                "id": "policy",
                "issuer": "issuer",
                "subject": "subject",
                "source_zone": "source",
                "target_zone": "target",
                "conduit": "source_to_target",
                "assets": ["asset"],
                "actions": ["read"],
                "parameter": [0, 100],
                "ticks": [100, 200],
                "modes": ["normal"],
                "required_sequence": ["authenticate"],
            }
        ],
        "plant_1d": {
            "a": 1,
            "b": 1,
            "disturbance": [0, 0],
            "initial_state": [0, 0],
        },
    }


def _request(**updates: Any) -> ActionRequest:
    values = {
        "subject": "subject",
        "source_zone": "source",
        "target_zone": "target",
        "conduit": "source_to_target",
        "asset": "asset",
        "action": "read",
        "value": 50,
        "tick": 150,
        "mode": "normal",
        "history": ("authenticate",),
    }
    values.update(updates)
    return ActionRequest(**values)


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


def _write_fixture(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_matrix(fixture_dir: Path) -> dict[str, Any]:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    base = base_document()
    mutations: list[tuple[str, Callable[[dict[str, Any]], None], bool, str | None]] = [
        ("valid_compile", lambda doc: None, True, None),
        (
            "duplicate_zone",
            lambda doc: doc["zones"].append("source"),
            False,
            "duplicate zone",
        ),
        (
            "duplicate_conduit",
            lambda doc: doc["conduits"].append(deepcopy(doc["conduits"][0])),
            False,
            "duplicate conduit",
        ),
        (
            "unknown_source_zone",
            lambda doc: doc["policies"][0].update(source_zone="unknown"),
            False,
            "unknown source or target zone",
        ),
        (
            "unknown_target_zone",
            lambda doc: doc["policies"][0].update(target_zone="unknown"),
            False,
            "unknown source or target zone",
        ),
        (
            "unknown_conduit",
            lambda doc: doc["policies"][0].update(conduit="unknown"),
            False,
            "unknown conduit",
        ),
        (
            "wrong_conduit_endpoints",
            lambda doc: doc["conduits"][0].update(target="source"),
            False,
            "endpoints do not match",
        ),
        (
            "asset_outside_conduit",
            lambda doc: doc["policies"][0].update(assets=["other"]),
            False,
            "asset not carried",
        ),
        (
            "action_outside_conduit",
            lambda doc: doc["policies"][0].update(actions=["write"]),
            False,
            "action not permitted",
        ),
        (
            "parameter_exceeds_conduit",
            lambda doc: doc["policies"][0].update(parameter=[-1, 101]),
            False,
            "parameter exceeds",
        ),
        (
            "empty_asset_and_action_scopes",
            lambda doc: doc["policies"][0].update(assets=[], actions=[]),
            True,
            None,
        ),
    ]
    compile_records: list[dict[str, Any]] = []
    capabilities = {}
    for name, mutation, expected_success, expected_error in mutations:
        document = deepcopy(base)
        mutation(document)
        path = fixture_dir / f"{name}.json"
        _write_fixture(path, document)
        success = True
        error = None
        capability = None
        try:
            capability = Architecture.load(path).compile_all()[0]
        except (CompilationError, KeyError, ValueError) as caught:
            success = False
            error = str(caught)
        expectation_match = success == expected_success and (
            expected_error is None or (error is not None and expected_error in error)
        )
        compile_records.append(
            {
                "case": name,
                "expected_success": expected_success,
                "expected_error_contains": expected_error,
                "success": success,
                "error": error,
                "expectation_match": expectation_match,
            }
        )
        if capability is not None:
            capabilities[name] = capability

    engine = PolicyEngine()
    valid_capability = capabilities["valid_compile"]
    decision_specs = [
        ("parameter_low_boundary", _request(value=0), Effect.ALLOW),
        ("parameter_high_boundary", _request(value=100), Effect.ALLOW),
        ("parameter_below_boundary", _request(value=-1), Effect.DENY),
        ("parameter_above_boundary", _request(value=101), Effect.DENY),
        ("tick_low_boundary", _request(tick=100), Effect.ALLOW),
        ("tick_high_boundary", _request(tick=200), Effect.ALLOW),
        ("before_time_window", _request(tick=99), Effect.DENY),
        ("expired_window", _request(tick=201), Effect.DENY),
        ("wrong_mode", _request(mode="maintenance"), Effect.DENY),
        ("missing_history", _request(history=()), Effect.DENY),
        (
            "empty_scope_request",
            _request(),
            Effect.DENY,
        ),
    ]
    decision_records = []
    for name, request, expected_effect in decision_specs:
        capability = (
            capabilities["empty_asset_and_action_scopes"]
            if name == "empty_scope_request"
            else valid_capability
        )
        result = engine.evaluate(capability, request, rewrite_out_of_range=False)
        decision_records.append(
            {
                "case": name,
                "expected_effect": expected_effect.value,
                "effect": result.effect.value,
                "reason": result.reason,
                "expectation_match": result.effect is expected_effect,
            }
        )
    return {"compile_cases": compile_records, "decision_cases": decision_records}


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-11 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    matrix = run_matrix(output_dir / "fixtures")
    _write_json(output_dir / "cases.json", matrix)
    compile_cases = matrix["compile_cases"]
    decision_cases = matrix["decision_cases"]
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "compile_cases": len(compile_cases),
        "expected_compile_successes": sum(case["expected_success"] for case in compile_cases),
        "expected_compile_rejections": sum(not case["expected_success"] for case in compile_cases),
        "compile_expectation_mismatches": sum(
            not case["expectation_match"] for case in compile_cases
        ),
        "decision_cases": len(decision_cases),
        "expected_allows": sum(case["expected_effect"] == "allow" for case in decision_cases),
        "expected_denies": sum(case["expected_effect"] == "deny" for case in decision_cases),
        "decision_expectation_mismatches": sum(
            not case["expectation_match"] for case in decision_cases
        ),
        "total_cases": len(compile_cases) + len(decision_cases),
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
        f"compile_cases={metrics['compile_cases']}",
        f"compile_expectation_mismatches={metrics['compile_expectation_mismatches']}",
        f"decision_cases={metrics['decision_cases']}",
        f"decision_expectation_mismatches={metrics['decision_expectation_mismatches']}",
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
    if (
        metrics["expected_count_mismatches"]
        or metrics["compile_expectation_mismatches"]
        or metrics["decision_expectation_mismatches"]
    ):
        raise AssertionError(f"exp-11 expectation mismatch: {metrics}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
