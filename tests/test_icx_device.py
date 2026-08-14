"""Tests for icx_device tools."""
from __future__ import annotations

from tools.icx_device import (
    _device_access_lists,
    _device_arp_table,
    _device_cable_diag,
    _device_chassis_health,
    _device_config_backup,
    _device_config_diff,
    _device_find_mac,
    _device_info,
    _device_interfaces_down,
    _device_interfaces_errors,
    _device_interfaces_stats,
    _device_interfaces_summary,
    _device_ip_addresses,
    _device_ip_routes,
    _device_ipv6_interfaces,
    _device_ipv6_routes,
    _device_lag_summary,
    _device_lldp_neighbors,
    _device_mac_table_vlan,
    _device_optic_info,
    _device_ping,
    _device_ping_ipv6,
    _device_poe_port,
    _device_poe_status,
    _device_port_state,
    _device_port_vlan,
    _device_resources,
    _device_sfp_info,
    _device_spanning_tree,
    _device_ssh_status,
    _device_status,
    _device_syslog,
    _device_time,
    _device_traceroute,
    _device_traceroute_ipv6,
    _device_users,
    _device_vlan_create,
    _device_vlan_delete,
    _device_vlan_port,
    _device_vlan_summary,
)


class TestDeviceInfo:
    def test_valid_device(self):
        result = _device_info("203.0.113.1")
        assert result["name"] == "SW-DIST-01"
        assert result["model"] == "ICX 7550-48ZP"

    def test_unknown_device(self):
        result = _device_info("192.168.99.99")
        assert result["error"] == "device_not_found"


class TestDeviceStatus:
    def test_returns_dict(self):
        result = _device_status("203.0.113.1")
        assert "cpu_pct" in result
        assert "memory_pct" in result
        assert "temperature_c" in result


class TestInterfacesSummary:
    def test_returns_list(self):
        result = _device_interfaces_summary("203.0.113.1")
        assert isinstance(result, list)
        assert len(result) == 3


class TestInterfacesDown:
    def test_returns_down_only(self):
        result = _device_interfaces_down("203.0.113.1")
        assert len(result) == 1
        assert result[0]["port"] == "1/1/2"


class TestInterfacesErrors:
    def test_returns_list(self):
        result = _device_interfaces_errors("203.0.113.1")
        assert isinstance(result, list)


class TestInterfacesStats:
    def test_returns_stats(self):
        result = _device_interfaces_stats("203.0.113.1")
        assert len(result) == 3
        assert "util_pct" in result[0]


class TestIpAddresses:
    def test_returns_list(self):
        result = _device_ip_addresses("203.0.113.1")
        assert len(result) == 1
        assert result[0]["ip"] == "203.0.113.1"


class TestIpRoutes:
    def test_all_routes(self):
        result = _device_ip_routes("203.0.113.1")
        assert result["total"] == 3

    def test_lookup_by_dest(self):
        result = _device_ip_routes("203.0.113.1", destination="0.0.0.0/0")
        assert result["total"] == 1

    def test_empty_route(self):
        result = _device_ip_routes("203.0.113.1", destination="8.8.8.8/32")
        assert result["total"] == 0


class TestIpv6Routes:
    def test_returns_routes(self):
        result = _device_ipv6_routes("203.0.113.1")
        assert result["total"] == 2


class TestVlanSummary:
    def test_returns_dict(self):
        result = _device_vlan_summary("203.0.113.1")
        assert result["total_vlans"] == 20
        assert len(result["vlans"]) == 3


class TestPortVlan:
    def test_returns_vlans(self):
        result = _device_port_vlan("203.0.113.1", "1/1/1")
        assert "vlans" in result
        assert len(result["vlans"]) == 2


class TestMacTableVlan:
    def test_returns_macs(self):
        result = _device_mac_table_vlan("203.0.113.1", 100)
        assert len(result) == 1
        assert result[0]["vlan"] == 100


class TestFindMac:
    def test_returns_port(self):
        result = _device_find_mac("203.0.113.1", "cc:dd:ee:11:22:01")
        assert len(result) == 1
        assert result[0]["port"] == "1/2/1"


