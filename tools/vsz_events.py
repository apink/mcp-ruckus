"""vSZ alert/event log tools."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)


async def _alert_events(
    limit: int = 20,
    severity: str | None = None,
    category: str | None = None,
    hours_back: int | None = None,
    text_search: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    logger.info("alert_events: severity=%s category=%s hours_back=%s limit=%d page=%d", severity, category, hours_back, limit, page)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.get_alert_events(
        limit=limit,
        severity=severity,
        category=category,
        hours_back=hours_back,
        text_search=text_search,
        page=page,
    )
    return {
        "totalCount": data.get("totalCount", 0),
        "firstIndex": data.get("firstIndex", 0),
        "hasMore": data.get("hasMore", False),
        "page": page,
        "limit": limit,
        "events": [
            {
                "id": e.get("id", ""),
                "time_ms": e.get("insertionTime", 0),
                "event_type": e.get("eventType", ""),
                "event_code": e.get("eventCode", 0),
                "severity": e.get("severity", ""),
                "category": e.get("category", ""),
                "activity": e.get("activity", ""),
            }
            for e in data.get("list", [])
        ],
    }


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def alert_events(
        limit: int = 20,
        severity: str | None = None,
        category: str | None = None,
        hours_back: int | None = None,
        text_search: str | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """Retrieve alert/event log from vSZ with server-side filters.

        Args:
            limit: Max events to return (default 20).
            severity: Filter by severity — Critical, Warning, Informational, Major, Minor, Debug.
            category: Filter by category — AP, Client, Cluster, Control_Plane, Data_Plane, etc.
            hours_back: Only events from last N hours (e.g. 24 = last 24h).
            text_search: Full-text search across event fields.
            page: Page number for pagination (default 1).
        """
        return await _alert_events(
            limit=limit, severity=severity, category=category,
            hours_back=hours_back, text_search=text_search, page=page,
        )
