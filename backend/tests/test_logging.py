"""Logging configuration tests."""

from __future__ import annotations

import logging

from jarvis.logging import configure_logging


def test_configure_logging_is_idempotent() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        configure_logging("DEBUG")
        handler_count = len(root.handlers)
        configure_logging("DEBUG")

        assert root.level == logging.DEBUG
        assert len(root.handlers) == handler_count
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)
