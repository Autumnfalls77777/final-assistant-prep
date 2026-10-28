"""Append-only JSONL audit logging for tool invocations."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_SENSITIVE_MARKERS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "session",
)
_MAX_STRING_LENGTH = 500


class AuditEntry(BaseModel):
    """One auditable tool invocation."""

    timestamp: datetime
    audit_id: str
    tool: str
    risk_level: str | None
    decision: str
    ok: bool
    error_code: str | None
    duration_ms: float
    arguments: dict[str, Any]


def sanitize_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe copy with sensitive keys and long strings redacted."""

    sanitized = _redact(dict(arguments))
    if not isinstance(sanitized, dict):
        return {"value": sanitized}
    return sanitized


def _redact(value: Any, key: str | None = None) -> Any:
    if key is not None and any(marker in key.lower() for marker in _SENSITIVE_MARKERS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_STRING_LENGTH:
        return f"{value[:_MAX_STRING_LENGTH]}...[truncated]"
    return value


class AuditLogger:
    """Write audit records to a local JSONL file."""

    def __init__(self, path: str | Path) -> None:
        resolved = Path(path)
        self.path = resolved if resolved.is_absolute() else PROJECT_ROOT / resolved
        self._lock = threading.Lock()

    async def ensure_ready(self) -> None:
        """Create the log directory/file before the application starts serving."""

        await asyncio.to_thread(self._ensure_ready)

    def _ensure_ready(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n"):
            pass

    async def record(self, entry: AuditEntry) -> None:
        """Append one audit entry without blocking the event loop."""

        await asyncio.to_thread(self._append, entry)

    def _append(self, entry: AuditEntry) -> None:
        payload = json.dumps(
            entry.model_dump(mode="json"),
            ensure_ascii=False,
            default=str,
        )
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
