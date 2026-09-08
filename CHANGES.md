# Changelog — MCP Ruckus

All significant changes to this project are recorded here.
Format: [ISO date] — Short description + technical details.

## Release Notes

| Date | Version / Topic | Summary |
|---|---|---|
| 2026-09-08 | Community + docs polish | Add issue/PR templates and Dependabot; `README.md` notes the GUI **Inventory** page edits `devices.yaml`; `docs/QUICKSTART.md` §4 points OpenClaw/Claude to README (Hermes kept inline) to avoid duplicating agent configs |
| 2026-09-08 | Quickstart: SERVER_IP not localhost | `docs/QUICKSTART.md` — agent URLs, admin login, and curl verify now use `{SERVER_IP}` with a "use `localhost` if same machine" note, matching `README.md` |
| 2026-09-08 | Quickstart: systemd for production | `docs/QUICKSTART.md` — "Start the server" Option B is now systemd (install units + polkit rule, enables the GUI **Restart MCP** button); local Python moved to a dev-only note; prerequisites now spell out per-path requirements (Docker vs systemd vs dev) with a `python3 --version` check; `deploy/systemd.md` documents Ubuntu/systemd + Python 3.12+ prerequisite |
| 2026-09-08 | Audit log rotation | `db.py` — `prune_audit()` + `audit_retention_days()` (env `MCP_AUDIT_RETENTION_DAYS`, default `90`, `0` = keep forever); expired events deleted on startup and throttled during inserts; `admin.py` Config page gains the setting; `.env.example` + `README.md` documented |
| 2026-09-08 | Quickstart doc + Hermes auth example | `docs/QUICKSTART.md` — new step-by-step first-run guide (login admin, create API key, connect agent, verify, troubleshooting); `README.md` links it, adds the `Authorization: "Bearer …"` header to the Hermes example, and lists it in More docs |
| 2026-09-07 | Admin GUI: reveal via session + static assets | `admin.py` — new/regenerated API keys are shown once via a signed session flash (no more `?key=` in the URL); CSS/JS split out to `static/style.css` + `static/app.js` served by Starlette StaticFiles; `Dockerfile` copies `static/` |
| 2026-09-07 | Default admin GUI password | `db.py` — `ensure_default_admin()` now falls back to `DEFAULT_ADMIN_PASSWORD = "digantiYA_30"` (instead of a random password) when `MCP_ADMIN_INIT_PASS` is unset; still `must_change_password=1` on first login; `.env.example` ships the default |
| 2026-09-07 | README: Docker + systemd quick start | `README.md` — quick start now Docker (Option A) + systemd (Option B) only; shared "prepare config files" step; local `python3` dev run moved to `.github/CONTRIBUTING.md` |
| 2026-09-07 | Auth required by default (fail-closed) | `server.py` — `SecurityMiddleware` now always requires a Bearer API key (no open access when no keys exist); `/health` stays exempt; startup logs a warning + 401 body gives a setup hint when no key is configured |
| 2026-09-07 | Docker: admin GUI service + consistency | `docker-compose.yml` adds `ruckus-admin` (port 8001) sharing `data/` + `inventory/` with the server; `Dockerfile` CMD is env-driven (drops dead `--transport/--port` flags); config editor/restart documented as systemd-only (Docker uses host `.env` + `docker compose restart`) |
| 2026-09-07 | Admin: editable config + restart | `admin.py` — Config page now edits `.env` (validated non-secret fields, write-only secrets) via read-modify-write with conflict detection + timestamped backup; superadmin-only "Restart MCP" button runs `systemctl restart` on `MCP_SYSTEMD_UNIT` |
| 2026-09-07 | Admin: tool-scope checkboxes | `admin.py` — key form "Allowed tools" is now a grouped checkbox list (vSZ/ICX/Inventory/Connectivity, 90 tools enumerated from `tools/*.py` via AST) with select-all/none, replacing the free-text textarea |
| 2026-09-07 | SQLite storage + admin web GUI | Keys + audit moved to SQLite (`data/admin.db`); new separate-process admin GUI (`admin.py`, port 8001) with users/roles, API key management, device inventory CRUD, audit viewer, and `/health` endpoint |
| 2026-09-07 | Per-client API keys + audit trail | `security.py` — per-client keys (`inventory/api_keys.yaml`) with `allowed_tools` allowlist + `allow_destructive` gate; JSON Lines audit trail (`logs/audit.jsonl`) of every tool call |
| 2026-09-04 | Time & NTP config | `ruckus_device_timezone_set`, `ruckus_device_clock_set`, `ruckus_device_ntp_server`, `ruckus_device_ntp_control` — configure device clock, timezone, and NTP with `confirm` + `dry_run` |
| 2026-09-04 | Config save | `ruckus_device_config_save` — persist running-config to startup (`write memory`) with `confirm` + `dry_run` |
| 2026-09-01 | IPv6 unicast routing + CLI errors | `ruckus_device_ipv6_unicast_routing` tool + detect rejected config commands (no more false `added: true`) |
| 2026-09-01 | Log noise reduction | Suppress per-request MCP/SSH/access INFO logs; `LOG_LEVEL=DEBUG` restores them |
| 2026-09-01 | Static IPv4 route | `ruckus_device_ip_route` + `_delete` — add/delete static IPv4 route (next-hop/null0/interface) with `confirm` + `dry_run` |
| 2026-09-01 | Static IPv6 route | `ruckus_device_ipv6_route` + `_delete` — add/delete static IPv6 route (next-hop/null0/interface) with `confirm` + `dry_run` |
| 2026-09-01 | Context-size optimization | All 30 list tools return `{items, total, returned, truncated, hint}` envelope + `MCP_MAX_ITEMS` hard cap + `summary=True` on 3 heaviest tools |
| 2026-08-22 | Doc/env sync | Tool count corrected to **80** (ICX 40) & tests to **231**; fix broken venv, `pytest-asyncio` dep, editable install, project URL |
| 2026-08-12 | PoE per-port status + params | `ruckus_device_poe_status` (read-only, per-port filter) + `ruckus_device_poe_port` added `priority`/`power_limit`/`power_by_class` |
| 2026-08-12 | PoE port control | `ruckus_device_poe_port` — enable/disable PoE without data link interruption |
| 2026-08-12 | Dry-run preview | All 4 ICX config tools support `dry_run=True` (preview without SSH) |
| 2026-08-12 | VLAN management | `vlan_create`, `vlan_delete`, `vlan_port` (single/range/multi) |
| 2026-08-11 | Port control | `ruckus_device_port_state` — enable/disable port |
| 2026-08-10 | Users + SSH | `ruckus_device_users`, `ruckus_device_ssh_status` |
| 2026-08-10 | Syslog fix | Parser edge case + 99.9% parse rate |
| 2026-08-06 | Resources + ARP + PoE + LLDP | `resources`, `arp_table`, `poe_status`, `lldp_neighbors` + rate limiting + per-device credentials |
| 2026-08-06 | Safety gates | 7 destructive tools require `confirm=True` |
| 2026-08-06 | 10 new tools | Traffic, alarms, domains, WLAN modify/toggle, reboot AP, disconnect client, controller stats |
| 2026-08-05 | Async refactor | vSZ adapter full async (2.7x–3.7x speedup), 148 tests |
| 2026-08-05 | Zone tree + 802.1X | `get_zones()` rewrite, `create_wlan` 802.1X, RADIUS |

