"""Tests for icx_device tools."""
from __future__ import annotations

from tools.icx_device import (
    _device_info,
    _device_status,
    _device_interfaces_summary,
    _device_interfaces_down,
    _device_interfaces_errors,
    _device_interfaces_stats,
    _device_ip_addresses,
    _device_ip_routes,
    _device_ipv6_routes,
    _device_vlan_summary,
    _device_port_vlan,
    _device_mac_table_vlan,
    _device_find_mac,
    _device_lag_summary,
    _device_chassis_health,
    _device_ipv6_interfaces,
    _device_ping,
    _device_ping_ipv6,
    _device_traceroute,
    _device_traceroute_ipv6,
    _device_config_backup,
    _device_config_diff,
)


class TestDeviceInfo:
    def test_valid_device(self):
        result = _device_info("10.60.172.1")
        assert result["name"] == "FTIS-SA02-SVR03"
        assert result["model"] == "ICX 7550-48ZP"

    def test_unknown_device(self):
        result = _device_info("192.168.99.99")
        assert result["error"] == "device_not_found"


class TestDeviceStatus:
    def test_returns_dict(self):
        result = _device_status("10.60.172.1")
        assert "cpu_pct" in result
        assert "memory_pct" in result
        assert "temperature_c" in result


class TestInterfacesSummary:
    def test_returns_list(self):
        result = _device_interfaces_summary("10.60.172.1")
        assert isinstance(result, list)
        assert len(result) == 3


class TestInterfacesDown:
    def test_returns_down_only(self):
        result = _device_interfaces_down("10.60.172.1")
        assert len(result) == 1
        assert result[0]["port"] == "1/1/2"


class TestInterfacesErrors:
    def test_returns_list(self):
        result = _device_interfaces_errors("10.60.172.1")
        assert isinstance(result, list)


class TestInterfacesStats:
    def test_returns_stats(self):
        result = _device_interfaces_stats("10.60.172.1")
        assert len(result) == 3
        assert "util_pct" in result[0]


class TestIpAddresses:
    def test_returns_list(self):
        result = _device_ip_addresses("10.60.172.1")
        assert len(result) == 1
        assert result[0]["ip"] == "10.60.172.1"


class TestIpRoutes:
    def test_all_routes(self):
        result = _device_ip_routes("10.60.172.1")
        assert result["total"] == 3

    def test_lookup_by_dest(self):
        result = _device_ip_routes("10.60.172.1", destination="0.0.0.0/0")
        assert result["total"] == 1

    def test_empty_route(self):
        result = _device_ip_routes("10.60.172.1", destination="8.8.8.8/32")
        assert result["total"] == 0


class TestIpv6Routes:
    def test_returns_routes(self):
        result = _device_ipv6_routes("10.60.172.1")
        assert result["total"] == 2


class TestVlanSummary:
    def test_returns_dict(self):
        result = _device_vlan_summary("10.60.172.1")
        assert result["total_vlans"] == 20
        assert len(result["vlans"]) == 3


class TestPortVlan:
    def test_returns_vlans(self):
        result = _device_port_vlan("10.60.172.1", "1/1/1")
        assert "vlans" in result
        assert len(result["vlans"]) == 2


class TestMacTableVlan:
    def test_returns_macs(self):
        result = _device_mac_table_vlan("10.60.172.1", 100)
        assert len(result) == 1
        assert result[0]["vlan"] == 100


class TestFindMac:
    def test_returns_port(self):
        result = _device_find_mac("10.60.172.1", "cc:dd:ee:11:22:01")
        assert len(result) == 1
        assert result[0]["port"] == "1/2/1"


class TestLagSummary:
    def test_returns_list(self):
        result = _device_lag_summary("10.60.172.1")
        assert len(result) == 1
        assert result[0]["status"] == "up"


class TestChassisHealth:
    def test_returns_health(self):
        result = _device_chassis_health("10.60.172.1")
        assert result["status"] == "healthy"
        assert result["power_supplies"] == 2


class TestIpv6Interfaces:
    def test_returns_interfaces(self):
        result = _device_ipv6_interfaces("10.60.172.1")
        assert len(result) == 1
        assert "2001:db8" in result[0]["ip"]


class TestDevicePing:
    def test_ping_v4(self):
        result = _device_ping("10.60.172.1", "8.8.8.8")
        assert result["success"] is True
        assert result["packets_received"] == 5

    def test_ping_v4_with_source(self):
        result = _device_ping("10.60.172.1", "8.8.8.8", source="10.60.172.1")
        assert result["success"] is True

    def test_ping_v6(self):
        result = _device_ping_ipv6("10.60.172.1", "2001:4860:4860::8888")
        assert result["success"] is True


class TestDeviceTraceroute:
    def test_traceroute_v4(self):
        result = _device_traceroute("10.60.172.1", "8.8.8.8")
        assert len(result) == 2
        assert result[0]["hop"] == 1

    def test_traceroute_v4_with_source(self):
        result = _device_traceroute("10.60.172.1", "8.8.8.8", source_ip="10.60.172.1")
        assert len(result) == 2

    def test_traceroute_v6(self):
        result = _device_traceroute_ipv6("10.60.172.1", "2001:4860:4860::8888")
        assert len(result) == 1


class TestConfigBackup:
    def test_metadata_only(self):
        result = _device_config_backup("10.60.172.1")
        assert "sha256" in result
        assert "path" in result
        assert "size_kb" in result
        assert "line_count" in result
        assert "config" not in result

    def test_include_config(self):
        result = _device_config_backup("10.60.172.1", include_config=True)
        assert "config" in result
        assert "hostname" in result["config"]

    def test_startup_config(self):
        result = _device_config_backup("10.60.172.1", config_type="startup")
        assert result["config_type"] == "startup"


class TestConfigDiff:
    def test_first_backup(self):
        result = _device_config_diff("10.60.172.1")
        assert "current_sha256" in result
        assert "changed" in result
        assert "config_type" in result
        assert "host" in result
