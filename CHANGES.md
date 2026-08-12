# Changelog — MCP Ruckus

Semua perubahan signifikan pada proyek ini dicatat di sini.
Format: [ISO date] — Deskripsi singkat + Detail teknis.

---

## 2026-08-12 — PoE Per-Port Status + PoE Port Enhancement

### PoE status per-port filter (enhancement)
- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_poe_status(host, port=None)` — now supports optional `port` parameter for single-port detail
- **Without port:** returns PoE budget summary + all ports
- **With port:** returns single-port status (consumed, PD type, class, priority)
- **Read-only** — no confirm gate, no destructive
- **Tests:** +2 (TestPoeStatusPerPort) — 185 → 187 pytest pass

### PoE port params (enhancement)
- **Tool:** `ruckus_device_poe_port(host, port, enable=True, priority=None, power_limit=None, power_by_class=None, confirm=True, dry_run=False)`
- **New optional params:** `priority` (critical/high/low), `power_limit` (milliwatts 1000-30000), `power_by_class` (class 0-4)
- **Backward compatible** — existing calls without new params still work
- **Safety:** `confirm=True` gate unchanged, `dry_run=True` preview shows CLI commands
- **Docs:** README (81 tools, ICX 41), skills/ruckus.md (81 tools + PoE workflow), DOCS_SAFETY.md (12 destructive), SECURITY.md (187 tests)
- **Tool count:** 80 → 81 tools, ICX 40 → 41

---

## 2026-08-12 — PoE Port Control

### PoE port enable/disable (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_poe_port(host, port, enable, confirm=True, dry_run=False)`
- **Commands:** `conf t` → `interface ethernet <port>` → `inline power` / `no inline power` → `end`
- **Difference from port_state:** Only toggles PoE — data link stays up (admin up/down = both link + PoE)
- **Safety:** `confirm=True` gate + `dry_run=True` preview
- **Live-tested:** ICX7150-48-POEF 740W budget — disable/enable works, no link interruption
- **Tests:** +4 (TestPoePort) — 178 → 182 pytest pass
- **Docs:** README (80 tools, ICX 40), skills/ruckus.md (80 tools, 12 destructive), DOCS_SAFETY.md (12 tools)
- **Tool count:** 79 → 80 tools

---

## 2026-08-12 — Dry-Run Preview for ICX Config Tools

### Safety — dry run without execution
- **All 4 ICX config tools** (`port_state`, `vlan_create`, `vlan_delete`, `vlan_port`) now support `dry_run=True`
- Returns `{"dry_run": True, "commands": [...]}` showing exact CLI commands without executing
- Commands generated from same code path as execution — guarantees accuracy
- No SSH connection when `dry_run=True` — zero side effects
- Tests: +4 (TestDryRun) — 174 → 178 pytest pass
- Docs: DOCS_SAFETY.md (dry-run section), this changelog

---

## 2026-08-12 — VLAN Management Tools

### VLAN create / delete / port (3 new tools)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tools:** `ruckus_device_vlan_create`, `ruckus_device_vlan_delete`, `ruckus_device_vlan_port`
- **Create:** `conf t` → `vlan <spec> [name <name>]` → optional tagged/untagged ports + spanning-tree + STP priority
- **Delete:** `conf t` → `no vlan <spec>` → `end`
- **Port add:** via interface mode `vlan-config add tagged-vlan/untagged-vlan <spec>`
- **Port remove:** via VLAN sub-mode `no tagged/untagged ethernet <port>` (firmware 08.0.95 `vlan-config remove` not supported)
- **VLAN spec:** single ('200'), range ('210 to 213'), multi ('200 210 220'), mixed ('16 17 20 to 24')
- **Port spec:** `ethernet 1/1/1 to 1/1/4 ethernet 1/1/17` format
- **Safety:** All 3 tools have `confirm=True` gate
- **Parser:** `_parse_vlan_spec()` — validates all VLAN IDs (1-4094), `_validate_ports_spec()` — validates all port tokens
- **Live-tested:** ICX7150-48-POEF 08.0.95nT213 — create/delete VLAN, add/remove tagged port vlan-config + VLAN sub-mode
- **Tests:** +11 (TestVlanCreate 5, TestVlanDelete 3, TestVlanPort 3) — 163 → 174 pytest pass
- **Docs:** README (79 tools, ICX 39), skills/ruckus.md (79 tools, 11 destructive), DOCS_SAFETY.md (11 tools)
- **Tool count:** 76 → 79 tools

