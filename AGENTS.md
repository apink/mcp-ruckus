# AGENTS.md

Guidelines for AI coding agents working on this repository.

## Project

FastMCP-based MCP server for Ruckus wireless (vSZ SmartZone) and switching (ICX) infrastructure. **81 MCP tools** (31 vSZ + 41 ICX + 6 inventory + 3 connectivity).

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -e .

# Run server
cp .env.example .env   # then edit credentials
python3 server.py

# Test (mock adapters, no real hardware)
pytest tests/ -q          # 187 tests, 12 files

# Lint
ruff check .
```

## Architecture

```
server.py                    # FastMCP entry (SSE + streamable-http)
├── adapters/
│   ├── vsz.py               # vSZ async REST adapter (httpx.AsyncClient)
│   ├── device_ssh.py        # ICX sync SSH driver (Netmiko)
│   └── config.py            # VsZConfig dataclass
├── tools/                   # MCP tool registrations (one module per domain)
│   ├── vsz_*.py             # vSZ tools (no name prefix)
│   └── icx_device.py        # ICX tools (ruckus_ prefix)
├── models/ruckus.py         # ICXDevice dataclass only
├── inventory/               # device list + manager (devices.yaml gitignored)
├── docs/TOOLS.md            # full tool reference
└── tests/                   # mock-based pytest suite
```

## Conventions

- **Type hints required** on all function signatures
- **snake_case** functions, **PascalCase** classes, **UPPER_SNAKE** constants
- **Regex**: always raw string `r''`, pre-compiled at module level
- **vSZ adapter**: async (`async def` + `await`), session reuse with TTL
- **ICX adapter**: sync (Netmiko not async-native), retry logic inline in `_connect()`
- **Tool naming**: vSZ tools no prefix (`ap_status`); ICX tools `ruckus_` prefix (`ruckus_device_info`)
- **Input validation**: every SSH/URL input validated via `_validate_*()` helpers
- **Error format**: return `{"error": "...", "detail": "..."}`, never raise through tool boundary
- **Destructive tools** require `confirm=True` gate; ICX config tools support `dry_run=True`
- **Test fixtures**: mock-only, never real hardware. Use RFC 5737 TEST-NET IPs (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), IPv6 `2001:db8::/32`, and locally-administered MACs (`aa:bb:cc:*`, `cc:dd:ee:*`). Never commit real/internal IPs, hostnames, or MACs.

## Key Files

| File | Purpose |
|---|---|
| `.github/CONTRIBUTING.md` | Full dev guidelines (security, reliability, code cleanliness) |
| `SKILL.md` | Agent skill workflow (copy to agent skills dir) |
| `docs/TOOLS.md` | Complete 81-tool reference |
| `DOCS_SAFETY.md` | Destructive tools + dry-run gates |
| `SECURITY.md` | Security policy |
