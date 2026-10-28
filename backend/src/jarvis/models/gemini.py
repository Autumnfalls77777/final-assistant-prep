"""Gemini generateContent provider using the REST API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import httpx
from pydantic import SecretStr

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


class GeminiProvider(ModelProvider):
    """Call Gemini through ``generateContent`` with function declarations."""

    name = ProviderName.GEMINI
    _BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: SecretStr | None,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(model=model.removeprefix("models/"), timeout_seconds=timeout_seconds)
        self._api_key = api_key if api_key is not None and api_key.get_secret_value() else None
        self._client = client

    @property
    def configured(self) -> bool:
        return self._api_key is not None

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
    ) -> ModelResponse:
        if self._api_key is None:
            raise ProviderUnavailableError(self.name, "GEMINI_API_KEY is not configured.")

        payload = self._build_payload(messages, tools)
        headers = {
            "x-goog-api-key": self._api_key.get_secret_value(),
            "Content-Type": "application/json",
        }

        try:
            async with self._client_context() as client:
                response = await client.post(
                    f"{self._BASE_URL}/models/{self.model}:generateContent",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderResponseError(
                self.name,
                f"Gemini returned HTTP {exc.response.status_code}.",
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(self.name, "Gemini request failed.") from exc
        except ValueError as exc:
            raise ProviderResponseError(self.name, "Gemini returned invalid JSON.") from exc

        return self._parse_response(data)

    async def health(self) -> ProviderHealth:
        if not self.configured:
            return ProviderHealth(
                available=False,
                detail="GEMINI_API_KEY is not configured.",
            )
        return ProviderHealth(
            available=True,
            detail="Configured; live validation occurs on the first request.",
        )

    @asynccontextmanager
    async def _client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            yield client

    def _build_payload(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolInfo],
    ) -> dict[str, Any]:
        contents, system_text = self._build_contents(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": _gemini_schema(tool.input_schema),
                        }
                        for tool in tools
                    ]
                }
            ]
            payload["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
        return payload

    def _build_contents(
        self,
        messages: Sequence[ChatMessage],
    ) -> tuple[list[dict[str, Any]], str]:
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []

        for message in messages:
            if message.role is ChatRole.SYSTEM:
                if message.content:
                    system_parts.append(message.content)
                continue

            if message.role is ChatRole.TOOL:
                part = self._function_response_part(message)
                if (
                    contents
                    and contents[-1].get("role") == "user"
                    and any(
                        "functionResponse" in item
                        for item in contents[-1].get("parts", [])
                        if isinstance(item, dict)
                    )
                ):
                    contents[-1]["parts"].append(part)
                else:
                    contents.append({"role": "user", "parts": [part]})
                continue

            if message.role is ChatRole.ASSISTANT:
                parts: list[dict[str, Any]] = []
                if message.content:
                    parts.append({"text": message.content})
                for tool_call in message.tool_calls:
                    function_call: dict[str, Any] = {
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                    }
                    if tool_call.id:
                        function_call["id"] = tool_call.id
                    parts.append({"functionCall": function_call})
                if parts:
                    contents.append({"role": "model", "parts": parts})
                continue

            contents.append({"role": "user", "parts": [{"text": message.content}]})

        return contents, "\n\n".join(system_parts)

    @staticmethod
    def _function_response_part(message: ChatMessage) -> dict[str, Any]:
        try:
            parsed: Any = json.loads(message.content) if message.content else {}
        except json.JSONDecodeError:
            parsed = {"raw": message.content}
        if not isinstance(parsed, dict):
            parsed = {"result": parsed}
        response: dict[str, Any] = {"name": message.name or "tool", "response": {"result": parsed}}
        if message.tool_call_id:
            response["id"] = message.tool_call_id
        return {"functionResponse": response}

    @staticmethod
    def _parse_response(data: Any) -> ModelResponse:
        if not isinstance(data, dict):
            raise ProviderResponseError(ProviderName.GEMINI, "Gemini returned an invalid response.")
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderResponseError(ProviderName.GEMINI, "Gemini returned no candidates.")
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderResponseError(
                ProviderName.GEMINI,
                "Gemini returned an invalid candidate.",
            )
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            parts = []

        texts: list[str] = []
        tool_calls: list[ToolCall] = []
        for index, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
            function_call = part.get("functionCall")
            if isinstance(function_call, dict):
                name = function_call.get("name")
                arguments = function_call.get("args", {})
                if not isinstance(name, str) or not name:
                    raise ProviderResponseError(
                        ProviderName.GEMINI,
                        "Gemini returned a function call without a name.",
                    )
                if not isinstance(arguments, dict):
                    arguments = {}
                call_id = function_call.get("id")
                if not isinstance(call_id, str) or not call_id:
                    call_id = f"gemini_{index}"
                tool_calls.append(ToolCall(id=call_id, name=name, arguments=arguments))

        if not texts and not tool_calls:
            raise ProviderResponseError(ProviderName.GEMINI, "Gemini returned no usable content.")

        finish_reason = candidate.get("finishReason")
        return ModelResponse(
            text="".join(texts).strip(),
            tool_calls=tool_calls,
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=_parse_usage(data),
        )


def _parse_usage(data: dict[str, Any]) -> TokenUsage:
    """Normalize Gemini usageMetadata without inventing missing counts."""

    metadata = data.get("usageMetadata")
    if not isinstance(metadata, dict):
        return TokenUsage()

    prompt_tokens = _non_negative_int(metadata.get("promptTokenCount"))
    candidates_tokens = _non_negative_int(metadata.get("candidatesTokenCount"))
    thoughts_tokens = _non_negative_int(metadata.get("thoughtsTokenCount"))
    completion_tokens = candidates_tokens + thoughts_tokens
    total_tokens = _non_negative_int(metadata.get("totalTokenCount"))
    if total_tokens < prompt_tokens + completion_tokens:
        total_tokens = prompt_tokens + completion_tokens
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value if value > 0 else 0


_DROP_SCHEMA_KEYS = {"title", "additionalProperties", "$schema", "default"}


def _gemini_schema(value: Any) -> Any:
    """Convert a Pydantic JSON schema into Gemini's supported subset."""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in _DROP_SCHEMA_KEYS:
                continue
            if key == "type" and isinstance(item, str):
                cleaned[key] = item.upper()
            elif key == "properties" and isinstance(item, dict):
                cleaned[key] = {
                    str(property_name): _gemini_schema(property_schema)
                    for property_name, property_schema in item.items()
                }
            elif key in {"items", "not"}:
                cleaned[key] = _gemini_schema(item)
            elif key in {"anyOf", "oneOf", "allOf"} and isinstance(item, list):
                cleaned[key] = [_gemini_schema(entry) for entry in item]
            else:
                cleaned[key] = item
        return cleaned
    if isinstance(value, list):
        return [_gemini_schema(item) for item in value]
    return value