---

## 2026-08-11 — Port Enable/Disable (ICX)

### Port state control (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_port_state(host, port, enable, confirm=True)`
- **Command:** `configure terminal` → `interface ethernet <port>` → `enable`/`disable` → `end`
- **Safety:** `confirm=True` gate (follows DOCS_SAFETY.md destructive tool pattern)
- **Tests:** +3 (TestPortState) — 160 → 163 pytest pass
- **Docs:** README (76 tools, ICX 36), skills/ruckus.md (76 tools, 8 destructive), DOCS_SAFETY.md (8 tools), DEVELOPMENT_GUIDELINES.md (backlog marked done)
- **Tool count:** 75 → 76 tools

---

## 2026-08-10 — Users + SSH Status Tools

### Active users (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_users(host)`
- **Command:** `show users`
- **Parser:** Local user accounts — username, encrypt, privilege, status, expire time. Password hash **tidak diekspos** (security)
- **Live-tested:** dist-poc 10.3.3.82 (admin, ansible) + acc-poc 10.80.172.35 (super)
- **Tool count:** 73 → 74 tools

### SSH server status (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_ssh_status(host)`
- **Command:** `show ip ssh` — `show ssh` **invalid** di firmware 08.0.x (Lessons: dipakai `show ip ssh`)
- **Parser:** SSH version + enabled + host key + per-session (direction, connection, version, encryption, username, HMAC, source IP)
- **Live-tested:** dist-poc + acc-poc — session aktif admin/super dari 10.10.10.177, hostkey RSA(2048)
- **Tool count:** 74 → 75 tools

### Cleanup

- **Dead code removed:** blok `get_poe_status` duplikat (unreachable) di dalam `get_arp_table` dari sesi debug terputus
- **Tests:** +5 (TestUsers, TestSshStatus) — 155 → 160 pytest pass
- **Docs:** README (75 tools, ICX 35), skills/ruckus.md (75 tools + SSH/login audit workflow + pitfalls `show ssh` invalid), DEVELOPMENT_GUIDELINES.md

---

## 2026-08-10 — Syslog Parser Fix

### Syslog parser edge case handling

- **File:** `adapters/device_ssh.py` (line 857)
- **Issue:** Regex `([^:]+):(.+)` gagal pada entry tanpa message (format: `timestamp:severity:facility`)
- **Examples gagal:** `Aug 6 17:12:05:N:SSH Server session 1 received key-exchange`, `Aug 6 13:53:08:I:COPY COMPLETED`
- **Fix:** Regex → `([^:]+):?(.*)$` (opsional colon, message boleh empty)
- **Hasil:** Parsing 3422→3460/3461 entries (99.9%)
- **Tambahan:** Filter header line `(4000 lines):`
- **Code style:** Ruff fixes — MAC_COLON_RE wrap, rate_in/rate_out regex line split, variable `l`→`ln`
- **Tests:** 155/155 pytest pass

---

## 2026-08-06 — CPU/Memory + ARP + PoE + LLDP + Rate Limiting

### CPU & Memory Resources (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_resources(host)`
- **Commands:** `show cpu` + `show memory`
- **Parser:** Per-core load averages (1s/5s/60s/300s) + DRAM total/free/used/pct
- **Regex fix:** `\s+sec` (not literal ` sec`) to handle variable spacing in ICX CLI output
- **Tested:** Live on ICX7450-24-HPOE (CPU0: 2/7/3/1%, CPU1: 0/1/0/1%, Mem: 36.8%)
- **Tool count:** 65 → 66 tools

### ARP Table (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_arp_table(host)`
- **Command:** `show arp`
- **Parser:** Numbered rows — ip, mac, type, age, port, status
- **Tested:** Live on ICX7450-24-HPOE (6 entries, including incomplete/NAT entries)
- **Tool count:** 64 → 65 tools

