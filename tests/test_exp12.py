from zonecap.exp12 import (
    EXPECTED_COMPOSED_ORDER,
    _bounded_deadlocks,
    _strict_runtime_envelope,
    compose_trace,
    negative_control_audit,
)
from zonecap.models import ActionRequest, Capability, Effect, Interval


def _capabilities() -> tuple[Capability, Capability]:
    parent = Capability(
        capability_id="exp12-parent",
        issuer="issuer",
        subject="parent-subject",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary"}),
        assets=frozenset({"valve"}),
        actions=frozenset({"read", "write"}),
        parameter=Interval(0.0, 100.0),
        ticks=Interval(100.0, 200.0),
        modes=frozenset({"normal", "maintenance"}),
        required_sequence=("authenticate",),
    )
    child = parent.attenuate(
        capability_id="exp12-child",
        subject="child-subject",
        actions={"read"},
        parameter=Interval(10.0, 90.0),
        ticks=Interval(110.0, 190.0),
        modes={"normal"},
        required_sequence=("authenticate", "authorize"),
    )
    return parent, child


def _request(value: float = 50.0) -> ActionRequest:
    return ActionRequest(
        subject="child-subject",
        source_zone="operations",
        target_zone="control",
        conduit="primary",
        asset="valve",
        action="read",
        value=value,
        tick=150,
        mode="normal",
        history=("authenticate", "authorize"),
    )


def test_runtime_envelope_is_strict_and_retains_every_registered_boundary():
    _, child = _capabilities()
    for value in (10.0, 50.0, 90.0):
        envelope = _strict_runtime_envelope(child, value)
        assert envelope != child.parameter
        assert envelope.is_subset_of(child.parameter)
        assert envelope.contains(value)


def test_composed_trace_reaches_all_effects_without_registered_violation():
    _, child = _capabilities()
    trace = compose_trace(child, _request(), resolution_bound=2)
    assert trace["effect_order"] == [effect.value for effect in EXPECTED_COMPOSED_ORDER]
    assert len(trace["physical_trace"]) == 3
    assert not trace["effect_order_violations"]
    assert not trace["attenuation_violations"]
    assert not trace["authority_violations"]
    assert not trace["nonstutter_violations"]
    assert not trace["deadlocks"]


def test_deadlock_detector_and_all_registered_negative_controls_fire():
    parent, child = _capabilities()
    assert _bounded_deadlocks([Effect.DEFER], resolution_bound=2)
    audit = negative_control_audit(parent, child, _request(), resolution_bound=2)
    assert audit["mutants"] == 5
    assert audit["killed"] == 5
