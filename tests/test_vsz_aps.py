"""Tests for vsz_aps tools."""
from __future__ import annotations

import pytest
from tools.vsz_aps import _ap_status, _ap_detail, _ap_down, _ap_high_client_count, _ap_neighbors, _ap_radio_stats

pytestmark = pytest.mark.asyncio


class TestApStatus:
    async def test_all_aps(self):
        result = await _ap_status()
        assert isinstance(result, list)
        assert len(result) == 5

    async def test_has_required_fields(self):
        result = await _ap_status()
        ap = result[0]
        assert "ap_name" in ap
        assert "mac" in ap
        assert "model" in ap
        assert "status" in ap
        assert "clients" in ap
        assert "zone" in ap
        assert "ip" in ap

    async def test_online_aps_have_status_up(self):
        result = await _ap_status()
        for ap in result:
            if ap["ap_name"] != "FTIS-AP03-04":
                assert ap["status"] == "up"

    async def test_disconnected_ap_has_raw_status(self):
        result = await _ap_status()
        dc = [ap for ap in result if ap["ap_name"] == "FTIS-AP03-04"]
        assert len(dc) == 1
        assert dc[0]["status"] != "up"

    async def test_zone_filter(self):
        result = await _ap_status(zone_id="FTI-Campus")
        assert len(result) == 5

    async def test_limit(self):
        result = await _ap_status(limit=2)
        assert len(result) == 2


class TestApDetail:
    async def test_known_ap(self):
        result = await _ap_detail("FTIS-AP01-01")
        assert isinstance(result, dict)
        assert result["ap_name"] == "FTIS-AP01-01"
        assert result["model"] == "R750"

    async def test_unknown_ap(self):
        result = await _ap_detail("NONEXISTENT")
        assert "error" in result
        assert result["error"] == "ap_not_found"


class TestApDown:
    async def test_returns_list(self):
        result = await _ap_down()
        assert isinstance(result, list)
        assert len(result) == 1

    async def test_disconnected_ap_found(self):
        result = await _ap_down()
        assert result[0]["ap_name"] == "FTIS-AP03-04"


class TestApHighClientCount:
    async def test_default_threshold(self):
        result = await _ap_high_client_count()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["ap_name"] == "FTIS-AP03-05"

    async def test_low_threshold(self):
        result = await _ap_high_client_count(threshold=20)
        assert len(result) >= 2

    async def test_high_threshold(self):
        result = await _ap_high_client_count(threshold=100)
        assert len(result) == 0


class TestApNeighbors:
    async def test_single_ap(self):
        result = await _ap_neighbors(ap_name="FTIS-AP01-01")
        assert "error" not in result
        assert result["ap"] == "FTIS-AP01-01"
        assert result["total_neighbors"] == 2
        assert "neighbors" in result

    async def test_unknown_ap(self):
        result = await _ap_neighbors(ap_name="UNKNOWN")
        assert "error" in result
        assert result["error"] == "ap_not_found"

    async def test_all_scope(self):
        result = await _ap_neighbors()
        assert "error" not in result
        assert result["scope"] == "all"
        assert "aps" in result

    async def test_summary_mode(self):
        result = await _ap_neighbors(include_detail=False)
        assert "aps" in result
        if result["aps"]:
            entry = result["aps"][0]
            assert "neighbors" in entry
            assert isinstance(entry["neighbors"], int)


class TestApRadioStats:
    async def test_known_ap(self):
        result = await _ap_radio_stats("FTIS-AP01-01")
        assert isinstance(result, dict)
        assert "radios" in result
        assert len(result["radios"]) == 2

    async def test_radio_bands(self):
        result = await _ap_radio_stats("FTIS-AP01-01")
        bands = {r["band"] for r in result["radios"]}
        assert "2.4GHz" in bands
        assert "5GHz" in bands

    async def test_unknown_ap(self):
        result = await _ap_radio_stats("UNKNOWN")
        assert "error" in result
