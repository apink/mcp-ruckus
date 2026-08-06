"""Tests for vsz_clients tools."""
from __future__ import annotations

import pytest
from tools.vsz_clients import _client_search, _client_roaming

pytestmark = pytest.mark.asyncio


class TestClientSearch:
    async def test_returns_clients(self):
        result = await _client_search("user01")
        assert isinstance(result, dict)
        assert result["total"] >= 1
        assert len(result["clients"]) >= 1

    async def test_client_fields(self):
        result = await _client_search("user01")
        client = result["clients"][0]
        assert "hostname" in client
        assert "mac" in client
        assert "ssid" in client
        assert "ap_name" in client
        assert "rssi" in client

    async def test_no_traffic_by_default(self):
        result = await _client_search("user01")
        client = result["clients"][0]
        assert "tx_mbytes" not in client

    async def test_include_traffic(self):
        result = await _client_search("user01", include_traffic=True)
        client = result["clients"][0]
        assert "tx_mbytes" in client
        assert "rx_mbytes" in client
        assert "median_tx_mcs" in client

    async def test_limit(self):
        result = await _client_search("user01", limit=1)
        assert len(result["clients"]) == 1

    async def test_empty_query(self):
        result = await _client_search("nonexistent_user_xyz")
        assert result["total"] == 0
        assert result["clients"] == []


class TestClientRoaming:
    async def test_returns_roaming_data(self):
        result = await _client_roaming("user01")
        assert isinstance(result, dict)
        assert "devices" in result

    async def test_has_roaming_timeline(self):
        result = await _client_roaming("user01")
        if result["devices"]:
            device = result["devices"][0]
            assert "mac" in device
            assert "roaming_timeline" in device
            assert "events" in device
