# Ruckus MCP Skill — 62 tools

## Description
Curated tools untuk Ruckus wireless infrastructure management: vSZ controller (AP, zone, radio stats, events, license, traffic analytics, alarms) dan ICX switch (device, interface, error monitoring, config backup). 62 tools total — 38 vSZ + 22 ICX + 2 inventory.

## Connection Methods

### vSZ Controller (REST API — async)
Primary untuk AP management, zone config, wireless monitoring, traffic analytics. Cakup semua AP dari controller tanpa SSH per device. Data realtime, bulk operations.
API version: v11_1 (configurable via VSZ_API_VERSION).

### ICX Switch (SSH — sync)
Untuk device-level monitoring: status, interface, error counter. Lebih detail untuk network troubleshooting. Netmiko-based SSH.

## Available Tools — vSZ

### ap_status
Status AP dari vSZ, termasuk utilization per band. Optional zone filter dan limit.

**Signature:** `ap_status(zone_id: str | None = None, limit: int = 100)`

**Return:**
```json
[
  {
    "ap_name": "AP-Lobby-1",
    "mac": "aa11.bb22.cc33",
    "serial": "ABC123",
    "model": "R710",
    "status": "up",
    "clients": 12,
    "clients_24g": 3,
    "clients_5g": 9,
    "location": "Lobby",
    "zone": "Lobby",
    "ip": "192.168.1.100",
    "channel_24g": "11 (20MHz)",
    "channel_5g": "161 (40MHz)",
    "airtime_24g_pct": 15,
    "airtime_5g_pct": 45,
    "capacity_pct": 60,
    "capacity_24g_pct": 30,
    "capacity_5g_pct": 90,
    "noise_24g_dbm": -92,
    "noise_5g_dbm": -89
  }
]
```

**Utilization metrics:**
- `airtime_24g_pct` — utilization 2.4GHz dalam %
- `airtime_5g_pct` — utilization 5GHz dalam %
- `capacity_pct` — total capacity utilization %
- `capacity_24g_pct` — capacity 2.4GHz %
- `capacity_5g_pct` — capacity 5GHz %

---

### ap_detail
Detail satu AP.

**Signature:** `ap_detail(ap_name: str)`

**Return:**
```json
{
  "ap_id": "AP-001",
  "name": "AP-Lobby-1",
  "status": "up",
  "ip": "192.168.1.100",
  "mac": "aa11.bb22.cc33",
  "model": "R710",
  "firmware": "110.0.0.0.1315",
  "serial": "ABC123",
  "zone": "Lobby",
  "clients": 12,
  "channel_utilization": 45.0,
  "uptime": "30 days",
  "mesh_role": "Root"
}
```

---

### ap_radio_stats
Real-time per-radio stats untuk satu AP via SCG `apdetail` endpoint. Lebih kaya dari `ap_detail` — punya noise floor real, airtime breakdown, retry/drop counter, tx power.

Berguna untuk: troubleshoot AP noisy (noise floor tinggi = interferensi), deteksi congestion (airtime busy + retry naik), cek packet loss (drop counter), verify config radio aktif (tx power, channel width), band steering analysis.

**Signature:** `ap_radio_stats(ap_name: str)`

**Return:**
```json
{
  "ap_name": "AP-Floor1-01",
  "mac": "AA:BB:CC:11:22:33",
  "model": "R650",
  "radios": [
    {
      "band": "2.4GHz",
      "radio_id": "0",
      "channel": "6",
      "secondary_channel": null,
      "channel_width_mhz": 20,
      "mode": "11ax",
      "tx_power": "max",
      "chainmask": "2x2 1x1",
      "clients": 5,
      "noise_floor_dbm": -94,
      "airtime_total_pct": 31,
      "airtime_busy_pct": 0,
      "airtime_rx_pct": 24,
      "airtime_tx_pct": 7,
      "tx_bytes_gb": 688.84,
      "rx_bytes_gb": 76.66,
      "retry": 219620427,
      "drop": 11373153,
      "background_scan": true,
      "auto_cell_sizing": false
    },
    {
      "band": "5GHz",
      "radio_id": "1",
      "channel": "120",
      "channel_width_mhz": 80,
      "mode": "11ax",
      "tx_power": "max",
      "chainmask": "4x4 3x3 2x2 1x1",
      "clients": 0,
      "noise_floor_dbm": -96,
      "airtime_total_pct": 2,
      ...
    }
  ]
}
```

**Key fields per radio:**
- `noise_floor_dbm` — noise floor real-time per radio (lebih akurat dari avg `noise24G/5G`)
- `airtime_total/busy/rx/tx_pct` — breakdown airtime utilization (0-100%)
- `retry`, `drop` — packet retry/drop counter (naik = RF/capacity issue)
- `tx_power`, `channel_width_mhz`, `mode`, `chainmask` — config radio aktif
- `clients` — client authorized per radio
- `tx/rx_bytes_gb` — cumulative traffic sejak boot

**Source:** SCG admin endpoint `/wsg/api/scg/aps/{mac}/apdetail` (bukan public `query/ap`). MAC colon-format.

---

### ap_down
Semua AP yang down.

**Signature:** `ap_down()`

---

### client_search
Cari client di vSZ berdasarkan ID, username, MAC, atau IP. Berguna untuk tracing siapa/device mana yang connect, di AP mana, dan kualitas koneksinya.

Mendukung multiple devices per user — return semua device yang match query, baik di AP sama maupun berbeda. Default limit 20 client, traffic stats opsional.

**Signature:** `client_search(query: str, limit: int = 20, include_traffic: bool = False)`

**Return:**
```json
{
  "query": "user@domain.com",
  "total": 3,
  "clients": [
    {
      "hostname": "LAPTOP-John",
      "username": "john.doe",
      "os_type": "Microsoft Windows/Windows 10.0.0",
      "device_type": "Laptop",
      "ipv4": "192.168.1.100",
      "ipv6": "fe80::1",
      "mac": "aa11.bb22.cc33",
      "ssid": "Office-WiFi",
      "bssid": "aa:11:bb:22:cc:dd",
      "vlan": 100,
      "rssi": -55,
      "snr": 42,
      "channel": "161",
      "radio_type": "a/n/ac",
      "tx_mbytes": 145.23,
      "rx_mbytes": 28.91,
      "uplink_mbytes": 28.91,
      "downlink_mbytes": 145.23,
      "tx_rate_bps": 11700.0,
      "median_tx_mcs": 156000,
      "median_rx_mcs": 130000,
      "auth_method": "Standard+802.1X",
      "encryption": "WPA2-AES",
      "auth_status": "AUTHORIZED",
      "ap_name": "AP-Lobby-1",
      "ap_mac": "C8:84:8C:AA:BB:CC",
      "ap_location": "Lobby Lt.1"
    }
  ]
}
```

**Connection quality fields (always returned):**
- `rssi`, `snr` — sinyal dan noise ratio (dBm/dB)
- `channel`, `radio_type` — kanal dan tipe radio (a/n/ac, b/g/n/ax)
- `tx_rate_bps` — transmit rate dalam bps

**Traffic fields (only when `include_traffic=True`):**
- `tx_mbytes`, `rx_mbytes` — total traffic dalam MB
- `uplink_mbytes`, `downlink_mbytes` — directional traffic dalam MB
- `median_tx_mcs`, `median_rx_mcs` — MCS rate
- `session_start` — session start timestamp

---

### ap_high_client_count
AP dengan client di atas threshold (default 50).

**Signature:** `ap_high_client_count(threshold: int = 50)`

---

### zone_status
Status zone dari vSZ. Zone didapat dari `GET /group/tree/apgroup`
(1 call, lihat semua zone root + domain, termasuk zona tanpa AP).

