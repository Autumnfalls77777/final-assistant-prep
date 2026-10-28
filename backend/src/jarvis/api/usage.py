"""Local token usage and budget endpoint."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from ..models.router import ModelRouter
from ..models.schemas import ProviderName, UsageSnapshot
from ..usage import UsageStore

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=UsageSnapshot, summary="Get daily token usage")
async def usage(
    request: Request,
    provider: ProviderName | None = None,
) -> UsageSnapshot:
    """Return today's local token ledger for the active or requested provider."""

    store = cast(UsageStore, request.app.state.usage_store)
    model_router = cast(ModelRouter, request.app.state.model_router)
    return await store.snapshot(provider or model_router.active_provider)
