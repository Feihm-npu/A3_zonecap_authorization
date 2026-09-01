from zonecap.exp13 import compare_step, deny_only_effect, mutation_audit


def _step(effect: str, emitted=None):
    return {
        "trace_kind": "test",
        "trace_id": "test",
        "policy_step": 0,
        "rich_effect": effect,
        "rich_emitted": emitted,
        "input_safe": True,
    }


def test_deny_only_preserves_allow_and_maps_every_other_effect_to_deny():
    assert deny_only_effect("allow") == "allow"
    for effect in ("deny", "attenuate", "rewrite", "defer"):
        assert deny_only_effect(effect) == "deny"


def test_only_rewrite_is_a_raw_request_false_block():
    rewritten = compare_step(_step("rewrite", {"operation": "write", "value": 100}))
    assert rewritten["deny_only_false_block"]
    assert rewritten["lost_rewrite_output"]
    for effect in ("allow", "deny", "attenuate", "defer"):
        assert not compare_step(_step(effect))["deny_only_false_block"]


def test_allow_output_is_preserved_and_mutants_are_detected():
    emitted = {"operation": "read", "value": 50}
    allowed = compare_step(_step("allow", emitted))
    assert allowed["deny_only_emitted"] == emitted
    audit = mutation_audit()
    assert audit["mutants"] == 3
    assert audit["killed"] == 3
