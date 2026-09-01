from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class PendingCommand:
    holder: int
    action: str
    value: int
    high_risk: bool
    approvals: frozenset[int] = frozenset()
    age: int = 0


@dataclass(frozen=True)
class ConcurrentState:
    revoked: frozenset[int] = frozenset()
    pending: tuple[PendingCommand, ...] = ()


def event_alphabet(holders: int) -> tuple[str, ...]:
    return tuple(
        [*(f"submit_{i}" for i in range(holders))]
        + [*(f"revoke_{i}" for i in range(holders))]
        + [*(f"approve_{i}" for i in range(holders))]
        + ["resolve", "tick"]
    )


def command_for(holder: int) -> PendingCommand:
    return PendingCommand(
        holder=holder,
        action=f"action_{holder}",
        value=10 * (holder + 1),
        high_risk=holder == 0,
    )


def command_authorized(command: PendingCommand) -> bool:
    return (
        command.action == f"action_{command.holder}"
        and command.value == 10 * (command.holder + 1)
    )


def quorum(holders: int) -> int:
    return min(2, holders)


def eligible(command: PendingCommand, holders: int) -> bool:
    return not command.high_risk or len(command.approvals) >= quorum(holders)


def deadlocked(state: ConcurrentState, holders: int, timeout_ticks: int) -> bool:
    if not state.pending:
        return False
    for command in state.pending:
        if command.holder in state.revoked:
            continue
        if eligible(command, holders):
            return False
        if command.high_risk and command.age < timeout_ticks:
            return False
    return True


def transition(
    state: ConcurrentState,
    event: str,
    *,
    holders: int,
    timeout_ticks: int,
) -> tuple[ConcurrentState, dict[str, Any]]:
    alphabet = event_alphabet(holders)
    if event not in alphabet:
        raise ValueError(f"unknown event: {event}")
    pending = list(state.pending)
    revoked = set(state.revoked)
    executed: PendingCommand | None = None
    expected_winner: int | None = None
    timeout_count = 0
    changed = False

    kind, _, suffix = event.partition("_")
    if kind == "submit":
        holder = int(suffix)
        if holder not in revoked and all(item.holder != holder for item in pending):
            pending.append(command_for(holder))
            pending.sort(key=lambda item: item.holder)
            changed = True
    elif kind == "revoke":
        holder = int(suffix)
        if holder not in revoked:
            changed = True
        revoked.add(holder)
        retained = [item for item in pending if item.holder != holder]
        changed = changed or len(retained) != len(pending)
        pending = retained
    elif kind == "approve":
        approver = int(suffix)
        updated = []
        for command in pending:
            if command.high_risk and approver not in command.approvals:
                command = replace(
                    command, approvals=command.approvals | frozenset({approver})
                )
                changed = True
            updated.append(command)
        pending = updated
    elif event == "tick":
        updated = []
        for command in pending:
            if command.high_risk and not eligible(command, holders):
                aged = replace(command, age=command.age + 1)
                if aged.age >= timeout_ticks:
                    timeout_count += 1
                    changed = True
                    continue
                command = aged
                changed = True
            updated.append(command)
        pending = updated
    elif event == "resolve":
        candidates = [
            command
            for command in pending
            if command.holder not in revoked and eligible(command, holders)
        ]
        if candidates:
            expected_winner = min(command.holder for command in candidates)
            executed = next(
                command for command in candidates if command.holder == expected_winner
            )
            pending = [item for item in pending if item.holder != executed.holder]
            changed = True

    next_state = ConcurrentState(frozenset(revoked), tuple(pending))
    record = {
        "event": event,
        "changed": changed,
        "executed": (
            None
            if executed is None
            else {
                "holder": executed.holder,
                "action": executed.action,
                "value": executed.value,
            }
        ),
        "expected_winner": expected_winner,
        "timeout_count": timeout_count,
        "post_revocation_violation": executed is not None
        and executed.holder in state.revoked,
        "permission_union_violation": executed is not None
        and not command_authorized(executed),
        "deterministic_resolution_violation": executed is not None
        and executed.holder != expected_winner,
        "deadlock": deadlocked(next_state, holders, timeout_ticks),
        "conflict_candidates": sum(
            command.holder not in revoked and eligible(command, holders)
            for command in state.pending
        )
        if event == "resolve"
        else 0,
    }
    return next_state, record
