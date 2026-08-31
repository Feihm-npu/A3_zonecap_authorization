from __future__ import annotations

from dataclasses import dataclass

from .models import ActionRequest, Capability, Decision, Effect


class EffectContractError(ValueError):
    pass


@dataclass(frozen=True)
class PhysicalAction:
    operation: str
    value: float


@dataclass(frozen=True)
class EffectBinding:
    """Bind policy effects to actuation-event semantics.

    DENY and ATTENUATE emit no physical action and therefore create no step in
    an actuation-event horizon. A fixed-tick plant adapter must separately bind
    no-command behavior to a parent-admissible idle input.
    """

    hold_operation: str
    hold_value: float

    def _assert_authorized(
        self, capability: Capability, action: PhysicalAction
    ) -> None:
        if action.operation not in capability.actions:
            raise EffectContractError("emitted operation is outside the capability")
        if not capability.parameter.contains(action.value):
            raise EffectContractError("emitted value is outside the capability")

    def emitted_action(
        self,
        capability: Capability,
        request: ActionRequest,
        decision: Decision,
    ) -> PhysicalAction | None:
        if decision.effect is Effect.ALLOW:
            action = PhysicalAction(request.action, request.value)
        elif decision.effect is Effect.REWRITE:
            if decision.rewritten_value is None:
                raise EffectContractError("REWRITE has no rewritten value")
            action = PhysicalAction(request.action, decision.rewritten_value)
        elif decision.effect is Effect.DEFER:
            action = PhysicalAction(self.hold_operation, self.hold_value)
        elif decision.effect in (Effect.DENY, Effect.ATTENUATE):
            return None
        else:
            raise EffectContractError(f"unrecognized effect: {decision.effect}")
        self._assert_authorized(capability, action)
        return action
