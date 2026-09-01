from zonecap.effects import BoundedEffectExecutor, EffectBinding
from zonecap.engine import PolicyEngine
from zonecap.exp16 import _capabilities, _request, audit


def test_bounded_executor_times_out_repeated_deferral_without_output():
    _, child = _capabilities()
    executor = BoundedEffectExecutor(EffectBinding("read", 0.0), max_deferrals=2)
    outcomes = [
        executor.evaluate(PolicyEngine(), child, _request(context_complete=False))
        for _ in range(3)
    ]
    assert [outcome.decision.effect.value for outcome in outcomes] == [
        "defer",
        "defer",
        "deny",
    ]
    assert outcomes[-1].fail_closed
    assert outcomes[-1].emitted is None


def test_valid_request_recovers_before_timeout():
    _, child = _capabilities()
    executor = BoundedEffectExecutor(EffectBinding("read", 0.0), max_deferrals=2)
    deferred = executor.evaluate(PolicyEngine(), child, _request(context_complete=False))
    allowed = executor.evaluate(PolicyEngine(), child, _request())
    assert deferred.decision.effect.value == "defer"
    assert allowed.decision.effect.value == "allow"
    assert not allowed.fail_closed


def test_full_sanity_audit_matches_all_registered_patterns():
    cases, counterexamples = audit(
        {"max_deferrals": 2, "unauthorized_rewrite_value": 1.5}
    )
    assert all(case["expectation_matched"] for case in cases.values())
    assert len(counterexamples["registered_premise_removed"]) == 1
