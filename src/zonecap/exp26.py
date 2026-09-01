from __future__ import annotations

import argparse
from collections import deque
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any, Callable

from .engine import PolicyEngine
from .models import ActionRequest, Capability, Effect, Interval


REQUIRED_STAGES = (
    "parse",
    "token_integrity",
    "revocation",
    "context",
    "decision",
    "audit",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_gzip_json(path: Path, payload: Any) -> None:
    serialized = (json.dumps(payload, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    path.write_bytes(gzip.compress(serialized, mtime=0))


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def nearest_rank(values: list[int], proportion: float) -> int:
    if not values:
        raise ValueError("percentile needs at least one value")
    if not 0 < proportion <= 1:
        raise ValueError("proportion must be in (0, 1]")
    ordered = sorted(values)
    return ordered[math.ceil(proportion * len(ordered)) - 1]


def distribution(values: list[int]) -> dict[str, Any]:
    return {
        "samples": len(values),
        "minimum_ns": min(values),
        "p50_ns": nearest_rank(values, 0.50),
        "p95_ns": nearest_rank(values, 0.95),
        "p99_ns": nearest_rank(values, 0.99),
        "p999_ns": nearest_rank(values, 0.999),
        "maximum_ns": max(values),
        "mean_ns": sum(values) / len(values),
        "zero_or_negative_samples": sum(value <= 0 for value in values),
    }


def empirical_timer_deltas(pairs: int) -> tuple[list[int], int]:
    deltas = []
    monotonicity_violations = 0
    for _ in range(pairs):
        before = time.perf_counter_ns()
        after = time.perf_counter_ns()
        delta = after - before
        monotonicity_violations += delta < 0
        if delta > 0:
            deltas.append(delta)
    return deltas, monotonicity_violations


def measure(
    operation: Callable[[], int], *, warmups: int, samples: int
) -> tuple[list[int], int]:
    checksum = 0
    for _ in range(warmups):
        checksum ^= operation()
    durations = []
    for _ in range(samples):
        started = time.perf_counter_ns()
        value = operation()
        stopped = time.perf_counter_ns()
        durations.append(stopped - started)
        checksum ^= value
    return durations, checksum


class InstrumentedSanityPipeline:
    def __init__(self) -> None:
        self.payload = json.dumps(
            {
                "subject": "operator.alice",
                "source_zone": "operations",
                "target_zone": "basic_control",
                "conduit": "ops_to_basic",
                "asset": "inlet_valve",
                "action": "set",
                "value": 0.5,
                "tick": 10,
                "mode": "normal",
                "history": ["inspect"],
                "context_complete": True,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.token = b"zonecap-exp26-frozen-token"
        self.token_digest = hashlib.sha256(self.token).digest()
        self.revoked: set[bytes] = set()
        self.audit: deque[tuple[str, int]] = deque(maxlen=2048)
        self.engine = PolicyEngine()
        self.capability = Capability(
            capability_id="exp26",
            issuer="authority",
            subject="operator.alice",
            source_zone="operations",
            target_zone="basic_control",
            conduits=frozenset({"ops_to_basic"}),
            assets=frozenset({"inlet_valve"}),
            actions=frozenset({"set"}),
            parameter=Interval(0.0, 1.0),
            ticks=Interval(0, 100),
            modes=frozenset({"normal"}),
            required_sequence=("inspect",),
        )

    def evaluate(
        self,
        *,
        disabled_stage: str | None = None,
        forced_delay_ns: int = 0,
    ) -> tuple[int, tuple[str, ...]]:
        if disabled_stage is not None and disabled_stage not in REQUIRED_STAGES:
            raise ValueError(f"unknown disabled stage: {disabled_stage}")
        active = []

        if disabled_stage != "parse":
            document = json.loads(self.payload)
            active.append("parse")
        else:
            document = {
                "subject": "operator.alice",
                "source_zone": "operations",
                "target_zone": "basic_control",
                "conduit": "ops_to_basic",
                "asset": "inlet_valve",
                "action": "set",
                "value": 0.5,
                "tick": 10,
                "mode": "normal",
                "history": ["inspect"],
                "context_complete": True,
            }

        if disabled_stage != "token_integrity":
            if hashlib.sha256(self.token).digest() != self.token_digest:
                raise RuntimeError("token integrity failure")
            active.append("token_integrity")

        if disabled_stage != "revocation":
            if self.token_digest in self.revoked:
                raise RuntimeError("token revoked")
            active.append("revocation")

        if disabled_stage != "context":
            if not document.get("context_complete"):
                raise RuntimeError("runtime context unavailable")
            active.append("context")

        decision_effect = Effect.ALLOW
        if disabled_stage != "decision":
            request = ActionRequest(
                subject=document["subject"],
                source_zone=document["source_zone"],
                target_zone=document["target_zone"],
                conduit=document["conduit"],
                asset=document["asset"],
                action=document["action"],
                value=document["value"],
                tick=document["tick"],
                mode=document["mode"],
                history=tuple(document["history"]),
                context_complete=document["context_complete"],
            )
            decision_effect = self.engine.evaluate(self.capability, request).effect
            if decision_effect is not Effect.ALLOW:
                raise RuntimeError(f"unexpected sanity decision: {decision_effect.value}")
            active.append("decision")

        if disabled_stage != "audit":
            self.audit.append((decision_effect.value, self.token_digest[0]))
            active.append("audit")

        if forced_delay_ns:
            time.sleep(forced_delay_ns / 1_000_000_000)
        return self.token_digest[0] ^ len(self.audit), tuple(active)


def check_activation_audit(
    pipeline: InstrumentedSanityPipeline,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    _, full_active = pipeline.evaluate()
    full_missing = sorted(set(REQUIRED_STAGES) - set(full_active))
    records = []
    killed = 0
    for stage in REQUIRED_STAGES:
        _, active = pipeline.evaluate(disabled_stage=stage)
        missing = sorted(set(REQUIRED_STAGES) - set(active))
        detected = missing == [stage]
        killed += detected
        records.append(
            {
                "disabled_stage": stage,
                "active_stages": list(active),
                "missing_stages": missing,
                "detected": detected,
            }
        )
    return (
        {
            "required_stages": list(REQUIRED_STAGES),
            "full_active_stages": list(full_active),
            "full_missing_stages": full_missing,
            "mutants": len(records),
            "mutants_killed": killed,
            "records": records,
        },
        full_active,
    )


def proc_allowed_list() -> str:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("Cpus_allowed_list:"):
            return line.partition(":")[2].strip()
    raise RuntimeError("Cpus_allowed_list missing from /proc/self/status")


def execute(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[int]], dict[str, Any]]:
    requested_core = config["cpu_core"]
    original_affinity = set(os.sched_getaffinity(0))
    if requested_core not in original_affinity:
        raise RuntimeError(f"requested CPU {requested_core} is unavailable")
    os.sched_setaffinity(0, {requested_core})
    try:
        observed_affinity = set(os.sched_getaffinity(0))
        proc_affinity = proc_allowed_list()
        clock = time.get_clock_info("perf_counter")
        timer_deltas, monotonicity_violations = empirical_timer_deltas(
            config["timer_pairs"]
        )
        pipeline = InstrumentedSanityPipeline()
        activation, _ = check_activation_audit(pipeline)

        empty_samples, empty_checksum = measure(
            lambda: 1,
            warmups=config["warmups"],
            samples=config["measured_samples"],
        )
        full_samples, full_checksum = measure(
            lambda: pipeline.evaluate()[0],
            warmups=config["warmups"],
            samples=config["measured_samples"],
        )
        slow_samples, slow_checksum = measure(
            lambda: pipeline.evaluate(forced_delay_ns=config["forced_delay_ns"])[0],
            warmups=config["forced_slow_warmups"],
            samples=config["forced_slow_samples"],
        )
    finally:
        os.sched_setaffinity(0, original_affinity)

    restored_affinity = set(os.sched_getaffinity(0))
    timer_stats = distribution(timer_deltas)
    empty_stats = distribution(empty_samples)
    full_stats = distribution(full_samples)
    slow_stats = distribution(slow_samples)
    timing_order = (
        empty_stats["p50_ns"] < full_stats["p50_ns"] < slow_stats["p50_ns"]
        and empty_stats["p99_ns"] < full_stats["p99_ns"] < slow_stats["p99_ns"]
    )
    empirical_resolution_below_empty = (
        timer_stats["minimum_ns"] < empty_stats["p50_ns"]
    )
    forced_slow_detected = slow_stats["minimum_ns"] >= config[
        "forced_slow_minimum_ns"
    ]
    affinity_verified = observed_affinity == {requested_core} and proc_affinity == str(
        requested_core
    )
    affinity_restored = restored_affinity == original_affinity
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "evidence_scope": "x86 infrastructure sanity only; not C5 hardware evidence",
        "seed": None,
        "clock_implementation": clock.implementation,
        "clock_monotonic": clock.monotonic,
        "clock_adjustable": clock.adjustable,
        "declared_clock_resolution_ns": int(clock.resolution * 1_000_000_000),
        "timer_pairs": config["timer_pairs"],
        "positive_timer_deltas": len(timer_deltas),
        "timer_monotonicity_violations": monotonicity_violations,
        "empty_samples": len(empty_samples),
        "full_sanity_samples": len(full_samples),
        "forced_slow_samples": len(slow_samples),
        "empirical_resolution_below_empty_p50": empirical_resolution_below_empty,
        "requested_cpu_core": requested_core,
        "observed_cpu_affinity": sorted(observed_affinity),
        "proc_cpus_allowed_list": proc_affinity,
        "affinity_verified": affinity_verified,
        "affinity_restored": affinity_restored,
        "required_checks": len(REQUIRED_STAGES),
        "check_mutants": activation["mutants"],
        "check_mutants_killed": activation["mutants_killed"],
        "full_missing_checks": activation["full_missing_stages"],
        "timer_delta_ns": timer_stats,
        "empty_call_ns": empty_stats,
        "full_sanity_pipeline_ns": full_stats,
        "forced_slow_pipeline_ns": slow_stats,
        "timing_order_passed": timing_order,
        "forced_slow_detected": forced_slow_detected,
        "checksums": {
            "empty": empty_checksum,
            "full": full_checksum,
            "forced_slow": slow_checksum,
        },
    }
    raw = {
        "timer_deltas_ns": timer_deltas,
        "empty_samples_ns": empty_samples,
        "full_samples_ns": full_samples,
        "forced_slow_samples_ns": slow_samples,
    }
    environment = {
        "original_affinity": sorted(original_affinity),
        "restored_affinity": sorted(restored_affinity),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "clock": {
            "implementation": clock.implementation,
            "monotonic": clock.monotonic,
            "adjustable": clock.adjustable,
            "resolution_seconds": clock.resolution,
        },
    }
    return metrics, raw, {"activation": activation, "environment": environment}


def run(config_path: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    dirty_before_run = _git(root, "status", "--porcelain")
    if dirty_before_run:
        raise RuntimeError("exp-26 requires a clean, committed pre-run freeze")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative_path, expected_hash in config["frozen_hashes"].items():
        if _sha256(root / relative_path) != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch: {relative_path}")

    metrics, raw, details = execute(config)
    metrics["expected_count_mismatches"] = {
        key: {"expected": expected, "observed": metrics.get(key)}
        for key, expected in config["expected_counts"].items()
        if metrics.get(key) != expected
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(config["command"] + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("none\n", encoding="utf-8")
    _write_json(output_dir / "metrics.json", metrics)
    _write_json(output_dir / "check_activation.json", details["activation"])
    _write_json(output_dir / "environment.json", details["environment"])
    for name, values in raw.items():
        _write_gzip_json(output_dir / f"{name}.json.gz", values)
    (output_dir / "log.txt").write_text(
        "\n".join(
            [
                f"experiment={config['exp']}",
                "seed=none",
                f"affinity_verified={str(metrics['affinity_verified']).lower()}",
                f"timer_resolution_ns={metrics['timer_delta_ns']['minimum_ns']}",
                f"empty_p99_ns={metrics['empty_call_ns']['p99_ns']}",
                f"full_p99_ns={metrics['full_sanity_pipeline_ns']['p99_ns']}",
                f"forced_slow_p99_ns={metrics['forced_slow_pipeline_ns']['p99_ns']}",
                f"timing_order_passed={str(metrics['timing_order_passed']).lower()}",
                "check_mutants_killed="
                f"{metrics['check_mutants_killed']}/{metrics['check_mutants']}",
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
        "inputs": {str(path.relative_to(root)): _sha256(path) for path in input_paths},
        "outputs": {
            str(path.relative_to(output_dir)): _sha256(path) for path in output_paths
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    failures = {
        "expected_count_mismatches": bool(metrics["expected_count_mismatches"]),
        "timer_resolution_not_below_empty": not metrics[
            "empirical_resolution_below_empty_p50"
        ],
        "timing_order": not metrics["timing_order_passed"],
        "forced_slow_not_detected": not metrics["forced_slow_detected"],
        "affinity_not_verified": not metrics["affinity_verified"],
        "affinity_not_restored": not metrics["affinity_restored"],
        "missing_full_check": bool(metrics["full_missing_checks"]),
        "nonpositive_timing_sample": any(
            metrics[name]["zero_or_negative_samples"]
            for name in (
                "timer_delta_ns",
                "empty_call_ns",
                "full_sanity_pipeline_ns",
                "forced_slow_pipeline_ns",
            )
        ),
    }
    if any(failures.values()):
        raise AssertionError(f"exp-26 expectation mismatch: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.config, arguments.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
