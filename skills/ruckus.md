# Ruckus MCP Skill — 81 tools

## Connection

- **vSZ (async REST):** `.env` → `VSZ_HOST`, `VSZ_PORT`, `VSZ_USER`, `VSZ_PASS`, `VSZ_API_VERSION` (default v11_1). Rate limit: `VSZ_RATE_LIMIT=10`.
- **ICX (SSH, netmiko):** `inventory/devices.yaml` → `username`/`password` per device. `${ENV_VAR}` supported. Rate limit: `ICX_RATE_LIMIT=5` per device.
- **MCP server:** `MCP_TRANSPORT=sse|streamable-http`, `MCP_PORT=8000`, `MCP_API_KEY` (Bearer), `MCP_ALLOWED_IPS` (CIDR).

## Tool Summary

```
vSZ (31): ap_status, ap_detail, ap_radio_stats, ap_down, client_search, ap_high_client_count,
          zone_status, zone_ap_list, license_status, radius_list, ssid_list, ssid_list_all,
          ssid_detail, create_wlan, alert_events, client_roaming, rogue_client_query, ap_neighbors,
          optimize_wifi_rf, apply_rf_recommendation, apply_ap_config, alarm_list, domain_list,
          toggle_wlan, modify_wlan, reboot_ap, disconnect_client, wlan_traffic_stats,
          ap_traffic_stats, zone_traffic_stats, controller_stats

ICX (41): ruckus_device_info, ruckus_device_status,
          ruckus_device_interfaces_summary, ruckus_device_interfaces_down,
          ruckus_device_interfaces_errors, ruckus_device_interfaces_stats,
          ruckus_device_ip_addresses, ruckus_device_ip_routes, ruckus_device_ipv6_routes,
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

- **12 destructive tools require `confirm=True`**: `apply_rf_recommendation`, `apply_ap_config`, `create_wlan`, `modify_wlan`, `reboot_ap`, `disconnect_client`, `toggle_wlan`, `ruckus_device_port_state`, `ruckus_device_vlan_create`, `ruckus_device_vlan_delete`, `ruckus_device_vlan_port`, `ruckus_device_poe_port`
- **Pilih host via IP, bukan name** — name tidak unique di devices.yaml (collision case: dua switch bernama `dist-poc`)
- **Error return format**: `{"error": "...", "detail": "..."}` — bukan exception
- **vSZ session TTL**: 10 menit, auto re-login
- **Production (764 APs) ≠ test target** — hanya gunakan riset env (dist-poc 10.3.3.82, acc-poc 10.80.172.35)
- **Skala besar**: 1000 AP → `ap_status` butuh 20+ call serial. Gunakan zone filter dan limit.

## Workflows

### Cek AP down
1. `ap_down()` → list AP yang down, sort by downtime
2. `ap_detail(ap_mac="...")` → model, firmware, IP
3. `ap_status(ap_mac="...")` → radio status, utilization
4. `alert_events(ap_mac="...", hours=24)` → event terkait

### Cek AP high-client
1. `ap_high_client_count(threshold=50)` → AP dengan client > threshold
2. `client_search(ap_mac="...")` → detail client per AP
3. `ap_radio_stats(ap_mac="...")` → utilization per band → tentukan perlu reroute atau tidak

### Troubleshoot RF interference
1. `ap_radio_stats(ap_mac="...")` → current channel, utilization, noise
2. `ap_neighbors(ap_mac="...")` → AP tetangga + RSSI
3. `optimize_wifi_rf(zone_id="...", dry_run=True)` → rekomendasi channel/power
4. Jika memuaskan → `apply_rf_recommendation(zone_id="...", confirm=True)`

### Cari user / device
1. `client_search(ssid="...", zone_id="...")` → SSID, AP, MAC, IP, signal
2. `ruckus_device_find_mac(host="10.x.x.x", mac="...")` → cari MAC di switch
3. `ruckus_device_arp_table(host="10.x.x.x")` → IP→MAC→port mapping

### Cek error interface
1. `ruckus_device_interfaces_summary(host="...")` → semua port + link/state/speed/MAC/VLAN
2. `ruckus_device_interfaces_errors(host="...")` → port dengan CRC/input error
3. `ruckus_device_cable_diag(host="...", port="1/1/x")` → TDR test kabel
4. `ruckus_device_interfaces_stats(host="...")` → utilization + PPS

### Backup config
1. `ruckus_device_config_backup(host="...")` → backup metadata (sha256, size, path)
2. `ruckus_device_config_backup(host="...", include_config=True)` → full config (secrets!)
3. `ruckus_device_config_diff(host="...")` → drift detection vs last backup
4. `ruckus_all_device_backup()` → backup semua switch

### Diagnosa port down / STP blocking
1. `ruckus_device_interfaces_down(host="...")` → list port down
2. `ruckus_device_spanning_tree(host="...")` → STP state (FORWARDING/BLOCKING/DISABLED)
3. `ruckus_device_lldp_neighbors(host="...")` → tetangga per port
4. `ruckus_device_interfaces_summary(host="...")` → cek speed/duplex mismatch

### Device audit
1. `ruckus_device_info(host="...")` → model, firmware, uptime
2. `ruckus_device_time(host="...")` → clock + NTP sync
3. `ruckus_device_syslog(host="...", severity="EW")` → error + warning logs terakhir

### NTP health check
1. `ruckus_device_time(host="...")` → NTP synced? peers stratum? reachable?
2. `ruckus_device_syslog(host="...", lines=20, severity="EW")` → cek log NTP errors

### Optic DOM monitoring
1. `ruckus_device_sfp_info(host="...")` → list all SFP/SFP+ ports + type
2. `ruckus_device_optic_info(host="...", port="1/2/2")` → DOM: temp, voltage, tx/rx power + thresholds alarm/warning

### Config change audit
1. `ruckus_device_config_diff(host="...")` → apa yang berubah sejak backup terakhir?
2. `ruckus_device_syslog(host="...", severity="IW", lines=100)` → login/logout/config changes

### SSH / login audit
1. `ruckus_device_ssh_status(host="...")` → status SSH server (v2.0, hostkey) + sesi aktif (user, source IP)
2. `ruckus_device_users(host="...")` → daftar akun lokal switch (hash password tidak diekspos)
3. `ruckus_device_syslog(host="...", severity="I", lines=50)` → riwayat SSH login/logout

### PoE status per-port
1. `ruckus_device_poe_status(host="...")` → PoE budget + all ports status
2. `ruckus_device_poe_status(host="...", port="1/1/1")` → single port PoE detail (consumed, PD type, class, priority)
3. `ruckus_device_poe_port(host="...", port="1/1/2", enable=False, confirm=True)` → enable/disable PoE on port

### VLAN management
1. `ruckus_device_vlan_summary(host="...")` → cek VLAN yang ada
2. `ruckus_device_vlan_create(host="...", vlan_spec="200 to 205", confirm=True)` → buat VLAN range
3. `ruckus_device_vlan_create(host="...", vlan_spec="300", name="PROD", tagged_ports="ethernet 1/1/1 to 1/1/4", confirm=True)` → single VLAN + tagged ports
4. `ruckus_device_vlan_port(host="...", port="1/1/5", vlan_spec="300", action="add", tagged=True, confirm=True)` → tambah port ke VLAN existing
5. `ruckus_device_vlan_port(host="...", port="1/1/5", vlan_spec="300", action="remove", tagged=True, confirm=True)` → hapus port dari VLAN
6. `ruckus_device_vlan_delete(host="...", vlan_spec="200 to 205", confirm=True)` → hapus VLAN

## Known Pitfalls & Bugs

| Issue | Tool | Workaround |
|---|---|---|
| `toggle_wlan` → 404 | v11_1 | Endpoint `/enableOrDisable` tidak tersedia di versi ini |
| `reboot_ap` → 500 | AP virtual (R510) | Hanya bekerja di AP fisik |
| `domain_list` → 403 | vSZ | Butuh admin privilege |
| `disconnect_client` → empty body | vSZ | Perlu live client; body kosong = berhasil |
| ICX `show access-list` invalid | firmware 08.0.95 | Gunakan `show ip access-list` |
| ICX `optical-monitor` not available | firmware 08.0.95 | Tidak support DOM di firmware ini |
| ICX rate-limited SSH banner error | transient | Auto-retry 2x, backoff 1.5s |
| ICX `show ssh` invalid | firmware 08.0.x | Gunakan `show ip ssh` — status server + sesi aktif |
| ICX `show users` = akun lokal | firmware 08.0.x | Bukan sesi aktif; sesi aktif via `show ip ssh` (per-user) |
| PoE tool untuk non-PoE switch | ICX | Return `note: "PoE not supported"` + empty ports |
| STP "not configured on port-vlan X" | ICX | Return `stp_configured: false` |
| Entry syslog tanpa message (mis. `COPY COMPLETED`) | `ruckus_device_syslog` | Parser handle format tanpa `:message` — regex `:?(.*)$` (fixed 2026-08-10) |
| ICX `vlan-config remove <id>` invalid | firmware 08.0.95 | Gunakan VLAN sub-mode: `vlan <id>` → `no tagged ethernet <port>` |
| VLAN down → interface "up" tapi MAC/IP table kosong | vSZ + ICX | Selalu check VLAN status juga |