### PoE Status (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_poe_status(host)`
- **Command:** `show inline power`
- **Parser:** Summary (capacity, free, requests) + per-port table (admin/oper state, consumed, allocated, PD type, class, priority)
- **Tested:** Live on ICX7450-24-HPOE (748W budget, all free, 24 ports parsed)
- **Tool count:** 63 → 64 tools

### LLDP Neighbors (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_lldp_neighbors(host)`
- **Command:** `show lldp neighbors`
- **Parser:** Column-based — local_port, chassis_id, port_id, port_description, system_name
- **Tested:** Live on ICX7450-24-HPOE (12 neighbors — Cisco WLC, ICX switch, APs) + ICX7150-48-POEF (1 neighbor — BS-RISET-L3)
- **Tool count:** 62 → 63 tools

### Rate Limiting (vSZ API + ICX SSH)

- **vSZ API (`adapters/vsz.py`):** `asyncio.Semaphore` — default 10 concurrent, config via `VSZ_RATE_LIMIT`
- **ICX SSH (`adapters/device_ssh.py`):** `threading.BoundedSemaphore` per-device — default 5 concurrent, config via `ICX_RATE_LIMIT`
- **ICX semaphore release:** monkey-patch `ConnectHandler.disconnect()` untuk auto-release setelah `with conn:` selesai
- **Efek:** Mencegah overload vSZ controller dan ICX management plane saat tool dipanggil bersamaan

### ICX Per-Device Credentials (devices.yaml)

- **File:** `models/ruckus.py`, `adapters/device_ssh.py`, `inventory/manager.py`
- **Mekanisme:** `username` / `password` literal langsung di `devices.yaml`
- **Env var substitution:** `${VAR_NAME}` di nilai YAML → resolve dari `.env` saat load
- **Unknown env var:** `KeyError` langsung saat `load_inventory()`, bukan gagal SSH
- **Import cleanup:** `DeviceCredentials` tidak lagi digunakan di SSH adapter
- **Inventaris:** `inventory/manager.py` punya `_resolve_env_vars()` regex-based, `_resolve_credentials()` post-processing

### Contoh devices.yaml

```yaml
devices:
  - host: 10.0.0.50
    name: icx-core
    username: ${ICX_CORE_USER}    # env var reference
    password: ${ICX_CORE_PASS}

  - host: 10.0.0.51
    name: icx-dist-01
    username: admin-dist          # literal langsung
    password: dist-pass
```

### Doc Update

- `.env.example`: `VSZ_RATE_LIMIT`, ICX credential docs
- `README.md`: rate limit + devices.yaml credential examples
- `inventory/devices.example.yaml`: literal + `${ENV}` examples

---

## 2026-08-06 — Safety Gates + Radius Enhancement + Docs Refresh

### Safety Gates — 7 tools
Semua tool destruktif sekarang wajib `confirm=True` gate:
- `reboot_ap`, `disconnect_client`, `toggle_wlan` — baru ditambahkan
- `apply_rf_recommendation`, `apply_ap_config`, `create_wlan`, `modify_wlan` — sudah ada

Tanpa `confirm=True`, return `{"error": "confirm_required"}` + no-op.

### `radius_list` — now shows IP & port
Sebelumnya hanya `has_primary: bool`. Sekarang:
- `primary_ip`, `primary_port`
- `secondary_ip`, `secondary_port` (None jika tidak ada)
- `sharedSecret` tetap tidak diekspos (security)

### Docs refresh
- `README.md` — 62 tools, complete tool tables, updated architecture
- `CHANGES.md` — restructured, backlog moved to DEVELOPMENT_GUIDELINES
- `DEVELOPMENT_GUIDELINES.md` — async section done, file structure updated, backlog cleaned
- `SECURITY.md` — 131 tests, FastMCP 3.4.2
- `skills/ruckus.md` — 62 tools header, traffic/alarm/monitoring tool docs added
- `kilo.json` — AI permission rules block .env reads