Complete technical details below.

---

## 2026-09-07 — SQLite Storage + Admin Web GUI

### SQLite storage (refactor)
- **Files:** `db.py` (new), `security.py`, `server.py`
- **What:** per-client API keys and the audit trail moved out of YAML/JSONL into SQLite (`data/admin.db`, gitignored)
- **Schema:** `users` (role + scrypt-hashed password + `must_change_password`), `api_keys` (`name`, `key`, `allowed_tools` JSON, `allow_destructive`), `audit_log` (`ts`, `client`, `client_ip`, `tool`, `args`, `outcome`, `duration_ms`, `destructive`, `reason`)
- **Concurrency:** WAL mode + busy timeout — the MCP server and admin GUI are separate processes sharing the same DB
- **Live keys:** `KeyStore` resolves the Bearer token via a per-request DB lookup, so key edits apply immediately (no reload)
- **MCP `/health`:** public JSON endpoint (tool count, uptime, user/key/audit counts, DB size) for the admin GUI + external monitors

### Admin web GUI (new feature, separate process)
- **File:** `admin.py` (new) — Starlette app on `MCP_ADMIN_HOST:PORT` (default `127.0.0.1:8001`)
- **Design (option B):** runs independently of the MCP server; reports status via `/health` but does not start/stop it
- **Pages:** Dashboard, API Keys, Inventory, Audit, Config (read-only, secrets masked), Users, Change password
- **Auth:** HMAC-signed session cookie + per-form CSRF; roles `superadmin` > `operator` > `viewer`
- **Default admin:** created on first boot (`MCP_ADMIN_USER` / `MCP_ADMIN_INIT_PASS`, else random password printed once), forced password change on first login
- **Inventory CRUD:** atomic write to `inventory/devices.yaml` (read live by the MCP server, no restart)

