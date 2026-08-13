"""Tests for inventory tools."""
from __future__ import annotations

from tools.inventory import list_devices, all_device_info, all_device_status, devices_by_location, devices_by_role


class TestListDevices:
    def test_returns_devices(self):
        result = list_devices()
        assert len(result) == 2
        assert result[0]["host"] == "203.0.113.1"

    def test_device_fields(self):
        result = list_devices()
        dev = result[0]
        assert "host" in dev
        assert "name" in dev
        assert "vendor" in dev
        assert "role" in dev


class TestAllDeviceInfo:
    def test_returns_all(self):
        result = all_device_info()
        assert len(result) == 2
        assert result[0]["host"] == "203.0.113.1"


class TestAllDeviceStatus:
    def test_returns_all(self):
        result = all_device_status()
        assert len(result) == 2


class TestDevicesByLocation:
    def test_matching_location(self):
        result = devices_by_location("building a south")
        assert len(result) == 2

    def test_no_match(self):
        result = devices_by_location("unknown")
        assert len(result) == 0


class TestDevicesByRole:
    def test_distribution(self):
        result = devices_by_role("distribution")
        assert len(result) == 1
        assert result[0]["host"] == "203.0.113.1"

    def test_access(self):
        result = devices_by_role("access")
        assert len(result) == 1
        assert result[0]["host"] == "203.0.113.3"