class TestLagSummary:
    def test_returns_list(self):
        result = _device_lag_summary("203.0.113.1")
        assert len(result) == 1
        assert result[0]["status"] == "up"


class TestChassisHealth:
    def test_returns_health(self):
        result = _device_chassis_health("203.0.113.1")
        assert result["status"] == "healthy"
        assert result["power_supplies"] == 2


class TestIpv6Interfaces:
    def test_returns_interfaces(self):
        result = _device_ipv6_interfaces("203.0.113.1")
        assert len(result) == 1
        assert "2001:db8" in result[0]["ip"]


class TestDevicePing:
    def test_ping_v4(self):
        result = _device_ping("203.0.113.1", "8.8.8.8")
        assert result["success"] is True
        assert result["packets_received"] == 5

    def test_ping_v4_with_source(self):
        result = _device_ping("203.0.113.1", "8.8.8.8", source="203.0.113.1")
        assert result["success"] is True

    def test_ping_v6(self):
        result = _device_ping_ipv6("203.0.113.1", "2001:4860:4860::8888")
        assert result["success"] is True


class TestDeviceTraceroute:
    def test_traceroute_v4(self):
        result = _device_traceroute("203.0.113.1", "8.8.8.8")
        assert len(result) == 2
        assert result[0]["hop"] == 1

    def test_traceroute_v4_with_source(self):
        result = _device_traceroute("203.0.113.1", "8.8.8.8", source_ip="203.0.113.1")
        assert len(result) == 2

    def test_traceroute_v6(self):
        result = _device_traceroute_ipv6("203.0.113.1", "2001:4860:4860::8888")
        assert len(result) == 1


class TestConfigBackup:
    def test_metadata_only(self):
        result = _device_config_backup("203.0.113.1")
        assert "sha256" in result
        assert "path" in result
        assert "size_kb" in result
        assert "line_count" in result
        assert "config" not in result

    def test_include_config(self):
        result = _device_config_backup("203.0.113.1", include_config=True)
        assert "config" in result
        assert "hostname" in result["config"]

    def test_startup_config(self):
        result = _device_config_backup("203.0.113.1", config_type="startup")
        assert result["config_type"] == "startup"


class TestConfigDiff:
    def test_first_backup(self):
        result = _device_config_diff("203.0.113.1")
        assert "current_sha256" in result


class TestLLdpNeighbors:
    def test_unknown_device(self):
        result = _device_lldp_neighbors("192.168.99.99")
        assert result[0]["error"] == "device_not_found"

    def test_returns_list(self):
        result = _device_lldp_neighbors("203.0.113.1")
        assert isinstance(result, list)
        if result and "error" not in result[0]:
            assert "local_port" in result[0]
            assert "system_name" in result[0]


