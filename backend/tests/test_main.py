"""Entry point tests."""

from __future__ import annotations

from typing import Any

import pytest

import jarvis.__main__ as cli
from jarvis.config import Settings


def test_main_uses_validated_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    settings = Settings(
        _env_file=None,
        api_host="127.0.0.1",
        api_port=8765,
        log_level="DEBUG",
    )

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: captured.update(kwargs))

    cli.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["log_level"] == "debug"
