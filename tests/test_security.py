"""Tests for SecurityMiddleware."""
from __future__ import annotations

import asyncio
import ipaddress
from typing import Any

from security import ClientIdentity, get_client_identity
from server import SecurityMiddleware, _parse_allowed_networks


class _FakeStore:
    """Stand-in for security.KeyStore with the same resolve/has_keys surface."""

    def __init__(self, identities: dict[str, ClientIdentity] | None = None) -> None:
        self._ids = identities or {}

    def resolve(self, token: str) -> ClientIdentity | None:
        return self._ids.get(token)

    def has_keys(self) -> bool:
        return bool(self._ids)


async def _noop_app(scope: dict, recv: Any, send: Any) -> None:
    return None


def _http_scope(headers: list[tuple[bytes, bytes]], client: tuple = None) -> dict:
    return {"type": "http", "headers": headers, "client": client}


class _CaptureSend:
    def __init__(self):
        self.status = None
        self.body = b""

    async def __call__(self, message: dict) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
        elif message["type"] == "http.response.body":
            self.body += message["body"]


class TestParseAllowedNetworks:
    def test_empty(self, monkeypatch):
        monkeypatch.setenv("MCP_ALLOWED_IPS", "")
        assert _parse_allowed_networks() == []

    def test_single_cidr(self, monkeypatch):
        monkeypatch.setenv("MCP_ALLOWED_IPS", "10.0.0.0/8")
        result = _parse_allowed_networks()
        assert len(result) == 1
        assert isinstance(result[0], ipaddress.IPv4Network)

    def test_multiple_cidr(self, monkeypatch):
        monkeypatch.setenv("MCP_ALLOWED_IPS", "10.0.0.0/8,192.168.1.0/24")
        assert len(_parse_allowed_networks()) == 2

    def test_invalid_cidr_skipped(self, monkeypatch):
        monkeypatch.setenv("MCP_ALLOWED_IPS", "invalid,10.0.0.0/8")
        assert len(_parse_allowed_networks()) == 1


class TestSecurityMiddleware:
    def _registry(self):
        return _FakeStore({"abc": ClientIdentity(name="alice", key="abc", allow_destructive=True)})

    def test_init(self):
        mw = SecurityMiddleware(_noop_app, self._registry(), "fallback", [ipaddress.ip_network("10.0.0.0/8")])
        assert mw.fallback_key == "fallback"
        assert mw._enforce_key is True
        assert mw._enforce_ip is True

    def test_no_config(self):
        mw = SecurityMiddleware(_noop_app, _FakeStore(), "", [])
        assert mw._enforce_key is False
        assert mw._enforce_ip is False

    async def _call(self, mw, scope):
        send = _CaptureSend()
        await mw(scope, None, send)
        return send

    def test_registry_key_resolves_identity(self):
        async def run():
            mw = SecurityMiddleware(_noop_app, self._registry(), "", [])
            send = await self._call(mw, _http_scope([(b"authorization", b"Bearer abc")]))
            assert send.status is None
            assert get_client_identity().name == "alice"

        asyncio.run(run())

    def test_fallback_key_resolves_default_identity(self):
        async def run():
            mw = SecurityMiddleware(_noop_app, _FakeStore(), "fallback", [])
            send = await self._call(mw, _http_scope([(b"authorization", b"Bearer fallback")]))
            assert send.status is None
            identity = get_client_identity()
            assert identity.name == "default"
            assert identity.allow_destructive is True

        asyncio.run(run())

    def test_unknown_key_rejected(self):
        async def run():
            mw = SecurityMiddleware(_noop_app, self._registry(), "", [])
            send = await self._call(mw, _http_scope([(b"authorization", b"Bearer nope")]))
            assert send.status == 401

        asyncio.run(run())

    def test_missing_bearer_rejected(self):
        async def run():
            mw = SecurityMiddleware(_noop_app, self._registry(), "", [])
            send = await self._call(mw, _http_scope([]))
            assert send.status == 401

        asyncio.run(run())

    def test_ip_allowlist_enforced(self):
        async def run():
            net = [ipaddress.ip_network("10.0.0.0/8")]
            mw = SecurityMiddleware(_noop_app, _FakeStore(), "", net)
            send = await self._call(mw, _http_scope([(b"authorization", b"Bearer x")], client=("8.8.8.8", 1)))
            assert send.status == 403

        asyncio.run(run())

    def test_health_exempt_from_key(self):
        async def run():
            mw = SecurityMiddleware(_noop_app, self._registry(), "", [])
            scope = {"type": "http", "headers": [], "client": ("8.8.8.8", 1), "path": "/health"}
            send = await self._call(mw, scope)
            assert send.status is None

        asyncio.run(run())
