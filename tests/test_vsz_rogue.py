"""Tests for vsz_rogue tools."""
from __future__ import annotations

import pytest
from tools.vsz_rogue import _rogue_client_query

pytestmark = pytest.mark.asyncio


class TestRogueClientQuery:
    async def test_returns_rogue_data(self):
        result = await _rogue_client_query()
        assert isinstance(result, dict)
        assert result["total"] == 1
        assert len(result["clients"]) == 1

    async def test_rogue_fields(self):
        result = await _rogue_client_query()
        client = result["clients"][0]
        assert "rogue_mac" in client
        assert "ssid" in client
        assert "type" in client
        assert "channel" in client
        assert "detected_by" in client

    async def test_detected_by_aps(self):
        result = await _rogue_client_query()
        ap_list = result["clients"][0]["detected_by"]
        assert len(ap_list) == 2
        assert ap_list[0]["main_detector"] is True
