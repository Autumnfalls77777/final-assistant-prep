"""Application logging configuration."""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str) -> None:
    """Configure root logging without duplicating handlers.

    Only format, level, logger name, and message are emitted. Request bodies
    and tool arguments are never logged through this configuration.
    """

    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)
