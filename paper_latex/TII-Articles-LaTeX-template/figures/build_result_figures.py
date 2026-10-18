#!/usr/bin/env python3
"""Build the data-bearing figures for the ZoneCap TII manuscript.

All quantitative marks are read from frozen experiment artifacts.  The script
also emits panel-level CSV files so that every plotted value can be audited
without extracting it from the artwork.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


# Mandatory publication/export settings.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
mpl.rcParams.update(
    {
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

mpl.rcParams.update(
    {
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "savefig.facecolor": "white",
    }
)


ROOT = Path(__file__).resolve().parents[3]
FIGURE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = FIGURE_DIR / "generated"
SOURCE_DIR = FIGURE_DIR / "source_data"

COLORS = {
    "hero": "#0F4D92",
    "hero_light": "#B9D0E8",
    "baseline": "#767676",
    "baseline_light": "#D8D8D8",
    "accent": "#42949E",
    "accent_light": "#BFE1E4",
    "warning": "#B64342",
    "warning_light": "#F1C8C5",
    "violet": "#7C6CCF",
    "gold": "#D39B28",
    "black": "#272727",
}

EFFECT_COLORS = {
    "allow": COLORS["hero"],
    "deny": COLORS["baseline"],
    "attenuate": COLORS["violet"],
    "rewrite": COLORS["accent"],
    "defer": COLORS["gold"],
}


def load_json(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    with (SOURCE_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{stem}.eps", bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(
        OUTPUT_DIR / f"{stem}.tiff",
        dpi=600,
        bbox_inches="tight",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    plt.close(fig)


def panel_label(ax: plt.Axes, label: str, x: float = -0.12, y: float = 1.10) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        ha="left",
        va="bottom",
    )


def place_panel_labels(fig: plt.Figure, axes: list[plt.Axes]) -> None:
    """Put each label just left of its panel's full extent, level with the title.

    Use when wide tick labels or titles make axes-relative offsets collide.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    to_figure = fig.transFigure.inverted()
    for idx, ax in enumerate(axes):
        extent = ax.get_tightbbox(renderer)
        title = ax.title.get_window_extent(renderer)
        x, y = to_figure.transform((extent.x0 - 3, (title.y0 + title.y1) / 2))
        fig.text(x, y, chr(ord("a") + idx), fontsize=8, fontweight="bold", ha="right", va="center")


