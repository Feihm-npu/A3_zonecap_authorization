import pytest

from zonecap.exp15 import summarize_effect_coverage, summarize_properties, validate_mapping


def _mapping():
    effects = {
        "allow": {"status": "exact", "projection": "allow"},
        "deny": {"status": "exact", "projection": "deny"},
        "attenuate": {"status": "partial", "projection": "delegate"},
        "rewrite": {"status": "absent", "projection": "N/A"},
        "defer": {"status": "partial", "projection": "escalate"},
    }
    return {
        "systems": {"baseline": {"effects": effects}},
        "properties": [{"property": "p", "baseline": "partial"}],
    }


def test_effect_summary_weights_exact_partial_and_absent_by_observations():
    mapping = _mapping()
    validate_mapping(mapping)
    summary = summarize_effect_coverage(
        mapping,
        {"allow": 2, "deny": 3, "attenuate": 5, "rewrite": 7, "defer": 11},
    )["baseline"]
    assert summary["effect_type_coverage"] == {"exact": 2, "partial": 2, "absent": 1}
    assert summary["weighted_policy_steps"] == {"exact": 5, "partial": 16, "absent": 7}
    assert summary["strict_nonexact_policy_steps"] == 23
    assert summary["unmapped_policy_steps"] == 7
    assert summarize_properties(mapping)["baseline"]["property_status_counts"] == {
        "partial": 1
    }


def test_mapping_rejects_missing_effect_and_invalid_property_status():
    mapping = _mapping()
    del mapping["systems"]["baseline"]["effects"]["defer"]
    with pytest.raises(ValueError, match="incomplete"):
        validate_mapping(mapping)
    mapping = _mapping()
    mapping["properties"][0]["baseline"] = "overclaimed"
    with pytest.raises(ValueError, match="invalid"):
        validate_mapping(mapping)
