from zonecap.exp08 import provenance_probes


def _table():
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


def test_source_grant_provenance_probes_change_generated_corpus():
    probes = provenance_probes(_table())
    assert len(probes) == 2
    assert all(probe["passed"] for probe in probes)
    assert {probe["observed"]["case_delta"] for probe in probes} == {1404}
