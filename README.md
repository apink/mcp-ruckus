# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

## What is this?

This is a small program that lets your **AI assistant** (Claude Code, Hermes, OpenClaw) talk to your **Ruckus network equipment** using plain language.

Normally, managing WiFi and switches means logging into each device and typing technical commands. With this server, you just ask the assistant things like:

- "Which access point has the most clients right now?"
- "Is port 1/1/5 on the core switch delivering power?"
- "Back up the config of every switch."
- "Show me the neighbors of switch X."

The assistant understands the question, calls the right tool behind the scenes, and shows you a plain answer.

How it works, in one picture:

```
You (plain English)  →  AI assistant  →  this server (MCP)  →  your Ruckus gear
```

The server speaks **MCP** (Model Context Protocol), the standard way AI tools talk to external programs. It exposes **81 tools** for monitoring and managing Ruckus wireless and switching gear.

### Jargon, in plain words

| Term | What it actually means |
|---|---|
| **vSZ / SmartZone** | The "controller" — the box that manages all your Ruckus WiFi access points in one place. |
| **ICX** | Ruckus's line of network **switches** — the boxes your computers plug into with a cable. |
| **AP (access point)** | The WiFi device that laptops/phones connect to wirelessly. |
| **PoE** | Power over Ethernet — the switch sends electricity through the network cable, so APs and cameras need no separate power plug. |
| **VLAN** | Virtual LAN — splitting one physical network into separate, isolated networks. |
| **LLDP** | A protocol where devices announce themselves, so you can see "what is plugged into what". |
| **RF** | Radio frequency — the WiFi signal itself. |
| **WLAN** | A wireless network (the thing with an SSID name). |
| **ARP** | The table that maps IP addresses to hardware (MAC) addresses. |
| **SFP / optic DOM** | Fiber-optic transceiver and its health readings (temperature, light levels). |
| **TDR** | Cable diagnostics — a built-in "cable tester" for finding wiring faults. |
| **SSH / REST API** | Two standard ways for programs to talk to network devices. |

## What can it do?

- **WiFi (vSZ)** — 31 tools: see AP status, radios, and neighbors; count clients per AP; optimize RF channels automatically; manage WLANs; traffic stats; alarms; rogue-AP detection; track clients; controller health.
- **Switches (ICX)** — 41 tools: device info/status, interfaces, VLANs, routing (IPv4 + IPv6), PoE, LLDP neighbors, ARP, fiber optic health, syslog, cable diagnostics, SFP, config backup + drift detection, and port/VLAN changes.
- **Inventory** — 6 tools to list and manage the devices you've registered.
- **Connectivity** — 3 tools to quickly check reachability.

Full list: [docs/TOOLS.md](docs/TOOLS.md)

## Before you start

You need:

1. **A computer** that can reach your Ruckus gear over the network.
2. **Python 3.12+** (or Docker, if you prefer containers).
3. **Login details** for at least one of:
   - a vSZ/SmartZone controller (its IP, username, password or API token), and/or
   - ICX switches (their IPs and SSH usernames/passwords).

You don't need to be a network expert — if you have the IPs and credentials, this README covers the rest.

## Quick start

### Option A — run locally (Python)

```bash
# 1. Get the code
git clone https://github.com/your-org/mcp-ruckus.git
cd mcp-ruckus

# 2. Create your config files from the templates
cp .env.example .env
cp inventory/devices.example.yaml inventory/devices.yaml   # only needed for ICX switch tools

# 3. Edit .env with your controller IP + credentials
#    Edit inventory/devices.yaml with your switches (if you have ICX)

# 4. Install
python3 -m venv venv && source venv/bin/activate
pip install -e .

# 5. Run
python3 server.py
```

When it starts, the server listens on `0.0.0.0:8000` and serves SSE at `http://localhost:8000/sse`.

### Option B — run with Docker

```bash
docker build -t ruckus-mcp:latest .
docker compose up -d
```

## Configuration

All settings live in a `.env` file (copy of `.env.example`) and, for switches, an inventory file.

### Environment variables

