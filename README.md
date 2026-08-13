# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

FastMCP-based MCP server untuk infrastruktur Ruckus — wireless (vSZ SmartZone) dan switching (ICX). Menyediakan **81 MCP tools** untuk monitoring AP, analisis traffic client, optimasi RF, manajemen WLAN, manajemen switch, PoE, LLDP, alarm, dan health monitoring. Transport SSE + streamable-http dengan security middleware.

## Features

- **81 MCP tools** (31 vSZ + 41 ICX + 6 inventory + 3 connectivity)
- **vSZ**: AP status/radio/neighbors, RF optimization (DSATUR + Tabu Search), WLAN CRUD, traffic stats, alarm, rogue detection, client tracking, controller health
- **ICX**: device info/status, interfaces, VLAN/LAG, routing (v4+v6), PoE, LLDP, ARP, optic DOM, syslog, TDR diag, SFP, config backup + drift detection, port control, VLAN management
- **Full async** vSZ adapter (httpx.AsyncClient), ICX SSH via Netmiko dengan rate limiting per-device

Daftar lengkap tools: [docs/TOOLS.md](docs/TOOLS.md)

## Quick Start

### Local

```bash
git clone https://github.com/your-org/mcp-ruckus.git
cd mcp-ruckus
cp .env.example .env
# Edit .env dengan kredensial kamu

python3 -m venv venv && source venv/bin/activate
pip install -e .        # atau: pip install -r requirements.txt

# Edit MCP_TRANSPORT di .env (sse / streamable-http)
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
| `MCP_API_KEY` | API key untuk security middleware | - |
| `MCP_ALLOWED_IPS` | Comma-separated allowed IPs | `10.0.0.0/8` |

### Device Inventory

Buat `inventory/devices.yaml` untuk tools ICX. `username`/`password` mendukung `${ENV_VAR}` substitution atau nilai literal:

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

| Doc | Isi |
|---|---|
| [docs/TOOLS.md](docs/TOOLS.md) | Daftar lengkap 81 tools |
| [DOCS_SAFETY.md](DOCS_SAFETY.md) | Safety gates (12 destructive tools) + dry-run preview |
| [SECURITY.md](SECURITY.md) | Security policy, input validation, credential handling |
| [CHANGES.md](CHANGES.md) | Changelog + release notes |
| [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) | Panduan pengembangan |

## Security

- Semua tool destruktif wajib `confirm=True` — tanpa itu return `confirm_required`, tanpa efek
- Tool config ICX mendukung `dry_run=True` untuk preview perintah tanpa eksekusi
- Config backup: metadata-only default (mode `0600`), `include_config=True` opt-in
- Kredensial tidak pernah di-hardcode; `.env` dan `devices.yaml` gitignored

## Testing

```bash
pytest tests/ -q   # 187 tests, 12 test files — mock adapter, tanpa hardware asli
```

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
- Thanks to UII Jogjakarta :)
