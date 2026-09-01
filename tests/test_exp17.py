from zonecap.concurrency import ConcurrentState, deadlocked, transition
from zonecap.exp17 import explore, mutation_audit


def _run(state, events, holders=2, timeout=2):
    records = []
    for event in events:
        state, record = transition(
            state, event, holders=holders, timeout_ticks=timeout
        )
        records.append(record)
    return state, records


def test_revocation_removes_pending_and_prevents_execution():
    state, records = _run(
        ConcurrentState(), ["submit_0", "revoke_0", "approve_0", "approve_1", "resolve"]
    )
    assert 0 in state.revoked
    assert records[-1]["executed"] is None
    assert not records[-1]["post_revocation_violation"]


def test_conflict_resolution_chooses_atomic_minimum_eligible_holder():
    _, records = _run(
        ConcurrentState(),
        ["submit_0", "submit_1", "approve_0", "approve_1", "resolve"],
    )
    execution = records[-1]
    assert execution["executed"] == {"holder": 0, "action": "action_0", "value": 10}
    assert not execution["permission_union_violation"]
    assert not execution["deterministic_resolution_violation"]


def test_high_risk_request_times_out_without_deadlock():
    state, records = _run(ConcurrentState(), ["submit_0", "tick", "tick"])
    assert not state.pending
    assert records[-1]["timeout_count"] == 1
    assert not deadlocked(state, holders=2, timeout_ticks=2)


def test_small_exhaustive_model_reaches_conflicts_and_kills_mutants():
    record = explore(3, horizon=3, timeout_ticks=2)
    assert record["words"] == 1 + 11 + 121 + 1331
    assert record["unique_conflict_states"] > 0
    audit = mutation_audit([record])
    assert audit["killed"] == audit["mutants"]
