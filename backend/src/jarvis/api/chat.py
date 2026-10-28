"""Chat orchestration endpoint."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from ..models.errors import NoProviderAvailableError
from ..models.orchestrator import AgentOrchestrator
from ..models.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="Run a tool-enabled chat turn")
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Interpret a request, execute approved tools, and return evidence."""

    orchestrator = cast(AgentOrchestrator, request.app.state.orchestrator)
    try:
        return await orchestrator.chat(payload)
    except NoProviderAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
