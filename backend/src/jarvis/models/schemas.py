"""Shared model-provider and chat schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..tools.models import ToolResult


class ProviderName(StrEnum):
    """Supported model providers."""

    GEMINI = "gemini"
    OLLAMA = "ollama"


class ChatRole(StrEnum):
    """Roles used in provider-neutral chat history."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A normalized function/tool call requested by a model."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """A provider-neutral chat message."""

    role: ChatRole
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class TokenUsage(BaseModel):
    """Provider-neutral token accounting for one model request."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    def merged(self, other: TokenUsage) -> TokenUsage:
        """Return combined usage across a multi-step turn."""

        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ModelResponse(BaseModel):
    """Normalized model output."""

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)


class ProviderHealth(BaseModel):
    """Result of a provider configuration or reachability check."""

    available: bool
    detail: str | None = None


class ProviderInfo(BaseModel):
    """Public, non-secret provider metadata."""

    name: ProviderName
    model: str
    configured: bool
    available: bool
    detail: str | None = None


class ModelStatus(BaseModel):
    """Current provider selection and health."""

    active_provider: ProviderName
    default_provider: ProviderName
    fallback_enabled: bool
    providers: list[ProviderInfo]


class ModelSelectionRequest(BaseModel):
    """Runtime model-provider selection."""

    provider: ProviderName


class RoutedCompletion(BaseModel):
    """A model completion plus routing metadata."""

    provider: ProviderName
    response: ModelResponse
    fallback_used: bool


class ChatRequest(BaseModel):
    """User request sent to the orchestrator."""

    message: str = Field(min_length=1, max_length=8000)
    provider: ProviderName | None = None
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)


class ChatResponse(BaseModel):
    """Truthful orchestration result, including execution evidence."""

    reply: str
    provider: ProviderName
    providers_used: list[ProviderName]
    fallback_used: bool
    tool_results: list[ToolResult]
    execution_verified: bool | None
    iterations: int
    conversation_id: str
    warnings: list[str] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)


class UsageSnapshot(BaseModel):
    """Local daily token budget state for one provider."""

    provider: ProviderName
    date: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    budget_tokens: int
    remaining_tokens: int
    percent_used: float
    scope: Literal["local"] = "local"
    note: str
