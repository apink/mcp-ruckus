# Quick start (step by step)

This is the guided first-run walkthrough. It takes you from a fresh checkout to
your first working tool call: start the server, log into the admin web UI,
create an API key, connect your AI assistant, and verify the whole chain.

The MCP endpoint **requires a Bearer API key** (fail-closed) — there is no
open access. That key is the thread that runs through every step below.

## 0. Prerequisites

- A machine that can reach your Ruckus gear (vSZ controller and/or ICX switches).
- Python 3.12+, or Docker.
- A `.env` file (copy of `.env.example`) with at least:
  - `VSZ_HOST` / `VSZ_PORT` / `VSZ_USER` / `VSZ_PASS` (or `VSZ_API_TOKEN`), and/or
  - `inventory/devices.yaml` (copy of `devices.example.yaml`) for ICX switches.

```bash
cp .env.example .env     # then edit credentials
```

## 1. Start the server + admin GUI

The MCP server (`server.py`, port 8000) and the admin GUI (`admin.py`, port
8001) are **separate processes** — you can run the server alone and skip the
GUI if you use `MCP_API_KEY` (see [Alternative: skip the GUI](#alternative-skip-the-gui)).

**Option A — Docker** (starts both):

```bash
docker compose up -d --build
# MCP server  → http://localhost:8000/mcp
# Admin GUI   → http://localhost:8001
```

> In Docker, `.env` is mounted read-only — edit it on the host, then
> `docker compose restart`. The GUI's **Config** editor and **Restart** button
> target systemd and are not used inside Docker.

**Option B — systemd** (production; enables the GUI **Restart MCP** button):

1. Put the code at a fixed path (the units assume `/opt/mcp-ruckus`), create a
   venv, and create a dedicated OS user (`mcp`). Adjust paths/user in the unit
   files and polkit rule if yours differ.
2. Install the units and polkit rule, then start them:

```bash
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

Open `http://localhost:8001` in a browser.

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
    url: http://localhost:8000/mcp
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
openclaw mcp add ruckus --url http://localhost:8000/mcp --transport streamable-http
```

Then add the header in `~/.openclaw/openclaw.json`:

```json5
{
  mcp: {
    servers: {
      ruckus: {
        url: "http://localhost:8000/mcp",
        transport: "streamable-http",
        headers: { "Authorization": "Bearer ruck_YOUR_KEY" }
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http ruckus http://localhost:8000/mcp \
  --header "Authorization: Bearer ruck_YOUR_KEY"
```

**Transport:** `streamable-http` at `/mcp` is the default. For SSE, use the
`/sse` URL with `MCP_TRANSPORT=sse` on the server and `transport: sse` in the
agent.

## 5. Verify it works

```bash
# 1. Server alive (no auth needed)
curl -s http://localhost:8000/health

# 2. Auth is enforced (should print 401)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/mcp

# 3. Your key is accepted (anything except 401 means auth passed)
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/mcp \
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
