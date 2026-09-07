#!/usr/bin/env python3
"""
Ruckus MCP Server — MCP for Ruckus Infrastructure
vSZ Controller (REST API) + ICX Switch (SSH)

Supported transports (MCP_TRANSPORT env var):
  streamable-http  — Streamable HTTP (default, recommended for production)
  sse              — Server-Sent Events (legacy, still supported)

Security (HTTP transports only):
  MCP_API_KEY      — Bearer token required on every request (fallback single key)
  MCP_ALLOWED_IPS  — Comma-separated CIDR allowlist for client IPs
  SQLite (data/admin.db) — per-client API keys (name, allowlist, destructive) + audit
Health:
  GET /health      — public JSON status (used by the admin GUI + external monitors)
"""
from __future__ import annotations

import ipaddress
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastmcp import FastMCP
from starlette.responses import JSONResponse

import db
from security import (
    AuditLogger,
    AuditMiddleware,
    ClientIdentity,
    KeyStore,
    set_client_identity,
    set_client_ip,
)
from tools import register_all_tools

BASE_DIR = Path(__file__).resolve().parent
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    with _env_path.open("r", encoding="utf-8") as _f:
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

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("ruckus-mcp")

# ── Log noise control ──────────────────────────────────────────────
# mcp.server.lowlevel.server and paramiko.transport emit an INFO line for
# every MCP request and SSH session. Silence them to WARNING (keep real
# warnings/errors) unless LOG_LEVEL=DEBUG is requested for full detail.
if os.getenv("LOG_LEVEL", "INFO").upper() != "DEBUG":
    for _noisy in ("mcp.server.lowlevel.server", "paramiko.transport"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)

mcp = FastMCP("Ruckus MCP")
register_all_tools(mcp)

_START_TIME = time.time()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Any) -> JSONResponse:
    """Public JSON status endpoint (no API key required)."""
    try:
        tool_count = len(await mcp.list_tools())
    except Exception:  # noqa: BLE001 - never fail health on a listing error
        tool_count = 0
    info = db.health_info()
    return JSONResponse(
        {
            "status": "ok",
            "service": "mcp-ruckus",
            "uptime_s": round(time.time() - _START_TIME, 1),
            "tool_count": tool_count,
            **info,
        }
    )


# ── Security Middleware ─────────────────────────────────────────────

def _parse_allowed_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = os.getenv("MCP_ALLOWED_IPS", "").strip()
    if not raw:
        return []
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in raw.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Invalid CIDR in MCP_ALLOWED_IPS: %r — ignored", cidr)
    return networks


class SecurityMiddleware:
    """ASGI middleware enforcing per-client API keys and IP allowlist.

    Pure ASGI callable — streaming-safe (SSE, chunked HTTP).
    Resolves the Bearer token against the SQLite-backed key registry (with the
    MCP_API_KEY fallback), then stores the identity for AuditMiddleware.
    The ``/health`` route is exempt so external monitors can poll it.
    """

    EXEMPT_PREFIXES = ("/health",)

    def __init__(
        self,
        app: Any,
        keystore: KeyStore,
        fallback_key: str,
        allowed_networks: list,
    ) -> None:
        self.app = app
        self.keystore = keystore
        self.fallback_key = fallback_key
        self.allowed_networks = allowed_networks
        self._enforce_ip = bool(allowed_networks)
        self._enforce_key = keystore.has_keys() or bool(fallback_key)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(self.EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        client_host: str | None = None
        if self._enforce_ip:
            client = scope.get("client")
            client_host = client[0] if client else None
            if not client_host:
                await self._respond(send, 403, "Forbidden: no client IP")
                return
            try:
                client_ip = ipaddress.ip_address(client_host)
                if not any(client_ip in net for net in self.allowed_networks):
                    logger.warning("Rejected %s: not in MCP_ALLOWED_IPS", client_host)
                    await self._respond(send, 403, "Forbidden: IP not allowed")
                    return
            except ValueError:
                await self._respond(send, 403, "Forbidden: invalid client IP")
                return
        set_client_ip(client_host)

        identity: ClientIdentity | None = None
        if self._enforce_key:
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            if not auth.startswith("Bearer "):
                await self._respond(send, 401, "Unauthorized: missing Bearer token")
                return
            token = auth[7:].strip()
            identity = self.keystore.resolve(token)
            if identity is None and self.fallback_key and token == self.fallback_key:
                identity = ClientIdentity(
                    name="default", key=token, allow_destructive=True
                )
            if identity is None:
                await self._respond(send, 401, "Unauthorized: invalid API key")
                return
        set_client_identity(identity)

        await self.app(scope, receive, send)

    @staticmethod
    async def _respond(send: Any, status: int, body: str) -> None:
        encoded = body.encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(encoded)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": encoded, "more_body": False})


# ── Entry Point ────────────────────────────────────────────────────

def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http").strip().lower()
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))

    if transport not in ("sse", "streamable-http"):
        logger.error("Unknown MCP_TRANSPORT=%r", transport)
        raise SystemExit(1)

    api_key = os.getenv("MCP_API_KEY", "").strip()
    allowed = _parse_allowed_networks()
    keystore = KeyStore()

    # Audit middleware records every tool call (identity-aware, SQLite-backed).
    mcp.add_middleware(AuditMiddleware(AuditLogger()))

    if keystore.has_keys() or api_key or allowed:
        logger.info(
            "Security: api_keys=%d, fallback_key=%s, allowed_networks=%d entries",
            db.count_api_keys(),
            "yes" if api_key else "no",
            len(allowed),
        )

    # Build the ASGI app (SSE or streamable-http)
    app = mcp.http_app(transport=transport)

    # Wrap with security middleware if configured
    if keystore.has_keys() or api_key or allowed:
        app = SecurityMiddleware(app, keystore, api_key, allowed)

    logger.info("Starting Ruckus MCP (%s) on %s:%d", transport, host, port)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=os.getenv("LOG_LEVEL", "info").upper() == "DEBUG",
    )


if __name__ == "__main__":
    main()