### Config
- `.env.example`: added `MCP_DB_PATH`, `MCP_ADMIN_HOST`, `MCP_ADMIN_PORT`, `MCP_ADMIN_USER`, `MCP_ADMIN_INIT_PASS`
- `.gitignore` / `.dockerignore`: `data/` replaces `inventory/api_keys.yaml` + `logs/`
- `kilo.json`: deny read/edit of `data/admin.db` + `data/admin-secret.key`

### Tests
- **339 tests pass** (was 311): +`tests/test_db.py` (14), +`tests/test_admin.py` (12), `tests/test_audit.py`/`tests/test_security.py` rewritten for SQLite-backed `KeyStore`/`AuditLogger`
- `ruff check .` clean

---

## 2026-09-07 — Per-Client API Keys + Audit Trail

### Per-client API keys (enhancement)
- **Files:** `security.py` (new), `server.py`, `inventory/api_keys.example.yaml` (new)
- **What:** replace the single global `MCP_API_KEY` with a per-client key registry
- **Config:** `inventory/api_keys.yaml` (gitignored) — each key has `name`, `allowed_tools` (empty = all), `allow_destructive` (default false); keys support `${ENV_VAR}` substitution (same pattern as `devices.yaml`)
- **Enforcement:** `SecurityMiddleware` resolves the Bearer token to a `ClientIdentity`; `AuditMiddleware` (FastMCP `on_call_tool`) rejects calls outside the key's `allowed_tools` or destructive tools without `allow_destructive`
- **Fallback:** `MCP_API_KEY` still works — treated as an unrestricted `"default"` client (preserves existing deployments)
- **Tool count:** unchanged (90 tools); destructive count unchanged (22)

### Audit trail (enhancement)
- **Files:** `security.py` (`AuditLogger`, `AuditMiddleware`), `server.py`
- **What:** append-only JSON Lines audit log at `logs/audit.jsonl` (gitignored)
- **Recorded per tool call:** timestamp, client name, client IP, tool, redacted arguments, outcome (`ok`/`error`/`denied`/`exception`), duration_ms, destructive flag
- **Redaction:** sensitive argument keys (`pass`/`secret`/`token`/`key`) redacted; long strings truncated; the API key itself is never logged
- **Coverage:** all 90 tools, including unauthenticated clients (logged as `anonymous`)
- **`DESTRUCTIVE_TOOLS`:** canonical frozenset in `security.py`, kept in sync with `DOCS_SAFETY.md`

### Tests
- **311 tests pass** (was 291): +20 (`tests/test_audit.py` new — 13 tests; `tests/test_security.py` updated — 7 tests)
- `ruff check .` clean

---

## 2026-09-01 — Context-Size Optimization (Response Envelope + Hard Cap + Summary)

