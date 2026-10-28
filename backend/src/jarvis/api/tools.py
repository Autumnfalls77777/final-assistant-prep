"""Tool discovery and execution endpoints."""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from ..tools.errors import ToolErrorCode
from ..tools.models import ToolInfo, ToolResult
from ..tools.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])

_ERROR_STATUS: dict[ToolErrorCode, int] = {
    ToolErrorCode.INVALID_INPUT: 422,
    ToolErrorCode.NOT_FOUND: 404,
    ToolErrorCode.PERMISSION_DENIED: 403,
    ToolErrorCode.TIMEOUT: 504,
    ToolErrorCode.EXECUTION_FAILED: 500,
}


@router.get("", response_model=list[ToolInfo], summary="List registered tools")
async def list_tools(request: Request) -> list[ToolInfo]:
    """Return tool metadata and JSON schemas without executing anything."""

    registry = cast(ToolRegistry, request.app.state.tool_registry)
    return registry.list_tools()


@router.post(
    "/{tool_name}/execute",
    response_model=ToolResult,
    summary="Execute a registered tool",
)
async def execute_tool(
    request: Request,
    tool_name: str,
    arguments: Annotated[dict[str, Any] | None, Body()] = None,
) -> ToolResult | JSONResponse:
    """Execute one tool through validation, policy, timeout, and audit checks."""

    registry = cast(ToolRegistry, request.app.state.tool_registry)
    result = await registry.execute(tool_name, arguments or {})
    if result.ok:
        return result

    status_code = _ERROR_STATUS.get(result.error.code, 500) if result.error is not None else 500
    return JSONResponse(
        status_code=status_code,
        content=result.model_dump(mode="json"),
    )