**Signature:** `zone_status()`

**Return:**
```json
[
  {"zone_id": "1", "name": "Lobby", "ap_count": 4, "client_count": 45, "status": "active"}
]
```

---

### zone_ap_list
AP list untuk zone tertentu.

**Signature:** `zone_ap_list(zone_id: str)`

---


### license_status
License vSZ (total AP, used, remaining).

**Signature:** `license_status()`

---

### radius_list
List RADIUS server di zone — referensi untuk `radius_profile`
sebelum create 802.1X WLAN.

**Signature:** `radius_list(zone_id: str, for_accounting: str = "all")`

- `for_accounting`: `"all"`, `"auth_only"`, atau `"accounting_only"`.

**Return:**
```json
[
  {"id": "uuid", "name": "radius-1", "service_type": "Authentication",
   "description": "...", "zone_id": "...",
   "has_primary": true, "has_secondary": false}
]
```

---

### ssid_list
Daftar SSID (WLAN) dalam satu zone. Untuk cek SSID apa saja yang tersedia di zone tertentu.

**Signature:** `ssid_list(zone_id: str)`

**Return:**
```json
[
  {"ssid": "Office-WiFi", "name": "Zone-01 - Office-WiFi", "id": "232", "zone_id": "..."}
]
```

---

### ssid_list_all
Daftar semua SSID di semua zone.

**Signature:** `ssid_list_all()`

**Return:**
```json
[
  {"ssid": "Office-WiFi", "name": "Zone-01 - Office-WiFi", "id": "232", "zone_id": "...", "zone": "Campus - Zone-01"}
]
```

---

### ssid_detail
Detail konfigurasi SSID: jenis auth, enkripsi, VLAN, timeout, max clients.

**Signature:** `ssid_detail(wlan_id: str, zone_id: str)`

**Return:**
```json
{
  "ssid": "Office-WiFi",
  "type": "Standard_8021X",
  "encryption_method": "WPA2",
  "auth_service": "Zone-01-RAD-10.89",
  "vlan_id": 583,
  "max_clients_per_radio": 100,
  "schedule": "AlwaysOn"
}
```

---

### create_wlan ✅ TESTED
> **Status: Sudah diuji ke vSZ live.** Open, WPA2-PSK, WPA3-SAE, WPA_Mixed, WPA23_Mixed, OWE, hidden SSID — semua berfungsi. 802.1X via endpoint dedicated `standard8021X`.

Buat WLAN (SSID) baru di sebuah zone via vSZ API. Mendukung Open, WPA2/WPA3 PSK, dan 802.1X Enterprise. Auto-set schedule AlwaysOn.

**PERINGATAN:** WLAN langsung dibuat di vSZ. AP di zone tersebut akan mulai broadcast SSID.

**Signature:** `create_wlan(zone_id, name, ssid, encryption="WPA2", passphrase="", auth_type="PSK", radius_profile="", access_vlan=1, description="", hidden=False, max_clients=100, client_isolation=False, confirm=False)`

**Args:**
- `zone_id`: Zone UUID.
- `name`: WLAN name (1-32 chars, nama di vSZ).
- `ssid`: Broadcasted SSID string (1-32 chars).
- `encryption`: `"WPA2"`, `"WPA3"`, `"WPA_Mixed"`, `"WPA23_Mixed"`, `"OWE"`, atau `"None"`.
- `passphrase`: PSK passphrase (8-63 chars). Wajib untuk PSK auth.
- `auth_type`: `"PSK"`, `"8021X"`, atau `"none"`.
- `radius_profile`: Nama Authentication Service untuk 8021X (e.g. `"Office-RAD"`). Profile harus sudah ada di vSZ.
- `access_vlan`: Access VLAN ID (1-4094).
- `description`: WLAN description (max 64 chars).
- `hidden`: Sembunyikan SSID (hidden SSID, default False).
- `max_clients`: Max client per radio (1-512, default 100).
- `client_isolation`: Blokir traffic antar client (default False).
- `confirm`: **Wajib `True`** untuk eksekusi (safety latch).

**Return:**
```json
{
  "status": "created",
  "id": "wlan-uuid",
  "name": "Office-WiFi",
  "ssid": "Office-WiFi",
  "zone_id": "zone-uuid",
  "encryption": "WPA2",
  "auth_type": "PSK",
  "access_vlan": 100,
  "hidden": false
}
```

**Auth type combinations:**

| auth_type | encryption | passphrase | radius_profile | Hasil |
|---|---|---|---|---|
| `none` | `None` | — | — | Open WLAN (no security) |
| `PSK` | `WPA2` | ✓ | — | WPA2-PSK (passphrase) |
| `PSK` | `WPA3` | ✓ | — | WPA3-SAE (passphrase) |
| `PSK` | `WPA23_Mixed` | ✓ | — | WPA2/WPA3 Mixed |
| `PSK` | `OWE` | — | — | Enhanced Open (OWE) |
| `8021X` | `WPA2` | — | ✓ | WPA2-Enterprise (RADIUS) — endpoint `standard8021X` |

**Note:** 802.1X memakai endpoint terpisah `POST /{api_version}/rkszones/{zoneId}/wlans/standard8021X` dengan `authServiceOrProfile` wajib. Nama RADIUS profile harus sudah ada di vSZ.

**Usage examples:**
```python
# WPA2-PSK WLAN
create_wlan(zone_id="zone-uuid", name="Office-WiFi", ssid="Office-WiFi",
            encryption="WPA2", passphrase="secure-passphrase", access_vlan=100, confirm=True)

# Open WLAN (guest)
create_wlan(zone_id="zone-uuid", name="Guest-WiFi", ssid="Guest",
            encryption="None", auth_type="none", access_vlan=200, confirm=True)

# Hidden WPA2-PSK
create_wlan(zone_id="zone-uuid", name="Hidden-Cam", ssid="Cam-Stream",
            encryption="WPA2", passphrase="camera-secret", hidden=True, access_vlan=50, confirm=True)
```

**Flow dengan agent (tanya jawab):**
```
User: "Tolong buatkan SSID Office-WiFi"
Agent: "Beberapa info yang dibutuhkan:
       1. Tipe: Open atau WPA2-PSK?
       2. VLAN ID berapa?
       3. Zone mana?"
User: "WPA2-PSK, VLAN 100, zone Lobby"
Agent: "Password-nya apa?"
User: "secure-passphrase"
Agent → create_wlan(..., confirm=True)
```

---

### alert_events
Event/alert log dari vSZ dengan server-side filtering dan pagination. Reduksi data volume dengan filter:
- Severity: Critical, Warning, Informational, Major, Minor, Debug
- Category: AP, Client, Cluster, Control_Plane, Data_Plane, Switch, dll
- Time range: last N hours (`hours_back`)
- Full-text search: cari di semua field event
- Pagination: `page` dan `limit`

**Signature:** `alert_events(limit=20, severity=None, category=None, hours_back=None, text_search=None, page=1)`

**Return:**
```json
{
  "totalCount": 12560,
  "firstIndex": 0,
  "hasMore": true,
  "page": 1,
  "limit": 20,
  "events": [
    {
      "id": "AZ9B1M0bxkCqDPF49gbl",
      "time_ms": 1783515893019,
      "event_type": "Switch Critical Message",
      "event_code": 20000,
      "severity": "Critical",
      "category": "Switch",
      "activity": "[ABC123XYZ] PoE: Power disabled on port 1/1/17 because of PD overload."
    }
  ]
}
```

**Filtering examples:**
```python
# Critical only
alert_events(limit=10, severity="Critical")  # ~12K events

# AP Warning events, last 24h
alert_events(limit=20, severity="Warning", category="AP", hours_back=24)

# Text search: semua event dengan kata "channel"
alert_events(limit=10, text_search="channel")

# Pagination: page 2 dari result Critical
alert_events(limit=20, severity="Critical", page=2)
```

