#!/usr/bin/env python3
"""Cross-platform launcher for the Ruckus MCP server and admin GUI.

Runs both processes natively on Linux, macOS, and Windows using only the
Python standard library — no bash, no systemd, no third-party packages.

    python run.py start|stop|restart|status

- ``start``    launches ``server.py`` (MCP) and ``admin.py`` (GUI) in the background
- ``stop``     terminates both via the recorded PID files
- ``restart``  stop, then start
- ``status``   reports whether each process is running

Logs are written to ``logs/server.log`` and ``logs/admin.log``; PID files live
under ``data/`` (already gitignored). Both processes load ``.env`` themselves,
so no OS-specific configuration is required.

To start on boot, register this command with the OS — see ``deploy/native.md``:

- Linux    → systemd unit
- macOS    → launchd LaunchAgent
- Windows  → Task Scheduler
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PID_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# name -> (script, human label). Insertion order = start order.
PROCS = {
    "server": ("server.py", "MCP server"),
    "admin": ("admin.py", "admin GUI"),
}


def _pid_file(name: str) -> Path:
    return PID_DIR / f"{name}.pid"


def _log_file(name: str) -> Path:
    return LOG_DIR / f"{name}.log"


def _ensure_dirs() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read_pid(name: str) -> int | None:
    path = _pid_file(name)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _is_running(pid: int | None) -> bool:
    """Return True if a process with the given PID is still alive."""
    if pid is None:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) is not a safe existence check on Windows, so query
        # the task list instead.
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate(pid: int) -> None:
    """Terminate a process tree, cross-platform."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def _start(name: str, script: str) -> None:
    _ensure_dirs()
    log = _log_file(name)
    with log.open("ab") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / script)],
            cwd=str(BASE_DIR),
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # POSIX: detach into its own session
        )
    _pid_file(name).write_text(str(proc.pid), encoding="utf-8")


def do_start() -> None:
    for name, (script, label) in PROCS.items():
        if _is_running(_read_pid(name)):
            print(f"[run] {label}: already running")
            continue
        _start(name, script)
        print(f"[run] {label}: started (pid {_read_pid(name)}) -> logs/{name}.log")


def do_stop() -> None:
    for name, (_, label) in PROCS.items():
        pid = _read_pid(name)
        if _is_running(pid):
            _terminate(pid)
            print(f"[run] {label}: stopped (pid {pid})")
        else:
            print(f"[run] {label}: not running")
        _pid_file(name).unlink(missing_ok=True)


def do_status() -> None:
    for name, (_, label) in PROCS.items():
        pid = _read_pid(name)
        state = f"RUNNING (pid {pid})" if _is_running(pid) else "STOPPED"
        print(f"[run] {label}: {state}")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "start":
        do_start()
    elif cmd == "stop":
        do_stop()
    elif cmd == "restart":
        do_stop()
        time.sleep(1)
        do_start()
    elif cmd == "status":
        do_status()
    else:
        print("usage: python run.py {start|stop|restart|status}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
