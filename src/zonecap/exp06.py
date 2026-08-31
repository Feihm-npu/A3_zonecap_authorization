from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .models import Capability, Interval, Plant1D
from .reachability import monotonicity_violations, reachable_intervals_1d


def _capabilities() -> tuple[Capability, Capability]:
    parent = Capability(
        capability_id="exp06-parent",
        issuer="issuer",
        subject="operator",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary"}),
        assets=frozenset({"valve"}),
        actions=frozenset({"set"}),
        parameter=Interval(0.0, 1.0),
        ticks=Interval(0.0, 10.0),
        modes=frozenset({"normal"}),
    )
    child = parent.attenuate(
        capability_id="exp06-child", parameter=Interval(0.2, 0.7)
    )
    return parent, child


def _legal_case(
    name: str,
    plant: Plant1D,
    initial: Interval,
    parent: Capability,
    child: Capability,
    horizon: int,
) -> dict[str, Any]:
    violations = monotonicity_violations(
        plant, initial, parent, child, horizon=horizon
    )
    return {
        "case": name,
        "expected": "zero inclusion violations",
        "observed": "zero inclusion violations" if not violations else "violation",
        "expectation_matched": not violations,
        "violations": violations,
    }


def run_matrix(config: dict[str, Any]) -> dict[str, Any]:
    parent, child = _capabilities()
    horizon = int(config["horizon"])
    initial = Interval.from_pair(config["initial"])
    cases: list[dict[str, Any]] = []

    identity = parent.attenuate(capability_id="exp06-identity")
    cases.append(
        _legal_case(
            "identity_child",
            Plant1D(a=1.0, b=1.0, disturbance=Interval(0.0, 0.0)),
            initial,
            parent,
            identity,
            horizon,
        )
    )

    empty = parent.attenuate(capability_id="exp06-empty-action", actions=set())
    empty_reach = reachable_intervals_1d(
        Plant1D(a=1.0, b=1.0, disturbance=Interval(0.0, 0.0)),
        initial,
        empty,
        horizon,
    )
    empty_violations = monotonicity_violations(
        Plant1D(a=1.0, b=1.0, disturbance=Interval(0.0, 0.0)),
        initial,
        parent,
        empty,
        horizon,
    )
    empty_matched = empty_reach[0] == initial and all(
        reachable is None for reachable in empty_reach[1:]
    ) and not empty_violations
    cases.append(
        {
            "case": "empty_action_child",
            "expected": "Reach_0 is common and every postinitial set is empty",
            "observed": [
                None if reachable is None else reachable.to_list()
                for reachable in empty_reach
            ],
            "expectation_matched": empty_matched,
            "violations": empty_violations,
        }
    )

    for plant_config in config["signed_plants"]:
        cases.append(
            _legal_case(
                plant_config["name"],
                Plant1D(
                    a=float(plant_config["a"]),
                    b=float(plant_config["b"]),
                    disturbance=Interval.from_pair(plant_config["disturbance"]),
                ),
                initial,
                parent,
                child,
                horizon,
            )
        )

    for name, disturbance in (
        ("zero_disturbance", Interval(0.0, 0.0)),
        ("nonzero_asymmetric_disturbance", Interval(-0.1, 0.2)),
    ):
        cases.append(
            _legal_case(
                name,
                Plant1D(a=-0.8, b=1.3, disturbance=disturbance),
                initial,
                parent,
                child,
                horizon,
            )
        )

    widened = replace(
        child,
        capability_id="exp06-deliberately-widened",
        parameter=Interval(-1.0, 2.0),
    )
    syntax_rejected = False
    syntax_error = None
    try:
        widened.assert_attenuates(parent)
    except ValueError as error:
        syntax_rejected = True
        syntax_error = str(error)
    widened_plant = Plant1D(a=0.0, b=1.0, disturbance=Interval(0.0, 0.0))
    parent_sets = reachable_intervals_1d(
        widened_plant, initial, parent, horizon=1
    )
    widened_sets = reachable_intervals_1d(
        widened_plant, initial, widened, horizon=1
    )
    assert parent_sets[1] is not None and widened_sets[1] is not None
    physical_violation_detected = not widened_sets[1].is_subset_of(parent_sets[1])
    cases.append(
        {
            "case": "deliberately_widened_child",
            "expected": "syntax rejection and a one-step physical inclusion violation if bypassed",
            "observed": {
                "syntax_rejected": syntax_rejected,
                "syntax_error": syntax_error,
                "parent_reach_1": parent_sets[1].to_list(),
                "widened_child_reach_1": widened_sets[1].to_list(),
                "physical_violation_detected": physical_violation_detected,
            },
            "expectation_matched": syntax_rejected and physical_violation_detected,
            "violations": (
                [] if syntax_rejected and physical_violation_detected else ["negative control failed"]
            ),
        }
    )

    return {
        "cases": cases,
        "expectation_mismatches": [
            case["case"] for case in cases if not case["expectation_matched"]
        ],
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    matrix = run_matrix(config)
    legal_cases = [
        case for case in matrix["cases"] if case["case"] != "deliberately_widened_child"
    ]
    widened = next(
        case for case in matrix["cases"] if case["case"] == "deliberately_widened_child"
    )
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "sanity_cases": len(matrix["cases"]),
        "legal_cases": len(legal_cases),
        "legal_case_inclusion_violations": sum(
            len(case["violations"]) for case in legal_cases
        ),
        "identity_case_passed": next(
            case["expectation_matched"]
            for case in matrix["cases"]
            if case["case"] == "identity_child"
        ),
        "empty_action_case_passed": next(
            case["expectation_matched"]
            for case in matrix["cases"]
            if case["case"] == "empty_action_child"
        ),
        "signed_plant_cases": len(config["signed_plants"]),
        "widened_child_syntax_rejected": widened["observed"]["syntax_rejected"],
        "widened_child_physical_violation_detected": widened["observed"][
            "physical_violation_detected"
        ],
        "expectation_mismatches": len(matrix["expectation_mismatches"]),
        "registered_c1_counterexamples": 0,
    }
    manifest_paths = [
        config_path,
        root / "src/zonecap/reachability.py",
        root / "src/zonecap/exp06.py",
        root / "tests/test_reachability.py",
        root / "research/c1_sanity_matrix.md",
    ]
    manifest = {
        "git_head": _git_head(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "files": {
            str(path.relative_to(root)): _sha256(path) for path in manifest_paths
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in (
        ("metrics.json", metrics),
        ("cases.json", matrix),
        ("manifest.json", manifest),
    ):
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    log = [
        f"experiment={config['exp']}",
        "seed=none",
        f"sanity_cases={metrics['sanity_cases']}",
        f"legal_case_inclusion_violations={metrics['legal_case_inclusion_violations']}",
        f"widened_child_syntax_rejected={str(metrics['widened_child_syntax_rejected']).lower()}",
        f"widened_child_physical_violation_detected={str(metrics['widened_child_physical_violation_detected']).lower()}",
        f"expectation_mismatches={metrics['expectation_mismatches']}",
        "registered_c1_counterexamples=0",
    ]
    (output_dir / "log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