### Response envelope (enhancement)
- **Files:** `tools/_response.py` (new), `tools/icx_device.py`, `tools/vsz_aps.py`, `tools/vsz_system.py`, `tools/vsz_wlans.py`
- **Goal:** keep MCP payloads small for small-context models without silent truncation
- **New helper:** `list_result(items, limit=None, hint="")` returns `{"items", "total", "returned", "truncated", "hint"}`; `MCP_MAX_ITEMS` (default 50) hard-caps list length
- **Applied to all 30 list tools:** ICX (interfaces_summary/down/errors/stats, ip_addresses, ipv6_interfaces, mac_table_vlan, lldp_neighbors, arp_table, find_mac, lag_summary, traceroute, traceroute_ipv6, sfp_info, users) + vSZ (ap_status, ap_down, ap_high_client_count, zone_status, zone_ap_list, ssid_list, ssid_list_all, radius_list, domain_list) + inventory (list_devices, all_device_info, all_device_status, all_device_backup, devices_by_location, devices_by_role)
- **Error path normalized:** list tools now return `{"error": ...}` dict (not `[{...}]`) on device-not-found/login failure — consistent with AGENTS.md convention
- **Drill-down hints:** every envelope carries a `hint` field pointing to the detail tool
- **Bug fix:** `domain_list` now iterates `domains_list` (was iterating raw `domains`, which broke non-list API responses)

### Summary mode (enhancement)
- **Tools:** `ap_status(summary=True)`, `ruckus_device_arp_table(summary=True)`, `ruckus_device_mac_table_vlan(summary=True)`
- **Returns aggregates only:** ap_status → `{total_aps, up, down, by_zone}`; arp → `{total_entries, by_port, by_type}`; mac → `{total_entries, by_port}`
- **Docs:** TOOLS.md envelope note, SKILL.md truncated rule, README env table, AGENTS.md convention

### Tests
- **234 tests pass** (was 231): +3 summary tests (`TestApStatus.test_summary`, `TestArpTable.test_summary`, `TestMacTableVlan.test_summary`)
- `ruff check .` clean

---

## 2026-09-01 — Static IPv4 Route Add/Delete (ICX)

### New tools: `ruckus_device_ip_route` + `ruckus_device_ip_route_delete` (enhancement)
- **Files:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Add:** `ruckus_device_ip_route(host, dest, mask, next_hop, metric=None, distance=None, name=None, tag=None, confirm=False, dry_run=False)` → `ip route <dest> <mask> <next-hop>`
- **Delete:** `ruckus_device_ip_route_delete(host, dest, mask, next_hop, confirm=False, dry_run=False)` → `no ip route <dest> <mask> <next-hop>`
- **next-hop:** IPv4 address, `null0` (blackhole/drop), or outgoing interface (`ethernet <port>`, `lag <id>`, `ve <id>`)
- **Add optional params:** `metric` (1-16), `distance` (1-255), `name`, `tag` (0-4294967295)
- **Safety:** `confirm=True` gate + `dry_run=True` preview (same pattern as other ICX config tools)
- **Validation:** new validators `_validate_netmask`, `_validate_route_metric`, `_validate_route_distance`, `_validate_route_name`, `_validate_route_tag`, `_normalize_next_hop` — block command injection
- **Live-tested:** added `192.0.2.0/24 null0` then deleted it on a lab ICX access switch — routing table verified before/after
- **Tests:** +14 (TestIpRoute 5, TestIpRouteDelete 4, TestIpRouteValidation 5) — 234 → 248 pytest pass
- **Tool count:** 80 → 82 tools, ICX 40 → 42

---

## 2026-09-01 — Static IPv6 Route Add/Delete (ICX)

