# Ruckus MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.4.2-orange.svg)](https://gofastmcp.com)

## What is this?

This is a small program that lets your **AI assistant** (Claude Code, Hermes, OpenClaw etc) talk to your **Ruckus network equipment** using plain language.

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

The server speaks **MCP** (Model Context Protocol), the standard way AI tools talk to external programs. It exposes **85 tools** for monitoring and managing Ruckus wireless and switching gear.

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
- **Switches (ICX)** — 42 tools: device info/status, interfaces, VLANs, routing (IPv4 + IPv6, incl. static route add/delete), PoE, LLDP neighbors, ARP, fiber optic health, syslog, cable diagnostics, SFP, config backup + drift detection, and port/VLAN changes.
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
git clone https://github.com/apink/mcp-ruckus.git
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

When it starts, the server listens on `0.0.0.0:8000` and serves Streamable HTTP at `http://{SERVER_IP}:8000/mcp` (use `localhost` for the same machine; SSE is also available at `/sse` if you set `MCP_TRANSPORT=sse`).

### Option B — run with Docker

Create your config files first (same as Option A, step 2):

```bash
cp .env.example .env
cp inventory/devices.example.yaml inventory/devices.yaml   # only needed for ICX switch tools
```

Then build and start the container:

```bash
docker compose up -d --build
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
| `MCP_TRANSPORT` | How the server talks to the AI: `streamable-http` (default) or `sse` | `streamable-http` |
| `MCP_HOST` | Which network address to listen on (`0.0.0.0` = all) | `0.0.0.0` |
| `MCP_PORT` | Which port the server listens on | `8000` |
| `LOG_LEVEL` | How much logging you want (`DEBUG` also shows framework/SSH/access noise) | `INFO` |
| `MCP_MAX_ITEMS` | Hard cap on list length returned by list tools | `50` |
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

Now that the server is running, your next step is to introduce it to your AI assistant (Hermes, OpenClaw, Claude Code, etc.). Once connected, the 85 tools will show up inside the assistant and you can use them just by asking.

> Replace `{SERVER_IP}` with the IP or hostname of the machine running the server. If the assistant runs on the same computer, you can use `localhost`.

### Pick a transport

| Transport | Endpoint | When to use |
|---|---|---|
| Streamable HTTP (default) | `http://{SERVER_IP}:8000/mcp` | Recommended — works everywhere, incl. production/remote |
| SSE | `http://{SERVER_IP}:8000/sse` | Alternative for older agents or local setups |

Streamable HTTP is the default. SSE also works — if your agent prefers it, just use the `/sse` endpoint and set the transport to `sse`.

### Hermes

For Hermes, open `~/.hermes/config.yaml` and add a `mcp_servers` block:

```yaml
mcp_servers:
  ruckus:
    url: http://{SERVER_IP}:8000/mcp
    transport: streamable-http
    timeout: 120
    connect_timeout: 15
```

Using SSE instead? Point `url` to `http://{SERVER_IP}:8000/sse` and set `transport: sse`.

### OpenClaw

The quickest way — just run this command:

```bash
openclaw mcp add ruckus --url http://{SERVER_IP}:8000/mcp --transport streamable-http
```

Or, if you prefer editing files, drop it into `~/.openclaw/openclaw.json`:

```json5
{
  mcp: {
    servers: {
      ruckus: {
        url: "http://{SERVER_IP}:8000/mcp",
        transport: "streamable-http",
        enabled: true
      }
    }
  }
}
```

Using SSE instead? Swap the URL to `http://{SERVER_IP}:8000/sse` and set `transport: "sse"`.

### Claude Code

Run this from your project folder:

```bash
claude mcp add --transport http ruckus http://{SERVER_IP}:8000/mcp
```

Or use a project-scoped `.mcp.json` (shareable via git):

```json
{
  "mcpServers": {
    "ruckus": {
      "type": "http",
      "url": "http://{SERVER_IP}:8000/mcp"
    }
  }
}
```

Using SSE instead? Use `--transport sse` with the `/sse` URL (and `"type": "sse"` in `.mcp.json`).

### If you set `MCP_API_KEY`

If you enabled `MCP_API_KEY`, the assistant must send it as a Bearer header. Example for Claude Code:

```bash
claude mcp add --transport http ruckus http://{SERVER_IP}:8000/mcp \
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

## Development

Contributing, coding guidelines, and how to run the test suite are in [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

To quickly check that the server starts and responds:

- Start the server: `python3 server.py`
- Register it in your agent (see [Connect your AI assistant](#connect-your-ai-assistant)) and try a tool, or
- Open the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) with `npx @modelcontextprotocol/inspector` (requires Node.js)

## More docs

| Doc | Content |
|---|---|
| [docs/TOOLS.md](docs/TOOLS.md) | Complete list of 85 tools |
| [DOCS_SAFETY.md](DOCS_SAFETY.md) | Safety gates (17 destructive tools) + dry-run preview |
| [SECURITY.md](SECURITY.md) | Security policy, input validation, credential handling |
| [CHANGES.md](CHANGES.md) | Changelog + release notes |
| [SKILL.md](SKILL.md) | AI agent skill (copy to your agent's skills dir) |

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
- Thanks to UII Jogjakarta :)
