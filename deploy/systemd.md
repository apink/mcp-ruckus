# Running under systemd (all-in-one admin GUI)

The admin GUI can edit `.env` and restart the MCP server. For the **Restart**
button to work, the server must run as a systemd unit and the admin GUI's OS
user must be allowed to restart *only* that unit.

Adjust `/opt/mcp-ruckus` and the `mcp` user to your real paths.

> Requires Ubuntu/Debian Linux with systemd, `sudo` access, and Python 3.12+.
>
> This is the recommended **native Linux production** path (auto-restart on
> crash, boot start, journald). Prefer Docker if you use containers; see
> [native.md](native.md) for other OSes.

## 1. Service units

`/etc/systemd/system/mcp-ruckus.service`

```ini
[Unit]
Description=Ruckus MCP Server
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/mcp-ruckus
ExecStart=/opt/mcp-ruckus/venv/bin/python /opt/mcp-ruckus/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/mcp-ruckus-admin.service`

```ini
[Unit]
Description=Ruckus MCP Admin GUI
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/mcp-ruckus
ExecStart=/opt/mcp-ruckus/venv/bin/python /opt/mcp-ruckus/admin.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> Do **not** use `EnvironmentFile=` here. systemd's environment-file parser does
> not strip inline `#` comments the same way the apps do, which corrupts values
> like `MCP_TRANSPORT=streamable-http   # sse`. Both `server.py` and `admin.py`
> load `.env` themselves (and strip inline comments), so the unit only needs
> `WorkingDirectory` + `ExecStart`.

## 2. Allow the admin GUI to restart the MCP unit (no password)

The GUI runs the command in `MCP_RESTART_CMD` directly (no shell, no sudo). By
default that is `systemctl restart mcp-ruckus`, so it needs a polkit rule
granting the **OS user that runs `admin.py`** permission to manage **only**
that unit.

Two things must match your setup:
- `subject.user` → the user running the admin GUI (`mcp` here; change to your user).
- `action.lookup("unit")` → the unit named in `MCP_RESTART_CMD` (`mcp-ruckus.service` here).

`/etc/polkit-1/rules.d/50-mcp-ruckus.rules`

```js
polkit.addRule(function (action, subject) {
    if (action.id === "org.freedesktop.systemd1.manage-units" &&
        subject.user === "mcp" &&
        action.lookup("unit") === "mcp-ruckus.service") {
        return polkit.Result.YES;
    }
});
```

> Alternative: keep `sudo` and change `MCP_RESTART_CMD` is not enough — the GUI
> invokes the command directly with no shell. Prefer the polkit rule above.

## 3. Install

```bash
# Place the code and create the venv
sudo mkdir -p /opt/mcp-ruckus
sudo cp -r . /opt/mcp-ruckus/          # or: git clone <url> /opt/mcp-ruckus
cd /opt/mcp-ruckus
python3 -m venv venv
venv/bin/pip install -e . pytest pytest-asyncio

# Create the service user and hand it the files
sudo useradd --system --home /opt/mcp-ruckus --shell /usr/sbin/nologin mcp
sudo chown -R mcp:mcp /opt/mcp-ruckus

# Configure credentials as the service user
sudo -u mcp cp .env.example .env       # then: sudo -u mcp nano .env

# Install units + polkit rule
sudo cp deploy/mcp-ruckus.service /etc/systemd/system/
sudo cp deploy/mcp-ruckus-admin.service /etc/systemd/system/
sudo cp deploy/50-mcp-ruckus.rules /etc/polkit-1/rules.d/

# Start
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-ruckus mcp-ruckus-admin
```

## 4. Verify

- Open `http://<host>:8001` and log in as `admin`.
- **Config** → edit a setting, **Save settings**, then **Restart MCP server**.
- Check `/config` "MCP server" flips back to RUNNING after the restart.
