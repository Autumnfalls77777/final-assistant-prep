"""Tool risk levels and permission decisions."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk classification required for every tool."""

    READ = "read"
    LOW = "low"
    CONFIRM = "confirm"
    CRITICAL = "critical"


class PermissionDecision(StrEnum):
    """Result of applying the permission policy to a tool."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


class PermissionPolicy:
    """Phase 1 policy for a local, read-only tool surface.

    READ tools are automatically allowed because they only retrieve local
    system information. LOW tools are denied by default, and CONFIRM/CRITICAL
    tools require a confirmation channel that does not exist yet. This keeps
    consequential actions unavailable until they are explicitly designed and
    approved in a later phase.
    """

    def __init__(self, auto_allowed: frozenset[RiskLevel] | None = None) -> None:
        self._auto_allowed = frozenset({RiskLevel.READ}) if auto_allowed is None else auto_allowed

    @property
    def auto_allowed(self) -> frozenset[RiskLevel]:
        return self._auto_allowed

    def evaluate(self, risk_level: RiskLevel) -> PermissionDecision:
        if risk_level in self._auto_allowed:
            return PermissionDecision.ALLOW
        if risk_level in {RiskLevel.CONFIRM, RiskLevel.CRITICAL}:
            return PermissionDecision.REQUIRE_CONFIRMATION
        return PermissionDecision.DENY
