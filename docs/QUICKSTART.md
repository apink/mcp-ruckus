# Quick start (step by step)

This is the guided first-run walkthrough. It takes you from a fresh checkout to
your first working tool call: start the server, log into the admin web UI,
create an API key, connect your AI assistant, and verify the whole chain.

The MCP endpoint **requires a Bearer API key** (fail-closed) — there is no
open access. That key is the thread that runs through every step below.

## 0. Prerequisites

- A machine that can reach your Ruckus gear (vSZ controller and/or ICX switches).
- A `.env` file (copy of `.env.example`) with at least:
  - `VSZ_HOST` / `VSZ_PORT` / `VSZ_USER` / `VSZ_PASS` (or `VSZ_API_TOKEN`), and/or
  - `inventory/devices.yaml` (copy of `devices.example.yaml`) for ICX switches.
- Depending on how you run it:
  - **Docker** — Docker + Docker Compose installed.
  - **systemd** — Ubuntu/Debian with systemd, `sudo` access, and Python 3.12+.
  - **local/dev** — Python 3.12+ only.

```bash
python3 --version      # must print 3.12 or newer (skip this for Docker)
cp .env.example .env   # then edit credentials
```

## 1. Start the server + admin GUI

The MCP server (`server.py`, port 8000) and the admin GUI (`admin.py`, port
8001) are **separate processes** — you can run the server alone and skip the
GUI if you use `MCP_API_KEY` (see [Alternative: skip the GUI](#alternative-skip-the-gui)).

> In the URLs below, replace `{SERVER_IP}` with the IP or hostname of the
> machine running the server. If the assistant (and your browser) runs on that
> same machine, use `localhost` instead.

**Option A — Docker** (starts both):

```bash
docker compose up -d --build
# MCP server  → http://{SERVER_IP}:8000/mcp
# Admin GUI   → http://{SERVER_IP}:8001
```

> In Docker, `.env` is mounted read-only — edit it on the host, then
> `docker compose restart`. The GUI's **Config** editor and **Restart** button
> target systemd and are not used inside Docker.

**Option B — systemd** (production; enables the GUI **Restart MCP** button):

Requires Ubuntu/Debian with systemd, `sudo`, and Python 3.12+ (see
[Prerequisites](#0-prerequisites)). The shipped units assume the code lives at
`/opt/mcp-ruckus` and run as a dedicated `mcp` user. If you use different
paths/users, edit `deploy/mcp-ruckus.service`, `deploy/mcp-ruckus-admin.service`,
and `deploy/50-mcp-ruckus.rules` to match, then run:

```bash
# 1. Place the code and create the venv
sudo mkdir -p /opt/mcp-ruckus
sudo cp -r . /opt/mcp-ruckus/          # or: git clone <url> /opt/mcp-ruckus
cd /opt/mcp-ruckus
python3 -m venv venv
venv/bin/pip install -e . pytest pytest-asyncio

# 2. Create the dedicated OS user and hand it the files
sudo useradd --system --home /opt/mcp-ruckus --shell /usr/sbin/nologin mcp
sudo chown -R mcp:mcp /opt/mcp-ruckus

# 3. Configure credentials as the service user
sudo -u mcp cp .env.example .env       # then: sudo -u mcp nano .env

# 4. Install units + polkit rule and start
sudo cp deploy/mcp-ruckus.service /etc/systemd/system/
sudo cp deploy/mcp-ruckus-admin.service /etc/systemd/system/
sudo cp deploy/50-mcp-ruckus.rules /etc/polkit-1/rules.d/

sudo systemctl daemon-reload
sudo systemctl enable --now mcp-ruckus        # MCP server
sudo systemctl enable --now mcp-ruckus-admin  # admin GUI (optional)
```

Full unit contents, the `mcp` user setup, and the polkit rule are in
[deploy/systemd.md](../deploy/systemd.md).

> For a quick **local/dev** run without root:
> `python3 -m venv venv && source venv/bin/activate && pip install -e .`,
> then `python3 server.py` and `python3 admin.py` in separate terminals.

## 2. Log into the admin GUI

Open `http://{SERVER_IP}:8001` in a browser.

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `digantiYA_30` (or the value of `MCP_ADMIN_INIT_PASS`) |

On first login you are **forced to change the password** — the initial one is
only a bootstrap. Roles are:

| Role | What it can do |
|---|---|
| `superadmin` | Everything, incl. users, config editor, and restart |
| `operator` | Manage keys, inventory, and audit |
| `viewer` | Read-only |

## 3. Create an API key

1. Click **API Keys** in the sidebar.
2. Click **Create key** and fill in:
   - **Name** — a label recorded against every tool call in the audit log
     (e.g. `hermes`, `ops-team`).
   - **Allowed tools** — leave empty to allow all 90 tools, or tick a subset.
   - **Allow destructive** — leave off (default); blocks the 22 destructive tools.
3. Submit. The generated key (`ruck_…`) is **shown once — copy it now**. If you
   lose it, regenerate and copy again (the old value is replaced immediately).

## 4. Connect your AI assistant

Add the server as an MCP server, sending the key as a Bearer header.

### Hermes

Edit `~/.hermes/config.yaml`:

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

> The `Bearer ` prefix is **required** — sending the bare key returns
> `401 Unauthorized: missing Bearer token`.

Then restart the gateway: `systemctl --user restart hermes-gateway` (or however
you run Hermes).

### OpenClaw

```bash
openclaw mcp add ruckus --url http://{SERVER_IP}:8000/mcp --transport streamable-http
```

Then add the header in `~/.openclaw/openclaw.json`:

```json5
{
  mcp: {
    servers: {
      ruckus: {
        url: "http://{SERVER_IP}:8000/mcp",
        transport: "streamable-http",
        headers: { "Authorization": "Bearer ruck_YOUR_KEY" }
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http ruckus http://{SERVER_IP}:8000/mcp \
  --header "Authorization: Bearer ruck_YOUR_KEY"
```

**Transport:** `streamable-http` at `/mcp` is the default. For SSE, use the
`/sse` URL with `MCP_TRANSPORT=sse` on the server and `transport: sse` in the
agent.

## 5. Verify it works

```bash
# 1. Server alive (no auth needed)
curl -s http://{SERVER_IP}:8000/health

# 2. Auth is enforced (should print 401)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://{SERVER_IP}:8000/mcp

# 3. Your key is accepted (anything except 401 means auth passed)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://{SERVER_IP}:8000/mcp \
  -H "Authorization: Bearer ruck_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Step 3 returning `400`/`405` (or `200`) is fine — it just means the key passed
and the empty body wasn't a valid MCP message. A `401` means the header is
wrong.

Finally, ask your assistant something simple, e.g. *"Which access point has the
most clients right now?"* — the first successful call shows up in the admin
GUI's **Audit** page.

## Alternative: skip the GUI

If you don't want per-client keys, set a single shared key in `.env`:

```
MCP_API_KEY=some-secret-token
```

and send it the same way (`Authorization: Bearer some-secret-token`). This
client is recorded in the audit log as `default` and has no per-tool scope.
Per-client keys are managed directly in SQLite (`data/admin.db`, table
`api_keys`) if you prefer the command line.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 missing Bearer token` | Header lacks the `Bearer ` prefix, or no header at all | Use `Authorization: Bearer <key>` |
| `401 invalid API key` | Key doesn't match the one in the DB | Regenerate in the GUI and re-copy |
| `401 no API keys configured` | No key and no `MCP_API_KEY` | Create a key or set `MCP_API_KEY` |
| `403 IP not allowed` | `MCP_ALLOWED_IPS` excludes the client | Fix the CIDR allowlist in `.env` |
| Connection refused | Server not running / wrong port | Check `systemctl status mcp-ruckus`, `docker compose ps`, or `python3 server.py` (dev), and `MCP_PORT` |
| Tools listed but calls fail | `sse` vs `streamable-http` mismatch | Match the URL + `transport` on both sides |

## Going further

- [README](../README.md) — overview, config reference, safety features
- [docs/TOOLS.md](TOOLS.md) — the complete 90-tool reference
- [deploy/systemd.md](../deploy/systemd.md) — systemd units + GUI "Restart MCP"
- [SECURITY.md](../SECURITY.md) — security policy and credential handling
