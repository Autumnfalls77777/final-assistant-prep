"""Persistent memory service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from jarvis.memory.schemas import MemoryCreate, MemoryKind, MemoryUpdate
from jarvis.memory.service import MemoryService
from support import build_test_memory


def _add(
    memory: MemoryService,
    content: str,
    kind: MemoryKind = MemoryKind.PERSONAL,
    *,
    project: str | None = "jarvis",
    key: str | None = None,
    confidence: float = 0.8,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> str:
    result = memory.add(
        MemoryCreate(
            kind=kind,
            content=content,
            source="user",
            confidence=confidence,
            project=project,
            key=key,
            ttl_seconds=ttl_seconds,
        ),
        now=now,
    )
    return result.memory.id


def test_add_get_and_list_memory(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    memory_id = _add(memory, "My preferred editor is VS Code.")

    record = memory.get(memory_id)

    assert record is not None
    assert record.kind is MemoryKind.PERSONAL
    assert record.content == "My preferred editor is VS Code."
    assert record.source == "user"
    assert record.is_active is True
    assert memory.list_memories() == [record]


def test_memory_persists_across_service_instances(tmp_path: Path) -> None:
    path = tmp_path / "persistent.db"
    first = MemoryService(path)
    first.initialize()
    memory_id = _add(first, "The project uses FastAPI.", MemoryKind.PROJECT)

    second = MemoryService(path)
    second.initialize()

    record = second.get(memory_id)
    assert record is not None
    assert record.content == "The project uses FastAPI."


def test_exact_duplicate_is_deduplicated(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    first = memory.add(
        MemoryCreate(
            kind=MemoryKind.PERSONAL,
            content="I prefer dark mode.",
            source="user",
            confidence=0.6,
            project="jarvis",
        )
    )
    second = memory.add(
        MemoryCreate(
            kind=MemoryKind.PERSONAL,
            content="  I prefer dark mode.  ",
            source="chat",
            confidence=0.9,
            project="jarvis",
            metadata={"confirmed": True},
        )
    )

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.memory.id == first.memory.id
    assert second.memory.confidence == 0.9
    assert second.memory.metadata == {"confirmed": True}
    assert len(memory.list_memories()) == 1
    assert any(event.action == "deduplicated" for event in memory.events())


def test_keyed_memory_supersedes_previous_value(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    old_id = _add(memory, "My preferred editor is VS Code.", key="preferred_editor")
    new_id = _add(memory, "My preferred editor is Neovim.", key="preferred_editor")

    old = memory.get(old_id)
    new = memory.get(new_id)

    assert old is not None
    assert old.is_active is False
    assert old.superseded_by == new_id
    assert new is not None
    assert new.is_active is True
    assert [record.id for record in memory.list_memories()] == [new_id]
    assert {record.id for record in memory.list_memories(include_inactive=True)} == {
        old_id,
        new_id,
    }
    assert any(event.action == "superseded" for event in memory.events())


def test_search_returns_relevant_memory_first(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    _add(memory, "My preferred editor is VS Code.")
    _add(memory, "I live in London.")
    _add(memory, "The backend uses FastAPI.", MemoryKind.PROJECT)

    results = memory.search("Which editor do I prefer?")

    assert results
    assert results[0].content == "My preferred editor is VS Code."
    assert results[0].score > 0


def test_search_filters_by_kind_and_project(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    _add(memory, "A personal fact about FastAPI.")
    _add(memory, "A project fact about FastAPI.", MemoryKind.PROJECT)
    _add(memory, "A fact in another project.", MemoryKind.PROJECT, project="other")

    project_results = memory.search(
        "FastAPI",
        kinds=[MemoryKind.PROJECT],
        project="jarvis",
    )

    assert len(project_results) == 1
    assert project_results[0].content == "A project fact about FastAPI."


def test_working_memory_expires_and_can_be_purged(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    memory_id = _add(
        memory,
        "Temporary task context.",
        MemoryKind.WORKING,
        ttl_seconds=60,
        now=now,
    )

    assert memory.search("temporary task", now=now) != []
    assert memory.search("temporary task", now=now + timedelta(seconds=120)) == []
    assert memory.stats(now=now + timedelta(seconds=120)).expired == 1
    assert memory.purge_expired(now=now + timedelta(seconds=120)) == 1
    assert memory.get(memory_id) is None


def test_update_corrects_content_and_records_event(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    memory_id = _add(memory, "The deployment target is Linux.")

    updated = memory.update(
        memory_id,
        MemoryUpdate(
            content="The deployment target is Windows.",
            confidence=0.99,
            metadata={"corrected": True},
        ),
    )

    assert updated is not None
    assert updated.content == "The deployment target is Windows."
    assert updated.confidence == 0.99
    assert updated.metadata == {"corrected": True}
    assert any(event.action == "updated" for event in memory.events())


def test_delete_is_hard_and_audit_has_no_content(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    memory_id = _add(memory, "Delete this secret fact.", key="secret")

    assert memory.delete(memory_id) is True
    assert memory.get(memory_id) is None
    assert memory.delete(memory_id) is False

    deleted_events = [event for event in memory.events() if event.action == "deleted"]
    assert len(deleted_events) == 1
    assert "Delete this secret fact." not in str(deleted_events[0].details)


def test_stats_and_format_context(tmp_path: Path) -> None:
    memory = build_test_memory(tmp_path)
    _add(memory, "A personal fact.")
    _add(memory, "A project fact.", MemoryKind.PROJECT)
    _add(memory, "A semantic fact.", MemoryKind.SEMANTIC)

    stats = memory.stats()
    assert stats.total_active == 3
    assert stats.by_kind["personal"] == 1
    assert stats.by_kind["project"] == 1
    assert stats.by_kind["semantic"] == 1

    results = memory.search("fact")
    context = memory.format_context(results, max_chars=4000)
    assert "Stored memory" in context
    assert len(context) <= 4000


def test_blank_memory_content_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(
            kind=MemoryKind.PERSONAL,
            content="   ",
            source="user",
        )