**Impact:** Dari 6.2M events, filter severity="Critical" → 12.5K events (penghematan 500x data yang dikirim).

---

### client_roaming
Track roaming history dan semua device user dari event log. Default severity="Informational" untuk filter roaming events saja (join/leave/roam).

**Signature:** `client_roaming(query: str, limit: int = 30, severity: str = "Informational")`

**Return:**
```json
{
  "query": "user12345",
  "total_events": 365,
  "events_fetched": 100,
  "total_devices": 2,
  "devices": [
    {
      "mac": "aa:bb:cc:dd:ee:ff",
      "ssid": "Office-WiFi",
      "ip_addresses": ["172.16.1.50", "192.168.1.100"],
      "total_events": 46,
      "roaming_timeline": [
        {"time": "2026-07-08 11:07:59", "ap": "AP01-08"},
        {"time": "2026-07-08 11:07:58", "ap": "AP01-08"},
        {"time": "2026-07-08 11:07:28", "ap": "AP01-21"},
        ...
      ]
    },
    {
      "mac": "11:22:33:44:55:66",
      "ssid": "example-eduroam",
      "ip_addresses": ["10.20.30.40"],
      "total_events": 54,
      "roaming_timeline": [
        {"time": "2026-07-08 11:01:27", "ap": "APBS-01"},
        ...
      ]
    }
  ]
}
```

**Usage examples:**
```python
# Roaming history (default: 30 events, Informational only)
client_roaming("user12345")

# Roaming history by MAC address
client_roaming("aa:bb:cc:dd:ee:ff")

# More events for detailed analysis
client_roaming("user12345", limit=50)

# All severities (Critical, Warning, etc.) untuk troubleshooting disconnect
client_roaming("user12345", severity="")
```

**Use case:** 
- Track perpindahan AP user (roaming behavior)
- Identifikasi device yang sering disconnect/reconnect
- Analisis performance per device (RSSI, SNR, channel changes)
- Verifikasi roaming antar subnet (172.16.1.50 → 192.168.1.100)

---

### rogue_client_query
Query rogue client (AP/client tidak dikenal) dari vSZ. Deteksi AP asing/berbahaya yang terdeteksi jaringan wireless. Support filter by MAC rogue, SSID, tipe, domain, dan zone.

Rogue types: `Rogue`, `Suspect`, `Known`, `Unknown`, `AD_HOC`, `INFRASTRUCTURE`.

**Signature:** `rogue_client_query(rogue_mac: str | None = None, ssid: str | None = None, rogue_type: str | None = None, domain_id: str | None = None, zone_id: str | None = None, limit: int = 100, page: int = 1)`

**Return:**
```json
{
  "total": 42,
  "raw_total": 42,
  "has_more": false,
  "page": 1,
  "clients": [
    {
      "rogue_mac": "aa:bb:cc:dd:ee:ff",
      "ssid": "Free-WiFi",
      "type": "Rogue",
      "encryption": "WPA2-AES",
      "channel": "11",
      "rogue_ap_mac": "11:22:33:44:55:66",
      "last_detected": "2026-07-23 14:30:00",
      "classification": "Rogue",
      "detected_by": [
        {
          "ap_name": "AP-Lobby-1",
          "rssi": -65,
          "zone_name": "Lobby",
          "main_detector": true
        }
      ]
    }
  ]
}
```

**Key fields:**
- `rogue_mac` — MAC address AP/client rogue
- `type`, `classification` — klasifikasi rogue (Rogue, Suspect, Known, Unknown)
- `rogue_ap_mac` — MAC AP rogue (kalau rogue ini AP, bukan client)
- `detected_by` — list AP authorized yang detect rogue, dengan RSSI + apakah main detector
- `last_detected` — timestamp deteksi terakhir

**Usage examples:**
```python
# Semua rogue client (default 100)
rogue_client_query()

# Filter tipe Rogue saja
rogue_client_query(rogue_type="Rogue")

# Cari rogue dengan SSID tertentu (kemungkinan evil twin)
rogue_client_query(ssid="Office-WiFi", rogue_type="Rogue")

# Cari rogue by MAC spesifik
rogue_client_query(rogue_mac="aa:bb:cc:dd:ee:ff")

# Pagination
rogue_client_query(limit=50, page=2)
```

**Use case:**
- Deteksi evil twin / rogue AP (SSID sama dengan SSID korporat)
- Identifikasi AP asing di area coverage (rogue_mac, rssi)
- Audit security wireless (classification, encryption)

---

### ap_neighbors
Data RF neighbor AP untuk optimasi channel/power. Mendukung 3 scope: single AP, zone, atau semua AP. Setiap neighbor berisi SNR per band, channel aktif, dan model — input utama untuk algoritma RF optimization (DSATUR / Tabu Search / dll).

**Signature:** `ap_neighbors(ap_name: str | None = None, zone_id: str | None = None, include_detail: bool = False, max_aps: int = 50)`

**Scope:**
- `ap_name` → single AP (selalu full neighbor list)
- `zone_id` → semua AP di zone (summary by default)
- kosong → semua AP di semua zone (summary by default)

**Return (single AP):**
```json
{
  "ap": "AP-Floor3-30",
  "mac": "AA:BB:CC:30:66:E0",
  "model": "R650",
  "zone": "Campus - Building A",
  "cur_ch_24g": 11,
  "cur_width_24g": 20,
  "cur_ch_5g": 149,
  "cur_width_5g": 80,
  "total_neighbors": 20,
  "neighbors": [
    {
      "name": "AP-Floor4-18",
      "mac": "DD:EE:FF:2F:2C:90",
      "model": "R720",
      "ip": "192.168.1.87",
      "ch_24g": 11,
      "width_24g": 20,
      "snr_24g": 23,
      "ch_5g": 40,
      "width_5g": 40,
      "snr_5g": 0
    }
  ]
}
```

**Return (zone/all, summary default):**
```json
{
  "scope": "zone:xxxxxxxx-xxxx-xxxx",
  "total_aps": 45,
  "queried": 45,
  "failed": 0,
  "aps": [
    {
      "ap": "AP-Floor3-30",
      "mac": "AA:BB:CC:30:66:E0",
      "neighbors": 20,
      "cur_ch_24g": 11,
      "cur_ch_5g": 149,
      "best_snr_24g": 25,
      "avg_snr_24g": 14.8,
      "best_snr_5g": 8,
      "avg_snr_5g": 3.2,
      "co_ch_24g": 4,
      "co_ch_5g": 2
    }
  ]
}
```

**Return (zone/all, include_detail=True):**
```json
{
  "scope": "zone:xxxxxxxx-xxxx-xxxx",
  "total_aps": 45,
  "queried": 45,
  "failed": 0,
  "aps": [
    {
      "ap": "AP-Floor3-30",
      "mac": "AA:BB:CC:30:66:E0",
      "cur_ch_24g": 11,
      "cur_ch_5g": 149,
      "neighbors": [ ... ]
    }
  ]
}
```

**Summary fields:**
- `neighbors` — total neighbor count
- `cur_ch_24g` / `cur_ch_5g` — channel AP sendiri (untuk co-channel detection)
- `best_snr_24g`, `avg_snr_24g` — SNR stats (SNR 0 = tidak terdengar, dikecualikan dari stats)
- `co_ch_24g` / `co_ch_5g` — jumlah neighbor di channel yang sama dengan SNR > 0 (interference)

