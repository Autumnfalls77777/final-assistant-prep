"""Configuration validation tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from jarvis.config import Settings

ENV_KEYS = ("APP_ENV", "LOG_LEVEL", "TIMEZONE", "API_HOST", "API_PORT")


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