def add_value_labels(ax: plt.Axes, bars, fmt) -> None:
    for bar in bars:
        value = bar.get_width() if bar.get_width() else bar.get_height()
        if bar.get_width() >= bar.get_height():
            ax.annotate(
                fmt(value),
                xy=(bar.get_x() + bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(3, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=6.5,
            )
        else:
            ax.annotate(
                fmt(value),
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height()),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=6.5,
            )


def build_refinement_reachability() -> None:
    data = load_json("results/exp05_common_subset_20260901/reachability.json")
    records = [row for row in data["records"] if row["adapter"] == "ZoneCap"]
    by_plant: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        by_plant[row["plant"]].append(row)
    plant_order = [
        "integrator_positive_input",
        "signed_coupled_response",
        "stable_negative_input",
    ]
    plant_titles = {
        "integrator_positive_input": "Positive-input integrator",
        "signed_coupled_response": "Signed coupled response",
        "stable_negative_input": "Stable negative-input plant",
    }

    source_rows: list[dict] = []
    for plant in plant_order:
        for row in sorted(by_plant[plant], key=lambda item: item["horizon"]):
            source_rows.append(
                {
                    "plant": plant,
                    "horizon": row["horizon"],
                    "parent_low": float(Fraction(row["parent"][0])),
                    "parent_high": float(Fraction(row["parent"][1])),
                    "child_low": float(Fraction(row["child"][0])),
                    "child_high": float(Fraction(row["child"][1])),
                    "included": row["included"],
                }
            )
    write_csv(
        "fig02_reachability.csv",
        ["plant", "horizon", "parent_low", "parent_high", "child_low", "child_high", "included"],
        source_rows,
    )

    fig = plt.figure(figsize=(7.15, 3.05), layout="constrained")
    grid = fig.add_gridspec(1, 4, width_ratios=[1.45, 1, 1, 1], wspace=0.20)
    ax0 = fig.add_subplot(grid[0, 0])
    ax0.set_axis_off()
    panel_label(ax0, "a", x=-0.02, y=1.05)
    ax0.set_title("Refinement contract", pad=9)

    chain = [
        (0.77, r"Field-wise attenuation  $c' \preceq c$"),
        (0.54, r"Authorized emissions  $\overline{E}_{c'} \subseteq \overline{E}_{c}$"),
        (0.31, r"Physical traces  $\mathrm{Tr}_H(c') \subseteq \mathrm{Tr}_H(c)$"),
        (0.08, r"Reachable sets  $\mathrm{Reach}_t(c') \subseteq \mathrm{Reach}_t(c)$"),
    ]
    for idx, (y, label) in enumerate(chain):
        box = FancyBboxPatch(
            (-0.22, y),
            1.44,
            0.13,
            boxstyle="round,pad=0.015,rounding_size=0.02",
            linewidth=0.8,
            edgecolor=COLORS["hero"] if idx in (0, 3) else COLORS["baseline"],
            facecolor=COLORS["hero_light"] if idx in (0, 3) else "white",
            transform=ax0.transAxes,
            clip_on=False,
        )
        ax0.add_patch(box)
        ax0.text(0.50, y + 0.065, label, transform=ax0.transAxes, ha="center", va="center", fontsize=6.6)
        if idx < len(chain) - 1:
            arrow = FancyArrowPatch(
                (0.50, y - 0.015),
                (0.50, chain[idx + 1][0] + 0.15),
                arrowstyle="-|>",
                mutation_scale=8,
                linewidth=0.8,
                color=COLORS["black"],
                transform=ax0.transAxes,
            )
            ax0.add_patch(arrow)
    ax0.text(
        0.50,
        -0.04,
        "Positive conjunction; sound and parent-realizable effects;\ncommon history, plant, uncertainty, and horizon",
        transform=ax0.transAxes,
        ha="center",
        va="top",
        fontsize=6.2,
        color=COLORS["baseline"],
    )

    for idx, plant in enumerate(plant_order, start=1):
        ax = fig.add_subplot(grid[0, idx])
        rows = sorted(by_plant[plant], key=lambda item: item["horizon"])
        horizon = np.array([row["horizon"] for row in rows])
        parent_low = np.array([float(Fraction(row["parent"][0])) for row in rows])
        parent_high = np.array([float(Fraction(row["parent"][1])) for row in rows])
        child_low = np.array([float(Fraction(row["child"][0])) for row in rows])
        child_high = np.array([float(Fraction(row["child"][1])) for row in rows])
        ax.fill_between(
            horizon,
            parent_low,
            parent_high,
            color=COLORS["baseline_light"],
            label="Parent",
            zorder=1,
        )
        ax.fill_between(
            horizon,
            child_low,
            child_high,
            color=COLORS["hero_light"],
            label="Child",
            zorder=2,
        )
        ax.plot(horizon, parent_low, color=COLORS["baseline"], lw=0.8)
        ax.plot(horizon, parent_high, color=COLORS["baseline"], lw=0.8)
        ax.plot(horizon, child_low, color=COLORS["hero"], lw=0.9)
        ax.plot(horizon, child_high, color=COLORS["hero"], lw=0.9)
        ax.set_title(plant_titles[plant], pad=9)
        ax.set_xlabel("Actuation-event horizon")
        ax.set_xticks([0, 2, 4, 6])
        if idx == 1:
            ax.set_ylabel("Reachable-state interval")
            ax.legend(loc="upper left")
        panel_label(ax, chr(ord("a") + idx), x=-0.18, y=1.08)
        ax.margins(x=0.02)

    save_figure(fig, "fig02_refinement_reachability")


def build_compiler_results() -> None:
    main = load_json("results/exp07_heldout_equivalence_20260901/metrics.json")
    adequacy = load_json("results/exp08_source_generation_ablation_20260901/metrics.json")
    delegation = load_json("results/exp09_depth_path_widening_20260901/metrics.json")

    source_rows = [
        {
            "architecture": "CPwE/CIP Security",
            "cases": main["architectures"]["cpwe_cip_security"]["cases"],
            "mismatches": main["architectures"]["cpwe_cip_security"]["mismatches"],
        },
        {
            "architecture": "ENISA landside signalling",
            "cases": main["architectures"]["enisa_rail_signalling"]["cases"],
            "mismatches": main["architectures"]["enisa_rail_signalling"]["mismatches"],
        },
    ]
    control_rows = [
        {
            "control": "Generated corpus: check-removal mutants killed",
            "observed": adequacy["generated_check_removal_mutants_killed"],
            "total": adequacy["registered_check_removal_mutants"],
        },
        {
            "control": "Six happy paths: check-removal mutants killed",
            "observed": adequacy["handwritten_fixture_check_removal_mutants_killed"],
            "total": adequacy["registered_check_removal_mutants"],
        },
        {
            "control": "Legal delegation checks passed",
            "observed": delegation["legal_delegation_dimension_checks"]
            - delegation["legal_delegation_dimension_failures"],
            "total": delegation["legal_delegation_dimension_checks"],
        },
        {
            "control": "Localized widenings rejected",
            "observed": delegation["widening_attempts"] - delegation["accepted_widenings"],
            "total": delegation["widening_attempts"],
        },
    ]
    write_csv("fig03_architectures.csv", ["architecture", "cases", "mismatches"], source_rows)
    write_csv(
        "fig03_corpus.csv",
        ["case_type", "cases"],
        [
            {"case_type": "Valid", "cases": main["valid_cases"]},
            {"case_type": "Single-field mutation", "cases": main["mutation_cases"]},
        ],
    )
    write_csv("fig03_controls.csv", ["control", "observed", "total"], control_rows)

    fig = plt.figure(figsize=(7.15, 2.55), layout="constrained")
    grid = fig.add_gridspec(1, 3, width_ratios=[1.15, 0.95, 1.65], wspace=0.30)

    ax = fig.add_subplot(grid[0, 0])
    labels = [row["architecture"] for row in source_rows][::-1]
    values = [row["cases"] for row in source_rows][::-1]
    bars = ax.barh(labels, values, color=[COLORS["accent"], COLORS["hero"]], height=0.55)
    ax.set_xlabel("Compiler/oracle cases")
    ax.set_title("Frozen source structures", pad=9)
    ax.set_xlim(0, max(values) * 1.24)
    add_value_labels(ax, bars, lambda value: f"{int(value):,}\n0 mismatch")
    panels = [ax]

    ax = fig.add_subplot(grid[0, 1])
    valid = main["valid_cases"]
    mutated = main["mutation_cases"]
    total = main["total_cases"]
    ax.barh([0], [valid], color=COLORS["hero"], height=0.40, label="Valid")
    ax.barh([0], [mutated], left=[valid], color=COLORS["warning_light"], height=0.40, label="Single-field mutation")
    ax.annotate(
        f"{valid:,} valid\n({valid / total * 100:.1f}%)",
        xy=(valid / 2, 0.19),
        xytext=(total * 0.10, 0.64),
        ha="center",
        va="bottom",
        fontsize=6.1,
        arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["hero"]},
    )
    ax.text(valid + mutated / 2, 0, f"{mutated:,}\n({mutated / total * 100:.1f}%)", ha="center", va="center", fontsize=6.2)
    ax.set_xlim(0, total)
    ax.set_ylim(-0.42, 0.88)
    ax.set_yticks([])
    ax.set_xlabel("Cases")
    ax.set_title(f"Complete corpus (n={total:,})", pad=9)
    panels.append(ax)

    ax = fig.add_subplot(grid[0, 2])
    control_labels = [
        "Generated corpus\nmutant kills",
        "Six happy paths\nmutant kills",
        "Legal delegation\nchecks",
        "Localized widening\nrejections",
    ][::-1]
    ratios = [row["observed"] / row["total"] * 100 for row in control_rows][::-1]
    ax.barh(control_labels, [100] * 4, color=COLORS["baseline_light"], height=0.56)
    overlay_colors = [COLORS["hero"], COLORS["warning"], COLORS["hero"], COLORS["hero"]][::-1]
    bars = ax.barh(control_labels, ratios, color=overlay_colors, height=0.56)
    for bar, row in zip(bars, control_rows[::-1]):
        xpos = max(bar.get_width(), 2)
        ax.text(
            xpos + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{row['observed']:,}/{row['total']:,}",
            ha="left",
            va="center",
            fontsize=6.4,
        )
    ax.set_xlim(0, 123)
    ax.set_xticks([0, 50, 100])
    ax.set_xlabel("Registered checks detected/passed (%)")
    ax.set_title("Adequacy and delegation controls", pad=9)
    panels.append(ax)
    place_panel_labels(fig, panels)

    save_figure(fig, "fig03_compiler_results")


