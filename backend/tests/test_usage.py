"""Local token usage ledger tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.models.schemas import ProviderName, TokenUsage
from jarvis.usage import UsageStore


def test_usage_store_accumulates_today_and_calculates_remaining(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.db", budget_tokens=1_000)
    store.initialize()

    first = asyncio.run(
        store.record(
            ProviderName.GEMINI,
            TokenUsage(prompt_tokens=100, completion_tokens=25, total_tokens=125),
        )
    )
    second = asyncio.run(
        store.record(
            ProviderName.GEMINI,
            TokenUsage(prompt_tokens=80, completion_tokens=20, total_tokens=100),
        )
    )

    assert first.total_tokens == 125
    assert second.total_tokens == 225
    assert second.requests == 2
    assert second.remaining_tokens == 775
    assert second.percent_used == 22.5
    assert second.scope == "local"
    assert "LOCAL_DAILY_TOKEN_BUDGET" in second.note


def test_usage_store_keeps_providers_separate(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.db", budget_tokens=500)
    store.initialize()

    asyncio.run(
        store.record(
            ProviderName.GEMINI,
            TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
        )
    )
    ollama = asyncio.run(
        store.record(
            ProviderName.OLLAMA,
            TokenUsage(prompt_tokens=20, completion_tokens=5, total_tokens=25),
        )
    )

    assert ollama.provider is ProviderName.OLLAMA
    assert ollama.total_tokens == 25
    assert ollama.remaining_tokens == 475


def test_usage_store_clamps_exhausted_budget(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.db", budget_tokens=100)
    store.initialize()

    snapshot = asyncio.run(
        store.record(
            ProviderName.GEMINI,
            TokenUsage(prompt_tokens=80, completion_tokens=60, total_tokens=140),
        )
    )

    assert snapshot.total_tokens == 140
    assert snapshot.remaining_tokens == 0
    assert snapshot.percent_used == 100.0