**Neighbor fields (normalized, compact):**
- `ch_24g`, `width_24g`, `snr_24g` — channel/width/SNR 2.4GHz
- `ch_5g`, `width_5g`, `snr_5g` — channel/width/SNR 5GHz
- `ch_6g`, `width_6g`, `snr_6g` — channel/width/SNR 6GHz (WiFi 6E only, biasanya null)
- `snr` value 0 = neighbor di band tersebut tapi tidak terdengar (no interference)

**Usage examples:**
```python
# Single AP — full neighbor list
ap_neighbors(ap_name="AP-Floor3-30")

# Zone summary (compact, co-channel detection)
ap_neighbors(zone_id="zone-uuid-here")

# Zone with full neighbor detail (untuk RF optimization input)
ap_neighbors(zone_id="zone-uuid-here", include_detail=True)

# All zones summary
ap_neighbors()

# All zones, limit to 100 APs
ap_neighbors(max_aps=100)
```

**Use case:**
- RF channel planning — identifikasi co-channel interference
- Coverage overlap analysis — neighbor SNR tinggi = overlap parah
- Input untuk optimization algorithm (DSATUR, Tabu Search)
- Power tuning — neighbor dengan SNR >30 dB = kurangi TX power

---

### optimize_wifi_rf
Optimasi channel & TX power WiFi (dry-run — tidak mengubah konfigurasi). Menggunakan DSATUR greedy coloring untuk initial assignment, lalu Tabu Search untuk refine. TX power disesuaikan berdasarkan SNR neighbor terdekat.

**Scope:** zone (zone_id), lantai (zone_id + floor), atau AP spesifik (ap_names). AP di luar scope yang audible tetap masuk graph sebagai **anchor** (read-only) — channel-nya dipertahankan dan dihindari.

**Signature:** `optimize_wifi_rf(zone_id=None, floor=None, ap_names=None, band="5g", channel_width=0, allow_dfs=False, max_aps=100, channels=None)`

**Args:**
- `zone_id`: Zone ID untuk scope per gedung/fakultas.
- `floor`: Nomor lantai (match pattern `AP{floor}` di nama AP, e.g. "2", "03"). Butuh zone_id.
- `ap_names`: Comma-separated AP names (override zone/floor).
- `band`: `"5g"` atau `"2.4g"`.
- `channel_width`: MHz (0 = auto-detect dari konfig AP saat ini).
- `allow_dfs`: Sertakan channel DFS 52-64, 100-144 (default False). Ignored jika `channels` di-set.
- `max_aps`: Maks AP yang di-query (default 100).
- `channels`: Custom channel pool (overrides `allow_dfs`). Contoh: `[36, 40, 44, 48]` untuk UNII-1 only, atau `[149, 153, 157, 161]` untuk UNII-3 tanpa 165. Channel tidak valid untuk band diabaikan.

**Return:**
```json
{
  "mode": "dry_run",
  "scope": "zone:Campus - Building A",
  "band": "5g",
  "channel_width": 40,
  "allow_dfs": false,
  "channels_available": 9,
  "graphs_nodes": 11,
  "score_before": 48.0,
  "score_after": 0.0,
  "score_dsatur_only": 0.0,
  "improvement_pct": 100.0,
  "aps_total": 11,
  "aps_changed": 6,
  "aps_unchanged": 5,
  "recommendations": [
    {
      "ap": "AP-Floor2-01",
      "cur_ch": 153,
      "cur_width": 20,
      "rec_ch": 36,
      "rec_width": 40,
      "cur_secondary": null,
      "rec_secondary": 40,
      "changed": true,
      "rec_power": "max",
      "power_reason": "no close neighbor — coverage priority",
      "reason_ch": "ch153 → ch36: 1 co-channel: AP-Floor1-02(25dB)"
    },
    {
      "ap": "AP-Floor2-04",
      "cur_ch": 161,
      "cur_width": 20,
      "rec_ch": 161,
      "rec_width": 40,
      "cur_secondary": null,
      "rec_secondary": 165,
      "changed": false,
      "rec_power": "max",
      "power_reason": "no close neighbor — coverage priority"
    }
  ],
  "note": "Review recommendations before applying. No config changed."
}
```

**Score fields:**
- `score_before` — total weighted interference dengan channel saat ini
- `score_after` — total interference setelah optimisasi (DSATUR + Tabu)
- `score_dsatur_only` — score setelah DSATUR saja (sebelum Tabu refine)
- `improvement_pct` — persentase penurunan interference

**Recommendation fields:**
- `cur_ch` / `rec_ch` — channel saat ini / rekomendasi
- `cur_width` / `rec_width` — channel width
- `cur_secondary` / `rec_secondary` — secondary (extension) channel untuk 5GHz bonding (5GHz only, `null` untuk 20MHz atau 2.4GHz)
- `changed` — true jika channel berubah
- `rec_power` — rekomendasi TX power: `max`, `high`, `half`, `quarter`, `min`
- `power_reason` — alasan power (SNR neighbor terdekat)
- `reason_ch` — alasan channel change (co-channel/adjacent neighbors)

**Power recommendations:**
| Strongest neighbor SNR | Power | Alasan |
|---|---|---|
| > 35 dB | `min` | Cell oversized, overlap parah |
| 30-35 dB | `quarter` | Overlap kuat |
| 25-30 dB | `half` | Overlap moderat |
| 15-25 dB | `high` | Overlap ringan |
| < 15 dB | `max` | Coverage priority |

**KPI snapshot (before vs after):**
```json
{
  "interference": {
    "total":             {"before": 104.6, "after": 0.0},
    "co_channel_pairs":  {"before": 7, "after": 0},
    "adjacent_pairs":    {"before": 0, "after": 0},
    "max_per_ap":        {"before": 48.0, "after": 0.0}
  },
  "channel_reuse": {
    "before":               {"149": 2, "153": 3, "157": 3, "161": 2, "120": 1},
    "after":                {"36": 3, "48": 3, "149": 2, "161": 1},
    "max_per_channel":      {"before": 3, "after": 3},
    "channels_used":        {"before": 5, "after": 4},
    "reuse_efficiency_pct": {"before": 56, "after": 44}
  },
  "snr_quality": {
    "avg_neighbor_snr":   17.2,
    "strong_overlap_pct": 18,
    "isolated_aps":       2
  },
  "power": {
    "avg_delta_db":      -5.3,
    "changes":           9,
    "coverage_risk_aps": 2
  }
}
```

**KPI fields:**
- `interference.total` — weighted SNR×overlap score (lower = better)
- `interference.co_channel_pairs` — AP pairs on same channel (must eliminate)
- `interference.adjacent_pairs` — AP pairs on overlapping channel (2.4G inherent)
- `interference.max_per_ap` — worst-case interference contribution per AP
- `channel_reuse.before/after` — AP count per channel
- `channel_reuse.max_per_channel` — channel paling padat
- `channel_reuse.reuse_efficiency_pct` — channels_used / ideal_max × 100
- `snr_quality.avg_neighbor_snr` — mean SNR semua edge (physical, tidak berubah)
- `snr_quality.strong_overlap_pct` — % edge dengan SNR > 25 dB
- `snr_quality.isolated_aps` — AP tanpa neighbor audible (coverage hole risk)
- `power.avg_delta_db` — rata-rata reduksi power (0 = semua max)
- `power.changes` — jumlah AP yang power disesuaikan
- `power.coverage_risk_aps` — AP dengan power min/quarter (waspada coverage)

**Verdict:**
| Label | Kondisi |
|---|---|
| `excellent` | Co-channel = 0, no coverage risk |
| `good` | Co-channel = 0 (dengan coverage note) atau improvement ≥50% |
| `fair` | Improvement 20-50%, ada residual interference |
| `warning` | Isolated APs (coverage hole) atau reuse efficiency < 30% |

