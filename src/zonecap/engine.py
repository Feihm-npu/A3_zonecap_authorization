from __future__ import annotations

from .models import ActionRequest, Capability, Decision, Effect


def _is_subsequence(required: tuple[str, ...], history: tuple[str, ...]) -> bool:
    if not required:
        return True
    cursor = 0
    for event in history:
        if event == required[cursor]:
            cursor += 1
            if cursor == len(required):
                return True
    return False


class PolicyEngine:
    """Reference semantics for five policy effects.

    The engine is deliberately fail-closed. REWRITE never emits a value outside the
    presented capability. ATTENUATE returns a child capability and does not execute
    the request; a caller must re-submit under the child token.
    """

    def evaluate(
        self,
        capability: Capability,
        request: ActionRequest,
        *,
        rewrite_out_of_range: bool = True,
    ) -> Decision:
        if not request.context_complete:
            return Decision(Effect.DEFER, "required runtime context is unavailable")
        if request.high_risk:
            return Decision(Effect.DEFER, "high-risk request requires human approval")

        structural_checks = (
            (request.subject == capability.subject, "subject mismatch"),
            (request.source_zone == capability.source_zone, "source-zone mismatch"),
            (request.target_zone == capability.target_zone, "target-zone mismatch"),
            (request.conduit in capability.conduits, "conduit mismatch"),
            (request.asset in capability.assets, "asset mismatch"),
            (request.action in capability.actions, "action mismatch"),
            (capability.ticks.contains(request.tick), "outside time window"),
            (request.mode in capability.modes, "mode not authorized"),
            (
                _is_subsequence(capability.required_sequence, request.history),
                "pre-action sequence unsatisfied",
            ),
        )
        for passed, reason in structural_checks:
            if not passed:
                return Decision(Effect.DENY, reason)

        if request.runtime_parameter is not None:
            effective = capability.parameter.intersection(request.runtime_parameter)
            if effective is None:
                return Decision(Effect.DENY, "runtime envelope and token do not overlap")
            if effective != capability.parameter:
                child = capability.attenuate(
                    capability_id=f"{capability.capability_id}:runtime",
                    parameter=effective,
                )
                return Decision(
                    Effect.ATTENUATE,
                    "live physical context requires a narrower parameter envelope",
                    derived_capability=child,
                )

        if not capability.parameter.contains(request.value):
            if not rewrite_out_of_range:
                return Decision(Effect.DENY, "parameter outside token envelope")
            rewritten = capability.parameter.clamp(request.value)
            if not capability.parameter.contains(rewritten):
                raise AssertionError("authority-preserving rewrite invariant failed")
            return Decision(
                Effect.REWRITE,
                "parameter rewritten to the nearest authorized boundary",
                rewritten_value=rewritten,
            )

        return Decision(Effect.ALLOW, "request satisfies the effective capability")

