"""Tests for the SQLite storage layer."""
from __future__ import annotations

import db


class TestPasswords:
    def test_hash_and_verify(self):
        stored = db.hash_password("s3cret")
        assert stored.startswith("scrypt$")
        assert db.verify_password("s3cret", stored) is True
        assert db.verify_password("wrong", stored) is False

    def test_unique_salts(self):
        assert db.hash_password("x") != db.hash_password("x")

    def test_verify_garbage(self):
        assert db.verify_password("x", "not-a-hash") is False


class TestDefaultAdmin:
    def test_creates_superadmin_once(self):
        user, pw = db.ensure_default_admin()
        assert user == "admin"
        assert pw == db.DEFAULT_ADMIN_PASSWORD
        admin = db.get_user_by_username("admin")
        assert admin["role"] == "superadmin"
        assert admin["must_change_password"] == 1
        assert db.ensure_default_admin() is None

    def test_init_pass_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("MCP_ADMIN_INIT_PASS", "custom-init-pass")
        user, pw = db.ensure_default_admin()
        assert user == "admin"
        assert pw == "custom-init-pass"
        assert db.verify_password("custom-init-pass", db.get_user_by_username("admin")["password_hash"])


class TestUsers:
    def test_crud(self):
        db.create_user("op", "password1", "operator")
        u = db.get_user_by_username("op")
        assert u["role"] == "operator"
        db.set_user_role(u["id"], "viewer")
        assert db.get_user_by_username("op")["role"] == "viewer"
        db.set_user_password(u["id"], "newpass123")
        assert db.verify_password("newpass123", db.get_user_by_username("op")["password_hash"])
        db.delete_user(u["id"])
        assert db.get_user_by_username("op") is None

    def test_list_users(self):
        db.create_user("a", "password1", "viewer")
        db.create_user("b", "password1", "operator")
        names = [u["username"] for u in db.list_users()]
        assert names == ["a", "b"]


class TestApiKeys:
    def test_create_and_list(self):
        db.create_api_key("ro", "ruck_1", ["ap_status"], False)
        keys = db.list_api_keys()
        assert len(keys) == 1
        k = keys[0]
        assert k["name"] == "ro"
        assert k["allowed_tools"] == ["ap_status"]
        assert k["allow_destructive"] is False

    def test_lookup_by_key(self):
        db.create_api_key("ro", "ruck_1", [], True)
        k = db.get_api_key_by_key("ruck_1")
        assert k["name"] == "ro"
        assert k["allow_destructive"] is True
        assert db.get_api_key_by_key("missing") is None

    def test_update(self):
        db.create_api_key("ro", "ruck_1", [], False)
        assert db.update_api_key("ro", ["ap_status"], True) is True
        k = db.get_api_key_by_name("ro")
        assert k["allowed_tools"] == ["ap_status"]
        assert k["allow_destructive"] is True
        assert db.update_api_key("missing", [], False) is False

    def test_regenerate_and_delete(self):
        db.create_api_key("ro", "ruck_1", [], False)
        new_key = db.regenerate_api_key("ro")
        assert new_key and new_key != "ruck_1"
        assert db.get_api_key_by_key(new_key)["name"] == "ro"
        assert db.delete_api_key("ro") is True
        assert db.count_api_keys() == 0

    def test_new_api_key_prefix(self):
        key = db.new_api_key()
        assert key.startswith("ruck_")
        assert len(key) > 16


class TestAudit:
    def test_insert_and_query(self):
        db.insert_audit(client="alice", tool="ap_status", args={"zone_id": "z1"},
                        outcome="ok", duration_ms=5.0, client_ip="10.0.0.5")
        rows, total = db.query_audit()
        assert total == 1
        assert rows[0]["client"] == "alice"
        assert rows[0]["destructive"] == 0

    def test_query_filters(self):
        for i in range(3):
            db.insert_audit(client=f"c{i}", tool="ap_status", args=None,
                            outcome="ok", duration_ms=1.0)
        db.insert_audit(client="bad", tool="reboot_ap", args=None,
                        outcome="denied", duration_ms=0.0, destructive=True, reason="no")
        rows, total = db.query_audit(client="c1")
        assert total == 1
        assert rows[0]["client"] == "c1"
        rows, total = db.query_audit(outcome="denied")
        assert total == 1
        assert rows[0]["tool"] == "reboot_ap"
        assert rows[0]["destructive"] == 1

    def test_summary(self):
        db.insert_audit(client="a", tool="t", args=None, outcome="ok", duration_ms=1.0)
        db.insert_audit(client="a", tool="t", args=None, outcome="denied", duration_ms=0.0)
        summary = db.audit_summary()
        assert summary["total"] == 2
        assert summary["by_outcome"] == {"ok": 1, "denied": 1}


class TestHealthInfo:
    def test_counts(self):
        db.create_api_key("a", "ruck_1", [], False)
        db.ensure_default_admin()
        db.insert_audit(client="a", tool="t", args=None, outcome="ok", duration_ms=1.0)
        info = db.health_info()
        assert info["api_keys"] == 1
        assert info["users"] == 1
        assert info["audit_events"] == 1
        assert info["db_size_bytes"] > 0
