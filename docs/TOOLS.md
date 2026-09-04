# Tool Reference — MCP Ruckus

Total **90 tools** (31 vSZ + 50 ICX + 6 inventory + 3 connectivity).

## Response envelope

List-returning tools now return a consistent envelope instead of a bare array:

```json
{"items": [...], "total": 100, "returned": 50, "truncated": true, "hint": "..."}
```

- `truncated=true` means more records exist — drill down by ID (see `hint`) rather than re-querying the full list.
- `returned` is capped by `MCP_MAX_ITEMS` (default 50).
- Some heavy tools add a `summary=True` parameter to return aggregate counts only.

## vSZ AP Tools (7)

| Tool | Description |
|---|---|
| `ap_status` | AP status with optional zone filter; `summary=True` for aggregate counts |
| `ap_detail` | Detailed AP info |
| `ap_radio_stats` | Real-time per-radio stats (noise, airtime, retry) |
| `ap_neighbors` | RF neighbor data (AP/zone/all scope) |
| `ap_down` | Offline APs |
| `ap_high_client_count` | APs above client threshold |
| `reboot_ap` | Reboot AP by name (confirm gate) |

## vSZ RF Tools (3)

| Tool | Description |
|---|---|
| `optimize_wifi_rf` | Channel/power optimization — DSATUR + Tabu Search |
| `apply_rf_recommendation` | Push optimization results to APs (confirm gate) |
| `apply_ap_config` | Manual channel/power override (confirm gate) |

## vSZ WLAN Tools (7)

| Tool | Description |
|---|---|
| `ssid_list` | List SSIDs per zone |
| `ssid_list_all` | List all SSIDs across zones |
| `ssid_detail` | SSID config details |
| `radius_list` | RADIUS servers per zone |
| `create_wlan` | Create WLAN (Open/PSK/802.1X) (confirm gate) |
| `modify_wlan` | Modify WLAN config (confirm gate) |

## vSZ Client Tools (3)

| Tool | Description |
|---|---|
| `client_search` | Search client by MAC/IP/username |
| `client_roaming` | Track client roaming history |
| `disconnect_client` | Disconnect client from AP (confirm gate) |

## vSZ Traffic Tools (3)

| Tool | Description |
|---|---|
| `wlan_traffic_stats` | Per-WLAN rx/tx MB + client count + zone breakdown |
| `ap_traffic_stats` | Per-AP rx/tx MB + client count |
| `zone_traffic_stats` | Per-zone rx/tx MB + AP count + active WLANs |

## vSZ Monitoring Tools (6)

| Tool | Description |
|---|---|
| `zone_status` | Zone list with status |
| `zone_ap_list` | APs per zone |
| `alert_events` | Alert/event log with filters |
| `alarm_list` | Active alarms with severity/time filter |
| `rogue_client_query` | Rogue AP detection |
| `controller_stats` | Controller node info + uptime |

## vSZ System Tools (3)

| Tool | Description |
|---|---|
| `license_status` | License capacity |
| `domain_list` | Administration domains |
| `toggle_wlan` | Enable/disable WLAN (confirm gate) |

## ICX Switch Tools (50)

