"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .api.chat import router as chat_router
from .api.health import router as health_router
from .api.memory import router as memory_router
from .api.models import router as models_router
from .api.tools import router as tools_router
from .config import Settings, get_settings
from .logging import configure_logging
from .memory.service import MemoryService
from .models.factory import build_model_router
from .models.orchestrator import AgentOrchestrator
from .models.router import ModelRouter
from .tools.audit import AuditLogger
from .tools.builtin import build_default_registry
from .tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
    model_router: ModelRouter | None = None,
    memory: MemoryService | None = None,
) -> FastAPI:
    """Create the JARVIS backend application."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    audit_logger = AuditLogger(resolved_settings.audit_log_path)
    tool_registry = registry or build_default_registry(audit_logger)
    memory_service = memory or MemoryService(
        db_path=resolved_settings.memory_db_path,
        max_results=resolved_settings.memory_max_results,
        min_score=resolved_settings.memory_min_score,
        retention_days=resolved_settings.memory_retention_days,
        working_ttl_hours=resolved_settings.memory_working_ttl_hours,
    )
    provider_router = model_router or build_model_router(resolved_settings)
    orchestrator = AgentOrchestrator(
        registry=tool_registry,
        router=provider_router,
        memory=memory_service,
        max_tool_iterations=resolved_settings.max_tool_iterations,
        max_tool_calls=resolved_settings.max_tool_calls_per_turn,
        memory_max_results=resolved_settings.memory_max_results,
        memory_context_max_chars=resolved_settings.memory_context_max_chars,
        auto_store_chat=resolved_settings.memory_auto_store_chat,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await tool_registry.audit_logger.ensure_ready()
        await asyncio.to_thread(memory_service.initialize)
        logger.info(
            "Starting JARVIS backend version=%s environment=%s tools=%d "
            "provider=%s fallback_enabled=%s memory=%s",
            __version__,
            resolved_settings.app_env,
            len(tool_registry.list_tools()),
            provider_router.active_provider.value,
            provider_router.fallback_enabled,
            memory_service.path,
        )
        yield
        logger.info("Stopping JARVIS backend")

    application = FastAPI(
        title="JARVIS Backend",
        version=__version__,
        description=(
            "Local-first JARVIS backend. Phase 2 adds Gemini/Ollama routing, "
            "tool calling, and truthful execution reporting. Phase 3 adds local "
            "SQLite memory with vector retrieval and correction."
        ),
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.tool_registry = tool_registry
    application.state.memory_service = memory_service
    application.state.model_router = provider_router
    application.state.orchestrator = orchestrator
    application.include_router(health_router)
    application.include_router(tools_router)
    application.include_router(models_router)
    application.include_router(chat_router)
    application.include_router(memory_router)
    return application


app = create_app()
