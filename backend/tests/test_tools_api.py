"""HTTP tool discovery and execution tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from jarvis.config import Settings
from jarvis.main import create_app
from jarvis.tools.audit import AuditLogger
from jarvis.tools.base import BaseTool
from jarvis.tools.policy import PermissionPolicy, RiskLevel
from jarvis.tools.registry import ToolRegistry


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class EchoOutput(BaseModel):
    value: str


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo a value."
    input_model = EchoInput
    output_model = EchoOutput
    risk_level = RiskLevel.READ

    async def execute(self, params: BaseModel) -> BaseModel:
        return EchoOutput(value=cast(EchoInput, params).value)


class ConfirmTool(EchoTool):
    name = "confirm_echo"
    risk_level = RiskLevel.CONFIRM


@pytest.fixture
def api_registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(
        tools=[EchoTool(), ConfirmTool()],
        policy=PermissionPolicy(),
        audit_logger=AuditLogger(tmp_path / "api-audit.jsonl"),
    )


@pytest.fixture
def api_client(settings: Settings, api_registry: ToolRegistry) -> Iterator[TestClient]:
    with TestClient(create_app(settings, registry=api_registry)) as client:
        yield client


def test_list_tools(api_client: TestClient) -> None:
    response = api_client.get("/tools")

    assert response.status_code == 200
    tools = response.json()
    assert {tool["name"] for tool in tools} == {"confirm_echo", "echo"}
    echo = next(tool for tool in tools if tool["name"] == "echo")
    assert echo["risk_level"] == "read"
    assert echo["input_schema"]["title"] == "EchoInput"
    assert "output_schema" in echo


def test_execute_tool_success(api_client: TestClient) -> None:
    response = api_client.post("/tools/echo/execute", json={"value": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tool"] == "echo"
    assert body["data"] == {"value": "hello"}
    assert body["audit_id"]
    assert body["audit_recorded"] is True


def test_execute_invalid_input(api_client: TestClient) -> None:
    response = api_client.post("/tools/echo/execute", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_input"
    assert body["error"]["details"]


def test_execute_unknown_tool(api_client: TestClient) -> None:
    response = api_client.post("/tools/missing/execute", json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_execute_confirmation_required(api_client: TestClient) -> None:
    response = api_client.post("/tools/confirm_echo/execute", json={"value": "hello"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_tool_execution_is_audited(
    api_client: TestClient,
    api_registry: ToolRegistry,
) -> None:
    response = api_client.post("/tools/echo/execute", json={"value": "audited"})
    assert response.status_code == 200

    lines = api_registry.audit_logger.path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert records[-1]["tool"] == "echo"
    assert records[-1]["ok"] is True
    assert records[-1]["arguments"] == {"value": "audited"}


def test_default_registry_is_read_only(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/tools")

    assert response.status_code == 200
    tools = response.json()
    assert {tool["name"] for tool in tools} == {
        "get_battery_status",
        "get_disk_usage",
        "get_system_info",
        "list_processes",
    }
    assert all(tool["risk_level"] == "read" for tool in tools)


def test_default_system_info_tool_executes(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post("/tools/get_system_info/execute", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["os_name"]
    assert body["data"]["python_version"].startswith("3.")
