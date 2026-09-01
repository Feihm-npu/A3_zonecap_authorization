from zonecap.concurrency import ConcurrentState, PendingCommand, symmetry_key
from zonecap.exp18 import converge, negative_control


def test_symmetry_key_erases_only_ordinary_holder_permutation():
    left = ConcurrentState(
        revoked=frozenset({1}),
        pending=(PendingCommand(2, "action_2", 30, False),),
    )
    right = ConcurrentState(
        revoked=frozenset({2}),
        pending=(PendingCommand(1, "action_1", 20, False),),
    )
    assert symmetry_key(left, 3) == symmetry_key(right, 3)
    high_revoked = ConcurrentState(revoked=frozenset({0, 2}))
    assert symmetry_key(left, 3) != symmetry_key(high_revoked, 3)


def test_symmetry_key_preserves_approval_status_correlation():
    left = ConcurrentState(
        revoked=frozenset({1}),
        pending=(
            PendingCommand(
                0,
                "action_0",
                10,
                True,
                approvals=frozenset({1}),
            ),
        ),
    )
    different = ConcurrentState(
        revoked=frozenset({1}),
        pending=(
            PendingCommand(
                0,
                "action_0",
                10,
                True,
                approvals=frozenset({2}),
            ),
        ),
    )
    assert symmetry_key(left, 3) != symmetry_key(different, 3)

    renamed = ConcurrentState(
        revoked=frozenset({2}),
        pending=(
            PendingCommand(
                0,
                "action_0",
                10,
                True,
                approvals=frozenset({2}),
            ),
        ),
    )
    assert symmetry_key(left, 3) == symmetry_key(renamed, 3)


def test_two_holder_graph_converges_and_is_closed():
    result = converge(2, max_depth=20, timeout_ticks=2)
    assert result["converged"]
    assert result["closure_missing_states"] == 0
    assert result["cycle_edges"] > 0
    assert result["canonical_reachable_states"] <= result["exact_reachable_states"]
    assert result["symmetry_classification_mismatches"] == 0
    assert result["post_revocation_executions"] == 0
    assert result["permission_union_violations"] == 0
    assert result["deadlocks"] == 0


def test_deadlock_negative_control_is_detected():
    assert negative_control(timeout_ticks=2)["detected"]
