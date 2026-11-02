import json
from pathlib import Path

import pytest

from zonecap.c5.corpus import build, load_variant, strict_runtime_envelope
from zonecap.c5.oracle import expected_decision


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    directory = tmp_path_factory.mktemp("c5") / "corpus"
    manifest = build(ROOT, directory)
    return directory, manifest


def test_main_variant_reproduces_exp12_effect_mix(corpus):
    _, manifest = corpus
    main = manifest["variants"]["main"]
    assert main["steps"] == 81648 and main["units"] == 63504
    assert main["expected_effects"] == {
        "allow": 9072, "attenuate": 4536, "defer": 4536, "deny": 49896, "rewrite": 13608,
    }
    assert main["chain_depths"] == {"0": 42336, "1": 22680, "2": 13608, "3": 3024}
    assert manifest["reference_engine_mismatches"] == 0


def test_scaling_and_sint_variants(corpus):
    _, manifest = corpus
    variants = manifest["variants"]
    assert [variants[f"scale_d{depth}"]["steps"] for depth in range(3)] == [936, 234, 234]
    assert variants["sint_subset"]["steps"] == 27216
    assert variants["sint_subset"]["sint_expected"] == {"allow": 4536, "deny": 22680}


def test_corpus_is_bit_reproducible_against_frozen_configs(corpus):
    _, manifest = corpus
    for path in sorted((ROOT / "configs" / "c5").glob("exp*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        assert config["corpus_fingerprint"] == manifest["fingerprint"], path.name


def test_composed_trace_steps_stay_in_one_unit(corpus):
    directory, _ = corpus
    _, steps = load_variant(directory, "main")
    units = {}
    for step in steps:
        units.setdefault(step["unit"], []).append(step["kind"])
    composed = [kinds for kinds in units.values() if len(kinds) > 1]
    assert len(composed) == 4536
    assert all(kinds == ["attenuate", "defer", "allow", "rewrite", "deny"] for kinds in composed)


def test_runtime_envelope_is_strict_and_contains_value():
    assert strict_runtime_envelope([0, 100], 0) == [0, 50.0]
    assert strict_runtime_envelope([0, 100], 100) == [50.0, 100]
    assert strict_runtime_envelope([10, 90], 50.0) == [50.0, 50.0]


def test_oracle_five_effects():
    scope = {
        "subject": "s", "source_zone": "a", "target_zone": "b", "conduits": ["k"],
        "assets": ["v"], "actions": ["read"], "parameter": [10, 90], "ticks": [100, 200],
        "modes": ["normal"], "required_sequence": ["authenticate"],
    }
    request = {"zs": "a", "zd": "b", "k": "k", "a": "v", "o": "read", "u": 50}
    context = {"tick": 150, "mode": "normal", "history": ["authenticate"], "complete": True,
               "high_risk": False, "envelope": None}
    assert expected_decision(scope, "s", request, context) == ["allow", "read", 50, None, None]
    assert expected_decision(scope, "s", {**request, "u": 95}, context) == ["rewrite", "read", 90, None, None]
    assert expected_decision(scope, "x", request, context)[0] == "deny"
    assert expected_decision(scope, "s", request, {**context, "envelope": [10, 50]}) == [
        "attenuate", None, None, 10, 50,
    ]
    assert expected_decision(scope, "s", request, {**context, "complete": False}) == [
        "defer", "read", 10, None, None,
    ]
    assert expected_decision(scope, "s", request, None)[0] == "defer"
