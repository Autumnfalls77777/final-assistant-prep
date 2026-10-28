"""Pydantic models exposed by the tool registry and API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .errors import ToolErrorCode
from .policy import RiskLevel


class ToolError(BaseModel):
    """Safe, structured error information for a failed tool call."""

    code: ToolErrorCode
    message: str
    details: list[dict[str, str]] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Result returned by every tool invocation."""

    ok: bool
    tool: str
    data: dict[str, Any] | None = None
    error: ToolError | None = None
    duration_ms: float
    audit_id: str
    audit_recorded: bool = True


class ToolInfo(BaseModel):
    """Tool metadata and schemas for discovery."""

    name: str
    description: str
    risk_level: RiskLevel
    timeout_seconds: float
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
