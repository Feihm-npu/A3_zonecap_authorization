from __future__ import annotations

from dataclasses import dataclass

from .engine import PolicyEngine
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


@dataclass(frozen=True)
class ExecutionOutcome:
    decision: Decision
    emitted: PhysicalAction | None
    fail_closed: bool = False


@dataclass
class BoundedEffectExecutor:
    """Bind effects and terminate unresolved deferrals without emitting.

    ``PolicyEngine`` remains a pure one-request decision function. This adapter
    owns the state needed by a deployment: consecutive deferrals, a fixed
    deferral bound, and fail-closed handling of an invalid physical binding.
    """

    binding: EffectBinding
    max_deferrals: int
    consecutive_deferrals: int = 0
    timed_out: bool = False

    def __post_init__(self) -> None:
        if self.max_deferrals < 0:
            raise ValueError("max_deferrals must be non-negative")

    @staticmethod
    def _denial(reason: str) -> Decision:
        return Decision(Effect.DENY, reason)

    def apply(
        self,
        capability: Capability,
        request: ActionRequest,
        decision: Decision,
    ) -> ExecutionOutcome:
        if decision.effect is Effect.DEFER:
            if self.timed_out or self.consecutive_deferrals >= self.max_deferrals:
                self.timed_out = True
                return ExecutionOutcome(
                    self._denial("defer approval/context timeout"),
                    None,
                    fail_closed=True,
                )
            self.consecutive_deferrals += 1
        else:
            self.consecutive_deferrals = 0
            self.timed_out = False

        try:
            emitted = self.binding.emitted_action(capability, request, decision)
        except EffectContractError as error:
            return ExecutionOutcome(
                self._denial(f"effect binding rejected: {error}"),
                None,
                fail_closed=True,
            )
        return ExecutionOutcome(decision, emitted)

    def evaluate(
        self,
        engine: PolicyEngine,
        capability: Capability,
        request: ActionRequest,
        *,
        rewrite_out_of_range: bool = True,
    ) -> ExecutionOutcome:
        decision = engine.evaluate(
            capability,
            request,
            rewrite_out_of_range=rewrite_out_of_range,
        )
        return self.apply(capability, request, decision)
