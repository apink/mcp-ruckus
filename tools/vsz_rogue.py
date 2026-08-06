"""vSZ rogue client detection tools."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)


async def _rogue_client_query(
    rogue_mac: str | None = None,
    ssid: str | None = None,
    rogue_type: str | None = None,
    domain_id: str | None = None,
    zone_id: str | None = None,
    limit: int = 100,
    page: int = 1,
) -> dict[str, Any]:
    logger.info("rogue_client_query: mac=%s ssid=%s type=%s", rogue_mac, ssid, rogue_type)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        logger.error("rogue_client_query: login failed %s", result["error"])
        return {"error": result["error"], "detail": result.get("detail", "")}

    data = await adapter.query_rogue_clients(
        domain_id=domain_id,
        zone_id=zone_id,
        rogue_mac=rogue_mac,
        ssid=ssid,
        rogue_type=rogue_type,
        page=page,
        limit=limit,
    )
    if "error" in data:
        return data

    raw_list = data.get("list", [])
    clients = []
    for c in raw_list:
        ap_info = []
        for ap in c.get("detectedByAP", []):
            ap_info.append({
                "ap_name": ap.get("apName", ""),
                "rssi": ap.get("rssi", ""),
                "zone_name": ap.get("zoneName", ""),
                "main_detector": ap.get("mainDetector", False),
            })
        t_ms = c.get("lastDetected", 0)
        t_str = datetime.datetime.fromtimestamp(t_ms / 1000).strftime('%Y-%m-%d %H:%M:%S') if t_ms else ""

        clients.append({
            "rogue_mac": c.get("rogueMac", ""),
            "ssid": c.get("ssid", ""),
            "type": c.get("type", ""),
            "encryption": c.get("encryption", ""),
            "channel": c.get("channel", ""),
            "rogue_ap_mac": c.get("rogueAPMac", ""),
            "last_detected": t_str,
            "classification": c.get("classification", ""),
            "detected_by": ap_info,
        })

    return {
        "total": data.get("totalCount", 0),
        "raw_total": data.get("rawDataTotalCount", 0),
        "has_more": data.get("hasMore", False),
        "page": page,
        "clients": clients,
    }


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def rogue_client_query(
        rogue_mac: str | None = None,
        ssid: str | None = None,
        rogue_type: str | None = None,
        domain_id: str | None = None,
        zone_id: str | None = None,
        limit: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Query rogue clients from vSZ. Support filter by MAC, SSID, type, domain, zone.

        Rogue types: Rogue, Suspect, Known, Unknown, AD_HOC, INFRASTRUCTURE
        """
        return await _rogue_client_query(
            rogue_mac=rogue_mac, ssid=ssid, rogue_type=rogue_type,
            domain_id=domain_id, zone_id=zone_id, limit=limit, page=page,
        )
