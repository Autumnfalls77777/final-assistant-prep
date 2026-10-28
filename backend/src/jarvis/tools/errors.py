"""Structured tool error codes."""

from __future__ import annotations

from enum import StrEnum


class ToolErrorCode(StrEnum):
    """Stable error codes returned by the tool registry."""

    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    EXECUTION_FAILED = "execution_failed"
