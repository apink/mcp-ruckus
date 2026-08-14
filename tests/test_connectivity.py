"""Tests for connectivity tools (async)."""
from __future__ import annotations

import pytest

from tools.connectivity import check_port, http_latency, ping_device


class TestPingDevice:
    @pytest.mark.asyncio
    async def test_localhost(self):
        result = await ping_device("127.0.0.1", count=1)
        assert "host" in result
        assert isinstance(result["reachable"], bool)

    @pytest.mark.asyncio
    async def test_unreachable(self):
        result = await ping_device("192.0.2.1", count=1)
        assert result["reachable"] is False


class TestCheckPort:
    @pytest.mark.asyncio
    async def test_closed_port(self):
        result = await check_port("127.0.0.1", 19999, timeout=1)
        assert result["status"] in ("closed", "timeout")


class TestHttpLatency:
    @pytest.mark.asyncio
    async def test_bad_url(self):
        result = await http_latency("http://127.0.0.1:19999", timeout=1)
        assert "error" in result
