"""Memory inspection and correction endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from ..memory.schemas import (
    MemoryCreate,
    MemoryCreateResult,
    MemoryEvent,
    MemoryExport,
    MemoryKind,
    MemoryRecord,
    MemorySearchResult,
    MemoryStats,
    MemoryUpdate,
)
from ..memory.service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def _service(request: Request) -> MemoryService:
    return cast(MemoryService, request.app.state.memory_service)


@router.post("", response_model=MemoryCreateResult, status_code=status.HTTP_201_CREATED)
async def create_memory(payload: MemoryCreate, request: Request) -> MemoryCreateResult:
    """Create a memory, deduplicating identical active content."""

    try:
        return await asyncio.to_thread(_service(request).add, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/search", response_model=list[MemorySearchResult])
async def search_memory(
    q: Annotated[str, Query(min_length=1, max_length=1000)],
    request: Request,
    kind: MemoryKind | None = None,
    project: str | None = None,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[MemorySearchResult]:
    """Retrieve relevant local memories by vector and lexical similarity."""

    kinds = [kind] if kind is not None else None
    return await asyncio.to_thread(
        _service(request).search,
        q,
        kinds,
        project,
        limit,
    )


@router.get("/stats", response_model=MemoryStats)
async def memory_stats(request: Request) -> MemoryStats:
    """Return aggregate memory counts."""

    return await asyncio.to_thread(_service(request).stats)


@router.get("/events", response_model=list[MemoryEvent])
async def memory_events(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MemoryEvent]:
    """Return recent content-free memory audit events."""

    return await asyncio.to_thread(_service(request).events, limit)


@router.get("/export", response_model=MemoryExport)
async def export_memories(
    request: Request,
    kind: MemoryKind | None = None,
    project: str | None = None,
    include_inactive: bool = False,
) -> MemoryExport:
    """Export matching local memories as portable JSON."""

    memories = await asyncio.to_thread(
        _service(request).export_memories,
        include_inactive,
        kind,
        project,
    )
    return MemoryExport(
        exported_at=datetime.now(UTC),
        memories=memories,
    )


@router.get("", response_model=list[MemoryRecord])
async def list_memories(
    request: Request,
    kind: MemoryKind | None = None,
    project: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_inactive: bool = False,
) -> list[MemoryRecord]:
    """List memories for inspection."""

    return await asyncio.to_thread(
        _service(request).list_memories,
        kind,
        project,
        limit,
        include_inactive,
    )


@router.get("/{memory_id}", response_model=MemoryRecord)
async def get_memory(memory_id: str, request: Request) -> MemoryRecord:
    """Return one memory by ID."""

    record = await asyncio.to_thread(_service(request).get, memory_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.patch("/{memory_id}", response_model=MemoryRecord)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    request: Request,
) -> MemoryRecord:
    """Correct an existing memory record."""

    try:
        record = await asyncio.to_thread(_service(request).update, memory_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return record


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(memory_id: str, request: Request) -> Response:
    """Permanently delete a memory record."""

    deleted = await asyncio.to_thread(_service(request).delete, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
