from zonecap.exp21 import case_specs, evaluate_case


def _evaluate(name):
    spec = next(spec for spec in case_specs() if spec[0] == name)
    return evaluate_case(*spec, holders=3, timeout_ticks=2)


def test_duplicate_revoke_is_an_idempotent_noop():
    immediate = _evaluate("immediate_revoke")
    duplicate = _evaluate("duplicate_revoke")
    assert duplicate["changed"] == [True, True, False, False]
    assert duplicate["final_revoked"] == immediate["final_revoked"] == [1]
    assert duplicate["final_pending_holders"] == []
    assert duplicate["execution_order"] == []


def test_equal_priority_uses_holder_id_as_secondary_order():
    result = _evaluate("simultaneous_equal_priority")
    assert result["execution_order"] == [1, 2]
    assert result["conflict_candidate_counts"] == [2, 1]
    assert result["final_pending_holders"] == []


def test_missing_approval_times_out_without_execution_or_deadlock():
    result = _evaluate("permanent_missing_approval")
    assert result["timeouts"] == 1
    assert result["execution_order"] == []
    assert result["final_pending_holders"] == []
    assert result["deadlocks"] == 0