| Tool | Description |
|---|---|
| `ruckus_device_access_lists` | IP ACL rules + brief summary |
| `ruckus_device_users` | Local user accounts (password hash not exposed) |
| `ruckus_device_ssh_status` | SSH server status + sesi aktif (user, source IP) |
| `ruckus_device_spanning_tree` | STP topology |
| `ruckus_device_time` | Clock + NTP sync status |
| `ruckus_device_timezone_set` | Set system timezone (`gmt±HH[:MM]`) (confirm gate) |
| `ruckus_device_clock_set` | Set system date/time manually (confirm gate) |
| `ruckus_device_ntp_server` | Add/remove NTP server (confirm gate) |
| `ruckus_device_ntp_control` | Enable/disable NTP service (confirm gate) |
| `ruckus_device_config_save` | Save running-config to startup (`write memory`) (confirm gate) |
| `ruckus_device_info` | Device model, firmware, uptime |
| `ruckus_device_status` | CPU, memory, temperature |
| `ruckus_device_interfaces_summary` | All interfaces |
| `ruckus_device_interfaces_down` | Down interfaces |
| `ruckus_device_interfaces_errors` | Interface errors |
| `ruckus_device_interfaces_stats` | Interface utilization |
| `ruckus_device_ip_addresses` | IP addresses |
| `ruckus_device_ip_routes` | IPv4 routing table |
| `ruckus_device_ipv6_routes` | IPv6 routing table |
| `ruckus_device_ip_route` | Add static IPv4 route (next-hop/null0/interface) (confirm gate) |
| `ruckus_device_ip_route_delete` | Delete static IPv4 route (confirm gate) |
| `ruckus_device_ipv6_route` | Add static IPv6 route (next-hop/null0/interface) (confirm gate) |
| `ruckus_device_ipv6_route_delete` | Delete static IPv6 route (confirm gate) |
| `ruckus_device_ipv6_unicast_routing` | Enable/disable `ipv6 unicast-routing` (confirm gate) |
| `ruckus_device_vlan_summary` | VLAN summary |
| `ruckus_device_port_vlan` | VLAN per port |
| `ruckus_device_mac_table_vlan` | MAC table by VLAN; `summary=True` for aggregate counts |
| `ruckus_device_find_mac` | Locate MAC across device |
| `ruckus_device_lag_summary` | LAG status |
| `ruckus_device_lldp_neighbors` | LLDP neighbors (topology) |
| `ruckus_device_poe_status` | PoE power budget + per-port status (optional port filter) |
| `ruckus_device_poe_port` | Enable/disable PoE per port (priority, power_limit, power_by_class) (confirm gate) |
| `ruckus_device_optic_info` | SFP optic DOM |
| `ruckus_device_syslog` | System logs (parsed, dedup, filter) |
| `ruckus_device_cable_diag` | TDR cable diagnostics |
| `ruckus_device_sfp_info` | SFP/transceiver types |
| `ruckus_device_resources` | CPU and memory utilization |
| `ruckus_device_arp_table` | ARP table (IP→MAC→port); `summary=True` for aggregate counts |
| `ruckus_device_port_state` | Enable/disable port (admin up/down) (confirm gate) |
| `ruckus_device_vlan_create` | Create VLAN (single/range/multi + name + ports) (confirm gate) |
| `ruckus_device_vlan_delete` | Delete VLAN (single/range/multi) (confirm gate) |
| `ruckus_device_vlan_port` | Add/remove port VLAN membership (confirm gate) |
| `ruckus_device_chassis_health` | Power, fans, temperature |
| `ruckus_device_ipv6_interfaces` | IPv6 interfaces |
| `ruckus_device_ping` | Ping from switch |
| `ruckus_device_ping_ipv6` | IPv6 ping |
| `ruckus_device_traceroute` | Traceroute from switch |
| `ruckus_device_traceroute_ipv6` | IPv6 traceroute |
| `ruckus_device_config_backup` | Config backup (metadata-only default) |
| `ruckus_device_config_diff` | Config drift detection |

## Inventory & Bulk Tools (6)

| Tool | Description |
|---|---|
| `ruckus_list_devices` | List all devices |
| `ruckus_all_device_info` | All device info |
| `ruckus_all_device_status` | All device status |
| `ruckus_all_device_backup` | Backup all configs |
| `ruckus_devices_by_location` | Filter by location |
| `ruckus_devices_by_role` | Filter by role |

## Connectivity Tools (3)

| Tool | Description |
|---|---|
| `ping_device` | ICMP ping from server |
| `check_port` | TCP port check |
| `http_latency` | HTTP GET latency |
