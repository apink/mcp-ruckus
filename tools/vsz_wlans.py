"""vSZ WLAN/SSID tools — CRUD, RADIUS profile listing."""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter
from tools._response import list_result

logger = logging.getLogger(__name__)


async def _ssid_list(zone_id: str) -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    wlans = await adapter.get_wlans_by_zone(zone_id)
    rows = [
        {"ssid": w.get("ssid", ""), "name": w.get("name", ""), "id": w.get("id", ""), "zone_id": w.get("zoneId", "")}
        for w in wlans
    ]
    return list_result(rows, hint="use ssid_detail(wlan_id=..., zone_id=...) for full config")


async def _ssid_list_all() -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    zones = await adapter.get_zones()
    all_ssids = []
    for zone in zones:
        zone_id = str(zone.get("id", ""))
        zone_name = zone.get("name", "")
        if zone_id:
            wlans = await adapter.get_wlans_by_zone(zone_id)
            for w in wlans:
                all_ssids.append({
                    "ssid": w.get("ssid", ""),
                    "name": w.get("name", ""),
                    "id": w.get("id", ""),
                    "zone_id": zone_id,
                    "zone": zone_name,
                })
    return list_result(all_ssids, hint="use ssid_detail(wlan_id=..., zone_id=...) for full config")


async def _ssid_detail(wlan_id: str, zone_id: str) -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.get_wlan_detail(zone_id, wlan_id)
    enc = data.get("encryption", {})
    auth = data.get("authServiceOrProfile", {})
    vlan = data.get("vlan", {})
    adv = data.get("advancedOptions", {})
    return {
        "ssid": data.get("ssid", ""),
        "name": data.get("name", ""),
        "id": data.get("id", ""),
        "zone_id": data.get("zoneId", ""),
        "type": data.get("type", ""),
        "encryption_method": enc.get("method", ""),
        "encryption_algorithm": enc.get("algorithm", ""),
        "auth_service": auth.get("name", ""),
        "vlan_id": vlan.get("accessVlan", 0),
        "aaa_vlan_override": vlan.get("aaaVlanOverride", False),
        "max_clients_per_radio": adv.get("maxClientsPerRadio", 100),
        "client_idle_timeout": adv.get("clientIdleTimeoutSec", 120),
        "user_session_timeout": adv.get("userSessionTimeout", 0),
        "schedule": data.get("schedule", {}).get("type", "AlwaysOn"),
    }


async def _radius_list(zone_id: str, for_accounting: str = "all") -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    fa: bool | None = None
    if for_accounting == "auth_only":
        fa = False
    elif for_accounting == "accounting_only":
        fa = True
    servers = await adapter.get_radius_servers(zone_id, for_accounting=fa)
    out = []
    for s in servers:
        primary_ip = ""
        primary_port = 0
        secondary_ip = ""
        secondary_port = 0
        if s.get("primary"):
            primary_ip = s["primary"].get("ip", "")
            primary_port = s["primary"].get("port", 0)
        if s.get("secondary"):
            secondary_ip = s["secondary"].get("ip", "")
            secondary_port = s["secondary"].get("port", 0)
        out.append({
            "id": s.get("id", ""),
            "name": s.get("name", ""),
            "service_type": s.get("serviceType", ""),
            "description": s.get("description", ""),
            "zone_id": s.get("zoneId", ""),
            "primary_ip": primary_ip,
            "primary_port": primary_port,
            "has_secondary": bool(s.get("secondary")),
            "secondary_ip": secondary_ip or None,
            "secondary_port": secondary_port or None,
        })
    return list_result(out, hint="see ssid_list for WLANs")