| Variable | What it does | Example |
|---|---|---|
| `VSZ_HOST` | IP address of your vSZ/SmartZone controller | `10.0.0.1` |
| `VSZ_PORT` | HTTPS port of the controller | `8443` |
| `VSZ_USER` / `VSZ_PASS` | Controller login | - |
| `VSZ_API_TOKEN` | API token (optional, instead of user/pass) | - |
| `VSZ_API_VERSION` | Controller API version | `v11_1` |
| `VSZ_RATE_LIMIT` | Max simultaneous API calls | `10` |
| `ICX_RATE_LIMIT` | Max simultaneous SSH sessions per switch | `5` |
| `MCP_TRANSPORT` | How the server talks to the AI: `sse` or `streamable-http` | `sse` |
| `MCP_HOST` | Which network address to listen on (`0.0.0.0` = all) | `0.0.0.0` |
| `MCP_PORT` | Which port the server listens on | `8000` |
| `LOG_LEVEL` | How much logging you want | `INFO` |
| `MCP_API_KEY` | Optional password the AI must send to connect | - |
| `MCP_ALLOWED_IPS` | Optional whitelist of IPs allowed to connect | `10.0.0.0/8` |

> Don't worry about most of these. The minimum is `VSZ_HOST`, `VSZ_PORT`, and `VSZ_USER`/`VSZ_PASS` (or `VSZ_API_TOKEN`).

### Device inventory (ICX switches)

If you also manage switches, create `inventory/devices.yaml` (copy `inventory/devices.example.yaml` to start). Each switch needs its IP and login. Logins can be written directly or pulled from environment variables with `${VAR_NAME}`:

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

## Connect your AI assistant

Once the server is running, point your AI assistant at it. That's how the 81 tools appear inside the agent.

Two endpoints, pick one:

| Transport | Endpoint | When to use |
|---|---|---|
| SSE | `http://localhost:8000/sse` | Simple, local setup |
| Streamable HTTP | `http://localhost:8000/mcp` | Production / remote server |

> If the agent runs on a different machine, replace `localhost` with the server's IP or hostname.

### Hermes

Add a `mcp_servers` block to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  ruckus:
    url: http://localhost:8000/sse
    transport: sse
    timeout: 120
    connect_timeout: 15
```

### OpenClaw

Easiest via CLI:

```bash
openclaw mcp add ruckus --url http://localhost:8000/sse --transport sse
```

or drop it into `~/.openclaw/openclaw.json`:

```json5
{
  mcp: {
    servers: {
      ruckus: {
        url: "http://localhost:8000/sse",
        transport: "sse",
        enabled: true
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport sse ruckus http://localhost:8000/sse
```

or a project-scoped `.mcp.json` (shareable via git):

```json
{
  "mcpServers": {
    "ruckus": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### If you set `MCP_API_KEY`

Pass it as a Bearer header. Example for Claude Code:

```bash
claude mcp add --transport sse ruckus http://localhost:8000/sse \
  --header "Authorization: Bearer YOUR_KEY"
```

For the JSON configs above, add a `headers` field:

```json
"headers": { "Authorization": "Bearer YOUR_KEY" }
```

## Safety features

- Tools that change things require `confirm=True` — without it they refuse and do nothing.
- Switch config changes support `dry_run=True`, so you can preview the command before it runs.
- Config backups store metadata only by default; including the actual config is opt-in.
- Passwords are never hardcoded in the repo; `.env` and `devices.yaml` are gitignored.

## Tests

```bash
pytest tests/ -q   # 187 unit tests, 12 files
```

These are **unit tests** for the tools and adapters. They run against mock vSZ/ICX adapters — no real hardware and no live MCP client. They cover tool logic (input validation, command building, output parsing), not the end-to-end MCP connection to an agent.

To smoke-test a real connection, start the server and either:

- register it in your agent (see [Connect your AI assistant](#connect-your-ai-assistant)), or
- open the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) with `npx @modelcontextprotocol/inspector`

## More docs

| Doc | Content |
|---|---|
| [docs/TOOLS.md](docs/TOOLS.md) | Complete list of 81 tools |
| [DOCS_SAFETY.md](DOCS_SAFETY.md) | Safety gates (12 destructive tools) + dry-run preview |
| [SECURITY.md](SECURITY.md) | Security policy, input validation, credential handling |
| [CHANGES.md](CHANGES.md) | Changelog + release notes |
| [SKILL.md](SKILL.md) | AI agent skill (copy to your agent's skills dir) |
| [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) | Development guidelines |

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
- Thanks to UII Jogjakarta :)
