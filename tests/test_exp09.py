import pytest

from zonecap.exp07 import _relation_for_capability
from zonecap.exp09 import _widened_candidate
from zonecap.models import Capability, Interval


def _parent():
    return Capability(
        capability_id="parent",
        issuer="issuer",
        subject="subject",
        source_zone="source",
        target_zone="target",
        conduits=frozenset({"conduit"}),
        assets=frozenset({"asset"}),
        actions=frozenset({"read"}),
        parameter=Interval(10, 90),
        ticks=Interval(110, 190),
        modes=frozenset({"normal"}),
        required_sequence=("authenticate", "authorize"),
        delegation_depth=1,
    )


@pytest.mark.parametrize(
    "dimension",
    [
        "zone",
        "conduit",
        "asset",
        "action",
        "parameter",
        "time",
        "mode",
        "pre_action_sequence",
    ],
)
def test_each_registered_widening_is_localized_and_rejected(dimension):
    parent = _parent()
    candidate = _widened_candidate(parent, dimension, 2)
    relation = _relation_for_capability(parent, candidate)
    assert not relation[dimension]
    assert sum(not passed for passed in relation.values()) == 1
    with pytest.raises(ValueError):
        candidate.assert_attenuates(parent)
