"""vSZ client tools — search, roaming history."""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)


async def _client_search(query: str, limit: int = 20, include_traffic: bool = False) -> dict[str, Any]:
    logger.info("client_search: query=%s limit=%d", query, limit)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.query_client(query)
    if data.get("totalCount", 0) == 0:
        return {"query": query, "total": 0, "clients": []}
    clients = []
    for c in data.get("list", [])[:limit]:
        client = {
            "hostname": c.get("hostname", ""),
            "username": c.get("userName", ""),
            "os_type": c.get("osType", ""),
            "device_type": c.get("deviceType", ""),
            "ipv4": c.get("ipAddress", ""),
            "ipv6": c.get("ipv6Address", ""),
            "mac": c.get("clientMac", ""),
            "ssid": c.get("ssid", ""),
            "bssid": c.get("bssid", ""),
            "vlan": c.get("vlan", 0),
            "rssi": c.get("rssi", 0),
            "snr": c.get("snr", 0),
            "channel": c.get("channel", ""),
            "radio_type": c.get("radioType", ""),
            "tx_rate_bps": c.get("txRatebps", 0),
            "auth_method": c.get("authMethod", ""),
            "encryption": c.get("encryptionMethod", ""),
            "ap_name": c.get("apName", ""),
            "ap_mac": c.get("apMac", ""),
            "ap_location": c.get("apLocation", ""),
        }
        if include_traffic:
            client["tx_mbytes"] = round(c.get("txBytes", 0) / 1_000_000, 2) if c.get("txBytes") else 0
            client["rx_mbytes"] = round(c.get("rxBytes", 0) / 1_000_000, 2) if c.get("rxBytes") else 0
            client["uplink_mbytes"] = round(c.get("uplink", 0) / 1_000_000, 2) if c.get("uplink") else 0
            client["downlink_mbytes"] = round(c.get("downlink", 0) / 1_000_000, 2) if c.get("downlink") else 0
            client["median_tx_mcs"] = c.get("medianTxMCSRate", 0)
            client["median_rx_mcs"] = c.get("medianRxMCSRate", 0)
            client["session_start"] = c.get("sessionStartTime", 0)
        clients.append(client)
    return {"query": query, "total": data.get("totalCount", 0), "clients": clients, "limit": limit}


async def _client_roaming(query: str, limit: int = 30, severity: str = "Informational") -> dict[str, Any]:
    logger.info("client_roaming: query=%s limit=%d severity=%s", query, limit, severity)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        logger.error("client_roaming: login failed %s", result["error"])
        return {"error": result["error"], "detail": result.get("detail", "")}

    data = await adapter.get_alert_events(
        limit=limit, text_search=query, category="Client", severity=severity,
    )
    events = data.get("list", [])
    total = data.get("totalCount", 0)

    if not events:
        return {"query": query, "total_events": 0, "total_devices": 0, "devices": []}

    devices: dict[str, dict] = {}
    mac_pattern = re.compile(r'@([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})')
    ip_pattern = re.compile(r'@(\d+\.\d+\.\d+\.\d+)@')
    ap_pattern = re.compile(r'from AP \[([^\]]+@[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})\]')
    ssid_pattern = re.compile(r'on WLAN \[([^\]]+)\]')

    for e in events:
        act = e.get("activity", "")
        mac_m = mac_pattern.search(act)
        if not mac_m:
            continue
        mac = mac_m.group(1).lower()
        ip_m = ip_pattern.search(act)
        ip = ip_m.group(1) if ip_m else ""
        ap_m = ap_pattern.search(act)
        ap = ap_m.group(1) if ap_m else ""
        ssid_m = ssid_pattern.search(act)
        ssid = ssid_m.group(1) if ssid_m else ""

        ap_name = ap.split("@")[0] if "@" in ap else ap

        t_ms = e.get("insertionTime", 0)
        t_str = datetime.datetime.fromtimestamp(t_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')

        if mac not in devices:
            devices[mac] = {"mac": mac, "ip_addresses": set(), "aps": [], "events": [], "ssid": ssid}

        devices[mac]["ip_addresses"].add(ip)
        devices[mac]["aps"].append({"ap": ap_name, "time": t_str})
        devices[mac]["events"].append({"time": t_str, "event_type": e.get("eventType", ""), "ap": ap_name, "ip": ip, "activity": act})

    result_devices = []
    for mac, dev in devices.items():
        result_devices.append({
            "mac": dev["mac"],
            "ssid": dev["ssid"],
            "ip_addresses": sorted(dev["ip_addresses"]),
            "total_events": len(dev["events"]),
            "roaming_timeline": [
                {"time": ap["time"], "ap": ap["ap"]}
                for ap in dev["aps"]
            ],
            "events": dev["events"],
        })

    result_devices.sort(key=lambda d: d["total_events"], reverse=True)

    return {
        "query": query,
        "total_events": total,
        "events_fetched": len(events),
        "total_devices": len(devices),
        "devices": result_devices,
    }


async def _disconnect_client(client_mac: str, ap_mac: str, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {"error": "confirm_required", "detail": "Set confirm=True to disconnect the client"}
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.disconnect_client(client_mac, ap_mac)
    if "error" in data:
        return data
    return {"client_mac": client_mac, "ap_mac": ap_mac, "status": "disconnect_initiated"}


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def client_search(query: str, limit: int = 20, include_traffic: bool = False) -> dict[str, Any]:
        """Search client by ID, username, MAC, or IP.

        Default returns compact view. Set include_traffic=True for tx/rx MB and MCS rates.
        """
        return await _client_search(query, limit=limit, include_traffic=include_traffic)

    @mcp.tool()
    async def client_roaming(query: str, limit: int = 30, severity: str = "Informational") -> dict[str, Any]:
        """Track client roaming history from vSZ event log.

        Default severity=Informational returns only roam/join/leave events.
        Override to empty string to include all severities (Critical, Warning, etc.).
        """
        return await _client_roaming(query=query, limit=limit, severity=severity)

    @mcp.tool()
    async def disconnect_client(client_mac: str, ap_mac: str, confirm: bool = False) -> dict[str, Any]:
        """Disconnect a wireless client from an AP.

        Args:
            client_mac: Client MAC address.
            ap_mac: AP MAC address the client is connected to.
            confirm: Must be True to execute (safety latch).
        """
        return await _disconnect_client(client_mac, ap_mac, confirm=confirm)
