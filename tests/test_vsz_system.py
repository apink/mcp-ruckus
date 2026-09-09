"""Tests for vsz_system tools."""
from __future__ import annotations

import pytest

from tools.vsz_system import (
    _controller_statistics,
    _license_status,
    _zone_ap_list,
    _zone_status,
)

pytestmark = pytest.mark.asyncio


class TestZoneStatus:
    async def test_returns_list(self):
        result = await _zone_status()
        assert isinstance(result, dict)
        assert len(result["items"]) == 2

    async def test_has_required_fields(self):
        result = await _zone_status()
        zone = result["items"][0]
        assert "zone_id" in zone
        assert "name" in zone
        assert "ap_count" in zone
        assert "client_count" in zone

    async def test_zone_names_match(self):
        result = await _zone_status()
        names = {z["name"] for z in result["items"]}
        assert "Campus" in names
        assert "Lab" in names


class TestZoneApList:
    async def test_returns_list_for_valid_zone(self):
        result = await _zone_ap_list("zone-001")
        assert isinstance(result, dict)
        assert len(result["items"]) == 5

    async def test_empty_for_unknown_zone(self):
        result = await _zone_ap_list("zone-unknown")
        assert isinstance(result, dict)
        assert len(result["items"]) == 0

    async def test_has_required_fields(self):
        result = await _zone_ap_list("zone-001")
        ap = result["items"][0]
        assert "ap_name" in ap
        assert "status" in ap
        assert "clients" in ap


class TestLicenseStatus:
    async def test_returns_dict(self):
        result = await _license_status()
        assert isinstance(result, dict)
        assert "total_license" in result
        assert result["total_license"] == 100


class TestControllerStatistics:
    async def test_returns_envelope(self):
        result = await _controller_statistics()
        assert isinstance(result, dict)
        assert "items" in result
        assert "total" in result
        assert "controller_id" in result
        assert "interval" in result
        assert result["interval"] == "QUARTER"

    async def test_has_stat_fields(self):
        result = await _controller_statistics()
        sample = result["items"][0]
        assert "cpu" in sample
        assert "memory" in sample
        assert "disk" in sample
        assert "management" in sample

    async def test_size_caps_samples(self):
        result = await _controller_statistics(size=2)
        assert len(result["items"]) == 2

    async def test_passes_controller_id(self):
        result = await _controller_statistics(
            controller_id="f214c803-c88f-40f8-83d5-a6e37a9840de")
        assert result["controller_id"] == "f214c803-c88f-40f8-83d5-a6e37a9840de"
