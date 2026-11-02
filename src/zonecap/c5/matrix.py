from __future__ import annotations

"""Run one registered C5 experiment: preflight, fresh-process repetitions, aggregation.

Usage (confirmatory runs require a clean, committed tree):

    PYTHONPATH=src python -m zonecap.c5.matrix --config configs/c5/exp22_c5_main.json \
        --corpus-dir build/c5_corpus --output-dir results/exp22_c5_main_<YYYYMMDD>

Configurations run in seed-major order; within seed ``i`` the registered
configuration list is rotated by ``i`` to spread thermal drift.  Every
repetition is a fresh ``zonecap.c5.harness`` process.  Aggregation recomputes
pooled percentiles from the returned raw samples.
"""

import argparse
from array import array
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

from .corpus import verify
from .harness import distribution, write_json


ROOT = Path(__file__).resolve().parents[3]


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python() -> list[str]:
    return [sys.executable, "-m"]


def _environment_commands(commands: list[str]) -> dict[str, Any]:
    captured = {}
    for command in commands:
        try:
            completed = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60
            )
            captured[command] = {
                "returncode": completed.returncode,
                "stdout": completed.stdout[-20000:],
                "stderr": completed.stderr[-4000:],
            }
        except subprocess.TimeoutExpired:
            captured[command] = {"returncode": None, "stdout": "", "stderr": "timeout"}
    return captured


def load_samples(path: Path) -> array:
    samples = array("Q")
    samples.frombytes(gzip.decompress(path.read_bytes()))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def rotated(items: list[Any], offset: int) -> list[Any]:
    offset %= len(items)
    return items[offset:] + items[:offset]


