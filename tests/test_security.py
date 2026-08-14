"""Tests for SecurityMiddleware."""
from __future__ import annotations

import ipaddress
from typing import Any

from server import SecurityMiddleware, _parse_allowed_networks


def _noop_app(scope: dict, recv: Any, send: Any) -> None:
    return None


class TestParseAllowedNetworks:
    def test_empty(self):
        import os
        os.environ["MCP_ALLOWED_IPS"] = ""
        result = _parse_allowed_networks()
        assert result == []

    def test_single_cidr(self):
        import os
        os.environ["MCP_ALLOWED_IPS"] = "10.0.0.0/8"
        result = _parse_allowed_networks()
        assert len(result) == 1
        assert isinstance(result[0], ipaddress.IPv4Network)

    def test_multiple_cidr(self):
        import os
        os.environ["MCP_ALLOWED_IPS"] = "10.0.0.0/8,192.168.1.0/24"
        result = _parse_allowed_networks()
        assert len(result) == 2

    def test_invalid_cidr_skipped(self):
        import os
        os.environ["MCP_ALLOWED_IPS"] = "invalid,10.0.0.0/8"
        result = _parse_allowed_networks()
        assert len(result) == 1


class TestSecurityMiddleware:
    def test_init(self):
        app = _noop_app
        mw = SecurityMiddleware(app, "secret", [ipaddress.ip_network("10.0.0.0/8")])
        assert mw.api_key == "secret"
        assert mw._enforce_key is True
        assert mw._enforce_ip is True

    def test_no_config(self):
        app = _noop_app
        mw = SecurityMiddleware(app, "", [])
        assert mw._enforce_key is False
        assert mw._enforce_ip is False
