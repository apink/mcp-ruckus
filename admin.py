"""Lightweight text-based web admin for the Ruckus MCP server.

Runs as a SEPARATE process from the MCP server (option B): it stays up while
the MCP server is down and reports its status via the MCP ``/health`` endpoint.
It does not start/stop the MCP process — that remains manual (systemd/docker).

Storage (hybrid):
  - SQLite (``data/admin.db``) — users/roles, per-client API keys, audit trail
  - ``inventory/devices.yaml`` — device inventory (editable here, read live by MCP)
  - ``.env`` — vSZ config (read-only display)

Roles: superadmin > operator > viewer.
"""
from __future__ import annotations

import ast
import base64
import functools
import hashlib
import hmac
import html
import ipaddress
import json
import os
import secrets
import shlex
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

import db
from inventory import manager as inv_manager
from lean import LEAN_TOOLS

BASE_DIR = Path(__file__).resolve().parent

_ENV_PATH = BASE_DIR / ".env"
if _ENV_PATH.exists():
    with _ENV_PATH.open("r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#"):
                if "#" in _line:
                    _line = _line[:_line.index("#")].strip()
                if "=" in _line:
                    _key, _, _val = _line.partition("=")
                    _val = _val.strip()
                    if _val:
                        os.environ.setdefault(_key.strip(), _val)

SESSION_COOKIE = "ruckus_admin"
SESSION_TTL = 24 * 3600
RANKS = {"viewer": 1, "operator": 2, "superadmin": 3}
PAGE_SIZE = 25
_PAGE_SIZES = (10, 25, 50, 100)


def _q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


# ── Session (HMAC-signed cookie) ────────────────────────────────────

def _secret() -> bytes:
    """Return a persistent signing secret (auto-created, chmod 0600)."""
    path = db.default_db_path().parent / "admin-secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes()
    secret = secrets.token_bytes(32)
    path.write_bytes(secret)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return secret


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sig(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def _make_token(user: dict[str, Any], flash: str | None = None) -> str:
    data = {
        "uid": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + SESSION_TTL,
    }
    if flash is not None:
        data["flash"] = flash
    payload = _b64e(json.dumps(data).encode())
    return payload + "." + _sig(payload)


def _read_token(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token or "." not in token:
        return None
    payload, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sig(payload), sig):
        return None
    try:
        data = json.loads(_b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


def _current_user(request: Request) -> dict[str, Any] | None:
    data = _read_token(request)
    if not data:
        return None
    return db.get_user_by_id(data["uid"])


def _csrf(user: dict[str, Any]) -> str:
    return _sig(f"csrf:{user['id']}")[:16]


def _check_csrf(form: Any, user: dict[str, Any]) -> bool:
    return hmac.compare_digest(str(form.get("csrf", "")), _csrf(user))


def _require(request: Request, min_role: str) -> tuple[dict[str, Any] | None, Response | None]:
    user = _current_user(request)
    if not user:
        return None, RedirectResponse("/login", status_code=303)
    if RANKS.get(user["role"], 0) < RANKS[min_role]:
        body = _page("Forbidden", _alert(f"Role '{user['role']}' cannot access this page."), user)
        return user, HTMLResponse(body, status_code=403)
    return user, None


def _set_session(response: Response, user: dict[str, Any]) -> Response:
    response.set_cookie(
        SESSION_COOKIE, _make_token(user), max_age=SESSION_TTL, httponly=True, samesite="lax"
    )
    return response


def _set_flash(response: Response, user: dict[str, Any], flash: str) -> Response:
    """Set a one-shot flash value (e.g. a revealed API key) on the session cookie."""
    response.set_cookie(
        SESSION_COOKIE, _make_token(user, flash), max_age=SESSION_TTL, httponly=True, samesite="lax"
    )
    return response


def _clear_session(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── HTML helpers ────────────────────────────────────────────────────

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _alert(msg: str, kind: str = "error") -> str:
    return f'<p class="alert {kind}">{esc(msg)}</p>'


_NAV_PATHS = {
    "Dashboard": "/dashboard",
    "API Keys": "/keys",
    "Inventory": "/inventory",
    "Audit": "/audit",
    "Config": "/config",
    "Users": "/users",
    "Change password": "/change-password",
}


def _nav(user: dict[str, Any] | None, current: str = "") -> str:
    if not user:
        return ""
    links = [
        ("Dashboard", "/dashboard"),
        ("API Keys", "/keys"),
        ("Inventory", "/inventory"),
        ("Audit", "/audit"),
        ("Config", "/config"),
    ]
    active_path = _NAV_PATHS.get(current, "")
    items = "".join(
        f'<a href="{u}" class="{"active" if u == active_path else ""}">{n}</a>'
        for n, u in links
    )
    if user["role"] == "superadmin":
        items += (
            '<div class="nav-sep"></div>'
            + f'<a href="/users" class="{"active" if active_path == "/users" else ""}">Users</a>'
        )
    role = f'<span class="badge role-{esc(user["role"])}">{esc(user["role"])}</span>'
    change_pw_active = ' class="active"' if active_path == "/change-password" else ""
    return (
        '<aside class="sidebar">'
        '<div class="brand">Ruckus MCP <span class="sub">Admin</span></div>'
        f"<nav>{items}</nav>"
        f'<div class="who"><span>{esc(user["username"])} {role}</span>'
        f'<a href="/change-password"{change_pw_active}>Change password</a>'
        '<a href="/logout">Logout</a></div>'
        "</aside>"
    )


def _page(title: str, body: str, user: dict[str, Any] | None, msg: str = "", err: str = "") -> str:
    alert = (_alert(msg, "ok") if msg else "") + (_alert(err, "error") if err else "")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)} — Ruckus MCP Admin</title>"
        '<link rel="stylesheet" href="/static/style.css">'
        '<script src="/static/app.js"></script></head><body>'
        f'<div class="shell">{_nav(user, title)}'
        f'<div class="main"><main class="content">{alert}{body}</main></div></div></body></html>'
    )


def _login_page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)} — Ruckus MCP Admin</title>"
        '<link rel="stylesheet" href="/static/style.css"></head>'
        f"<body class='login'><main class='login-wrap'>{body}</main></body></html>"
    )


# ── Tool catalog (for key scoping) ──────────────────────────────────

