"""Basic system information tool."""

from __future__ import annotations

import asyncio
import platform
import socket
from datetime import UTC, datetime

import psutil
from pydantic import BaseModel, ConfigDict

from ..base import BaseTool
from ..policy import RiskLevel


class SystemInfoInput(BaseModel):
    """This tool takes no arguments."""

    model_config = ConfigDict(extra="forbid")


class SystemInfoOutput(BaseModel):
    """Basic, non-sensitive system information."""

    model_config = ConfigDict(extra="forbid")

    os_name: str
    os_version: str
    os_release: str
    machine: str
    hostname: str
    python_version: str
    cpu_count_logical: int | None
    cpu_count_physical: int | None
    memory_total_bytes: int
    memory_available_bytes: int
    boot_time_utc: datetime
    uptime_seconds: float


class SystemInfoTool(BaseTool):
    """Read operating system, CPU, memory, and uptime information."""

    name = "get_system_info"
    description = "Read basic operating system, CPU, memory, and uptime information."
    input_model = SystemInfoInput
    output_model = SystemInfoOutput
    risk_level = RiskLevel.READ
    timeout_seconds = 5.0

    async def execute(self, params: BaseModel) -> BaseModel:
        SystemInfoInput.model_validate(params)
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> SystemInfoOutput:
        memory = psutil.virtual_memory()
        boot_time = psutil.boot_time()
        boot_time_utc = datetime.fromtimestamp(boot_time, tz=UTC)

        try:
            hostname = socket.gethostname()
        except OSError:
            hostname = "unknown"

        now = datetime.now(UTC)
        return SystemInfoOutput(
            os_name=platform.system(),
            os_version=platform.version(),
            os_release=platform.release(),
            machine=platform.machine(),
            hostname=hostname,
            python_version=platform.python_version(),
            cpu_count_logical=psutil.cpu_count(),
            cpu_count_physical=psutil.cpu_count(logical=False),
            memory_total_bytes=memory.total,
            memory_available_bytes=memory.available,
            boot_time_utc=boot_time_utc,
            uptime_seconds=max(0.0, (now - boot_time_utc).total_seconds()),
        )
