# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

FastMCP-based MCP server for Ruckus wireless (vSZ SmartZone) and switching (ICX) infrastructure. Provides **81 MCP tools** for AP monitoring, client traffic analytics, RF optimization, WLAN management, switch management, LLDP neighbors, PoE status, alarms, and health monitoring via streamable-http / SSE transport with security middleware.

## Features

- **81 MCP tools** (31 vSZ + 41 ICX + 6 inventory + 3 connectivity)
- **vSZ**: AP status/radio/neighbors, RF optimization (DSATUR + Tabu Search), WLAN CRUD, traffic stats, alarms, rogue detection, client tracking, controller health
- **ICX**: device info/status, interfaces, VLAN/LAG, routing (v4+v6), PoE, LLDP, ARP, optic DOM, syslog, TDR diagnostics, SFP, config backup + drift detection, port control, VLAN management
- **Full async** vSZ adapter (httpx.AsyncClient), ICX SSH via Netmiko with per-device rate limiting

Complete tool list: [docs/TOOLS.md](docs/TOOLS.md)

## Quick Start

### Local

```bash
git clone https://github.com/your-org/mcp-ruckus.git
cd mcp-ruckus
cp .env.example .env
# Edit .env with your credentials

python3 -m venv venv && source venv/bin/activate
pip install -e .        # or: pip install -r requirements.txt

# Edit MCP_TRANSPORT in .env (sse / streamable-http)
python3 server.py
```

### Docker

```bash
docker build -t ruckus-mcp:latest .
docker compose up -d
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `VSZ_HOST` | vSZ SmartZone IP | `10.0.0.1` |
| `VSZ_PORT` | vSZ HTTPS port | `8443` |
| `VSZ_USER` / `VSZ_PASS` | vSZ credentials | - |
| `VSZ_API_TOKEN` | Optional API token | - |
| `VSZ_API_VERSION` | API version (v10_0, v11_1) | `v11_1` |
| `VSZ_RATE_LIMIT` | Max concurrent API requests | `10` |
| `ICX_RATE_LIMIT` | Max concurrent SSH sessions per device | `5` |
| `MCP_API_KEY` | API key for security middleware | - |
| `MCP_ALLOWED_IPS` | Comma-separated allowed IPs | `10.0.0.0/8` |

### Device Inventory

Create `inventory/devices.yaml` for ICX tools. `username`/`password` support `${ENV_VAR}` substitution or literal values:

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

## Documentation

| Doc | Content |
|---|---|
| [docs/TOOLS.md](docs/TOOLS.md) | Complete list of 81 tools |
| [DOCS_SAFETY.md](DOCS_SAFETY.md) | Safety gates (12 destructive tools) + dry-run preview |
| [SECURITY.md](SECURITY.md) | Security policy, input validation, credential handling |
| [CHANGES.md](CHANGES.md) | Changelog + release notes |
| [SKILL.md](SKILL.md) | AI agent skill (copy to your agent's skills dir) |
| [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) | Development guidelines |

## Security

- All destructive tools require `confirm=True` — without it returns `confirm_required`, no effect
- ICX config tools support `dry_run=True` for preview without execution
- Config backup: metadata-only default (mode `0600`), `include_config=True` opt-in
- Credentials never hardcoded; `.env` and `devices.yaml` are gitignored

## Testing

```bash
pytest tests/ -q   # 187 tests, 12 test files — mock adapter, no real hardware
```

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
- Thanks to UII Jogjakarta :)