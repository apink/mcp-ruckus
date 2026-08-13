"""Tests for vsz_system tools."""
from __future__ import annotations

import pytest
from tools.vsz_system import _zone_status, _zone_ap_list, _license_status

pytestmark = pytest.mark.asyncio


class TestZoneStatus:
    async def test_returns_list(self):
        result = await _zone_status()
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_has_required_fields(self):
        result = await _zone_status()
        zone = result[0]
        assert "zone_id" in zone
        assert "name" in zone
        assert "ap_count" in zone
        assert "client_count" in zone

    async def test_zone_names_match(self):
        result = await _zone_status()
        names = {z["name"] for z in result}
        assert "Campus" in names
        assert "Lab" in names


class TestZoneApList:
    async def test_returns_list_for_valid_zone(self):
        result = await _zone_ap_list("zone-001")
        assert isinstance(result, list)
        assert len(result) == 5

    async def test_empty_for_unknown_zone(self):
        result = await _zone_ap_list("zone-unknown")
        assert isinstance(result, list)
        assert len(result) == 0

    async def test_has_required_fields(self):
        result = await _zone_ap_list("zone-001")
        ap = result[0]
        assert "ap_name" in ap
        assert "status" in ap
        assert "clients" in ap


class TestLicenseStatus:
    async def test_returns_dict(self):
        result = await _license_status()
        assert isinstance(result, dict)
        assert "total_license" in result
        assert result["total_license"] == 100
