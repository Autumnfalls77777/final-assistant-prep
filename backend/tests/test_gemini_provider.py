"""Gemini provider request and response tests."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from jarvis.models.errors import ProviderResponseError, ProviderUnavailableError
from jarvis.models.gemini import GeminiProvider
from jarvis.models.schemas import ChatMessage, ChatRole, TokenUsage, ToolCall
from support import make_tool_info


def _provider(handler: Any) -> GeminiProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GeminiProvider(
        api_key=SecretStr("test-secret"),
        model="gemini-test",
        timeout_seconds=5.0,
        client=client,
    )


def test_gemini_text_completion_and_request_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/models/gemini-test:generateContent")
        assert request.headers["x-goog-api-key"] == "test-secret"
        payload = json.loads(request.content)
        assert payload["contents"][0]["role"] == "user"
        assert payload["contents"][0]["parts"][0]["text"] == "Hello"
        assert payload["systemInstruction"]["parts"][0]["text"] == "System rules"
        assert payload["tools"][0]["functionDeclarations"][0]["name"] == "echo"
        assert payload["tools"][0]["functionDeclarations"][0]["parameters"]["type"] == "OBJECT"
        assert "title" not in payload["tools"][0]["functionDeclarations"][0]["parameters"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Hi there"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 12,
                    "candidatesTokenCount": 4,
                    "thoughtsTokenCount": 2,
                    "totalTokenCount": 18,
                },
            },
        )

    provider = _provider(handler)
    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content="System rules"),
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]
    result = asyncio.run(provider.complete(messages, [make_tool_info()]))

    assert result.text == "Hi there"
    assert result.tool_calls == []
    assert result.finish_reason == "STOP"
    assert result.usage == TokenUsage(
        prompt_tokens=12,
        completion_tokens=6,
        total_tokens=18,
    )


def test_gemini_function_call_is_normalized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "id": "call-1",
                                        "name": "echo",
                                        "args": {"value": "hello"},
                                    }
                                }
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    provider = _provider(handler)
    result = asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="echo")], []))

    assert result.text == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0] == ToolCall(
        id="call-1",
        name="echo",
        arguments={"value": "hello"},
    )


def test_gemini_tool_history_uses_function_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        contents = payload["contents"]
        assert contents[1]["role"] == "model"
        assert contents[1]["parts"][0]["functionCall"]["name"] == "echo"
        assert contents[1]["parts"][0]["functionCall"]["id"] == "call-1"
        assert contents[2]["role"] == "user"
        assert contents[2]["parts"][0]["functionResponse"]["name"] == "echo"
        assert contents[2]["parts"][0]["functionResponse"]["id"] == "call-1"
        assert contents[2]["parts"][0]["functionResponse"]["response"]["result"]["ok"] is True
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Done"}]}}]},
        )

    provider = _provider(handler)
    messages = [
        ChatMessage(role=ChatRole.USER, content="echo"),
        ChatMessage(
            role=ChatRole.ASSISTANT,
            tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "hello"})],
        ),
        ChatMessage(
            role=ChatRole.TOOL,
            name="echo",
            tool_call_id="call-1",
            content=json.dumps({"ok": True, "data": {"value": "hello"}}),
        ),
        ChatMessage(role=ChatRole.USER, content="continue"),
    ]
    result = asyncio.run(provider.complete(messages, []))

    assert result.text == "Done"


def test_gemini_missing_key_is_unavailable() -> None:
    provider = GeminiProvider(
        api_key=None,
        model="gemini-test",
        timeout_seconds=5.0,
    )

    with pytest.raises(ProviderUnavailableError, match="GEMINI_API_KEY"):
        asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="hello")], []))


def test_gemini_http_error_does_not_leak_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    provider = _provider(handler)

    with pytest.raises(ProviderResponseError) as exc_info:
        asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="hello")], []))

    assert "HTTP 400" in str(exc_info.value)
    assert "test-secret" not in str(exc_info.value)


def test_gemini_empty_candidates_are_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    provider = _provider(handler)

    with pytest.raises(ProviderResponseError, match="no candidates"):
        asyncio.run(provider.complete([ChatMessage(role=ChatRole.USER, content="hello")], []))


def test_gemini_health_reports_configuration_without_live_call() -> None:
    provider = GeminiProvider(
        api_key=SecretStr("test-secret"),
        model="gemini-test",
        timeout_seconds=5.0,
    )
    health = asyncio.run(provider.health())

    assert health.available is True
    assert "live validation" in (health.detail or "")
