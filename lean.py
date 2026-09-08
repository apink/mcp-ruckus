"""Curated read-only toolset for AI agents.

A lean subset of the full Ruckus tool registry (~17 of 90 tools) covering the
high-value, read-only operations agents use most: search, status, summary, and
diagnostics. Exposing only these tools to an agent drastically reduces the
``tools/list`` token/context footprint and improves tool-selection accuracy.

This list is a starting point derived from audit-log usage. Review and refine
it as real production usage data accumulates; keep it read-only (never add a
tool from ``security.DESTRUCTIVE_TOOLS``).
"""
from __future__ import annotations

LEAN_TOOLS: frozenset[str] = frozenset(
    {
        "client_search",
        "zone_ap_list",
        "zone_status",
        "ruckus_devices_by_location",
        "ap_status",
        "ruckus_device_vlan_summary",
        "ruckus_list_devices",
        "ap_detail",
        "ap_traffic_stats",
        "check_port",
        "ping_device",
        "ssid_detail",
        "ap_neighbors",
        "ap_radio_stats",
        "controller_stats",
        "domain_list",
        "ssid_list_all",
    }
)
