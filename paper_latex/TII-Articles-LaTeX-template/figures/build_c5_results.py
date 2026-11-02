#!/usr/bin/env python3
"""Build the conditional C5 hardware displays and number macros.

Run only after exp-22--25 have returned and passed the research audit:

    python build_c5_results.py --exp22 results/exp22_c5_main_<date> \
        --exp23 results/exp23_c5_ablation_<date> --exp24 results/exp24_c5_scaling_<date> \
        --exp25 results/exp25_c5_baselines_<date> --testbed c5_testbed.json [--e2e e2e.json]

(``c5_testbed.json`` is filled from ``c5_testbed.template.json`` during the audit.)

Every number quoted in Section VII-D comes from the macros written here, and
every macro is computed from the returned result directories.  The script
refuses development runs.  ``--preview DIR`` lifts that refusal for dry runs of
the pipeline only: outputs go to DIR, carry a watermark, and must never be
copied into the manuscript.

The outcome case follows the decision rules registered in
``hardware_delivery/exp_requirements.md`` v1.1, Sections 1.2--1.4:

0. C5 thresholds met in every repetition; A1 and A2 ruled out;
1. thresholds met, A1 not ruled out (holds only with a warm verification cache);
2. thresholds met, A2 not ruled out (holds only up to a smaller policy count);
3. thresholds met, neither A1 nor A2 ruled out;
4. C5 refuted (any exp-22 repetition fails any registered check, or preflight fails).

The case is mechanical.  Acceptance of the claim remains with the S3 review
and the human; the generated text is a draft for that review.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from array import array
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from build_result_figures import COLORS, place_panel_labels

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from zonecap.c5.harness import distribution  # noqa: E402  (frozen percentile code)

FIGURE_DIR = Path(__file__).resolve().parent
THRESHOLD_US = 1000.0
SCAN_PERIOD_US = 10_000.0
POLICY_COUNTS = (1, 10, 100, 1000)
DEPTHS = (0, 1, 2)
CASE_NAMES = ("supported", "warm-cache only", "policy-count limited",
              "warm-cache only and policy-count limited", "refuted")


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_samples(path: Path) -> array:
    samples = array("Q")
    samples.frombytes(gzip.decompress(path.read_bytes()))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def audit_run(run_dir: Path, exp: str, *, allow_development: bool) -> dict:
    """Check one returned matrix directory before any number is used."""

    metrics = load(run_dir / "metrics.json")
    if metrics["exp"] != exp:
        raise AuditError(f"{run_dir}: expected {exp}, found {metrics['exp']}")
    if metrics["run_role"] != "confirmatory" and not allow_development:
        raise AuditError(f"{run_dir}: run_role {metrics['run_role']} cannot support C5")
    if not metrics["preflight"]["passed"]:
        raise AuditError(f"{run_dir}: preflight did not pass")
    manifest = load(run_dir / "manifest.json")
    for relative, expected in manifest["outputs"].items():
        if sha256(run_dir / relative) != expected:
            raise AuditError(f"{run_dir}: manifest hash mismatch for {relative}")
    config = load(run_dir / "config.json")
    registered = load(ROOT / "configs" / "c5" / f"{exp.replace('-', '')}_{config_name(exp)}.json")
    if config["frozen_hashes"] != registered["frozen_hashes"]:
        raise AuditError(f"{run_dir}: frozen hashes differ from configs/c5")
    if config["corpus_fingerprint"] != registered["corpus_fingerprint"]:
        raise AuditError(f"{run_dir}: corpus fingerprint differs from configs/c5")
    for name, item in metrics["configurations"].items():
        for seed in metrics["seeds"]:
            directory = run_dir / "configurations" / name / "repetitions" / str(seed)
            stored = load(directory / "metrics.json")
            if distribution(raw_samples(directory / "raw_samples_ns.bin.gz")) != stored["decision_latency_ns"]:
                raise AuditError(f"{directory}: raw samples do not reproduce the stored metrics")
            if stored["run_role"] != metrics["run_role"]:
                raise AuditError(f"{directory}: repetition role differs from the run role")
    metrics["_dir"] = run_dir
    return metrics


def config_name(exp: str) -> str:
    return {"exp-22": "c5_main", "exp-23": "c5_ablation", "exp-24": "c5_scaling",
            "exp-25": "c5_baselines"}[exp]


def repetitions(run: dict, configuration: str) -> list[tuple[int, dict]]:
    rows = []
    for seed in run["seeds"]:
        directory = run["_dir"] / "configurations" / configuration / "repetitions" / str(seed)
        rows.append((seed, load(directory / "metrics.json")))
    return rows


def pooled(run: dict, configuration: str) -> np.ndarray:
    parts = []
    for seed in run["seeds"]:
        directory = run["_dir"] / "configurations" / configuration / "repetitions" / str(seed)
        parts.append(np.frombuffer(raw_samples(directory / "raw_samples_ns.bin.gz").tobytes(), dtype="<u8"))
    return np.concatenate(parts)


def all_checks(run: dict, configuration: str) -> bool:
    return all(run["configurations"][configuration]["every_repetition_passes"].values())


def us(ns: float) -> float:
    return ns / 1000.0


def fmt_us(value_us: float) -> str:
    return f"{value_us:,.0f}" if value_us >= 100 else f"{value_us:.1f}"


def fmt_ms(value_us: float) -> str:
    return f"{value_us / 1000:.2f}"


def fmt_signed_us(value_us: float) -> str:
    sign = "+" if value_us >= 0 else "$-$"
    return sign + fmt_us(abs(value_us))


def outcome_case(exp22: dict, exp23: dict, exp24: dict) -> tuple[int, list[str]]:
    reasons = []
    c5 = exp22["registered_checks"]["C5_registered_thresholds"]["all_repetitions_meet_checks"]
    if not c5:
        failing = exp22["configurations"]["full"]["every_repetition_passes"]
        reasons = [name for name, passed in failing.items() if not passed]
        return 4, reasons
    a1 = exp23["registered_checks"]["A1_excluded_by_cache_miss"]["all_repetitions_meet_checks"]
    a2 = exp24["registered_checks"]["A2_excluded_at_1000_policies"]["all_repetitions_meet_checks"]
    if a1 and a2:
        return 0, reasons
    if not a1 and a2:
        return 1, reasons
    if a1 and not a2:
        return 2, reasons
    return 3, reasons


def largest_passing_policy_count(exp24: dict) -> int | None:
    largest = None
    for count in POLICY_COUNTS:
        if all(all_checks(exp24, f"p{count}_d{depth}") for depth in DEPTHS):
            largest = count
        else:
            break
    return largest


def macros(values: dict[str, str], case: int, watermark: bool) -> str:
    lines = [
        "% Generated by figures/build_c5_results.py from audited result directories.",
        "% Do not edit by hand; regenerate after any change to the inputs.",
        f"\\def\\cfiveoutcomecase{{{case}}}",
    ]
    if watermark:
        lines.append("% DEVELOPMENT PREVIEW -- NOT EVIDENCE")
    for key, value in sorted(values.items()):
        lines.append(f"\\expandafter\\def\\csname cfive@{key}\\endcsname{{{value}}}")
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> None:
    preview = args.preview is not None
    out_dir = Path(args.preview) if preview else FIGURE_DIR / "generated"
    source_dir = out_dir / "source_data" if preview else FIGURE_DIR / "source_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    exp22 = audit_run(ROOT / args.exp22, "exp-22", allow_development=preview)
    exp23 = audit_run(ROOT / args.exp23, "exp-23", allow_development=preview)
    exp24 = audit_run(ROOT / args.exp24, "exp-24", allow_development=preview)
    exp25 = audit_run(ROOT / args.exp25, "exp-25", allow_development=preview)
    testbed = load(Path(args.testbed))
    case, failing_checks = outcome_case(exp22, exp23, exp24)

    full = repetitions(exp22, "full")
    worst_seed, worst = max(full, key=lambda item: item[1]["decision_latency_ns"]["p99_ns"])
    full_pool = distribution(pooled(exp22, "full").tolist())
    cache_miss = repetitions(exp23, "cache_miss")
    cache_worst = max(item[1]["decision_latency_ns"]["p99_ns"] for item in cache_miss)
    cold = exp23["configurations"]["cold_start"]["worst_repetition"]["p99_ns"]
    unsigned_pool = exp23["configurations"]["unsigned"]["pooled_decision_latency_ns"]
    audit_off_pool = exp23["configurations"]["audit_disabled"]["pooled_decision_latency_ns"]
    remote_worst = exp23["configurations"]["remote_revocation"]["worst_repetition"]["p99_ns"]
    propagation = exp23["revocation_propagation"]["issuance_to_visibility_ns"]
    timer = load(exp22["_dir"] / "timer_sanity.json")
    controls = load(exp22["_dir"] / "negative_controls.json")
    scaling = {
        (count, depth): exp24["configurations"][f"p{count}_d{depth}"]["worst_repetition"]["p99_ns"]
        for count in POLICY_COUNTS for depth in DEPTHS
    }
    scaling_miss = {
        depth: exp24["configurations"][f"p1000_d{depth}_cache_miss"]["worst_repetition"]["p99_ns"]
        for depth in DEPTHS
    }
    baselines = {
        name: exp25["configurations"][name] for name in ("zonecap_full", "zonecap_cache_miss", "sint")
    }
    speedup = exp25["speedup_bug_signal"]["comparisons"]
    policy_limit = largest_passing_policy_count(exp24)

    values = {
        "module": testbed["module"],
        "jetpack": testbed["jetpack"],
        "powermode": testbed["power_mode"],
        "topology": testbed["topology"],
        "openplc": testbed["openplc"],
        "timerres": f"{timer['timer_delta_ns']['minimum_ns']:,}",
        "controls": str(len(controls)),
        "mutants": "10",
        "worstpninetynine": fmt_us(us(worst["decision_latency_ns"]["p99_ns"])),
        "worstpninetyninems": fmt_ms(us(worst["decision_latency_ns"]["p99_ns"])),
        "worstocc": f"{us(worst['decision_latency_ns']['p99_ns']) / SCAN_PERIOD_US * 100:.1f}",
        "worstseed": str(worst_seed),
        "poolpfifty": fmt_us(us(full_pool["p50_ns"])),
        "poolpninetynine": fmt_us(us(full_pool["p99_ns"])),
        "poolpthreenines": fmt_us(us(full_pool["p999_ns"])),
        "maxmax": fmt_ms(us(max(item[1]["decision_latency_ns"]["maximum_ns"] for item in full))),
        "mismatches": f"{sum(item[1]['decision_mismatches'] for item in full):,}",
        "decisions": f"{sum(item[1]['measured_decisions'] for item in full):,}",
        "tputmin": f"{min(item[1]['throughput_decisions_per_s_wall'] for item in full) / 1000:.1f}",
        "tputmax": f"{max(item[1]['throughput_decisions_per_s_wall'] for item in full) / 1000:.1f}",
        "peakrss": f"{max(item[1]['peak_rss_kib'] for item in full) / 1024:.0f}",
        "cachemissworst": fmt_us(us(cache_worst)),
        "cachemissworstms": fmt_ms(us(cache_worst)),
        "coldworst": fmt_us(us(cold)),
        "unsignedchange": fmt_signed_us(us(unsigned_pool["p50_ns"] - full_pool["p50_ns"])),
        "auditcost": fmt_signed_us(us(audit_off_pool["p50_ns"] - full_pool["p50_ns"])),
        "remoteworst": fmt_us(us(remote_worst)),
        "proppfifty": fmt_us(us(propagation["p50_ns"])),
        "proppninetynine": fmt_us(us(propagation["p99_ns"])),
        "propmax": fmt_ms(us(propagation["maximum_ns"])),
        "scaleoneworst": fmt_us(us(max(scaling[(1, depth)] for depth in DEPTHS))),
        "scalethousandworst": fmt_us(us(max(scaling[(1000, depth)] for depth in DEPTHS))),
        "scalemissworst": fmt_us(us(max(scaling_miss.values()))),
        "policylimit": "none" if policy_limit is None else f"{policy_limit:,}",
        "sintworstms": fmt_ms(us(baselines["sint"]["worst_repetition"]["p99_ns"])),
        "zcfullworst": fmt_us(us(baselines["zonecap_full"]["worst_repetition"]["p99_ns"])),
        "zcmissworst": fmt_us(us(baselines["zonecap_cache_miss"]["worst_repetition"]["p99_ns"])),
        "ratiofull": f"{speedup['zonecap_full']['sint_over_zonecap']['p99_ns']:.0f}",
        "ratiomiss": f"{speedup['zonecap_cache_miss']['sint_over_zonecap']['p99_ns']:.0f}",
        "failedchecks": ", ".join(name.replace("_", " ") for name in failing_checks) or "none",
    }
    if args.e2e:
        e2e = load(Path(args.e2e))
        values.update({
            "etoepfifty": fmt_ms(e2e["total_p50_us"]),
            "etoepninetynine": fmt_ms(e2e["total_p99_us"]),
            "etoeoverruns": f"{e2e['overruns_with_pep']:,}",
            "etoeoverrunsbypass": f"{e2e['overruns_bypass']:,}",
        })
    table_rows = []
    csv_rows = []
    for seed, item in full:
        latency = item["decision_latency_ns"]
        row = {
            "seed": seed,
            "p50_us": us(latency["p50_ns"]),
            "p99_us": us(latency["p99_ns"]),
            "max_us": us(latency["maximum_ns"]),
            "occupancy_percent": us(latency["p99_ns"]) / SCAN_PERIOD_US * 100,
            "throughput_k_per_s": item["throughput_decisions_per_s_wall"] / 1000,
            "peak_rss_mib": item["peak_rss_kib"] / 1024,
            "mismatches": item["decision_mismatches"],
        }
        csv_rows.append(row)
        table_rows.append(
            f"{seed} & {fmt_us(row['p50_us'])} & {fmt_us(row['p99_us'])} & {fmt_ms(row['max_us'])} & "
            f"{row['occupancy_percent']:.1f} & {row['throughput_k_per_s']:.1f} & "
            f"{row['peak_rss_mib']:.0f} & {row['mismatches']} \\\\"
        )
    # Table rows live in a macro: \input inside a tabular breaks \bottomrule.
    numbers = macros(values, case, preview) + "\\def\\cfivetablerows{%\n" + "\n".join(table_rows) + "\n}\n"
    (out_dir / "c5_numbers.tex").write_text(numbers, encoding="utf-8")
    with (source_dir / "fig06_tab04_repetitions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    build_figure(out_dir, source_dir, exp22, exp23, exp24, exp25, full, cache_miss, scaling, preview)
    summary = {"case": case, "case_name": CASE_NAMES[case], "failing_checks": failing_checks,
               "policy_limit": policy_limit, "preview": preview}
    (out_dir / "c5_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


def build_figure(out_dir, source_dir, exp22, exp23, exp24, exp25, full, cache_miss, scaling, preview) -> None:
    fig = plt.figure(figsize=(7.2, 3.6))
    grid = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.2, 1.05], hspace=0.75, wspace=0.45)
    ax_rep = fig.add_subplot(grid[0, 0])
    ax_tail = fig.add_subplot(grid[:, 1])
    ax_scale = fig.add_subplot(grid[0, 2])
    ax_base = fig.add_subplot(grid[1, 0])
    ax_key = fig.add_subplot(grid[1, 2])

    # a: per-repetition p99, full path and cache-cleared diagnostic.
    seeds = [seed for seed, _ in full]
    x = np.arange(len(seeds))
    full_p99 = [us(item["decision_latency_ns"]["p99_ns"]) for _, item in full]
    miss_p99 = [us(item["decision_latency_ns"]["p99_ns"]) for _, item in cache_miss]
    ax_rep.axhline(THRESHOLD_US, color=COLORS["warning"], lw=0.8, ls="--")
    full_handle = ax_rep.scatter(x, full_p99, s=16, color=COLORS["hero"], zorder=3)
    miss_handle = ax_rep.scatter(x, miss_p99, s=16, facecolors="white", edgecolors=COLORS["hero"], zorder=3)
    ax_rep.set_xticks(x, [str(seed) for seed in seeds], rotation=35, ha="right")
    ax_rep.set_xlabel("repetition seed")
    ax_rep.set_ylabel("p99 (µs)")
    ax_rep.set_ylim(0, max(THRESHOLD_US * 1.15, max(full_p99 + miss_p99) * 1.15))
    ax_rep.set_title("Per-repetition p99", loc="left")

    # b: upper-tail complementary CDF of every full-path sample.
    samples = np.sort(pooled(exp22, "full")) / 1000.0
    n = samples.size
    survival = 1.0 - np.arange(1, n + 1) / n
    keep = survival > 0
    ax_tail.loglog(samples[keep], survival[keep], color=COLORS["hero"], lw=1.0)
    for proportion, label in ((0.95, "p95"), (0.99, "p99"), (0.999, "p99.9")):
        value = samples[math.ceil(proportion * n) - 1]
        ax_tail.plot([value], [1 - proportion], marker="o", ms=3, color=COLORS["hero"])
        ax_tail.annotate(label, (value, 1 - proportion), textcoords="offset points", xytext=(4, 2), fontsize=6)
    ax_tail.axvline(THRESHOLD_US, color=COLORS["warning"], lw=0.8, ls="--")
    ax_tail.set_xlabel("decision latency (µs)")
    ax_tail.set_ylabel("fraction of decisions above")
    ax_tail.set_title(f"Upper tail, {n:,} samples", loc="left")

    # c: worst-repetition p99 over policy count and delegation depth.
    matrix = np.array([[us(scaling[(count, depth)]) for count in POLICY_COUNTS] for depth in DEPTHS])
    top = max(THRESHOLD_US, matrix.max())
    ax_scale.imshow(matrix, cmap="Blues", vmin=0, vmax=top, aspect="auto")
    for row in range(len(DEPTHS)):
        for column in range(len(POLICY_COUNTS)):
            value = matrix[row, column]
            ax_scale.text(column, row, fmt_us(value), ha="center", va="center", fontsize=5.8,
                          color="white" if value > 0.55 * top else COLORS["black"])
    ax_scale.set_xticks(range(len(POLICY_COUNTS)), [f"{count:,}" for count in POLICY_COUNTS])
    ax_scale.set_yticks(range(len(DEPTHS)), [str(depth) for depth in DEPTHS])
    ax_scale.set_xlabel("registered policies")
    ax_scale.set_ylabel("delegation depth")
    ax_scale.set_title("Worst p99 (µs)", loc="left")

    # d: same-target comparison on the common subset, horizontal bars on a log axis.
    names = ("sint", "zonecap_cache_miss", "zonecap_full")
    labels = ("pinned SINT", "ZoneCap, cache cleared", "ZoneCap")
    worst_p99 = [us(exp25["configurations"][name]["worst_repetition"]["p99_ns"]) for name in names]
    colors = (COLORS["baseline_light"], COLORS["hero_light"], COLORS["hero"])
    # On a log axis a bar needs a positive origin: draw each from 10 µs to its value.
    origin = 10.0
    ax_base.barh(range(3), [value - origin for value in worst_p99], left=origin, color=colors,
                 edgecolor=COLORS["black"], linewidth=0.4)
    ax_base.set_xscale("log")
    ax_base.set_xlim(origin, max(worst_p99) * 3)
    ax_base.axvline(THRESHOLD_US, color=COLORS["warning"], lw=0.8, ls="--")
    ax_base.set_yticks(range(3), labels, fontsize=6)
    ax_base.set_xlabel("worst p99 (µs)")
    ax_base.set_title("Common subset, same target", loc="left")
    for index, value in enumerate(worst_p99):
        ax_base.text(value * 1.15, index, fmt_us(value), va="center", fontsize=5.8)

    ax_key.axis("off")
    threshold_handle = plt.Line2D([], [], color=COLORS["warning"], lw=0.8, ls="--")
    ax_key.legend([full_handle, miss_handle, threshold_handle],
                  ["full path", "verification cache cleared", "registered 1 ms threshold"],
                  loc="upper left", fontsize=6, frameon=False, handletextpad=0.4, borderaxespad=0)
    ax_key.text(0, 0.30, "Executable PLC ABAC/NGAC: N/A\n(no versioned artifact supplied)\n"
                "Occupancy = p99 / 10 ms (derived)", fontsize=6, va="top", color=COLORS["black"],
                transform=ax_key.transAxes)
    if preview:
        fig.text(0.5, 0.5, "DEVELOPMENT PREVIEW\nNOT EVIDENCE", fontsize=26, color=COLORS["warning_light"],
                 ha="center", va="center", rotation=20, zorder=0)

    place_panel_labels(fig, [ax_rep, ax_tail, ax_scale, ax_base])
    stem = "fig06_c5_feasibility"
    for suffix, options in ((".svg", {}), (".pdf", {}), (".eps", {}), (".png", {"dpi": 300}),
                            (".tiff", {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}})):
        fig.savefig(out_dir / f"{stem}{suffix}", bbox_inches="tight", **options)
    plt.close(fig)

    with (source_dir / "fig06_scaling.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["delegation_depth", "registered_policies", "worst_repetition_p99_us"])
        for row, depth in enumerate(DEPTHS):
            for column, count in enumerate(POLICY_COUNTS):
                writer.writerow([depth, count, f"{matrix[row, column]:.3f}"])
    with (source_dir / "fig06_baselines.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["configuration", "worst_repetition_p99_us"])
        for name, value in zip(names, worst_p99):
            writer.writerow([name, f"{value:.3f}"])
    with (source_dir / "fig06_repetitions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "full_path_p99_us", "cache_cleared_p99_us"])
        for seed, full_value, miss_value in zip(seeds, full_p99, miss_p99):
            writer.writerow([seed, f"{full_value:.3f}", f"{miss_value:.3f}"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conditional C5 displays from audited runs.")
    for name in ("exp22", "exp23", "exp24", "exp25"):
        parser.add_argument(f"--{name}", required=True, help="result directory relative to the repository root")
    parser.add_argument("--testbed", required=True, help="JSON with module, jetpack, power_mode, topology, openplc")
    parser.add_argument("--e2e", help="JSON with total_p50_us, total_p99_us, overruns_with_pep, overruns_bypass")
    parser.add_argument("--preview", help="development dry run: write watermarked outputs to this directory")
    try:
        build(parser.parse_args())
    except AuditError as error:
        sys.exit(f"audit failed: {error}")


if __name__ == "__main__":
    main()