_DOMAIN_ORDER = ["vSZ", "ICX", "Inventory", "Connectivity"]

_DOMAIN_BY_MODULE = {
    "icx_device": "ICX",
    "inventory": "Inventory",
    "connectivity": "Connectivity",
}


def _domain_for_module(stem: str) -> str:
    """Map a tools module name to a display domain ('' to skip)."""
    if stem.startswith("vsz_"):
        return "vSZ"
    return _DOMAIN_BY_MODULE.get(stem, "")


def _is_tool_decorator(node: ast.expr) -> bool:
    """Return True if a decorator is an ``@mcp.tool()`` call."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "tool"


@functools.lru_cache(maxsize=1)
def _tool_names_by_domain() -> list[tuple[str, list[str]]]:
    """Enumerate MCP tool names from tools/*.py source, grouped by domain."""
    groups: dict[str, set[str]] = {}
    tools_dir = BASE_DIR / "tools"
    for path in sorted(tools_dir.glob("*.py")):
        domain = _domain_for_module(path.stem)
        if not domain:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(_is_tool_decorator(d) for d in node.decorator_list):
                    names.add(node.name)
        if names:
            groups.setdefault(domain, set()).update(names)
    return [(d, sorted(groups[d])) for d in _DOMAIN_ORDER if d in groups]


def _tool_checkboxes(selected: set[str]) -> str:
    """Render grouped, collapsible checkboxes for tool scoping (empty = all)."""
    groups = _tool_names_by_domain()
    if not groups:
        return "<p class='muted'>Could not enumerate tools (tools/ not found).</p>"
    blocks = []
    for domain, names in groups:
        boxes = "".join(
            f'<label class="tool"><input type="checkbox" name="tool" value="{esc(n)}" '
            f'data-g="{esc(domain)}" onchange="updateScope()" '
            f'{"checked" if n in selected else ""}> {esc(n)}</label>'
            for n in names
        )
        open_attr = " open" if set(names) & selected else ""
        blocks.append(
            f'<details class="tool-group"{open_attr}><summary class="tool-head">{esc(domain)} '
            f'<span class="muted">({len(names)})</span>'
            f'<a href="#" onclick="event.stopPropagation(); return setGroup(\'{esc(domain)}\',true)">all</a>'
            f'<a href="#" onclick="event.stopPropagation(); return setGroup(\'{esc(domain)}\',false)">none</a>'
            f'</summary><div class="tool-list">{boxes}</div></details>'
        )
    return (
        '<div class="tools"><div class="tool-actions">'
        '<a href="#" onclick="return setAll(true)">Select all</a> · '
        '<a href="#" onclick="return setAll(false)">Clear</a> · '
        '<a href="#" onclick="return setLean()" title="Read-only tools agents use most">Most used tools</a>'
        '<input type="text" id="tool-filter" placeholder="Filter tools…" '
        'oninput="filterTools(this)">'
        '</div>'
        + "".join(blocks)
        + f"<script>window.LEAN_TOOLS={json.dumps(sorted(LEAN_TOOLS))};updateScope();</script>"
        + "</div>"
    )


def _tools_summary(tools: list[str]) -> str:
    """Return a compact summary of an allowed-tools list for table display."""
    tools = sorted(set(tools))
    if not tools:
        return "<span class='muted'>all</span>"
    full = ", ".join(esc(t) for t in tools)
    shown = ", ".join(esc(t) for t in tools[:3])
    if len(tools) > 3:
        shown += f' <span class="muted">+{len(tools) - 3} more</span>'
    return f'<span title="{full}">{shown}</span>'


# ── MCP status ──────────────────────────────────────────────────────

def _mcp_health_url() -> str:
    host = os.getenv("MCP_HOST", "0.0.0.0")
    if host in ("0.0.0.0", "::", ""):
        host = "127.0.0.1"
    port = os.getenv("MCP_PORT", "8000")
    return f"http://{host}:{port}/health"


async def _mcp_status() -> tuple[bool, dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(_mcp_health_url())
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    return False, {}


def _status_badge(up: bool) -> str:
    cls = "up" if up else "down"
    label = "RUNNING" if up else "STOPPED"
    return f'<span class="status {cls}">{label}</span>'


# ── Auth routes ─────────────────────────────────────────────────────

async def login_page(request: Request) -> Response:
    msg = request.query_params.get("msg", "")
    body = (
        '<div class="login-card">'
        '<div class="login-brand">Ruckus MCP <span>Admin</span></div>'
        + (_alert(msg) if msg else "")
        + '<form method="post" action="/login">'
        '<label>Username</label><input type="text" name="username" autofocus>'
        '<label>Password</label><input type="password" name="password">'
        '<button type="submit">Login</button></form></div>'
    )
    return HTMLResponse(_login_page("Login", body))


async def login_submit(request: Request) -> Response:
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    user = db.get_user_by_username(username)
    if not user or not db.verify_password(password, user["password_hash"]):
        return RedirectResponse("/login?msg=" + _q("Invalid credentials"), status_code=303)
    db.record_login(user["id"])
    target = "/change-password" if user["must_change_password"] else "/dashboard"
    return _set_session(RedirectResponse(target, status_code=303), user)


async def logout(request: Request) -> Response:
    return _clear_session(RedirectResponse("/login", status_code=303))


async def change_password_page(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    return HTMLResponse(_page("Change password", _pw_form(), user))


async def change_password_submit(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    form = await request.form()
    new_password = str(form.get("new_password", ""))
    confirm = str(form.get("confirm", ""))
    if len(new_password) < 8 or new_password != confirm:
        body = _alert("Password must be >= 8 chars and match.") + _pw_form()
        return HTMLResponse(_page("Change password", body, user))
    db.set_user_password(user["id"], new_password)
    return RedirectResponse("/dashboard?msg=" + _q("Password updated"), status_code=303)


def _pw_form() -> str:
    return (
        '<div class="page-head"><h2>Change password</h2></div>'
        '<div class="card">'
        '<form method="post" action="/change-password">'
        '<label>New password</label><input type="password" name="new_password" autocomplete="new-password"><br>'
        '<label>Confirm</label><input type="password" name="confirm" autocomplete="new-password"><br>'
        '<button type="submit">Save</button></form></div>'
    )


# ── Dashboard ───────────────────────────────────────────────────────

async def dashboard(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    up, health = await _mcp_status()
    info = db.health_info()
    stats = [
        ("MCP server", _status_badge(up)),
        ("Uptime (s)", esc(health.get("uptime_s", "—")) if up else "—"),
        ("Tools registered", esc(health.get("tool_count", "—")) if up else "—"),
        ("API keys", esc(info["api_keys"])),
        ("Admin users", esc(info["users"])),
        ("Audit events", esc(info["audit_events"])),
        ("DB size", f"{info['db_size_bytes'] / 1024 / 1024:.2f} MB"),
        ("Transport", esc(os.getenv("MCP_TRANSPORT", "streamable-http"))),
        ("Bind", f"{os.getenv('MCP_HOST', '0.0.0.0')}:{os.getenv('MCP_PORT', '8000')}"),
    ]
    grid = "".join(
        f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in stats
    )
    body = f'<div class="page-head"><h2>Dashboard</h2></div><div class="stat-grid">{grid}</div>'
    return HTMLResponse(_page("Dashboard", body, user, request.query_params.get("msg", "")))


# ── API keys ────────────────────────────────────────────────────────

async def keys_page(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    rows = db.list_api_keys()
    trs = []
    for k in rows:
        tools = _tools_summary(k["allowed_tools"])
        destructive = "yes" if k["allow_destructive"] else "no"
        masked = k["key"][:7] + "••••••"
        trs.append(
            f"<tr><td>{esc(k['name'])}</td><td>{esc(masked)}</td><td>{tools}</td>"
            f"<td>{destructive}</td><td><a href='/keys?edit={esc(k['name'])}'>edit</a></td></tr>"
        )
    table = (
        "<div class='card'><div class='table-scroll'><table><tr><th>Name</th><th>Key</th><th>Allowed tools</th>"
        "<th>Config</th><th></th></tr>"
        + "".join(trs)
        + "</table></div></div>"
    )

    edit_name = request.query_params.get("edit", "")
    edit_form = ""
    if edit_name:
        target = db.get_api_key_by_name(edit_name)
        if target:
            edit_form = _key_form(target, user)
    add_form = "" if edit_name else _key_form(None, user)

    data = _read_token(request)
    reveal_key = (data or {}).get("flash", "")
    reveal_box = ""
    if reveal_key:
        reveal_box = (
            '<div class="reveal"><div class="reveal-label">'
            "API key — copy it now, it will not be shown again</div>"
            '<div class="reveal-row"><code class="reveal-key" id="reveal-key">'
            f"{esc(reveal_key)}</code>"
            '<button type="button" onclick="copyKey()">Copy</button></div></div>'
        )

    body = (
        f'<div class="page-head"><h2>API Keys</h2></div>{reveal_box}'
        f"{table}{add_form}{edit_form}"
    )
    response = HTMLResponse(_page("API Keys", body, user, request.query_params.get("msg", "")))
    if data and "flash" in data:
        _set_session(response, user)
    return response


def _key_form(target: dict[str, Any] | None, user: dict[str, Any]) -> str:
    is_edit = target is not None
    name = target["name"] if target else ""
    selected = set(target["allowed_tools"]) if target else set(LEAN_TOOLS)
    checked = "checked" if (target and target["allow_destructive"]) else ""
    csrf = _csrf(user)
    heading = f"<h3>Edit key '{esc(name)}'</h3>" if is_edit else "<h3>Add key</h3>"
    name_field = (
        f'<input type="hidden" name="name" value="{esc(name)}"><label>Name</label>{esc(name)}<br>'
        if is_edit
        else '<label>Name</label><input type="text" name="name"><br>'
    )
    action = "/keys/update" if is_edit else "/keys"
    scope = "all" if (target is not None and not target["allowed_tools"]) else "selected"
    sel_checked = "checked" if scope == "selected" else ""
    all_checked = "checked" if scope == "all" else ""
    form = (
        f"{heading}<form method='post' action='{action}'>"
        f'<input type="hidden" name="csrf" value="{csrf}">'
        f"{name_field}"
        '<label>Scope</label>'
        '<div class="scope-row">'
        f'<label><input type="radio" name="scope" value="selected" '
        f'onchange="updateScope()" {sel_checked}> Selected tools</label>'
        f'<label><input type="radio" name="scope" value="all" '
        f'onchange="updateScope()" {all_checked}> All tools</label>'
        '</div>'
        '<p id="tool-warn" class="alert warn" style="display:none"></p>'
        '<div id="tool-scope">'
        + _tool_checkboxes(selected)
        + '</div>'
        + f'<label>Allow config</label><input type="checkbox" name="allow_destructive" {checked}><br>'
        + f"<button type='submit'>{'Save' if is_edit else 'Add'}</button></form>"
    )
    if is_edit:
        form += (
            f'<form method="post" action="/keys/regenerate" '
            f'onsubmit="return confirm(\'Regenerate key {esc(name)}?\')">'
            f'<input type="hidden" name="name" value="{esc(name)}">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<button type="submit">Regenerate key</button></form>'
            f'<form method="post" action="/keys/delete" '
            f'onsubmit="return confirm(\'Delete key {esc(name)}?\')">'
            f'<input type="hidden" name="name" value="{esc(name)}">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<button type="submit">Delete</button></form>'
        )
    return f'<div class="card">{form}</div>'


async def key_add(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    name = str(form.get("name", "")).strip()
    if not name:
        return RedirectResponse("/keys?msg=" + _q("Name is required"), status_code=303)
    key_input = str(form.get("key", "")).strip()
    generated = not key_input
    key = key_input or db.new_api_key()
    scope = str(form.get("scope", "selected")).strip()
    if scope == "all":
        tools: list[str] = []
    else:
        tools = [str(t).strip() for t in form.getlist("tool") if str(t).strip()]
        if not tools:
            return RedirectResponse(
                "/keys?msg=" + _q("Select at least one tool, or choose 'All tools'"),
                status_code=303,
            )
    destructive = form.get("allow_destructive") is not None
    try:
        db.create_api_key(name, key, tools, destructive)
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse("/keys?msg=" + _q(f"Error: {exc}"), status_code=303)
    response = RedirectResponse("/keys?msg=" + _q("Key created: " + name), status_code=303)
    if generated:
        _set_flash(response, user, key)
    return response


async def key_update(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    name = str(form.get("name", "")).strip()
    scope = str(form.get("scope", "selected")).strip()
    if scope == "all":
        tools: list[str] = []
    else:
        tools = [str(t).strip() for t in form.getlist("tool") if str(t).strip()]
        if not tools:
            return RedirectResponse(
                "/keys?msg=" + _q("Select at least one tool, or choose 'All tools'"),
                status_code=303,
            )
    destructive = form.get("allow_destructive") is not None
    db.update_api_key(name, tools, destructive)
    return RedirectResponse("/keys?msg=" + _q("Key updated: " + name), status_code=303)


async def key_delete(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    name = str(form.get("name", "")).strip()
    db.delete_api_key(name)
    return RedirectResponse("/keys?msg=" + _q("Key deleted: " + name), status_code=303)


async def key_regenerate(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    name = str(form.get("name", "")).strip()
    new_key = db.regenerate_api_key(name)
    if new_key:
        response = RedirectResponse("/keys?msg=" + _q("Key regenerated: " + name), status_code=303)
        _set_flash(response, user, new_key)
        return response
    return RedirectResponse("/keys?msg=" + _q("Key not found"), status_code=303)


# ── Inventory ───────────────────────────────────────────────────────

async def inventory_page(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    devices = inv_manager.load_inventory_raw()
    trs = []
    for d in devices:
        cred = esc(d.get("username", "")) if d.get("username") else ""
        if d.get("password"):
            cred += " / (password set)"
        trs.append(
            f"<tr><td>{esc(d.get('host',''))}</td><td>{esc(d.get('name',''))}</td>"
            f"<td>{esc(d.get('vendor',''))}</td><td>{esc(d.get('role',''))}</td>"
            f"<td>{esc(d.get('location',''))}</td><td>{esc(d.get('rack',''))}</td>"
            f"<td>{cred}</td><td><a href='/inventory?edit={esc(d.get('host',''))}'>edit</a></td></tr>"
        )
    table = (
        "<div class='card'><div class='table-scroll'><table><tr><th>Host</th><th>Name</th><th>Vendor</th><th>Role</th>"
        "<th>Location</th><th>Rack</th><th>Auth</th><th></th></tr>" + "".join(trs) + "</table></div></div>"
    )

    edit_host = request.query_params.get("edit", "")
    target = None
    for d in devices:
        if d.get("host") == edit_host:
            target = d
            break

    body = f'<div class="page-head"><h2>Device Inventory</h2></div>{table}{_inventory_form(target, user)}'
    return HTMLResponse(_page("Inventory", body, user, request.query_params.get("msg", "")))


def _inventory_form(target: dict[str, Any] | None, user: dict[str, Any]) -> str:
    is_edit = target is not None
    v = target or {}
    csrf = _csrf(user)
    heading = f"<h3>Edit device '{esc(v.get('host',''))}'</h3>" if is_edit else "<h3>Add device</h3>"
    host_field = (
        f'<input type="hidden" name="host" value="{esc(v.get("host",""))}">'
        f'<label>Host (IP)</label>{esc(v.get("host",""))}<br>'
        if is_edit
        else '<label>Host (IP)</label><input type="text" name="host"><br>'
    )
    pw_placeholder = "leave empty = unchanged" if is_edit else ""
    form = (
        f"{heading}<form method='post' action='/inventory/save'>"
        f'<input type="hidden" name="csrf" value="{csrf}">{host_field}'
        f'<label>Name</label><input type="text" name="name" value="{esc(v.get("name",""))}"><br>'
        f'<label>Vendor</label><input type="text" name="vendor" value="{esc(v.get("vendor","ruckus"))}"><br>'
        f'<label>Role</label><input type="text" name="role" value="{esc(v.get("role",""))}"><br>'
        f'<label>Location</label><input type="text" name="location" value="{esc(v.get("location",""))}"><br>'
        f'<label>Rack</label><input type="text" name="rack" value="{esc(v.get("rack",""))}"><br>'
        f'<label>Username</label><input type="text" name="username" value="{esc(v.get("username",""))}"><br>'
        f'<label>Password</label><input type="password" name="password" placeholder="{pw_placeholder}"><br>'
        f"<button type='submit'>{'Save' if is_edit else 'Add'}</button></form>"
    )
    if is_edit:
        form += (
            f'<form method="post" action="/inventory/delete" '
            f'onsubmit="return confirm(\'Delete device {esc(v.get("host",""))}?\')">'
            f'<input type="hidden" name="host" value="{esc(v.get("host",""))}">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<button type="submit">Delete</button></form>'
        )
    return f'<div class="card">{form}</div>'


async def inventory_save(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    host = str(form.get("host", "")).strip()
    if not host:
        return RedirectResponse("/inventory?msg=" + _q("Host is required"), status_code=303)
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    devices = inv_manager.load_inventory_raw()
    existing = next((d for d in devices if d.get("host") == host), None)
    new_dev = {
        "host": host,
        "name": str(form.get("name", "")).strip() or host,
        "vendor": str(form.get("vendor", "")).strip() or "ruckus",
        "role": str(form.get("role", "")).strip(),
        "location": str(form.get("location", "")).strip(),
        "rack": str(form.get("rack", "")).strip(),
        "username": username or (existing.get("username", "") if existing else ""),
        "password": password or (existing.get("password", "") if existing else ""),
    }
    devices = [d for d in devices if d.get("host") != host] + [new_dev]
    inv_manager.save_inventory(devices)
    return RedirectResponse("/inventory?msg=" + _q("Saved: " + host), status_code=303)


async def inventory_delete(request: Request) -> Response:
    user, err = _require(request, "operator")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    host = str(form.get("host", "")).strip()
    devices = [d for d in inv_manager.load_inventory_raw() if d.get("host") != host]
    inv_manager.save_inventory(devices)
    return RedirectResponse("/inventory?msg=" + _q("Deleted: " + host), status_code=303)


# ── Audit ───────────────────────────────────────────────────────────

def _fmt_ts(ts: str) -> str:
    """Format an ISO UTC timestamp for display in the server's local timezone."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts


def _pager(page: int, pages: int, client: str, tool: str, outcome: str, text: str, per_page: int) -> str:
    """Render a bounded pagination bar (prev/next + windowed page numbers)."""

    def link(p: int, label: str) -> str:
        qs = (
            f"client={_q(client)}&tool={_q(tool)}&outcome={_q(outcome)}"
            f"&text={_q(text)}&per_page={per_page}&page={p}"
        )
        return f'<a href="/audit?{qs}">{label}</a>'

    items: list[str] = []
    if page > 1:
        items.append(link(page - 1, "Prev"))
    shown = sorted({p for p in (1, pages, page - 2, page - 1, page, page + 1, page + 2) if 1 <= p <= pages})
    prev = 0
    for p in shown:
        if p != prev + 1:
            items.append('<span class="gap">…</span>')
        if p == page:
            items.append(f'<span class="current">{p}</span>')
        else:
            items.append(link(p, str(p)))
        prev = p
    if page < pages:
        items.append(link(page + 1, "Next"))
    return f'<div class="pager">{"".join(items)}</div>'


async def audit_page(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    q = request.query_params
    client = q.get("client", "")
    tool = q.get("tool", "")
    outcome = q.get("outcome", "")
    text = q.get("text", "")
    try:
        page = max(1, int(q.get("page", "1")))
    except ValueError:
        page = 1
    try:
        per_page = int(q.get("per_page", str(PAGE_SIZE)))
    except ValueError:
        per_page = PAGE_SIZE
    if per_page not in _PAGE_SIZES:
        per_page = PAGE_SIZE
    rows, total = db.query_audit(
        client=client, tool=tool, outcome=outcome, text=text,
        limit=per_page, offset=(page - 1) * per_page,
    )
    summary = db.audit_summary()
    client_opts = ['<option value="">(all)</option>'] + [
        f'<option value="{esc(c)}" {"selected" if c == client else ""}>{esc(c)}</option>'
        for c in db.distinct_audit_clients()
    ]
    outcome_opts = ['<option value="">(all)</option>'] + [
        f'<option value="{o}" {"selected" if o == outcome else ""}>{o}</option>'
        for o in ("ok", "error", "denied", "exception")
    ]
    per_page_opts = "".join(
        f'<option value="{n}" {"selected" if n == per_page else ""}>{n}</option>'
        for n in _PAGE_SIZES
    )

    by_outcome = " · ".join(f"{esc(k)}: {v}" for k, v in sorted(summary["by_outcome"].items()))
    outcome_txt = f" · {by_outcome}" if by_outcome else ""
    body = (
        '<div class="page-head"><h2>Audit Trail</h2></div>'
        '<div class="card">'
        f"<p class='muted'>Total events: {summary['total']}{outcome_txt}</p>"
        '<form method="get" action="/audit">'
        f'<label>Client</label><select name="client">{"".join(client_opts)}</select><br>'
        f'<label>Outcome</label><select name="outcome">{"".join(outcome_opts)}</select><br>'
        f'<label>Text</label><input type="text" name="text" value="{esc(text)}" placeholder="tool or client"><br>'
        f'<label>Rows</label><select name="per_page">{"".join(per_page_opts)}</select><br>'
        '<button type="submit">Filter</button></form></div>'
    )
    if rows:
        trs = []
        for r in rows:
            args = r.get("args") or "{}"
            try:
                args_txt = json.dumps(json.loads(args))
            except (ValueError, TypeError):
                args_txt = args
            trs.append(
                f"<tr><td>{esc(_fmt_ts(r['ts']))}</td><td>{esc(r['client'])}</td><td>{esc(r['client_ip'] or '')}</td>"
                f"<td>{esc(r['tool'])}</td><td>{esc(r['outcome'])}</td><td>{esc(r['duration_ms'])}</td>"
                f"<td>{'yes' if r['destructive'] else ''}</td><td class='muted'>{esc(args_txt[:120])}</td></tr>"
            )
        body += (
            "<div class='card'><div class='table-scroll'><table><tr><th>Time</th><th>Client</th><th>IP</th>"
            "<th>Tool</th>"
            "<th>Outcome</th><th>ms</th><th>Destr</th><th>Args</th></tr>"
            + "".join(trs)
            + "</table></div></div>"
        )
    else:
        body += "<p>No events.</p>"

    pages = (total + per_page - 1) // per_page
    if pages > 1:
        body += _pager(page, pages, client, tool, outcome, text, per_page)
    return HTMLResponse(_page("Audit", body, user))


# ── Config (editable .env, superadmin only) ─────────────────────────

_FIELDS: list[tuple[str, str, str, str]] = [
    ("VSZ_HOST", "vSZ host", "text", ""),
    ("VSZ_PORT", "vSZ port", "int", "8443"),
    ("VSZ_USER", "vSZ username", "text", "admin"),
    ("VSZ_API_VERSION", "vSZ API version", "text", "v11_1"),
    ("VSZ_RATE_LIMIT", "vSZ rate limit", "int", "10"),
    ("ICX_RATE_LIMIT", "ICX rate limit", "int", "5"),
    ("MCP_TRANSPORT", "MCP transport", "select", "streamable-http"),
    ("MCP_PORT", "MCP port", "int", "8000"),
    ("MCP_HOST", "MCP host", "text", "0.0.0.0"),
    ("LOG_LEVEL", "Log level", "select", "INFO"),
    ("MCP_MAX_ITEMS", "MCP max items", "int", "50"),
    ("MCP_ALLOWED_IPS", "MCP allowed IPs", "cidr", ""),
    ("MCP_AUDIT_RETENTION_DAYS", "Audit retention (days)", "int", "90"),
]

_SECRETS: list[tuple[str, str]] = [
    ("VSZ_PASS", "vSZ password"),
    ("VSZ_API_TOKEN", "vSZ API token"),
    ("MCP_API_KEY", "MCP API key (fallback)"),
]

_TRANSPORTS = ("streamable-http", "sse")
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _env_file() -> Path:
    return BASE_DIR / ".env"


def _env_lines() -> list[str]:
    p = _env_file()
    if p.exists():
        return p.read_text(encoding="utf-8").splitlines()
    return []


def _env_hash() -> str:
    p = _env_file()
    if not p.exists():
        return ""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _env_value(lines: list[str], key: str) -> str:
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "#" in s:
            s = s[: s.index("#")].strip()
        if "=" in s:
            k, _, v = s.partition("=")
            if k.strip() == key:
                return _strip_quotes(v)
    return ""


def _line_key(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "#" in s:
        s = s[: s.index("#")].strip()
    if "=" not in s:
        return None
    return s.partition("=")[0].strip()


def _line_comment(line: str) -> str:
    s = line.strip()
    idx = s.find("#")
    return s[idx:] if idx != -1 else ""


def _backup_env(p: Path) -> None:
    if not p.exists():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = p.with_name(p.name + ".bak." + stamp)
    try:
        bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass


def _write_env(updates: dict[str, str]) -> None:
    p = _env_file()
    lines = _env_lines()
    done: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = _line_key(line)
        if key in updates:
            comment = _line_comment(line)
            out.append(f"{key}={updates[key]}" + ((" " + comment) if comment else ""))
            done.add(key)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in done:
            out.append(f"{key}={val}")
    _backup_env(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, p)


def _first_bad_cidr(raw: str) -> str | None:
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "/" in part:
                ipaddress.ip_network(part, strict=False)
            else:
                ipaddress.ip_address(part)
        except ValueError:
            return part
    return None


def _validate_fields(form: Any) -> tuple[dict[str, str], list[str]]:
    updates: dict[str, str] = {}
    errors: list[str] = []
    for key, label, kind, _default in _FIELDS:
        raw = str(form.get(key, "")).strip()
        if kind == "int":
            if not raw:
                errors.append(f"{label} is required")
                continue
            try:
                n = int(raw)
            except ValueError:
                errors.append(f"{label} must be an integer")
                continue
            if key == "MCP_AUDIT_RETENTION_DAYS":
                if n < 0 or n > 36500:
                    errors.append(f"{label} must be 0 (keep forever) or up to 36500 days")
                    continue
            elif n < 1 or n > 65535:
                errors.append(f"{label} must be between 1 and 65535")
                continue
            updates[key] = str(n)
        elif kind == "select":
            allowed = _TRANSPORTS if key == "MCP_TRANSPORT" else _LOG_LEVELS
            if raw not in allowed:
                errors.append(f"{label} must be one of: {', '.join(allowed)}")
                continue
            updates[key] = raw
        elif kind == "cidr":
            bad = _first_bad_cidr(raw)
            if bad is not None:
                errors.append(f"{label}: invalid address '{bad}'")
                continue
            updates[key] = raw
        else:
            updates[key] = raw
    return updates, errors


def _restart_cmd() -> str:
    """Return the command used to restart the MCP server (config-driven)."""
    cmd = os.getenv("MCP_RESTART_CMD", "").strip()
    if cmd:
        return cmd
    return f"systemctl restart {os.getenv('MCP_SYSTEMD_UNIT', 'mcp-ruckus')}"


def _restart_mcp() -> tuple[bool, str]:
    cmd = _restart_cmd()
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return False, f"invalid MCP_RESTART_CMD: {exc}"
    if not argv:
        return False, "MCP_RESTART_CMD is empty"
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return False, f"command not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return False, "restart timed out"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if proc.returncode == 0:
        return True, f"Restart requested via: {cmd}"
    detail = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
    if argv[0].endswith("systemctl"):
        detail += " — install the unit and a polkit/sudo rule matching this process "
        "user (see deploy/systemd.md)."
    return False, detail

def _config_input(key: str, label: str, kind: str, value: str) -> str:
    if kind == "select":
        allowed = _TRANSPORTS if key == "MCP_TRANSPORT" else _LOG_LEVELS
        opts = "".join(
            f"<option value='{o}' {'selected' if o == value else ''}>{o}</option>" for o in allowed
        )
        return f"<label>{esc(label)}</label><select name='{key}'>{opts}</select><br>"
    placeholder = (
        "0 = keep forever" if key == "MCP_AUDIT_RETENTION_DAYS" else (
            "1-65535" if kind == "int" else ("comma-separated CIDR, empty = all" if kind == "cidr" else "")
        )
    )
    return (
        f"<label>{esc(label)}</label>"
        f"<input type='text' name='{key}' value='{esc(value)}' placeholder='{esc(placeholder)}'><br>"
    )


def _config_body(
    user: dict[str, Any],
    up: bool,
    errors: list[str] | None = None,
    submitted: Any = None,
) -> str:
    lines = _env_lines()
    base_hash = _env_hash()

    def cfg(key: str, default: str = "") -> str:
        v = _env_value(lines, key)
        return v if v != "" else default

    def secret_state(key: str) -> str:
        return "••• (set)" if _env_value(lines, key) else "(not set)"

    rows = [
        ("vSZ host", cfg("VSZ_HOST")),
        ("vSZ port", cfg("VSZ_PORT", "8443")),
        ("vSZ API version", cfg("VSZ_API_VERSION", "v11_1")),
        ("vSZ username", cfg("VSZ_USER", "admin")),
        ("vSZ password", secret_state("VSZ_PASS")),
        ("vSZ API token", secret_state("VSZ_API_TOKEN")),
        ("vSZ rate limit", cfg("VSZ_RATE_LIMIT", "10")),
        ("ICX rate limit", cfg("ICX_RATE_LIMIT", "5")),
        ("MCP transport", cfg("MCP_TRANSPORT", "streamable-http")),
        ("MCP host:port", f"{cfg('MCP_HOST', '0.0.0.0')}:{cfg('MCP_PORT', '8000')}"),
        ("MCP max items", cfg("MCP_MAX_ITEMS", "50")),
        ("MCP allowed IPs", cfg("MCP_ALLOWED_IPS", "(all)")),
        ("Audit retention (days)", cfg("MCP_AUDIT_RETENTION_DAYS", "90")),
        ("MCP_API_KEY fallback", secret_state("MCP_API_KEY")),
        ("Admin bind", f"{os.getenv('MCP_ADMIN_HOST','127.0.0.1')}:{os.getenv('MCP_ADMIN_PORT','8001')}"),
        ("DB path", str(db.default_db_path())),
        ("MCP server", _status_badge(up)),
    ]
    table = "".join(
        f"<tr><th>{k}</th><td>{v if k == 'MCP server' else esc(v)}</td></tr>" for k, v in rows
    )

    env_path = BASE_DIR / ".env"
    howto = (
        '<details class="card"><summary>How to edit via CLI (click to show)</summary>'
        "<p>You can also edit the file by hand. If you edit it manually while a form is open, "
        "the GUI will ask you to reload before saving.</p>"
        f"<p class='muted'>Your file: <code>{esc(str(env_path))}</code></p>"
        '<ol class="howto">'
        "<li>Open the file: <pre>nano .env</pre>"
        "Each line is <code>NAME=value</code>; lines starting with <code>#</code> are ignored. "
        "Save with <code>Ctrl+O</code>, <code>Enter</code>, then <code>Ctrl+X</code>.</li>"
        "<li>Restart the server to apply (use the Restart button, or run "
        f"<code>{esc(_restart_cmd())}</code>).</li>"
        "</ol>"
        "<p class='muted'>Secrets are never shown here, only set/rotated.</p></details>"
    )

    body: list[str] = ['<div class="page-head"><h2>Configuration</h2></div>']
    if errors:
        body.append(_alert("; ".join(errors), "error"))

    if user["role"] == "superadmin":
        csrf = _csrf(user)
        field_inputs = "".join(
            _config_input(
                key, label, kind,
                str(submitted.get(key, "")) if submitted is not None else cfg(key, default),
            )
            for key, label, kind, default in _FIELDS
        )
        secret_inputs = "".join(
            f"<label>{esc(label)}</label><input type='password' name='{key}' "
            f"placeholder='leave empty = unchanged ({secret_state(key)})' "
            f"autocomplete='new-password'><br>"
            for key, label in _SECRETS
        )
        body.append(
            '<div class="card"><h3>Edit settings</h3>'
            "<form method='post' action='/config/save'>"
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="base_hash" value="{base_hash}">'
            f"{field_inputs}"
            "<button type='submit'>Save settings</button></form></div>"
        )
        body.append(
            '<div class="card"><h3>Secrets (write-only)</h3>'
            "<p class='muted'>Type a new value to set/rotate it. Leave empty to keep the "
            "current value. Secrets are never shown back.</p>"
            "<form method='post' action='/config/secrets'>"
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="base_hash" value="{base_hash}">'
            f"{secret_inputs}"
            "<button type='submit'>Save secrets</button></form></div>"
        )
        body.append(
            '<div class="card"><h3>Service</h3>'
            "<p class='muted'>After saving, restart the MCP server to apply changes. "
            f"This runs <code>{esc(_restart_cmd())}</code>.</p>"
            "<form method='post' action='/config/restart' "
            "onsubmit=\"return confirm('Restart the MCP server now?')\">"
            f'<input type="hidden" name="csrf" value="{csrf}">'
            "<button type='submit'>Restart MCP server</button></form></div>"
        )
    else:
        body.append(
            "<p class='muted'>Sign in as a superadmin to edit settings or restart the server.</p>"
        )

    body.append(
        "<p class='muted'>Current values:</p>"
        + f"<div class='card'><div class='table-scroll'><table>{table}</table></div></div>"
    )
    body.append(howto)
    return "".join(body)


async def config_page(request: Request) -> Response:
    user, err = _require(request, "viewer")
    if err:
        return err
    up, _ = await _mcp_status()
    body = _config_body(user, up)
    return HTMLResponse(
        _page("Config", body, user, request.query_params.get("msg", ""),
              request.query_params.get("err", ""))
    )


async def config_save(request: Request) -> Response:
    user, err = _require(request, "superadmin")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    if str(form.get("base_hash", "")) != _env_hash():
        up, _ = await _mcp_status()
        body = _config_body(user, up, errors=["The .env file changed outside the GUI — reload and re-apply."])
        return HTMLResponse(_page("Config", body, user), status_code=409)
    updates, errors = _validate_fields(form)
    if errors:
        up, _ = await _mcp_status()
        body = _config_body(user, up, errors=errors, submitted=form)
        return HTMLResponse(_page("Config", body, user), status_code=400)
    try:
        _write_env(updates)
    except OSError as exc:
        up, _ = await _mcp_status()
        body = _config_body(user, up, errors=[f"Could not write .env: {exc}"])
        return HTMLResponse(_page("Config", body, user), status_code=409)
    return RedirectResponse("/config?msg=" + _q("Settings saved — restart to apply"), status_code=303)


async def config_secrets(request: Request) -> Response:
    user, err = _require(request, "superadmin")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    if str(form.get("base_hash", "")) != _env_hash():
        up, _ = await _mcp_status()
        body = _config_body(user, up, errors=["The .env file changed outside the GUI — reload and re-apply."])
        return HTMLResponse(_page("Config", body, user), status_code=409)
    updates: dict[str, str] = {}
    for key, _label in _SECRETS:
        val = str(form.get(key, "")).strip()
        if not val:
            continue
        if "#" in val or "\n" in val or "\r" in val:
            up, _ = await _mcp_status()
            body = _config_body(user, up, errors=["Secret values cannot contain '#' or newlines."])
            return HTMLResponse(_page("Config", body, user), status_code=400)
        updates[key] = val
    if not updates:
        return RedirectResponse("/config?msg=" + _q("No secrets changed"), status_code=303)
    try:
        _write_env(updates)
    except OSError as exc:
        up, _ = await _mcp_status()
        body = _config_body(user, up, errors=[f"Could not write .env: {exc}"])
        return HTMLResponse(_page("Config", body, user), status_code=409)
    return RedirectResponse("/config?msg=" + _q("Secrets updated — restart to apply"), status_code=303)


async def config_restart(request: Request) -> Response:
    user, err = _require(request, "superadmin")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, user):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), user), status_code=403)
    ok, detail = _restart_mcp()
    if ok:
        return RedirectResponse("/config?msg=" + _q(detail), status_code=303)
    return RedirectResponse("/config?err=" + _q("Restart failed: " + detail), status_code=303)


# ── Users (superadmin) ──────────────────────────────────────────────

async def users_page(request: Request) -> Response:
    user, err = _require(request, "superadmin")
    if err:
        return err
    trs = []
    for u in db.list_users():
        trs.append(
            f"<tr><td>{esc(u['username'])}</td><td>{esc(u['role'])}</td>"
            f"<td>{'yes' if u['must_change_password'] else 'no'}</td>"
            f"<td class='muted'>{esc(u['last_login'] or '')}</td>"
            f"<td><a href='/users?edit={esc(u['username'])}'>edit</a></td></tr>"
        )
    table = (
        "<div class='card'><div class='table-scroll'><table><tr><th>Username</th><th>Role</th><th>Must change pw</th>"
        "<th>Last login</th><th></th></tr>" + "".join(trs) + "</table></div></div>"
    )
    edit_name = request.query_params.get("edit", "")
    target = db.get_user_by_username(edit_name) if edit_name else None
    body = f'<div class="page-head"><h2>Users</h2></div>{table}{_user_form(target, user)}'
    return HTMLResponse(_page("Users", body, user, request.query_params.get("msg", "")))


def _user_form(target: dict[str, Any] | None, actor: dict[str, Any]) -> str:
    is_edit = target is not None
    username = target["username"] if target else ""
    role = target["role"] if target else "operator"
    csrf = _csrf(actor)
    role_opts = "".join(
        f"<option value='{r}' {'selected' if r == role else ''}>{r}</option>"
        for r in ("viewer", "operator", "superadmin")
    )
    heading = f"<h3>Edit user '{esc(username)}'</h3>" if is_edit else "<h3>Add user</h3>"
    name_field = (
        f'<input type="hidden" name="username" value="{esc(username)}"><label>Username</label>{esc(username)}<br>'
        if is_edit
        else '<label>Username</label><input type="text" name="username"><br>'
    )
    password_field = (
        '<label>Password</label><input type="password" name="password" placeholder="leave empty = unchanged"><br>'
        if is_edit
        else '<label>Password</label><input type="password" name="password"><br>'
    )
    form = (
        f"{heading}<form method='post' action='/users/save'>"
        f'<input type="hidden" name="csrf" value="{csrf}">{name_field}{password_field}'
        f'<label>Role</label><select name="role">{role_opts}</select><br>'
        f"<button type='submit'>{'Save' if is_edit else 'Add'}</button></form>"
    )
    if is_edit and target["id"] != actor["id"]:
        form += (
            f'<form method="post" action="/users/delete" '
            f'onsubmit="return confirm(\'Delete user {esc(username)}?\')">'
            f'<input type="hidden" name="username" value="{esc(username)}">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<button type="submit">Delete</button></form>'
        )
    return f'<div class="card">{form}</div>'


async def user_save(request: Request) -> Response:
    actor, err = _require(request, "superadmin")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, actor):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), actor), status_code=403)
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    role = str(form.get("role", "operator")).strip()
    if role not in RANKS:
        role = "operator"
    existing = db.get_user_by_username(username)
    if existing is None:
        if not username or len(password) < 8:
            return RedirectResponse("/users?msg=" + _q("Username + password (>=8) required"), status_code=303)
        db.create_user(username, password, role)
        return RedirectResponse("/users?msg=" + _q("User created: " + username), status_code=303)
    # prevent demoting the last superadmin
    if existing["role"] == "superadmin" and role != "superadmin":
        others = [u for u in db.list_users() if u["role"] == "superadmin" and u["id"] != existing["id"]]
        if not others:
            return RedirectResponse("/users?msg=" + _q("Cannot demote the last superadmin"), status_code=303)
    db.set_user_role(existing["id"], role)
    if password:
        if len(password) < 8:
            return RedirectResponse("/users?msg=" + _q("Password must be >= 8 chars"), status_code=303)
        db.set_user_password(existing["id"], password)
    return RedirectResponse("/users?msg=" + _q("User updated: " + username), status_code=303)


async def user_delete(request: Request) -> Response:
    actor, err = _require(request, "superadmin")
    if err:
        return err
    form = await request.form()
    if not _check_csrf(form, actor):
        return HTMLResponse(_page("Forbidden", _alert("Bad CSRF token"), actor), status_code=403)
    username = str(form.get("username", "")).strip()
    target = db.get_user_by_username(username)
    if target and target["id"] != actor["id"]:
        if target["role"] == "superadmin":
            others = [u for u in db.list_users() if u["role"] == "superadmin" and u["id"] != target["id"]]
            if not others:
                return RedirectResponse("/users?msg=" + _q("Cannot delete the last superadmin"), status_code=303)
        db.delete_user(target["id"])
        return RedirectResponse("/users?msg=" + _q("User deleted: " + username), status_code=303)
    return RedirectResponse("/users?msg=" + _q("Cannot delete that user"), status_code=303)


# ── Admin's own health ──────────────────────────────────────────────

async def admin_health(request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "ruckus-admin", "db": str(db.default_db_path())})


# ── App + entrypoint ────────────────────────────────────────────────

routes = [
    Route("/", lambda r: RedirectResponse("/dashboard", status_code=303)),
    Route("/health", admin_health, methods=["GET"]),
    Route("/login", login_page, methods=["GET"]),
    Route("/login", login_submit, methods=["POST"]),
    Route("/logout", logout, methods=["GET"]),
    Route("/change-password", change_password_page, methods=["GET"]),
    Route("/change-password", change_password_submit, methods=["POST"]),
    Route("/dashboard", dashboard, methods=["GET"]),
    Route("/keys", keys_page, methods=["GET"]),
    Route("/keys", key_add, methods=["POST"]),
    Route("/keys/update", key_update, methods=["POST"]),
    Route("/keys/delete", key_delete, methods=["POST"]),
    Route("/keys/regenerate", key_regenerate, methods=["POST"]),
    Route("/inventory", inventory_page, methods=["GET"]),
    Route("/inventory/save", inventory_save, methods=["POST"]),
    Route("/inventory/delete", inventory_delete, methods=["POST"]),
    Route("/audit", audit_page, methods=["GET"]),
    Route("/config", config_page, methods=["GET"]),
    Route("/config/save", config_save, methods=["POST"]),
    Route("/config/secrets", config_secrets, methods=["POST"]),
    Route("/config/restart", config_restart, methods=["POST"]),
    Route("/users", users_page, methods=["GET"]),
    Route("/users/save", user_save, methods=["POST"]),
    Route("/users/delete", user_delete, methods=["POST"]),
]

app = Starlette(routes=routes)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def main() -> None:
    host = os.getenv("MCP_ADMIN_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_ADMIN_PORT", "8001"))
    created = db.ensure_default_admin()
    if created:
        print(f"[ruckus-admin] created default superadmin: {created[0]} / {created[1]}", flush=True)
    print(f"[ruckus-admin] listening on http://{host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