class TestPoeStatus:
    def test_unknown_device(self):
        result = _device_poe_status("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_all_ports(self):
        result = _device_poe_status("203.0.113.1")
        assert result["power_capacity_total_mw"] == 740000
        assert len(result["ports"]) == 1

    def test_single_port(self):
        result = _device_poe_status("203.0.113.1", port="1/1/1")
        assert result["port"] == "1/1/1"
        assert result["status"]["admin_state"] == "On"
        assert result["status"]["priority"] == 3

    def test_unknown_port(self):
        result = _device_poe_status("203.0.113.1", port="9/9/9")
        assert result["port"] == "9/9/9"
        assert result["status"] is None


class TestArpTable:
    def test_unknown_device(self):
        result = _device_arp_table("192.168.99.99")
        assert result[0]["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_arp_table("203.0.113.1")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["ip"] == "203.0.113.81"


class TestDeviceResources:
    def test_unknown_device(self):
        result = _device_resources("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_resources("203.0.113.1")
        assert "cpus" in result
        assert "memory_used_pct" in result
        assert len(result["cpus"]) == 1
        assert result["cpus"][0]["cpu_id"] == 0


class TestSfpInfo:
    def test_unknown_device(self):
        result = _device_sfp_info("192.168.99.99")
        assert result[0]["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_sfp_info("203.0.113.1")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["port"] == "1/2/1"


class TestCableDiag:
    def test_unknown_device(self):
        result = _device_cable_diag("192.168.99.99", "1/1/1")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_cable_diag("203.0.113.1", "1/1/1")
        assert result["host"] == "203.0.113.1"
        assert len(result["pairs"]) == 4
        assert result["pairs"][0]["pair_status"] == "terminated"


class TestSyslog:
    def test_unknown_device(self):
        result = _device_syslog("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_syslog("203.0.113.1")
        assert result["host"] == "203.0.113.1"
        assert len(result["entries"]) == 2
        assert result["entries"][0]["severity"] == "I"
        assert result["total"] == 2

    def test_severity_filter(self):
        result = _device_syslog("203.0.113.1", severity="E")
        assert result["severity_filter"] == "E"


class TestOpticInfo:
    def test_unknown_device(self):
        result = _device_optic_info("192.168.99.99", "1/2/1")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_optic_info("203.0.113.1", "1/2/1")
        assert result["temperature"] == 35.4
        assert result["tx_power"] == 0.68
        assert result["rx_power_unit"] == "dBm"
        assert "thresholds" in result
        assert result["thresholds"]["temperature"]["high_alarm"] == 95.0


class TestDeviceTime:
    def test_unknown_device(self):
        result = _device_time("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_time("203.0.113.1")
        assert result["host"] == "203.0.113.1"
        assert "current_time" in result
        assert result["ntp_synced"] is False
        assert len(result["ntp_peers"]) == 2


class TestSpanningTree:
    def test_unknown_device(self):
        result = _device_spanning_tree("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_spanning_tree("203.0.113.1")
        assert result["stp_configured"] is True
        assert result["vlan"] == 1
        assert result["root_cost"] == 0
        assert len(result["ports"]) == 2
        assert result["ports"][0]["state"] == "FORWARDING"


class TestAccessLists:
    def test_unknown_device(self):
        result = _device_access_lists("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_all_acls(self):
        result = _device_access_lists("203.0.113.1")
        assert result["host"] == "203.0.113.1"
        assert len(result["acls"]) == 2
        assert result["acls"][0]["name"] == "ADMINSSH"
        assert result["acls"][0]["type"] == "Standard"
        assert len(result["acls"][0]["rules"]) == 2

    def test_brief(self):
        result = _device_access_lists("203.0.113.1", brief=True)
        assert len(result["acls"]) == 2
        assert result["acls"][1]["entries"] == 5
        assert "rules" not in result["acls"][0]


class TestUsers:
    def test_unknown_device(self):
        result = _device_users("192.168.99.99")
        assert result[0]["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_users("203.0.113.1")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["username"] == "admin"
        assert result[0]["status"] == "enabled"
        assert "password" not in result[0]

    def test_password_hash_not_exposed(self):
        result = _device_users("203.0.113.1")
        assert all("password" not in u for u in result)
        assert all("$1$" not in str(u) for u in result)


class TestSshStatus:
    def test_unknown_device(self):
        result = _device_ssh_status("192.168.99.99")
        assert result["error"] == "device_not_found"

    def test_valid_device(self):
        result = _device_ssh_status("203.0.113.1")
        assert result["ssh_enabled"] is True
        assert result["ssh_version"] == "v2.0"
        assert result["host_key"] == "RSA(2048)"
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["username"] == "admin"


class TestPortState:
    def test_unknown_device(self):
        result = _device_port_state("192.168.99.99", "1/1/24", enable=True)
        assert result["error"] == "device_not_found"

    def test_enable_port(self):
        result = _device_port_state("203.0.113.1", "1/1/24", enable=True)
        assert result["port"] == "1/1/24"
        assert result["state"] == "enabled"

    def test_disable_port(self):
        result = _device_port_state("203.0.113.1", "1/1/24", enable=False)
        assert result["port"] == "1/1/24"
        assert result["state"] == "disabled"


class TestVlanCreate:
    def test_unknown_device(self):
        r = _device_vlan_create("192.168.99.99", "200")
        assert r["error"] == "device_not_found"

    def test_single_vlan(self):
        r = _device_vlan_create("203.0.113.1", "200", name="TEST_VLAN")
        assert r["vlan_spec"] == "200"
        assert r["vlan_ids"] == [200]
        assert r["created"] is True

    def test_vlan_range(self):
        r = _device_vlan_create("203.0.113.1", "210 to 213")
        assert r["vlan_ids"] == [210, 211, 212, 213]

    def test_vlan_multi(self):
        r = _device_vlan_create("203.0.113.1", "200 210 220")
        assert r["vlan_ids"] == [200, 210, 220]

    def test_vlan_mixed(self):
        r = _device_vlan_create("203.0.113.1", "16 17 20 to 24")
        assert r["vlan_ids"] == [16, 17, 20, 21, 22, 23, 24]


class TestVlanDelete:
    def test_unknown_device(self):
        r = _device_vlan_delete("192.168.99.99", "200")
        assert r["error"] == "device_not_found"

    def test_delete_single(self):
        r = _device_vlan_delete("203.0.113.1", "200")
        assert r["deleted"] is True
        assert r["vlan_ids"] == [200]

    def test_delete_range(self):
        r = _device_vlan_delete("203.0.113.1", "200 to 205")
        assert r["vlan_ids"] == [200, 201, 202, 203, 204, 205]


class TestVlanPort:
    def test_unknown_device(self):
        r = _device_vlan_port("192.168.99.99", "1/1/1", "200", "add")
        assert r["error"] == "device_not_found"

    def test_add_tagged(self):
        r = _device_vlan_port("203.0.113.1", "1/1/1", "200", "add", tagged=True)
        assert r["success"] is True
        assert r["action"] == "add"

    def test_remove(self):
        r = _device_vlan_port("203.0.113.1", "1/1/1", "200", "remove")
        assert r["success"] is True
        assert r["action"] == "remove"


class TestDryRun:
    def test_port_state_dry_run(self):
        r = _device_port_state("203.0.113.1", "1/1/1", enable=False, dry_run=True)
        assert r["dry_run"] is True
        assert "commands" in r
        assert len(r["commands"]) >= 2

    def test_vlan_create_dry_run(self):
        r = _device_vlan_create("203.0.113.1", "100", name="TEST", tagged_ports="ethernet 1/1/1",
                                spanning_tree=True, dry_run=True)
        assert r["dry_run"] is True
        assert "commands" in r
        assert len(r["commands"]) >= 2

    def test_vlan_delete_dry_run(self):
        r = _device_vlan_delete("203.0.113.1", "100", dry_run=True)
        assert r["dry_run"] is True
        assert "commands" in r
        assert len(r["commands"]) >= 2

    def test_vlan_port_dry_run(self):
        r = _device_vlan_port("203.0.113.1", "1/1/1", "200", action="add", dry_run=True)
        assert r["dry_run"] is True
        assert "commands" in r
        assert len(r["commands"]) >= 2


class TestPoePort:
    def test_unknown_device(self):
        r = _device_poe_port("192.168.99.99", "1/1/1", enable=True)
        assert r["error"] == "device_not_found"

    def test_enable(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=True)
        assert r["success"] is True
        assert r["action"] == "enable"

    def test_disable(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=False)
        assert r["action"] == "disable"

    def test_dry_run(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=True, dry_run=True)
        assert r["dry_run"] is True
        assert "commands" in r

    def test_enable_with_priority(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=True, priority=2)
        assert r["success"] is True
        assert r["action"] == "enable"

    def test_enable_with_priority_and_power_limit(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=True,
                             priority=2, power_limit=30000)
        assert r["success"] is True

    def test_enable_with_priority_and_class(self):
        r = _device_poe_port("203.0.113.1", "1/1/1", enable=True,
                             priority=2, power_by_class=4)
        assert r["success"] is True
