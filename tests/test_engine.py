from zonecap.compiler import Architecture
from zonecap.engine import PolicyEngine
from zonecap.models import ActionRequest, Effect, Interval


def _request(**updates):
    values = dict(
        subject="operator.alice",
        source_zone="operations",
        target_zone="basic_control",
        conduit="ops_to_basic",
        asset="inlet_valve",
        action="set",
        value=0.5,
        tick=10,
        mode="normal",
    )
    values.update(updates)
    return ActionRequest(**values)


def test_all_five_effects_are_reachable():
    cap = Architecture.load("examples/dev_tank.json").compile_all()[0]
    engine = PolicyEngine()
    assert engine.evaluate(cap, _request()).effect is Effect.ALLOW
    assert engine.evaluate(cap, _request(mode="shutdown")).effect is Effect.DENY
    assert engine.evaluate(cap, _request(context_complete=False)).effect is Effect.DEFER
    assert engine.evaluate(cap, _request(value=1.5)).effect is Effect.REWRITE
    attenuated = engine.evaluate(
        cap, _request(runtime_parameter=Interval(0.0, 0.4), value=0.3)
    )
    assert attenuated.effect is Effect.ATTENUATE
    assert attenuated.derived_capability.parameter == Interval(0.0, 0.4)


def test_rewrite_is_authority_preserving():
    cap = Architecture.load("examples/dev_tank.json").compile_all()[0]
    decision = PolicyEngine().evaluate(cap, _request(value=100.0))
    assert decision.effect is Effect.REWRITE
    assert cap.parameter.contains(decision.rewritten_value)

