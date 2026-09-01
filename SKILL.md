---
name: ruckus-mcp
description: Ruckus wireless (vSZ) and switching (ICX) MCP server — 85 tools for AP monitoring, client analytics, RF optimization, WLAN management, switch management, PoE, LLDP, and diagnostics. Use when working with Ruckus vSZ or ICX infrastructure.
---

# Ruckus MCP Skill — 85 tools

## How to Install This Skill

This file (SKILL.md) is a ready-to-use skill for the Ruckus MCP server. Copy it to your agent's skill directory:

| Agent | Location |
|---|---|
| Hermes | `~/.hermes/skills/ruckus/SKILL.md` |
| OpenClaw | `~/.openclaw/skills/ruckus/SKILL.md` |
| Claude Code | `~/.claude/skills/ruckus/SKILL.md` |

Make sure the MCP server is running and registered in your agent before loading the skill (see [README.md](README.md) → "Connect your AI assistant").

## Connection

- **vSZ (async REST):** `.env` → `VSZ_HOST`, `VSZ_PORT`, `VSZ_USER`, `VSZ_PASS`, `VSZ_API_VERSION` (default v11_1). Rate limit: `VSZ_RATE_LIMIT=10`.
- **ICX (SSH, netmiko):** `inventory/devices.yaml` → `username`/`password` per device. `${ENV_VAR}` supported. Rate limit: `ICX_RATE_LIMIT=5` per device.
- **MCP server:** `MCP_TRANSPORT=streamable-http|sse` (default: streamable-http), `MCP_PORT=8000`, `MCP_API_KEY` (Bearer), `MCP_ALLOWED_IPS` (CIDR).

## Tool Summary

Full descriptions in [docs/TOOLS.md](docs/TOOLS.md).

```
vSZ (31): ap_status, ap_detail, ap_radio_stats, ap_down, client_search, ap_high_client_count,
          zone_status, zone_ap_list, license_status, radius_list, ssid_list, ssid_list_all,
          ssid_detail, create_wlan, alert_events, client_roaming, rogue_client_query, ap_neighbors,
          optimize_wifi_rf, apply_rf_recommendation, apply_ap_config, alarm_list, domain_list,
          toggle_wlan, modify_wlan, reboot_ap, disconnect_client, wlan_traffic_stats,
          ap_traffic_stats, zone_traffic_stats, controller_stats

ICX (42): ruckus_device_info, ruckus_device_status,
          ruckus_device_interfaces_summary, ruckus_device_interfaces_down,
          ruckus_device_interfaces_errors, ruckus_device_interfaces_stats,
          ruckus_device_ip_addresses, ruckus_device_ip_routes, ruckus_device_ip_route,
          ruckus_device_ip_route_delete, ruckus_device_ipv6_routes,
          ruckus_device_vlan_summary, ruckus_device_port_vlan, ruckus_device_mac_table_vlan,
          ruckus_device_find_mac, ruckus_device_lag_summary, ruckus_device_lldp_neighbors,
          ruckus_device_poe_status, ruckus_device_arp_table, ruckus_device_chassis_health,
          ruckus_device_ipv6_interfaces, ruckus_device_ping, ruckus_device_ping_ipv6,
          ruckus_device_traceroute, ruckus_device_traceroute_ipv6,
          ruckus_device_config_backup, ruckus_device_config_diff,
          ruckus_device_resources, ruckus_device_sfp_info, ruckus_device_cable_diag,
          ruckus_device_syslog, ruckus_device_optic_info, ruckus_device_time,
          ruckus_device_spanning_tree, ruckus_device_access_lists,
          ruckus_device_users, ruckus_device_ssh_status, ruckus_device_port_state,
          ruckus_device_vlan_create, ruckus_device_vlan_delete,
          ruckus_device_vlan_port,
          ruckus_device_poe_port

Inventory (3): ruckus_list_devices, ruckus_devices_by_location, ruckus_devices_by_role
Bulk (3): ruckus_all_device_info, ruckus_all_device_status, ruckus_all_device_backup
Connectivity (3): ping_device, check_port, http_latency
```

## Critical Rules

