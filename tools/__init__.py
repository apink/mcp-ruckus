"""Ruckus MCP tools — aggregated registration.

Each sub-module exposes a register_tools(mcp) function that is called
by register_all_tools() to register every tool on the FastMCP server instance.
"""
from fastmcp import FastMCP

from tools import (
    connectivity,
    inventory,
    vsz_alarms,
    vsz_aps,
    vsz_clients,
    vsz_domains,
    vsz_events,
    vsz_rf,
    vsz_rogue,
    vsz_system,
    vsz_traffic,
    vsz_wlans,
)
from tools import icx_device

_MODULES = [
    vsz_system,
    vsz_aps,
    vsz_wlans,
    vsz_clients,
    vsz_events,
    vsz_rogue,
    vsz_alarms,
    vsz_domains,
    vsz_traffic,
    vsz_rf,
    icx_device,
    inventory,
    connectivity,
]


def register_all_tools(mcp: FastMCP) -> None:
    """Register every Ruckus tool on the MCP server."""
    for module in _MODULES:
        module.register_tools(mcp)
