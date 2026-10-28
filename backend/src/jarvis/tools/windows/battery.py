"""Read-only battery status tool."""

from __future__ import annotations

import asyncio
from typing import Literal

import psutil
from pydantic import BaseModel, ConfigDict

from ..base import BaseTool
from ..policy import RiskLevel


class BatteryStatusInput(BaseModel):
    """This tool takes no arguments."""

    model_config = ConfigDict(extra="forbid")


class BatteryStatusOutput(BaseModel):
    """Battery presence and charge information."""

    model_config = ConfigDict(extra="forbid")

    present: bool
    percent: float | None
    plugged_in: bool | None
    seconds_left: int | None
    power_source: Literal["battery", "ac", "unknown"]


class BatteryStatusTool(BaseTool):
    """Read battery status, reporting unsupported hardware honestly."""

    name = "get_battery_status"
    description = "Read battery charge and power-source status, if present."
    input_model = BatteryStatusInput
    output_model = BatteryStatusOutput
    risk_level = RiskLevel.READ
    timeout_seconds = 5.0

    async def execute(self, params: BaseModel) -> BaseModel:
        BatteryStatusInput.model_validate(params)
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> BatteryStatusOutput:
        battery = psutil.sensors_battery()
        if battery is None:
            return BatteryStatusOutput(
                present=False,
                percent=None,
                plugged_in=None,
                seconds_left=None,
                power_source="unknown",
            )

        seconds_left = battery.secsleft
        if (
            seconds_left in {psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN}
            or seconds_left < 0
        ):
            seconds_left_value = None
        else:
            seconds_left_value = int(seconds_left)

        plugged_in = battery.power_plugged
        if plugged_in is None:
            power_source: Literal["battery", "ac", "unknown"] = "unknown"
        elif plugged_in:
            power_source = "ac"
        else:
            power_source = "battery"

        return BatteryStatusOutput(
            present=True,
            percent=float(battery.percent),
            plugged_in=plugged_in,
            seconds_left=seconds_left_value,
            power_source=power_source,
        )
