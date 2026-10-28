"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jarvis.config import Settings
from jarvis.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Return isolated settings that do not depend on the developer .env file."""

    return Settings(
        _env_file=None,
        app_env="test",
        log_level="INFO",
        timezone="UTC",
        api_host="127.0.0.1",
        api_port=8765,
        audit_log_path=tmp_path / "audit.jsonl",
        usage_db_path=tmp_path / "usage.db",
        local_daily_token_budget=1_000_000,
        memory_db_path=tmp_path / "jarvis.db",
        default_model_provider="gemini",
        local_fallback_enabled=True,
        gemini_api_key=None,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Return a test client with application lifespan enabled."""

    with TestClient(create_app(settings)) as test_client:
        yield test_client
