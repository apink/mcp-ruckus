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

The server speaks **MCP** (Model Context Protocol), the standard way AI tools talk to external programs. It exposes **90 tools** for monitoring and managing Ruckus wireless and switching gear.

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
- **Switches (ICX)** — 50 tools: device info/status, interfaces, VLANs, routing (IPv4 + IPv6, incl. static route add/delete), PoE, LLDP neighbors, ARP, fiber optic health, syslog, cable diagnostics, SFP, config backup + drift detection, port/VLAN changes, time/NTP configuration (timezone, clock set, NTP servers), and config save.
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

> Prefer a guided, step-by-step walkthrough — including logging into the admin
> GUI and creating your first API key? See [docs/QUICKSTART.md](docs/QUICKSTART.md).

### Prepare your config files

```bash
git clone https://github.com/apink/mcp-ruckus.git
cd mcp-ruckus

cp .env.example .env
cp inventory/devices.example.yaml inventory/devices.yaml   # only needed for ICX switch tools
```

Edit `.env`:

| Key | What to set |
|---|---|
| `VSZ_HOST` / `VSZ_PORT` / `VSZ_USER` / `VSZ_PASS` (or `VSZ_API_TOKEN`) | Your controller address + login |
| `MCP_API_KEY` | **Required** — the AI sends this as a Bearer token |
| `MCP_ADMIN_INIT_PASS` | Initial admin GUI password (default `digantiYA_30`; you're forced to change it on first login) |

Then edit `inventory/devices.yaml` with your switches if you use ICX.

> The MCP endpoint **requires an API key** (fail-closed). Simplest path: set
> `MCP_API_KEY` in `.env` and send it as a Bearer token (see
> [Connect your AI assistant](#connect-your-ai-assistant)), or create a per-client
> key in the admin GUI. Without a key, tool calls return `401 Unauthorized`.

The MCP server listens on `0.0.0.0:8000` and serves Streamable HTTP at
`http://{SERVER_IP}:8000/mcp` (SSE is also available at `/sse` if you set
`MCP_TRANSPORT=sse`).

Three ways to run it, in order of preference:

### Production (recommended) — Docker

```bash
docker compose up -d --build
```

This starts both processes:
- MCP server → `http://{SERVER_IP}:8000/mcp`
- Admin web UI → `http://{SERVER_IP}:8001` (keys, users, inventory, audit)

> In Docker, `.env` is mounted read-only. To change settings, edit `.env` on the
> host and run `docker compose restart`. The GUI's **Config** editor and
> **Restart** button target the non-Docker deployments (systemd/native) and are
> not used inside Docker.

### Native Linux production — systemd

For Ubuntu/Debian without Docker, run under systemd: automatic restart on
crash, boot start, journald logging, and a GUI **Restart MCP** button that works
without a password (polkit rule). The button runs whatever `MCP_RESTART_CMD`
says (default `systemctl restart mcp-ruckus`). Full setup — unit files, polkit
rule, and commands — is in [deploy/systemd.md](deploy/systemd.md).

```bash
sudo systemctl enable --now mcp-ruckus        # MCP server
sudo systemctl enable --now mcp-ruckus-admin  # admin GUI (optional)
```

### Any other OS — native launcher (`run.py`)

For macOS, Windows, or Linux without systemd, use the bundled cross-platform
launcher. This is a **simple launcher** — it has no automatic restart on crash
— so use it for home/lab or single-host setups; prefer Docker or systemd for
production:

```bash
python run.py start      # launches MCP server + admin GUI in the background
python run.py status
```

Point the GUI's restart button at it by setting
`MCP_RESTART_CMD=python run.py restart` in `.env`. See
[deploy/native.md](deploy/native.md) for launchd (macOS), Task Scheduler
(Windows), and cron (Linux).

> For local development (running `python3 server.py` / `python3 admin.py`
> directly), see [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Connect your AI assistant

Now that the server is running, your next step is to introduce it to your AI assistant (Hermes, OpenClaw, Claude Code, etc.). Once connected, the 90 tools will show up inside the assistant and you can use them just by asking.

> Replace `{SERVER_IP}` with the IP or hostname of the machine running the server. If the assistant runs on the same computer, you can use `localhost`.

### Pick a transport

| Transport | Endpoint | When to use |
|---|---|---|
| Streamable HTTP (default) | `http://{SERVER_IP}:8000/mcp` | Recommended — works everywhere, incl. production/remote |
| SSE | `http://{SERVER_IP}:8000/sse` | Alternative for older agents or local setups |

Streamable HTTP is the default. SSE also works — if your agent prefers it, just use the `/sse` endpoint and set the transport to `sse`.

### Hermes

For Hermes, open `~/.hermes/config.yaml` and add a `mcp_servers` block. Send the
API key as a Bearer header (the `Bearer ` prefix is required):

```yaml
mcp_servers:
  ruckus:
    url: http://{SERVER_IP}:8000/mcp
    transport: streamable-http
    timeout: 120
    connect_timeout: 15
    headers:
      Authorization: "Bearer ruck_YOUR_KEY"
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

### Send your API key (required)

The MCP endpoint requires a Bearer token on every request. Send the key you
created — either `MCP_API_KEY` from `.env`, or a per-client key from the admin
GUI — as an `Authorization` header. Example for Claude Code:

```bash
claude mcp add --transport http ruckus http://{SERVER_IP}:8000/mcp \
  --header "Authorization: Bearer YOUR_KEY"
```

For the JSON configs above, add a `headers` field:

```json
"headers": { "Authorization": "Bearer YOUR_KEY" }
```

## Configuration

All settings live in a `.env` file (copy of `.env.example`) and, for switches, an inventory file.

### Environment variables

| Variable | What it does | Example |
|---|---|---|
| `VSZ_HOST` | IP address of your vSZ/SmartZone controller | `192.0.2.10` |
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
| `MCP_API_KEY` | Fallback single key the AI must send as a Bearer token (see per-client keys below) | - |
| `MCP_ALLOWED_IPS` | Optional whitelist of IPs allowed to connect | `192.0.2.0/24` |
| `MCP_DB_PATH` | Where the SQLite DB lives (users, API keys, audit trail) | `./data/admin.db` |
| `MCP_AUDIT_RETENTION_DAYS` | How long to keep audit events before rotation (`0` = keep forever) | `90` |
| `MCP_ADMIN_HOST` | Address the admin web UI listens on (`127.0.0.1` = localhost only) | `127.0.0.1` |
| `MCP_ADMIN_PORT` | Port the admin web UI listens on | `8001` |
| `MCP_ADMIN_USER` | Default superadmin username (first boot only) | `admin` |
| `MCP_ADMIN_INIT_PASS` | Initial superadmin password (first boot only; defaults to `digantiYA_30`, change on first login) | `digantiYA_30` |
| `MCP_RESTART_CMD` | Command the admin GUI runs on **Restart MCP** (split like a shell command, no shell) | `systemctl restart mcp-ruckus` |

> Don't worry about most of these. The minimum is `VSZ_HOST`, `VSZ_PORT`, and `VSZ_USER`/`VSZ_PASS` (or `VSZ_API_TOKEN`) — plus `MCP_API_KEY` (or a per-client key), because the endpoint requires authentication.

### Device inventory (ICX switches)

If you also manage switches, create `inventory/devices.yaml` (copy `inventory/devices.example.yaml` to start). Each switch needs its IP and login. Logins can be written directly or pulled from environment variables with `${VAR_NAME}`:

```yaml
devices:
  - host: "192.0.2.10"
    name: "switch-core-01"
    vendor: "ruckus"
    role: "core"
    location: "datacenter"
    username: "${ICX_CORE_USER}"
    password: "${ICX_CORE_PASS}"

  - host: "198.51.100.20"
    name: "sw-branch"
    username: "${ICX_BRANCH_USER}"
    password: "${ICX_BRANCH_PASS}"
```

> You can also add, edit, and delete devices from the admin web UI's
> **Inventory** page instead of editing this file by hand — both write to the
> same `inventory/devices.yaml` and changes apply live. The GUI accepts either a
> literal password or a `${VAR_NAME}` reference, exactly like the examples above.

## Admin web UI

The admin GUI is a **separate process** from the MCP server, so it stays up even when the server is down:

```bash
python3 admin.py        # http://localhost:8001  (default)
```

| Page | What it does |
|---|---|
| Dashboard | MCP server status (via `/health`), tool/API-key/user/audit counts, DB size |
| API Keys | Create / edit / regenerate / delete per-client keys |
| Inventory | Add / edit / delete devices in `inventory/devices.yaml` (applies live) |
| Audit | Browse and filter the tool-call audit trail |
| Config | (superadmin) edit `.env` settings, set/rotate secrets (write-only), restart the MCP server |
| Users | (superadmin) manage admin accounts and roles |

On first boot it creates a default `admin` superadmin with password `digantiYA_30` (or whatever you set in `MCP_ADMIN_INIT_PASS`); you're forced to change it on first login. Roles are `superadmin`, `operator`, and `viewer`.

> The admin GUI does **not** start/stop the MCP process itself. The **Config** page
> can restart it by running `MCP_RESTART_CMD` (superadmin only) — see
> [deploy/systemd.md](deploy/systemd.md) or [deploy/native.md](deploy/native.md).
> Otherwise restarting stays manual (Docker); the GUI just reports status.

## Per-client API keys + audit trail

Instead of one shared `MCP_API_KEY`, you can give **each AI assistant its own key** with its own scope. Keys live in SQLite and are managed through the **admin web UI** (see above):

- **API Keys** page — create a key with a `name` (recorded in the audit log), a `Scope` choice (**Selected tools** or **All tools**), and an `allow_destructive` toggle (default off, blocks the 22 destructive tools). New keys default to **Selected tools** with the read-only **Most used tools** set pre-filled.
- **Most used tools preset** — one click scopes a key to the curated read-only `lean.LEAN_TOOLS` set (~17 of 90 tools), ideal for AI assistants that only need search/status/summary.
- The `tools/list` response is filtered to the key's scope too — a scoped key only receives the schemas for the tools it may call, cutting token/context overhead (not just blocking calls).
- Keys take effect **immediately** — the MCP server resolves them live, no restart needed.
- `MCP_API_KEY` still works as a fallback (treated as an unrestricted `"default"` client).

Every tool call is recorded to the SQLite audit log (client name, tool, redacted arguments, outcome, duration) — view and filter it in the admin UI's **Audit** page. Audit events are rotated automatically: events older than `MCP_AUDIT_RETENTION_DAYS` (default `90`) are pruned on startup and periodically while the server runs.

## Safety features

- The MCP endpoint requires a Bearer API key by default (fail-closed) — no open access.
- Tools that change things require `confirm=True` — without it they refuse and do nothing.
- Switch config changes support `dry_run=True`, so you can preview the command before it runs.
- Config backups store metadata only by default; including the actual config is opt-in.
- No real controller/device passwords are stored in the repo; the admin GUI ships a default initial password (`digantiYA_30`) you must change on first login. `.env`, `devices.yaml`, and `data/` are gitignored.
- Each client can have its own API key with an `allowed_tools` allowlist and a destructive-tool gate.
- Every tool call is recorded to the SQLite audit log (client, tool, redacted args, outcome, duration).

## Development

Contributing, coding guidelines, and how to run the test suite are in [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

To quickly check that the server starts and responds:

- Start the server: `python3 server.py`
- Register it in your agent (see [Connect your AI assistant](#connect-your-ai-assistant)) and try a tool, or
- Open the [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) with `npx @modelcontextprotocol/inspector` (requires Node.js)

## More docs

| Doc | Content |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Step-by-step first run: login, API key, connect agent, verify |
| [docs/TOOLS.md](docs/TOOLS.md) | Complete list of 90 tools |
| [DOCS_SAFETY.md](DOCS_SAFETY.md) | Safety gates (22 destructive tools) + dry-run preview |
| [SECURITY.md](SECURITY.md) | Security policy, input validation, credential handling |
| [CHANGES.md](CHANGES.md) | Changelog + release notes |
| [SKILL.md](SKILL.md) | AI agent skill (copy to your agent's skills dir) |
| [deploy/systemd.md](deploy/systemd.md) | systemd deployment (units, polkit rule, GUI restart) |
| [deploy/native.md](deploy/native.md) | cross-platform `run.py` launcher + macOS/Windows/Linux boot setup |

## License

MIT License — see [LICENSE](LICENSE).

## Credits

- Ruckus Networks (vSZ, ICX)
- FastMCP 3.4.2
- Netmiko (ICX SSH)
- Thanks to UII :)