- **17 destructive tools require `confirm=True`**: `apply_rf_recommendation`, `apply_ap_config`, `create_wlan`, `modify_wlan`, `reboot_ap`, `disconnect_client`, `toggle_wlan`, `ruckus_device_port_state`, `ruckus_device_vlan_create`, `ruckus_device_vlan_delete`, `ruckus_device_vlan_port`, `ruckus_device_poe_port`, `ruckus_device_ip_route`, `ruckus_device_ip_route_delete`, `ruckus_device_ipv6_route`, `ruckus_device_ipv6_route_delete`, `ruckus_device_ipv6_unicast_routing`
- **Pick host by IP, not name** — names are not unique in `devices.yaml`
- **Error return format**: `{"error": "...", "detail": "..."}` — not exceptions
- **vSZ session TTL**: 10 minutes, auto re-login
- **Large scale**: 1000 AP → `ap_status` needs 20+ serial calls. Use zone filters and limits.
- **List tools return an envelope**: `{"items", "total", "returned", "truncated", "hint"}`. If `truncated=true`, drill down by ID (see `hint`) — don't re-query the full list. Heavy tools (`ap_status`, `ruckus_device_arp_table`, `ruckus_device_mac_table_vlan`) accept `summary=True` for aggregate counts only.

## Workflows

### Check down APs
1. `ap_down()` → list down APs, sort by downtime
2. `ap_detail(ap_mac="...")` → model, firmware, IP
3. `ap_status(ap_mac="...")` → radio status, utilization
4. `alert_events(ap_mac="...", hours=24)` → related events

### Check high-client APs
1. `ap_high_client_count(threshold=50)` → APs with more clients than threshold
2. `client_search(ap_mac="...")` → client detail per AP
3. `ap_radio_stats(ap_mac="...")` → utilization per band → decide if reroute needed

### Troubleshoot RF interference
1. `ap_radio_stats(ap_mac="...")` → current channel, utilization, noise
2. `ap_neighbors(ap_mac="...")` → neighbor APs + RSSI
3. `optimize_wifi_rf(zone_id="...", dry_run=True)` → channel/power recommendation
4. If acceptable → `apply_rf_recommendation(zone_id="...", confirm=True)`

### Find user / device
1. `client_search(ssid="...", zone_id="...")` → SSID, AP, MAC, IP, signal
2. `ruckus_device_find_mac(host="10.x.x.x", mac="...")` → find MAC on switch
3. `ruckus_device_arp_table(host="10.x.x.x")` → IP→MAC→port mapping

### Check interface errors
1. `ruckus_device_interfaces_summary(host="...")` → all ports + link/state/speed/MAC/VLAN
2. `ruckus_device_interfaces_errors(host="...")` → ports with CRC/input errors
3. `ruckus_device_cable_diag(host="...", port="1/1/x")` → TDR cable test
4. `ruckus_device_interfaces_stats(host="...")` → utilization + PPS

### Backup config
1. `ruckus_device_config_backup(host="...")` → backup metadata (sha256, size, path)
2. `ruckus_device_config_backup(host="...", include_config=True)` → full config (contains secrets!)
3. `ruckus_device_config_diff(host="...")` → drift detection vs last backup
4. `ruckus_all_device_backup()` → backup all switches

### Diagnose port down / STP blocking
1. `ruckus_device_interfaces_down(host="...")` → list down ports
2. `ruckus_device_spanning_tree(host="...")` → STP state (FORWARDING/BLOCKING/DISABLED)
3. `ruckus_device_lldp_neighbors(host="...")` → neighbors per port
4. `ruckus_device_interfaces_summary(host="...")` → check speed/duplex mismatch

### Device audit
1. `ruckus_device_info(host="...")` → model, firmware, uptime
2. `ruckus_device_time(host="...")` → clock + NTP sync
3. `ruckus_device_syslog(host="...", severity="EW")` → recent error + warning logs

### NTP health check
1. `ruckus_device_time(host="...")` → NTP synced? peers stratum? reachable?
2. `ruckus_device_syslog(host="...", lines=20, severity="EW")` → check NTP error logs

### Optic DOM monitoring
1. `ruckus_device_sfp_info(host="...")` → list all SFP/SFP+ ports + type
2. `ruckus_device_optic_info(host="...", port="1/2/2")` → DOM: temp, voltage, tx/rx power + alarm/warning thresholds

