"""Default Phase 1 read-only tool registry."""

from __future__ import annotations

from .audit import AuditLogger
from .policy import PermissionPolicy
from .registry import ToolRegistry
from .windows.battery import BatteryStatusTool
from .windows.disk_usage import DiskUsageTool
from .windows.processes import ProcessListTool
from .windows.system_info import SystemInfoTool


def build_default_registry(
    audit_logger: AuditLogger,
    policy: PermissionPolicy | None = None,
) -> ToolRegistry:
    """Build the explicitly approved Phase 1 read-only tool set."""

    return ToolRegistry(
        tools=[
            SystemInfoTool(),
            DiskUsageTool(),
            ProcessListTool(),
            BatteryStatusTool(),
        ],
        policy=policy or PermissionPolicy(),
        audit_logger=audit_logger,
    )