### Radio config — lessons learned
AP config via PUT (not PATCH), body harus di-clean: unwritable fields strip, semua null hapus, integer untuk channel/width (bukan string), `autoChannelSelection` hapus kalau manual channel. HTTP 204 = success. Verified: set channel/power, disable/enable radios, auto channel.

---

## 2026-08-06 — 10 New Tools: Traffic, Alarms, Domains, WLAN Modify, Controller, Client Disconnect, AP Reboot

**10 new tools added** — total now 62 tools.

### Traffic Tools (3)
- `wlan_traffic_stats` — per-SSID rx/tx MB + client count + per-zone breakdown
- `ap_traffic_stats` — per-AP rx/tx MB + zone/model info
- `zone_traffic_stats` — per-zone rx/tx MB + AP count + active WLAN count
- Source: `POST /query/client` aggregation with pagination (500/page)
- Adapter: `query_clients(ssid, ap_name)` — extraFilters for SSID/AP_NAME

### Monitoring Tools (2)
- `alarm_list` — active alarms with severity/hours/text_search filters
- `domain_list` — administration domains (403 on restricted accounts)

### WLAN Tools (2)
- `modify_wlan` — update description, passphrase, encryption, VLAN, max_clients, client_isolation
  - Full WLAN body cleaning: unwritable fields stripped, nulls removed, min-value fields fixed (1)
  - `confirm=True` safety gate
  - Requires admin credentials (read-only gets 403)
- `toggle_wlan` — enable/disable via `/enableOrDisable` endpoint (v12+ required)

### AP Tools (1)
- `reboot_ap` — reboot AP by name, resolves MAC from `query_ap`

### Client Tools (1)
- `disconnect_client` — POST `/clients/disconnect` with `{mac, apMac}`

### System Tools (1)
- `controller_stats` — node info: model, version, role, uptime (CPU/mem/disk not exposed by public API)

---

## 2026-08-05 — Async Refactor Complete + Test Suite

### Full Async Migration
- `VsZRestAdapter` → `httpx.AsyncClient`, all 21 methods `async def`, session TTL + auth fallback preserved
- All 7 vSZ tool modules → `async def` + `await`
- `asyncio.gather()` for neighbor batch fetch (was ThreadPoolExecutor)
- `asyncio.to_thread()` for RF optimizer (CPU-bound DSATUR/Tabu Search)
- ICX adapter stays sync (Netmiko not async-native)
- Benchmark: 2.7x–3.7x speedup with async parallel

### Test Suite
- 12 test files, 148 tests, zero real hardware needed
- `tests/conftest.py` — module-level mock patches
- `tests/fixtures.py` — 461 lines deterministic sample data
- Mock adapters: `MockVsZRestAdapter`, `MockRuckusDeviceDriver`

### Bug Fixes
- `get_aps_by_zone()` added to adapter (was missing, caused AttributeError in 5 tools)
- `get_ap_neighbors` endpoint confirmed: `/aps/{mac}/apNeighbors`
- `query_clients` extraFilters fix: SSID filter moved from `filters` to `extraFilters`

### Cleanup
- `tools/management.py` (1669 lines, deprecated) deleted
- Git init deferred

---

## 2026-08-05 — Zone Tree Discovery + 802.1X + RADIUS + Auth Fallback

### `get_zones()` — rewrite: `/group/tree/apgroup` primary

**Masalah:** Domain-scoped user tidak bisa akses `/rkszones` (403).
Zona tanpa AP tidak terdeteksi lewat `/query/ap` extraction.

**Solusi:**
- `GET /group/tree/apgroup` → 1 call, berfungsi root + domain, selalu
  lihat semua zona termasuk yang tanpa AP
- `get_zone_tree()` — panggil tree endpoint
- `_flatten_zone_tree()` — recursive walk cari node `type: "ZONE"`,
  bawa `domainUUID`/`domainName` ke bawah
- Fallback: `/rkszones` (root) → `/query/ap` extraction
- Return zone object sekarang punya field tambahan: `domainName`,
  `offlineCount`, `onlineCount`

### `create_wlan` — 802.1X support via `standard8021X` endpoint

