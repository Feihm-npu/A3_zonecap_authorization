from __future__ import annotations

"""Table-to-scope and request generation for the frozen exp-07 protocol."""

from itertools import product
from typing import Any, Iterator


def _midpoint(low: float, high: float) -> float:
    return low + (high - low) / 2


def _boundary_values(interval: list[float]) -> list[float]:
    low, high = interval
    return [low, _midpoint(low, high), high]


def _history_values(required: list[str]) -> list[list[str]]:
    return [list(required), ["connect", *required, "audit"]]


def expand_scopes(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overlay = document["evaluation_overlay"]
    roots: list[dict[str, Any]] = []
    delegations: list[dict[str, Any]] = []
    for architecture in document["architectures"]:
        asset_by_zone = {zone["id"]: zone["asset"] for zone in architecture["zones"]}
        known_zones = [zone["id"] for zone in architecture["zones"]]
        known_assets = [zone["asset"] for zone in architecture["zones"]]
        known_conduits = [grant["conduit"] for grant in architecture["grants"]]
        grant_pairs = [
            [grant["source_zone"], grant["target_zone"]]
            for grant in architecture["grants"]
        ]
        for grant_index, grant in enumerate(architecture["grants"]):
            grant_id = f"g{grant_index:03d}"
            common = {
                "architecture": architecture["id"],
                "grant_id": grant_id,
                "issuer": f"issuer:{architecture['id']}",
                "source_zone": grant["source_zone"],
                "target_zone": grant["target_zone"],
                "conduits": [grant["conduit"]],
                "assets": [asset_by_zone[grant["target_zone"]]],
                "known_zones": known_zones,
                "known_assets": known_assets,
                "known_conduits": known_conduits,
                "grant_pairs": grant_pairs,
            }
            root = {
                **common,
                "scope_id": f"{architecture['id']}:{grant_id}:d0",
                "parent_scope_id": None,
                "depth": 0,
                "subject": f"subject:{architecture['id']}:{grant_id}:d0",
                "actions": list(overlay["actions"]),
                "parameter": list(overlay["parameter"]),
                "ticks": list(overlay["ticks"]),
                "modes": list(overlay["modes"]),
                "required_sequence": list(overlay["required_sequence"]),
            }
            depth1 = {
                **common,
                "scope_id": f"{architecture['id']}:{grant_id}:d1",
                "parent_scope_id": root["scope_id"],
                "depth": 1,
                "subject": f"subject:{architecture['id']}:{grant_id}:d1",
                "actions": ["read"],
                "parameter": [10, 90],
                "ticks": [110, 190],
                "modes": ["normal"],
                "required_sequence": ["authenticate", "authorize"],
            }
            depth2 = {
                **common,
                "scope_id": f"{architecture['id']}:{grant_id}:d2",
                "parent_scope_id": depth1["scope_id"],
                "depth": 2,
                "subject": f"subject:{architecture['id']}:{grant_id}:d2",
                "actions": ["read"],
                "parameter": [25, 75],
                "ticks": [125, 175],
                "modes": ["normal"],
                "required_sequence": ["authenticate", "authorize", "inspect"],
            }
            roots.append(root)
            delegations.extend((depth1, depth2))
    return roots, delegations


def _different(items: list[str], current: str, fallback: str) -> str:
    return next((item for item in items if item != current), fallback)


def _denied_zone_mutation(scope: dict[str, Any], field: str) -> str:
    granted = {tuple(pair) for pair in scope["grant_pairs"]}
    source = scope["source_zone"]
    target = scope["target_zone"]
    if field == "source_zone":
        return next(
            (
                candidate
                for candidate in scope["known_zones"]
                if candidate != source and (candidate, target) not in granted
            ),
            "outside_source_zone",
        )
    return next(
        (
            candidate
            for candidate in scope["known_zones"]
            if candidate != target and (source, candidate) not in granted
        ),
        "outside_target_zone",
    )


def _mutations(scope: dict[str, Any], request: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    low, high = scope["parameter"]
    tick_low, tick_high = scope["ticks"]
    action_mutation = "write" if scope["depth"] > 0 else "outside_action"
    mode_mutation = "maintenance" if scope["depth"] > 0 else "emergency"
    values: list[tuple[str, str, Any]] = [
        ("subject", "subject", "unauthorized_subject"),
        ("source_zone", "source_zone", _denied_zone_mutation(scope, "source_zone")),
        ("target_zone", "target_zone", _denied_zone_mutation(scope, "target_zone")),
        (
            "conduit",
            "conduit",
            _different(scope["known_conduits"], scope["conduits"][0], "undefined_conduit"),
        ),
        (
            "asset",
            "asset",
            _different(scope["known_assets"], scope["assets"][0], "outside_asset"),
        ),
        ("action", "action", action_mutation),
        ("parameter_low", "value", low - 1),
        ("parameter_high", "value", high + 1),
        ("tick_low", "tick", tick_low - 1),
        ("tick_high", "tick", tick_high + 1),
        ("mode", "mode", mode_mutation),
        ("history", "history", []),
    ]
    mutations: list[tuple[str, dict[str, Any]]] = []
    for mutation_name, field, value in values:
        changed = dict(request)
        changed[field] = value
        mutations.append((mutation_name, changed))
    return mutations


def generate_cases(scope: dict[str, Any]) -> Iterator[dict[str, Any]]:
    combinations = product(
        scope["assets"],
        scope["actions"],
        _boundary_values(scope["parameter"]),
        _boundary_values(scope["ticks"]),
        scope["modes"],
        _history_values(scope["required_sequence"]),
    )
    for valid_index, (asset, action, value, tick, mode, history) in enumerate(combinations):
        request = {
            "subject": scope["subject"],
            "source_zone": scope["source_zone"],
            "target_zone": scope["target_zone"],
            "conduit": scope["conduits"][0],
            "asset": asset,
            "action": action,
            "value": value,
            "tick": tick,
            "mode": mode,
            "history": history,
        }
        case_prefix = f"{scope['scope_id']}:v{valid_index:03d}"
        yield {
            "case_id": f"{case_prefix}:valid",
            "architecture": scope["architecture"],
            "scope_id": scope["scope_id"],
            "depth": scope["depth"],
            "kind": "valid",
            "mutation": None,
            "expected_allow": True,
            "request": request,
        }
        for mutation_name, mutated_request in _mutations(scope, request):
            yield {
                "case_id": f"{case_prefix}:mutation:{mutation_name}",
                "architecture": scope["architecture"],
                "scope_id": scope["scope_id"],
                "depth": scope["depth"],
                "kind": "mutation",
                "mutation": mutation_name,
                "expected_allow": False,
                "request": mutated_request,
            }


def architecture_document(
    architecture: dict[str, Any], root_scopes: list[dict[str, Any]]
) -> dict[str, Any]:
    selected = [scope for scope in root_scopes if scope["architecture"] == architecture["id"]]
    conduits = []
    policies = []
    for scope in selected:
        conduits.append(
            {
                "id": scope["conduits"][0],
                "source": scope["source_zone"],
                "target": scope["target_zone"],
                "assets": scope["assets"],
                "actions": scope["actions"],
                "parameter": scope["parameter"],
            }
        )
        policies.append(
            {
                "id": scope["grant_id"],
                "issuer": scope["issuer"],
                "subject": scope["subject"],
                "source_zone": scope["source_zone"],
                "target_zone": scope["target_zone"],
                "conduit": scope["conduits"][0],
                "assets": scope["assets"],
                "actions": scope["actions"],
                "parameter": scope["parameter"],
                "ticks": scope["ticks"],
                "modes": scope["modes"],
                "required_sequence": scope["required_sequence"],
            }
        )
    return {
        "name": architecture["id"],
        "zones": [zone["id"] for zone in architecture["zones"]],
        "conduits": conduits,
        "policies": policies,
        "plant_1d": {
            "a": 1,
            "b": 1,
            "disturbance": [0, 0],
            "initial_state": [0, 0],
        },
        "source_basis": architecture["source_file"],
        "evidence_scope": "held-out source table plus locked evaluation overlay",
    }
