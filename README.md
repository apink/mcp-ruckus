# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

FastMCP-based MCP server for Ruckus wireless (vSZ SmartZone) and switching (ICX) infrastructure. Provides **62 tools** for AP monitoring, client traffic analytics, RF optimization, WLAN management, switch management, alarms, and health monitoring via streamable-http / SSE transport with security middleware.

## Features

- **62 MCP tools** across vSZ + ICX domains
- **vSZ tools (35)**: AP status/radio/neighbors, **RF channel/power optimization (DSATUR + Tabu Search)**, SSID/WLAN CRUD, **client traffic stats per WLAN/AP/zone**, alarm list, rogue detection, client tracking, events, **controller health**
- **ICX switch tools (22)**: device info/status, interfaces (summary/down/errors/stats), VLAN/LAG, MAC tables, routing table (v4+v6), IPv6, chassis health, ping/traceroute (v4+v6), **config backup + drift detection**
- **Bulk tools (3)**: all-device info/status/backup
- **Inventory tools (2)**: filter by location/role
- **Connectivity tools (3)**: local ping, port check, HTTP latency

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
| `RUCKUS_ICX_USER` | ICX SSH username | - |
| `RUCKUS_ICX_PASS` | ICX SSH password | - |
| `MCP_API_KEY` | API key for security middleware | - |
| `MCP_ALLOWED_IPS` | Comma-separated allowed IPs | `10.0.0.0/8` |

### Server Configuration

| Variable | Description | Default |
|---|---|---|
| `MCP_TRANSPORT` | Transport protocol | `sse` |
| `MCP_PORT` | Server port | `8000` |
| `MCP_HOST` | Bind address | `0.0.0.0` |

### Agent-Side Setup

**Claude Desktop** — macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`  
Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```jsonc
{
  "mcpServers": {
    "ruckus": {
      "type": "sse",
      "url": "http://<server-ip>:8000/sse",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

**Hermes (Goose)** — `~/.config/hermes/config.json`

```jsonc
{
  "mcpServers": {
    "ruckus": {
      "transport": "sse",
      "url": "http://<server-ip>:8000/sse",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

**Endpoint mapping:**

| Transport | URL Path |
|-----------|----------|
| SSE | `http://<host>:<port>/sse` |
| streamable-http | `http://<host>:<port>/mcp` |

### Device Inventory

Create `inventory/devices.yaml` for ICX tools:

```yaml
devices:
  - host: "10.0.0.10"
    name: "switch-core-01"
    vendor: "ruckus"
    role: "core"
    location: "datacenter"
```

## Tools

### vSZ AP Tools (6)

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

### vSZ Monitoring Tools (5)

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

### ICX Switch Tools (22)

| Tool | Description |
|---|---|
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
| `ruckus_device_chassis_health` | Power, fans, temperature |
| `ruckus_device_ipv6_interfaces` | IPv6 interfaces |
| `ruckus_device_ping` | Ping from switch |
| `ruckus_device_ping_ipv6` | IPv6 ping |
| `ruckus_device_traceroute` | Traceroute from switch |
| `ruckus_device_traceroute_ipv6` | IPv6 traceroute |
| `ruckus_device_config_backup` | Config backup (metadata-only default) |
| `ruckus_device_config_diff` | Config drift detection |

### Inventory & Bulk Tools (5)

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
│   ├── device_ssh.py (sync ICX Netmiko SSH driver, 22 tools)
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
│   ├── icx_device.py (22 ICX switch tools)
│   ├── inventory.py (device inventory + bulk)
│   └── connectivity.py (local ping/port/http)
├── inventory/
│   └── devices.yaml (gitignored)
├── backups/ (gitignored, mode 0600)
└── tests/ (12 test files, 131 tests, mock adapters)
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
pytest tests/ -q           # 131 tests, 12 test files
pytest tests/ -v           # verbose output
```

Zero real hardware required — full mock adapter layer in `tests/conftest.py`.

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
