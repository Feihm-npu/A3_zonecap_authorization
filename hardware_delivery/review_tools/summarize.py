#!/usr/bin/env python3
"""Summarise an ``observer_check.sh`` run against fakeplc's exactly periodic heartbeat.

Because fakeplc's tick ``n`` happens at exactly ``t0 + n * period``, every late tick
in the rows below is produced by the observer, and the true scan phase of every
command is ``(t_send - t0) mod period``.  The scan-period rows reuse the
statistics ``client.py`` itself computed (its percentile convention, not
nearest-rank); the phase-error and observer-lag rows use nearest-rank.

The reference-observer rows come from ``reference_observer.py``, which
``observer_check.sh`` runs as a separate process alongside every mode.
``--observer-log`` checks any other replacement observer the same way: give it
the observer's raw ``t_ns heartbeat`` pairs (one per line, space or comma
separated, optionally gzip) recorded with ``time.perf_counter_ns`` against the
same fakeplc session.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

LATE_NS = 12_000_000
RANDOM_GUESS_MS = {"p50": 2.5, "p90": 4.5, "p99": 4.95}  # |circular error| ~ U(0, period/2)


def nearest_rank(values: list[float], p: float) -> float:
    return values[max(0, math.ceil(p * len(values)) - 1)]


def read_fakeplc(out_dir: Path) -> tuple[int, int]:
    words = (out_dir / "fakeplc.log").read_text(encoding="utf-8").split()
    return int(words[words.index("t0_ns") + 1]), int(words[words.index("period_ns") + 1])


def scan_row(stats: dict) -> dict:
    observed, gaps = stats["observed_scans"], stats["observation_gaps"]
    period = stats["scan_period_ns"]
    return {
        "observed_scans": observed,
        "late_ticks_pct": round(100 * stats["late_ticks_over_12ms"] / observed, 2) if observed else None,
        "observation_gaps_pct": round(100 * gaps / (observed + gaps), 2) if observed + gaps else None,
        **{f"{key}_ms": round(period[key] / 1e6, 2) for key in ("p50", "p99", "min", "max", "mean")},
    }


def phase_row(records: list[dict], t0: int, period: int) -> dict:
    errors = []
    histogram = [0] * 10
    for record in records:
        true = (record["t_send"] - t0) % period
        logged = round(record["phase_us"] * 1_000) % period
        errors.append(abs((logged - true + period // 2) % period - period // 2))
        histogram[true * 10 // period] += 1
    errors.sort()
    return {
        "commands": len(records),
        **{f"error_{name}_ms": round(nearest_rank(errors, p) / 1e6, 2)
           for name, p in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99))},
        "error_max_ms": round(errors[-1] / 1e6, 2),
        "true_phase_histogram_1ms": histogram,
    }


def observer_row(path: Path, t0: int, period: int) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    lags, deltas = [], []
    last_value = last_time = None
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            fields = line.replace(",", " ").split()
            if len(fields) < 2:
                continue
            now, value = int(fields[0]), int(fields[1]) & 0xFFFF
            if value == last_value:
                continue
            ticks = (now - t0) // period
            tick = ticks - ((ticks - value) % 0x10000)
            lags.append(now - (t0 + tick * period))
            if last_value is not None and (value - last_value) & 0xFFFF == 1:
                deltas.append(now - last_time)
            last_value, last_time = value, now
    lags.sort()
    return {
        "boundaries": len(lags),
        **{f"lag_{name}_ms": round(nearest_rank(lags, p) / 1e6, 3) for name, p in (("p50", 0.5), ("p99", 0.99))},
        "lag_max_ms": round(lags[-1] / 1e6, 3),
        "late_ticks_pct": round(100 * sum(d > LATE_NS for d in deltas) / len(deltas), 2) if deltas else None,
    }


def load_records(path: Path) -> list[dict]:
    if not path.exists():  # an archived run keeps the records gzip-compressed
        path = path.with_name(path.name + ".gz")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise an observer check against fakeplc")
    parser.add_argument("out_dir")
    parser.add_argument("--observer-log", default=None)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    t0, period = read_fakeplc(out_dir)

    summary: dict = {"fakeplc_t0_ns": t0, "period_ns": period, "scan": {}, "phase": {}, "sanity": {}}
    summary["scan"]["idle"] = scan_row(json.loads((out_dir / "idle.json").read_text(encoding="utf-8")))
    for mode in ("bypass", "instrumented"):
        stats = json.loads((out_dir / f"{mode}.jsonl.scan_stats.json").read_text(encoding="utf-8"))
        summary["scan"][mode] = scan_row(stats)
        records = load_records(out_dir / f"{mode}.jsonl")
        summary["phase"][mode] = phase_row(records, t0, period)
        sanity = {"commands": len(records), "ack_timeouts": sum(r.get("ack_timeout", 0) for r in records),
                  "emitted": sum(r.get("emitted", 0) for r in records)}
        if mode == "instrumented":
            sanity["effect_mismatches"] = sum(r["effect"] != r["expected_effect"] for r in records)
        summary["sanity"][mode] = sanity
    summary["reference_observer"] = {}
    for mode in ("idle", "bypass", "instrumented"):
        log = out_dir / f"{mode}.observer.txt"
        if not log.exists():
            log = log.with_name(log.name + ".gz")
        if log.exists():
            summary["reference_observer"][mode] = observer_row(log, t0, period)
    if args.observer_log:
        summary["observer"] = observer_row(Path(args.observer_log), t0, period)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Scan-period statistics reported by the observer (fakeplc is exactly periodic):\n")
    print("| mode | late ticks >12 ms | observation gaps | p50 | p99 | min | max | mean |")
    print("|---|---|---|---|---|---|---|---|")
    for mode, row in summary["scan"].items():
        print(f"| {mode} | {row['late_ticks_pct']}% | {row['observation_gaps_pct']}% | {row['p50_ms']} ms | "
              f"{row['p99_ms']} ms | {row['min_ms']} ms | {row['max_ms']} ms | {row['mean_ms']} ms |")
    print("\nLogged phase_us against the true scan phase (nearest-rank):\n")
    print("| mode | error p50 | p90 | p99 | max | true phase, 1 ms bins |")
    print("|---|---|---|---|---|---|")
    for mode, row in summary["phase"].items():
        print(f"| {mode} | {row['error_p50_ms']} ms | {row['error_p90_ms']} ms | {row['error_p99_ms']} ms | "
              f"{row['error_max_ms']} ms | {row['true_phase_histogram_1ms']} |")
    guess = RANDOM_GUESS_MS
    print(f"| random guess | {guess['p50']} ms | {guess['p90']} ms | {guess['p99']} ms | 5.0 ms | |")
    if summary["reference_observer"]:
        print("\nSeparate-process reference observer under the same load (nearest-rank):\n")
        print("| mode | boundaries | late ticks >12 ms | lag p50 | lag p99 | lag max |")
        print("|---|---|---|---|---|---|")
        for mode, row in summary["reference_observer"].items():
            print(f"| {mode} | {row['boundaries']} | {row['late_ticks_pct']}% | {row['lag_p50_ms']} ms | "
                  f"{row['lag_p99_ms']} ms | {row['lag_max_ms']} ms |")
    print("\nSanity:", json.dumps(summary["sanity"]))
    if "observer" in summary:
        print("Replacement observer:", json.dumps(summary["observer"]))


if __name__ == "__main__":
    main()
