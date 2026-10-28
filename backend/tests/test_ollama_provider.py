"""Ollama provider request and response tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from jarvis.models.errors import ProviderResponseError
from jarvis.models.ollama import OllamaProvider
from jarvis.models.schemas import ChatMessage, ChatRole, ToolCall
from support import make_tool_info


def _provider(handler: Any) -> OllamaProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="test-model",
        timeout_seconds=5.0,
        client=client,
    )


def test_ollama_text_completion_and_request_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["stream"] is False
        assert payload["messages"] == [
            {"role": "system", "content": "System rules"},
            {"role": "user", "content": "Hello"},
        ]
        assert payload["tools"][0]["function"]["name"] == "echo"
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Hi there"}, "done_reason": "stop"},
        )

    provider = _provider(handler)
    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content="System rules"),
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]
    result = asyncio.run(provider.complete(messages, [make_tool_info()]))

    assert result.text == "Hi there"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"


def test_ollama_tool_call_arguments_are_normalized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "echo",
                                "arguments": json.dumps({"value": "hello"}),
                            }
                        }
                    ],
                }
            },
        )

    provider = _provider(handler)
    result = asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="echo")], []))

    assert result.text == ""
    assert result.tool_calls == [ToolCall(id="ollama_0", name="echo", arguments={"value": "hello"})]


def test_ollama_tool_message_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["messages"][1]["role"] == "assistant"
        assert payload["messages"][1]["tool_calls"][0]["function"]["name"] == "echo"
        assert payload["messages"][2] == {
            "role": "tool",
            "content": '{"ok": true}',
            "tool_name": "echo",
        }
        return httpx.Response(200, json={"message": {"content": "Done"}})

    provider = _provider(handler)
    messages = [
        ChatMessage(role=ChatRole.USER, content="echo"),
        ChatMessage(
            role=ChatRole.ASSISTANT,
            tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "x"})],
        ),
        ChatMessage(
            role=ChatRole.TOOL,
            name="echo",
            tool_call_id="call-1",
            content='{"ok": true}',
        ),
    ]
    result = asyncio.run(provider.complete(messages, []))

    assert result.text == "Done"


def test_ollama_health_detects_missing_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "other-model"}]})

    provider = _provider(handler)
    health = asyncio.run(provider.health())

    assert health.available is False
    assert "not installed" in (health.detail or "")


def test_ollama_health_detects_running_model() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "test-model"}]})

    provider = _provider(handler)
    health = asyncio.run(provider.health())

    assert health.available is True


def test_ollama_health_handles_unreachable_service() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = _provider(handler)
    health = asyncio.run(provider.health())

    assert health.available is False
    assert "not reachable" in (health.detail or "")


def test_ollama_missing_model_is_a_safe_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    provider = _provider(handler)

    with pytest.raises(ProviderResponseError) as exc_info:
        asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="hello")], []))

    assert "test-model" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_ollama_empty_message_is_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": ""}})

    provider = _provider(handler)

    with pytest.raises(ProviderResponseError, match="no usable content"):
        asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="hello")], []))
