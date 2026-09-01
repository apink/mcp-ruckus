"""vSZ domain tools."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter
from tools._response import list_result

logger = logging.getLogger(__name__)


async def _domain_list() -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    domains = await adapter._request("/domains")
    if isinstance(domains, dict) and "error" in domains:
        return {"error": domains["error"], "detail": domains.get("detail", "")}
    if not isinstance(domains, list):
        domains_list = domains.get("list", []) if isinstance(domains, dict) else []
    else:
        domains_list = domains
    return list_result([
        {"id": d.get("id", ""), "name": d.get("name", ""),
         "description": d.get("description", ""), "status": d.get("status", "")}
        for d in domains_list
    ])


def register_tools(mcp: FastMCP) -> None:
    """Register vSZ domain tools."""
    @mcp.tool()
    async def domain_list() -> dict[str, Any]:
        """List all administration domains visible to the current user."""
        return await _domain_list()
