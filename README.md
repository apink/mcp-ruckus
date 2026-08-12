# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

FastMCP-based MCP server for Ruckus wireless (vSZ SmartZone) and switching (ICX) infrastructure. Provides **81 MCP tools** for AP monitoring, client traffic analytics, RF optimization, WLAN management, switch management, LLDP neighbors, PoE status, alarms, and health monitoring via streamable-http / SSE transport with security middleware.

## Features

- **81 MCP tools** across vSZ + ICX domains
- **vSZ tools (31)**: AP status/radio/neighbors, **RF channel/power optimization (DSATUR + Tabu Search)**, SSID/WLAN CRUD, **client traffic stats per WLAN/AP/zone**, alarm list, rogue detection, client tracking, events, **controller health**
- **ICX switch tools (41)**: device info/status, interfaces (summary/down/errors/stats), VLAN/LAG, MAC tables, routing table (v4+v6), IPv6, chassis health, ping/traceroute (v4+v6), **LLDP, PoE, ARP, CPU/mem, optic DOM, syslog, TDR cable diag, SFP info, config backup + drift detection, users, SSH status, port enable/disable, VLAN create/delete/port, PoE port enable/disable + per-port PoE status**
- **Inventory & bulk tools (6)**: list devices, all-device info/status/backup, filter by location/role

- **Multi-transport**: SSE + streamable-http with ASGI SecurityMiddleware
- **Async**: full async vSZ adapter (httpx.AsyncClient) + all vSZ tools, parallel neighbor fetch, RF optimizer offloaded

## Quick Start

### Local Development

```bash
git clone https://github.com/your-org/mcp-ruckus.git
cd mcp-ruckus
cp .env.example .env
# Edit .env with your credentials

# via pyproject.toml (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -e .

# atau via requirements.txt
pip install -r requirements.txt

# Edit MCP_TRANSPORT di .env (sse / streamable-http)
python3 server.py
```

### Docker Deployment

```bash
docker build -t ruckus-mcp:latest .
docker compose up -d
```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|---|---|---|
| `VSZ_HOST` | vSZ SmartZone IP | `10.0.0.1` |
| `VSZ_PORT` | vSZ HTTPS port | `8443` |
| `VSZ_USER` | vSZ username | - |
| `VSZ_PASS` | vSZ password | - |
| `VSZ_API_TOKEN` | Optional API token | - |
| `VSZ_API_VERSION` | API version (v10_0, v11_1) | `v11_1` |
| `VSZ_RATE_LIMIT` | Max concurrent API requests | `10` |
| `ICX_RATE_LIMIT` | Max concurrent SSH sessions per device | `5` |
| `MCP_API_KEY` | API key for security middleware | - |
| `MCP_ALLOWED_IPS` | Comma-separated allowed IPs | `10.0.0.0/8` |

### Device Inventory

Create `inventory/devices.yaml` for ICX tools.
`username` / `password` support `${ENV_VAR}` substitution or literal values:

```yaml
devices:
  - host: "10.0.0.10"
    name: "switch-core-01"
    vendor: "ruckus"
    role: "core"
    location: "datacenter"
    username: "${ICX_CORE_USER}"
    password: "${ICX_CORE_PASS}"

  - host: "10.0.10.1"
    name: "sw-branch"
    username: "admin-branch"
    password: "s3cret123"
```

## Tools

### vSZ AP Tools (7)

| Tool | Description |
|---|---|
| `ap_status` | AP status with optional zone filter |
| `ap_detail` | Detailed AP info |
| `ap_radio_stats` | Real-time per-radio stats (noise, airtime, retry) |
| `ap_neighbors` | RF neighbor data (AP/zone/all scope) |
| `ap_down` | Offline APs |
| `ap_high_client_count` | APs above client threshold |
| `reboot_ap` | Reboot AP by name |

### vSZ RF Tools (3)

| Tool | Description |
|---|---|
| `optimize_wifi_rf` | Channel/power optimization — DSATUR + Tabu Search |
| `apply_rf_recommendation` | Push optimization results to APs (confirm gate) |
| `apply_ap_config` | Manual channel/power override |

### vSZ WLAN Tools (6)

| Tool | Description |
|---|---|
| `ssid_list` | List SSIDs per zone |
| `ssid_list_all` | List all SSIDs across zones |
| `ssid_detail` | SSID config details |
| `radius_list` | RADIUS servers per zone |
| `create_wlan` | Create WLAN (Open/PSK/802.1X) |
| `modify_wlan` | Modify WLAN config (confirm gate) |

### vSZ Client Tools (3)

| Tool | Description |
|---|---|
| `client_search` | Search client by MAC/IP/username |
| `client_roaming` | Track client roaming history |
| `disconnect_client` | Disconnect client from AP |

### vSZ Traffic Tools (3)

| Tool | Description |
|---|---|
| `wlan_traffic_stats` | Per-WLAN rx/tx MB + client count + zone breakdown |
| `ap_traffic_stats` | Per-AP rx/tx MB + client count |
| `zone_traffic_stats` | Per-zone rx/tx MB + AP count + active WLANs |

### vSZ Monitoring Tools (6)

| Tool | Description |
|---|---|
| `zone_status` | Zone list with status |
| `zone_ap_list` | APs per zone |
| `alert_events` | Alert/event log with filters |
| `alarm_list` | Active alarms with severity/time filter |
| `rogue_client_query` | Rogue AP detection |
| `controller_stats` | Controller node info + uptime |

### vSZ System Tools (3)

| Tool | Description |
|---|---|
| `license_status` | License capacity |
| `domain_list` | Administration domains |
| `toggle_wlan` | Enable/disable WLAN |

### icx_device.py (41 ICX switch tools)

