#!/usr/bin/env python3
"""Build Figure 1, the ZoneCap compilation and enforcement overview.

The figure is a conceptual schematic and carries no evaluation counts.  It
reuses the palette, typography, and export settings of the data-bearing
figures so that effect colors stay identical between Figures 1 and 4.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

from build_result_figures import COLORS, EFFECT_COLORS, save_figure


FONT = 6.4
SMALL = 5.9


def box(ax, x, y, w, h, *, edge, face="white", dashed=False, lw=0.8, radius=0.6):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw,
        linestyle=(0, (3, 2)) if dashed else "solid",
        edgecolor=edge,
        facecolor=face,
        zorder=2,
    )
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, *, color=None, lw=0.8, style="-|>", ls="solid", rad=0.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=7,
        linewidth=lw,
        linestyle=ls,
        color=color or COLORS["black"],
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=0,
        shrinkB=0,
        zorder=3,
    )
    ax.add_patch(patch)


def polyline(ax, points, *, color=None, lw=0.8):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=color or COLORS["black"], lw=lw, solid_capstyle="butt", zorder=3)


def badge(ax, x, y, number):
    ax.add_patch(Circle((x, y), 0.95, facecolor=COLORS["hero"], edgecolor="none", zorder=5))
    ax.text(x, y - 0.05, str(number), ha="center", va="center", color="white", fontsize=5.6, fontweight="bold", zorder=6)


def band_title(ax, x0, x1, label):
    ax.text((x0 + x1) / 2, 31.0, label, ha="center", va="center", fontsize=7, fontweight="bold")
    ax.plot([x0, x1], [30.0, 30.0], color=COLORS["baseline_light"], lw=0.8, zorder=1)


def build_overview() -> None:
    fig = plt.figure(figsize=(7.15, 2.30))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 32)
    ax.set_axis_off()

    band_title(ax, 0.5, 20.5, "Policy input")
    band_title(ax, 27.0, 53.5, "Capability lineage")
    band_title(ax, 56.0, 85.0, "Runtime authorization")
    band_title(ax, 87.5, 99.5, "Plant")

    # Policy band: source-derived topology versus encoded/overlaid fields.
    box(ax, 0.5, 13.5, 20.0, 14.5, edge=COLORS["baseline"], face=COLORS["baseline_light"])
    ax.text(10.5, 26.2, "Source-derived topology", ha="center", va="center", fontsize=FONT)
    zones = [(1.6, "Zone 1"), (8.0, "Zone 2"), (14.4, "Zone 3")]
    for x, label in zones:
        box(ax, x, 19.0, 4.9, 3.6, edge=COLORS["baseline"], radius=0.4)
        ax.text(x + 2.45, 20.8, label, ha="center", va="center", fontsize=SMALL)
    for (x, _), (nx, _), label in zip(zones[:-1], zones[1:], [r"$k_1$", r"$k_2$"]):
        arrow(ax, (x + 4.9, 20.8), (nx, 20.8))
        ax.text((x + 4.9 + nx) / 2, 22.2, label, ha="center", va="bottom", fontsize=SMALL)
    ax.text(10.5, 15.8, "directed zone/conduit\ngrant rows", ha="center", va="center", fontsize=SMALL)

    box(ax, 0.5, 4.5, 20.0, 7.6, edge=COLORS["baseline"], dashed=True)
    ax.text(10.5, 10.6, "Encoded + declared overlay", ha="center", va="center", fontsize=FONT)
    ax.text(10.5, 8.2, "per-zone asset IDs", ha="center", va="center", fontsize=SMALL)
    ax.text(10.5, 6.0, r"$O,\ I_u,\ I_t,\ M,\ L$", ha="center", va="center", fontsize=SMALL)

    # Compiler.
    box(ax, 22.0, 4.5, 3.4, 23.5, edge=COLORS["hero"], face=COLORS["hero_light"])
    ax.text(23.7, 16.2, "Topology-validating compiler", ha="center", va="center", rotation=90, fontsize=FONT)
    arrow(ax, (20.5, 20.8), (22.0, 20.8))
    arrow(ax, (20.5, 8.3), (22.0, 8.3))
    badge(ax, 23.7, 28.4, 1)

    # Capability lineage: root, depth-1 child, depth-2 child.
    lineage = [
        (21.5, r"Root $c$", "depth 0", COLORS["baseline"], COLORS["baseline_light"]),
        (13.0, r"Child $c' \preceq c$", "depth 1", COLORS["hero"], COLORS["hero_light"]),
        (4.5, r"Child $c'' \preceq c'$", "depth 2", COLORS["hero"], COLORS["hero_light"]),
    ]
    for y, title, depth, edge, face in lineage:
        box(ax, 27.0, y, 11.0, 5.0, edge=edge, face=face)
        ax.text(32.5, y + 3.2, title, ha="center", va="center", fontsize=FONT)
        ax.text(32.5, y + 1.4, depth, ha="center", va="center", fontsize=SMALL, color=COLORS["baseline"])
    arrow(ax, (25.4, 24.0), (27.0, 24.0))
    for upper, lower in [(21.5, 18.0), (13.0, 9.5)]:
        arrow(ax, (32.5, upper), (32.5, lower))
        ax.text(31.9, (upper + lower) / 2, "delegate", ha="right", va="center", fontsize=SMALL, color=COLORS["baseline"])
        arrow(ax, (40.0, (upper + lower) / 2), (32.7, (upper + lower) / 2), style="-", ls=(0, (2, 1.5)), color=COLORS["baseline"], lw=0.6)

    # Attenuation validator.
    box(ax, 40.0, 4.5, 14.0, 23.5, edge=COLORS["black"])
    ax.text(47.0, 25.9, "Attenuation validator", ha="center", va="center", fontsize=FONT)
    ax.text(47.0, 24.0, "8 dimensions", ha="center", va="center", fontsize=SMALL, color=COLORS["baseline"])
    rules = [
        (20.8, r"$Z_s, Z_d$", "invariant"),
        (18.0, r"$K, A, O, M$", "subset"),
        (15.2, r"$I_u, I_t$", "subinterval"),
        (12.4, r"$L$", "prefix extension"),
    ]
    for y, fields, rule in rules:
        ax.text(41.0, y, fields, ha="left", va="center", fontsize=SMALL)
        ax.text(53.2, y, rule, ha="right", va="center", fontsize=SMALL)
    ax.plot([41.0, 53.0], [10.4, 10.4], color=COLORS["baseline_light"], lw=0.6, zorder=3)
    ax.text(47.0, 8.6, "any widening", ha="center", va="center", fontsize=SMALL, color=COLORS["warning"])
    ax.text(47.0, 6.6, "rejected, not clamped", ha="center", va="center", fontsize=SMALL, color=COLORS["warning"])

    # Runtime: policy engine and the five effects.
    arrow(ax, (54.0, 16.0), (56.0, 16.0))
    box(ax, 56.0, 7.5, 8.6, 17.0, edge=COLORS["hero"], face=COLORS["hero_light"])
    ax.text(60.3, 21.3, "Policy\nengine", ha="center", va="center", fontsize=FONT)
    ax.text(60.3, 17.6, r"in: $c_{\mathrm{eff}}$, $q$", ha="center", va="center", fontsize=SMALL)
    ax.text(60.3, 12.4, "fail-closed\norder;\npre-emission\nrecheck", ha="center", va="center", fontsize=SMALL, color=COLORS["black"])

    effects = [
        (23.0, "ALLOW", "checked $u$"),
        (19.5, "REWRITE", "boundary $u$"),
        (16.0, "DEFER", "read hold"),
        (12.5, "ATTENUATE", "derived child"),
        (9.0, "DENY", "fail closed"),
    ]
    for y, name, outcome in effects:
        color = EFFECT_COLORS[name.lower()]
        box(ax, 66.4, y - 1.35, 8.0, 2.7, edge=color, face=color, radius=0.35)
        ax.text(70.4, y, name, ha="center", va="center", fontsize=5.6, color="white", fontweight="bold")
        arrow(ax, (64.6, 16.0), (66.4, y), lw=0.6, style="-")
        ax.text(75.0, y, outcome, ha="left", va="center", fontsize=SMALL)

    # Emitting effects converge on the plant; the others emit nothing.
    polyline(ax, [(83.0, 23.0), (84.2, 23.0), (84.2, 16.0), (83.0, 16.0)], color=COLORS["hero"])
    arrow(ax, (84.2, 19.5), (88.0, 19.5), color=COLORS["hero"])
    badge(ax, 86.0, 21.4, 2)
    polyline(ax, [(83.0, 12.5), (84.2, 12.5), (84.2, 9.0), (83.0, 9.0)], color=COLORS["baseline"])
    ax.text(85.0, 10.75, "no actuation event", ha="left", va="center", fontsize=SMALL, color=COLORS["baseline"])

    # Plant and shared physical assumptions.
    box(ax, 88.0, 16.0, 11.5, 10.5, edge=COLORS["black"])
    ax.text(93.75, 24.9, r"Plant $\mathcal{P}$", ha="center", va="center", fontsize=FONT)
    ax.text(93.75, 22.4, r"$x_{t+1}=$", ha="center", va="center", fontsize=SMALL)
    ax.text(93.75, 20.4, r"$F(x_t,u_t,w_t)$", ha="center", va="center", fontsize=SMALL)
    ax.text(93.75, 17.6, r"$x_0\in X_0,\ w_t\in W$", ha="center", va="center", fontsize=SMALL)
    badge(ax, 98.6, 27.2, 3)
    ax.text(93.75, 15.2, r"traces $\mathcal{T}_H$," "\n" r"reach sets $\mathcal{R}_t$", ha="center", va="top", fontsize=SMALL)

    # Trusted physical history feeds back to the engine.
    polyline(ax, [(93.75, 26.5), (93.75, 27.8), (60.3, 27.8)], color=COLORS["baseline"])
    arrow(ax, (60.3, 27.8), (60.3, 24.5), color=COLORS["baseline"])
    ax.text(77.0, 28.1, r"trusted history $\eta_t$, mode, time", ha="center", va="bottom", fontsize=SMALL, color=COLORS["baseline"])

    # Interface legend.
    legend = [
        (1, "positive conjunctive compilation"),
        (2, "authorized, parent-realizable emission"),
        (3, r"common $\eta$, $F$, $X_0$, $W$, $H$ for parent and child"),
    ]
    x = 4.0
    for number, label in legend:
        badge(ax, x, 1.6, number)
        ax.text(x + 1.5, 1.6, label, ha="left", va="center", fontsize=FONT)
        x += 31.0

    save_figure(fig, "fig01_zonecap_overview")


if __name__ == "__main__":
    build_overview()