### New tools: `ruckus_device_ipv6_route` + `ruckus_device_ipv6_route_delete` (enhancement)
- **Files:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Add:** `ruckus_device_ipv6_route(host, dest, next_hop, metric=None, distance=None, confirm=False, dry_run=False)` → `ipv6 route <dest>/<prefix> <next-hop>`
- **Delete:** `ruckus_device_ipv6_route_delete(host, dest, next_hop, confirm=False, dry_run=False)` → `no ipv6 route <dest>/<prefix> <next-hop>`
- **dest:** IPv6 prefix (e.g. `2001:db8::/32`), validated by existing `_validate_route_dest_ipv6`
- **next-hop:** IPv6 address, `null0` (blackhole/drop), or outgoing interface (`ethernet <port>`, `lag <id>`, `ve <id>`, `tunnel <id>`)
- **Add optional params:** `metric` (1-16), `distance` (1-255)
- **Safety:** `confirm=True` gate + `dry_run=True` preview (same pattern as IPv4 route tools)
- **Validation:** new helper `_normalize_next_hop_ipv6` — block command injection; reuses `_validate_route_metric`/`_validate_route_distance`
- **Tests:** +13 (TestIpv6Route 6, TestIpv6RouteDelete 4, TestIpv6RouteValidation 3) — 248 → 261 pytest pass
- **Tool count:** 82 → 84 tools, ICX 42 → 44

---

## 2026-09-01 — IPv6 Unicast Routing + CLI Error Detection (ICX)

### New tool: `ruckus_device_ipv6_unicast_routing` (enhancement)
- **Files:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Enable/disable:** `ruckus_device_ipv6_unicast_routing(host, enable=True, confirm=False, dry_run=False)` → `ipv6 unicast-routing` / `no ipv6 unicast-routing`
- **Why:** `ipv6 route` is rejected on the device until `ipv6 unicast-routing` is enabled globally
- **Safety:** `confirm=True` gate + `dry_run=True` preview
- **Tests:** +4 (TestIpv6UnicastRouting) — 261 → 265 pytest pass

### Informative CLI errors (bug fix)
- **Files:** `adapters/device_ssh.py`
- **Problem:** config tools used `send_command_timing` without reading output, so a rejected command (e.g. `ipv6 unicast-routing must be enabled before configuring static route`) still returned `added: true` / `deleted: true`
- **Fix:** new `_send_config()` helper + `_extract_cli_error()`; IPv4/IPv6 route add/delete and unicast-routing now return `{"error": "<cli message>"}` when the switch rejects a command
- **Detection patterns:** `Unrecognized command`, `Invalid input`, `Incomplete command`, `must be enabled`, `not found`, `access denied`, `already exists`, etc.
- **Live-verified:** on a lab ICX access switch the IPv6 route add correctly reported the `ipv6 unicast-routing must be enabled...` error instead of a false success
- **Tests:** +3 (TestCliErrorDetection) — 265 → 268 pytest pass

### Tool count
- **Tool count:** 84 → 85 tools, ICX 44 → 45, destructive 16 → 17

---

## 2026-09-01 — Log Noise Reduction

### Quieter default logging (enhancement)
- **File:** `server.py`
- **Problem:** per-request INFO spam from `mcp.server.lowlevel.server` (`Processing request of type ...`), `paramiko.transport` (`Connected ...` / `Authentication ... successful!`), and uvicorn's HTTP access log
- **Fix:**
  - `mcp.server.lowlevel.server` and `paramiko.transport` loggers are set to `WARNING`
  - uvicorn access log disabled (`access_log=False`)
  - App logs (`tools.*`, `adapters.*`, `ruckus-mcp`) unchanged at `LOG_LEVEL`
- **Escape hatch:** set `LOG_LEVEL=DEBUG` to restore full framework/SSH/access logging

---

## 2026-08-22 — Documentation & Environment Sync

### Tool count correction (fix)
- **Issue**: Documentation inconsistency — docs claimed 81 tools but code registered 80; test counts also outdated (187 vs 231)
- **Root cause**: Historical inaccuracies in changelog not corrected, new features added without syncing all docs
- **Fix**: Updated all docs to match actual state:
  - **80 tools** (31 vSZ + 40 ICX + 6 inventory + 3 connectivity)
  - **231 tests** (12 test files)
- **Files updated**: AGENTS.md, README.md, docs/TOOLS.md, SKILL.md, SECURITY.md
- **Note**: CHANGES.md historical entries left unchanged (per project rule: no deletion)