**Usage examples:**
```python
# Optimisasi 5GHz seluruh zone
optimize_wifi_rf(zone_id="zone-uuid-here", band="5g")

# Optimisasi per lantai (floor 2)
optimize_wifi_rf(zone_id="zone-uuid-here", floor="2", band="5g")

# Optimisasi AP spesifik
optimize_wifi_rf(ap_names="AP-Floor1-01,AP-Floor2-03", band="5g")

# Optimisasi 2.4GHz
optimize_wifi_rf(zone_id="zone-uuid-here", band="2.4g")

# Dengan DFS channels
optimize_wifi_rf(zone_id="zone-uuid-here", band="5g", allow_dfs=True)

# Force channel width 80MHz
optimize_wifi_rf(zone_id="zone-uuid-here", band="5g", channel_width=80)

# Custom channel pool — UNII-3 tanpa ch165
optimize_wifi_rf(zone_id="zone-uuid-here", band="5g", channels=[149, 153, 157, 161])

# Hanya UNII-1 (36-48)
optimize_wifi_rf(zone_id="zone-uuid-here", band="5g", channels=[36, 40, 44, 48])

# Hanya non-overlapping 2.4GHz (1, 6, 11)
optimize_wifi_rf(zone_id="zone-uuid-here", band="2.4g", channels=[1, 6, 11])
```

**Algorithm:**
1. **DSATUR** — greedy graph coloring: AP paling "jenuh" (paling banyak neighbor diwarnai) diproses duluan, tiap AP dapat channel dengan minimum interference.
2. **Tabu Search** — local search: coba swap channel per AP, escape local optima via tabu memory (15 moves), aspiration criterion (accept tabu if beats global best).
3. **Power heuristic** — per AP, cek SNR neighbor terdekat yang masih punya interference, adjust TX power.

**Anchor handling:** AP di luar scope (beda lantai/zone) yang audible = anchor. Channel anchor tidak diubah. DSATUR/Tabu menghindari channel anchor saat assign AP yang di-optimisasi.

---

### apply_rf_recommendation ⚠️ BELUM DIUJI
> **Status: SUDAH DITULIS, BELUM DIUJI ke vSZ live.** Tool ini push konfigurasi via PATCH `/aps/{apMac}`. Perlu test ke device real sebelum production use.

Apply rekomendasi RF optimization ke AP via vSZ API (push konfigurasi). Gunakan `optimization_id` dari hasil `optimize_wifi_rf`. Auto-set `channelSelectMode=None` supaya channel manual tidak di-override vSZ.

**PERINGATAN:** Config langsung diterapkan ke AP. Client aktif akan terputus sementara saat channel berubah.

**Signature:** `apply_rf_recommendation(optimization_id: str, ap_names: str = "", confirm: bool = False)`

**Args:**
- `optimization_id`: ID dari hasil optimize_wifi_rf (TTL 30 menit).
- `ap_names`: Comma-separated AP names untuk apply selektif (kosong = semua AP yang changed).
- `confirm`: **Wajib `True`** untuk eksekusi (safety latch).

**Return:**
```json
{
  "optimization_id": "opt_a1b2c3d4",
  "band": "5g",
  "total_selected": 3,
  "applied": 3,
  "failed": 0,
  "results": [
    {"ap": "AP-Floor2-01", "mac": "AA:BB:CC:30:66:E0", "status": "applied"},
    {"ap": "AP-Floor2-04", "mac": "DD:EE:FF:2F:2C:90", "status": "applied"}
  ]
}
```

**Usage examples:**
```python
# Apply semua rekomendasi yang changed
apply_rf_recommendation(optimization_id="opt_a1b2c3d4", confirm=True)

# Apply hanya AP tertentu
apply_rf_recommendation(optimization_id="opt_a1b2c3d4", ap_names="AP-A,AP-C", confirm=True)
```

**Flow lengkap:**
```
1. optimize_wifi_rf(zone_id="xxx", band="5g")  → dapat optimization_id
2. Review rekomendasi
3. apply_rf_recommendation(optimization_id="opt_xxx", confirm=True)
```

---

### apply_ap_config ⚠️ BELUM DIUJI
> **Status: SUDAH DITULIS, BELUM DIUJI ke vSZ live.** Tool ini push konfigurasi via PATCH `/aps/{apMac}`. Perlu test ke device real sebelum production use.

Apply config RF manual ke AP via vSZ API (override optimization). Set channel, channel width, dan/atau TX power langsung. Auto-disable auto channel selection.

**PERINGATAN:** Config langsung diterapkan ke AP. Client aktif akan terputus sementara saat channel berubah.

**Signature:** `apply_ap_config(zone_id=None, ap_names=None, band="5g", channel=0, channel_width=0, power=None, confirm=False)`

**Args:**
- `zone_id`: Apply ke SEMUA AP di zone ini.
- `ap_names`: Comma-separated AP names (override zone_id).
- `band`: `"5g"` atau `"2.4g"`.
- `channel`: Target channel (wajib, e.g. 36, 149, 1).
- `channel_width`: MHz (0 = default 20).
- `power`: TX power — label (`max`, `high`, `half`, `quarter`, `min`) atau API value (`Full`, `-3dB(1/2)`, dll). `None` = keep current.
- `confirm`: **Wajib `True`** untuk eksekusi (safety latch).

**Power mapping:**
| Label | API txPower | dB |
|---|---|---|
| `max` / `full` | `Full` | 0 |
| `high` | `-3dB(1/2)` | -3 |
| `half` | `-6dB(1/4)` | -6 |
| `quarter` | `-9dB(1/8)` | -9 |
| `min` | `Min` | -12 |

**Return:**
```json
{
  "scope": "zone:zone-uuid-here",
  "band": "5g",
  "channel": 36,
  "channel_width": 20,
  "power": "Full",
  "total_aps": 12,
  "applied": 12,
  "failed": 0,
  "results": [
    {"ap": "AP-Floor1-01", "mac": "AA:BB:CC:30:66:E0", "status": "applied"},
    {"ap": "AP-Floor1-02", "mac": "DD:EE:FF:2F:2C:90", "status": "applied"}
  ]
}
```

**Usage examples:**
```python
# Semua AP di zone X pakai channel 36 (5GHz)
apply_ap_config(zone_id="zone-uuid-here", band="5g", channel=36, confirm=True)

# AP tertentu ke channel 1, power half
apply_ap_config(ap_names="AP-Lobby-1,AP-Lobby-2", band="2.4g", channel=1, power="half", confirm=True)

# Semua AP zone X ke channel 149, width 40, power max
apply_ap_config(zone_id="zone-uuid-here", band="5g", channel=149, channel_width=40, power="max", confirm=True)
```

**Safety:** Tanpa `confirm=True`, tool return error `safety_latch` tanpa mengubah apapun.

---

### alarm_list
List active alarms from vSZ with optional severity, time, and text filters.

**Signature:** `alarm_list(limit: int = 50, severity: str | None = None, hours_back: int | None = 24, text_search: str | None = None, page: int = 1)`

**Return:** `{"total": N, "has_more": bool, "page": int, "limit": int, "alarms": [...]}`

Alarm fields: `id`, `time_ms`, `type`, `code`, `severity`, `category`, `activity`.

---

### domain_list
List all administration domains visible to the current vSZ user.

**Signature:** `domain_list()`

**Return:** `[{"id": "...", "name": "...", "description": "...", "status": "..."}]`

Note: Returns error on restricted accounts (read-only users get 403).

---

### toggle_wlan
Enable or disable a WLAN (SSID) in a zone without deleting config.

**Signature:** `toggle_wlan(zone_id: str, wlan_id: str, enabled: bool, confirm: bool = False)`

**Safety:** Confirm gate required. Note: Requires vSZ v12+. Returns 404 on v11_1 and earlier.

---

