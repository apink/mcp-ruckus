"""Tests for the real inventory manager (yaml + env var resolution)."""
from __future__ import annotations

import yaml

import inventory.manager as inv


class TestResolveEnvVars:
    def test_replaces_var(self, monkeypatch):
        monkeypatch.setenv("ICX_USER", "admin")
        assert inv._resolve_env_vars("${ICX_USER}") == "admin"

    def test_missing_var_raises(self, monkeypatch):
        monkeypatch.delenv("NOPE_VAR_XYZ", raising=False)
        import pytest
        with pytest.raises(KeyError):
            inv._resolve_env_vars("${NOPE_VAR_XYZ}")

    def test_non_string_passthrough(self):
        assert inv._resolve_env_vars(123) == 123


class TestResolveCredentials:
    def test_resolves_password(self, monkeypatch):
        monkeypatch.setenv("ICX_PASS", "s3cret")
        device = {"host": "203.0.113.1", "password": "${ICX_PASS}"}
        out = inv._resolve_credentials(device)
        assert out["password"] == "s3cret"

    def test_missing_resets_empty(self, monkeypatch):
        monkeypatch.delenv("ICX_PASS_XYZ", raising=False)
        device = {"host": "203.0.113.1", "name": "sw1", "password": "${ICX_PASS_XYZ}"}
        out = inv._resolve_credentials(device)
        assert out["password"] == ""


class TestLoadInventory:
    def test_loads_devices(self, tmp_path, monkeypatch):
        yaml_file = tmp_path / "devices.yaml"
        yaml_file.write_text(yaml.safe_dump({
            "devices": [{"host": "203.0.113.1", "name": "sw1",
                         "username": "admin", "password": "pw"}],
        }))
        monkeypatch.setattr(inv, "INVENTORY_PATH", yaml_file)
        devices = inv._REAL_load_inventory()
        assert len(devices) == 1
        assert devices[0].host == "203.0.113.1"
        assert devices[0].name == "sw1"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(inv, "INVENTORY_PATH", tmp_path / "nope.yaml")
        assert inv._REAL_load_inventory() == []


class TestGetDeviceRecord:
    def test_found_by_name(self, monkeypatch):
        from models.ruckus import ICXDevice
        dev = ICXDevice(host="203.0.113.1", name="sw1")
        monkeypatch.setattr(inv, "load_inventory", lambda: [dev])
        rec = inv._REAL_get_device_record("sw1")
        assert rec is not None
        assert rec.host == "203.0.113.1"

    def test_found_by_host(self, monkeypatch):
        from models.ruckus import ICXDevice
        dev = ICXDevice(host="203.0.113.1", name="sw1")
        monkeypatch.setattr(inv, "load_inventory", lambda: [dev])
        rec = inv._REAL_get_device_record("203.0.113.1")
        assert rec is not None
        assert rec.name == "sw1"

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(inv, "load_inventory", lambda: [])
        assert inv._REAL_get_device_record("sw1") is None
