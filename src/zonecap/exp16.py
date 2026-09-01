from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from typing import Any

from .effects import BoundedEffectExecutor, EffectBinding, PhysicalAction
from .engine import PolicyEngine
from .models import ActionRequest, Capability, Decision, Effect, Interval


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


def _capabilities() -> tuple[Capability, Capability]:
    parent = Capability(
        capability_id="exp16-parent",
        issuer="issuer",
        subject="operator",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary"}),
        assets=frozenset({"valve"}),
        actions=frozenset({"read", "set"}),
        parameter=Interval(0.0, 1.0),
        ticks=Interval(0.0, 10.0),
        modes=frozenset({"normal"}),
    )
    child = parent.attenuate(
        capability_id="exp16-child", parameter=Interval(0.0, 0.4)
    )
    return parent, child


def _request(**updates: Any) -> ActionRequest:
    values: dict[str, Any] = {
        "subject": "operator",
        "source_zone": "operations",
        "target_zone": "control",
        "conduit": "primary",
        "asset": "valve",
        "action": "set",
        "value": 0.2,
        "tick": 5,
        "mode": "normal",
    }
    values.update(updates)
    return ActionRequest(**values)


def _authorized(capability: Capability, action: PhysicalAction | None) -> bool:
    return action is None or (
        action.operation in capability.actions
        and capability.parameter.contains(action.value)
    )


def _sequence(
    executor: BoundedEffectExecutor,
    parent: Capability,
    child: Capability,
    requests: list[ActionRequest],
) -> list[dict[str, Any]]:
    engine = PolicyEngine()
    records = []
    physical_state = 0.0
    for request in requests:
        outcome = executor.evaluate(engine, child, request)
        before = physical_state
        if outcome.emitted is not None and outcome.emitted.operation != "read":
            physical_state += outcome.emitted.value
        records.append(
            {
                "effect": outcome.decision.effect.value,
                "reason": outcome.decision.reason,
                "fail_closed": outcome.fail_closed,
                "emitted": (
                    None
                    if outcome.emitted is None
                    else {
                        "operation": outcome.emitted.operation,
                        "value": outcome.emitted.value,
                    }
                ),
                "authorized": _authorized(child, outcome.emitted),
                "parent_authorized": _authorized(parent, outcome.emitted),
                "stutter": (
                    outcome.decision.effect is not Effect.DEFER
                    or (
                        outcome.emitted is not None
                        and outcome.emitted.operation == "read"
                        and physical_state == before
                    )
                ),
            }
        )
    return records