### modify_wlan
Modify an existing WLAN configuration. Only provided fields are updated — unspecified fields keep current values.

**Signature:** `modify_wlan(zone_id, wlan_id, passphrase=None, encryption=None, access_vlan=None, description=None, hidden=None, max_clients=None, client_isolation=None, confirm=False)`

**Return:** `{"zone_id": "...", "wlan_id": "...", "status": "modified", "updated_fields": [...]}`

Safety: `confirm=True` gate required. Passphrase must be 8-63 chars. Requires admin credentials.

---

### reboot_ap
Reboot an access point by name. Resolves MAC from query_ap.

**Signature:** `reboot_ap(ap_name: str, confirm: bool = False)`

**Safety:** Confirm gate required. Note: Virtual/test AP may return 500.

---

### disconnect_client
Disconnect a wireless client from an AP by MAC address.

**Signature:** `disconnect_client(client_mac: str, ap_mac: str, confirm: bool = False)`

**Safety:** Confirm gate required.

---

### wlan_traffic_stats
Per-WLAN traffic statistics aggregated from all connected clients via client query. Returns total rx/tx MB and client count per SSID with per-zone breakdown.

**Signature:** `wlan_traffic_stats(ssid: str | None = None, zone_id: str | None = None)`

**Return:** `{"wlans": [{"ssid", "total_clients", "total_rx_mb", "total_tx_mb", "zone_breakdown": [...]}], "total_wlans": N}`

---

### ap_traffic_stats
Per-AP traffic statistics aggregated from connected clients. Returns total rx/tx MB and client count per access point.

**Signature:** `ap_traffic_stats(zone_id: str | None = None, ap_name: str | None = None)`

**Return:** `{"aps": [{"ap_name", "ap_mac", "zone_name", "model", "total_clients", "total_rx_mb", "total_tx_mb"}], "total_aps": N}`

---

### zone_traffic_stats
Per-zone traffic statistics with AP count and active WLAN count.

**Signature:** `zone_traffic_stats()`

**Return:** `{"zones": [{"zone_name", "zone_id", "ap_count", "total_clients", "total_rx_mb", "total_tx_mb", "active_wlans"}], "total_zones": N}`

Source: Aggregation from `POST /query/client` with pagination (500/page).

---

### controller_stats
Controller health information — node model, version, role, uptime.

**Signature:** `controller_stats()`

**Return:** `{"total_nodes": N, "nodes": [{"name", "model", "version", "ap_version", "role", "uptime_days", "control_ip", "serial"}], "note": "CPU/memory/storage not exposed by vSZ public API"}`

---

## Available Tools — ICX Switch

### ruckus_list_devices
List semua ICX switch di inventory.

**Signature:** `ruckus_list_devices()`

**Return:**
```json
[
  {"host": "192.168.1.50", "name": "switch-core-01", "vendor": "ruckus", "role": "core-switch", "location": "datacenter-1"}
]
```

---

### ruckus_device_info
Info satu device (version, model, uptime).

**Signature:** `ruckus_device_info(host: str)`

---

### ruckus_device_status
Status up/down satu device.

**Signature:** `ruckus_device_status(host: str)`

---

### ruckus_device_interfaces_summary
Ringkas interface satu device.

**Signature:** `ruckus_device_interfaces_summary(host: str)`

**Return:**
```json
[
  {"name": "1/2/1", "status": "up", "protocol": "up", "speed": "10G", "duplex": "Full", "state": "Forward", "description": "TR-TO-BSI"}
]
```

---

### ruckus_device_interfaces_down
Interface down di satu device.

**Signature:** `ruckus_device_interfaces_down(host: str)`

---

### ruckus_device_interfaces_errors
Interface dengan error counter > 0 di satu device.

**Signature:** `ruckus_device_interfaces_errors(host: str)`

**Return:**
```json
[
  {"host": "192.168.1.50", "name": "1/1/1", "input_errors": 12, "output_errors": 0, "crc": 3}
]
```

---

### ruckus_device_interfaces_stats
Utilization dan traffic statistics untuk semua interface Ethernet fisik di satu device. Berguna untuk capacity planning, performance investigation, dan bandwidth audit.

**Signature:** `ruckus_device_interfaces_stats(host: str)`

**Return:**
```json
[
  {
    "host": "192.168.1.50",
    "name": "1/2/2",
    "input_errors": 277,
    "output_errors": 0,
    "crc": 275,
    "input_rate_bps": 151334320,
    "input_rate_pps": 15334,
    "input_util_pct": 1.53,
    "output_rate_bps": 10071808,
    "output_rate_pps": 4996,
    "output_util_pct": 0.1,
    "packets_in": 38796808314,
    "bytes_in": 42530714569326,
    "packets_out": 17937893869,
    "bytes_out": 6204007138050,
    "broadcasts_in": 1758727810,
    "multicasts_in": 1327975543,
    "broadcasts_out": 5477273,
    "multicasts_out": 24640251
  }
]
```

**Rate fields (300-second average):**
- `input_rate_bps`, `output_rate_bps` — bits per second
- `input_rate_pps`, `output_rate_pps` — packets per second
- `input_util_pct`, `output_util_pct` — utilization percentage (0-100%)

**Cumulative counters:**
- `packets_in`, `packets_out` — total packet count since boot
- `bytes_in`, `bytes_out` — total byte count since boot
- `broadcasts_*`, `multicasts_*` — broadcast/multicast counters

**Note:** Hanya interface Ethernet fisik (format `x/y/z`) yang dicek. Interface management (`mgmt`) dan virtual (`ve`) diabaikan.

---

### ruckus_device_ping
Ping dari device ICX ke IP target (IPv4). Problem: device ke host A reachable, host B unreachable. Jalankan langsung dari switch — gak perlu PC terpisah.

**Signature:** `ruckus_device_ping(host: str, ip: str, source: str | None = None)`

**Return:**
```json
{
  "host": "192.168.1.50",
  "target_ip": "8.8.8.8",
  "source_ip": "10.20.30.1",
  "reached": true,
  "rtt_ms": 22,
  "success_rate_pct": 100,
  "rtt_min_ms": 22,
  "rtt_avg_ms": 22,
  "rtt_max_ms": 22
}
```

---

### ruckus_device_ping_ipv6
Ping IPv6 dari device ICX.

**Signature:** `ruckus_device_ping_ipv6(host: str, ip: str)`

---

### ruckus_device_traceroute
Traceroute IPv4 dari device ICX — lihat path routing yang dilalui paket.

**Signature:** `ruckus_device_traceroute(host: str, ip: str, source_ip: str | None = None)`

**Return:**
```json
[
  {"hop": 1, "ip": "10.0.1.1", "rtt1_ms": 1.0, "rtt2_ms": 0.5, "rtt3_ms": 0.5},
  {"hop": 2, "ip": "10.0.1.2", "rtt1_ms": 0.5, "rtt2_ms": 0.5, "rtt3_ms": 0.5},
  {"hop": 6, "ip": "1.1.1.1", "rtt1_ms": 0.5, "rtt2_ms": 1.0, "rtt3_ms": 1.0}
]
```

---

### ruckus_device_traceroute_ipv6
Traceroute IPv6 dari ICX switch.

**Signature:** `ruckus_device_traceroute_ipv6(host: str, ip: str)`

---

### ruckus_device_ip_addresses
IP address bindings di satu device (ve interfaces).

**Signature:** `ruckus_device_ip_addresses(host: str)`

---

### ruckus_device_ip_routes
IP routing table (`show ip route`). Optional longest-prefix lookup by destination IP/CIDR. Berguna untuk cek gateway, next-hop, route type (Static/Connected/BGP/OSPF), dan troubleshoot routing.

**Signature:** `ruckus_device_ip_routes(host: str, destination: str | None = None)`

