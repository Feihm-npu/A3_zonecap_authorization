from zonecap.exp20 import summarize


def test_summary_separates_queue_approval_from_gateway_execution_check():
    config = {
        "claim": "C4",
        "exp": "exp-20",
        "sint_commit": "pinned",
        "sint_source_hashes": {"a": "hash"},
    }
    raw = {
        "commit": "pinned",
        "sourceHashes": {"a": "hash"},
        "localRevocationTrace": {
            "beforeRevocation": "allow",
            "issuedButNotDelivered": "allow",
            "afterDelivery": "deny",
            "afterDeliveryPolicy": "TOKEN_REVOKED",
        },
        "quorumConflictTrace": {
            "gatewayInitialActions": ["escalate", "escalate"],
            "firstVotesPending": True,
            "approvalCountAfterDuplicate": 1,
            "revokedRequestResolution": "approved",
            "otherRequestResolution": "approved",
            "approvedSameResourceRequests": 2,
            "crossRequestWinner": None,
            "revokedGatewayRecheck": "deny",
            "revokedGatewayRecheckPolicy": "TOKEN_REVOKED",
        },
        "missingApprovalTrace": {
            "timedOut": True,
            "fallbackAction": "deny",
            "pendingAtEnd": 0,
        },
    }
    metrics, comparison = summarize(raw, config)
    assert metrics["issued_not_delivered_allows"] == 1
    assert metrics["post_delivery_revocation_denies"] == 1
    assert metrics["revoked_enqueued_request_approved"] == 1
    assert metrics["revoked_gateway_recheck_denies"] == 1
    assert metrics["same_resource_requests_approved"] == 2
    assert metrics["cross_request_winners"] == 0
    assert comparison["trace_results"]["revoke_pending_approval_atomically"] == "absent"
    assert comparison["trace_results"][
        "same_asset_deterministic_conflict_winner"
    ] == "absent"

