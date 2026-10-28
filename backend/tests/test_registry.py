"""Tool registry behavior and security-boundary tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field

from jarvis.tools.audit import AuditLogger
from jarvis.tools.base import BaseTool
from jarvis.tools.errors import ToolErrorCode
from jarvis.tools.policy import PermissionPolicy, RiskLevel
from jarvis.tools.registry import ToolRegistry


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1)
    token: str | None = None


class EchoOutput(BaseModel):
    value: str


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo a value."
    input_model = EchoInput
    output_model = EchoOutput
    risk_level = RiskLevel.READ

    async def execute(self, params: BaseModel) -> BaseModel:
        typed_params = cast(EchoInput, params)
        return EchoOutput(value=typed_params.value)


class LowTool(EchoTool):
    name = "low_echo"
    risk_level = RiskLevel.LOW


class ConfirmTool(EchoTool):
    name = "confirm_echo"
    risk_level = RiskLevel.CONFIRM
    calls = 0

    async def execute(self, params: BaseModel) -> BaseModel:
        type(self).calls += 1
        return await super().execute(params)


class SlowTool(EchoTool):
    name = "slow_echo"
    timeout_seconds = 0.01

    async def execute(self, params: BaseModel) -> BaseModel:
        await asyncio.sleep(0.2)
        return await super().execute(params)


class FailTool(EchoTool):
    name = "fail_echo"

    async def execute(self, params: BaseModel) -> BaseModel:
        raise RuntimeError("sensitive internal failure detail")


class BadOutput(BaseModel):
    wrong: str = "wrong"


class BadOutputTool(EchoTool):
    name = "bad_output"

    async def execute(self, params: BaseModel) -> BaseModel:
        return BadOutput()


@pytest.fixture
def audit_logger(tmp_path: Path) -> AuditLogger:
    logger = AuditLogger(tmp_path / "audit.jsonl")
    asyncio.run(logger.ensure_ready())
    return logger


@pytest.fixture
def registry(audit_logger: AuditLogger) -> ToolRegistry:
    ConfirmTool.calls = 0
    return ToolRegistry(
        tools=[
            EchoTool(),
            LowTool(),
            ConfirmTool(),
            SlowTool(),
            FailTool(),
            BadOutputTool(),
        ],
        policy=PermissionPolicy(),
        audit_logger=audit_logger,
    )


def read_audit(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_list_tools_returns_schemas(registry: ToolRegistry) -> None:
    tools = registry.list_tools()

    names = [tool.name for tool in tools]
    assert names == sorted(names)
    assert "echo" in names
    echo = next(tool for tool in tools if tool.name == "echo")
    assert echo.risk_level is RiskLevel.READ
    assert echo.input_schema["properties"]["value"]["minLength"] == 1
    assert echo.output_schema["title"] == "EchoOutput"


def test_duplicate_tool_names_are_rejected(audit_logger: AuditLogger) -> None:
    with pytest.raises(ValueError, match="Duplicate tool name"):
        ToolRegistry(
            tools=[EchoTool(), EchoTool()],
            policy=PermissionPolicy(),
            audit_logger=audit_logger,
        )


def test_read_tool_executes_and_writes_audit_record(
    registry: ToolRegistry,
    audit_logger: AuditLogger,
) -> None:
    result = asyncio.run(
        registry.execute("echo", {"value": "hello", "token": "super-secret-value"})
    )

    assert result.ok is True
    assert result.data == {"value": "hello"}
    assert result.audit_id
    assert result.audit_recorded is True

    records = read_audit(audit_logger.path)
    assert len(records) == 1
    record = records[0]
    assert record["tool"] == "echo"
    assert record["decision"] == "allow"
    assert record["ok"] is True
    assert record["arguments"]["value"] == "hello"
    assert record["arguments"]["token"] == "[REDACTED]"
    assert "super-secret-value" not in audit_logger.path.read_text(encoding="utf-8")


def test_unknown_tool_returns_not_found(
    registry: ToolRegistry,
    audit_logger: AuditLogger,
) -> None:
    result = asyncio.run(registry.execute("missing", {}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.NOT_FOUND
    records = read_audit(audit_logger.path)
    assert records[-1]["decision"] == "not_found"


def test_invalid_input_returns_structured_error(
    registry: ToolRegistry,
    audit_logger: AuditLogger,
) -> None:
    result = asyncio.run(registry.execute("echo", {"value": ""}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.INVALID_INPUT
    assert result.error.details
    assert result.error.details[0]["location"] == "value"
    records = read_audit(audit_logger.path)
    assert records[-1]["error_code"] == "invalid_input"


def test_low_risk_tool_is_denied_by_default(registry: ToolRegistry) -> None:
    result = asyncio.run(registry.execute("low_echo", {"value": "hello"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED


def test_confirm_tool_is_not_executed_without_confirmation(
    registry: ToolRegistry,
    audit_logger: AuditLogger,
) -> None:
    result = asyncio.run(registry.execute("confirm_echo", {"value": "hello"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.PERMISSION_DENIED
    assert ConfirmTool.calls == 0
    records = read_audit(audit_logger.path)
    assert records[-1]["decision"] == "require_confirmation"


def test_timeout_is_reported(registry: ToolRegistry) -> None:
    result = asyncio.run(registry.execute("slow_echo", {"value": "hello"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.TIMEOUT


def test_execution_failure_does_not_leak_internal_detail(
    registry: ToolRegistry,
) -> None:
    result = asyncio.run(registry.execute("fail_echo", {"value": "hello"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.EXECUTION_FAILED
    assert "sensitive internal failure detail" not in result.error.message


def test_invalid_tool_output_is_rejected(registry: ToolRegistry) -> None:
    result = asyncio.run(registry.execute("bad_output", {"value": "hello"}))

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.EXECUTION_FAILED
