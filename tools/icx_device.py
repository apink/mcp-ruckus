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
from tools._response import list_result

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


def _device_interfaces_summary(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_interfaces_summary(), hint="see ruckus_device_port_vlan for per-port VLAN")


def _device_interfaces_down(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_interfaces_down(), hint="see ruckus_device_interfaces_summary for full detail")


def _device_interfaces_errors(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_interfaces_errors(), hint="see ruckus_device_cable_diag for TDR diagnostics")


def _device_interfaces_stats(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_interfaces_stats(), hint="see ruckus_device_interfaces_errors for error counters")


def _device_ip_addresses(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_ip_addresses(), hint="see ruckus_device_ip_routes for routing table")


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


def _device_mac_table_vlan(host: str, vlan_id: int, summary: bool = False) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    entries = driver.get_mac_table_vlan(vlan_id)
    if summary:
        by_port: dict[str, int] = {}
        for e in entries:
            p = e.get("port", "") or "unknown"
            by_port[p] = by_port.get(p, 0) + 1
        return {"total_entries": len(entries), "by_port": by_port}
    return list_result(entries, hint="see ruckus_device_find_mac to locate a MAC")


def _device_find_mac(host: str, mac: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.find_mac(mac), hint="see ruckus_device_mac_table_vlan for full MAC table")


def _device_lag_summary(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_lag_summary(), hint="see ruckus_device_interfaces_summary for member ports")


def _device_chassis_health(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_chassis_health()


def _device_ipv6_interfaces(host: str) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_ipv6_interfaces(), hint="see ruckus_device_ipv6_routes for IPv6 routes")


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


def _device_traceroute(host: str, ip: str, source_ip: str | None = None, max_ttl: int = 30) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "target_ip": ip, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.device_traceroute(ip, source_ip, max_ttl), hint="see ruckus_device_ping for reachability")


def _device_traceroute_ipv6(host: str, ip: str, max_ttl: int = 30) -> dict[str, Any]:
    device = get_device_record(host)
    if not device:
        return {"host": host, "target_ip": ip, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.device_traceroute_ipv6(ip, max_ttl), hint="see ruckus_device_ping_ipv6 for reachability")


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


