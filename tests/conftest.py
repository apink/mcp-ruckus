"""pytest fixtures — mock adapters for offline testing.

Monkeypatches VsZRestAdapter and RuckusDeviceDriver so all 52 tools
can be tested without real vSZ/ICX hardware.

Patches are applied at import time (before any test module imports tools)
to ensure all references are captured correctly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("VSZ_HOST", "mock-vsz")
os.environ.setdefault("VSZ_USER", "mockuser")
os.environ.setdefault("VSZ_PASS", "mockpass")

from tests.fixtures import (  # noqa: E402
    SAMPLE_AP_RADIO_STATS,
    SAMPLE_APS,
    SAMPLE_CLIENTS,
    SAMPLE_CONFIG,
    SAMPLE_DEVICE_INFO,
    SAMPLE_DEVICE_STATUS,
    SAMPLE_EVENTS,
    SAMPLE_ICX_DEVICES,
    SAMPLE_INTERFACES,
    SAMPLE_IP_ROUTES,
    SAMPLE_ROGUE_CLIENTS,
    SAMPLE_VLAN_SUMMARY,
    SAMPLE_WLAN_DETAIL,
    SAMPLE_WLANS_ZONE1,
    SAMPLE_ZONES,
)


class MockVsZRestAdapter:
    """Drop-in mock for VsZRestAdapter."""

    def __init__(self, config: Any = None) -> None:
        self.config = config
        self._service_ticket = "mock-ticket"
        self._login_time = 9999999999.0
        self._logged_in = True

    async def login(self) -> dict[str, Any]:
        return {"status": "token_login_ok"}

    async def _ensure_login(self) -> dict[str, Any]:
        return {"status": "session_reused"}

    def close(self) -> None:
        pass
    async def aclose(self) -> None:
        pass

    async def get_all_aps(self) -> list[dict[str, Any]]:
        return list(SAMPLE_APS)

    async def get_aps_by_zone(self, zone_id: str) -> list[dict[str, Any]]:
        return [ap for ap in SAMPLE_APS if ap.get("zoneId") == zone_id or ap.get("zoneName") == zone_id]

    async def query_ap(self, search_term: str) -> list[dict[str, Any]]:
        return [ap for ap in SAMPLE_APS if search_term.lower() in ap.get("deviceName", "").lower()]

    async def get_ap_detail(self, mac: str) -> dict[str, Any]:
        return dict(SAMPLE_AP_RADIO_STATS)

    async def get_ap_neighbors(self, mac: str) -> dict[str, Any]:
        return {
            "list": [
                {"deviceName": "FTIS-AP01-02", "apMac": "aa:bb:cc:11:22:02", "model": "R750",
                 "ip": "10.60.172.102", "channel24G": "1 (20MHz)", "channel5G": "149 (80MHz)",
                 "snr24G": "25 dB", "snr5G": "30 dB"},
                {"deviceName": "FTIS-AP02-03", "apMac": "aa:bb:cc:11:33:03", "model": "R650",
                 "ip": "10.60.172.201", "channel24G": "11 (20MHz)", "channel5G": "52 (40MHz)",
                 "snr24G": "15 dB", "snr5G": "20 dB"},
            ]
        }

    async def modify_ap(self, ap_mac: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "applied", "apMac": ap_mac}

    async def get_zones(self) -> list[dict[str, Any]]:
        return list(SAMPLE_ZONES)

    async def get_zone_tree(self) -> dict[str, Any]:
        return {"name": "root", "zones": list(SAMPLE_ZONES)}

    async def get_wlans_by_zone(self, zone_id: str) -> list[dict[str, Any]]:
        if zone_id == "zone-fti-001":
            return list(SAMPLE_WLANS_ZONE1)
        return []

    async def get_wlan_detail(self, zone_id: str, wlan_id: str) -> dict[str, Any]:
        return dict(SAMPLE_WLAN_DETAIL)

    async def get_radius_servers(self, zone_id: str, for_accounting: bool | None = None) -> list[dict[str, Any]]:
        return [{"id": "radius-001", "name": "FTI-RADIUS", "serviceType": "ActiveDirectory",
                 "description": "FTI Auth Server", "zoneId": zone_id,
                 "primary": {"ip": "10.60.172.10"}, "secondary": {}}]

    async def create_wlan(self, zone_id: str, payload: dict[str, Any], wlan_type: str = "standard") -> dict[str, Any]:
        return {"id": "wlan-new-001", "status": "created", "ssid": payload.get("ssid", "")}

    async def query_client(self, client_id: str) -> dict[str, Any]:
        if not client_id:
            return {"totalCount": 0, "list": []}
        matches = [
            c for c in SAMPLE_CLIENTS["list"]
            if client_id.lower()
            in (c.get("hostname", "") + c.get("userName", "")
                + c.get("clientMac", "")).lower()
        ]
        return {"totalCount": len(matches), "list": matches}

    async def query_clients_by_ids(self, client_ids: list[str]) -> list[dict[str, Any]]:
        return list(SAMPLE_CLIENTS["list"])

    async def get_alert_events(self, limit: int = 20, severity: str | None = None,
                               category: str | None = None, hours_back: int | None = None,
                               text_search: str | None = None, page: int = 1) -> dict[str, Any]:
        events = list(SAMPLE_EVENTS["list"])
        if severity:
            events = [e for e in events if e["severity"] == severity]
        if category:
            events = [e for e in events if e["category"] == category]
        if text_search:
            events = [e for e in events if text_search.lower() in e.get("activity", "").lower()]
        start = (page - 1) * limit
        return {"totalCount": len(events), "firstIndex": start,
                "hasMore": len(events) > start + limit, "list": events[start:start + limit]}

    async def query_rogue_clients(self, domain_id: str | None = None, zone_id: str | None = None,
                                  rogue_mac: str | None = None, ssid: str | None = None,
                                  rogue_type: str | None = None, page: int = 1, limit: int = 100) -> dict[str, Any]:
        return dict(SAMPLE_ROGUE_CLIENTS)

    async def get_license(self) -> dict[str, Any]:
        return {"total_license": 100, "used_license": 5, "available_license": 95}

    async def get_domains(self) -> list[dict[str, Any]]:
        return [{"id": "domain-001", "name": "Default Domain"}]

    async def enable_disable_wlan(self, zone_id: str, wlan_id: str, enabled: bool) -> dict[str, Any]:
        return {"status": "ok", "enabled": enabled}

    async def reboot_ap(self, mac: str) -> dict[str, Any]:
        return {"status": "reboot_initiated"}

    async def disconnect_client(self, mac: str, ap_mac: str) -> dict[str, Any]:
        return {"status": "disconnect_initiated"}

    async def query_clients(self, limit: int = 100, page: int = 1,
                            ssid: str | None = None, ap_name: str | None = None
                            ) -> dict[str, Any]:
        return {"totalCount": 0, "hasMore": False, "firstIndex": 0, "list": []}

    async def modify_wlan(self, zone_id: str, wlan_id: str,
                          updates: dict[str, Any]) -> dict[str, Any]:
        return {"status": "modified", "updated_fields": list(updates.keys())}

    async def controller_stats(self) -> dict[str, Any]:
        return {
            "total_nodes": 1,
            "nodes": [{
                "name": "SZ-01", "model": "vSZ-H", "version": "6.1.2",
                "ap_version": "6.1.2", "role": "Leader", "uptime_days": 45.2,
                "control_ip": "10.0.0.1", "serial": "xxx",
            }],
            "note": "CPU/memory/storage not exposed by vSZ public API",
        }


class MockRuckusDeviceDriver:
    """Drop-in mock for RuckusDeviceDriver."""

    def __init__(self, device: Any) -> None:
        self.device = device

    def get_device_info(self) -> dict[str, Any]:
        return dict(SAMPLE_DEVICE_INFO)

    def get_device_status(self) -> dict[str, Any]:
        return dict(SAMPLE_DEVICE_STATUS)

    def get_interfaces_summary(self) -> list[dict[str, Any]]:
        return list(SAMPLE_INTERFACES)

    def get_interfaces_down(self) -> list[dict[str, Any]]:
        return [i for i in SAMPLE_INTERFACES if i["link"] == "down"]

    def get_interfaces_errors(self) -> list[dict[str, Any]]:
        return []

    def get_interfaces_stats(self) -> list[dict[str, Any]]:
        return [dict(i, util_pct=50, pps_in=1000, pps_out=800) for i in SAMPLE_INTERFACES]

    def get_ip_addresses(self) -> list[dict[str, Any]]:
        return [{"interface": "ve 100", "ip": "10.60.172.1", "mask": "255.255.255.0"}]

    def get_ip_routes(self, destination: str | None = None) -> dict[str, Any]:
        routes = list(SAMPLE_IP_ROUTES["routes"])
        if destination:
            routes = [r for r in routes if r["destination"] == destination]
        return {"total": len(routes), "routes": routes}

    def get_ipv6_routes(self, destination: str | None = None) -> dict[str, Any]:
        return {"total": 2, "routes": [{"destination": "::/0", "next_hop": "fe80::1", "type": "Static"}]}

    def get_vlan_summary(self) -> dict[str, Any]:
        return dict(SAMPLE_VLAN_SUMMARY)

    def get_port_vlan(self, port: str) -> dict[str, Any]:
        return {"port": port, "vlans": [{"id": 100, "mode": "tagged"}, {"id": 1, "mode": "untagged"}]}

    def get_mac_table_vlan(self, vlan_id: int) -> list[dict[str, Any]]:
        return [{"mac": "cc:dd:ee:11:22:01", "port": "1/2/1", "vlan": vlan_id}]

    def find_mac(self, mac: str) -> list[dict[str, Any]]:
        return [{"mac": mac, "port": "1/2/1", "vlan": 100}]

    def get_lag_summary(self) -> list[dict[str, Any]]:
        return [{"name": "LAG-1", "ports": ["1/1/1", "1/1/2"], "status": "up"}]

    def get_lldp_neighbors(self) -> list[dict[str, Any]]:
        return [
            {"local_port": "1/1/1", "chassis_id": "c0c5.2053.b258", "port_id": "c1c5.2053.b35a",
             "port_description": "GigabitEthernet1/1/3", "system_name": "BS-RISET-L3"},
        ]

    def get_poe_status(
        self, port: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "port": port or "1/1/1",
            "admin_state": "On",
            "oper_state": "Off",
            "power_consumed_mw": 0,
            "power_allocated_mw": 30000,
            "pd_type": "n/a",
            "pd_class": "n/a",
            "priority": 3,
            "fault": None,
        }
        if port:
            if port not in ("1/1/1", "1/1/2"):
                return {"host": "10.60.172.1", "port": port, "status": None}
            return {"host": "10.60.172.1", "port": port, "status": entry}
        return {"host": "10.60.172.1",
                "power_capacity_total_mw": 740000,
                "power_capacity_free_mw": 740000,
                "ports": [entry]}

    def get_arp_table(self) -> list[dict[str, Any]]:
        return [
            {"ip": "10.3.3.81", "mac": "c0c5.206c.53c2", "type": "Dynamic",
             "age": 2, "port": "1/1/23", "status": "Valid"},
        ]

    def get_users(self) -> list[dict[str, Any]]:
        return [
            {"username": "admin", "encrypt": "enabled", "privilege": "0",
             "status": "enabled", "expire_time": "Never"},
        ]

    def get_ssh_status(self) -> dict[str, Any]:
        return {
            "host": "10.60.172.1", "ssh_version": "v2.0", "ssh_enabled": True,
            "host_key": "RSA(2048)", "sessions": [
                {"direction": "inbound", "connection": 3, "version": "SSH-2",
                 "encryption": "aes128-ctr", "username": "admin",
                 "hmac": "hmac-sha1", "server_hostkey": "ssh-rsa",
                 "source_ip": "10.10.10.177"},
            ],
        }

    def get_device_resources(self) -> dict[str, Any]:
        return {
            "host": "10.60.172.1",
            "cpus": [
                {"cpu_id": 0, "pct_busy_1sec": 2, "pct_busy_5sec": 2,
                 "pct_busy_60sec": 2, "pct_busy_300sec": 1},
            ],
            "memory_total_bytes": 2094768128, "memory_free_bytes": 1323335680,
            "memory_used_bytes": 771432448, "memory_used_pct": 36.8,
        }

    def get_sfp_info(self, port: str | None = None) -> list[dict[str, Any]]:
        return [
            {"port": "1/2/1", "type": "10GE LR 10km (SFP+)"},
            {"port": "1/2/2", "type": "EMPTY"},
        ]

    def get_cable_diag(self, port: str) -> dict[str, Any]:
        return {
            "host": "10.60.172.1", "port": port, "pairs": [
                {"local_pair": "A", "remote_pair": "B", "pair_status": "terminated"},
                {"local_pair": "B", "remote_pair": "A", "pair_status": "terminated"},
                {"local_pair": "C", "remote_pair": "D", "pair_status": "terminated"},
                {"local_pair": "D", "remote_pair": "C", "pair_status": "terminated"},
            ],
        }

    def get_syslog(self, lines: int = 50, severity: str = "",
                   dedup: bool = True) -> dict[str, Any]:
        entries = [
            {"timestamp": "Aug  7 09:32:15", "severity": "I", "facility": "Security",
             "message": "SSH login by admin from src IP 10.10.10.177"},
            {"timestamp": "Aug  7 09:31:05", "severity": "E", "facility": "STP",
             "message": "Port 1/1/2 BLOCKING topology change"},
        ]
        return {"host": "10.60.172.1", "returned": 2, "total": 2,
                "severity_filter": severity or "all", "entries": entries}

    def get_optic_info(self, port: str) -> dict[str, Any]:
        return {"host": "10.60.172.1", "port": port,
                "temperature": 35.4, "temperature_unit": "C",
                "voltage": 3.31, "voltage_unit": "V",
                "tx_power": 0.68, "tx_power_unit": "dBm",
                "rx_power": 0.55, "rx_power_unit": "dBm",
                "tx_bias": 12.8, "tx_bias_unit": "mA",
                "thresholds": {
                    "temperature": {"high_alarm": 95.0, "low_alarm": -50.0,
                                    "high_warning": 85.0, "low_warning": -40.0},
                    "voltage": {"high_alarm": 3.63, "low_alarm": 2.97,
                                "high_warning": 3.465, "low_warning": 3.135},
                    "tx_bias": {"high_alarm": 90.0, "low_alarm": 2.0,
                                "high_warning": 80.0, "low_warning": 3.0},
                    "tx_power": {"high_alarm": 3.5, "low_alarm": -6.2,
                                 "high_warning": 1.5, "low_warning": -4.2},
                    "rx_power": {"high_alarm": 2.5, "low_alarm": -16.4,
                                 "high_warning": 0.5, "low_warning": -14.4},
                }}

    def get_device_time(self) -> dict[str, Any]:
        return {
            "host": "10.60.172.1",
            "current_time": "Fri Aug 07 2026 14:34:13.227 GMT+07",
            "ntp_synced": False,
            "ntp_status": "unsynchronized — no reference clock",
            "ntp_server_enabled": True,
            "ntp_client_enabled": True,
            "ntp_master_enabled": False,
            "ntp_in_panic": False,
            "ntp_peers": [
                {"address": "10.10.10.147", "ref_clock": "INIT", "stratum": "16",
                 "reachable": False, "delay": "0.00", "offset": "0.000"},
                {"address": "103.123.108.224", "ref_clock": "INIT", "stratum": "16",
                 "reachable": False, "delay": "0.00", "offset": "0.000"},
            ],
        }

    def get_spanning_tree(self, vlan: str | None = None) -> dict[str, Any]:
        return {
            "host": "10.60.172.1", "stp_configured": True, "vlan": 1,
            "root_id": "800050a7334112a0", "root_cost": 0, "root_port": "Root",
            "bridge_priority": "8000", "bridge_address": "50a7334112a0",
            "ports": [
                {"port": "1/1/1", "priority": "80", "path_cost": 4,
                 "state": "FORWARDING", "fwd_transitions": 3,
                 "designated_cost": "0", "designated_root": "800050a7334112a0",
                 "designated_bridge": "800050a7334112a0"},
                {"port": "1/1/2", "priority": "80", "path_cost": 0,
                 "state": "DISABLED", "fwd_transitions": 0,
                 "designated_cost": "0", "designated_root": "0000000000000000",
                 "designated_bridge": "0000000000000000"},
            ],
        }

    def get_access_lists(self, name: str | None = None, brief: bool = False) -> dict[str, Any]:
        if brief:
            return {
                "host": "10.60.172.1",
                "acls": [
                    {"type": "Standard", "name": "ADMINSSH", "entries": 8},
                    {"type": "Extended", "name": "INET-ONLY", "entries": 5},
                ],
            }
        return {
            "host": "10.60.172.1",
            "acls": [
                {"type": "Standard", "name": "ADMINSSH", "entries": 8, "rules": [
                    {"sequence": 10, "action": "permit", "match": "host 10.10.10.4"},
                    {"sequence": 20, "action": "permit", "match": "host 10.10.10.215"},
                ]},
                {"type": "Extended", "name": "INET-ONLY", "entries": 5, "rules": [
                    {"sequence": 10, "action": "permit", "match": "icmp 10.80.0.0 0.0.255.255 host 10.255.255.80"},
                    {"sequence": 500, "action": "permit", "match": "ip any any"},
                ]},
            ],
        }

    def get_chassis_health(self) -> dict[str, Any]:
        return {"power_supplies": 2, "fans": 4, "temperature_c": 45, "status": "healthy"}

    def get_ipv6_interfaces(self) -> list[dict[str, Any]]:
        return [{"interface": "ve 100", "ip": "2001:db8::1", "prefix": "64"}]

    def device_ping(self, ip: str, source: str | None = None) -> dict[str, Any]:
        return {"target": ip, "success": True, "rtt_avg_ms": 1.5, "packets_sent": 5, "packets_received": 5}

    def device_ping_ipv6(self, ip: str) -> dict[str, Any]:
        return {"target": ip, "success": True, "rtt_avg_ms": 2.0, "packets_sent": 5, "packets_received": 5}

    def device_traceroute(self, ip: str, source_ip: str | None = None, max_ttl: int = 30) -> list[dict[str, Any]]:
        return [{"hop": 1, "ip": "10.60.172.254", "rtt_ms": 1.0}, {"hop": 2, "ip": ip, "rtt_ms": 2.0}]

    def device_traceroute_ipv6(self, ip: str, max_ttl: int = 30) -> list[dict[str, Any]]:
        return [{"hop": 1, "ip": "fe80::1", "rtt_ms": 1.0}]

    def get_config(self, config_type: str = "running") -> dict[str, Any]:
        return dict(SAMPLE_CONFIG)

    def set_port_state(
        self, port: str, enable: bool, dry_run: bool = False,
    ) -> dict[str, Any]:
        state = "enabled" if enable else "disabled"
        if dry_run:
            return {"host": "10.60.172.1", "port": port, "dry_run": True,
                    "state": state, "commands": ["conf t", f"int eth {port}", state, "end"]}
        return {"host": "10.60.172.1", "port": port, "state": state}

    def create_vlan(
        self, vlan_spec: str, name: str | None = None,
        tagged_ports: str = "", untagged_ports: str = "",
        spanning_tree: bool = False, stp_priority: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from adapters.device_ssh import _parse_vlan_spec
        vlan_ids = _parse_vlan_spec(vlan_spec)
        if dry_run:
            return {"host": "10.60.172.1", "vlan_spec": vlan_spec,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": ["conf t", "...", "end"]}
        return {"host": "10.60.172.1", "vlan_spec": vlan_spec,
                "vlan_ids": vlan_ids, "created": True}

    def delete_vlan(
        self, vlan_spec: str, dry_run: bool = False,
    ) -> dict[str, Any]:
        from adapters.device_ssh import _parse_vlan_spec
        vlan_ids = _parse_vlan_spec(vlan_spec)
        if dry_run:
            return {"host": "10.60.172.1", "vlan_spec": vlan_spec,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": ["conf t", "no vlan ...", "end"]}
        return {"host": "10.60.172.1", "vlan_spec": vlan_spec,
                "vlan_ids": vlan_ids, "deleted": True}

    def modify_vlan_port(
        self, port: str, vlan_spec: str, action: str, tagged: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from adapters.device_ssh import _parse_vlan_spec
        vlan_ids = _parse_vlan_spec(vlan_spec)
        if dry_run:
            return {"host": "10.60.172.1", "port": port, "action": action,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": ["conf t", "...", "end"]}
        return {"host": "10.60.172.1", "port": port, "action": action,
                "vlan_spec": vlan_spec, "vlan_ids": vlan_ids, "success": True}

    def set_poe_port(
        self, port: str, enable: bool,
        priority: int | None = None,
        power_limit: int | None = None,
        power_by_class: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        action = "disable" if not enable else "enable"
        if dry_run:
            return {"host": "10.60.172.1", "port": port, "dry_run": True,
                    "action": action, "commands": ["conf t", "...", "end"]}
        return {"host": "10.60.172.1", "port": port, "action": action,
                "success": True}


class MockICXDevice:
    def __init__(self, host: str = "", name: str = "", vendor: str = "ruckus",
                 role: str = "", location: str = "", rack: str = "", **kwargs):
        self.host = host
        self.name = name
        self.vendor = vendor
        self.role = role
        self.location = location
        self.rack = rack

    def to_dict(self) -> dict[str, Any]:
        return {"host": self.host, "name": self.name, "vendor": self.vendor,
                "role": self.role, "location": self.location, "rack": self.rack}


def _mock_load_inventory():
    return [MockICXDevice(**d) for d in SAMPLE_ICX_DEVICES]


def _mock_get_device_record(host: str):
    for d in SAMPLE_ICX_DEVICES:
        if d["host"] == host:
            return MockICXDevice(**d)
    return None


# ── Module-level patches (applied before any test collects) ──────

_ALREADY_PATCHED = False

def _apply_mocks():
    global _ALREADY_PATCHED
    if _ALREADY_PATCHED:
        return
    _ALREADY_PATCHED = True

    # Patch inventory BEFORE tools are imported (tools import at module level)
    import inventory.manager as inv_manager
    inv_manager.load_inventory = _mock_load_inventory
    inv_manager.get_device_record = _mock_get_device_record

    # Patch adapters
    import adapters.vsz as vsz_mod
    vsz_mod.VsZRestAdapter = MockVsZRestAdapter

    import adapters.device_ssh as ssh_mod
    ssh_mod.RuckusDeviceDriver = MockRuckusDeviceDriver


_apply_mocks()


@pytest.fixture(autouse=True)
def mock_adapters():
    """Fixture placeholder — mocks already applied at module level."""
    yield