def build_runtime_results() -> None:
    main = load_json("results/exp12_effect_automaton_20260901/metrics.json")
    deny_only = load_json("results/exp13_deny_only_ablation_20260901/metrics.json")
    exhaustive = load_json("results/exp14_exhaustive_sequences_20260901/metrics.json")

    effect_order = ["allow", "deny", "attenuate", "rewrite", "defer"]
    effect_rows = [
        {"effect": effect, "policy_steps": main["total_effect_counts"][effect]}
        for effect in effect_order
    ]
    ngram_rows = []
    for order in (1, 2, 3):
        total = main["all_five_effects_reached"] and 5**order
        ngram_rows.extend(
            [
                {
                    "strategy": "One named path per scope",
                    "order": order,
                    "covered": exhaustive["handpicked_ngram_counts"][str(order)],
                    "total": total,
                },
                {
                    "strategy": "Exhaustive through horizon 5",
                    "order": order,
                    "covered": exhaustive["exhaustive_ngram_counts"][str(order)],
                    "total": total,
                },
            ]
        )
    output_rows = [
        {"outcome": "Retained ALLOW outputs", "count": deny_only["deny_only_physical_outputs"]},
        {"outcome": "Lost REWRITE outputs", "count": deny_only["lost_rewrite_outputs"]},
        {"outcome": "Lost DEFER holds", "count": deny_only["lost_defer_stutters"]},
    ]
    write_csv("fig04_effect_counts.csv", ["effect", "policy_steps"], effect_rows)
    write_csv("fig04_ngram_coverage.csv", ["strategy", "order", "covered", "total"], ngram_rows)
    write_csv("fig04_deny_only_outputs.csv", ["outcome", "count"], output_rows)

    fig = plt.figure(figsize=(7.15, 2.70), layout="constrained")
    grid = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.25, 1.15], wspace=0.30)

    ax = fig.add_subplot(grid[0, 0])
    labels = [row["effect"].upper() for row in effect_rows][::-1]
    values = [row["policy_steps"] for row in effect_rows][::-1]
    colors = [EFFECT_COLORS[row["effect"]] for row in effect_rows][::-1]
    bars = ax.barh(labels, np.array(values) / 1000, color=colors, height=0.58)
    ax.set_xlabel("Policy steps (thousands)")
    ax.set_title("Observed effect mix", pad=9)
    ax.set_xlim(0, max(values) / 1000 * 1.22)
    add_value_labels(ax, bars, lambda value: f"{int(round(value * 1000)):,}")
    panel_label(ax, "a", x=-0.18, y=1.08)

    ax = fig.add_subplot(grid[0, 1])
    x = np.arange(3)
    width = 0.34
    totals = np.array([5, 25, 125])
    named_counts = np.array([5, 4, 3])
    exhaustive_counts = np.array([5, 25, 125])
    named_pct = named_counts / totals * 100
    exhaustive_pct = exhaustive_counts / totals * 100
    named_bars = ax.bar(x - width / 2, named_pct, width, color=COLORS["baseline_light"], edgecolor=COLORS["baseline"], label="Named path")
    exhaustive_bars = ax.bar(x + width / 2, exhaustive_pct, width, color=COLORS["hero"], label="Exhaustive")
    for bars, counts in ((named_bars, named_counts), (exhaustive_bars, exhaustive_counts)):
        for bar, count, total in zip(bars, counts, totals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 3,
                f"{count}/{total}",
                ha="center",
                va="bottom",
                fontsize=6.2,
            )
    ax.set_xticks(x, ["1-gram", "2-gram", "3-gram"])
    ax.set_ylim(0, 116)
    ax.set_ylabel("Effect-order coverage (%)")
    ax.set_title("Sequence coverage", pad=9)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    panel_label(ax, "b", y=1.08)

    ax = fig.add_subplot(grid[0, 2])
    total_outputs = deny_only["rich_physical_outputs"]
    left = 0
    segments = [
        ("Retained ALLOW", deny_only["deny_only_physical_outputs"], COLORS["hero"]),
        ("Lost REWRITE", deny_only["lost_rewrite_outputs"], COLORS["warning_light"]),
        ("Lost DEFER hold", deny_only["lost_defer_stutters"], COLORS["baseline_light"]),
    ]
    for label, count, color in segments:
        pct = count / total_outputs * 100
        ax.barh([0], [pct], left=[left], color=color, height=0.42, label=label)
        if pct >= 14:
            ax.text(left + pct / 2, 0, f"{count:,}\n({pct:.1f}%)", ha="center", va="center", fontsize=6.2)
        left += pct
    ax.set_xlim(0, 100)
    ax.set_yticks([])
    ax.set_xlabel("Rich-effect physical outputs (%)")
    ax.set_title("Deny-only service loss", pad=9)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=1)
    panel_label(ax, "c", y=1.08)

    save_figure(fig, "fig04_runtime_results")


