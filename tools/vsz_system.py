"""vSZ system/zone/license tools."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter
from tools._response import list_result

logger = logging.getLogger(__name__)


async def _zone_status() -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    zones = await adapter.get_zones()
    rows = [
        {
            "zone_id": z.get("id", ""),
            "name": z.get("name", ""),
            "description": z.get("description", ""),
            "ap_count": z.get("apCount", 0),
            "client_count": z.get("clientCount", 0),
            "status": z.get("status", ""),
        }
        for z in zones
    ]
    return list_result(rows, hint="use zone_ap_list(zone_id=...) for APs in a zone")


async def _zone_ap_list(zone_id: str) -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    aps = await adapter.get_aps_by_zone(zone_id)
    rows = [
        {
            "ap_name": ap.get("deviceName", ""),
            "status": ap.get("status", ""),
            "clients": ap.get("numClients", 0),
            "location": ap.get("location", ""),
            "zone": ap.get("zoneName", ""),
        }
        for ap in aps
    ]
    return list_result(rows, hint="use ap_detail(ap_name=...) for full record")


async def _license_status() -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    return await adapter.get_license()


async def _controller_stats() -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.controller_stats()
    if "error" in data:
        return data
    return data


def register_tools(mcp: FastMCP) -> None:
    """Register vSZ system/controller tools."""
    @mcp.tool()
    async def zone_status() -> dict[str, Any]:
        """Get zone status from vSZ."""
        return await _zone_status()

    @mcp.tool()
    async def zone_ap_list(zone_id: str) -> dict[str, Any]:
        """Get AP list for a specific zone."""
        return await _zone_ap_list(zone_id)

    @mcp.tool()
    async def license_status() -> dict[str, Any]:
        """Shows license status (total AP capacity, used, remaining)."""
        return await _license_status()

    @mcp.tool()
    async def controller_stats() -> dict[str, Any]:
        """Controller health stats — CPU, memory, disk, AP/client counts.

        Requires admin-level vSZ credentials (read-only users get 'not_authenticated').
        """
        return await _controller_stats()
