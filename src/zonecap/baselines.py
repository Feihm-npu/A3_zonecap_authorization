from __future__ import annotations

from .models import ActionRequest


class StaticRBAC:
    """Deliberately coarse reference: identity/asset/action only."""

    def __init__(self, grants: set[tuple[str, str, str]]) -> None:
        self.grants = grants

    def allows(self, request: ActionRequest) -> bool:
        return (request.subject, request.asset, request.action) in self.grants


class ContextABAC:
    """Reference ABAC: adds zones, mode and time, but no physical envelope/history."""

    def __init__(self, rules: list[dict[str, object]]) -> None:
        self.rules = rules

    def allows(self, request: ActionRequest) -> bool:
        for rule in self.rules:
            if (
                request.subject == rule["subject"]
                and request.asset in rule["assets"]
                and request.action in rule["actions"]
                and request.source_zone == rule["source_zone"]
                and request.target_zone == rule["target_zone"]
                and request.mode in rule["modes"]
                and float(rule["ticks"][0]) <= request.tick <= float(rule["ticks"][1])
            ):
                return True
        return False

