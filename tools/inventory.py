from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from inventory.manager import load_inventory
from tools._response import list_result


def list_devices() -> dict[str, Any]:
    """List all Ruckus devices (ICX switches) in inventory."""
    return list_result([device.to_dict() for device in load_inventory()])


def all_device_info() -> dict[str, Any]:
    """Get info for all devices."""
    from adapters.device_ssh import RuckusDeviceDriver
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        driver = RuckusDeviceDriver(device)
        results.append(driver.get_device_info())
    return list_result(results)


def all_device_status() -> dict[str, Any]:
    """Get status for all devices."""
    from adapters.device_ssh import RuckusDeviceDriver
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        driver = RuckusDeviceDriver(device)
        results.append(driver.get_device_status())
    return list_result(results)


def all_device_backup(config_type: str = "running") -> dict[str, Any]:
    """Backup config for all devices (serial query, metadata only).

    Returns metadata per device (path, sha256, size, lines). Secrets stay out
    of agent context — full config written to filesystem for restore.
    """
    from tools.icx_device import _device_config_backup as device_config_backup
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        results.append(device_config_backup(device.host, config_type=config_type))
    return list_result(results)


def devices_by_location(location: str) -> dict[str, Any]:
    """Filter devices by location."""
    return list_result([device.to_dict() for device in load_inventory()
                        if device.location == location])


def devices_by_role(role: str) -> dict[str, Any]:
    """Filter devices by role."""
    return list_result([device.to_dict() for device in load_inventory()
                        if device.role == role])

def register_tools(mcp: FastMCP) -> None:
    """Register inventory and bulk device tools."""

    @mcp.tool()
    def ruckus_list_devices() -> dict[str, Any]:
        """List all Ruckus devices (ICX switches) in inventory."""
        return list_devices()

    @mcp.tool()
    def ruckus_all_device_info() -> dict[str, Any]:
        """Get info for all devices."""
        return all_device_info()

    @mcp.tool()
    def ruckus_all_device_status() -> dict[str, Any]:
        """Get status for all devices."""
        return all_device_status()

    @mcp.tool()
    def ruckus_all_device_backup(config_type: str = "running") -> dict[str, Any]:
        """Backup config for all devices (metadata only, secrets out of context)."""
        return all_device_backup(config_type=config_type)

    @mcp.tool()
    def ruckus_devices_by_location(location: str) -> dict[str, Any]:
        """Filter devices by location."""
        return devices_by_location(location)

    @mcp.tool()
    def ruckus_devices_by_role(role: str) -> dict[str, Any]:
        """Filter devices by role."""
        return devices_by_role(role)