async def _create_wlan(
    zone_id: str,
    name: str,
    ssid: str,
    encryption: str = "WPA2",
    passphrase: str = "",
    auth_type: str = "PSK",
    radius_profile: str = "",
    access_vlan: int = 1,
    description: str = "",
    hidden: bool = False,
    max_clients: int = 100,
    client_isolation: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {"error": "safety_latch", "detail": "confirm must be True to create WLAN"}

    if not zone_id:
        return {"error": "missing_zone_id", "detail": "zone_id is required"}
    if not name or len(name) > 32:
        return {"error": "invalid_name", "detail": "name must be 1-32 chars"}
    if not ssid or len(ssid) > 32:
        return {"error": "invalid_ssid", "detail": "ssid must be 1-32 chars"}
    if len(description) > 64:
        return {"error": "invalid_description", "detail": "description max 64 chars"}
    if not 1 <= access_vlan <= 4094:
        return {"error": "invalid_vlan", "detail": "access_vlan must be 1-4094"}
    if not 1 <= max_clients <= 512:
        return {"error": "invalid_max_clients", "detail": "max_clients must be 1-512"}

    valid_enc = {"WPA2", "WPA3", "WPA_Mixed", "WPA23_Mixed", "OWE", "OWE_Transition", "None"}
    if encryption not in valid_enc:
        return {"error": "invalid_encryption", "detail": f"encryption must be one of {valid_enc}"}

    if auth_type == "8021X":
        if not radius_profile:
            return {"error": "missing_radius", "detail": "radius_profile required for 8021X auth"}
    elif auth_type == "PSK":
        if not passphrase or len(passphrase) < 8:
            return {"error": "invalid_passphrase", "detail": "passphrase required (8-63 chars) for PSK"}
    elif auth_type != "none":
        return {"error": "invalid_auth_type", "detail": "auth_type must be PSK, 8021X, or none"}

    payload: dict[str, Any] = {
        "name": name,
        "ssid": ssid,
        "schedule": {"type": "AlwaysOn"},
    }

    if description:
        payload["description"] = description

    wlan_type = "standard"

    if auth_type == "8021X":
        wlan_type = "standard8021X"
        payload["authServiceOrProfile"] = {"name": radius_profile}
        enc = {"method": encryption if encryption != "None" else "WPA2", "algorithm": "AES", "mfp": "disabled"}
        payload["encryption"] = enc
    else:
        enc: dict[str, Any] = {"method": encryption}
        if encryption == "None":
            enc["method"] = "None"
        if auth_type == "PSK" and encryption in ("WPA2", "WPA_Mixed", "WPA3", "WPA23_Mixed"):
            enc["algorithm"] = "AES"
            enc["passphrase"] = passphrase
        if encryption == "OWE":
            enc["algorithm"] = "AES"
            enc["mfp"] = "required"
        payload["encryption"] = enc

    payload["vlan"] = {"accessVlan": access_vlan}

    adv: dict[str, Any] = {
        "hideSsidEnabled": hidden,
        "maxClientsPerRadio": max_clients,
        "clientIsolationEnabled": client_isolation,
    }
    payload["advancedOptions"] = adv

    logger.warning("create_wlan: zone=%s name=%s ssid=%s enc=%s auth=%s vlan=%d",
                   zone_id, name, ssid, encryption, auth_type, access_vlan)

    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}

    resp = await adapter.create_wlan(zone_id, payload, wlan_type=wlan_type)
    if "error" in resp:
        return resp

    return {
        "status": "created",
        "id": resp.get("id", ""),
        "name": name,
        "ssid": ssid,
        "zone_id": zone_id,
        "encryption": encryption,
        "auth_type": auth_type,
        "access_vlan": access_vlan,
        "hidden": hidden,
    }


