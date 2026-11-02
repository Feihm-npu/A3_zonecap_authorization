from __future__ import annotations

"""One C5 repetition, and the per-run preflight, in a fresh process.

``repetition`` pins the worker, loads a verified corpus variant, builds the
reference PEP, runs the warm-up and measured loops, and writes raw samples,
decision records, and per-repetition metrics.  ``preflight`` runs the timer
sanity checks, the disabled-check detector, and negative controls 1-7.

The timer starts immediately before ``ReferencePEP.decide`` receives the
serialized envelope and stops when it returns after the audit enqueue.
Context publication, cache invalidation for ``cache_miss``, corpus iteration,
and all bookkeeping happen outside the timed region.
"""

import argparse
from array import array
import gc
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import shutil
import subprocess
import sys
import time
from typing import Any

import nacl

from . import audit as audit_queue
from .corpus import SCALE_ARCHITECTURE, load_variant, scale_policy_ids, verify
from .pep import (
    ALLOW,
    AUDIT,
    DEFER,
    DENY,
    FULL_MASK,
    REWRITE,
    SIGNATURE,
    STAGES,
    ContextSnapshot,
    ContextStore,
    LocalRevocationStore,
    PEPOptions,
    PipeAuditSink,
    ReferencePEP,
    RegisteredPolicy,
)
from .resp import RedisRevocationStore
from .wire import encode_envelope, split_envelope


REVOKED_PREFIX = "revoked:synthetic:"


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def nearest_rank(ordered: list[int], proportion: float) -> int:
    """Nearest-rank percentile on an already sorted list: ``ceil(p*N)``, one-indexed."""

    if not ordered:
        raise ValueError("percentile needs at least one value")
    if not 0 < proportion <= 1:
        raise ValueError("proportion must be in (0, 1]")
    return ordered[math.ceil(proportion * len(ordered)) - 1]


def distribution(values: list[int] | array) -> dict[str, Any]:
    ordered = sorted(values)
    median = nearest_rank(ordered, 0.50)
    deviations = sorted(abs(value - median) for value in ordered)
    return {
        "samples": len(ordered),
        "minimum_ns": ordered[0],
        "p50_ns": median,
        "p95_ns": nearest_rank(ordered, 0.95),
        "p99_ns": nearest_rank(ordered, 0.99),
        "p999_ns": nearest_rank(ordered, 0.999),
        "maximum_ns": ordered[-1],
        "mean_ns": sum(ordered) / len(ordered),
        "median_absolute_deviation_ns": nearest_rank(deviations, 0.50),
        "zero_or_negative_samples": sum(value <= 0 for value in ordered),
    }


def proc_status(field: str) -> str:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith(field + ":"):
            return line.partition(":")[2].strip()
    raise RuntimeError(f"{field} missing from /proc/self/status")


def rss_kib() -> dict[str, int]:
    return {
        "vm_rss_kib": int(proc_status("VmRSS").split()[0]),
        "vm_hwm_kib": int(proc_status("VmHWM").split()[0]),
    }


def pin(core: int) -> dict[str, Any]:
    available = set(os.sched_getaffinity(0))
    if core not in available:
        raise RuntimeError(f"requested CPU {core} is unavailable")
    os.sched_setaffinity(0, {core})
    observed = sorted(os.sched_getaffinity(0))
    allowed = proc_status("Cpus_allowed_list")
    return {
        "requested_core": core,
        "sched_getaffinity": observed,
        "proc_cpus_allowed_list": allowed,
        "verified": observed == [core] and allowed == str(core),
    }


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def cpu_state(core: int) -> dict[str, Any]:
    base = f"/sys/devices/system/cpu/cpu{core}/cpufreq/"
    return {
        name: _read(base + name)
        for name in (
            "scaling_governor",
            "scaling_cur_freq",
            "scaling_min_freq",
            "scaling_max_freq",
            "cpuinfo_cur_freq",
        )
    }


def environment(core: int) -> dict[str, Any]:
    import nacl.bindings

    sodium = Path(sys.modules["nacl._sodium"].__file__)
    cpu_model = None
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.lower().startswith(("model name", "cpu part", "hardware")):
            cpu_model = line.partition(":")[2].strip()
            break
    clock = time.get_clock_info("perf_counter")
    return {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "pynacl": nacl.__version__,
        "libsodium_binary": str(sodium),
        "libsodium_binary_sha256": sha256_file(sodium),
        "cpu_model": cpu_model,
        "online_cpus": os.cpu_count(),
        "load_average": os.getloadavg(),
        "benchmark_core_cpufreq": cpu_state(core),
        "gc_enabled": gc.isenabled(),
        "gc_thresholds": gc.get_threshold(),
        "clock": {
            "implementation": clock.implementation,
            "monotonic": clock.monotonic,
            "adjustable": clock.adjustable,
            "resolution_s": clock.resolution,
        },
        "byteorder": sys.byteorder,
        "nacl_bindings_module": nacl.bindings.__name__,
    }


