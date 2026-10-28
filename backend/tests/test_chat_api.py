"""HTTP chat and model-selection endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from jarvis.config import Settings
from jarvis.main import create_app
from jarvis.memory.service import MemoryService
from jarvis.models.errors import ProviderUnavailableError
from jarvis.models.router import ModelRouter
from jarvis.models.schemas import ModelResponse, ProviderName, ToolCall
from support import ScriptedProvider, build_test_registry


@contextmanager
def _client(
    settings: Settings,
    tmp_path: Path,
    providers: list[ScriptedProvider],
    *,
    fallback_enabled: bool = False,
    memory: MemoryService | None = None,
) -> Iterator[TestClient]:
    router = ModelRouter(
        providers={provider.name: provider for provider in providers},
        default_provider=providers[0].name,
        fallback_enabled=fallback_enabled,
    )
    memory_service = memory or MemoryService(tmp_path / "api-memory.db")
    with TestClient(
        create_app(
            settings,
            registry=build_test_registry(tmp_path),
            model_router=router,
            memory=memory_service,
        )
    ) as client:
        yield client


def test_models_endpoint_reports_selection(settings: Settings, tmp_path: Path) -> None:
    gemini = ScriptedProvider([], name=ProviderName.GEMINI, configured=True)
    ollama = ScriptedProvider([], name=ProviderName.OLLAMA, configured=False)

    with _client(settings, tmp_path, [gemini, ollama]) as client:
        response = client.get("/models")

    assert response.status_code == 200
    body = response.json()
    assert body["active_provider"] == "gemini"
    assert body["default_provider"] == "gemini"
    assert body["fallback_enabled"] is False
    assert [provider["name"] for provider in body["providers"]] == ["gemini", "ollama"]
    assert body["providers"][1]["available"] is False


def test_switch_provider_and_chat(settings: Settings, tmp_path: Path) -> None:
    gemini = ScriptedProvider(
        [ModelResponse(text="Cloud answer.")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider(
        [ModelResponse(text="Local answer.")],
        name=ProviderName.OLLAMA,
    )

    with _client(settings, tmp_path, [gemini, ollama]) as client:
        response = client.put("/models/active", json={"provider": "ollama"})
        assert response.status_code == 200
        assert response.json()["active_provider"] == "ollama"

        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Local answer."
    assert body["provider"] == "ollama"
    assert body["providers_used"] == ["ollama"]
    assert body["fallback_used"] is False


def test_chat_executes_tool_and_stores_episode(settings: Settings, tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "hello"})]
            ),
            ModelResponse(text="The echo succeeded."),
        ]
    )

    with _client(settings, tmp_path, [provider]) as client:
        response = client.post("/chat", json={"message": "echo hello"})
        episodes = client.get("/memory", params={"kind": "episodic"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "The echo succeeded."
    assert body["execution_verified"] is True
    assert body["tool_results"][0]["ok"] is True
    assert body["iterations"] == 2
    assert episodes.status_code == 200
    assert len(episodes.json()) == 1


def test_chat_reports_provider_fallback(settings: Settings, tmp_path: Path) -> None:
    gemini = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider(
        [ModelResponse(text="Local fallback.")],
        name=ProviderName.OLLAMA,
    )

    with _client(
        settings,
        tmp_path,
        [gemini, ollama],
        fallback_enabled=True,
    ) as client:
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Local fallback."
    assert body["provider"] == "ollama"
    assert body["fallback_used"] is True


def test_chat_returns_503_when_all_providers_fail(
    settings: Settings,
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )

    with _client(settings, tmp_path, [provider]) as client:
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 503
    assert "No model provider is available" in response.json()["detail"]


def test_unregistered_provider_selection_is_rejected(
    settings: Settings,
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider([], name=ProviderName.GEMINI)

    with _client(settings, tmp_path, [provider]) as client:
        response = client.put("/models/active", json={"provider": "ollama"})

    assert response.status_code == 400


def test_chat_rejects_blank_message(settings: Settings, tmp_path: Path) -> None:
    provider = ScriptedProvider([], name=ProviderName.GEMINI)

    with _client(settings, tmp_path, [provider]) as client:
        response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422
