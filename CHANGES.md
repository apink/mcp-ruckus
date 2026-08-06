# Changelog — MCP Ruckus

Semua perubahan signifikan pada proyek ini dicatat di sini.
Format: [ISO date] — Deskripsi singkat + Detail teknis.

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
- 12 test files, 131 tests, zero real hardware needed
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
