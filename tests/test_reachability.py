from zonecap.compiler import Architecture
from zonecap.models import Interval, Plant1D
from zonecap.reachability import (
    monotonicity_violations,
    randomized_counterexample_search,
    reachable_intervals_1d,
)


def test_attenuation_shrinks_reachable_intervals_with_signed_dynamics():
    architecture = Architecture.load("examples/dev_robot_cell.json")
    parent = architecture.compile_all()[0]
    child = parent.attenuate(capability_id="child", parameter=Interval(0.2, 0.7))
    plant = Plant1D(a=-1.2, b=-0.7, disturbance=Interval(-0.1, 0.1))
    assert monotonicity_violations(
        plant, architecture.initial_state, parent, child, horizon=12
    ) == []


def test_seeded_counterexample_smoke_search():
    parent = Architecture.load("examples/dev_tank.json").compile_all()[0]
    outcome = randomized_counterexample_search(parent, seed=7, cases=100, horizon=6)
    assert outcome["violations"] == []


def test_empty_action_scope_has_no_postinitial_actuation_reachability():
    architecture = Architecture.load("examples/dev_tank.json")
    parent = architecture.compile_all()[0]
    child = parent.attenuate(capability_id="empty", actions=set())
    reachable = reachable_intervals_1d(
        architecture.plant, architecture.initial_state, child, horizon=3
    )
    assert reachable == [architecture.initial_state, None, None, None]
    assert monotonicity_violations(
        architecture.plant,
        architecture.initial_state,
        parent,
        child,
        horizon=3,
    ) == []
