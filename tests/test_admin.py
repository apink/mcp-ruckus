"""Tests for the admin GUI (auth, role gating, key management)."""
from __future__ import annotations

import re

import pytest
from starlette.testclient import TestClient

import admin
import db
from admin import app


def _client() -> TestClient:
    return TestClient(app)


def _create_user(username: str, password: str, role: str, must_change: bool = False) -> None:
    db.create_user(username, password, role)
    if not must_change:
        db.clear_must_change(db.get_user_by_username(username)["id"])


def _login(client: TestClient, username: str, password: str) -> TestClient:
    client.post("/login", data={"username": username, "password": password})
    return client


def _csrf_from(page_html: str) -> str:
    match = re.search(r'name="csrf" value="([0-9a-f]{16})"', page_html)
    assert match, "csrf token not found in page"
    return match.group(1)


@pytest.fixture
def operator_client():
    _create_user("op", "password1", "operator")
    client = _client()
    _login(client, "op", "password1")
    return client


@pytest.fixture
def superadmin_client():
    _create_user("root", "password1", "superadmin")
    client = _client()
    _login(client, "root", "password1")
    return client


class TestHealth:
    def test_health_public(self):
        resp = _client().get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestLogin:
    def test_anonymous_redirects_to_login(self):
        resp = _client().get("/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/login" in resp.headers["location"]

    def test_bad_credentials(self):
        _create_user("op", "password1", "operator")
        resp = _client().post("/login", data={"username": "op", "password": "wrong"},
                              follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "Invalid" in resp.headers["location"]

    def test_good_login_sets_session(self):
        _create_user("op", "password1", "operator")
        client = _client()
        resp = client.post("/login", data={"username": "op", "password": "password1"},
                           follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "ruckus_admin" in client.cookies

    def test_forced_password_change(self):
        _create_user("op", "password1", "operator", must_change=True)
        client = _client()
        resp = client.post("/login", data={"username": "op", "password": "password1"},
                           follow_redirects=False)
        assert "/change-password" in resp.headers["location"]

    def test_change_password_flow(self):
        _create_user("op", "password1", "operator", must_change=True)
        client = _client()
        _login(client, "op", "password1")
        resp = client.post("/change-password",
                           data={"new_password": "newpass123", "confirm": "newpass123"},
                           follow_redirects=False)
        assert resp.status_code in (302, 303)
        user = db.get_user_by_username("op")
        assert user["must_change_password"] == 0
        assert db.verify_password("newpass123", user["password_hash"])


class TestRoleGating:
    def test_viewer_cannot_view_users(self):
        _create_user("viewer", "password1", "viewer")
        client = _client()
        _login(client, "viewer", "password1")
        resp = client.get("/users")
        assert resp.status_code == 403

    def test_operator_can_view_keys(self, operator_client):
        resp = operator_client.get("/keys")
        assert resp.status_code == 200
        assert "API Keys" in resp.text

    def test_superadmin_can_view_users(self, superadmin_client):
        resp = superadmin_client.get("/users")
        assert resp.status_code == 200
        assert "Users" in resp.text


class TestApiKeyManagement:
    def test_operator_creates_key(self, operator_client):
        page = operator_client.get("/keys").text
        csrf = _csrf_from(page)
        resp = operator_client.post(
            "/keys",
            data={"csrf": csrf, "name": "monitor", "tool": ["ap_status", "ap_down"]},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        key = db.get_api_key_by_name("monitor")
        assert key is not None
        assert key["allowed_tools"] == ["ap_status", "ap_down"]
        assert key["allow_destructive"] is False

    def test_bad_csrf_rejected(self, operator_client):
        resp = operator_client.post(
            "/keys", data={"csrf": "0000000000000000", "name": "x"}, follow_redirects=False
        )
        assert resp.status_code == 403

    def test_viewer_cannot_create_key(self):
        _create_user("viewer", "password1", "viewer")
        client = _client()
        _login(client, "viewer", "password1")
        resp = client.post("/keys", data={"name": "x"}, follow_redirects=False)
        assert resp.status_code == 403


class TestConfig:
    def _isolate_env(self, monkeypatch, tmp_path):
        p = tmp_path / ".env"
        monkeypatch.setattr(admin, "_env_file", lambda: p)
        return p

    def _base_hash(self):
        return admin._env_hash()

    def test_superadmin_sees_edit_forms(self, superadmin_client):
        resp = superadmin_client.get("/config")
        assert resp.status_code == 200
        assert "/config/save" in resp.text
        assert "/config/secrets" in resp.text
        assert "/config/restart" in resp.text

    def test_viewer_readonly(self):
        _create_user("viewer2", "password1", "viewer")
        client = _client()
        _login(client, "viewer2", "password1")
        resp = client.get("/config")
        assert resp.status_code == 200
        assert "/config/save" not in resp.text

    def test_save_settings_writes_env(self, superadmin_client, monkeypatch, tmp_path):
        p = self._isolate_env(monkeypatch, tmp_path)
        p.write_text("VSZ_PORT=8443\n", encoding="utf-8")
        page = superadmin_client.get("/config").text
        csrf = _csrf_from(page)
        resp = superadmin_client.post(
            "/config/save",
            data={
                "csrf": csrf,
                "base_hash": self._base_hash(),
                "VSZ_HOST": "10.0.0.5",
                "VSZ_PORT": "8443",
                "VSZ_USER": "admin",
                "VSZ_API_VERSION": "v11_1",
                "VSZ_RATE_LIMIT": "10",
                "ICX_RATE_LIMIT": "5",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_PORT": "8000",
                "MCP_HOST": "0.0.0.0",
                "LOG_LEVEL": "INFO",
                "MCP_MAX_ITEMS": "50",
                "MCP_ALLOWED_IPS": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert "VSZ_HOST=10.0.0.5" in p.read_text(encoding="utf-8")

    def test_save_settings_validation_error(self, superadmin_client, monkeypatch, tmp_path):
        self._isolate_env(monkeypatch, tmp_path)
        page = superadmin_client.get("/config").text
        csrf = _csrf_from(page)
        resp = superadmin_client.post(
            "/config/save",
            data={
                "csrf": csrf,
                "base_hash": self._base_hash(),
                "VSZ_HOST": "",
                "VSZ_PORT": "notanumber",
                "VSZ_USER": "",
                "VSZ_API_VERSION": "",
                "VSZ_RATE_LIMIT": "10",
                "ICX_RATE_LIMIT": "5",
                "MCP_TRANSPORT": "streamable-http",
                "MCP_PORT": "8000",
                "MCP_HOST": "0.0.0.0",
                "LOG_LEVEL": "INFO",
                "MCP_MAX_ITEMS": "50",
                "MCP_ALLOWED_IPS": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400
        assert "must be an integer" in resp.text

    def test_secret_write_only(self, superadmin_client, monkeypatch, tmp_path):
        p = self._isolate_env(monkeypatch, tmp_path)
        p.write_text("VSZ_PASS=oldsecret\n", encoding="utf-8")
        page = superadmin_client.get("/config").text
        csrf = _csrf_from(page)
        resp = superadmin_client.post(
            "/config/secrets",
            data={"csrf": csrf, "base_hash": self._base_hash(), "VSZ_PASS": "newsecret"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        content = p.read_text(encoding="utf-8")
        assert "VSZ_PASS=newsecret" in content
        assert "oldsecret" not in content

    def test_restart_calls_systemctl(self, superadmin_client, monkeypatch):
        calls: dict = {}

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(args, **kwargs):
            calls["args"] = args
            return _Proc()

        monkeypatch.setattr(admin.subprocess, "run", fake_run)
        page = superadmin_client.get("/config").text
        csrf = _csrf_from(page)
        resp = superadmin_client.post(
            "/config/restart", data={"csrf": csrf}, follow_redirects=False
        )
        assert resp.status_code in (302, 303)
        assert calls["args"] == ["systemctl", "restart", "mcp-ruckus"]
