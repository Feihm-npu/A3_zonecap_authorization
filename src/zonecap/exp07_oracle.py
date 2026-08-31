from __future__ import annotations

"""Independent table oracle for exp-07.

This module intentionally uses only the Python standard library.  It evaluates
plain dictionaries and does not import the compiler, runtime engine, or token
model used by the implementation under test.
"""

from typing import Any, Iterable


def sequence_satisfied(required: Iterable[str], history: Iterable[str]) -> bool:
    required_items = tuple(required)
    if not required_items:
        return True
    cursor = 0
    for event in history:
        if event == required_items[cursor]:
            cursor += 1
            if cursor == len(required_items):
                return True
    return False


def allows(scope: dict[str, Any], request: dict[str, Any]) -> bool:
    parameter_low, parameter_high = scope["parameter"]
    tick_low, tick_high = scope["ticks"]
    return all(
        (
            request["subject"] == scope["subject"],
            request["source_zone"] == scope["source_zone"],
            request["target_zone"] == scope["target_zone"],
            request["conduit"] in scope["conduits"],
            request["asset"] in scope["assets"],
            request["action"] in scope["actions"],
            parameter_low <= request["value"] <= parameter_high,
            tick_low <= request["tick"] <= tick_high,
            request["mode"] in scope["modes"],
            sequence_satisfied(scope["required_sequence"], request["history"]),
        )
    )


def allows_with_ignored_check(
    scope: dict[str, Any], request: dict[str, Any], ignored: str
) -> bool:
    """Diagnostic mutant used only by the registered too-good-result audit."""

    parameter_low, parameter_high = scope["parameter"]
    tick_low, tick_high = scope["ticks"]
    checks = {
        "subject": request["subject"] == scope["subject"],
        "source_zone": request["source_zone"] == scope["source_zone"],
        "target_zone": request["target_zone"] == scope["target_zone"],
        "conduit": request["conduit"] in scope["conduits"],
        "asset": request["asset"] in scope["assets"],
        "action": request["action"] in scope["actions"],
        "parameter": parameter_low <= request["value"] <= parameter_high,
        "time": tick_low <= request["tick"] <= tick_high,
        "mode": request["mode"] in scope["modes"],
        "sequence": sequence_satisfied(
            scope["required_sequence"], request["history"]
        ),
    }
    if ignored not in checks:
        raise KeyError(f"unknown ignored check: {ignored}")
    return all(value for name, value in checks.items() if name != ignored)
