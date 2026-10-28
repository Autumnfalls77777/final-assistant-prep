"""Health endpoint that does not depend on models, memory, or credentials."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .. import __version__
from ..config import Settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Small liveness response."""

    status: Literal["ok"] = "ok"
    service: Literal["jarvis-backend"] = "jarvis-backend"
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health(request: Request) -> HealthResponse:
    """Return a local liveness response without touching external systems."""

    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(version=__version__, environment=settings.app_env)
