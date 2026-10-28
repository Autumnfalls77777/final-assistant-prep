"""Memory domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryKind(StrEnum):
    """Supported memory categories."""

    PERSONAL = "personal"
    PROJECT = "project"
    EPISODIC = "episodic"
    WORKING = "working"
    SEMANTIC = "semantic"


class MemoryRecord(BaseModel):
    """A persisted memory record without its internal embedding."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: MemoryKind
    content: str
    source: str
    confidence: float
    project: str | None = None
    key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None
    superseded_by: str | None = None
    is_active: bool


class MemorySearchResult(MemoryRecord):
    """A memory record plus its retrieval score."""

    score: float


class MemoryCreate(BaseModel):
    """Request to create, deduplicate, or supersede a memory."""

    model_config = ConfigDict(extra="forbid")

    kind: MemoryKind
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="user", min_length=1, max_length=200)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    project: str | None = Field(default=None, max_length=100)
    key: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int | None = Field(default=None, ge=1, le=31_536_000)

    @field_validator("content", "source")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank")
        return stripped

    @field_validator("project", "key")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MemoryUpdate(BaseModel):
    """Correction request for an existing memory."""

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=1, max_length=4000)
    source: str | None = Field(default=None, min_length=1, max_length=200)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    project: str | None = Field(default=None, max_length=100)
    key: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] | None = None

    @field_validator("content", "source")
    @classmethod
    def _strip_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank")
        return stripped


class MemoryCreateResult(BaseModel):
    """Creation result, including deduplication metadata."""

    memory: MemoryRecord
    deduplicated: bool


class MemoryStats(BaseModel):
    """Aggregate memory counts."""

    total_active: int
    total_inactive: int
    expired: int
    by_kind: dict[str, int]


class MemoryEvent(BaseModel):
    """Audit entry for a memory mutation."""

    id: int
    memory_id: str
    action: str
    timestamp: datetime
    source: str
    details: dict[str, Any]
