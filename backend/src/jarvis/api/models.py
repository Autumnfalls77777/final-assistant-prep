"""Model discovery and runtime provider selection."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from ..models.router import ModelRouter
from ..models.schemas import ModelSelectionRequest, ModelStatus

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelStatus, summary="List model providers")
async def list_models(request: Request) -> ModelStatus:
    """Return provider configuration, active selection, and health."""

    model_router = cast(ModelRouter, request.app.state.model_router)
    return await model_router.status()


@router.put("/active", response_model=ModelStatus, summary="Select the active provider")
async def select_model(
    payload: ModelSelectionRequest,
    request: Request,
) -> ModelStatus:
    """Switch the runtime primary provider without persisting secrets."""

    model_router = cast(ModelRouter, request.app.state.model_router)
    try:
        model_router.set_active_provider(payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await model_router.status()
