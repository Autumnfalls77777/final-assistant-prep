"""Validated tool registry with policy enforcement, timeouts, and auditing."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from .audit import AuditEntry, AuditLogger, sanitize_arguments
from .base import BaseTool
from .errors import ToolErrorCode
from .models import ToolError, ToolInfo, ToolResult
from .policy import PermissionDecision, PermissionPolicy

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Owns registered tools and the execution boundary around them."""

    def __init__(
        self,
        tools: Iterable[BaseTool],
        policy: PermissionPolicy,
        audit_logger: AuditLogger,
    ) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool
        self._policy = policy
        self.audit_logger = audit_logger

    def list_tools(self) -> list[ToolInfo]:
        """Return deterministic tool metadata for discovery."""

        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                risk_level=tool.risk_level,
                timeout_seconds=tool.timeout_seconds,
                input_schema=tool.input_model.model_json_schema(),
                output_schema=tool.output_model.model_json_schema(),
            )
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def get_tool(self, name: str) -> BaseTool | None:
        """Return a registered tool by name, if present."""

        return self._tools.get(name)

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> ToolResult:
        """Validate, authorize, execute, and audit one tool invocation."""

        audit_id = uuid4().hex
        started = perf_counter()
        raw_arguments = dict(arguments or {})
        tool = self._tools.get(name)
        risk_level: str | None = None
        decision = "not_found"

        if tool is None:
            result = self._failure(name, ToolErrorCode.NOT_FOUND, f"Unknown tool: {name}")
        else:
            risk_level = tool.risk_level.value
            permission = self._policy.evaluate(tool.risk_level)
            decision = permission.value
            if permission is PermissionDecision.ALLOW:
                result = await self._run_tool(tool, raw_arguments)
            else:
                result = self._permission_failure(tool.name, permission)

        duration_ms = round((perf_counter() - started) * 1000, 3)
        result = result.model_copy(update={"duration_ms": duration_ms, "audit_id": audit_id})

        audit_recorded = True
        try:
            await self.audit_logger.record(
                AuditEntry(
                    timestamp=datetime.now(UTC),
                    audit_id=audit_id,
                    tool=name,
                    risk_level=risk_level,
                    decision=decision,
                    ok=result.ok,
                    error_code=result.error.code.value if result.error else None,
                    duration_ms=duration_ms,
                    arguments=sanitize_arguments(raw_arguments),
                )
            )
        except OSError:
            audit_recorded = False
            logger.exception(
                "Failed to write audit record audit_id=%s tool=%s",
                audit_id,
                name,
            )

        return result.model_copy(update={"audit_recorded": audit_recorded})

    async def _run_tool(
        self,
        tool: BaseTool,
        raw_arguments: dict[str, Any],
    ) -> ToolResult:
        try:
            params = tool.input_model.model_validate(raw_arguments)
        except ValidationError as exc:
            details = [
                {
                    "location": ".".join(str(part) for part in error["loc"]),
                    "message": str(error["msg"]),
                    "type": str(error["type"]),
                }
                for error in exc.errors()
            ]
            return self._failure(
                tool.name,
                ToolErrorCode.INVALID_INPUT,
                f"Invalid arguments for tool '{tool.name}'.",
                details,
            )

        try:
            output = await asyncio.wait_for(
                tool.execute(params),
                timeout=tool.timeout_seconds,
            )
        except TimeoutError:
            return self._failure(
                tool.name,
                ToolErrorCode.TIMEOUT,
                f"Tool exceeded its {tool.timeout_seconds:g}s timeout.",
            )
        except Exception:
            logger.exception("Tool execution failed tool=%s", tool.name)
            return self._failure(
                tool.name,
                ToolErrorCode.EXECUTION_FAILED,
                "Tool execution failed.",
            )

        try:
            validated_output = tool.output_model.model_validate(output)
        except ValidationError:
            logger.exception("Tool returned invalid output tool=%s", tool.name)
            return self._failure(
                tool.name,
                ToolErrorCode.EXECUTION_FAILED,
                "Tool returned invalid output.",
            )

        return ToolResult(
            ok=True,
            tool=tool.name,
            data=validated_output.model_dump(mode="json"),
            duration_ms=0.0,
            audit_id="",
        )

    def _permission_failure(
        self,
        tool_name: str,
        permission: PermissionDecision,
    ) -> ToolResult:
        if permission is PermissionDecision.REQUIRE_CONFIRMATION:
            message = "Tool requires confirmation, but no confirmation channel is available."
        else:
            message = "Tool is not permitted by the current policy."
        return self._failure(tool_name, ToolErrorCode.PERMISSION_DENIED, message)

    @staticmethod
    def _failure(
        tool_name: str,
        code: ToolErrorCode,
        message: str,
        details: list[dict[str, str]] | None = None,
    ) -> ToolResult:
        return ToolResult(
            ok=False,
            tool=tool_name,
            error=ToolError(code=code, message=message, details=details or []),
            duration_ms=0.0,
            audit_id="",
        )
