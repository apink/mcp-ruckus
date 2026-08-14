"""Tests for vSZ traffic stats tools."""
from __future__ import annotations

import pytest

from tools.vsz_traffic import (
    _ap_traffic_stats,
    _build_zone_map,
    _wlan_traffic_stats,
    _zone_traffic_stats,
)


class TestBuildZoneMap:
    def test_builds_map(self):
        zones = [{"id": "zone-001", "name": "Campus"}, {"id": "zone-002", "name": "Lab"}]
        assert _build_zone_map(zones) == {"zone-001": "Campus", "zone-002": "Lab"}

    def test_missing_name_falls_back_to_id(self):
        zones = [{"id": "zone-001"}]
        assert _build_zone_map(zones) == {"zone-001": "zone-001"}


class TestWlanTrafficStats:
    pytestmark = pytest.mark.asyncio

    async def test_aggregates_wlans(self):
        result = await _wlan_traffic_stats()
        assert result["total_wlans"] == 2
        ssids = {w["ssid"] for w in result["wlans"]}
        assert ssids == {"Secure", "Guest"}

    async def test_client_counts(self):
        result = await _wlan_traffic_stats()
        by_ssid = {w["ssid"]: w for w in result["wlans"]}
        assert by_ssid["Secure"]["total_clients"] == 2
        assert by_ssid["Guest"]["total_clients"] == 1

    async def test_ssid_filter(self):
        result = await _wlan_traffic_stats(ssid="Secure")
        assert result["total_wlans"] == 1
        assert result["wlans"][0]["ssid"] == "Secure"


class TestApTrafficStats:
    pytestmark = pytest.mark.asyncio

    async def test_aggregates_aps(self):
        result = await _ap_traffic_stats()
        assert result["total_aps"] == 3

    async def test_ap_fields(self):
        result = await _ap_traffic_stats()
        ap = result["aps"][0]
        assert "ap_name" in ap
        assert "ap_mac" in ap
        assert "total_clients" in ap
        assert "total_rx_mb" in ap

    async def test_ap_name_filter(self):
        result = await _ap_traffic_stats(ap_name="AP-01-01")
        assert result["total_aps"] == 1
        assert result["aps"][0]["ap_name"] == "AP-01-01"


class TestZoneTrafficStats:
    pytestmark = pytest.mark.asyncio

    async def test_returns_zones(self):
        result = await _zone_traffic_stats()
        assert result["total_zones"] == 1
        zone = result["zones"][0]
        assert "total_clients" in zone
        assert "active_wlans" in zone
        assert zone["total_clients"] == 3