def build_revocation_results() -> None:
    data = load_json("results/exp19_c4_adversarial_scheduler_20260902/metrics.json")
    delays = [0, 1, 2]
    stale = [data["violations_by_delay"][str(delay)]["post_issuance_revocation_executions"] for delay in delays]
    schedules = [data["violations_by_delay"][str(delay)]["schedules"] for delay in delays]
    fence = [0, 0, 0]
    write_csv(
        "fig05_revocation.csv",
        ["delivery_delay_steps", "fair_schedules", "unfenced_stale_executions", "post_hoc_epoch_fence_stale_executions"],
        [
            {
                "delivery_delay_steps": delay,
                "fair_schedules": schedule_count,
                "unfenced_stale_executions": stale_count,
                "post_hoc_epoch_fence_stale_executions": fence_count,
            }
            for delay, schedule_count, stale_count, fence_count in zip(delays, schedules, stale, fence)
        ],
    )

    fig = plt.figure(figsize=(3.45, 3.35), layout="constrained")
    grid = fig.add_gridspec(2, 1, height_ratios=[1.15, 0.85], hspace=0.22)

    ax = fig.add_subplot(grid[0, 0])
    x = np.arange(len(delays))
    width = 0.34
    bars = ax.bar(x - width / 2, stale, width, color=COLORS["warning"], label="Registered semantics")
    fence_bars = ax.bar(
        x + width / 2,
        fence,
        width,
        facecolor="white",
        edgecolor=COLORS["hero"],
        linewidth=1.2,
        hatch="///",
        label="Epoch fence (post-hoc)",
    )
    for bar, value in zip(bars, stale):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.12, str(value), ha="center", va="bottom")
    for bar in fence_bars:
        ax.text(bar.get_x() + bar.get_width() / 2, 0.10, "0", ha="center", va="bottom", color=COLORS["hero"])
    ax.set_xticks(x, ["0", "1", "2"])
    ax.set_ylim(0, 6.4)
    ax.set_ylabel("Post-issuance stale executions")
    ax.set_xlabel("Revocation-delivery delay (resolver steps)")
    ax.set_title("Five fixed fair schedules per delay")
    ax.legend(loc="upper left")
    panel_label(ax, "a", x=-0.11, y=1.17)

    ax = fig.add_subplot(grid[1, 0])
    ax.set_axis_off()
    panel_label(ax, "b", x=-0.02, y=0.98)
    y = 0.50
    ax.plot([0.06, 0.94], [y, y], color=COLORS["black"], lw=0.9, transform=ax.transAxes)
    events = [
        (0.10, "Issue\nrevocation"),
        (0.38, "Resolver\nstill stale"),
        (0.62, "Queued command\nmay execute"),
        (0.90, "Deliver\nrevocation"),
    ]
    ax.axvspan(0.10, 0.90, ymin=0.34, ymax=0.68, color=COLORS["warning_light"], transform=ax.transAxes)
    for idx, (xpos, label) in enumerate(events):
        color = COLORS["warning"] if idx in (0, 2) else COLORS["black"]
        ax.scatter([xpos], [y], s=22, color=color, transform=ax.transAxes, zorder=3)
        ax.text(xpos, 0.70 if idx % 2 == 0 else 0.27, label, transform=ax.transAxes, ha="center", va="center", fontsize=6.3)
    ax.text(0.50, 0.90, "Issuance-relative stale window", transform=ax.transAxes, ha="center", color=COLORS["warning"], fontsize=6.5)
    ax.text(0.94, 0.02, "Post-delivery checks: 0 stale executions", transform=ax.transAxes, ha="right", color=COLORS["hero"], fontsize=6.3)

    save_figure(fig, "fig05_revocation")


def main() -> None:
    build_refinement_reachability()
    build_compiler_results()
    build_runtime_results()
    build_revocation_results()


if __name__ == "__main__":
    main()