def merged_configuration(config: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in config["configurations"] if item["name"] == name]
    if len(matches) != 1:
        raise KeyError(f"configuration {name!r} is not registered exactly once")
    merged = json.loads(json.dumps(config["defaults"]))
    for key, value in matches[0].items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def scaled_setting(
    config: dict[str, Any], name: str, run_role: str, development_scale: int
) -> dict[str, Any]:
    """Registered setting; a development dry run may divide the decision counts."""

    setting = merged_configuration(config, name)
    if development_scale != 1:
        if run_role != "development" or development_scale < 1:
            raise ValueError("only a development run may scale the decision counts")
        setting["warmup"] = int(setting["warmup"]) // development_scale
        setting["measured"] = int(setting["measured"]) // development_scale
    return setting


def load_registry(corpus_dir: Path, setting: dict[str, Any]) -> dict[str, RegisteredPolicy]:
    documents = json.loads((corpus_dir / "registry.json").read_text(encoding="utf-8"))
    selection = setting.get("registry", "main")
    if selection == "main":
        selected = [
            item for policy_id, item in documents.items()
            if not policy_id.startswith(SCALE_ARCHITECTURE + ":")
        ]
    elif selection == "scale":
        selected = [documents[policy_id] for policy_id in scale_policy_ids(int(setting["registry_size"]))]
    else:
        raise ValueError(f"unknown registry selection {selection!r}")
    return {
        item["policy_id"]: RegisteredPolicy(
            policy_id=item["policy_id"],
            issuer=item["issuer"],
            subject=item["subject"],
            source_zone=item["source_zone"],
            target_zone=item["target_zone"],
            conduits=frozenset(item["conduits"]),
            assets=frozenset(item["assets"]),
            actions=frozenset(item["actions"]),
            parameter=(item["parameter"][0], item["parameter"][1]),
            ticks=(item["ticks"][0], item["ticks"][1]),
            modes=frozenset(item["modes"]),
            sequence=tuple(item["required_sequence"]),
        )
        for item in selected
    }


