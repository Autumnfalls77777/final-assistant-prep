"""Provider routing and fallback tests."""

from __future__ import annotations

import asyncio

import pytest

from jarvis.models.errors import NoProviderAvailableError, ProviderUnavailableError
from jarvis.models.router import ModelRouter
from jarvis.models.schemas import ChatMessage, ChatRole, ModelResponse, ProviderName
from support import ScriptedProvider


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role=ChatRole.USER, content="hello")]


def test_primary_provider_success() -> None:
    gemini = ScriptedProvider([ModelResponse(text="primary")], name=ProviderName.GEMINI)
    router = ModelRouter(
        providers={ProviderName.GEMINI: gemini},
        default_provider=ProviderName.GEMINI,
        fallback_enabled=True,
    )

    result = asyncio.run(router.complete(_messages(), []))

    assert result.provider is ProviderName.GEMINI
    assert result.response.text == "primary"
    assert result.fallback_used is False


def test_gemini_falls_back_to_ollama() -> None:
    gemini = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider([ModelResponse(text="local")], name=ProviderName.OLLAMA)
    router = ModelRouter(
        providers={
            ProviderName.GEMINI: gemini,
            ProviderName.OLLAMA: ollama,
        },
        default_provider=ProviderName.GEMINI,
        fallback_enabled=True,
    )

    result = asyncio.run(router.complete(_messages(), []))

    assert result.provider is ProviderName.OLLAMA
    assert result.response.text == "local"
    assert result.fallback_used is True


def test_both_providers_failing_returns_safe_error() -> None:
    gemini = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.OLLAMA, "Ollama unavailable")],
        name=ProviderName.OLLAMA,
    )
    router = ModelRouter(
        providers={
            ProviderName.GEMINI: gemini,
            ProviderName.OLLAMA: ollama,
        },
        default_provider=ProviderName.GEMINI,
        fallback_enabled=True,
    )

    with pytest.raises(NoProviderAvailableError) as exc_info:
        asyncio.run(router.complete(_messages(), []))

    assert "Gemini unavailable" in str(exc_info.value)
    assert "Ollama unavailable" in str(exc_info.value)


def test_fallback_can_be_disabled() -> None:
    gemini = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider([ModelResponse(text="local")], name=ProviderName.OLLAMA)
    router = ModelRouter(
        providers={
            ProviderName.GEMINI: gemini,
            ProviderName.OLLAMA: ollama,
        },
        default_provider=ProviderName.GEMINI,
        fallback_enabled=False,
    )

    with pytest.raises(NoProviderAvailableError):
        asyncio.run(router.complete(_messages(), []))


def test_switching_to_ollama_does_not_use_gemini_fallback() -> None:
    gemini = ScriptedProvider([ModelResponse(text="cloud")], name=ProviderName.GEMINI)
    ollama = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.OLLAMA, "Ollama unavailable")],
        name=ProviderName.OLLAMA,
    )
    router = ModelRouter(
        providers={
            ProviderName.GEMINI: gemini,
            ProviderName.OLLAMA: ollama,
        },
        default_provider=ProviderName.GEMINI,
        fallback_enabled=True,
    )
    router.set_active_provider(ProviderName.OLLAMA)

    with pytest.raises(NoProviderAvailableError):
        asyncio.run(router.complete(_messages(), []))


def test_status_reports_selection_without_secrets() -> None:
    gemini = ScriptedProvider([], name=ProviderName.GEMINI, configured=True)
    ollama = ScriptedProvider([], name=ProviderName.OLLAMA, configured=False)
    router = ModelRouter(
        providers={
            ProviderName.GEMINI: gemini,
            ProviderName.OLLAMA: ollama,
        },
        default_provider=ProviderName.GEMINI,
        fallback_enabled=True,
    )

    status = asyncio.run(router.status())

    assert status.active_provider is ProviderName.GEMINI
    assert status.default_provider is ProviderName.GEMINI
    assert status.fallback_enabled is True
    assert [provider.name for provider in status.providers] == [
        ProviderName.GEMINI,
        ProviderName.OLLAMA,
    ]
    assert status.providers[1].available is False


def test_unregistered_default_and_selection_are_rejected() -> None:
    gemini = ScriptedProvider([], name=ProviderName.GEMINI)
    with pytest.raises(ValueError):
        ModelRouter(
            providers={ProviderName.GEMINI: gemini},
            default_provider=ProviderName.OLLAMA,
        )

    router = ModelRouter(
        providers={ProviderName.GEMINI: gemini},
        default_provider=ProviderName.GEMINI,
    )
    with pytest.raises(ValueError):
        router.set_active_provider(ProviderName.OLLAMA)
