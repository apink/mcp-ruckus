#!/usr/bin/env python3
"""
Ruckus MCP Server — MCP for Ruckus Infrastructure
vSZ Controller (REST API) + ICX Switch (SSH)

Supported transports (MCP_TRANSPORT env var):
  streamable-http  — Streamable HTTP (default, recommended for production)
  sse              — Server-Sent Events (legacy, still supported)

Security (HTTP transports only):
  MCP_API_KEY      — Bearer token required on every request
  MCP_ALLOWED_IPS  — Comma-separated CIDR allowlist for client IPs
"""
from __future__ import annotations

import ipaddress
import logging
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
from fastmcp import FastMCP

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

mcp = FastMCP("Ruckus MCP")
register_all_tools(mcp)


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
    """ASGI middleware enforcing API-key and IP-allowlist.

    Pure ASGI callable — streaming-safe (SSE, chunked HTTP).
    """

    def __init__(self, app: Any, api_key: str, allowed_networks: list) -> None:
        self.app = app
        self.api_key = api_key
        self.allowed_networks = allowed_networks
        self._enforce_ip = bool(allowed_networks)
        self._enforce_key = bool(api_key)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._enforce_ip:
            client = scope.get("client")
            client_host: str | None = client[0] if client else None
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

        if self._enforce_key:
            headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            if not auth.startswith("Bearer "):
                await self._respond(send, 401, "Unauthorized: missing Bearer token")
                return
            if auth[7:].strip() != self.api_key:
                await self._respond(send, 401, "Unauthorized: invalid API key")
                return

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

    if api_key or allowed:
        logger.info(
            "Security: api_key=%s, allowed_networks=%d entries",
            "yes" if api_key else "no",
            len(allowed),
        )

    # Build the ASGI app (SSE or streamable-http)
    app = mcp.http_app(transport=transport)

    # Wrap with security middleware if configured
    if api_key or allowed:
        app = SecurityMiddleware(app, api_key, allowed)

    logger.info("Starting Ruckus MCP (%s) on %s:%d", transport, host, port)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