def registry_digest(registry: dict[str, RegisteredPolicy]) -> str:
    serial = json.dumps(
        [
            [
                policy.policy_id, policy.issuer, policy.subject, policy.source_zone,
                policy.target_zone, sorted(policy.conduits), sorted(policy.assets),
                sorted(policy.actions), list(policy.parameter), list(policy.ticks),
                sorted(policy.modes), list(policy.sequence),
            ]
            for policy in sorted(registry.values(), key=lambda item: item.policy_id)
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


def revoked_identifiers(count: int) -> list[str]:
    return [f"{REVOKED_PREFIX}{index:06d}" for index in range(count)]


def build_revocation(setting: dict[str, Any]) -> Any:
    revocation = setting["revocation"]
    identifiers = revoked_identifiers(int(revocation["preloaded"]))
    if revocation["backend"] == "local":
        return LocalRevocationStore(identifiers)
    if revocation["backend"] == "redis":
        host = os.environ.get("ZONECAP_C5_REDIS_HOST", revocation.get("host", "127.0.0.1"))
        port = int(os.environ.get("ZONECAP_C5_REDIS_PORT", revocation.get("port", 6379)))
        store = RedisRevocationStore(host, port, timeout_s=int(revocation["timeout_ms"]) / 1000)
        store.load(identifiers)
        if store.size() != len(identifiers):
            raise RuntimeError("Redis revocation set size differs from the preload")
        return store
    raise ValueError(f"unknown revocation backend {revocation['backend']!r}")


def pep_options(setting: dict[str, Any], **overrides: Any) -> PEPOptions:
    values = dict(setting["pep"])
    values.update(overrides)
    if "disabled_stages" in values:
        values["disabled_stages"] = frozenset(values["disabled_stages"])
    return PEPOptions(**values)


def snapshot_for(step: dict[str, Any]) -> ContextSnapshot:
    context = step["context"]
    envelope = context["envelope"]
    return ContextSnapshot(
        tick=context["tick"],
        mode=context["mode"],
        history=tuple(context["history"]),
        complete=context["complete"],
        high_risk=context["high_risk"],
        envelope=None if envelope is None else (envelope[0], envelope[1]),
    )


def decision_matches(expected: list[Any], observed: tuple) -> bool:
    return (
        expected[0] == observed[0]
        and expected[1] == observed[1]
        and expected[2] == observed[2]
        and expected[3] == observed[3]
        and expected[4] == observed[4]
    )


def expected_mask(options: PEPOptions) -> int:
    return FULL_MASK & ~options.diagnostic_disabled_mask()


def _stage_names(mask: int) -> list[str]:
    return [name for name, bit in STAGES if mask & bit]


def _order(steps: list[dict[str, Any]], seed: int) -> list[int]:
    units: dict[int, list[int]] = {}
    for index, step in enumerate(steps):
        units.setdefault(step["unit"], []).append(index)
    unit_ids = sorted(units)
    random.Random(seed).shuffle(unit_ids)
    return [index for unit in unit_ids for index in units[unit]]


def _start_tegrastats(path: Path, core: int | None) -> subprocess.Popen | None:
    executable = shutil.which("tegrastats")
    if executable is None:
        return None
    handle = path.open("w", encoding="utf-8")

    def _affinity() -> None:
        if core is not None:
            os.sched_setaffinity(0, {core})

    return subprocess.Popen(
        [executable, "--interval", "1000"], stdout=handle, stderr=subprocess.STDOUT,
        preexec_fn=_affinity,
    )


# --------------------------------------------------------------------------
# Repetition
# --------------------------------------------------------------------------


def run_repetition(
    config: dict[str, Any],
    configuration: str,
    seed: int,
    corpus_dir: Path,
    output_dir: Path,
    run_role: str = "confirmatory",
    development_scale: int = 1,
) -> dict[str, Any]:
    setting = scaled_setting(config, configuration, run_role, development_scale)
    if setting.get("system", "zonecap") == "sint":
        return run_sint_repetition(
            config, configuration, seed, corpus_dir, output_dir, run_role, development_scale
        )
    output_dir.mkdir(parents=True, exist_ok=False)
    cores = config["cpu"]
    affinity = pin(cores["benchmark_core"])
    if not affinity["verified"]:
        raise RuntimeError(f"CPU affinity not observed: {affinity}")
    manifest = verify(corpus_dir)
    if manifest["fingerprint"] != config["corpus_fingerprint"]:
        raise RuntimeError("corpus fingerprint differs from the frozen configuration")

    memory = {"process_start": rss_kib()}
    envelopes, steps = load_variant(corpus_dir, setting["variant"])
    memory["after_corpus_load"] = rss_kib()
    anchors = {
        issuer: bytes.fromhex(key)
        for issuer, key in json.loads((corpus_dir / "anchors.json").read_text()).items()
    }
    registry = load_registry(corpus_dir, setting)
    revocation = build_revocation(setting)
    context = ContextStore()
    options = pep_options(setting)

    drain = None
    write_fd = None
    audit_log = output_dir / "audit.log"
    if options.audit_enabled:
        read_fd, write_fd, granted = audit_queue.open_queue(setting["audit_queue_bytes"])
        if granted < setting["audit_queue_bytes"]:
            raise RuntimeError(f"audit queue capacity {granted} below the registered size")
        drain = audit_queue.start_drain(read_fd, audit_log, cores.get("audit_core"))
        sink = PipeAuditSink(write_fd)
    else:
        granted = 0
        sink = None
    pep = ReferencePEP(
        anchors=anchors, registry=registry, revocation=revocation, context=context,
        audit=sink, options=options,
    )

    subjects = [step["subject"] for step in steps]
    keys = [(step["request"]["zd"], step["request"]["a"]) for step in steps]
    snapshots = [snapshot_for(step) for step in steps]
    sequence = _order(steps, seed)
    warmup = int(setting["warmup"])
    measured = int(setting["measured"])
    positions = [sequence[index % len(sequence)] for index in range(warmup + measured)]
    cache_miss = bool(setting.get("cache_miss", False))
    memory["after_pep_init"] = rss_kib()

    tegrastats = _start_tegrastats(output_dir / "tegrastats.log", cores.get("monitor_core"))
    environment_before = environment(cores["benchmark_core"])
    gc.collect()
    gc.freeze()
    frozen_objects = gc.get_freeze_count()

    publish = context.publish
    decide = pep.decide
    clear = pep.clear_verification_cache
    clock = time.perf_counter_ns
    for index in range(warmup):
        step = positions[index]
        publish(keys[step], snapshots[step])
        if cache_miss:
            clear()
        decide(subjects[step], envelopes[step])
    memory["after_warmup"] = rss_kib()

    samples = array("Q", bytes(8 * measured))
    observed: list[tuple] = [()] * measured
    loop_started = clock()
    for index in range(measured):
        step = positions[warmup + index]
        publish(keys[step], snapshots[step])
        if cache_miss:
            clear()
        started = clock()
        result = decide(subjects[step], envelopes[step])
        stopped = clock()
        samples[index] = stopped - started
        observed[index] = result
    loop_stopped = clock()
    memory["after_measured"] = rss_kib()
    environment_after = environment(cores["benchmark_core"])
    if tegrastats is not None:
        tegrastats.terminate()
        tegrastats.wait(timeout=10)
    gc.unfreeze()

    audit_summary = None
    if drain is not None:
        audit_summary = audit_queue.finish_drain(drain, write_fd, audit_log)
        summary_path = audit_log.with_suffix(".log.summary.json")
        summary_path.replace(output_dir / "audit_summary.json")
        if setting.get("retain_audit_log", False):
            with audit_log.open("rb") as source, gzip.GzipFile(
                output_dir / "audit.jsonl.gz", "wb", mtime=0
            ) as sink_file:
                shutil.copyfileobj(source, sink_file)
        audit_log.unlink()

    # ---- post-processing (outside every timed region) ----
    mask_expected = expected_mask(options)
    response_digest = hashlib.sha256()
    mismatches = []
    mask_failures = 0
    verification_failures = 0
    audit_denials = 0
    verified_total = 0
    hits_total = 0
    by_effect: dict[str, list[int]] = {}
    by_depth: dict[str, list[int]] = {}
    reasons: dict[str, int] = {}
    with gzip.GzipFile(output_dir / "decisions.jsonl.gz", "wb", mtime=0) as compressed, io.TextIOWrapper(
        compressed, encoding="utf-8"
    ) as records:
        for index, result in enumerate(observed):
            step_index = positions[warmup + index]
            step = steps[step_index]
            expected = step["expected"]
            ok = decision_matches(expected, result)
            mask_ok = result[6] == mask_expected
            chain = step["chain"]
            verified, hits = result[7], result[8]
            if not options.verify_signatures:
                verification_ok = verified == 0 and hits == 0
            elif cache_miss or not options.verification_cache:
                verification_ok = verified == chain and hits == 0
            else:
                verification_ok = verified + hits == chain
            verified_total += verified
            hits_total += hits
            mask_failures += not mask_ok
            verification_failures += not verification_ok
            audit_denials += result[5] == "audit_unavailable"
            reasons[result[5]] = reasons.get(result[5], 0) + 1
            response_digest.update(result[9])
            by_effect.setdefault(expected[0], []).append(samples[index])
            by_depth.setdefault(str(step["depth"]), []).append(samples[index])
            if not ok:
                mismatches.append(
                    {"measured_index": index, "step": step_index, "case": step["case"],
                     "kind": step["kind"], "expected": expected, "observed": list(result[:6])}
                )
            records.write(
                json.dumps(
                    [index, step_index, expected[0], list(result[:6]), result[6], verified, hits,
                     ok and mask_ok and verification_ok],
                    separators=(",", ":"),
                )
                + "\n"
            )

    raw = samples.tobytes() if sys.byteorder == "little" else _byteswapped(samples)
    (output_dir / "raw_samples_ns.bin.gz").write_bytes(gzip.compress(raw, mtime=0))

    stats = distribution(samples)
    scan_period_ns = int(setting["scan_period_us"]) * 1000
    wall_ns = loop_stopped - loop_started
    sum_ns = sum(samples)
    step_sequence_digest = hashlib.sha256(
        array("I", positions[warmup:]).tobytes()
    ).hexdigest()
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "configuration": configuration,
        "configuration_role": setting["role"],
        "run_role": run_role,
        "system": "zonecap",
        "seed": seed,
        "variant": setting["variant"],
        "warmup_decisions": warmup,
        "measured_decisions": measured,
        "development_scale": development_scale,
        "cache_miss": cache_miss,
        "pep_options": {
            "verify_signatures": options.verify_signatures,
            "verification_cache": options.verification_cache,
            "cache_capacity": options.cache_capacity,
            "audit_enabled": options.audit_enabled,
            "max_deferrals": options.max_deferrals,
            "max_context_age_ns": options.max_context_age_ns,
            "disabled_stages": sorted(options.disabled_stages),
        },
        "expected_stage_mask": mask_expected,
        "expected_stages": _stage_names(mask_expected),
        "registry_policies": len(registry),
        "registry_sha256": registry_digest(registry),
        "revocation_backend": setting["revocation"]["backend"],
        "revocation_entries": revocation.size(),
        "audit_queue_bytes": granted,
        "decision_latency_ns": stats,
        "latency_by_expected_effect_ns": {
            effect: _summary(values) for effect, values in sorted(by_effect.items())
        },
        "latency_by_chain_depth_ns": {
            depth: _summary(values) for depth, values in sorted(by_depth.items())
        },
        "p99_us": stats["p99_ns"] / 1000,
        "derived_p99_scan_occupancy_percent": stats["p99_ns"] / scan_period_ns * 100,
        "throughput_decisions_per_s_wall": measured / (wall_ns / 1e9),
        "throughput_decisions_per_s_decision_time": measured / (sum_ns / 1e9),
        "measured_loop_wall_ns": wall_ns,
        "memory_kib": memory,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "token_bytes_by_depth": manifest["token_bytes_by_depth"],
        "decision_mismatches": len(mismatches),
        "stage_mask_failures": mask_failures,
        "verification_count_failures": verification_failures,
        "signatures_verified": verified_total,
        "verification_cache_hits": hits_total,
        "audit_unavailable_denials": audit_denials,
        "decision_reason_counts": dict(sorted(reasons.items())),
        "revocation_reconnects": getattr(revocation, "reconnects", None),
        "audit_records": None if audit_summary is None else audit_summary["records"],
        "audit_records_expected": (warmup + measured) if options.audit_enabled else 0,
        "audit_peak_backlog_bytes": None if audit_summary is None else audit_summary["peak_backlog_bytes"],
        "response_sha256": response_digest.hexdigest(),
        "measured_step_sequence_sha256": step_sequence_digest,
        "gc_frozen_objects": frozen_objects,
        "affinity": affinity,
        "corpus_fingerprint": manifest["fingerprint"],
    }
    metrics["threshold_checks"] = {
        "p99_at_most_1000_us": stats["p99_ns"] <= int(setting["threshold_p99_us"]) * 1000,
        "derived_occupancy_at_most_10_percent": metrics["derived_p99_scan_occupancy_percent"]
        <= float(setting["threshold_occupancy_percent"]),
        "zero_decision_mismatches": not mismatches,
        "every_expected_stage_exercised": mask_failures == 0,
        "verification_counts_consistent": verification_failures == 0,
        "audit_complete": (not options.audit_enabled)
        or (audit_summary["records"] == warmup + measured and audit_denials == 0),
        "no_nonpositive_sample": stats["zero_or_negative_samples"] == 0,
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "environment.json", {"before": environment_before, "after": environment_after})
    with (output_dir / "decision_mismatches.jsonl").open("w", encoding="utf-8") as handle:
        for item in mismatches:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    return metrics


def _cpu_list(text: str) -> set[int]:
    cores: set[int] = set()
    for part in text.split(","):
        low, _, high = part.partition("-")
        cores.update(range(int(low), int(high or low) + 1))
    return cores


def dist_tree_sha256(directory: Path) -> str:
    """SHA-256 over the sorted ``path sha256`` lines of every built ``.js`` file."""

    lines = [
        f"{path.relative_to(directory).as_posix()} {sha256_file(path)}\n"
        for path in sorted(directory.rglob("*.js"))
    ]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _mutation_kind(case_id: str) -> str:
    return case_id.split(":mutation:", 1)[1] if ":mutation:" in case_id else "valid"


def run_sint_repetition(
    config: dict[str, Any],
    configuration: str,
    seed: int,
    corpus_dir: Path,
    output_dir: Path,
    run_role: str,
    development_scale: int = 1,
) -> dict[str, Any]:
    """Run the pinned-SINT Node runner on the same ordered common subset.

    The Node process receives the benchmark core plus the audit-drain core:
    the same two-core budget as ZoneCap's worker plus its audit drain, so V8's
    helper threads do not compete with the main thread on a single core.
    """

    setting = scaled_setting(config, configuration, run_role, development_scale)
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest = verify(corpus_dir)
    if manifest["fingerprint"] != config["corpus_fingerprint"]:
        raise RuntimeError("corpus fingerprint differs from the frozen configuration")
    sint = config["sint"]
    repo = Path(os.environ.get("ZONECAP_C5_SINT_REPO", sint["repo"])).resolve()
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], check=True,
                           capture_output=True, text=True).stdout.strip()
    if head != sint["commit"] or dirty:
        raise RuntimeError(f"SINT checkout is not the clean pinned commit: {head}")
    source_hashes = {relative: sha256_file(repo / relative) for relative in sint["source_hashes"]}
    if source_hashes != sint["source_hashes"]:
        raise RuntimeError("pinned SINT source hash mismatch")
    built = {relative: dist_tree_sha256(repo / relative) for relative in sint["built_dist_tree_sha256"]}
    if built != sint["built_dist_tree_sha256"]:
        raise RuntimeError(
            "SINT dist differs from the reference build; rebuild with the registered prepare_command"
        )

    _, steps = load_variant(corpus_dir, setting["variant"])
    warmup = int(setting["warmup"])
    measured = int(setting["measured"])
    sequence = _order(steps, seed)
    positions = [sequence[index % len(sequence)] for index in range(warmup + measured)]
    order_path = output_dir / "order.bin"
    order = array("I", positions)
    if sys.byteorder != "little":
        order.byteswap()
    order_path.write_bytes(order.tobytes())
    cores = config["cpu"]
    allowed_cores = {cores["benchmark_core"], cores["audit_core"]}

    def _pin() -> None:
        os.sched_setaffinity(0, allowed_cores)

    root = Path(__file__).resolve().parents[3]
    command = [
        shutil.which("node") or "node", str(root / "scripts" / "exp25_sint_runner.mjs"),
        "--sint-repo", str(repo), "--corpus-dir", str(corpus_dir), "--order", str(order_path),
        "--output-dir", str(output_dir), "--warmup", str(warmup), "--measured", str(measured),
        "--revoked", str(int(setting["revocation"]["preloaded"])),
    ]
    environment_before = environment(cores["benchmark_core"])
    tegrastats = _start_tegrastats(output_dir / "tegrastats.log", cores.get("monitor_core"))
    with (output_dir / "runner.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, preexec_fn=_pin)
        allowed = None
        for line in Path(f"/proc/{process.pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("Cpus_allowed_list:"):
                allowed = line.partition(":")[2].strip()
        if allowed is None or _cpu_list(allowed) != allowed_cores:
            process.kill()
            process.wait()
            raise RuntimeError(f"SINT runner affinity not observed: {allowed}")
        returncode = process.wait()
    if tegrastats is not None:
        tegrastats.terminate()
        tegrastats.wait(timeout=10)
    environment_after = environment(cores["benchmark_core"])
    if returncode != 0:
        raise RuntimeError(f"SINT runner exited with {returncode}")
    child_peak_rss_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    order_path.unlink()

    samples = array("Q")
    samples.frombytes(gzip.decompress((output_dir / "raw_samples_ns.bin.gz").read_bytes()))
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != measured:
        raise AssertionError(f"SINT runner returned {len(samples)} samples, expected {measured}")
    meta = json.loads((output_dir / "sint_meta.json").read_text(encoding="utf-8"))
    expected_reasons = sint["expected_reasons"]
    mismatches = []
    by_effect: dict[str, list[int]] = {}
    reasons: dict[str, int] = {}
    records = 0
    with gzip.open(output_dir / "sint_decisions.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            index, step_index, action, reason = json.loads(line)
            records += 1
            if index != records - 1 or step_index != positions[warmup + index]:
                raise AssertionError("SINT runner did not follow the registered order")
            step = steps[step_index]
            expected_reason = expected_reasons[_mutation_kind(step["case"])]
            by_effect.setdefault(step["sint_expected"], []).append(samples[index])
            reasons[str(reason)] = reasons.get(str(reason), 0) + 1
            if action != step["sint_expected"] or reason != expected_reason:
                mismatches.append(
                    {"measured_index": index, "step": step_index, "case": step["case"],
                     "expected": [step["sint_expected"], expected_reason],
                     "observed": [action, reason]}
                )
    if records != measured:
        raise AssertionError(f"SINT runner returned {records} decisions, expected {measured}")
    stats = distribution(samples)
    scan_period_ns = int(setting["scan_period_us"]) * 1000
    affinity_ok = _cpu_list(allowed) == allowed_cores
    metrics = {
        "exp": config["exp"],
        "claim": config["claim"],
        "configuration": configuration,
        "configuration_role": setting["role"],
        "run_role": run_role,
        "system": "sint",
        "seed": seed,
        "variant": setting["variant"],
        "warmup_decisions": warmup,
        "measured_decisions": measured,
        "development_scale": development_scale,
        "sint_commit": head,
        "sint_source_hashes": source_hashes,
        "sint_built_dist_tree_sha256": built,
        "sint_meta": meta,
        "decision_latency_ns": stats,
        "latency_by_expected_effect_ns": {
            effect: _summary(values) for effect, values in sorted(by_effect.items())
        },
        "latency_by_chain_depth_ns": {},
        "decision_reason_counts": dict(sorted(reasons.items())),
        "p99_us": stats["p99_ns"] / 1000,
        "derived_p99_scan_occupancy_percent": stats["p99_ns"] / scan_period_ns * 100,
        "throughput_decisions_per_s_wall": measured / (meta["measured_loop_wall_ns"] / 1e9),
        "throughput_decisions_per_s_decision_time": measured / (sum(samples) / 1e9),
        "peak_rss_kib": child_peak_rss_kib,
        "decision_mismatches": len(mismatches),
        "stage_mask_failures": 0,
        "verification_count_failures": 0,
        "signatures_verified": None,
        "verification_cache_hits": None,
        "audit_records": None,
        "affinity": {"requested_cores": sorted(allowed_cores), "proc_cpus_allowed_list": allowed,
                     "verified": affinity_ok},
        "measured_step_sequence_sha256": hashlib.sha256(
            array("I", positions[warmup:]).tobytes()
        ).hexdigest(),
        "corpus_fingerprint": manifest["fingerprint"],
    }
    metrics["threshold_checks"] = {
        "zero_decision_mismatches": not mismatches,
        "affinity_verified": affinity_ok,
        "no_nonpositive_sample": stats["zero_or_negative_samples"] == 0,
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "environment.json", {"before": environment_before, "after": environment_after})
    with (output_dir / "decision_mismatches.jsonl").open("w", encoding="utf-8") as handle:
        for item in mismatches:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    return metrics


def _summary(values: list[int]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "samples": len(ordered),
        "p50_ns": nearest_rank(ordered, 0.50),
        "p99_ns": nearest_rank(ordered, 0.99),
        "maximum_ns": ordered[-1],
    }


def _byteswapped(samples: array) -> bytes:
    copy = array("Q", samples)
    copy.byteswap()
    return copy.tobytes()


# --------------------------------------------------------------------------
# Preflight: timer sanity, disabled-check detector, negative controls
# --------------------------------------------------------------------------


def _timer_deltas(pairs: int) -> tuple[list[int], int]:
    clock = time.perf_counter_ns
    deltas = []
    backwards = 0
    for _ in range(pairs):
        before = clock()
        after = clock()
        delta = after - before
        backwards += delta < 0
        if delta > 0:
            deltas.append(delta)
    return deltas, backwards


def _time_calls(call: Any, *, warmup: int, samples: int) -> list[int]:
    clock = time.perf_counter_ns
    for _ in range(warmup):
        call()
    values = []
    for _ in range(samples):
        started = clock()
        call()
        values.append(clock() - started)
    return values


class _ListSink:
    def __init__(self) -> None:
        self.records: list[bytes] = []

    def enqueue(self, record: bytes) -> bool:
        self.records.append(record)
        return True


def run_preflight(
    config: dict[str, Any], corpus_dir: Path, output_dir: Path
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    preflight = config["preflight"]
    first = config["configurations"][0]["name"]
    setting = merged_configuration(config, first)
    affinity = pin(config["cpu"]["benchmark_core"])
    manifest = verify(corpus_dir)
    fingerprint_ok = manifest["fingerprint"] == config["corpus_fingerprint"]
    envelopes, steps = load_variant(corpus_dir, "main")
    anchors = {
        issuer: bytes.fromhex(key)
        for issuer, key in json.loads((corpus_dir / "anchors.json").read_text()).items()
    }
    registry = load_registry(corpus_dir, {"registry": "main"})

    def make_pep(sink: Any = None, **overrides: Any) -> tuple[ReferencePEP, ContextStore, LocalRevocationStore]:
        store = ContextStore()
        revocation = LocalRevocationStore(revoked_identifiers(1000))
        pep = ReferencePEP(
            anchors=anchors, registry=registry, revocation=revocation, context=store,
            audit=sink if sink is not None else _ListSink(),
            options=pep_options({"pep": {**setting["pep"], **overrides}}),
        )
        return pep, store, revocation

    # The registered audit-queue capacity must be grantable on this host.
    queue_read, queue_write, queue_granted = audit_queue.open_queue(setting["audit_queue_bytes"])
    os.close(queue_read)
    os.close(queue_write)

    # Representative step: a depth-2 valid ALLOW case exercises every stage.
    probe_index = next(
        index for index, step in enumerate(steps)
        if step["kind"] == "single" and step["depth"] == 2 and step["expected"][0] == ALLOW
    )
    probe = steps[probe_index]
    probe_key = (probe["request"]["zd"], probe["request"]["a"])
    probe_snapshot = snapshot_for(probe)

    # Timer sanity.
    deltas, backwards = _timer_deltas(int(preflight["timer_pairs"]))
    timer = distribution(deltas)
    empty = distribution(
        _time_calls(lambda: None, warmup=preflight["warmup"], samples=preflight["empty_samples"])
    )
    full_pep, full_store, _ = make_pep()
    full_store.publish(probe_key, probe_snapshot)
    full = distribution(
        _time_calls(
            lambda: full_pep.decide(probe["subject"], envelopes[probe_index]),
            warmup=preflight["warmup"],
            samples=preflight["full_samples"],
        )
    )
    slow_pep, slow_store, _ = make_pep(forced_delay_ns=int(preflight["forced_delay_ns"]))

    def slow_call() -> None:
        slow_store.publish(probe_key, probe_snapshot)
        slow_pep.decide(probe["subject"], envelopes[probe_index])

    slow = distribution(
        _time_calls(slow_call, warmup=preflight["forced_slow_warmup"], samples=preflight["forced_slow_samples"])
    )
    timer_checks = {
        "affinity_verified": affinity["verified"],
        "clock_monotonic": time.get_clock_info("perf_counter").monotonic,
        "no_backwards_clock": backwards == 0,
        "resolution_below_empty_p50": timer["minimum_ns"] < empty["p50_ns"],
        "full_slower_than_empty": empty["p50_ns"] < full["p50_ns"] and empty["p99_ns"] < full["p99_ns"],
        "forced_slow_detected": slow["minimum_ns"] >= int(preflight["forced_slow_minimum_ns"]),
        "forced_slow_slowest": full["p99_ns"] < slow["p50_ns"],
        "corpus_fingerprint": fingerprint_ok,
        "registered_audit_queue_granted": queue_granted >= int(setting["audit_queue_bytes"]),
    }
    timer_result = {
        "affinity": affinity,
        "timer_pairs": int(preflight["timer_pairs"]),
        "timer_delta_ns": timer,
        "timer_backwards_transitions": backwards,
        "empty_call_ns": empty,
        "full_probe_ns": full,
        "forced_slow_ns": slow,
        "checks": timer_checks,
    }

    # Disabled-check detector: each single-stage mutant must expose its missing bit.
    detector_records = []
    for name, bit in STAGES:
        pep, store, _ = make_pep(disabled_stages=[name])
        store.publish(probe_key, probe_snapshot)
        result = pep.decide(probe["subject"], envelopes[probe_index])
        missing = [stage for stage, stage_bit in STAGES if not result[6] & stage_bit]
        detector_records.append(
            {"disabled_stage": name, "missing_stages": missing, "detected": missing == [name]}
        )
    pep, store, _ = make_pep()
    store.publish(probe_key, probe_snapshot)
    baseline = pep.decide(probe["subject"], envelopes[probe_index])
    activation = {
        "probe_step": probe_index,
        "probe_case": probe["case"],
        "full_mask": baseline[6],
        "full_stages": _stage_names(baseline[6]),
        "full_missing_stages": [stage for stage, bit in STAGES if not baseline[6] & bit],
        "mutants": len(detector_records),
        "mutants_killed": sum(record["detected"] for record in detector_records),
        "records": detector_records,
    }

    # Negative controls 2-7 against the full path.
    controls = []

    def control(name: str, expected: str, result: tuple, extra: bool = True) -> None:
        passed = result[0] == expected and extra
        controls.append(
            {"control": name, "expected_effect": expected, "observed": list(result[:6]),
             "stage_mask": result[6], "passed": passed}
        )

    pep, store, revocation = make_pep()
    store.publish(probe_key, probe_snapshot)
    tokens, request_bytes = split_envelope(envelopes[probe_index])
    leaf_payload, leaf_signature = tokens[-1]
    tokens[-1] = (leaf_payload, bytes([leaf_signature[0] ^ 0x01]) + leaf_signature[1:])
    result = pep.decide(probe["subject"], encode_envelope(tokens, request_bytes))
    control("invalid_signature", DENY, result, result[5] == "bad_signature" and result[1] is None)

    pep, store, revocation = make_pep()
    store.publish(probe_key, probe_snapshot)
    middle = probe["leaf"].rsplit(":", 1)[0] + ":d1"
    revocation.revoke(middle)
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("revoked_token", DENY, result, result[5] == "revoked" and result[1] is None)

    rewrite_index = next(
        index for index, step in enumerate(steps)
        if step["kind"] == "single" and step["depth"] == 2 and step["expected"][0] == REWRITE
    )
    rewrite_step = steps[rewrite_index]
    pep, store, _ = make_pep()
    store.publish((rewrite_step["request"]["zd"], rewrite_step["request"]["a"]), snapshot_for(rewrite_step))
    result = pep.decide(rewrite_step["subject"], envelopes[rewrite_index])
    leaf_scope = json.loads((corpus_dir / "scopes.json").read_text())[rewrite_step["leaf"]]
    control(
        "out_of_scope_parameter", REWRITE, result,
        result[2] is not None and leaf_scope["parameter"][0] <= result[2] <= leaf_scope["parameter"][1],
    )
    action_index = next(
        index for index, step in enumerate(steps)
        if step["case"].endswith(":mutation:action") and step["depth"] == 2
    )
    action_step = steps[action_index]
    pep, store, _ = make_pep()
    store.publish((action_step["request"]["zd"], action_step["request"]["a"]), snapshot_for(action_step))
    result = pep.decide(action_step["subject"], envelopes[action_index])
    control("out_of_scope_action", DENY, result, result[1] is None)

    pep, store, _ = make_pep()
    stale_age = int(setting["pep"]["max_context_age_ns"]) * 2
    store.publish(probe_key, probe_snapshot, published_ns=time.monotonic_ns() - stale_age)
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("stale_context", DEFER, result, result[1] == "read" and result[5] == "context_unavailable")
    pep, store, _ = make_pep()
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("missing_context", DEFER, result, result[1] == "read" and result[5] == "context_unavailable")
    pep, store, _ = make_pep()
    store.publish(
        probe_key,
        ContextSnapshot(tick=probe_snapshot.tick, mode=probe_snapshot.mode,
                        history=probe_snapshot.history, high_risk=True),
    )
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("high_risk_context", DEFER, result, result[1] == "read" and result[5] == "high_risk")
    pep, store, _ = make_pep()
    store.publish(probe_key, probe_snapshot, published_ns=time.monotonic_ns() - stale_age)
    result = pep.decide("subject:not-the-holder", envelopes[probe_index])
    holder = pep.decide(probe["subject"], envelopes[probe_index])
    control(
        "non_holder_presenter", DENY, result,
        result[5] == "subject" and result[1] is None and holder[0] == DEFER and pep.deferrals == {probe["subject"]: 1},
    )

    read_fd, write_fd, _ = audit_queue.open_queue(65536)
    filler = b"x" * 4095 + b"\n"
    os.set_blocking(write_fd, False)
    while True:
        try:
            os.write(write_fd, filler)
        except BlockingIOError:
            break
    pep, store, _ = make_pep(sink=PipeAuditSink(write_fd))
    store.publish(probe_key, probe_snapshot)
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("audit_queue_full", DENY, result, result[5] == "audit_unavailable" and result[1] is None and not result[6] & AUDIT)
    os.close(read_fd)
    pep, store, _ = make_pep(sink=PipeAuditSink(write_fd))
    store.publish(probe_key, probe_snapshot)
    result = pep.decide(probe["subject"], envelopes[probe_index])
    control("audit_queue_closed", DENY, result, result[5] == "audit_unavailable" and result[1] is None)
    os.close(write_fd)

    sample = list(range(min(200, len(steps))))
    wrong = [list(steps[index]["expected"]) for index in sample]
    wrong[0] = ["allow" if wrong[0][0] != "allow" else "deny", None, None, None, None]
    pep, store, _ = make_pep()
    detected = 0
    for index, expected in zip(sample, wrong):
        step = steps[index]
        store.publish((step["request"]["zd"], step["request"]["a"]), snapshot_for(step))
        detected += not decision_matches(expected, pep.decide(step["subject"], envelopes[index]))
    controls.append(
        {"control": "wrong_oracle_decision", "expected_mismatches": 1,
         "observed_mismatches": detected, "passed": detected == 1}
    )

    result = {
        "timer_sanity": timer_result,
        "check_activation": activation,
        "negative_controls": controls,
        "passed": all(timer_checks.values())
        and activation["mutants_killed"] == activation["mutants"]
        and not activation["full_missing_stages"]
        and all(item["passed"] for item in controls),
        "environment": environment(config["cpu"]["benchmark_core"]),
    }
    write_json(output_dir / "timer_sanity.json", timer_result)
    write_json(output_dir / "check_activation.json", activation)
    write_json(output_dir / "negative_controls.json", controls)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="One C5 repetition or preflight in a fresh process.")
    sub = parser.add_subparsers(dest="command", required=True)
    repetition = sub.add_parser("repetition")
    repetition.add_argument("--config", type=Path, required=True)
    repetition.add_argument("--configuration", required=True)
    repetition.add_argument("--seed", type=int, required=True)
    repetition.add_argument("--corpus-dir", type=Path, required=True)
    repetition.add_argument("--output-dir", type=Path, required=True)
    repetition.add_argument("--run-role", choices=("confirmatory", "development"), required=True)
    repetition.add_argument("--development-scale", type=int, default=1)
    pre = sub.add_parser("preflight")
    pre.add_argument("--config", type=Path, required=True)
    pre.add_argument("--corpus-dir", type=Path, required=True)
    pre.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    config = json.loads(arguments.config.read_text(encoding="utf-8"))
    if arguments.command == "repetition":
        metrics = run_repetition(
            config, arguments.configuration, arguments.seed,
            arguments.corpus_dir.resolve(), arguments.output_dir.resolve(), arguments.run_role,
            arguments.development_scale,
        )
        print(json.dumps({"configuration": arguments.configuration, "seed": arguments.seed,
                          "p99_us": metrics["p99_us"], "checks": metrics["threshold_checks"]}))
    else:
        result = run_preflight(config, arguments.corpus_dir.resolve(), arguments.output_dir.resolve())
        print(json.dumps({"passed": result["passed"]}))
        if not result["passed"]:
            sys.exit(3)


if __name__ == "__main__":
    main()
