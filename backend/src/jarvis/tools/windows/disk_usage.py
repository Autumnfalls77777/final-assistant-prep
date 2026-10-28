"""Read-only disk usage tool."""

from __future__ import annotations

import asyncio

import psutil
from pydantic import BaseModel, ConfigDict

from ..base import BaseTool
from ..policy import RiskLevel


class DiskUsageInput(BaseModel):
    """This tool takes no arguments."""

    model_config = ConfigDict(extra="forbid")


class DiskPartitionInfo(BaseModel):
    """Usage information for one accessible partition."""

    model_config = ConfigDict(extra="forbid")

    device: str
    mountpoint: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


class UnavailablePartition(BaseModel):
    """A partition that could not be queried."""

    model_config = ConfigDict(extra="forbid")

    mountpoint: str
    reason: str


class DiskUsageOutput(BaseModel):
    """Accessible and unavailable partitions."""

    model_config = ConfigDict(extra="forbid")

    partitions: list[DiskPartitionInfo]
    unavailable: list[UnavailablePartition]


class DiskUsageTool(BaseTool):
    """Read local disk and partition usage."""

    name = "get_disk_usage"
    description = "Read local disk and partition usage information."
    input_model = DiskUsageInput
    output_model = DiskUsageOutput
    risk_level = RiskLevel.READ
    timeout_seconds = 5.0

    async def execute(self, params: BaseModel) -> BaseModel:
        DiskUsageInput.model_validate(params)
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> DiskUsageOutput:
        partitions: list[DiskPartitionInfo] = []
        unavailable: list[UnavailablePartition] = []

        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (OSError, psutil.Error) as exc:
                unavailable.append(
                    UnavailablePartition(
                        mountpoint=partition.mountpoint,
                        reason=type(exc).__name__,
                    )
                )
                continue

            partitions.append(
                DiskPartitionInfo(
                    device=partition.device,
                    mountpoint=partition.mountpoint,
                    filesystem=partition.fstype,
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                    percent=usage.percent,
                )
            )

        partitions.sort(key=lambda item: item.mountpoint.casefold())
        unavailable.sort(key=lambda item: item.mountpoint.casefold())
        return DiskUsageOutput(partitions=partitions, unavailable=unavailable)
