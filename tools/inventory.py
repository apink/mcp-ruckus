from __future__ import annotations

from typing import Any

from inventory.manager import load_inventory


def list_devices() -> list[dict[str, Any]]:
    """List all Ruckus devices (ICX switches) in inventory."""
    return [device.to_dict() for device in load_inventory()]


def all_device_info() -> list[dict[str, Any]]:
    """Get info for all devices."""
    from adapters.device_ssh import RuckusDeviceDriver
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        driver = RuckusDeviceDriver(device)
        results.append(driver.get_device_info())
    return results


def all_device_status() -> list[dict[str, Any]]:
    """Get status for all devices."""
    from adapters.device_ssh import RuckusDeviceDriver
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        driver = RuckusDeviceDriver(device)
        results.append(driver.get_device_status())
    return results


def all_device_backup(config_type: str = "running") -> list[dict[str, Any]]:
    """Backup config for all devices (serial query, metadata only).

    Returns metadata per device (path, sha256, size, lines). Secrets stay out
    of agent context — full config written to filesystem for restore.
    """
    from tools.icx_device import _device_config_backup as device_config_backup
    results: list[dict[str, Any]] = []
    for device in load_inventory():
        results.append(device_config_backup(device.host, config_type=config_type))
    return results


def devices_by_location(location: str) -> list[dict[str, Any]]:
    """Filter devices by location."""
    return [device.to_dict() for device in load_inventory()
            if device.location == location]


def devices_by_role(role: str) -> list[dict[str, Any]]:
    """Filter devices by role."""
    return [device.to_dict() for device in load_inventory()
            if device.role == role]

def register_tools(mcp):
    """Register inventory and bulk device tools."""
    from fastmcp import FastMCP

    @mcp.tool()
    def ruckus_list_devices() -> list[dict[str, Any]]:
        """List all Ruckus devices (ICX switches) in inventory."""
        return list_devices()

    @mcp.tool()
    def ruckus_all_device_info() -> list[dict[str, Any]]:
        """Get info for all devices."""
        return all_device_info()

    @mcp.tool()
    def ruckus_all_device_status() -> list[dict[str, Any]]:
        """Get status for all devices."""
        return all_device_status()

    @mcp.tool()
    def ruckus_all_device_backup(config_type: str = "running") -> list[dict[str, Any]]:
        """Backup config for all devices (metadata only, secrets out of context)."""
        return all_device_backup(config_type=config_type)

    @mcp.tool()
    def ruckus_devices_by_location(location: str) -> list[dict[str, Any]]:
        """Filter devices by location."""
        return devices_by_location(location)

    @mcp.tool()
    def ruckus_devices_by_role(role: str) -> list[dict[str, Any]]:
        """Filter devices by role."""
        return devices_by_role(role)
