"""Provider interface shared by Gemini and Ollama."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar

from ..tools.models import ToolInfo
from .schemas import (
    ChatMessage,
    ModelResponse,
    ProviderHealth,
    ProviderInfo,
    ProviderName,
)


class ModelProvider(ABC):
    """Base interface for a provider-neutral chat completion."""

    name: ClassVar[ProviderName]

    def __init__(self, model: str, timeout_seconds: float) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        """Whether the provider has the configuration needed to attempt a call."""

        return True

    @abstractmethod
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
    ) -> ModelResponse:
        """Return a normalized completion for the supplied chat history."""

    async def health(self) -> ProviderHealth:
        """Return a safe reachability/configuration status."""

        if self.configured:
            return ProviderHealth(available=True, detail="Configured.")
        return ProviderHealth(available=False, detail="Provider is not configured.")

    def info(self, health: ProviderHealth) -> ProviderInfo:
        """Build public provider metadata without exposing credentials."""

        return ProviderInfo(
            name=self.name,
            model=self.model,
            configured=self.configured,
            available=health.available,
            detail=health.detail,
        )
