import json

import pytest

from zonecap.compiler import Architecture, CompilationError
from zonecap.models import Interval


def test_development_architectures_compile():
    for path in ("examples/dev_tank.json", "examples/dev_robot_cell.json"):
        capabilities = Architecture.load(path).compile_all()
        assert len(capabilities) == 1


def test_compiler_rejects_zone_conduit_mismatch(tmp_path):
    source = json.loads(open("examples/dev_tank.json", encoding="utf-8").read())
    source["policies"][0]["target_zone"] = "safety"
    fixture = tmp_path / "bad.json"
    fixture.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(CompilationError, match="endpoints"):
        Architecture.load(fixture).compile_all()


def test_attenuation_rejects_widening():
    parent = Architecture.load("examples/dev_tank.json").compile_all()[0]
    with pytest.raises(ValueError, match="parameter interval widened"):
        parent.attenuate(capability_id="bad", parameter=Interval(-1.0, 1.0))


def test_pre_action_refinement_must_extend_parent_sequence():
    parent = Architecture.load("examples/dev_robot_cell.json").compile_all()[0]
    child = parent.attenuate(
        capability_id="good",
        required_sequence=("isolate_cell", "ack_operator", "inspect_guard"),
    )
    assert child.parent_id == parent.capability_id
    with pytest.raises(ValueError, match="pre-action"):
        parent.attenuate(capability_id="bad", required_sequence=("ack_operator",))

