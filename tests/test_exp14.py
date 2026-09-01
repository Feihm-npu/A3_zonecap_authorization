from zonecap.exp14 import (
    ALPHABET,
    HANDPICKED_PATH,
    ModelState,
    _explore_scope,
    mutation_coverage,
    transition,
)
from zonecap.models import Capability, Interval


def _capabilities():
    parent = Capability(
        capability_id="exp14-parent",
        issuer="issuer",
        subject="parent",
        source_zone="operations",
        target_zone="control",
        conduits=frozenset({"primary"}),
        assets=frozenset({"valve"}),
        actions=frozenset({"read", "write"}),
        parameter=Interval(0, 100),
        ticks=Interval(100, 200),
        modes=frozenset({"normal"}),
        required_sequence=("authenticate",),
    )
    child = parent.attenuate(
        capability_id="exp14-child",
        subject="child",
        actions={"read"},
        parameter=Interval(10, 90),
        ticks=Interval(110, 190),
        required_sequence=("authenticate", "authorize"),
    )
    return parent, child


def test_every_symbol_has_expected_safe_transition():
    parent, child = _capabilities()
    for symbol in ALPHABET:
        _, record = transition(ModelState(child), symbol, parent=parent)
        assert not record["effect_violation"]
        assert not record["attenuation_violation"]
        assert not record["authority_violation"]
        assert not record["nonstutter_violation"]
        assert not record["parent_realizability_violation"]


def test_small_exhaustive_tree_counts_every_word_and_ordered_pair():
    parent, child = _capabilities()
    result = _explore_scope(child, parent, horizon=2)
    assert result["words"] == 1 + 5 + 25
    assert result["transitions"] == 5 + 25
    assert result["ngram_counts"] == {"1": 5, "2": 25, "3": 0}


def test_handpicked_path_misses_registered_pair_mutants():
    parent, child = _capabilities()
    exhaustive = _explore_scope(child, parent, horizon=2)
    handpicked = _explore_scope(child, parent, horizon=5, paths=(HANDPICKED_PATH,))
    audit = mutation_coverage(exhaustive["ngrams"]["2"], handpicked["ngrams"]["2"])
    assert audit["exhaustive_killed"] == 3
    assert audit["handpicked_killed"] == 0
