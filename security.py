"""Per-client API keys, tool allowlists, and audit logging for the MCP server.

Provides:
  - ``KeyStore`` — live per-client key registry backed by SQLite.
  - ``ClientIdentity`` — the resolved identity of a connecting client.
  - ``AuditLogger`` — writes tool-call events to the SQLite audit log.
  - ``AuditMiddleware`` — FastMCP middleware that enforces per-key tool scope
    and destructive-tool gating, then records every tool call to the audit log.
"""
from __future__ import annotations

import contextvars
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import Tool, ToolResult

import db

logger = logging.getLogger(__name__)

_SENSITIVE_KEY_RE = re.compile(r"(pass|secret|token|apikey|api_key)", re.IGNORECASE)

# Tools that mutate infrastructure (require confirm=True inside the tool).
# This list must stay in sync with DOCS_SAFETY.md.
DESTRUCTIVE_TOOLS = frozenset(
    {
        "apply_rf_recommendation",
        "apply_ap_config",
        "create_wlan",
        "modify_wlan",
        "reboot_ap",
        "disconnect_client",
        "toggle_wlan",
        "ruckus_device_port_state",
        "ruckus_device_vlan_create",
        "ruckus_device_vlan_delete",
        "ruckus_device_vlan_port",
        "ruckus_device_poe_port",
        "ruckus_device_ip_route",
        "ruckus_device_ip_route_delete",
        "ruckus_device_ipv6_route",
        "ruckus_device_ipv6_route_delete",
        "ruckus_device_ipv6_unicast_routing",
        "ruckus_device_timezone_set",
        "ruckus_device_clock_set",
        "ruckus_device_ntp_server",
        "ruckus_device_ntp_control",
        "ruckus_device_config_save",
    }
)


@dataclass(frozen=True)
class ClientIdentity:
    """Resolved identity for one API key."""

    name: str
    key: str = field(repr=False, compare=False)
    allowed_tools: frozenset[str] = frozenset()
    allow_destructive: bool = False

    def can_call(self, tool_name: str) -> bool:
        """Return True if this identity may call the given tool."""
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        if tool_name in DESTRUCTIVE_TOOLS and not self.allow_destructive:
            return False
        return True

    def deny_reason(self, tool_name: str) -> str:
        """Return a human-readable reason the tool call is denied."""
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return f"tool {tool_name!r} not in allowed_tools for key {self.name!r}"
        if tool_name in DESTRUCTIVE_TOOLS and not self.allow_destructive:
            return f"tool {tool_name!r} is destructive; key {self.name!r} lacks allow_destructive"
        return "access denied"


class KeyStore:
    """Live per-client API key registry backed by SQLite.

    Keys are resolved per request (a cheap DB lookup), so admin edits take
    effect immediately with no restart and no reload machinery.
    """

    def resolve(self, token: str) -> ClientIdentity | None:
        """Resolve a Bearer token to a ClientIdentity (or None)."""
        row = db.get_api_key_by_key(token)
        if not row:
            return None
        return ClientIdentity(
            name=row["name"],
            key=row["key"],
            allowed_tools=frozenset(row["allowed_tools"]),
            allow_destructive=row["allow_destructive"],
        )

    def has_keys(self) -> bool:
        """Return True if at least one client key is registered."""
        return db.count_api_keys() > 0


# ── Per-request identity (set by SecurityMiddleware, read by AuditMiddleware) ──

_client_identity: contextvars.ContextVar[ClientIdentity | None] = contextvars.ContextVar(
    "ruckus_client_identity", default=None
)
_client_ip: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ruckus_client_ip", default=None
)


def set_client_identity(identity: ClientIdentity | None) -> None:
    """Store the resolved client identity for the current request."""
    _client_identity.set(identity)


def set_client_ip(client_ip: str | None) -> None:
    """Store the client IP for the current request."""
    _client_ip.set(client_ip)


def get_client_identity() -> ClientIdentity | None:
    """Return the resolved client identity for the current request (or None)."""
    return _client_identity.get()


def get_client_ip() -> str | None:
    """Return the client IP for the current request (or None)."""
    return _client_ip.get()


def _redact_args(args: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of args with sensitive values redacted and long values truncated."""
    if not args:
        return {}
    out: dict[str, Any] = {}
    for key, value in args.items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            out[key] = "[redacted]"
        elif isinstance(value, str) and len(value) > 200:
            out[key] = value[:200] + "..."
        else:
            out[key] = value
    return out


class AuditLogger:
    """Write tool-call events to the SQLite audit log."""

    def log(
        self,
        *,
        client: str,
        tool: str,
        args: dict[str, Any] | None,
        outcome: str,
        duration_ms: float,
        client_ip: str | None = None,
        reason: str = "",
    ) -> None:
        """Insert one audit record (never raises — audit must not break tools)."""
        try:
            db.insert_audit(
                client=client,
                tool=tool,
                args=_redact_args(args),
                outcome=outcome,
                duration_ms=round(duration_ms, 2),
                client_ip=client_ip,
                destructive=tool in DESTRUCTIVE_TOOLS,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001 - audit failure must not fail the tool
            logger.warning("audit log write failed: %s", exc)


class AuditMiddleware(Middleware):
    """Enforce per-key tool scope and record every tool call to the audit log."""

    def __init__(self, audit: AuditLogger) -> None:
        self.audit = audit

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        args = context.message.arguments or {}
        identity = get_client_identity()
        client = identity.name if identity else "anonymous"

        if identity is not None and not identity.can_call(tool_name):
            reason = identity.deny_reason(tool_name)
            logger.warning("Audit: denied %s -> %s (%s)", client, tool_name, reason)
            self.audit.log(
                client=client,
                tool=tool_name,
                args=args,
                outcome="denied",
                duration_ms=0.0,
                client_ip=get_client_ip(),
                reason=reason,
            )
            return ToolResult(content=f"Access denied: {reason}", is_error=True)

        start = time.perf_counter()
        try:
            result = await call_next(context)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self.audit.log(
                client=client,
                tool=tool_name,
                args=args,
                outcome="exception",
                duration_ms=duration_ms,
                client_ip=get_client_ip(),
                reason=str(exc),
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        self.audit.log(
            client=client,
            tool=tool_name,
            args=args,
            outcome=self._outcome(result),
            duration_ms=duration_ms,
            client_ip=get_client_ip(),
        )
        return result

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        """Filter the tool list to what the current key may actually call."""
        tools = await call_next(context)
        identity = get_client_identity()
        if identity is None:
            return tools
        return [tool for tool in tools if identity.can_call(tool.name)]

    @staticmethod
    def _outcome(result: ToolResult) -> str:
        """Classify a tool result as ok/error."""
        if getattr(result, "is_error", False):
            return "error"
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict) and "error" in structured:
            return "error"
        return "ok"
