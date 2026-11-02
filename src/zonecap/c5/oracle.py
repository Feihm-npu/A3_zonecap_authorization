from __future__ import annotations

"""Separate expected-decision oracle for the C5 corpora.

This module uses only the Python standard library.  It evaluates plain
dictionaries produced from the frozen policy table and does not import the
compiler, models, engine, wire format, or reference PEP under test.  Every
corpus chain is well formed, correctly signed, and unrevoked, so the oracle
covers the context, policy, and binding stages; negative controls cover the
other stages.

Expected decision: ``[effect, operation, value, child_low, child_high]``.
"""

from typing import Any


HOLD_OPERATION = "read"


def _sequence_satisfied(required: list[str], history: list[str]) -> bool:
    if not required:
        return True
    cursor = 0
    for event in history:
        if event == required[cursor]:
            cursor += 1
            if cursor == len(required):
                return True
    return False


def _hold(scope: dict[str, Any]) -> list[Any]:
    if HOLD_OPERATION not in scope["actions"]:
        return ["deny", None, None, None, None]
    return ["defer", HOLD_OPERATION, scope["parameter"][0], None, None]


def expected_decision(
    scope: dict[str, Any],
    subject: str,
    request: dict[str, Any],
    context: dict[str, Any] | None,
) -> list[Any]:
    """Five-effect decision for one well-formed, valid-chain step.

    ``scope`` is the effective (leaf) authority with keys ``subject``,
    ``source_zone``, ``target_zone``, ``conduits``, ``assets``, ``actions``,
    ``parameter``, ``ticks``, ``modes``, and ``required_sequence``.
    ``request`` has ``zs``, ``zd``, ``k``, ``a``, ``o``, and ``u``.
    ``context`` is ``None`` when no fresh snapshot exists.
    """

    if context is None or not context["complete"] or context.get("stale", False):
        return _hold(scope)
    if context["high_risk"]:
        return _hold(scope)
    low, high = scope["parameter"]
    tick_low, tick_high = scope["ticks"]
    structural = (
        subject == scope["subject"],
        request["zs"] == scope["source_zone"],
        request["zd"] == scope["target_zone"],
        request["k"] in scope["conduits"],
        request["a"] in scope["assets"],
        request["o"] in scope["actions"],
        tick_low <= context["tick"] <= tick_high,
        context["mode"] in scope["modes"],
        _sequence_satisfied(scope["required_sequence"], context["history"]),
    )
    if not all(structural):
        return ["deny", None, None, None, None]
    envelope = context.get("envelope")
    if envelope is not None:
        effective_low = max(low, envelope[0])
        effective_high = min(high, envelope[1])
        if effective_low > effective_high:
            return ["deny", None, None, None, None]
        if [effective_low, effective_high] != [low, high]:
            return ["attenuate", None, None, effective_low, effective_high]
    value = request["u"]
    if value < low or value > high:
        return ["rewrite", request["o"], min(max(value, low), high), None, None]
    return ["allow", request["o"], value, None, None]


def sint_expected_decision(
    scope: dict[str, Any],
    subject: str,
    request: dict[str, Any],
    context: dict[str, Any],
) -> str:
    """Pinned-SINT resource/action/maximum/expiry projection used by exp-10.

    The non-negative lower domain is invariant; delegated lower bounds,
    zones, conduits, modes, and event histories are not expressible.
    """

    allowed = (
        subject == scope["subject"]
        and request["a"] in scope["assets"]
        and request["o"] in scope["actions"]
        and 0 <= request["u"] <= scope["parameter"][1]
        and context["tick"] <= scope["ticks"][1]
    )
    return "allow" if allowed else "deny"
