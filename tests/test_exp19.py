from zonecap.exp19 import evaluate, fair_schedule, scenarios


def _config():
    return {
        "approval_timeout_ticks": 2,
        "claim": "C4",
        "delivery_delays": [0, 1, 2],
        "exp": "exp-19",
        "holders": 3,
        "maximum_delivery_delay": 2,
    }


def test_registered_fair_schedules_only_delay_revocation():
    assert fair_schedule(1, 0, 2) == ("revoke_1", "resolve", "tick")
    assert fair_schedule(1, 1, 2) == ("resolve", "revoke_1", "tick")
    assert fair_schedule(1, 2, 2) == ("resolve", "tick", "revoke_1")


def test_scenarios_cover_winner_and_loser_revocation():
    names = {scenario.name for scenario in scenarios()}
    assert "conflict_revoked_winner" in names
    assert "conflict_revoked_loser" in names
    assert "approved_high_risk" in names


def test_delayed_delivery_exposes_issuer_relative_counterexample():
    records, metrics = evaluate(_config())
    assert len(records) == 15
    assert metrics["central_fifo_post_issuance_revocation_executions"] == 0
    assert metrics["adversarial_post_issuance_revocation_executions"] > 0
    assert metrics["violations_by_delay"]["0"][
        "post_issuance_revocation_executions"
    ] == 0
    assert metrics["violations_by_delay"]["1"][
        "post_issuance_revocation_executions"
    ] > 0
    assert metrics["post_delivery_revocation_executions"] == 0
    assert metrics["stale_executions_blocked_by_epoch_fence"] == metrics[
        "adversarial_post_issuance_revocation_executions"
    ]
    assert not metrics["claim_supported_under_delayed_delivery"]

