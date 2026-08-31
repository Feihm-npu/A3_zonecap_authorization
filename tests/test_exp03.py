from fractions import Fraction

from zonecap.exp03 import (
    _box,
    convex_hull,
    negative_controls,
    point_in_convex,
    polytope_is_subset,
)


def test_convex_hull_and_subset_are_exact_for_nested_polytopes():
    parent = _box(Fraction(-2), Fraction(2), Fraction(-1), Fraction(1))
    child = convex_hull(
        (
            (Fraction(-1), Fraction(0)),
            (Fraction(0), Fraction(-1, 2)),
            (Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(1, 2)),
        )
    )
    assert polytope_is_subset(child, parent)
    assert point_in_convex(parent, (Fraction(2), Fraction(1)))
    assert not point_in_convex(parent, (Fraction(2), Fraction(2)))


def test_exp03_negative_controls_are_detected():
    controls = negative_controls()
    assert controls["mimo_widening_detected"]
    assert controls["history_widening_detected"]