| Tool | Description |
|---|---|---|
| `ruckus_device_access_lists` | IP ACL rules + brief summary |
| `ruckus_device_users` | Local user accounts (hash tidak diekspos) |
| `ruckus_device_ssh_status` | SSH server status + sesi aktif (user, source IP) |
| `ruckus_device_spanning_tree` | STP topology |
| `ruckus_device_time` | Clock + NTP sync status |
| `ruckus_device_info` | Device model, firmware, uptime |
| `ruckus_device_status` | CPU, memory, temperature |
| `ruckus_device_interfaces_summary` | All interfaces |
| `ruckus_device_interfaces_down` | Down interfaces |
| `ruckus_device_interfaces_errors` | Interface errors |
| `ruckus_device_interfaces_stats` | Interface utilization |
| `ruckus_device_ip_addresses` | IP addresses |
| `ruckus_device_ip_routes` | IPv4 routing table |
| `ruckus_device_ipv6_routes` | IPv6 routing table |
| `ruckus_device_vlan_summary` | VLAN summary |
| `ruckus_device_port_vlan` | VLAN per port |
| `ruckus_device_mac_table_vlan` | MAC table by VLAN |
| `ruckus_device_find_mac` | Locate MAC across device |
| `ruckus_device_lag_summary` | LAG status |
| `ruckus_device_lldp_neighbors` | LLDP neighbors (topology) |
| `ruckus_device_poe_status` | PoE power budget + per-port status (optional port filter) |
| `ruckus_device_poe_port` | Enable/disable PoE per port (priority, power_limit, power_by_class) — confirm gate |
| `ruckus_device_optic_info` | SFP optic DOM |
| `ruckus_device_syslog` | System logs (parsed, dedup, filter) |
| `ruckus_device_cable_diag` | TDR cable diagnostics |
| `ruckus_device_sfp_info` | SFP/transceiver types |
| `ruckus_device_resources` | CPU and memory utilization |
| `ruckus_device_arp_table` | ARP table (IP→MAC→port) |
| `ruckus_device_port_state` | Enable/disable port (admin up/down) — confirm gate |
| `ruckus_device_vlan_create` | Create VLAN (single/range/multi + name + ports) — confirm gate |
| `ruckus_device_vlan_delete` | Delete VLAN (single/range/multi) — confirm gate |
| `ruckus_device_vlan_port` | Add/remove port VLAN membership — confirm gate |
| `ruckus_device_chassis_health` | Power, fans, temperature |
| `ruckus_device_ipv6_interfaces` | IPv6 interfaces |
| `ruckus_device_ping` | Ping from switch |
| `ruckus_device_ping_ipv6` | IPv6 ping |
| `ruckus_device_traceroute` | Traceroute from switch |
| `ruckus_device_traceroute_ipv6` | IPv6 traceroute |
| `ruckus_device_config_backup` | Config backup (metadata-only default) |
| `ruckus_device_config_diff` | Config drift detection |

### Inventory & Bulk Tools (6)

| Tool | Description |
|---|---|
| `ruckus_list_devices` | List all devices |
| `ruckus_all_device_info` | All device info |
| `ruckus_all_device_status` | All device status |
| `ruckus_all_device_backup` | Backup all configs |
| `ruckus_devices_by_location` | Filter by location |
| `ruckus_devices_by_role` | Filter by role |

### Connectivity Tools (3)

| Tool | Description |
|---|---|
| `ping_device` | ICMP ping from server |
| `check_port` | TCP port check |
| `http_latency` | HTTP GET latency |

## Architecture

```
server.py (FastMCP, SSE + streamable-http, ASGI SecurityMiddleware)
├── adapters/
│   ├── vsz.py (async vSZ REST adapter — httpx.AsyncClient, 24 methods)
│   ├── device_ssh.py (sync ICX Netmiko SSH driver, 30 tools)
│   └── config.py (VsZConfig, DeviceCredentials)
├── tools/
│   ├── vsz_system.py (zone, license, controller stats)
│   ├── vsz_aps.py (AP status, detail, radio, neighbors, reboot)
│   ├── vsz_wlans.py (WLAN CRUD, modify, toggle)
│   ├── vsz_clients.py (search, roaming, disconnect)
│   ├── vsz_traffic.py (WLAN/AP/zone traffic aggregation)
│   ├── vsz_events.py (alert events)
│   ├── vsz_alarms.py (active alarms)
│   ├── vsz_rogue.py (rogue client query)
│   ├── vsz_rf.py (RF optimization + apply)
│   ├── vsz_domains.py (domain list)
│   ├── icx_device.py (41 ICX switch tools)
│   ├── inventory.py (device inventory + bulk)
│   └── connectivity.py (local ping/port/http)
├── inventory/
│   └── devices.yaml (gitignored)
├── backups/ (gitignored, mode 0600)
└── tests/ (12 test files, 187 tests, mock adapters)
```

## Security

### Config Backup
- Switch config backed up to `backups/{host}_{type}_{ts}.cfg`, mode `0600`
- Default: metadata only (path, sha256, size) — secrets stay out of context
- `include_config=True` opt-in returns raw config (audit logged)

### Input Validation
- 10+ pre-compiled regex validators for SSH commands (port, MAC, IP, VLAN)
- UUID validation for vSZ API path parameters

### Transport Security
- ASGI SecurityMiddleware: API key + IP whitelist
- SSE and streamable-http authenticated endpoints

## Testing

```bash
pytest tests/ -q           # 187 tests, 12 test files
pytest tests/ -v           # verbose output
```

Zero real hardware required — full mock adapter layer in `tests/conftest.py`. **187 tests**, 12 test files.

## Deployment

```bash
docker build -t ruckus-mcp:latest .
docker compose up -d
```

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
