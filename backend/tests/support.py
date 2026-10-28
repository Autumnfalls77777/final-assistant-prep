"""Shared deterministic test doubles for model and memory tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from jarvis.memory.service import MemoryService
from jarvis.models.base import ModelProvider
from jarvis.models.errors import ProviderUnavailableError
from jarvis.models.schemas import (
    ChatMessage,
    ModelResponse,
    ProviderHealth,
    ProviderName,
)
from jarvis.tools.audit import AuditLogger
from jarvis.tools.base import BaseTool
from jarvis.tools.models import ToolInfo
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


class ConfirmEchoTool(EchoTool):
    name = "confirm_echo"
    risk_level = RiskLevel.CONFIRM


def build_test_registry(
    tmp_path: Path,
    tools: Sequence[BaseTool] | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        tools=list(tools) if tools is not None else [EchoTool()],
        policy=PermissionPolicy(),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
    )


def build_test_memory(tmp_path: Path) -> MemoryService:
    memory = MemoryService(tmp_path / "memory.db")
    memory.initialize()
    return memory


def make_tool_info(name: str = "echo") -> ToolInfo:
    return ToolInfo(
        name=name,
        description="Echo a value.",
        risk_level=RiskLevel.READ,
        timeout_seconds=5.0,
        input_schema={
            "title": "EchoInput",
            "type": "object",
            "properties": {"value": {"type": "string", "title": "Value"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )


class ScriptedProvider(ModelProvider):
    """Provider that returns queued responses or raises queued errors."""

    name = ProviderName.GEMINI

    def __init__(
        self,
        responses: Sequence[ModelResponse | Exception],
        name: ProviderName = ProviderName.GEMINI,
        model: str = "test-model",
        configured: bool = True,
    ) -> None:
        super().__init__(model=model, timeout_seconds=5.0)
        self.name = name
        self._responses = list(responses)
        self._configured = configured
        self._index = 0
        self.seen_messages: list[list[ChatMessage]] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
    ) -> ModelResponse:
        self.seen_messages.append(list(messages))
        if self._index >= len(self._responses):
            raise ProviderUnavailableError(self.name, "No scripted response remains.")
        response = self._responses[self._index]
        self._index += 1
        if isinstance(response, Exception):
            raise response
        return response

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            available=self._configured,
            detail="Configured." if self._configured else "Not configured.",
        )
