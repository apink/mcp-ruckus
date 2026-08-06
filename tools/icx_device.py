"""ICX switch tools — info, interfaces, routing, VLAN, MAC, LAG, health, ping, traceroute, backup."""
from __future__ import annotations

import datetime
import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from adapters.device_ssh import RuckusDeviceDriver
from inventory.manager import get_device_record

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = _BASE_DIR / "backups"


def _device_info(host: str) -> dict[str, Any]:
    logger.info("device_info: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_device_info()


def _device_status(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_device_status()


def _device_interfaces_summary(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_interfaces_summary()


def _device_interfaces_down(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_interfaces_down()


def _device_interfaces_errors(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_interfaces_errors()


def _device_interfaces_stats(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_interfaces_stats()


def _device_ip_addresses(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_ip_addresses()


def _device_ip_routes(host: str, destination: str | None = None) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_ip_routes(destination)


def _device_ipv6_routes(host: str, destination: str | None = None) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_ipv6_routes(destination)


def _device_vlan_summary(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_vlan_summary()


def _device_port_vlan(host: str, port: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_port_vlan(port)


def _device_mac_table_vlan(host: str, vlan_id: int) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_mac_table_vlan(vlan_id)


def _device_find_mac(host: str, mac: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.find_mac(mac)


def _device_lag_summary(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_lag_summary()


def _device_chassis_health(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_chassis_health()


def _device_ipv6_interfaces(host: str) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.get_ipv6_interfaces()


def _device_ping(host: str, ip: str, source: str | None = None) -> dict[str, Any]:
    logger.info("device_ping: host=%s ip=%s source=%s", host, ip, source)
    device = get_device_record(host)
    if not device:
        return {"host": host, "target_ip": ip, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.device_ping(ip, source)


def _device_ping_ipv6(host: str, ip: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "target_ip": ip, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.device_ping_ipv6(ip)


def _device_traceroute(host: str, ip: str, source_ip: str | None = None, max_ttl: int = 30) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "target_ip": ip, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.device_traceroute(ip, source_ip, max_ttl)


def _device_traceroute_ipv6(host: str, ip: str, max_ttl: int = 30) -> list[dict[str, Any]]:
    device = get_device_record(host)
    if not device:
        return [{"host": host, "target_ip": ip, "error": "device_not_found"}]
    driver = RuckusDeviceDriver(device)
    return driver.device_traceroute_ipv6(ip, max_ttl)


def _device_config_backup(host: str, config_type: str = "running", include_config: bool = False) -> dict[str, Any]:
    logger.info("device_config_backup: host=%s type=%s include_config=%s", host, config_type, include_config)
    if include_config:
        logger.warning("device_config_backup: include_config=True for %s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    data = driver.get_config(config_type)
    if "error" in data:
        return data

    config = data["config"]
    BACKUP_DIR.mkdir(mode=0o700, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_host = host.replace("/", "_").replace(":", "_")
    filename = f"{safe_host}_{config_type}_{timestamp}.cfg"
    path = BACKUP_DIR / filename
    path.write_text(config, encoding="utf-8")
    path.chmod(0o600)

    result: dict[str, Any] = {
        "host": host,
        "config_type": config_type,
        "path": str(path.relative_to(_BASE_DIR)),
        "sha256": data["sha256"],
        "size_kb": round(data["size_bytes"] / 1024, 2),
        "line_count": data["line_count"],
        "backed_up_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if include_config:
        result["config"] = config
    return result


def _device_config_diff(host: str, config_type: str = "running") -> dict[str, Any]:
    logger.info("device_config_diff: host=%s type=%s", host, config_type)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    data = driver.get_config(config_type)
    if "error" in data:
        return data

    current_sha = data["sha256"]
    safe_host = host.replace("/", "_").replace(":", "_")
    backups = sorted(BACKUP_DIR.glob(f"{safe_host}_{config_type}_*.cfg")) if BACKUP_DIR.exists() else []
    if not backups:
        return {
            "host": host, "config_type": config_type,
            "changed": True, "current_sha256": current_sha,
            "last_backup_sha256": None, "last_backup_at": None,
            "note": "no previous backup found",
        }
    latest = backups[-1]
    last_config = latest.read_text(encoding="utf-8").strip()
    last_sha = hashlib.sha256(last_config.encode("utf-8")).hexdigest()
    last_at: str | None = None
    ts_match = re.search(r"(\d{8}_\d{6})\.cfg$", latest.name)
    if ts_match:
        last_at = datetime.datetime.strptime(ts_match.group(1), "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    return {
        "host": host, "config_type": config_type,
        "changed": current_sha != last_sha,
        "current_sha256": current_sha,
        "last_backup_sha256": last_sha,
        "last_backup_path": str(latest.relative_to(_BASE_DIR)),
        "last_backup_at": last_at,
    }


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def ruckus_device_info(host: str) -> dict[str, Any]:
        """Get device info for a specific ICX switch."""
        return _device_info(host)

    @mcp.tool()
    def ruckus_device_status(host: str) -> dict[str, Any]:
        """Get device status for a specific ICX switch."""
        return _device_status(host)

    @mcp.tool()
    def ruckus_device_interfaces_summary(host: str) -> list[dict[str, Any]]:
        """Get interface summary for a specific ICX switch."""
        return _device_interfaces_summary(host)

    @mcp.tool()
    def ruckus_device_interfaces_down(host: str) -> list[dict[str, Any]]:
        """Get down interfaces for a specific ICX switch."""
        return _device_interfaces_down(host)

    @mcp.tool()
    def ruckus_device_interfaces_errors(host: str) -> list[dict[str, Any]]:
        """Get interfaces with errors for a specific ICX switch."""
        return _device_interfaces_errors(host)

    @mcp.tool()
    def ruckus_device_interfaces_stats(host: str) -> list[dict[str, Any]]:
        """Get interface utilization and traffic statistics for a specific ICX switch."""
        return _device_interfaces_stats(host)

    @mcp.tool()
    def ruckus_device_ip_addresses(host: str) -> list[dict[str, Any]]:
        """Get IP address bindings for a specific ICX switch."""
        return _device_ip_addresses(host)

    @mcp.tool()
    def ruckus_device_ip_routes(host: str, destination: str | None = None) -> dict[str, Any]:
        """Get IP routing table (show ip route). Optional longest-prefix lookup by destination (IP/CIDR)."""
        return _device_ip_routes(host, destination)

    @mcp.tool()
    def ruckus_device_ipv6_routes(host: str, destination: str | None = None) -> dict[str, Any]:
        """Get IPv6 routing table (show ipv6 route). Optional longest-prefix lookup by destination (IPv6/prefix)."""
        return _device_ipv6_routes(host, destination)

    @mcp.tool()
    def ruckus_device_vlan_summary(host: str) -> dict[str, Any]:
        """Get VLAN summary for a specific ICX switch."""
        return _device_vlan_summary(host)

    @mcp.tool()
    def ruckus_device_port_vlan(host: str, port: str) -> dict[str, Any]:
        """Get VLAN membership for a specific port on an ICX switch."""
        return _device_port_vlan(host, port)

    @mcp.tool()
    def ruckus_device_mac_table_vlan(host: str, vlan_id: int) -> list[dict[str, Any]]:
        """Get MAC address table for a specific VLAN on an ICX switch."""
        return _device_mac_table_vlan(host, vlan_id)

    @mcp.tool()
    def ruckus_device_find_mac(host: str, mac: str) -> list[dict[str, Any]]:
        """Find which port a specific MAC address is connected to."""
        return _device_find_mac(host, mac)

    @mcp.tool()
    def ruckus_device_lag_summary(host: str) -> list[dict[str, Any]]:
        """Get LAG (Link Aggregation Group) summary for a specific ICX switch."""
        return _device_lag_summary(host)

    @mcp.tool()
    def ruckus_device_chassis_health(host: str) -> dict[str, Any]:
        """Get chassis health (power supply, fan, temperature) for a specific ICX switch."""
        return _device_chassis_health(host)

    @mcp.tool()
    def ruckus_device_ipv6_interfaces(host: str) -> list[dict[str, Any]]:
        """Get IPv6 interface addresses for a specific ICX switch."""
        return _device_ipv6_interfaces(host)

    @mcp.tool()
    def ruckus_device_ping(host: str, ip: str, source: str | None = None) -> dict[str, Any]:
        """Ping test via ICMP (IPv4) from device with optional source IP."""
        return _device_ping(host, ip, source)

    @mcp.tool()
    def ruckus_device_ping_ipv6(host: str, ip: str) -> dict[str, Any]:
        """Ping test via ICMPv6 from device."""
        return _device_ping_ipv6(host, ip)

    @mcp.tool()
    def ruckus_device_traceroute(host: str, ip: str, source_ip: str | None = None, max_ttl: int = 30) -> list[dict[str, Any]]:
        """Traceroute (IPv4) from device with optional source IP."""
        return _device_traceroute(host, ip, source_ip, max_ttl)

    @mcp.tool()
    def ruckus_device_traceroute_ipv6(host: str, ip: str, max_ttl: int = 30) -> list[dict[str, Any]]:
        """Traceroute IPv6 from ICX switch."""
        return _device_traceroute_ipv6(host, ip, max_ttl)

    @mcp.tool()
    def ruckus_device_config_backup(host: str, config_type: str = "running", include_config: bool = False) -> dict[str, Any]:
        """Backup switch configuration to filesystem (restore-ready, mode 0600).

        Args:
            host: Device host (IP or name) from inventory.
            config_type: running (RAM, live) or startup (flash, boot).
            include_config: Return raw config text (default False, metadata only).
        """
        return _device_config_backup(host, config_type=config_type, include_config=include_config)

    @mcp.tool()
    def ruckus_device_config_diff(host: str, config_type: str = "running") -> dict[str, Any]:
        """Check if current config differs from latest backup (sha256 compare)."""
        return _device_config_diff(host, config_type=config_type)