| Type | Endpoint | Hasil |
|---|---|---|
| PSK / Open | `POST /rkszones/{zid}/wlans` | verified (7 types) |
| 802.1X | `POST /rkszones/{zid}/wlans/standard8021X` | verified |

Payload 802.1X: `authServiceOrProfile: {name}` + `encryption: {WPA2, AES, mfp:disabled}`,
tanpa passphrase. Wajib `radius_profile` (nama auth service di zone).

### `radius_list` — tool baru

`GET /rkszones/{zid}/aaa/radius` — list RADIUS server di zone untuk
referensi `radius_profile` sebelum create 802.1X WLAN.

Adapter: `get_radius_servers(zone_id, for_accounting=None)`

### `_request()` — support PATCH/PUT

Sebelumnya hanya GET/POST/DELETE. PATCH/PUT jatuh ke GET (bug).
Sekarang: `httpx.request(method, url, ...)` untuk PUT/PATCH.

### Auth fallback: static token → credentials

`VSZ_API_TOKEN` di .env bisa expired/revoked. Jika request 401 saat
pakai token: `_token_failed = True`, login ulang via `VSZ_USER`/`VSZ_PASS`,
retry sekali. Aktif di `_request()` dan `create_wlan()`.

---

## Cara Menambah Dokumentasi Perubahan

Setiap kali ada perubahan signifikan (patch, bug fix, feature baru),
tambah entry di file ini dengan format yang sama. Jangan hapus entry
lama — ini historical record untuk developer selanjutnya (manusia
atau AI).

### v0.13.0 - Access Lists
- Added `ruckus_device_access_lists` (ICX tool #33): `show ip access-list` + `show ip access-list brief`
  — Standard/Extended ACLs, per-ACL rules (seq/action/match), brief summary (name + entries)

### v0.12.0 - Spanning Tree
- Added `ruckus_device_spanning_tree` (ICX tool #32): `show span` — root bridge, per-port state, path costs

### v0.11.0 - Clock + NTP
- Added `ruckus_device_time` (ICX tool #31): `show clock` + `show ntp status` + `show ntp associations`
  — current time, NTP sync state, peer status (stratum, reachable, delay, offset)

### v0.10.0 - Optic DOM
- Added `ruckus_device_optic_info` (ICX tool #30): `show optic <port>` + `show optic thresholds <port>`
  — temperature, voltage, tx/rx power, tx bias  + alarm/warning thresholds
- Parser: handles both DOM table format and threshold table format
- Tested live on ICX stack 08.0.90b (10GE LR SFP+, 38.5C, V=3.21, TX=-2.25 dBm, RX=-4.35 dBm)
- Tool count: 69 → 70, 146 → 148 tests

### v0.9.0 - Syslog tool
- Added `ruckus_device_syslog` (ICX tool #29): `show log` — parsed, deduplicated, severity-filtered
- Token-optimized: default 50 last entries, max 500; severity filter (E=error, W=warning, etc.)
- Dedup: identical messages collapsed with `count` + `first`/`last_ts` timestamps
- Tested live: 3945 parsed entries from 4000 raw lines
- Tool count: 68 → 69, 143 → 146 tests

### v0.8.0 - TDR cable diagnostics
- Added `ruckus_device_cable_diag` (ICX tool #28): `show cable-diag tdr <port>` — per-pair status
- Copper ports only: terminated, open, short, impedance mismatch
- Fiber ports return `note: "TDR not supported on this port"`
- Tool count: 67 → 68, 141 → 143 tests

### v0.7.0 - SFP/transceiver info
- Added `ruckus_device_sfp_info` (ICX tool #27): `show media` — per-port transceiver type (SFP+/Gig-Copper/EMPTY)
- Optional `port` parameter for single-port detail (vendor, version, part#, serial#)
- Interface brief upgraded to `show interface brief wide` — now includes MAC, VLAN tag/PVID, trunk, priority
- Non-PoE switch detection added to PoE tool: `note: "PoE not supported"` when `power_capacity_mw` missing
- Tool count: 66 → 67, 139 → 141 tests
