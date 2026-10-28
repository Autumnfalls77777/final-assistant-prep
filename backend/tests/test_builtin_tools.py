"""Built-in read-only Windows tool tests with isolated system data."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import psutil

from jarvis.tools.windows import battery, disk_usage, processes, system_info


def test_system_info_reads_expected_fields(
    monkeypatch: Any,
) -> None:
    now_timestamp = datetime.now(UTC).timestamp()

    monkeypatch.setattr(system_info.platform, "system", lambda: "Windows")
    monkeypatch.setattr(system_info.platform, "version", lambda: "10.0.0")
    monkeypatch.setattr(system_info.platform, "release", lambda: "10")
    monkeypatch.setattr(system_info.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(system_info.socket, "gethostname", lambda: "test-host")
    monkeypatch.setattr(
        system_info.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=16 * 1024**3, available=8 * 1024**3),
    )
    monkeypatch.setattr(system_info.psutil, "boot_time", lambda: now_timestamp - 3600)
    monkeypatch.setattr(
        system_info.psutil,
        "cpu_count",
        lambda logical=True: 8 if logical else 4,
    )

    result = asyncio.run(system_info.SystemInfoTool().execute(system_info.SystemInfoInput()))

    assert isinstance(result, system_info.SystemInfoOutput)
    assert result.os_name == "Windows"
    assert result.hostname == "test-host"
    assert result.cpu_count_logical == 8
    assert result.cpu_count_physical == 4
    assert result.memory_total_bytes == 16 * 1024**3
    assert 3500 <= result.uptime_seconds <= 3700


def test_disk_usage_reports_unavailable_partition(
    monkeypatch: Any,
) -> None:
    partitions = [
        SimpleNamespace(device="C:", mountpoint="C:\\", fstype="NTFS", opts="rw"),
        SimpleNamespace(device="D:", mountpoint="D:\\", fstype="NTFS", opts="rw"),
    ]
    monkeypatch.setattr(
        disk_usage.psutil,
        "disk_partitions",
        lambda all=False: partitions,
    )

    def fake_disk_usage(mountpoint: str) -> SimpleNamespace:
        if mountpoint == "D:\\":
            raise OSError("device not ready")
        return SimpleNamespace(total=100, used=40, free=60, percent=40.0)

    monkeypatch.setattr(disk_usage.psutil, "disk_usage", fake_disk_usage)

    result = asyncio.run(disk_usage.DiskUsageTool().execute(disk_usage.DiskUsageInput()))

    assert isinstance(result, disk_usage.DiskUsageOutput)
    assert len(result.partitions) == 1
    assert result.partitions[0].mountpoint == "C:\\"
    assert result.partitions[0].percent == 40.0
    assert len(result.unavailable) == 1
    assert result.unavailable[0].mountpoint == "D:\\"
    assert result.unavailable[0].reason == "OSError"


def _process_info(
    pid: int,
    name: str,
    rss: int,
    memory_percent: float = 1.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        info={
            "pid": pid,
            "name": name,
            "status": "running",
            "memory_info": SimpleNamespace(rss=rss),
            "memory_percent": memory_percent,
            "create_time": None,
        }
    )


def test_process_list_sorts_and_limits(monkeypatch: Any) -> None:
    fake_processes = [
        _process_info(1, "alpha", 100),
        _process_info(2, "Beta", 300),
        _process_info(3, "gamma", 200),
    ]
    monkeypatch.setattr(
        processes.psutil,
        "process_iter",
        lambda attrs: iter(fake_processes),
    )

    result = asyncio.run(
        processes.ProcessListTool().execute(processes.ProcessListInput(limit=2, sort_by="memory"))
    )

    assert isinstance(result, processes.ProcessListOutput)
    assert [item.name for item in result.processes] == ["Beta", "gamma"]
    assert result.total_matched == 3


def test_process_list_sorts_by_name(monkeypatch: Any) -> None:
    fake_processes = [
        _process_info(1, "zeta", 100),
        _process_info(2, "Alpha", 300),
    ]
    monkeypatch.setattr(
        processes.psutil,
        "process_iter",
        lambda attrs: iter(fake_processes),
    )

    result = asyncio.run(
        processes.ProcessListTool().execute(processes.ProcessListInput(limit=10, sort_by="name"))
    )

    assert [item.name for item in result.processes] == ["Alpha", "zeta"]


def test_process_list_skips_access_denied(monkeypatch: Any) -> None:
    class DeniedProcess:
        @property
        def info(self) -> dict[str, Any]:
            raise psutil.AccessDenied(pid=1)

    monkeypatch.setattr(
        processes.psutil,
        "process_iter",
        lambda attrs: iter([DeniedProcess(), _process_info(2, "allowed", 100)]),
    )

    result = asyncio.run(processes.ProcessListTool().execute(processes.ProcessListInput()))

    assert [item.name for item in result.processes] == ["allowed"]
    assert result.total_matched == 1


def test_battery_absent(monkeypatch: Any) -> None:
    monkeypatch.setattr(battery.psutil, "sensors_battery", lambda: None)

    result = asyncio.run(battery.BatteryStatusTool().execute(battery.BatteryStatusInput()))

    assert isinstance(result, battery.BatteryStatusOutput)
    assert result.present is False
    assert result.percent is None
    assert result.power_source == "unknown"


def test_battery_reports_unlimited_remaining_time(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        battery.psutil,
        "sensors_battery",
        lambda: SimpleNamespace(
            percent=80.0,
            power_plugged=True,
            secsleft=psutil.POWER_TIME_UNLIMITED,
        ),
    )

    result = asyncio.run(battery.BatteryStatusTool().execute(battery.BatteryStatusInput()))

    assert result.present is True
    assert result.percent == 80.0
    assert result.plugged_in is True
    assert result.seconds_left is None
    assert result.power_source == "ac"


def test_battery_reports_discharge_time(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        battery.psutil,
        "sensors_battery",
        lambda: SimpleNamespace(
            percent=55.0,
            power_plugged=False,
            secsleft=3600,
        ),
    )

    result = asyncio.run(battery.BatteryStatusTool().execute(battery.BatteryStatusInput()))

    assert result.seconds_left == 3600
    assert result.power_source == "battery"
