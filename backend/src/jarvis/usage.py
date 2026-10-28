"""Persistent local daily token accounting for the desktop usage meter."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import PROJECT_ROOT
from .models.schemas import ProviderName, TokenUsage, UsageSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_token_usage (
    usage_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (usage_date, provider)
);
"""

_NOTE = (
    "Gemini API keys do not expose live remaining quota. This value tracks "
    "tokens used today against the local LOCAL_DAILY_TOKEN_BUDGET setting."
)


class UsageStore:
    """Record token usage locally and expose a truthful daily budget snapshot."""

    def __init__(
        self,
        db_path: str | Path,
        budget_tokens: int,
        timezone_name: str = "UTC",
    ) -> None:
        path = Path(db_path)
        self.path = path if path.is_absolute() else PROJECT_ROOT / path
        self.budget_tokens = budget_tokens
        self.timezone = ZoneInfo(timezone_name)
        self._lock = asyncio.Lock()

    def initialize(self) -> None:
        """Create the local usage database if it does not exist."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(_SCHEMA)

    async def record(self, provider: ProviderName, usage: TokenUsage) -> UsageSnapshot:
        """Add one completed turn to today's local usage ledger."""

        async with self._lock:
            today = self._today()
            await asyncio.to_thread(self._record_sync, today, provider, usage)
            return await asyncio.to_thread(self._snapshot_sync, today, provider)

    async def snapshot(self, provider: ProviderName) -> UsageSnapshot:
        """Return today's usage and the configured local remaining budget."""

        async with self._lock:
            today = self._today()
            return await asyncio.to_thread(self._snapshot_sync, today, provider)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=10.0)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _today(self) -> str:
        return datetime.now(self.timezone).date().isoformat()

    def _record_sync(self, day: str, provider: ProviderName, usage: TokenUsage) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO daily_token_usage (
                    usage_date,
                    provider,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    requests
                )
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(usage_date, provider) DO UPDATE SET
                    prompt_tokens = prompt_tokens + excluded.prompt_tokens,
                    completion_tokens = completion_tokens + excluded.completion_tokens,
                    total_tokens = total_tokens + excluded.total_tokens,
                    requests = requests + 1
                """,
                (
                    day,
                    provider.value,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                ),
            )

    def _snapshot_sync(self, day: str, provider: ProviderName) -> UsageSnapshot:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM daily_token_usage WHERE usage_date = ? AND provider = ?",
                (day, provider.value),
            ).fetchone()

        prompt_tokens = int(row["prompt_tokens"]) if row is not None else 0
        completion_tokens = int(row["completion_tokens"]) if row is not None else 0
        total_tokens = int(row["total_tokens"]) if row is not None else 0
        requests = int(row["requests"]) if row is not None else 0
        remaining_tokens = max(0, self.budget_tokens - total_tokens)
        percent_used = min(100.0, round((total_tokens / self.budget_tokens) * 100, 2))
        return UsageSnapshot(
            provider=provider,
            date=day,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            requests=requests,
            budget_tokens=self.budget_tokens,
            remaining_tokens=remaining_tokens,
            percent_used=percent_used,
            scope="local",
            note=_NOTE,
        )
