"""vSZ alarm tools — active alarms, acknowledge, clear."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)


async def _alarm_list(
    limit: int = 50,
    severity: str | None = None,
    hours_back: int | None = 24,
    text_search: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.get_alert_events(
        limit=limit, severity=severity, hours_back=hours_back,
        text_search=text_search, page=page,
    )
    return {
        "total": data.get("totalCount", 0),
        "has_more": data.get("hasMore", False),
        "page": page,
        "limit": limit,
        "alarms": [
            {
                "id": e.get("id", ""),
                "time_ms": e.get("insertionTime", 0),
                "type": e.get("eventType", ""),
                "code": e.get("eventCode", 0),
                "severity": e.get("severity", ""),
                "category": e.get("category", ""),
                "activity": e.get("activity", ""),
            }
            for e in data.get("list", [])
        ],
    }


def register_tools(mcp: FastMCP) -> None:
    """Register vSZ alarm tools."""
    @mcp.tool()
    async def alarm_list(
        limit: int = 50,
        severity: str | None = None,
        hours_back: int | None = 24,
        text_search: str | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """List alarms from vSZ with optional filters.

        Defaults to last 24 hours. Use severity filter for Critical/Warning.
        Use text_search for specific device names or event text.

        Args:
            limit: Max alarms to return (default 50).
            severity: Filter by severity — Critical, Warning, Major, Minor.
            hours_back: Only alarms from last N hours (default 24, None for all time).
            text_search: Full-text search across alarm fields.
            page: Page number for pagination.
        """
        return await _alarm_list(
            limit=limit, severity=severity, hours_back=hours_back,
            text_search=text_search, page=page,
        )
