"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .api.health import router as health_router
from .api.tools import router as tools_router
from .config import Settings, get_settings
from .logging import configure_logging
from .tools.audit import AuditLogger
from .tools.builtin import build_default_registry
from .tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    registry: ToolRegistry | None = None,
) -> FastAPI:
    """Create the JARVIS backend application."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    audit_logger = AuditLogger(resolved_settings.audit_log_path)
    tool_registry = registry or build_default_registry(audit_logger)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await tool_registry.audit_logger.ensure_ready()
        logger.info(
            "Starting JARVIS backend version=%s environment=%s tools=%d",
            __version__,
            resolved_settings.app_env,
            len(tool_registry.list_tools()),
        )
        yield
        logger.info("Stopping JARVIS backend")

    application = FastAPI(
        title="JARVIS Backend",
        version=__version__,
        description=(
            "Local-first JARVIS backend. Phase 1 exposes read-only system tools "
            "through a permissioned, audited registry."
        ),
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.tool_registry = tool_registry
    application.include_router(health_router)
    application.include_router(tools_router)
    return application


app = create_app()