### Environment fixes (fix)
- **Broken venv**: Interpreter path pointed to a non-existent venv path → recreated at the correct project venv path
- **Missing test dependency**: Added `pytest-asyncio>=0.24.0` to dev dependencies in `pyproject.toml`
- **Editable install**: Fixed hatchling configuration for namespace packages (`adapters`, `inventory`, `models`, `tools`)
- **Project metadata**: Updated `pyproject.toml` URLs from placeholder `your-org` to actual `apink/mcp-ruckus`
- **Verification**: All 231 tests pass, `ruff check .` passes

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
- **Parser:** Local user accounts — username, encrypt, privilege, status, expire time. Password hash is **not exposed** (security)
- **Live-tested:** 2 switches (development + access) — local user accounts verified
- **Tool count:** 73 → 74 tools

### SSH server status (new tool)

- **File:** `adapters/device_ssh.py`, `tools/icx_device.py`
- **Tool:** `ruckus_device_ssh_status(host)`
- **Command:** `show ip ssh` — `show ssh` is **invalid** on firmware 08.0.x (Lesson: use `show ip ssh`)
- **Parser:** SSH version + enabled + host key + per-session (direction, connection, version, encryption, username, HMAC, source IP)
- **Live-tested:** 2 switches — active sessions + hostkey RSA(2048) verified
- **Tool count:** 74 → 75 tools

### Cleanup

- **Dead code removed:** duplicate `get_poe_status` block (unreachable) inside `get_arp_table` from an interrupted debug session
- **Tests:** +5 (TestUsers, TestSshStatus) — 155 → 160 pytest pass
- **Docs:** README (75 tools, ICX 35), skills/ruckus.md (75 tools + SSH/login audit workflow + pitfalls `show ssh` invalid), DEVELOPMENT_GUIDELINES.md

---

## 2026-08-10 — Syslog Parser Fix

### Syslog parser edge case handling

- **File:** `adapters/device_ssh.py` (line 857)
- **Issue:** Regex `([^:]+):(.+)` fails on entries without a message (format: `timestamp:severity:facility`)
- **Failing examples:** `Aug 6 17:12:05:N:SSH Server session 1 received key-exchange`, `Aug 6 13:53:08:I:COPY COMPLETED`
- **Fix:** Regex → `([^:]+):?(.*)$` (optional colon, message may be empty)
- **Result:** Parsing 3422→3460/3461 entries (99.9%)
- **Also:** Filter the header line `(4000 lines):`
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
- **Tested:** Live on ICX7450-24-HPOE (12 neighbors — WLC, ICX switch, APs) + ICX7150-48-POEF (1 neighbor — upstream L3 switch)
- **Tool count:** 62 → 63 tools

### Rate Limiting (vSZ API + ICX SSH)

- **vSZ API (`adapters/vsz.py`):** `asyncio.Semaphore` — default 10 concurrent, config via `VSZ_RATE_LIMIT`
- **ICX SSH (`adapters/device_ssh.py`):** `threading.BoundedSemaphore` per-device — default 5 concurrent, config via `ICX_RATE_LIMIT`
- **ICX semaphore release:** monkey-patch `ConnectHandler.disconnect()` to auto-release after the `with conn:` block completes
- **Effect:** Prevents overloading the vSZ controller and ICX management plane when tools are called concurrently

### ICX Per-Device Credentials (devices.yaml)

- **File:** `models/ruckus.py`, `adapters/device_ssh.py`, `inventory/manager.py`
- **Mechanism:** `username` / `password` as literals directly in `devices.yaml`
- **Env var substitution:** `${VAR_NAME}` in the YAML value → resolved from `.env` at load time
- **Unknown env var:** `KeyError` immediately at `load_inventory()`, not an SSH failure
- **Import cleanup:** `DeviceCredentials` is no longer used in the SSH adapter
- **Inventory:** `inventory/manager.py` has a regex-based `_resolve_env_vars()` and a `_resolve_credentials()` post-processing step

### Example devices.yaml

