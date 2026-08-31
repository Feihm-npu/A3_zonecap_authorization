import pytest

from zonecap.effects import EffectBinding, EffectContractError
from zonecap.engine import PolicyEngine
from zonecap.exp04 import _capabilities, _request


def test_safe_effect_binding_emits_allow_rewrite_and_hold_inside_child():
    _, child = _capabilities()
    engine = PolicyEngine()
    binding = EffectBinding(hold_operation="set", hold_value=0.0)
    for request in (_request(), _request(value=0.8), _request(high_risk=True)):
        decision = engine.evaluate(child, request)
        action = binding.emitted_action(child, request, decision)
        assert action.operation in child.actions
        assert child.parameter.contains(action.value)


def test_effect_binding_rejects_unauthorized_hold():
    _, child = _capabilities()
    request = _request(high_risk=True)
    decision = PolicyEngine().evaluate(child, request)
    with pytest.raises(EffectContractError, match="outside the capability"):
        EffectBinding(hold_operation="set", hold_value=-1.0).emitted_action(
            child, request, decision
        )
