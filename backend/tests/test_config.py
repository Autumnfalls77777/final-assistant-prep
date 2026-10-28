"""Configuration validation tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from jarvis.config import Settings

ENV_KEYS = (
    "APP_ENV",
    "LOG_LEVEL",
    "TIMEZONE",
    "API_HOST",
    "API_PORT",
    "DEFAULT_MODEL_PROVIDER",
    "LOCAL_FALLBACK_ENABLED",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MEMORY_DB_PATH",
)


@pytest.fixture(autouse=True)
def clear_phase_zero_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep host environment variables from changing test defaults."""

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


def test_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.timezone == "UTC"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.default_model_provider == "gemini"
    assert settings.local_fallback_enabled is True
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.gemini_model
    assert settings.ollama_model
    assert settings.memory_db_path.name == "jarvis.db"
    assert settings.memory_auto_store_chat is True


def test_environment_overrides_and_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "TESTING")
    monkeypatch.setenv("LOG_LEVEL", "warn")
    monkeypatch.setenv("TIMEZONE", "Europe/London")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.log_level == "WARNING"
    assert settings.timezone == "Europe/London"
    assert settings.api_port == 9001


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_rejects_non_loopback_hosts(host: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_host=host)


@pytest.mark.parametrize("port", [0, 80, 65536, 70000])
def test_rejects_invalid_ports(port: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_port=port)


def test_rejects_invalid_log_level() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="verbose")


def test_rejects_invalid_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Not/A_Real_Zone")


def test_future_phase_keys_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMOTE_ACCESS_ENABLED", "true")
    monkeypatch.setenv("WAKE_WORD_ENABLED", "true")

    settings = Settings(_env_file=None)

    assert not hasattr(settings, "remote_access_enabled")
    assert not hasattr(settings, "wake_word_enabled")


@pytest.mark.parametrize(
    "url",
    [
        "http://0.0.0.0:11434",
        "http://192.168.1.10:11434",
        "https://example.com",
        "ftp://127.0.0.1:11434",
    ],
)
def test_rejects_non_loopback_ollama_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ollama_base_url=url)


def test_accepts_localhost_ollama_url() -> None:
    settings = Settings(_env_file=None, ollama_base_url="http://localhost:11434/")

    assert settings.ollama_base_url == "http://localhost:11434"


def test_rejects_invalid_model_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, default_model_provider="unknown")


def test_gemini_key_is_not_exposed_by_repr() -> None:
    settings = Settings(_env_file=None, gemini_api_key="test-secret-value")

    assert "test-secret-value" not in repr(settings)
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "test-secret-value"
