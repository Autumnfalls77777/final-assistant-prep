"""Primary/fallback routing across model providers."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from ..tools.models import ToolInfo
from .base import ModelProvider
from .errors import ModelProviderError, NoProviderAvailableError
from .schemas import (
    ChatMessage,
    ModelStatus,
    ProviderName,
    RoutedCompletion,
)

logger = logging.getLogger(__name__)


class ModelRouter:
    """Route completions to the selected provider, with optional local fallback."""

    def __init__(
        self,
        providers: Mapping[ProviderName, ModelProvider],
        default_provider: ProviderName,
        fallback_enabled: bool = True,
    ) -> None:
        if default_provider not in providers:
            raise ValueError(f"Default provider is not registered: {default_provider}")
        self._providers = dict(providers)
        self._default_provider = default_provider
        self._active_provider = default_provider
        self._fallback_enabled = fallback_enabled

    @property
    def active_provider(self) -> ProviderName:
        return self._active_provider

    @property
    def default_provider(self) -> ProviderName:
        return self._default_provider

    @property
    def fallback_enabled(self) -> bool:
        return self._fallback_enabled

    def set_active_provider(self, provider: ProviderName) -> None:
        """Select the runtime primary provider."""

        if provider not in self._providers:
            raise ValueError(f"Provider is not registered: {provider}")
        self._active_provider = provider

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
        provider: ProviderName | None = None,
    ) -> RoutedCompletion:
        """Try the selected provider and, for Gemini, the local Ollama fallback."""

        primary = provider or self._active_provider
        attempts: list[ProviderName] = [primary]
        if (
            self._fallback_enabled
            and primary is ProviderName.GEMINI
            and ProviderName.OLLAMA in self._providers
        ):
            attempts.append(ProviderName.OLLAMA)

        errors: list[str] = []
        for name in attempts:
            candidate = self._providers.get(name)
            if candidate is None:
                errors.append(f"{name.value}: provider is not registered.")
                continue
            try:
                response = await candidate.complete(messages, tools)
            except ModelProviderError as exc:
                errors.append(str(exc))
                logger.warning(
                    "Model provider failed provider=%s error=%s",
                    name.value,
                    exc,
                )
                continue
            return RoutedCompletion(
                provider=name,
                response=response,
                fallback_used=name is not primary,
            )

        raise NoProviderAvailableError(errors)

    async def status(self) -> ModelStatus:
        """Return provider configuration and health without exposing credentials."""

        providers = []
        for provider in self._providers.values():
            health = await provider.health()
            providers.append(provider.info(health))
        return ModelStatus(
            active_provider=self._active_provider,
            default_provider=self._default_provider,
            fallback_enabled=self._fallback_enabled,
            providers=providers,
        )
