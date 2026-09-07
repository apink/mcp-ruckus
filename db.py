"""SQLite storage for the Ruckus MCP server and its admin GUI.

Shared by two processes (the MCP server and the admin GUI), so it uses WAL
mode plus a busy timeout for safe concurrent access. All functions open a
short-lived connection per operation — cheap at this scale and avoids any
cross-thread/cross-process connection sharing.

Tables:
  - users      — admin GUI accounts (role + forced password change)
  - api_keys   — per-client MCP keys (name, allowlist, destructive flag)
  - audit_log  — append-only tool-call audit trail
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    must_change_password INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    key TEXT NOT NULL UNIQUE,
    allowed_tools TEXT NOT NULL DEFAULT '[]',
    allow_destructive INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    client TEXT NOT NULL,
    client_ip TEXT,
    tool TEXT NOT NULL,
    args TEXT,
    outcome TEXT NOT NULL,
    duration_ms REAL,
    destructive INTEGER NOT NULL DEFAULT 0,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_client ON audit_log(client);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_log(tool);
"""

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def default_db_path() -> Path:
    """Return the SQLite file path (configurable via MCP_DB_PATH)."""
    return Path(os.getenv("MCP_DB_PATH", str(BASE_DIR / "data" / "admin.db")))


def connect() -> sqlite3.Connection:
    """Open a connection with WAL + busy timeout and ensure the schema exists."""
    path = default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Password hashing ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a scrypt hash of ``password`` as ``scrypt$salt$digest``."""
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    ).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Return True if ``password`` matches the stored scrypt hash."""
    try:
        _, salt, digest = stored.split("$")
        calc = hashlib.scrypt(
            password.encode(), salt=salt.encode(), n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
        ).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, TypeError):
        return False


# ── Users ───────────────────────────────────────────────────────────

def ensure_default_admin() -> tuple[str, str] | None:
    """Create the default super admin if no user exists.

    Returns ``(username, password)`` when created (so the caller can print the
    one-time password), otherwise ``None``.
    """
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count:
            return None
        username = os.getenv("MCP_ADMIN_USER", "admin").strip() or "admin"
        password = os.getenv("MCP_ADMIN_INIT_PASS", "").strip() or secrets.token_urlsafe(12)
        conn.execute(
            "INSERT INTO users (username, password_hash, role, must_change_password, created_at) "
            "VALUES (?, ?, 'superadmin', 1, ?)",
            (username, hash_password(password), _now()),
        )
        conn.commit()
        return username, password


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, username, role, must_change_password, created_at, last_login "
            "FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def create_user(username: str, password: str, role: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, must_change_password, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (username, hash_password(password), role, _now()),
        )
        conn.commit()


def set_user_role(user_id: int, role: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        conn.commit()


def set_user_password(user_id: int, password: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (hash_password(password), user_id),
        )
        conn.commit()


def clear_must_change(user_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET must_change_password = 0 WHERE id = ?", (user_id,))
        conn.commit()


def record_login(user_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))
        conn.commit()


def delete_user(user_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


# ── API keys ────────────────────────────────────────────────────────

def new_api_key() -> str:
    """Generate a fresh random API key."""
    return "ruck_" + secrets.token_hex(24)


def create_api_key(name: str, key: str, allowed_tools: list[str], allow_destructive: bool) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO api_keys (name, key, allowed_tools, allow_destructive, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, key, json.dumps(allowed_tools), 1 if allow_destructive else 0, _now()),
        )
        conn.commit()


def list_api_keys() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, key, allowed_tools, allow_destructive, created_at "
            "FROM api_keys ORDER BY id"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["allowed_tools"] = json.loads(d["allowed_tools"] or "[]")
        d["allow_destructive"] = bool(d["allow_destructive"])
        out.append(d)
    return out


def get_api_key_by_name(name: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, key, allowed_tools, allow_destructive, created_at "
            "FROM api_keys WHERE name = ?",
            (name,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["allowed_tools"] = json.loads(d["allowed_tools"] or "[]")
    d["allow_destructive"] = bool(d["allow_destructive"])
    return d


def get_api_key_by_key(key: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, key, allowed_tools, allow_destructive, created_at "
            "FROM api_keys WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["allowed_tools"] = json.loads(d["allowed_tools"] or "[]")
    d["allow_destructive"] = bool(d["allow_destructive"])
    return d


def update_api_key(name: str, allowed_tools: list[str], allow_destructive: bool) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET allowed_tools = ?, allow_destructive = ? WHERE name = ?",
            (json.dumps(allowed_tools), 1 if allow_destructive else 0, name),
        )
        conn.commit()
    return cur.rowcount > 0


def regenerate_api_key(name: str) -> str | None:
    key = new_api_key()
    with connect() as conn:
        cur = conn.execute("UPDATE api_keys SET key = ? WHERE name = ?", (key, name))
        conn.commit()
    return key if cur.rowcount > 0 else None


def delete_api_key(name: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM api_keys WHERE name = ?", (name,))
        conn.commit()
    return cur.rowcount > 0


def count_api_keys() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM api_keys").fetchone()["c"]


# ── Audit log ───────────────────────────────────────────────────────

def insert_audit(
    *,
    client: str,
    tool: str,
    args: dict[str, Any] | None,
    outcome: str,
    duration_ms: float,
    client_ip: str | None = None,
    destructive: bool = False,
    reason: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (ts, client, client_ip, tool, args, outcome, duration_ms, destructive, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _now(),
                client,
                client_ip,
                tool,
                json.dumps(args or {}),
                outcome,
                duration_ms,
                1 if destructive else 0,
                reason,
            ),
        )
        conn.commit()


def query_audit(
    *,
    client: str = "",
    tool: str = "",
    outcome: str = "",
    text: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    where: list[str] = []
    params: list[Any] = []
    if client:
        where.append("client = ?")
        params.append(client)
    if tool:
        where.append("tool = ?")
        params.append(tool)
    if outcome:
        where.append("outcome = ?")
        params.append(outcome)
    if text:
        where.append("(tool LIKE ? OR client LIKE ?)")
        params.extend([f"%{text}%", f"%{text}%"])
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM audit_log {clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM audit_log {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [dict(r) for r in rows], total


def audit_summary() -> dict[str, Any]:
    """Return counts by outcome and top denied clients/tools."""
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
        by_outcome = {
            r["outcome"]: r["c"]
            for r in conn.execute("SELECT outcome, COUNT(*) AS c FROM audit_log GROUP BY outcome").fetchall()
        }
        top_denied = [
            dict(r)
            for r in conn.execute(
                "SELECT client, COUNT(*) AS c FROM audit_log WHERE outcome IN ('denied','error') "
                "GROUP BY client ORDER BY c DESC LIMIT 5"
            ).fetchall()
        ]
    return {"total": total, "by_outcome": by_outcome, "top_denied": top_denied}


def distinct_audit_clients() -> list[str]:
    """Return sorted distinct client names seen in the audit log."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT client FROM audit_log WHERE client != '' ORDER BY client"
        ).fetchall()
    return [r["client"] for r in rows]


# ── Health / status ─────────────────────────────────────────────────

def health_info() -> dict[str, Any]:
    """Return counts and DB file size for the health endpoint/dashboard."""
    with connect() as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        keys = conn.execute("SELECT COUNT(*) AS c FROM api_keys").fetchone()["c"]
        audit = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
    try:
        size = default_db_path().stat().st_size
    except OSError:
        size = 0
    return {"users": users, "api_keys": keys, "audit_events": audit, "db_size_bytes": size}