### Config change audit
1. `ruckus_device_config_diff(host="...")` → what changed since last backup?
2. `ruckus_device_syslog(host="...", severity="IW", lines=100)` → login/logout/config changes

### SSH / login audit
1. `ruckus_device_ssh_status(host="...")` → SSH server status (v2.0, hostkey) + active sessions (user, source IP)
2. `ruckus_device_users(host="...")` → local switch accounts (password hashes not exposed)
3. `ruckus_device_syslog(host="...", severity="I", lines=50)` → SSH login/logout history

### PoE status per-port
1. `ruckus_device_poe_status(host="...")` → PoE budget + all ports status
2. `ruckus_device_poe_status(host="...", port="1/1/1")` → single port PoE detail (consumed, PD type, class, priority)
3. `ruckus_device_poe_port(host="...", port="1/1/2", enable=False, confirm=True)` → enable/disable PoE on port

### VLAN management
1. `ruckus_device_vlan_summary(host="...")` → check existing VLANs
2. `ruckus_device_vlan_create(host="...", vlan_spec="200 to 205", confirm=True)` → create VLAN range
3. `ruckus_device_vlan_create(host="...", vlan_spec="300", name="PROD", tagged_ports="ethernet 1/1/1 to 1/1/4", confirm=True)` → single VLAN + tagged ports
4. `ruckus_device_vlan_port(host="...", port="1/1/5", vlan_spec="300", action="add", tagged=True, confirm=True)` → add port to existing VLAN
5. `ruckus_device_vlan_port(host="...", port="1/1/5", vlan_spec="300", action="remove", tagged=True, confirm=True)` → remove port from VLAN
6. `ruckus_device_vlan_delete(host="...", vlan_spec="200 to 205", confirm=True)` → delete VLAN

### Static route management
1. `ruckus_device_ip_routes(host="...")` → view current IPv4 routing table
2. `ruckus_device_ip_route(host="...", dest="192.0.2.0", mask="255.255.255.0", next_hop="203.0.113.254", confirm=True)` → add route via next-hop IP
3. `ruckus_device_ip_route(host="...", dest="198.51.100.0", mask="255.255.255.0", next_hop="null0", confirm=True)` → add blackhole route
4. `ruckus_device_ip_route(host="...", dest="203.0.113.128", mask="255.255.255.128", next_hop="null0", name="BLACKHOLE", dry_run=True)` → preview command before executing
5. `ruckus_device_ip_route_delete(host="...", dest="198.51.100.0", mask="255.255.255.0", next_hop="null0", confirm=True)` → delete route

## Known Pitfalls & Bugs

| Issue | Tool | Workaround |
|---|---|---|
| `toggle_wlan` → 404 | v11_1 | `/enableOrDisable` endpoint not available on this version |
| `reboot_ap` → 500 | Virtual AP (R510) | Only works on physical APs |
| `domain_list` → 403 | vSZ | Requires admin privilege |
| `disconnect_client` → empty body | vSZ | Needs live client; empty body = success |
| ICX `show access-list` invalid | firmware 08.0.95 | Use `show ip access-list` |
| ICX `optical-monitor` not available | firmware 08.0.95 | DOM not supported on this firmware |
| ICX rate-limited SSH banner error | transient | Auto-retry 2x, backoff 1.5s |
| ICX `show ssh` invalid | firmware 08.0.x | Use `show ip ssh` — server status + active sessions |
| ICX `show users` = local accounts | firmware 08.0.x | Not active sessions; active sessions via `show ip ssh` (per-user) |
| PoE tool on non-PoE switch | ICX | Returns `note: "PoE not supported"` + empty ports |
| STP "not configured on port-vlan X" | ICX | Returns `stp_configured: false` |
| Syslog entry without message (e.g. `COPY COMPLETED`) | `ruckus_device_syslog` | Parser handles format without `:message` — regex `:?(.*)$` (fixed 2026-08-10) |
| ICX `vlan-config remove <id>` invalid | firmware 08.0.95 | Use VLAN sub-mode: `vlan <id>` → `no tagged ethernet <port>` |
| VLAN down → interface "up" but empty MAC/IP table | vSZ + ICX | Always check VLAN status too |