def aggregate(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    configurations = {}
    for item in config["configurations"]:
        name = item["name"]
        repetitions = {}
        pooled = array("Q")
        for seed in config["seeds"]:
            directory = output_dir / "configurations" / name / "repetitions" / str(seed)
            metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
            samples = load_samples(directory / "raw_samples_ns.bin.gz")
            recomputed = distribution(samples)
            if recomputed != metrics["decision_latency_ns"]:
                raise AssertionError(f"{name}/{seed}: raw samples do not reproduce metrics")
            pooled.extend(samples)
            repetitions[str(seed)] = {
                "p50_ns": metrics["decision_latency_ns"]["p50_ns"],
                "p99_ns": metrics["decision_latency_ns"]["p99_ns"],
                "p999_ns": metrics["decision_latency_ns"]["p999_ns"],
                "maximum_ns": metrics["decision_latency_ns"]["maximum_ns"],
                "derived_p99_scan_occupancy_percent": metrics["derived_p99_scan_occupancy_percent"],
                "throughput_decisions_per_s_wall": metrics["throughput_decisions_per_s_wall"],
                "peak_rss_kib": metrics["peak_rss_kib"],
                "decision_mismatches": metrics["decision_mismatches"],
                "stage_mask_failures": metrics["stage_mask_failures"],
                "verification_count_failures": metrics["verification_count_failures"],
                "signatures_verified": metrics["signatures_verified"],
                "verification_cache_hits": metrics["verification_cache_hits"],
                "audit_records": metrics["audit_records"],
                "threshold_checks": metrics["threshold_checks"],
                "latency_by_expected_effect_ns": metrics["latency_by_expected_effect_ns"],
                "latency_by_chain_depth_ns": metrics["latency_by_chain_depth_ns"],
            }
        worst = max(repetitions.items(), key=lambda pair: pair[1]["p99_ns"])
        configurations[name] = {
            "repetitions": repetitions,
            "pooled_decision_latency_ns": distribution(pooled),
            "worst_repetition": {"seed": int(worst[0]), "p99_ns": worst[1]["p99_ns"]},
            "every_repetition_passes": {
                check: all(rep["threshold_checks"][check] for rep in repetitions.values())
                for check in next(iter(repetitions.values()))["threshold_checks"]
            },
        }
    criteria = {}
    for criterion in config.get("criteria", []):
        selected = [configurations[name] for name in criterion["configurations"]]
        criteria[criterion["name"]] = {
            "statement": criterion["statement"],
            "configurations": criterion["configurations"],
            "checks": criterion["checks"],
            "all_repetitions_meet_checks": all(
                item["every_repetition_passes"][check]
                for item in selected
                for check in criterion["checks"]
            ),
        }
    return {"configurations": configurations, "registered_checks": criteria}


def run_matrix(
    config_path: Path,
    corpus_dir: Path,
    output_dir: Path,
    *,
    development: bool,
    fake_redis: bool,
    development_scale: int = 1,
) -> dict[str, Any]:
    config_path = config_path.resolve()
    corpus_dir = corpus_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite result directory: {output_dir}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run_role = "development" if development else "confirmatory"
    if development_scale != 1 and not development:
        raise RuntimeError("--development-scale requires --development")
    status = _git("status", "--porcelain")
    # Untracked result directories from earlier experiments are allowed, so the
    # four experiments can run back to back from one committed tree.
    blocking = [line for line in status.splitlines() if not line.startswith("?? results/")]

    # The run directory exists before any check, so an aborted attempt is retained.
    output_dir.mkdir(parents=True)
    command = " ".join(shlex.quote(part) for part in [sys.executable, "-m", "zonecap.c5.matrix", *sys.argv[1:]])
    write_json(output_dir / "config.json", config)
    (output_dir / "command.txt").write_text(command + "\n", encoding="utf-8")
    (output_dir / "seed.txt").write_text("".join(f"{seed}\n" for seed in config["seeds"]), encoding="utf-8")
    log_lines = [f"experiment={config['exp']}", f"run_role={run_role}",
                 f"development_scale={development_scale}",
                 f"git_head={_git('rev-parse', 'HEAD')}",
                 f"git_tree_clean_except_untracked_results={not blocking}"]

    def abort(reason: str, detail: str) -> None:
        (output_dir / "log.txt").write_text(
            "\n".join([*log_lines, f"aborted={reason}", f"detail={detail}"]) + "\n", encoding="utf-8"
        )
        raise RuntimeError(f"{reason}: {detail}; the aborted run directory is retained")

    if blocking and not development:
        abort("dirty_tree", " | ".join(blocking))
    hash_mismatches = sorted(
        path for path, expected in config["frozen_hashes"].items() if _sha256(ROOT / path) != expected
    )
    if hash_mismatches:
        abort("frozen_hash_mismatch", ", ".join(hash_mismatches))
    try:
        manifest = verify(corpus_dir)
    except RuntimeError as error:
        abort("corpus_hash_mismatch", str(error))
    if manifest["fingerprint"] != config["corpus_fingerprint"]:
        abort("corpus_fingerprint_mismatch", manifest["fingerprint"])
    write_json(
        output_dir / "environment_manifest.json",
        {"commands": _environment_commands(config.get("environment_commands", [])),
         "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    )

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    preflight = subprocess.run(
        [*_python(), "zonecap.c5.harness", "preflight", "--config", str(config_path),
         "--corpus-dir", str(corpus_dir), "--output-dir", str(output_dir)],
        cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    (output_dir / "preflight_stdout.log").write_text(preflight.stdout + preflight.stderr, encoding="utf-8")
    log_lines.append(f"preflight_returncode={preflight.returncode}")
    if preflight.returncode != 0:
        (output_dir / "log.txt").write_text("\n".join(log_lines) + "\naborted=preflight\n", encoding="utf-8")
        raise RuntimeError("preflight failed; the aborted run directory is retained")

    fake = None
    if fake_redis:
        if not development:
            raise RuntimeError("the fake Redis server is for development runs only")
        fake = subprocess.Popen(
            [*_python(), "zonecap.c5.resp", "--serve-fake", "--port", "0",
             "--cpu-core", str(config["cpu"].get("support_core", config["cpu"]["audit_core"]))],
            cwd=ROOT, env=environment, stdout=subprocess.PIPE, text=True,
        )
        port = fake.stdout.readline().strip()
        environment["ZONECAP_C5_REDIS_PORT"] = port
        log_lines.append(f"fake_redis_port={port}")

    names = [item["name"] for item in config["configurations"]]
    try:
        for seed_index, seed in enumerate(config["seeds"]):
            for name in rotated(names, seed_index):
                directory = output_dir / "configurations" / name / "repetitions" / str(seed)
                started = time.time()
                completed = subprocess.run(
                    [*_python(), "zonecap.c5.harness", "repetition", "--config", str(config_path),
                     "--configuration", name, "--seed", str(seed), "--corpus-dir", str(corpus_dir),
                     "--output-dir", str(directory), "--run-role", run_role,
                     "--development-scale", str(development_scale)],
                    cwd=ROOT, env=environment, capture_output=True, text=True,
                )
                log_lines.append(
                    f"repetition configuration={name} seed={seed} returncode={completed.returncode} "
                    f"seconds={time.time() - started:.1f}"
                )
                (directory.parent / f"{seed}.log").write_text(
                    completed.stdout + completed.stderr, encoding="utf-8"
                )
                if completed.returncode != 0:
                    (output_dir / "log.txt").write_text("\n".join(log_lines) + "\naborted=repetition\n", encoding="utf-8")
                    raise RuntimeError(f"repetition {name}/{seed} failed; directory retained")
        propagation = config.get("propagation")
        if propagation is not None:
            host = environment.get("ZONECAP_C5_REDIS_HOST", "127.0.0.1")
            port = environment.get("ZONECAP_C5_REDIS_PORT", "6379")
            completed = subprocess.run(
                [*_python(), "zonecap.c5.propagation", "--host", host, "--port", port,
                 "--count", str(propagation["revocations"]), "--seed", str(propagation["seed"]),
                 "--authority-core", str(propagation["authority_core"]),
                 "--resolver-core", str(propagation["resolver_core"]),
                 "--output-dir", str(output_dir / "propagation")],
                cwd=ROOT, env=environment, capture_output=True, text=True,
            )
            log_lines.append(f"propagation returncode={completed.returncode}")
            (output_dir / "propagation.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
            if completed.returncode != 0:
                (output_dir / "log.txt").write_text("\n".join(log_lines) + "\naborted=propagation\n", encoding="utf-8")
                raise RuntimeError("revocation propagation measurement failed; directory retained")
    finally:
        if fake is not None:
            fake.terminate()
            fake.wait(timeout=10)

    summary = aggregate(config, output_dir)
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "run_role": run_role,
        "development_scale": development_scale,
        "evidence_scope": config["evidence_scope"] if not development else
        "development run of the frozen harness; not C5 evidence",
        "seeds": config["seeds"],
        "corpus_fingerprint": manifest["fingerprint"],
        "corpus_variants": manifest["variants"],
        "token_bytes_by_depth": manifest["token_bytes_by_depth"],
        "preflight": json.loads(preflight.stdout.strip().splitlines()[-1]),
        **summary,
    }
    if config.get("propagation") is not None:
        metrics["revocation_propagation"] = json.loads(
            (output_dir / "propagation" / "metrics.json").read_text(encoding="utf-8")
        )
    if config.get("unavailable_baselines"):
        metrics["unavailable_baselines"] = config["unavailable_baselines"]
    ratio_limit = config.get("speedup_bug_signal_ratio")
    if ratio_limit is not None:
        configurations = summary["configurations"]
        baseline = configurations["sint"]["pooled_decision_latency_ns"]
        signals = {}
        for name in ("zonecap_full", "zonecap_cache_miss"):
            pooled = configurations[name]["pooled_decision_latency_ns"]
            ratios = {stat: baseline[stat] / pooled[stat] for stat in ("p50_ns", "p99_ns")}
            signals[name] = {
                "sint_over_zonecap": ratios,
                "audit_required": any(value > ratio_limit for value in ratios.values()),
            }
        metrics["speedup_bug_signal"] = {"ratio_limit": ratio_limit, "comparisons": signals}
    write_json(output_dir / "metrics.json", metrics)
    with (output_dir / "decision_mismatches.jsonl").open("w", encoding="utf-8") as sink:
        for path in sorted((output_dir / "configurations").rglob("decision_mismatches.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                record["repetition"] = str(path.parent.relative_to(output_dir))
                sink.write(json.dumps(record, sort_keys=True) + "\n")
    write_json(
        output_dir / "source_manifest.json",
        {"git_head": _git("rev-parse", "HEAD"), "git_status_before_run": status,
         "blocking_tree_changes": blocking,
         "frozen_hashes": config["frozen_hashes"], "corpus_manifest_sha256": _sha256(corpus_dir / "manifest.json")},
    )
    for name, item in summary["configurations"].items():
        log_lines.append(
            f"configuration={name} worst_p99_ns={item['worst_repetition']['p99_ns']} "
            f"pooled_p99_ns={item['pooled_decision_latency_ns']['p99_ns']}"
        )
    for name, item in summary["registered_checks"].items():
        log_lines.append(f"registered_check={name} all_repetitions_meet_checks={str(item['all_repetitions_meet_checks']).lower()}")
    (output_dir / "log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    inputs = [config_path, corpus_dir / "manifest.json", *[ROOT / path for path in config["frozen_hashes"]]]
    outputs = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.name != "manifest.json")
    write_json(
        output_dir / "manifest.json",
        {
            "git_head": _git("rev-parse", "HEAD"),
            "inputs": {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): _sha256(path) for path in inputs},
            "outputs": {str(path.relative_to(output_dir)): _sha256(path) for path in outputs},
        },
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one registered C5 experiment.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--fake-redis", action="store_true")
    parser.add_argument("--development-scale", type=int, default=1)
    arguments = parser.parse_args()
    metrics = run_matrix(
        arguments.config, arguments.corpus_dir, arguments.output_dir,
        development=arguments.development, fake_redis=arguments.fake_redis,
        development_scale=arguments.development_scale,
    )
    print(json.dumps(metrics["registered_checks"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