def audit(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    parent, child = _capabilities()
    safe_binding = EffectBinding("read", 0.0)
    request = _request(value=0.8)
    unsafe_decision = Decision(
        Effect.REWRITE,
        "forced unsafe rewrite",
        rewritten_value=config["unauthorized_rewrite_value"],
    )
    unsafe_executor = BoundedEffectExecutor(
        safe_binding, max_deferrals=config["max_deferrals"]
    )
    unsafe_outcome = unsafe_executor.apply(child, request, unsafe_decision)
    bypassed_action = PhysicalAction(
        request.action, config["unauthorized_rewrite_value"]
    )
    unauthorized_rewrite = {
        "expected_effect": "deny",
        "effect": unsafe_outcome.decision.effect.value,
        "fail_closed": unsafe_outcome.fail_closed,
        "emitted": None,
        "child_authorized_if_bypassed": _authorized(child, bypassed_action),
        "parent_authorized_if_bypassed": _authorized(parent, bypassed_action),
        "counterexample_if_binding_bypassed": {
            "operation": bypassed_action.operation,
            "value": bypassed_action.value,
            "child_parameter": child.parameter.to_list(),
            "parent_parameter": parent.parameter.to_list(),
        },
    }

    missing_hold_executor = BoundedEffectExecutor(
        EffectBinding("hold", 0.0), max_deferrals=config["max_deferrals"]
    )
    missing_hold_outcome = missing_hold_executor.evaluate(
        PolicyEngine(), child, _request(high_risk=True)
    )
    missing_hold = {
        "expected_effect": "deny",
        "effect": missing_hold_outcome.decision.effect.value,
        "fail_closed": missing_hold_outcome.fail_closed,
        "emitted": None,
    }

    lost_context = _sequence(
        BoundedEffectExecutor(safe_binding, config["max_deferrals"]),
        parent,
        child,
        [_request(context_complete=False) for _ in range(config["max_deferrals"] + 1)],
    )
    approval_timeout = _sequence(
        BoundedEffectExecutor(safe_binding, config["max_deferrals"]),
        parent,
        child,
        [_request(high_risk=True) for _ in range(config["max_deferrals"] + 1)],
    )
    recovery = _sequence(
        BoundedEffectExecutor(safe_binding, config["max_deferrals"]),
        parent,
        child,
        [_request(context_complete=False), _request()],
    )

    expected_timeout = [
        *(["defer"] * config["max_deferrals"]),
        "deny",
    ]
    cases = {
        "unauthorized_rewrite": {
            **unauthorized_rewrite,
            "expectation_matched": (
                unauthorized_rewrite["effect"] == "deny"
                and unauthorized_rewrite["fail_closed"]
                and not unauthorized_rewrite["child_authorized_if_bypassed"]
                and not unauthorized_rewrite["parent_authorized_if_bypassed"]
            ),
        },
        "missing_hold_action": {
            **missing_hold,
            "expectation_matched": missing_hold["effect"] == "deny"
            and missing_hold["fail_closed"],
        },
        "lost_context": {
            "expected_effects": expected_timeout,
            "steps": lost_context,
            "expectation_matched": [step["effect"] for step in lost_context]
            == expected_timeout
            and all(
                step["authorized"] and step["parent_authorized"] and step["stutter"]
                for step in lost_context
            ),
        },
        "approval_timeout": {
            "expected_effects": expected_timeout,
            "steps": approval_timeout,
            "expectation_matched": [step["effect"] for step in approval_timeout]
            == expected_timeout
            and all(
                step["authorized"] and step["parent_authorized"] and step["stutter"]
                for step in approval_timeout
            ),
        },
        "recovery_before_timeout": {
            "expected_effects": ["defer", "allow"],
            "steps": recovery,
            "expectation_matched": [step["effect"] for step in recovery]
            == ["defer", "allow"]
            and all(
                step["authorized"] and step["parent_authorized"] and step["stutter"]
                for step in recovery
            ),
        },
    }
    counterexamples = {
        "registered_premise_removed": [
            {
                "case": "unauthorized_rewrite",
                "removed_premise": "rewrite output remains inside the effective capability",
                **unauthorized_rewrite["counterexample_if_binding_bypassed"],
            }
        ]
    }
    return cases, counterexamples


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-16 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    cases, counterexamples = audit(config)
    all_steps = [
        step
        for name in ("lost_context", "approval_timeout", "recovery_before_timeout")
        for step in cases[name]["steps"]
    ]
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "seed": None,
        "cases": len(cases),
        "expectation_mismatches": sum(
            not record["expectation_matched"] for record in cases.values()
        ),
        "immediate_fail_closed_cases": sum(
            cases[name]["fail_closed"]
            for name in ("unauthorized_rewrite", "missing_hold_action")
        ),
        "timeout_fail_closed_cases": sum(
            cases[name]["steps"][-1]["fail_closed"]
            for name in ("lost_context", "approval_timeout")
        ),
        "authorized_defer_holds": sum(
            step["effect"] == "defer" and step["authorized"] and step["stutter"]
            for step in all_steps
        ),
        "recovery_allows": sum(
            step["effect"] == "allow"
            for step in cases["recovery_before_timeout"]["steps"]
        ),
        "executor_unauthorized_outputs": sum(
            not step["authorized"] or not step["parent_authorized"]
            for step in all_steps
        ),
        "executor_nonstutter_defers": sum(not step["stutter"] for step in all_steps),
        "terminal_pending_requests": sum(
            cases[name]["steps"][-1]["effect"] != "deny"
            for name in ("lost_context", "approval_timeout")
        ),
        "premise_removed_counterexamples": len(
            counterexamples["registered_premise_removed"]
        ),
        "max_deferrals": config["max_deferrals"],
    }
    observed = {key: metrics.get(key) for key in config["expected_counts"]}
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": observed[key]}
        for key, expected in config["expected_counts"].items()
        if observed[key] != expected
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "cases.json", cases)
    _write_json(output_dir / "counterexamples.json", counterexamples)
    _write_json(output_dir / "metrics.json", metrics)
    log_lines = [
        f"experiment={config['exp']}",
        "seed=none",
        f"cases={metrics['cases']}",
        f"expectation_mismatches={metrics['expectation_mismatches']}",
        f"immediate_fail_closed_cases={metrics['immediate_fail_closed_cases']}",
        f"timeout_fail_closed_cases={metrics['timeout_fail_closed_cases']}",
        f"authorized_defer_holds={metrics['authorized_defer_holds']}",
        f"recovery_allows={metrics['recovery_allows']}",
        f"premise_removed_counterexamples={metrics['premise_removed_counterexamples']}",
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
    if metrics["expected_count_mismatches"] or metrics["expectation_mismatches"]:
        raise AssertionError(f"exp-16 expectation mismatch: {metrics}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
