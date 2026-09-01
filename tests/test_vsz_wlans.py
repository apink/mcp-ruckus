"""Tests for vsz_wlans tools."""
from __future__ import annotations

import pytest

from tools.vsz_wlans import _create_wlan, _radius_list, _ssid_detail, _ssid_list, _ssid_list_all

pytestmark = pytest.mark.asyncio


class TestSsidList:
    async def test_known_zone(self):
        result = await _ssid_list("zone-001")
        assert isinstance(result, dict)
        assert len(result["items"]) == 3

    async def test_has_required_fields(self):
        result = await _ssid_list("zone-001")
        wlan = result["items"][0]
        assert "ssid" in wlan
        assert "name" in wlan
        assert "id" in wlan
        assert "zone_id" in wlan


class TestSsidListAll:
    async def test_returns_list(self):
        result = await _ssid_list_all()
        assert isinstance(result, dict)
        assert len(result["items"]) == 3

    async def test_has_zone_info(self):
        result = await _ssid_list_all()
        for w in result["items"]:
            assert "zone" in w


class TestSsidDetail:
    async def test_known_wlan(self):
        result = await _ssid_detail("wlan-001", "zone-001")
        assert isinstance(result, dict)
        assert result["ssid"] == "Secure"
        assert "encryption_method" in result
        assert "vlan_id" in result


class TestRadiusList:
    async def test_auth_only(self):
        result = await _radius_list("zone-001", for_accounting="auth_only")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "RADIUS"

    async def test_all(self):
        result = await _radius_list("zone-001")
        assert isinstance(result, list)
        assert len(result) >= 1


class TestCreateWlan:
    async def test_safety_latch(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s")
        assert "error" in result
        assert result["error"] == "safety_latch"

    async def test_missing_zone(self):
        result = await _create_wlan(zone_id="", name="n", ssid="s", confirm=True)
        assert result["error"] == "missing_zone_id"

    async def test_long_name(self):
        result = await _create_wlan(zone_id="z", name="x" * 33, ssid="s", confirm=True)
        assert result["error"] == "invalid_name"

    async def test_long_ssid(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="x" * 33, confirm=True)
        assert result["error"] == "invalid_ssid"

    async def test_invalid_vlan(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", access_vlan=5000, confirm=True)
        assert result["error"] == "invalid_vlan"

    async def test_invalid_max_clients(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", max_clients=0, confirm=True)
        assert result["error"] == "invalid_max_clients"

    async def test_invalid_encryption(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", encryption="WEP", confirm=True)
        assert result["error"] == "invalid_encryption"

    async def test_psk_no_passphrase(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", auth_type="PSK", confirm=True)
        assert result["error"] == "invalid_passphrase"

    async def test_8021x_no_radius(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", auth_type="8021X", confirm=True)
        assert result["error"] == "missing_radius"

    async def test_successful_create(self):
        result = await _create_wlan(
            zone_id="zone-001", name="Test-WLAN", ssid="Test-SSID",
            encryption="WPA2", passphrase="testpass123", confirm=True,
        )
        assert result["status"] == "created"
        assert result["name"] == "Test-WLAN"

    async def test_invalid_auth_type(self):
        result = await _create_wlan(zone_id="z", name="n", ssid="s", auth_type="INVALID", confirm=True)
        assert result["error"] == "invalid_auth_type"
