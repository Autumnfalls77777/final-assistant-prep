"""Read-only process list tool."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal, cast

import psutil
from pydantic import BaseModel, ConfigDict, Field

from ..base import BaseTool
from ..policy import RiskLevel


class ProcessListInput(BaseModel):
    """Bounds for the process list query."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=50)
    sort_by: Literal["memory", "name", "pid"] = "memory"


class ProcessInfo(BaseModel):
    """Non-sensitive process metadata."""

    model_config = ConfigDict(extra="forbid")

    pid: int
    name: str
    status: str
    memory_rss_bytes: int
    memory_percent: float | None
    create_time_utc: datetime | None


class ProcessListOutput(BaseModel):
    """A bounded, sorted process list."""

    model_config = ConfigDict(extra="forbid")

    processes: list[ProcessInfo]
    total_matched: int


class ProcessListTool(BaseTool):
    """List a bounded subset of running processes without command lines."""

    name = "list_processes"
    description = "List a bounded subset of running processes with PID, name, and memory use."
    input_model = ProcessListInput
    output_model = ProcessListOutput
    risk_level = RiskLevel.READ
    timeout_seconds = 8.0

    async def execute(self, params: BaseModel) -> BaseModel:
        typed_params = cast(ProcessListInput, params)
        return await asyncio.to_thread(self._collect, typed_params)

    def _collect(self, params: ProcessListInput) -> ProcessListOutput:
        processes: list[ProcessInfo] = []

        for process in psutil.process_iter(
            ["pid", "name", "status", "memory_info", "memory_percent", "create_time"]
        ):
            try:
                info = process.info
                pid = info.get("pid")
                name = info.get("name")
                if pid is None or not name:
                    continue

                memory_info = info.get("memory_info")
                memory_percent = info.get("memory_percent")
                create_time = info.get("create_time")
                create_time_utc = (
                    datetime.fromtimestamp(create_time, tz=UTC) if create_time is not None else None
                )
                processes.append(
                    ProcessInfo(
                        pid=int(pid),
                        name=str(name),
                        status=str(info.get("status") or "unknown"),
                        memory_rss_bytes=int(getattr(memory_info, "rss", 0) or 0),
                        memory_percent=(
                            float(memory_percent) if memory_percent is not None else None
                        ),
                        create_time_utc=create_time_utc,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        total_matched = len(processes)
        if params.sort_by == "memory":
            processes.sort(key=lambda item: item.memory_rss_bytes, reverse=True)
        elif params.sort_by == "name":
            processes.sort(key=lambda item: item.name.casefold())
        else:
            processes.sort(key=lambda item: item.pid)

        return ProcessListOutput(
            processes=processes[: params.limit],
            total_matched=total_matched,
        )
