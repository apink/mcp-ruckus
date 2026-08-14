"""Tests for vSZ RF optimization tools."""
from __future__ import annotations

import pytest

from tools.vsz_rf import (
    _apply_ap_config,
    _apply_rf_recommendation,
    _apply_to_aps,
    _build_radio_payload,
    _extract_floor,
    _optimize_wifi_rf,
    _parse_ch,
    _resolve_power,
)


class TestParseCh:
    def test_valid(self):
        assert _parse_ch("6 (20MHz)") == (6, 20)
        assert _parse_ch("149 (80MHz)") == (149, 80)

    def test_empty(self):
        assert _parse_ch("") == (None, None)
        assert _parse_ch(None) == (None, None)

    def test_malformed(self):
        assert _parse_ch("n/a") == (None, None)


class TestExtractFloor:
    def test_ap_pattern(self):
        assert _extract_floor("AP01") == "01"

    def test_case_insensitive(self):
        assert _extract_floor("ap3") == "3"

    def test_no_floor(self):
        assert _extract_floor("switch-core") is None


class TestResolvePower:
    def test_labels(self):
        assert _resolve_power("max") == "Full"
        assert _resolve_power("half") == "-6dB(1/4)"
        assert _resolve_power("min") == "Min"

    def test_passthrough(self):
        assert _resolve_power("Full") == "Full"


class TestBuildRadioPayload:
    def test_5g_with_secondary(self):
        payload = _build_radio_payload("5g", 36, 80, power="max", secondary=40)
        radio = payload["radioConfig"]["radio5g"]
        assert radio["channel"] == 36
        assert radio["channelWidth"] == 80
        assert radio["txPower"] == "Full"
        assert radio["secondaryChannel"] == 40

    def test_24g_default_width(self):
        payload = _build_radio_payload("2.4g", 6, 0)
        radio = payload["radioConfig"]["radio24g"]
        assert radio["channelWidth"] == 20
        assert "txPower" not in radio


class TestApplyToAps:
    pytestmark = pytest.mark.asyncio

    async def test_applied(self):
        class FakeAdapter:
            async def modify_ap(self, mac, payload):
                return {"status": "applied"}

        results = await _apply_to_aps(FakeAdapter(), [("AP1", "aa:bb:cc:11:22:01", {})])
        assert results[0]["status"] == "applied"

    async def test_missing_mac_skipped(self):
        class FakeAdapter:
            async def modify_ap(self, mac, payload):
                return {"status": "applied"}

        results = await _apply_to_aps(FakeAdapter(), [("AP1", "", {})])
        assert results[0]["status"] == "skipped"

    async def test_error_propagated(self):
        class FakeAdapter:
            async def modify_ap(self, mac, payload):
                return {"error": "boom"}

        results = await _apply_to_aps(FakeAdapter(), [("AP1", "aa:bb:cc:11:22:01", {})])
        assert results[0]["status"] == "failed"


class TestOptimizeWifiRf:
    pytestmark = pytest.mark.asyncio

    async def test_invalid_band(self):
        result = await _optimize_wifi_rf(band="6g")
        assert result["error"] == "invalid_band"

    async def test_no_aps_matched(self):
        result = await _optimize_wifi_rf(ap_names="nonexistent_ap")
        assert result["error"] == "no_aps_found"

    async def test_full_zone_flow(self):
        result = await _optimize_wifi_rf(zone_id="zone-001", band="5g", channel_width=80)
        assert isinstance(result, dict)
        assert "optimization_id" in result
        assert result["mode"] == "dry_run"


class TestApplyRfRecommendation:
    pytestmark = pytest.mark.asyncio

    async def test_safety_latch(self):
        result = await _apply_rf_recommendation("opt_x", confirm=False)
        assert result["error"] == "safety_latch"

    async def test_not_found(self):
        result = await _apply_rf_recommendation("opt_missing", confirm=True)
        assert result["error"] == "optimization_expired_or_not_found"


class TestApplyApConfig:
    pytestmark = pytest.mark.asyncio

    async def test_safety_latch(self):
        result = await _apply_ap_config(zone_id="zone-001", confirm=False)
        assert result["error"] == "safety_latch"

    async def test_missing_channel(self):
        result = await _apply_ap_config(zone_id="zone-001", confirm=True)
        assert result["error"] == "missing_channel"

    async def test_invalid_band(self):
        result = await _apply_ap_config(zone_id="zone-001", channel=36, band="6g", confirm=True)
        assert result["error"] == "invalid_band"

    async def test_no_target(self):
        result = await _apply_ap_config(channel=36, confirm=True)
        assert result["error"] == "no_target"

    async def test_apply_by_zone(self):
        result = await _apply_ap_config(
            zone_id="zone-001", band="5g", channel=36, channel_width=40, power="max", confirm=True
        )
        assert result["applied"] == 5
        assert result["failed"] == 0
        assert result["channel"] == 36
