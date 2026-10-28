"""Tool-calling orchestration tests with deterministic providers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.memory.schemas import MemoryCreate, MemoryKind
from jarvis.models.errors import ProviderUnavailableError
from jarvis.models.orchestrator import AgentOrchestrator
from jarvis.models.router import ModelRouter
from jarvis.models.schemas import (
    ChatRequest,
    ChatRole,
    ModelResponse,
    ProviderName,
    TokenUsage,
    ToolCall,
)
from support import (
    ConfirmEchoTool,
    EchoTool,
    ScriptedProvider,
    build_test_memory,
    build_test_registry,
)


def _router(*providers: ScriptedProvider) -> ModelRouter:
    mapping = {provider.name: provider for provider in providers}
    return ModelRouter(
        providers=mapping,
        default_provider=providers[0].name,
        fallback_enabled=len(providers) > 1,
    )


def test_tool_call_is_executed_and_reported(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "hello"})]
            ),
            ModelResponse(text="The echo succeeded."),
        ]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="echo hello")))

    assert response.reply == "The echo succeeded."
    assert response.iterations == 2
    assert response.providers_used == [ProviderName.GEMINI, ProviderName.GEMINI]
    assert len(response.tool_results) == 1
    assert response.tool_results[0].ok is True
    assert response.tool_results[0].data == {"value": "hello"}
    assert response.execution_verified is True
    assert response.warnings == []


def test_usage_is_aggregated_across_tool_iterations(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "hello"})],
                usage=TokenUsage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            ),
            ModelResponse(
                text="Done.",
                usage=TokenUsage(prompt_tokens=140, completion_tokens=20, total_tokens=160),
            ),
        ]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="echo hello")))

    assert response.usage == TokenUsage(
        prompt_tokens=240,
        completion_tokens=30,
        total_tokens=270,
    )


def test_failed_tool_is_reported_truthfully(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(tool_calls=[ToolCall(id="call-1", name="missing", arguments={})]),
            ModelResponse(text="The tool failed."),
        ]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="do something")))

    assert response.execution_verified is False
    assert response.tool_results[0].ok is False
    assert "One or more tool calls failed." in response.warnings
    assert "Execution note" in response.reply


def test_permission_denied_tool_is_not_executed(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="confirm_echo",
                        arguments={"value": "blocked"},
                    )
                ]
            ),
            ModelResponse(text="The action was not permitted."),
        ]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path, [EchoTool(), ConfirmEchoTool()]),
        _router(provider),
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="change something")))

    assert response.tool_results[0].ok is False
    assert response.tool_results[0].error is not None
    assert response.tool_results[0].error.code.value == "permission_denied"
    assert response.execution_verified is False


def test_tool_call_limit_stops_execution(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [
            ModelResponse(
                tool_calls=[
                    ToolCall(id="call-1", name="echo", arguments={"value": "one"}),
                    ToolCall(id="call-2", name="echo", arguments={"value": "two"}),
                ]
            )
        ]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        max_tool_calls=1,
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="echo twice")))

    assert response.iterations == 1
    assert len(response.tool_results) == 1
    assert response.warnings == ["The tool-call limit was reached."]
    assert "tool-call limit" in response.reply


def test_tool_iteration_limit_stops_execution(tmp_path: Path) -> None:
    provider = ScriptedProvider(
        [ModelResponse(tool_calls=[ToolCall(id="call-1", name="echo", arguments={"value": "one"})])]
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        max_tool_iterations=1,
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="keep going")))

    assert response.iterations == 1
    assert "tool-iteration limit" in response.reply
    assert response.warnings == ["The tool-iteration limit was reached."]


def test_provider_fallback_is_reported(tmp_path: Path) -> None:
    gemini = ScriptedProvider(
        [ProviderUnavailableError(ProviderName.GEMINI, "Gemini unavailable")],
        name=ProviderName.GEMINI,
    )
    ollama = ScriptedProvider(
        [ModelResponse(text="Local answer.")],
        name=ProviderName.OLLAMA,
    )
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(gemini, ollama),
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="hello")))

    assert response.reply == "Local answer."
    assert response.provider is ProviderName.OLLAMA
    assert response.providers_used == [ProviderName.OLLAMA]
    assert response.fallback_used is True
    assert response.execution_verified is None


def test_retrieved_memory_is_included_in_system_prompt(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    memory.add(
        MemoryCreate(
            kind=MemoryKind.PERSONAL,
            content="My preferred editor is VS Code.",
            source="user",
            confidence=0.9,
            project="jarvis",
        )
    )
    provider = ScriptedProvider([ModelResponse(text="You prefer VS Code.")])
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        memory=memory,
        auto_store_chat=False,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="What is my preferred editor?")))

    assert response.reply == "You prefer VS Code."
    assert provider.seen_messages
    system_message = provider.seen_messages[0][0]
    assert system_message.role is ChatRole.SYSTEM
    assert "VS Code" in system_message.content


def test_completed_chat_stores_episodic_memory(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    provider = ScriptedProvider([ModelResponse(text="Hello, Prabal.")])
    orchestrator = AgentOrchestrator(
        build_test_registry(tmp_path),
        _router(provider),
        memory=memory,
        auto_store_chat=True,
    )

    response = asyncio.run(orchestrator.chat(ChatRequest(message="Hello JARVIS")))

    episodes = memory.list_memories(kind=MemoryKind.EPISODIC)
    assert len(episodes) == 1
    assert "Hello JARVIS" in episodes[0].content
    assert "Hello, Prabal." in episodes[0].content
    assert episodes[0].metadata["conversation_id"] == response.conversation_id
    assert episodes[0].metadata["provider"] == "gemini"