def _device_lldp_neighbors(host: str) -> dict[str, Any]:
    logger.info("device_lldp_neighbors: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_lldp_neighbors(), hint="see ruckus_device_interfaces_summary for port detail")


def _device_poe_status(host: str) -> dict[str, Any]:
    logger.info("device_poe_status: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_poe_status()


def _device_arp_table(host: str, summary: bool = False) -> dict[str, Any]:
    logger.info("device_arp_table: host=%s summary=%s", host, summary)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    entries = driver.get_arp_table()
    if summary:
        by_port: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for e in entries:
            p = e.get("port", "") or "unknown"
            t = e.get("type", "") or "unknown"
            by_port[p] = by_port.get(p, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1
        return {"total_entries": len(entries), "by_port": by_port, "by_type": by_type}
    return list_result(entries, hint="see ruckus_device_find_mac to locate a MAC")


def _device_resources(host: str) -> dict[str, Any]:
    logger.info("device_resources: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_device_resources()


def _device_sfp_info(host: str, port: str | None = None) -> dict[str, Any]:
    logger.info("device_sfp_info: host=%s port=%s", host, port)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_sfp_info(port), hint="see ruckus_device_optic_info for DOM readings")


def _device_cable_diag(host: str, port: str) -> dict[str, Any]:
    logger.info("device_cable_diag: host=%s port=%s", host, port)
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_cable_diag(port)


def _device_syslog(host: str, lines: int = 50, severity: str = "", dedup: bool = True) -> dict[str, Any]:
    logger.info("device_syslog: host=%s lines=%s severity=%s dedup=%s", host, lines, severity, dedup)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_syslog(lines=lines, severity=severity, dedup=dedup)


def _device_optic_info(host: str, port: str) -> dict[str, Any]:
    logger.info("device_optic_info: host=%s port=%s", host, port)
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_optic_info(port)


def _device_time(host: str) -> dict[str, Any]:
    logger.info("device_time: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_device_time()


def _device_spanning_tree(host: str, vlan: str | None = None) -> dict[str, Any]:
    logger.info("device_spanning_tree: host=%s vlan=%s", host, vlan)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_spanning_tree(vlan)


def _device_access_lists(host: str, name: str | None = None, brief: bool = False) -> dict[str, Any]:
    logger.info("device_access_lists: host=%s acl=%s brief=%s", host, name, brief)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_access_lists(name, brief)


def _device_users(host: str) -> dict[str, Any]:
    logger.info("device_users: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return list_result(driver.get_users(), hint="see ruckus_device_ssh_status for active sessions")


def _device_ssh_status(host: str) -> dict[str, Any]:
    logger.info("device_ssh_status: host=%s", host)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_ssh_status()


def _device_port_state(host: str, port: str, enable: bool, dry_run: bool = False) -> dict[str, Any]:
    logger.info(
        "device_port_state: host=%s port=%s enable=%s dry_run=%s",
        host, port, enable, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.set_port_state(port, enable, dry_run=dry_run)


def _device_vlan_create(
    host: str, vlan_spec: str, name: str | None = None,
    tagged_ports: str = "", untagged_ports: str = "",
    spanning_tree: bool = False, stp_priority: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_vlan_create: host=%s spec=%s name=%s stp=%s dry_run=%s",
        host, vlan_spec, name, spanning_tree, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "vlan_spec": vlan_spec, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.create_vlan(
        vlan_spec, name=name, tagged_ports=tagged_ports,
        untagged_ports=untagged_ports, spanning_tree=spanning_tree,
        stp_priority=stp_priority, dry_run=dry_run,
    )


def _device_vlan_delete(
    host: str, vlan_spec: str, dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_vlan_delete: host=%s spec=%s dry_run=%s",
        host, vlan_spec, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "vlan_spec": vlan_spec, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.delete_vlan(vlan_spec, dry_run=dry_run)


def _device_vlan_port(
    host: str, port: str, vlan_spec: str, action: str,
    tagged: bool = True, dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_vlan_port: host=%s port=%s action=%s spec=%s tagged=%s dry_run=%s",
        host, port, action, vlan_spec, tagged, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.modify_vlan_port(port, vlan_spec, action, tagged=tagged, dry_run=dry_run)


def _device_poe_port(
    host: str, port: str, enable: bool,
    priority: int | None = None,
    power_limit: int | None = None,
    power_by_class: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_poe_port: host=%s port=%s enable=%s dry_run=%s",
        host, port, enable, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "port": port, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.set_poe_port(
        port, enable, priority=priority, power_limit=power_limit,
        power_by_class=power_by_class, dry_run=dry_run,
    )


def _device_poe_status(host: str, port: str | None = None) -> dict[str, Any]:
    logger.info("device_poe_status: host=%s port=%s", host, port)
    device = get_device_record(host)
    if not device:
        return {"host": host, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.get_poe_status(port=port)


def _device_ip_route(
    host: str, dest: str, mask: str, next_hop: str,
    metric: int | None = None, distance: int | None = None,
    name: str | None = None, tag: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_ip_route: host=%s dest=%s/%s next_hop=%s dry_run=%s",
        host, dest, mask, next_hop, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "dest": dest, "mask": mask, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.add_static_route(
        dest, mask, next_hop, metric=metric, distance=distance,
        name=name, tag=tag, dry_run=dry_run,
    )


def _device_ip_route_delete(
    host: str, dest: str, mask: str, next_hop: str, dry_run: bool = False,
) -> dict[str, Any]:
    logger.info(
        "device_ip_route_delete: host=%s dest=%s/%s next_hop=%s dry_run=%s",
        host, dest, mask, next_hop, dry_run,
    )
    device = get_device_record(host)
    if not device:
        return {"host": host, "dest": dest, "mask": mask, "error": "device_not_found"}
    driver = RuckusDeviceDriver(device)
    return driver.delete_static_route(dest, mask, next_hop, dry_run=dry_run)


def register_tools(mcp: FastMCP) -> None:
    """Register ICX device tools (ruckus_ prefix)."""
    @mcp.tool()
    def ruckus_device_info(host: str) -> dict[str, Any]:
        """Get device info for a specific ICX switch."""
        return _device_info(host)

    @mcp.tool()
    def ruckus_device_status(host: str) -> dict[str, Any]:
        """Get device status for a specific ICX switch."""
        return _device_status(host)

    @mcp.tool()
    def ruckus_device_interfaces_summary(host: str) -> dict[str, Any]:
        """Get interface summary for a specific ICX switch."""
        return _device_interfaces_summary(host)

    @mcp.tool()
    def ruckus_device_interfaces_down(host: str) -> dict[str, Any]:
        """Get down interfaces for a specific ICX switch."""
        return _device_interfaces_down(host)

    @mcp.tool()
    def ruckus_device_interfaces_errors(host: str) -> dict[str, Any]:
        """Get interfaces with errors for a specific ICX switch."""
        return _device_interfaces_errors(host)

    @mcp.tool()
    def ruckus_device_interfaces_stats(host: str) -> dict[str, Any]:
        """Get interface utilization and traffic statistics for a specific ICX switch."""
        return _device_interfaces_stats(host)

    @mcp.tool()
    def ruckus_device_ip_addresses(host: str) -> dict[str, Any]:
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
    def ruckus_device_mac_table_vlan(host: str, vlan_id: int, summary: bool = False) -> dict[str, Any]:
        """Get MAC address table for a specific VLAN on an ICX switch.

        summary=True returns aggregate counts (total_entries, by_port)
        instead of the full list.
        """
        return _device_mac_table_vlan(host, vlan_id, summary=summary)

    @mcp.tool()
    def ruckus_device_find_mac(host: str, mac: str) -> dict[str, Any]:
        """Find which port a specific MAC address is connected to."""
        return _device_find_mac(host, mac)

    @mcp.tool()
    def ruckus_device_lag_summary(host: str) -> dict[str, Any]:
        """Get LAG (Link Aggregation Group) summary for a specific ICX switch."""
        return _device_lag_summary(host)

    @mcp.tool()
    def ruckus_device_chassis_health(host: str) -> dict[str, Any]:
        """Get chassis health (power supply, fan, temperature) for a specific ICX switch."""
        return _device_chassis_health(host)

    @mcp.tool()
    def ruckus_device_ipv6_interfaces(host: str) -> dict[str, Any]:
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
    def ruckus_device_traceroute(
        host: str, ip: str, source_ip: str | None = None, max_ttl: int = 30
    ) -> dict[str, Any]:
        """Traceroute (IPv4) from device with optional source IP."""
        return _device_traceroute(host, ip, source_ip, max_ttl)

    @mcp.tool()
    def ruckus_device_traceroute_ipv6(host: str, ip: str, max_ttl: int = 30
                                      ) -> dict[str, Any]:
        """Traceroute IPv6 from ICX switch."""
        return _device_traceroute_ipv6(host, ip, max_ttl)

    @mcp.tool()
    def ruckus_device_config_backup(
        host: str, config_type: str = "running", include_config: bool = False
    ) -> dict[str, Any]:
        """Backup switch configuration to filesystem (restore-ready, mode 0600).

        Args:
            host: Device host (IP or name) from inventory.
            config_type: running (RAM, live) or startup (flash, boot).
            include_config: Return raw config text (default False, metadata only).
        """
        return _device_config_backup(host, config_type=config_type, include_config=include_config)

    @mcp.tool()
    def ruckus_device_config_diff(
        host: str, config_type: str = "running"
    ) -> dict[str, Any]:
        """Check if current config differs from latest backup (sha256 compare)."""
        return _device_config_diff(host, config_type=config_type)

    @mcp.tool()
    def ruckus_device_lldp_neighbors(host: str) -> dict[str, Any]:
        """Get LLDP neighbors for an ICX switch — remote device, port, description per local interface."""
        return _device_lldp_neighbors(host)

    @mcp.tool()
    def ruckus_device_arp_table(host: str, summary: bool = False) -> dict[str, Any]:
        """Get ARP table for an ICX switch — IP-to-MAC-to-port mapping for L2/L3 troubleshooting.

        summary=True returns aggregate counts (total_entries, by_port, by_type)
        instead of the full list.
        """
        return _device_arp_table(host, summary=summary)

    @mcp.tool()
    def ruckus_device_resources(host: str) -> dict[str, Any]:
        """Get CPU and memory utilization for an ICX switch — per-core load averages + DRAM usage."""
        return _device_resources(host)

    @mcp.tool()
    def ruckus_device_sfp_info(host: str, port: str | None = None) -> dict[str, Any]:
        """Get SFP/transceiver info for an ICX switch — port type, vendor, serial. Optional port filter."""
        return _device_sfp_info(host, port)

    @mcp.tool()
    def ruckus_device_cable_diag(host: str, port: str) -> dict[str, Any]:
        """Run TDR cable diagnostic on an ICX copper port — per-pair status (terminated, open, short)."""
        return _device_cable_diag(host, port)

    @mcp.tool()
    def ruckus_device_syslog(host: str, lines: int = 50, severity: str = "",
                             dedup: bool = True) -> dict[str, Any]:
        """Token-optimized ICX syslog: last N entries, optional severity filter (E=error, W=warning, I=info),
        dedup collapses repeated messages. Default 50 lines, dedup on."""
        return _device_syslog(host, lines=lines, severity=severity, dedup=dedup)

    @mcp.tool()
    def ruckus_device_optic_info(host: str, port: str) -> dict[str, Any]:
        """Get SFP optic DOM info for an ICX port — temperature, voltage, tx/rx power, bias."""
        return _device_optic_info(host, port)

    @mcp.tool()
    def ruckus_device_time(host: str) -> dict[str, Any]:
        """Check ICX switch time + NTP sync status — current clock, NTP peers, sync state."""
        return _device_time(host)

    @mcp.tool()
    def ruckus_device_spanning_tree(host: str, vlan: str | None = None) -> dict[str, Any]:
        """Show STP topology — root bridge, port roles, per-port state (FORWARDING, BLOCKING, DISABLED)."""
        return _device_spanning_tree(host, vlan)

    @mcp.tool()
    def ruckus_device_access_lists(
        host: str, name: str | None = None, brief: bool = False
    ) -> dict[str, Any]:
        """List IP ACLs (all or specific). brief=True gives summary list (name + entries count)."""
        return _device_access_lists(host, name, brief)

    @mcp.tool()
    def ruckus_device_users(host: str) -> dict[str, Any]:
        """List local user accounts on an ICX switch — username, privilege, status, expire time."""
        return _device_users(host)

    @mcp.tool()
    def ruckus_device_ssh_status(host: str) -> dict[str, Any]:
        """Show SSH server status + active SSH sessions — version, host key, per-session user/source IP."""
        return _device_ssh_status(host)

    @mcp.tool()
    def ruckus_device_port_state(
        host: str, port: str, enable: bool, confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Enable or disable an ICX switch port (admin up/down) via SSH config mode.

        Args:
            host: Device host (IP or name) from inventory.
            port: Port identifier (e.g., 1/1/24).
            enable: True to enable (admin up), False to disable (admin down).
            confirm: Set to True to execute. Without it, returns confirm_required error.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_port_state(host, port, enable, dry_run=True)
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to enable/disable the port",
            }
        return _device_port_state(host, port, enable)

    # ── VLAN Tools (destructive) ──────────────────────────────────

    @mcp.tool()
    def ruckus_device_vlan_create(
        host: str,
        vlan_spec: str,
        name: str | None = None,
        tagged_ports: str = "",
        untagged_ports: str = "",
        spanning_tree: bool = False,
        stp_priority: int | None = None,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create VLAN(s) on ICX switch.

        Args:
            host: Device host from inventory.
            vlan_spec: VLAN ID, range, or list. Examples: '200', '210 to 213',
                       '200 210 220', '16 17 20 to 24'.
            name: Optional VLAN name (single VLAN only).
            tagged_ports: Tagged port spec (e.g. 'ethernet 1/1/1 to 1/1/4 ethernet 1/1/17').
            untagged_ports: Untagged port spec (single VLAN only).
            spanning_tree: Enable STP (802-1w for multi-range, RSTP for single).
            stp_priority: STP bridge priority (single VLAN only, 0-61440, multiple of 4096).
            confirm: Set to True to execute. Without it, returns confirm_required error.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_vlan_create(
                host, vlan_spec, name=name, tagged_ports=tagged_ports,
                untagged_ports=untagged_ports, spanning_tree=spanning_tree,
                stp_priority=stp_priority, dry_run=True,
            )
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to create VLAN(s)",
            }
        return _device_vlan_create(
            host, vlan_spec, name=name, tagged_ports=tagged_ports,
            untagged_ports=untagged_ports, spanning_tree=spanning_tree,
            stp_priority=stp_priority,
        )

    @mcp.tool()
    def ruckus_device_vlan_delete(
        host: str, vlan_spec: str, confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete VLAN(s) from ICX switch.

        Args:
            host: Device host from inventory.
            vlan_spec: VLAN spec as in create (single, range, multi, mixed).
            confirm: Set to True to execute.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_vlan_delete(host, vlan_spec, dry_run=True)
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to delete VLAN(s)",
            }
        return _device_vlan_delete(host, vlan_spec)

    @mcp.tool()
    def ruckus_device_vlan_port(
        host: str,
        port: str,
        vlan_spec: str,
        action: str = "add",
        tagged: bool = True,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add or remove a port from VLAN membership via interface vlan-config.

        Args:
            host: Device host from inventory.
            port: Target port (e.g. '1/1/1').
            vlan_spec: VLAN spec to add/remove port from.
            action: 'add' or 'remove'. Add creates membership, remove strips VLANs from port.
            tagged: True for tagged membership (add only), False for untagged.
            confirm: Set to True to execute.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_vlan_port(
                host, port, vlan_spec, action, tagged=tagged, dry_run=True,
            )
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to modify VLAN port membership",
            }
        return _device_vlan_port(host, port, vlan_spec, action, tagged=tagged)

    # ── PoE Tools ──────────────────────────────────────────────────

    @mcp.tool()
    def ruckus_device_poe_port(
        host: str,
        port: str,
        enable: bool = True,
        priority: int | None = None,
        power_limit: int | None = None,
        power_by_class: int | None = None,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Enable/disable PoE on a port with optional priority, power-limit, or class.

        Unlike port_state (admin up/down), this only toggles inline power —
        the data link stays up.

        Power classes (IEEE 802.3): 0=15.4W  1=4W  2=7W  3=15.4W
        4=30W  5=45W  6=60W  7=75W  8=90W
        Priority: 1=critical  2=high  3=low (default)

        Args:
            host: Device host from inventory.
            port: Port identifier (e.g. '1/1/1').
            enable: True to supply PoE, False to cut power.
            priority: Optional — 1(critical), 2(high), 3(low). Required if setting
                      power_limit or power_by_class (ICX syntax rule).
            power_limit: Optional power limit in mW (e.g. 30000 for 30W).
            power_by_class: Optional IEEE class 0-8. Auto-sets power limit.
            confirm: Set to True to execute.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_poe_port(
                host, port, enable, priority=priority,
                power_limit=power_limit, power_by_class=power_by_class,
                dry_run=True,
            )
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to toggle PoE on port",
            }
        return _device_poe_port(
            host, port, enable, priority=priority,
            power_limit=power_limit, power_by_class=power_by_class,
        )

    @mcp.tool()
    def ruckus_device_poe_status(
        host: str,
        port: str | None = None,
    ) -> dict[str, Any]:
        """Read PoE status per port (no SSH write, safe to run any time).

        If port is specified returns single port status; otherwise returns
        all 48 ports with capacity summary.

        Args:
            host: Device host from inventory.
            port: Optional port (e.g. '1/1/1') for single-port lookup.
        """
        return _device_poe_status(host, port=port)

    # ── Static Route Tools (destructive) ──────────────────────────

    @mcp.tool()
    def ruckus_device_ip_route(
        host: str,
        dest: str,
        mask: str,
        next_hop: str,
        metric: int | None = None,
        distance: int | None = None,
        name: str | None = None,
        tag: int | None = None,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add a static IPv4 route to an ICX switch.

        next_hop may be an IPv4 next-hop address, 'null0' (blackhole/drop),
        or an outgoing interface ('ethernet 1/1/1', 'lag 1', 've 10').

        Args:
            host: Device host from inventory.
            dest: Destination IPv4 address (e.g. '192.0.2.0').
            mask: Dotted-quad netmask (e.g. '255.255.255.0').
            next_hop: Next hop — IPv4 address, 'null0', 'ethernet <port>',
                      'lag <id>', or 've <id>'.
            metric: Optional cost metric (1-16, default 1).
            distance: Optional administrative distance (1-255).
            name: Optional route name (alphanumeric/_/./-, 1-32 chars).
            tag: Optional route tag (0-4294967295).
            confirm: Set to True to execute. Without it, returns confirm_required.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_ip_route(
                host, dest, mask, next_hop, metric=metric, distance=distance,
                name=name, tag=tag, dry_run=True,
            )
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to add static route",
            }
        return _device_ip_route(
            host, dest, mask, next_hop, metric=metric, distance=distance,
            name=name, tag=tag,
        )

    @mcp.tool()
    def ruckus_device_ip_route_delete(
        host: str,
        dest: str,
        mask: str,
        next_hop: str,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete a static IPv4 route from an ICX switch.

        Args:
            host: Device host from inventory.
            dest: Destination IPv4 address (e.g. '192.0.2.0').
            mask: Dotted-quad netmask (e.g. '255.255.255.0').
            next_hop: Next hop to remove — same form used when adding
                      (IPv4 address, 'null0', 'ethernet <port>', 'lag <id>', or 've <id>').
            confirm: Set to True to execute. Without it, returns confirm_required.
            dry_run: If True, returns planned commands without executing.
        """
        if dry_run:
            return _device_ip_route_delete(host, dest, mask, next_hop, dry_run=True)
        if not confirm:
            return {
                "error": "confirm_required",
                "detail": "Set confirm=True to delete static route",
            }
        return _device_ip_route_delete(host, dest, mask, next_hop)
