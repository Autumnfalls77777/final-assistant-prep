"""Ollama native chat provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx

from ..tools.models import ToolInfo
from .base import ModelProvider
from .errors import ProviderResponseError, ProviderUnavailableError
from .schemas import (
    ChatMessage,
    ChatRole,
    ModelResponse,
    ProviderHealth,
    ProviderName,
    TokenUsage,
    ToolCall,
)


class OllamaProvider(ModelProvider):
    """Call a local Ollama server through ``/api/chat``."""

    name = ProviderName.OLLAMA

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(model=model, timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]

        try:
            async with self._client_context() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise ProviderResponseError(
                    self.name,
                    f"Ollama model '{self.model}' was not found.",
                ) from exc
            raise ProviderResponseError(
                self.name,
                f"Ollama returned HTTP {status}.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(
                self.name,
                "Ollama is not reachable. Start the Ollama service and retry.",
            ) from exc
        except ValueError as exc:
            raise ProviderResponseError(self.name, "Ollama returned invalid JSON.") from exc

        return self._parse_response(data)

    async def health(self) -> ProviderHealth:
        try:
            async with self._client_context() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=min(self.timeout_seconds, 2.0),
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return ProviderHealth(
                available=False,
                detail=f"Ollama returned HTTP {exc.response.status_code}.",
            )
        except httpx.RequestError:
            return ProviderHealth(
                available=False,
                detail="Ollama is not reachable.",
            )
        except ValueError:
            return ProviderHealth(available=False, detail="Ollama returned invalid JSON.")

        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return ProviderHealth(available=False, detail="Ollama returned an invalid model list.")
        names = {
            item.get("name")
            for item in models
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if self.model not in names:
            return ProviderHealth(
                available=False,
                detail=f"Ollama is running, but model '{self.model}' is not installed.",
            )
        return ProviderHealth(
            available=True,
            detail="Ollama is reachable and the model is installed.",
        )

    @asynccontextmanager
    async def _client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            yield client

    def _build_messages(self, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages:
            if message.role is ChatRole.TOOL:
                result.append(
                    {
                        "role": "tool",
                        "content": message.content,
                        "tool_name": message.name or "tool",
                    }
                )
                continue

            item: dict[str, Any] = {
                "role": message.role.value,
                "content": message.content,
            }
            if message.role is ChatRole.ASSISTANT and message.tool_calls:
                item["tool_calls"] = [
                    {
                        "function": {
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        }
                    }
                    for tool_call in message.tool_calls
                ]
            result.append(item)
        return result

    @staticmethod
    def _parse_response(data: Any) -> ModelResponse:
        if not isinstance(data, dict):
            raise ProviderResponseError(ProviderName.OLLAMA, "Ollama returned an invalid response.")
        message = data.get("message")
        if not isinstance(message, dict):
            raise ProviderResponseError(ProviderName.OLLAMA, "Ollama returned no message.")

        content = message.get("content")
        text = content if isinstance(content, str) else ""
        raw_tool_calls = message.get("tool_calls")
        tool_calls: list[ToolCall] = []
        if isinstance(raw_tool_calls, list):
            for index, raw_call in enumerate(raw_tool_calls):
                if not isinstance(raw_call, dict):
                    continue
                function = raw_call.get("function")
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                if not isinstance(name, str) or not name:
                    raise ProviderResponseError(
                        ProviderName.OLLAMA,
                        "Ollama returned a tool call without a name.",
                    )
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                call_id = raw_call.get("id")
                if not isinstance(call_id, str) or not call_id:
                    call_id = f"ollama_{index}"
                tool_calls.append(ToolCall(id=call_id, name=name, arguments=arguments))

        if not text.strip() and not tool_calls:
            raise ProviderResponseError(ProviderName.OLLAMA, "Ollama returned no usable content.")

        finish_reason = data.get("done_reason")
        prompt_tokens = _non_negative_int(data.get("prompt_eval_count"))
        completion_tokens = _non_negative_int(data.get("eval_count"))
        return ModelResponse(
            text=text.strip(),
            tool_calls=tool_calls,
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value > 0 else 0