**Return (full table):**
```json
{
  "host": "192.168.1.50",
  "destination": null,
  "total_routes": 41,
  "routes": [
    {
      "line": 1,
      "destination": "0.0.0.0/0",
      "gateway": "10.3.3.1",
      "port": "ve 2050",
      "cost": "1/1",
      "distance": 1,
      "metric": 1,
      "type": "S",
      "type_name": "Static",
      "uptime": "130d"
    },
    {
      "line": 2,
      "destination": "10.3.3.0/30",
      "gateway": "DIRECT",
      "port": "ve 2050",
      "distance": 0,
      "metric": 0,
      "type": "D",
      "type_name": "Connected",
      "uptime": "130d"
    }
  ]
}
```

**Return (lookup, no match):**
```json
{
  "host": "192.168.1.50",
  "destination": "1.1.1.1/24",
  "total_routes": 0,
  "routes": [],
  "note": "no matching entry"
}
```

**Key fields per route:**
- `destination` — network CIDR (e.g. `0.0.0.0/0`, `192.168.0.0/22`)
- `gateway` — next-hop IP atau `DIRECT` (connected route)
- `port` — outgoing interface (`ve 2050`)
- `distance`, `metric` — administrative distance + metric (dipecah dari cost)
- `type` / `type_name` — S=Static, D=Connected, B=BGP, O=OSPF, R=RIP

**Usage examples:**
```python
# Full routing table
ruckus_device_ip_routes("192.168.1.50")

# Lookup longest-prefix match untuk IP
ruckus_device_ip_routes("192.168.1.50", "8.8.8.8")

# Lookup exact CIDR
ruckus_device_ip_routes("192.168.1.50", "0.0.0.0/0")
```

**Note:** Hostname ditolak validator (route destination harus IP/CIDR). "Can't find matching entry" dari switch di-return sebagai `note`.

---

### ruckus_device_ipv6_routes
IPv6 routing table (`show ipv6 route`). Optional longest-prefix lookup by destination IPv6/prefix. Berguna untuk cek IPv6 gateway, next-hop, route type (Static/Connected/Local).

**Signature:** `ruckus_device_ipv6_routes(host: str, destination: str | None = None)`

**Return (full table):**
```json
{
  "host": "192.168.1.50",
  "destination": null,
  "total_routes": 21,
  "routes": [
    {
      "type": "S",
      "type_name": "Static",
      "destination": "2000::/3",
      "gateway": "2001:db8:b:60::a",
      "port": "ve 2050",
      "cost": "1/1",
      "distance": 1,
      "metric": 1,
      "uptime": "130d"
    },
    {
      "type": "C",
      "type_name": "Connected",
      "destination": "2001:db8:60::ffff/128",
      "gateway": "::",
      "port": "loopback 1",
      "cost": "0/0",
      "distance": 0,
      "metric": 0,
      "uptime": "130d"
    }
  ]
}
```

**Key fields per route:**
- `destination` — IPv6 prefix (e.g. `2000::/3`, `2001:db8:b:60::/64`)
- `gateway` — next-hop IPv6 atau `::` (connected/local route)
- `port` — outgoing interface (`ve 2050`, `loopback 1`)
- `type` / `type_name` — S=Static, C=Connected, L=Local, B=BGP, O=OSPF, R=RIP

**Usage examples:**
```python
# Full IPv6 routing table
ruckus_device_ipv6_routes("192.168.1.50")

# Lookup longest-prefix match untuk IPv6
ruckus_device_ipv6_routes("192.168.1.50", "2606:4700:4700::1")

# Lookup exact prefix
ruckus_device_ipv6_routes("192.168.1.50", "2000::/3")
```

**Note:** Destination harus IPv6/prefix (hostname + IPv4 ditolak validator). Parser handle prefix panjang yang wrap ke baris berikutnya.

---

### ruckus_device_vlan_summary
VLAN summary (total + list) di satu device.

**Signature:** `ruckus_device_vlan_summary(host: str)`

---

### ruckus_device_port_vlan
VLAN membership per port (untagged/tagged).

**Signature:** `ruckus_device_port_vlan(host: str, port: str)`

---

### ruckus_device_mac_table_vlan
MAC address table untuk VLAN tertentu.

**Signature:** `ruckus_device_mac_table_vlan(host: str, vlan_id: int)`

---

### ruckus_device_find_mac
Cari port tempat MAC address tertentu terhubung.

**Signature:** `ruckus_device_find_mac(host: str, mac: str)`

---

### ruckus_device_lag_summary
LAG (Link Aggregation Group) summary di satu device.

**Signature:** `ruckus_device_lag_summary(host: str)`

---

### ruckus_device_chassis_health
Chassis health: power supply, fan, temperature per slot.

**Signature:** `ruckus_device_chassis_health(host: str)`

---

### ruckus_device_ipv6_interfaces
IPv6 interface addresses di satu device.

**Signature:** `ruckus_device_ipv6_interfaces(host: str)`

---

## Available Tools — Config Backup

### ruckus_device_config_backup
Backup switch configuration ke filesystem. File selalu lengkap (gak di-mask), mode `0600`, restore-ready. Default return metadata only supaya secret (SNMP community, RADIUS key, password hash) gak masuk agent context.

**Signature:** `ruckus_device_config_backup(host: str, config_type: str = "running", include_config: bool = False)`

- `config_type`: `"running"` (RAM, live) atau `"startup"` (flash, boot config)
- `include_config`: default `False` (metadata only). `True` = return raw config text (opt-in, logged WARNING)

**Return (default, metadata only):**
```json
{
  "host": "192.168.1.50",
  "config_type": "running",
  "path": "backups/192.168.1.50_running_20260724_130000.cfg",
  "sha256": "a3f5...e91c",
  "size_kb": 42.3,
  "line_count": 318,
  "backed_up_at": "2026-07-24 13:00:00"
}
```

**Return (include_config=True):** tambah key `"config"` berisi raw text.

**Usage examples:**
```python
# Backup rutin (safe — secret gak masuk context)
ruckus_device_config_backup("192.168.1.50")

# Backup startup config
ruckus_device_config_backup("192.168.1.50", config_type="startup")

# Backup + baca config (opt-in, untuk review/diff)
ruckus_device_config_backup("192.168.1.50", include_config=True)
```

**Restore:** File `backups/{host}_{type}_{ts}.cfg` = config FastIron mentah. Restore via TFTP/SCP/paste ke enable mode switch. File selalu lengkap.

---

### ruckus_device_config_diff
Cek apakah config current berbeda dari backup terakhir, via sha256 compare. Tanpa expose config text — aman untuk monitoring config drift.

**Signature:** `ruckus_device_config_diff(host: str, config_type: str = "running")`

**Return:**
```json
{
  "host": "192.168.1.50",
  "config_type": "running",
  "changed": true,
  "current_sha256": "b1c2...9f8e",
  "last_backup_sha256": "a3f5...e91c",
  "last_backup_path": "backups/192.168.1.50_running_20260724_130000.cfg",
  "last_backup_at": "2026-07-24 13:00:00"
}
```

**Note:** Kalau belum ada backup sebelumnya, `changed: true` + `note: "no previous backup found"`.

---

### ruckus_all_device_backup
Bulk backup config semua device di inventory (metadata only, secret gak masuk context).

**Signature:** `ruckus_all_device_backup(config_type: str = "running")`

**Return:** list metadata per device (sama format kayak `ruckus_device_config_backup`).

---

## MCP Server Connectivity Tests

Ini tool **bukan dari SSH device**, tapi langsung dari MCP server — cepat, gak butuh login.

### ping_device
Ping ICMP dari MCP server ke host.

**Signature:** `ping_device(host: str, count: int = 4)`

