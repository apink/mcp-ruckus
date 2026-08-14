#!/usr/bin/env python3
"""pytest test suite for Ruckus MCP tools.
Run: pytest test_tools.py -v
"""

import os
import time
import pytest
from pathlib import Path

# Setup environment
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "#" in line:
                    line = line[:line.index("#")].strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    val = val.strip()
                    if val:
                        os.environ.setdefault(key.strip(), val)

from tools.vsz_aps import _ap_status as ap_status, _ap_detail as ap_detail
from tools.vsz_events import _alert_events as alert_events
from tools.vsz_clients import _client_roaming as client_roaming
from tools.icx_device import _device_info as device_info
from adapters.device_ssh import (
    _validate_port,
    _validate_mac,
    _validate_ipv4,
    _validate_vlan_id,
    _validate_ipv6,
)
from adapters.vsz import VsZRestAdapter

# Test categories
@pytest.mark.vsz
def test_vsz_ap_status():
    """Test vSZ AP status (basic connectivity)"""
    result = ap_status()
    assert isinstance(result, list), "ap_status should return list"
    if len(result) == 0:
        pytest.skip("vSZ returned empty (likely auth expired)")
    if "error" in result[0]:
        pytest.skip(f"vSZ login failed: {result[0]['error']}")

@pytest.mark.vsz
def test_vsz_ap_detail():
    """Test vSZ AP detail (valid AP name)"""
    result = ap_detail(ap_name="ap-001")
    if "error" in result:
        pytest.skip(f"vSZ ap_detail failed: {result.get('error')}")
    assert isinstance(result, dict), "ap_detail should return dict"
    assert "ap_name" in result, "ap_detail missing ap_name field"

@pytest.mark.vsz
def test_vsz_alert_events():
    """Test vSZ alert events (Critical)"""
    result = alert_events(limit=3, severity="Critical")
    if "error" in result:
        pytest.skip(f"vSZ alert_events failed: {result.get('error')}")
    # alert_events returns dict with paged response
    assert isinstance(result, dict), "alert_events should return dict"
    assert "totalCount" in result or len(result) > 0, "alert_events missing totalCount or empty"

@pytest.mark.vsz
def test_vsz_client_roaming():
    """Test vSZ client roaming"""
    result = client_roaming(query="user-001", limit=5)
    if "error" in result:
        pytest.skip(f"vSZ client_roaming failed: {result.get('error')}")
    assert isinstance(result, dict), "client_roaming should return dict"

@pytest.mark.icx
def test_icx_device_info():
    """Test ICX device info (valid device)"""
    result = device_info(host="203.0.113.1")
    assert "error" not in result, f"ICX device_info failed: {result.get('error')}"
    assert isinstance(result, dict), "device_info should return dict"
    assert "name" in result, "device_info missing name field"

@pytest.mark.security
def test_input_validation():
    """Test all input validators"""
    # Valid inputs
    _validate_port("1/1/1")
    _validate_mac("0200.1234.abcd")
    _validate_ipv4("203.0.113.1")
    _validate_vlan_id(100)
    _validate_ipv6("2001:db8::1")
    
    # Invalid inputs (should raise ValueError)
    with pytest.raises(ValueError):
        _validate_port("1/1/1; ls")
    with pytest.raises(ValueError):
        _validate_mac("aa11.bb22; show run")
    with pytest.raises(ValueError):
        _validate_ipv4("8.8.8.8; cat /etc/shadow")
    with pytest.raises(ValueError):
        _validate_vlan_id(0)
    with pytest.raises(ValueError):
        _validate_vlan_id(5000)
    with pytest.raises(ValueError):
        _validate_ipv6("2001:db8::1; ping")

@pytest.mark.reliability
def test_vsz_session_reuse():
    """Test vSZ session reuse (TTL)"""
    adapter = VsZRestAdapter()
    # First login
    result1 = adapter.login()
    assert "error" not in result1, "vSZ login failed"
    
    # Second call should reuse session
    result2 = adapter._ensure_login()
    assert result2.get("status") == "session_reused", "Session not reused"

@pytest.mark.reliability
def test_vsz_error_handling():
    """Test vSZ explicit error handling (unreachable)"""
    adapter = VsZRestAdapter()
    adapter.base_url = "https://192.0.2.1:8443"
    adapter._service_ticket = "fake"
    adapter._login_time = time.time()
    
    result = adapter._request("/rkszones")
    assert "error" in result, "vSZ should return explicit error"
    assert result["error"] == "network_error", f"Expected network_error, got {result['error']}"