async def _toggle_wlan(zone_id: str, wlan_id: str, enabled: bool, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {"error": "confirm_required", "detail": "Set confirm=True to toggle WLAN state"}
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = await adapter.enable_disable_wlan(zone_id, wlan_id, enabled)
    if "error" in data:
        return data
    return {
        "zone_id": zone_id,
        "wlan_id": wlan_id,
        "status": "enabled" if enabled else "disabled",
    }


async def _modify_wlan(
    zone_id: str,
    wlan_id: str,
    passphrase: str | None = None,
    encryption: str | None = None,
    access_vlan: int | None = None,
    description: str | None = None,
    hidden: bool | None = None,
    max_clients: int | None = None,
    client_isolation: bool | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {"error": "confirm_required", "detail": "Set confirm=True to modify WLAN config"}
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    updates: dict[str, Any] = {}
    if passphrase is not None:
        pass_len = len(passphrase)
        if pass_len and pass_len < 8:
            return {"error": "passphrase_too_short", "detail": f"Passphrase must be 8-63 chars, got {pass_len}"}
        updates["passphrase"] = passphrase
    if encryption is not None:
        updates["encryption"] = encryption
    if access_vlan is not None:
        updates["accessVlan"] = access_vlan
    if description is not None:
        updates["description"] = description
    if hidden is not None:
        updates["hideSsid"] = hidden
    if max_clients is not None:
        updates["maxClients"] = max_clients
    if client_isolation is not None:
        updates["clientIsolation"] = client_isolation
    if not updates:
        return {"error": "no_fields", "detail": "No fields provided to modify"}
    data = await adapter.modify_wlan(zone_id, wlan_id, updates)
    if "error" in data:
        return data
    return {
        "zone_id": zone_id,
        "wlan_id": wlan_id,
        "status": "modified",
        "updated_fields": list(updates.keys()),
    }


def register_tools(mcp: FastMCP) -> None:
    """Register vSZ WLAN management tools."""
    @mcp.tool()
    async def ssid_list(zone_id: str) -> dict[str, Any]:
        """List all SSIDs (WLANs) in a specific zone."""
        return await _ssid_list(zone_id)

    @mcp.tool()
    async def ssid_list_all() -> dict[str, Any]:
        """List all SSIDs across all zones."""
        return await _ssid_list_all()

    @mcp.tool()
    async def ssid_detail(wlan_id: str, zone_id: str) -> dict[str, Any]:
        """Get detailed config for a specific SSID (encryption, auth, VLAN)."""
        return await _ssid_detail(wlan_id, zone_id)

    @mcp.tool()
    async def radius_list(zone_id: str, for_accounting: str = "all") -> dict[str, Any]:
        """List RADIUS servers in a zone. Use to find valid auth profiles for 802.1X WLAN creation.

        Args:
            zone_id: Zone UUID.
            for_accounting: 'all', 'auth_only', or 'accounting_only'.
        """
        return await _radius_list(zone_id, for_accounting)

    @mcp.tool()
    async def create_wlan(
        zone_id: str,
        name: str,
        ssid: str,
        encryption: str = "WPA2",
        passphrase: str = "",
        auth_type: str = "PSK",
        radius_profile: str = "",
        access_vlan: int = 1,
        description: str = "",
        hidden: bool = False,
        max_clients: int = 100,
        client_isolation: bool = False,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Create a new WLAN (SSID) in a zone via vSZ API.

        Supports Open, WPA2/WPA3 PSK, and 802.1X (Enterprise) auth.
        802.1X uses the dedicated standard8021X endpoint.

        Args:
            zone_id: Zone UUID.
            name: WLAN name (1-32 chars).
            ssid: Broadcasted SSID string (1-32 chars).
            encryption: WPA2, WPA3, WPA_Mixed, WPA23_Mixed, OWE, or None.
            passphrase: PSK passphrase (8-63 chars). Required for PSK.
            auth_type: PSK, 8021X, or none.
            radius_profile: Auth service name for 802.1X (must exist in vSZ).
            access_vlan: Access VLAN ID (1-4094).
            description: WLAN description (max 64 chars).
            hidden: Hide SSID from broadcast (default False).
            max_clients: Max clients per radio (1-512, default 100).
            client_isolation: Block client-to-client traffic (default False).
            confirm: Must be True to execute.
        """
        return await _create_wlan(
            zone_id=zone_id, name=name, ssid=ssid, encryption=encryption,
            passphrase=passphrase, auth_type=auth_type, radius_profile=radius_profile,
            access_vlan=access_vlan, description=description, hidden=hidden,
            max_clients=max_clients, client_isolation=client_isolation, confirm=confirm,
        )

    @mcp.tool()
    async def toggle_wlan(zone_id: str, wlan_id: str, enabled: bool, confirm: bool = False) -> dict[str, Any]:
        """Enable or disable a WLAN (SSID) in a zone.

        Args:
            zone_id: Zone UUID.
            wlan_id: WLAN ID.
            enabled: True to enable, False to disable.
            confirm: Must be True to execute (safety latch).
        """
        return await _toggle_wlan(zone_id, wlan_id, enabled, confirm=confirm)

    @mcp.tool()
    async def modify_wlan(
        zone_id: str,
        wlan_id: str,
        passphrase: str | None = None,
        encryption: str | None = None,
        access_vlan: int | None = None,
        description: str | None = None,
        hidden: bool | None = None,
        max_clients: int | None = None,
        client_isolation: bool | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Modify an existing WLAN (SSID) configuration.

        Only provided fields are updated. Unspecified fields keep their current value.
        Uses vSZ PUT endpoint — full WLAN config is merged server-side.

        Args:
            zone_id: Zone UUID (required).
            wlan_id: WLAN ID to modify (required).
            passphrase: New PSK passphrase (8-63 chars).
            encryption: WPA2, WPA3, WPA_Mixed, WPA23_Mixed, OWE, or None.
            access_vlan: Access VLAN ID (1-4094).
            description: WLAN description text.
            hidden: Hide SSID from broadcast.
            max_clients: Max clients per radio (1-512).
            client_isolation: Block client-to-client traffic.
            confirm: Must be True to execute (safety latch).
        """
        return await _modify_wlan(
            zone_id=zone_id, wlan_id=wlan_id, passphrase=passphrase,
            encryption=encryption, access_vlan=access_vlan, description=description,
            hidden=hidden, max_clients=max_clients,
            client_isolation=client_isolation, confirm=confirm,
        )