```yaml
devices:
  - host: 192.0.2.50
    name: icx-core
    username: ${ICX_CORE_USER}    # env var reference
    password: ${ICX_CORE_PASS}

  - host: 198.51.100.51
    name: icx-dist-01
    username: admin-dist          # literal value
    password: CHANGE_ME           # literal value (prefer env vars)
```

### Doc Update

- `.env.example`: `VSZ_RATE_LIMIT`, ICX credential docs
- `README.md`: rate limit + devices.yaml credential examples
- `inventory/devices.example.yaml`: literal + `${ENV}` examples

---

## 2026-08-06 — Safety Gates + Radius Enhancement + Docs Refresh

### Safety Gates — 7 tools
All destructive tools now require a `confirm=True` gate:
- `reboot_ap`, `disconnect_client`, `toggle_wlan` — newly added
- `apply_rf_recommendation`, `apply_ap_config`, `create_wlan`, `modify_wlan` — already present

Without `confirm=True`, they return `{"error": "confirm_required"}` + no-op.

### `radius_list` — now shows IP & port
Previously only `has_primary: bool`. Now:
- `primary_ip`, `primary_port`
- `secondary_ip`, `secondary_port` (None if absent)
- `sharedSecret` remains not exposed (security)

### Docs refresh
- `README.md` — 62 tools, complete tool tables, updated architecture
- `CHANGES.md` — restructured, backlog moved to DEVELOPMENT_GUIDELINES
- `DEVELOPMENT_GUIDELINES.md` — async section done, file structure updated, backlog cleaned
- `SECURITY.md` — 131 tests, FastMCP 3.4.2
- `skills/ruckus.md` — 62 tools header, traffic/alarm/monitoring tool docs added
- `kilo.json` — AI permission rules block .env reads

### Radio config — lessons learned
AP config uses PUT (not PATCH), and the body must be cleaned: strip unwritable fields, remove all nulls, use integers for channel/width (not strings), and remove `autoChannelSelection` when using a manual channel. HTTP 204 = success. Verified: set channel/power, disable/enable radios, auto channel.

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

**Problem:** Domain-scoped users cannot access `/rkszones` (403).
Zones without APs are not detected via `/query/ap` extraction.

**Solution:**
- `GET /group/tree/apgroup` → 1 call, works for root + domain, always
  shows all zones including those without APs
- `get_zone_tree()` — calls the tree endpoint
- `_flatten_zone_tree()` — recursive walk looking for `type: "ZONE"` nodes,
  carrying `domainUUID`/`domainName` down
- Fallback: `/rkszones` (root) → `/query/ap` extraction
- Returned zone objects now have extra fields: `domainName`,
  `offlineCount`, `onlineCount`

### `create_wlan` — 802.1X support via `standard8021X` endpoint

| Type | Endpoint | Result |
|---|---|---|
| PSK / Open | `POST /rkszones/{zid}/wlans` | verified (7 types) |
| 802.1X | `POST /rkszones/{zid}/wlans/standard8021X` | verified |

802.1X payload: `authServiceOrProfile: {name}` + `encryption: {WPA2, AES, mfp:disabled}`,
without a passphrase. Requires `radius_profile` (the auth service name in the zone).

### `radius_list` — new tool

`GET /rkszones/{zid}/aaa/radius` — lists RADIUS servers in the zone to
reference `radius_profile` before creating an 802.1X WLAN.

Adapter: `get_radius_servers(zone_id, for_accounting=None)`

### `_request()` — PATCH/PUT support

Previously only GET/POST/DELETE. PATCH/PUT fell through to GET (bug).
Now: `httpx.request(method, url, ...)` for PUT/PATCH.

### Auth fallback: static token → credentials

`VSZ_API_TOKEN` in `.env` can expire or be revoked. If a request returns 401 while
using the token: `_token_failed = True`, log in again via `VSZ_USER`/`VSZ_PASS`,
and retry once. Active in `_request()` and `create_wlan()`.

---

## How to Add Change Documentation

Whenever there is a significant change (patch, bug fix, new feature),
add an entry to this file in the same format. Do not delete old
entries — this is a historical record for future developers (human
or AI).

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
