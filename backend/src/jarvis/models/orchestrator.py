"""Tool-calling orchestration with truthful execution reporting."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ..tools.models import ToolResult
from ..tools.registry import ToolRegistry
from .prompts import build_system_prompt
from .router import ModelRouter
from .schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ProviderName,
)

if TYPE_CHECKING:
    from ..memory.service import MemoryService

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Run a bounded tool-calling loop against the selected model provider."""

    def __init__(
        self,
        registry: ToolRegistry,
        router: ModelRouter,
        memory: MemoryService | None = None,
        max_tool_iterations: int = 3,
        max_tool_calls: int = 8,
        memory_max_results: int = 5,
        memory_context_max_chars: int = 4000,
        auto_store_chat: bool = True,
    ) -> None:
        self._registry = registry
        self._router = router
        self._memory = memory
        self._max_tool_iterations = max_tool_iterations
        self._max_tool_calls = max_tool_calls
        self._memory_max_results = memory_max_results
        self._memory_context_max_chars = memory_context_max_chars
        self._auto_store_chat = auto_store_chat

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Interpret a request, execute approved tools, and return evidence."""

        conversation_id = request.conversation_id or uuid4().hex
        memory_context = await self._retrieve_memory_context(request.message)
        messages = [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content=build_system_prompt(memory_context),
            ),
            ChatMessage(role=ChatRole.USER, content=request.message),
        ]

        tool_results: list[ToolResult] = []
        providers_used: list[ProviderName] = []
        warnings: list[str] = []
        fallback_used = False
        iterations = 0
        reply = ""
        stopped_at_limit = False

        for iteration in range(1, self._max_tool_iterations + 1):
            routed = await self._router.complete(
                messages,
                tools=self._registry.list_tools(),
                provider=request.provider,
            )
            iterations = iteration
            providers_used.append(routed.provider)
            fallback_used = fallback_used or routed.fallback_used
            response = routed.response

            if not response.tool_calls:
                reply = response.text.strip() or "I could not produce a response."
                break

            messages.append(
                ChatMessage(
                    role=ChatRole.ASSISTANT,
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )

            for tool_call in response.tool_calls:
                if len(tool_results) >= self._max_tool_calls:
                    messages.append(
                        ChatMessage(
                            role=ChatRole.TOOL,
                            content=json.dumps(
                                {
                                    "ok": False,
                                    "error": {
                                        "code": "tool_limit",
                                        "message": "Tool call limit reached; not executed.",
                                    },
                                }
                            ),
                            name=tool_call.name,
                            tool_call_id=tool_call.id,
                        )
                    )
                    stopped_at_limit = True
                    continue

                result = await self._registry.execute(tool_call.name, tool_call.arguments)
                tool_results.append(result)
                messages.append(
                    ChatMessage(
                        role=ChatRole.TOOL,
                        content=json.dumps(
                            result.model_dump(mode="json"),
                            ensure_ascii=False,
                            default=str,
                        ),
                        name=tool_call.name,
                        tool_call_id=tool_call.id,
                    )
                )

            if stopped_at_limit:
                break

        if stopped_at_limit:
            reply = (
                "I stopped before completing the request because the tool-call limit was reached."
            )
            warnings.append("The tool-call limit was reached.")
        elif not reply:
            reply = (
                "I stopped before completing the request because the tool-iteration "
                "limit was reached."
            )
            warnings.append("The tool-iteration limit was reached.")

        execution_verified = all(result.ok for result in tool_results) if tool_results else None
        if execution_verified is False:
            warnings.append("One or more tool calls failed.")
            reply = (
                f"{reply.rstrip()}\n\n"
                "Execution note: one or more tool calls failed. See the structured "
                "execution results."
            )
        if any(not result.audit_recorded for result in tool_results):
            warnings.append("One or more tool calls could not be written to the audit log.")

        await self._store_episode(
            conversation_id=conversation_id,
            user_message=request.message,
            reply=reply,
            provider=providers_used[-1] if providers_used else self._router.active_provider,
        )

        return ChatResponse(
            reply=reply,
            provider=providers_used[-1] if providers_used else self._router.active_provider,
            providers_used=providers_used,
            fallback_used=fallback_used,
            tool_results=tool_results,
            execution_verified=execution_verified,
            iterations=iterations,
            conversation_id=conversation_id,
            warnings=warnings,
        )

    async def _retrieve_memory_context(self, query: str) -> str:
        if self._memory is None:
            return ""
        try:
            memories: list[Any] = await asyncio.to_thread(
                self._memory.search,
                query,
                limit=self._memory_max_results,
            )
        except Exception:
            logger.exception("Memory retrieval failed")
            return ""
        if not memories:
            return ""
        return await asyncio.to_thread(
            self._memory.format_context,
            memories,
            self._memory_context_max_chars,
        )

    async def _store_episode(
        self,
        conversation_id: str,
        user_message: str,
        reply: str,
        provider: ProviderName,
    ) -> None:
        if self._memory is None or not self._auto_store_chat:
            return
        try:
            await asyncio.to_thread(
                self._memory.add_episode,
                user_message,
                reply,
                conversation_id=conversation_id,
                provider=provider.value,
            )
        except Exception:
            logger.exception("Failed to store chat memory episode")
