"""vSZ traffic stats — per-WLAN, per-AP, per-zone aggregations from client data."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)

PAGE_SIZE = 500


async def _fetch_all_clients(ssid: str | None = None,
                              ap_name: str | None = None
                              ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return [], result
    all_clients: list[dict[str, Any]] = []
    page = 1
    while True:
        data = await adapter.query_clients(limit=PAGE_SIZE, page=page,
                                            ssid=ssid, ap_name=ap_name)
        if "error" in data:
            return [], data
        batch = data.get("list", [])
        all_clients.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return all_clients, None


def _build_zone_map(zones: list[dict[str, Any]]) -> dict[str, str]:
    return {z["id"]: z.get("name", z["id"]) for z in zones if "id" in z}


# ── Per-WLAN Traffic ──────────────────────────────────

async def _wlan_traffic_stats(ssid: str | None = None,
                               zone_id: str | None = None,
                               ) -> dict[str, Any]:
    clients, err = await _fetch_all_clients(ssid=ssid)
    if err:
        return err

    adapter = VsZRestAdapter()
    await adapter.login()
    zones = _build_zone_map(await adapter.get_zones())

    wlans: dict[str, dict[str, Any]] = {}
    for c in clients:
        zid = c.get("zoneId", "")
        if zone_id and zid != zone_id:
            continue
        wlan_key = c.get("ssid", "Unknown")
        zn = zones.get(zid, zid)
        if wlan_key not in wlans:
            wlans[wlan_key] = {
                "ssid": wlan_key,
                "zones": {},
                "total_clients": 0,
                "total_rx_bytes": 0,
                "total_tx_bytes": 0,
            }
        w = wlans[wlan_key]
        w["total_clients"] += 1
        w["total_rx_bytes"] += c.get("rxBytes", 0) or 0
        w["total_tx_bytes"] += c.get("txBytes", 0) or 0
        if zn not in w["zones"]:
            w["zones"][zn] = {"clients": 0, "rx_bytes": 0, "tx_bytes": 0}
        w["zones"][zn]["clients"] += 1
        w["zones"][zn]["rx_bytes"] += c.get("rxBytes", 0) or 0
        w["zones"][zn]["tx_bytes"] += c.get("txBytes", 0) or 0

    result: list[dict[str, Any]] = []
    for wlan_key, data in sorted(wlans.items()):
        entry = {
            "ssid": data["ssid"],
            "total_clients": data["total_clients"],
            "total_rx_mb": round(data["total_rx_bytes"] / 1_048_576, 2),
            "total_tx_mb": round(data["total_tx_bytes"] / 1_048_576, 2),
            "zone_breakdown": [
                {"zone": zn, "clients": zd["clients"],
                 "rx_mb": round(zd["rx_bytes"] / 1_048_576, 2),
                 "tx_mb": round(zd["tx_bytes"] / 1_048_576, 2)}
                for zn, zd in sorted(data["zones"].items())
            ],
        }
        result.append(entry)
    return {"wlans": result, "total_wlans": len(result)}


# ── Per-AP Traffic ────────────────────────────────────

async def _ap_traffic_stats(zone_id: str | None = None,
                              ap_name: str | None = None,
                              ) -> dict[str, Any]:
    clients, err = await _fetch_all_clients(ap_name=ap_name)
    if err:
        return err

    # Also get AP info from adapter for context
    adapter = VsZRestAdapter()
    await adapter.login()
    all_aps = await adapter.get_all_aps()
    ap_zone: dict[str, str] = {}
    ap_model: dict[str, str] = {}
    for ap in all_aps:
        mac = ap.get("apMac", "")
        ap_zone[mac] = ap.get("zoneName", "")
        ap_model[mac] = ap.get("model", "")

    aps: dict[str, dict[str, Any]] = {}
    for c in clients:
        mac = c.get("apMac", "")
        if zone_id and c.get("zoneId", "") != zone_id:
            continue
        ap_key = c.get("apName") or mac
        if ap_key not in aps:
            aps[ap_key] = {
                "ap_name": ap_key,
                "ap_mac": mac,
                "zone_name": ap_zone.get(mac, ""),
                "model": ap_model.get(mac, ""),
                "total_clients": 0,
                "total_rx_bytes": 0,
                "total_tx_bytes": 0,
                "ssid_breakdown": {},
            }
        a = aps[ap_key]
        a["total_clients"] += 1
        a["total_rx_bytes"] += c.get("rxBytes", 0) or 0
        a["total_tx_bytes"] += c.get("txBytes", 0) or 0

    result: list[dict[str, Any]] = []
    for ap_key, data in sorted(aps.items()):
        result.append({
            "ap_name": data["ap_name"],
            "ap_mac": data["ap_mac"],
            "zone_name": data["zone_name"],
            "model": data["model"],
            "total_clients": data["total_clients"],
            "total_rx_mb": round(data["total_rx_bytes"] / 1_048_576, 2),
            "total_tx_mb": round(data["total_tx_bytes"] / 1_048_576, 2),
        })
    return {"aps": result, "total_aps": len(result)}


# ── Per-Zone Traffic ──────────────────────────────────

async def _zone_traffic_stats() -> dict[str, Any]:
    clients, err = await _fetch_all_clients()
    if err:
        return err

    adapter = VsZRestAdapter()
    await adapter.login()
    zones = await adapter.get_zones()
    zone_map = _build_zone_map(zones)

    all_aps = await adapter.get_all_aps()
    zone_ap_count: dict[str, int] = defaultdict(int)
    for ap in all_aps:
        zid = ap.get("zoneId", "")
        if zid:
            zone_ap_count[zid] += 1

    zstats: dict[str, dict[str, Any]] = {}
    for c in clients:
        zid = c.get("zoneId", "")
        zn = zone_map.get(zid, zid)
        if zn not in zstats:
            zstats[zn] = {
                "zone_name": zn,
                "zone_id": zid,
                "ap_count": zone_ap_count.get(zid, 0),
                "total_clients": 0,
                "total_rx_bytes": 0,
                "total_tx_bytes": 0,
                "wlans_seen": set(),
            }
        zs = zstats[zn]
        zs["total_clients"] += 1
        zs["total_rx_bytes"] += c.get("rxBytes", 0) or 0
        zs["total_tx_bytes"] += c.get("txBytes", 0) or 0
        ssid = c.get("ssid", "")
        if ssid:
            zs["wlans_seen"].add(ssid)

    result: list[dict[str, Any]] = []
    for zn, data in sorted(zstats.items()):
        result.append({
            "zone_name": data["zone_name"],
            "zone_id": data["zone_id"],
            "ap_count": data["ap_count"],
            "total_clients": data["total_clients"],
            "total_rx_mb": round(data["total_rx_bytes"] / 1_048_576, 2),
            "total_tx_mb": round(data["total_tx_bytes"] / 1_048_576, 2),
            "active_wlans": len(data["wlans_seen"]),
        })
    return {"zones": result, "total_zones": len(result)}


# ── Tool Registration ─────────────────────────────────

def register_tools(mcp: FastMCP) -> None:
    """Register vSZ traffic analytics tools."""
    @mcp.tool()
    async def wlan_traffic_stats(ssid: str | None = None,
                                  zone_id: str | None = None,
                                  ) -> dict[str, Any]:
        """Per-WLAN traffic statistics aggregated from all connected clients.

        Returns total rx/tx MB and client count per SSID, with per-zone breakdown.
        Optional ssid filter for single WLAN, zone_id filter for single zone.

        Args:
            ssid: Filter to a specific SSID (e.g. 'eduroam').
            zone_id: Filter to a specific zone UUID.
        """
        return await _wlan_traffic_stats(ssid=ssid, zone_id=zone_id)

    @mcp.tool()
    async def ap_traffic_stats(zone_id: str | None = None,
                                ap_name: str | None = None,
                                ) -> dict[str, Any]:
        """Per-AP traffic statistics aggregated from connected clients.

        Returns total rx/tx MB and client count per access point.
        Optional zone_id or ap_name filter.

        Args:
            zone_id: Limit to APs in a specific zone UUID.
            ap_name: Limit to a specific AP device name.
        """
        return await _ap_traffic_stats(zone_id=zone_id, ap_name=ap_name)

    @mcp.tool()
    async def zone_traffic_stats() -> dict[str, Any]:
        """Per-zone traffic statistics aggregated from all connected clients.

        Returns total rx/tx MB, client count, AP count, and active WLAN count per zone.
        """
        return await _zone_traffic_stats()
