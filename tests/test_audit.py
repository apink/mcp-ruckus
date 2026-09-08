"""Tests for per-client API keys, tool scope, and audit logging."""
from __future__ import annotations

import asyncio
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult

import admin
import db
import security
from lean import LEAN_TOOLS
from security import AuditLogger, AuditMiddleware, ClientIdentity, KeyStore, set_client_identity


class TestClientIdentity:
    def test_all_tools_when_empty_allowlist(self):
        ident = ClientIdentity(name="a", key="k", allow_destructive=True)
        assert ident.can_call("ap_status") is True
        assert ident.can_call("reboot_ap") is True

    def test_allowlist_restricts(self):
        ident = ClientIdentity(name="a", key="k", allowed_tools=frozenset({"ap_status"}))
        assert ident.can_call("ap_status") is True
        assert ident.can_call("ap_down") is False

    def test_destructive_gate(self):
        ident = ClientIdentity(name="a", key="k")
        assert ident.can_call("ap_status") is True
        assert ident.can_call("reboot_ap") is False
        assert "destructive" in ident.deny_reason("reboot_ap")


class TestKeyStore:
    def test_resolve(self):
        db.create_api_key("alice", "k-abc", ["ap_status"], True)
        ident = KeyStore().resolve("k-abc")
        assert ident is not None
        assert ident.name == "alice"
        assert ident.allowed_tools == frozenset({"ap_status"})
        assert ident.allow_destructive is True

    def test_resolve_missing(self):
        assert KeyStore().resolve("nope") is None

    def test_has_keys(self):
        assert KeyStore().has_keys() is False
        db.create_api_key("a", "k1", [], False)
        assert KeyStore().has_keys() is True


class TestRedactArgs:
    def test_redacts_sensitive_keys(self):
        out = security._redact_args({"password": "s3cret", "api_token": "tok", "host": "10.0.0.1"})
        assert out["password"] == "[redacted]"
        assert out["api_token"] == "[redacted]"
        assert out["host"] == "10.0.0.1"

    def test_truncates_long_strings(self):
        out = security._redact_args({"blob": "x" * 300})
        assert out["blob"].endswith("...")
        assert len(out["blob"]) < 300

    def test_none_args(self):
        assert security._redact_args(None) == {}


class TestAuditLogger:
    def test_writes_to_db(self):
        AuditLogger().log(
            client="alice", tool="ap_status", args={"zone_id": "z1"},
            outcome="ok", duration_ms=12.3, client_ip="10.0.0.5",
        )
        rows, total = db.query_audit()
        assert total == 1
        r = rows[0]
        assert r["client"] == "alice"
        assert r["tool"] == "ap_status"
        assert r["outcome"] == "ok"
        assert r["duration_ms"] == 12.3
        assert r["destructive"] == 0
        assert r["client_ip"] == "10.0.0.5"

    def test_redacts_in_log(self):
        AuditLogger().log(
            client="alice", tool="create_wlan", args={"passphrase": "pw"},
            outcome="ok", duration_ms=1.0,
        )
        rows, _ = db.query_audit()
        assert "pw" not in rows[0]["args"]
        assert "[redacted]" in rows[0]["args"]


def _ctx(name: str, arguments: dict[str, Any] | None = None) -> MiddlewareContext:
    return MiddlewareContext(message=mt.CallToolRequestParams(name=name, arguments=arguments))


async def _never_called(ctx):
    raise AssertionError("call_next must not be invoked on deny")


def _last_audit() -> dict[str, Any]:
    rows, _ = db.query_audit(limit=1)
    return rows[0]


class TestAuditMiddleware:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_deny_unknown_tool(self):
        mw = AuditMiddleware(AuditLogger())
        ident = ClientIdentity(name="ro", key="k", allowed_tools=frozenset({"ap_status"}))

        async def run():
            set_client_identity(ident)
            return await mw.on_call_tool(_ctx("reboot_ap"), _never_called)

        result = self._run(run())
        assert result.is_error is True
        record = _last_audit()
        assert record["outcome"] == "denied"
        assert record["client"] == "ro"

    def test_deny_destructive_without_flag(self):
        mw = AuditMiddleware(AuditLogger())
        ident = ClientIdentity(name="ro", key="k")  # allow_destructive=False

        async def run():
            set_client_identity(ident)
            return await mw.on_call_tool(_ctx("reboot_ap"), _never_called)

        result = self._run(run())
        assert result.is_error is True

    def test_allow_and_record_ok(self):
        mw = AuditMiddleware(AuditLogger())
        ident = ClientIdentity(name="admin", key="k", allow_destructive=True)

        async def call_next(ctx):
            return ToolResult(structured_content={"items": []})

        async def run():
            set_client_identity(ident)
            return await mw.on_call_tool(_ctx("ap_status"), call_next)

        result = self._run(run())
        assert result.is_error is False
        record = _last_audit()
        assert record["outcome"] == "ok"
        assert record["client"] == "admin"

    def test_anonymous_identity(self):
        mw = AuditMiddleware(AuditLogger())

        async def call_next(ctx):
            return ToolResult(structured_content={"error": "confirm_required"})

        async def run():
            set_client_identity(None)
            return await mw.on_call_tool(_ctx("ap_status"), call_next)

        result = self._run(run())
        assert result.is_error is False
        record = _last_audit()
        assert record["client"] == "anonymous"
        assert record["outcome"] == "error"


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


def _list_ctx() -> MiddlewareContext:
    return MiddlewareContext(message=None)


class TestAuditMiddlewareListTools:
    def _call(self, identity: ClientIdentity | None, tools: list[_FakeTool]):
        mw = AuditMiddleware(AuditLogger())

        async def call_next(ctx):
            return tools

        async def run():
            set_client_identity(identity)
            return await mw.on_list_tools(_list_ctx(), call_next)

        return asyncio.run(run())

    def test_anonymous_returns_full_list(self):
        tools = [_FakeTool("ap_status"), _FakeTool("reboot_ap"), _FakeTool("client_search")]
        result = self._call(None, tools)
        assert [t.name for t in result] == ["ap_status", "reboot_ap", "client_search"]

    def test_allowlist_filters_list(self):
        ident = ClientIdentity(name="ro", key="k", allowed_tools=frozenset({"ap_status", "client_search"}))
        tools = [_FakeTool("ap_status"), _FakeTool("reboot_ap"), _FakeTool("client_search")]
        result = self._call(ident, tools)
        assert [t.name for t in result] == ["ap_status", "client_search"]

    def test_destructive_gate_hides_destructive(self):
        ident = ClientIdentity(name="ro", key="k")  # allow_destructive=False
        tools = [_FakeTool("ap_status"), _FakeTool("reboot_ap")]
        result = self._call(ident, tools)
        assert [t.name for t in result] == ["ap_status"]

    def test_empty_allowlist_returns_full_list(self):
        ident = ClientIdentity(name="admin", key="k", allow_destructive=True)
        tools = [_FakeTool("ap_status"), _FakeTool("reboot_ap")]
        result = self._call(ident, tools)
        assert [t.name for t in result] == ["ap_status", "reboot_ap"]


class TestLeanTools:
    def test_non_empty(self):
        assert len(LEAN_TOOLS) > 0

    def test_no_destructive_tools(self):
        assert not (LEAN_TOOLS & security.DESTRUCTIVE_TOOLS)

    def test_all_names_registered(self):
        all_names = {name for _, names in admin._tool_names_by_domain() for name in names}
        assert LEAN_TOOLS <= all_names
