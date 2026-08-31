from __future__ import annotations

from dataclasses import replace
import random
from typing import Any

from .models import Capability, Interval, Plant1D


def reachable_intervals_1d(
    plant: Plant1D,
    initial: Interval,
    capability: Capability,
    horizon: int,
) -> list[Interval]:
    if horizon < 0:
        raise ValueError("horizon must be non-negative")
    reachable = [initial]
    current = initial
    for _ in range(horizon):
        current = (
            current.linear_image(plant.a)
            .minkowski(capability.parameter.linear_image(plant.b))
            .minkowski(plant.disturbance)
        )
        reachable.append(current)
    return reachable


def monotonicity_violations(
    plant: Plant1D,
    initial: Interval,
    parent: Capability,
    child: Capability,
    horizon: int,
) -> list[dict[str, Any]]:
    child.assert_attenuates(parent)
    parent_sets = reachable_intervals_1d(plant, initial, parent, horizon)
    child_sets = reachable_intervals_1d(plant, initial, child, horizon)
    violations = []
    for tick, (parent_set, child_set) in enumerate(zip(parent_sets, child_sets)):
        if not child_set.is_subset_of(parent_set, atol=1e-9):
            violations.append(
                {
                    "tick": tick,
                    "parent": parent_set.to_list(),
                    "child": child_set.to_list(),
                }
            )
    return violations


def randomized_counterexample_search(
    template: Capability,
    *,
    seed: int,
    cases: int,
    horizon: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    violations: list[dict[str, Any]] = []
    for case in range(cases):
        a = rng.uniform(-1.5, 1.5)
        b = rng.uniform(-1.5, 1.5)
        w_radius = rng.uniform(0.0, 0.2)
        parent_low = rng.uniform(-2.0, 0.0)
        parent_high = rng.uniform(0.0, 2.0)
        left_shrink = rng.uniform(0.0, 0.45 * (parent_high - parent_low))
        right_shrink = rng.uniform(0.0, 0.45 * (parent_high - parent_low))
        child_interval = Interval(
            parent_low + left_shrink,
            parent_high - right_shrink,
        )
        parent = replace(
            template,
            capability_id=f"random-parent-{case}",
            parameter=Interval(parent_low, parent_high),
            parent_id=None,
            delegation_depth=0,
        )
        child = parent.attenuate(
            capability_id=f"random-child-{case}",
            parameter=child_interval,
        )
        initial_center = rng.uniform(-1.0, 1.0)
        initial_radius = rng.uniform(0.0, 0.2)
        found = monotonicity_violations(
            Plant1D(a=a, b=b, disturbance=Interval(-w_radius, w_radius)),
            Interval(initial_center - initial_radius, initial_center + initial_radius),
            parent,
            child,
            horizon,
        )
        if found:
            violations.append({"case": case, "violations": found})
    return {
        "seed": seed,
        "cases": cases,
        "horizon": horizon,
        "violations": violations,
    }
