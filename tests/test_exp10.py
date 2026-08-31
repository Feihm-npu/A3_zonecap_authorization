from zonecap.exp10 import sint_profile_allows


def _scope():
    return {
        "subject": "holder",
        "assets": ["resource"],
        "actions": ["read"],
        "parameter": [10, 90],
        "ticks": [110, 190],
    }


def _request(**updates):
    request = {
        "subject": "holder",
        "asset": "resource",
        "action": "read",
        "value": 50,
        "tick": 150,
    }
    request.update(updates)
    return request


def test_sint_profile_enforces_resource_action_max_and_expiry():
    scope = _scope()
    assert sint_profile_allows(scope, _request())
    assert not sint_profile_allows(scope, _request(asset="other"))
    assert not sint_profile_allows(scope, _request(action="write"))
    assert not sint_profile_allows(scope, _request(value=91))
    assert not sint_profile_allows(scope, _request(tick=191))


def test_sint_profile_does_not_claim_raised_lower_bounds():
    scope = _scope()
    assert sint_profile_allows(scope, _request(value=9))
    assert sint_profile_allows(scope, _request(tick=109))
    assert not sint_profile_allows(scope, _request(value=-1))
