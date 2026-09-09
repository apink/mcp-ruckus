# Running natively on any OS (no systemd, no Docker)

For Linux without systemd, macOS, or Windows, use the bundled cross-platform
launcher `run.py`. It starts both `server.py` (MCP) and `admin.py` (GUI) in the
background using only the Python standard library, and records their PIDs so
`stop`/`status` work anywhere.

```bash
python run.py start      # launch MCP server + admin GUI
python run.py status     # show RUNNING/STOPPED for each process
python run.py restart    # stop, then start
python run.py stop       # stop both
```

- Logs: `logs/server.log`, `logs/admin.log`
- PID files: `data/server.pid`, `data/admin.pid` (both gitignored)
- Use `python` / `python3` / the absolute venv path that has the deps installed.

> `run.py` launches the processes as children of your shell. They keep running
> after you log out only if you register `run.py start` as a boot service (below).

## Make the GUI "Restart MCP" button work natively

Set `MCP_RESTART_CMD` in `.env` to the exact command you'd run:

```dotenv
MCP_RESTART_CMD=python run.py restart
```

Use an absolute interpreter path if `python` isn't on the service account's
`PATH` (e.g. `/opt/mcp-ruckus/venv/bin/python run.py restart`).

## Start on boot

### macOS — launchd

Create `~/Library/LaunchAgents/com.mcp-ruckus.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcp-ruckus</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOU/mcp-ruckus/run.py</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOU/mcp-ruckus</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.mcp-ruckus.plist
```

> `KeepAlive` restarts the launcher if it exits; `run.py start` is idempotent,
> so a re-run won't spawn duplicates. Stop everything with `python run.py stop`
> or `launchctl unload ~/Library/LaunchAgents/com.mcp-ruckus.plist`.

### Windows — Task Scheduler

1. Open **Task Scheduler** → **Create Basic Task** → name it `mcp-ruckus`.
2. Trigger: **When the computer starts**.
3. Action: **Start a program**
   - Program/script: the full path to `python.exe` (from your venv)
   - Arguments: `C:\path\to\mcp-ruckus\run.py start`
   - Start in: `C:\path\to\mcp-ruckus`
4. On the **General** tab, choose **Run whether user is logged on or not** and
   tick **Run with highest privileges** if it binds to privileged ports.
5. Finish, then right-click the task → **Run** to start it now.

To stop, run `python run.py stop` from a terminal in the project directory.

> For a proper Windows service (auto-restart, no console), wrap `run.py` with
> [NSSM](https://nssm.cc/): `nssm install mcp-ruckus C:\path\to\python.exe C:\path\to\mcp-ruckus\run.py start`.

### Linux without systemd

Use a cron `@reboot` entry (crontab -e) or an init script:

```cron
@reboot /usr/bin/python3 /opt/mcp-ruckus/run.py start
```

## See also

- [systemd.md](systemd.md) — the recommended Linux production setup (includes
  the polkit rule that makes the GUI restart work without a password).
