import ast
import json
from pathlib import Path

from zonecap.compiler import Architecture
from zonecap.engine import PolicyEngine
from zonecap.exp07_generator import architecture_document, expand_scopes, generate_cases
from zonecap.exp07_oracle import allows
from zonecap.models import ActionRequest, Effect


def _fixture():
    return {
        "evaluation_overlay": {
            "actions": ["read", "write"],
            "parameter": [0, 100],
            "ticks": [100, 200],
            "modes": ["normal", "maintenance"],
            "required_sequence": ["authenticate"],
        },
        "architectures": [
            {
                "id": "fixture",
                "source_file": "fixture.txt",
                "zones": [
                    {"id": "source", "asset": "source_asset"},
                    {"id": "target", "asset": "target_asset"},
                ],
                "grants": [
                    {
                        "source_zone": "source",
                        "target_zone": "target",
                        "conduit": "source_to_target",
                    }
                ],
            }
        ],
    }


def test_oracle_module_has_no_zonecap_dependency():
    path = Path("src/zonecap/exp07_oracle.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name.startswith("zonecap") for name in imports)


def test_generator_emits_full_root_cross_product_and_every_mutation():
    roots, delegations = expand_scopes(_fixture())
    assert len(roots) == 1
    assert len(delegations) == 2
    cases = list(generate_cases(roots[0]))
    assert len(cases) == 72 * 13
    assert sum(case["kind"] == "valid" for case in cases) == 72
    assert {case["mutation"] for case in cases if case["mutation"]} == {
        "subject",
        "source_zone",
        "target_zone",
        "conduit",
        "asset",
        "action",
        "parameter_low",
        "parameter_high",
        "tick_low",
        "tick_high",
        "mode",
        "history",
    }
    assert all(allows(roots[0], case["request"]) == case["expected_allow"] for case in cases)


def test_tiny_fixture_compiler_and_oracle_agree(tmp_path):
    fixture = _fixture()
    roots, _ = expand_scopes(fixture)
    document = architecture_document(fixture["architectures"][0], roots)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    capability = Architecture.load(path).compile_all()[0]
    engine = PolicyEngine()
    for case in generate_cases(roots[0]):
        request = dict(case["request"])
        request["history"] = tuple(request["history"])
        compiler_allows = (
            engine.evaluate(
                capability, ActionRequest(**request), rewrite_out_of_range=False
            ).effect
            is Effect.ALLOW
        )
        assert compiler_allows == allows(roots[0], case["request"])