**Return:**
```json
{
  "host": "8.8.8.8",
  "reachable": true,
  "packets_sent": 4,
  "packets_received": 4,
  "packet_loss_pct": 0.0,
  "rtt_min_ms": 12.3,
  "rtt_avg_ms": 15.1,
  "rtt_max_ms": 18.2
}
```

---

### check_port
Cek TCP port dari MCP server.

**Signature:** `check_port(host: str, port: int, timeout: int = 3)`

**Return:**
```json
{"host": "192.168.1.1", "port": 22, "status": "open"}
```
Status: `open`, `closed`, `timeout`, `error`

---

### http_latency
HTTP GET latency dari MCP server.

**Signature:** `http_latency(url: str, timeout: int = 5)`

**Return:**
```json
{
  "url": "https://google.com",
  "status_code": 200,
  "latency_ms": 42.15
}
```

---

## Available Tools — Inventory Filtering

### ruckus_devices_by_location
Filter device by location.

**Signature:** `ruckus_devices_by_location(location: str)`

**Return:**
```json
[{"host": "192.168.1.50", "name": "switch-core-01", "location": "datacenter-1", "role": "core-switch"}]
```

---

### ruckus_devices_by_role
Filter device by role.

**Signature:** `ruckus_devices_by_role(role: str)`

**Return:**
```json
[{"host": "192.168.1.50", "name": "switch-core-01", "role": "core-switch", "location": "datacenter-1"}]
```

---

### ruckus_all_device_info
Info semua device (bulk).

**Signature:** `ruckus_all_device_info()`

---

### ruckus_all_device_status
Status semua device (bulk).

**Signature:** `ruckus_all_device_status()`

---

## Workflows

### Cek AP yang down
```
1. ap_down() — semua AP down
2. zone_ap_list(zone_id) — per zone
```

### Cek AP bermasalah (high client)
```
1. ap_high_client_count(50) — AP dengan >50 client
2. ap_detail(ap_name) — detail AP
3. zone_status() — cek beban zone
```

### Troubleshoot RF performance per AP
```
1. ap_radio_stats(ap_name) — noise floor, airtime, retry/drop per radio
2. Lihat noise_floor_dbm: >-85 dBm = interferensi/noise tinggi
3. Lihat airtime_busy_pct + retry naik = channel congestion → butuh channel planning
4. Lihat drop counter besar = packet loss (RF atau kapasitas)
5. Bandingkan clients per band: 2.4G penuh + 5G kosong = band steering issue
```

### Cari user / device dengan client_search
```
1. client_search("nama_user") — cari berdasarkan username (compact view)
2. client_search("aa11.bb22.cc33") — cari berdasarkan MAC
3. client_search("192.168.1.100") — cari berdasarkan IP
4. client_search("nama_user", include_traffic=True) — dengan traffic stats
```
Return semua device untuk user tersebut — termasuk info AP, RSSI, SNR, dan auth. Set `include_traffic=True` untuk tx/rx MB dan MCS rates.

### Cek SSID di zone tertentu
```
1. ssid_list_all() — semua SSID di semua zone
2. ssid_list(zone_id) — filter per zone
3. ssid_detail(wlan_id, zone_id) — detail konfigurasi
```

### Cek AP utilization (per band)
```
1. ap_status(limit=50) — 50 AP dengan airtime/capacity per band
2. ap_status(zone_id="zone-001") — filter per zone
3. ap_high_client_count(threshold) — AP dengan client padat
4. ap_detail(ap_name) — detail satu AP
```
Lihat `airtime_24g_pct`, `airtime_5g_pct`, `capacity_24g_pct`, `capacity_5g_pct` untuk identifikasi AP overload.

### Inventarisasi device per lokasi
```
1. ruckus_devices_by_location("datacenter-1") — device DC Jakarta
2. ruckus_all_device_info() — info lengkap semua device
3. ruckus_device_interfaces_down(host) — interface down per device
```

### Cek error interface
```
1. ruckus_devices_by_role("core-switch") — fokus core
2. ruckus_device_interfaces_errors(host) — error per device
```

### Cek bandwidth utilization per interface
```
1. ruckus_device_interfaces_stats(host) — rate + cumulative counters semua port
2. Filter port dengan util_pct tinggi (>80%) untuk identifikasi bottleneck
3. Bandingkan input_rate vs output_rate untuk detect asymmetric traffic
```

### Backup config switch
```
1. ruckus_device_config_backup(host) — backup rutin (metadata only, secret aman)
2. ruckus_device_config_diff(host) — cek config berubah sejak backup terakhir
3. ruckus_all_device_backup() — bulk backup semua device sekaligus
4. Restore: baca file backups/{host}_*.cfg, push via TFTP/SCP/paste ke switch
```

### Optimisasi channel & power WiFi
```
1. ap_radio_stats(ap_name) — identifikasi AP dengan RF issue (noise tinggi, retry/drop)
2. ap_neighbors(zone_id) — lihat summary topology neighbor + co-channel count per AP
3. optimize_wifi_rf(zone_id, band="5g") — jalankan optimisasi (dry-run, tidak push)
4. Cek verdict: excellent/good = aman apply, fair/warning = review dulu
5. optimize_wifi_rf(zone_id, floor="2", band="5g") — scope per lantai kalau zone besar
6. optimize_wifi_rf(zone_id, band="2.4g") — optimisasi 2.4GHz
7. optimize_wifi_rf(zone_id, band="5g", allow_dfs=True) — dengan DFS channels
```
Note: `optimize_wifi_rf` collect neighbor data secara internal — tidak perlu
panggil `ap_neighbors` terpisah sebelumnya. `ap_neighbors` digunakan untuk
inspeksi manual sebelum atau setelah optimisasi. Verdict `warning` biasanya
karena isolated AP (rekomendasi tetap valid tapi butuh site survey).

### Apply konfigurasi RF ke AP
```
A. Apply dari rekomendasi optimization:
1. optimize_wifi_rf(zone_id, band="5g") — dapat optimization_id
2. Review rekomendasi (channel, power, secondary)
3. apply_rf_recommendation(optimization_id="opt_xxx", confirm=True) — apply semua
4. apply_rf_recommendation(optimization_id="opt_xxx", ap_names="AP-A,AP-C", confirm=True) — selektif

B. Apply manual (tanpa optimisasi):
1. apply_ap_config(zone_id="xxx", band="5g", channel=36, confirm=True) — semua AP zone
2. apply_ap_config(ap_names="AP-A,AP-B", band="2.4g", channel=1, power="half", confirm=True) — AP tertentu
3. apply_ap_config(zone_id="xxx", band="5g", channel=149, channel_width=40, power="max", confirm=True)
```
PERINGATAN: Apply akan mengubah channel/power AP secara langsung. Client aktif
terputus sementara saat channel berubah. Selalu review dulu sebelum confirm=True.

---

## Notes

- vSZ tools → async REST API ke controller (httpx.AsyncClient), data realtime
- ICX tools → SSH per device, serial query (netmiko, sync)
- Traffic tools → aggregasi dari client query, rx/tx bytes per WLAN/AP/zone
- Alarm tools → filter by severity, hours, text search
- RF optimizer → DSATUR + Tabu Search, dry-run, apply dengan confirm=True
- Field kosong → `null`
- Location/role device dari inventory (field optional)
- Error handling → tool return dict `{"error": "...", "detail": "..."}` bukan exception
- Session reuse → vSZ 10-min TTL, auto re-login
- Security → API key + IP whitelist via ASGI SecurityMiddleware
- Confirm gates → 7 destructive tools require `confirm=True`: apply_rf_recommendation, apply_ap_config, create_wlan, modify_wlan, reboot_ap, disconnect_client, toggle_wlan