# Ruckus MCP Development Guidelines

Panduan pengembangan production-ready untuk mcp-ruckus.
Fokus: **Security, Reliability, Code Cleanliness**.

---

## PRIORITY 0 — SECURITY (Wajib sebelum production)

### S1. Input Sanitization — Cegah Command Injection

**Masalah**: Input user langsung dimasukkan ke SSH command tanpa validasi.
Switch Ruckus ICX memproses karakter `;` sebagai command separator.
Input berbahaya seperti `1/1/1; enable; configure terminal` bisa dieksekusi switch.

**Aturan**: VALIDATE SETIAP input yang masuk ke `send_command()` atau `send_command_timing()`.

```python
import re

# Pre-compiled validators (di top of file, bukan inline)
PORT_RE = re.compile(r'^\d+/\d+/\d+$')          # Format: 1/2/3
MAC_RE = re.compile(r'^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$')  # d4c1.9e32.2c48
IPV4_RE = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')  # 192.168.1.1
UUID_RE = re.compile(r'^[0-9a-fA-F-]{36}$')       # zone_id, wlan_id

def _validate_port(port: str) -> str:
    if not PORT_RE.match(port):
        raise ValueError(f"Invalid port format: {port}")
    return port

def _validate_mac(mac: str) -> str:
    if not MAC_RE.match(mac):
        raise ValueError(f"Invalid MAC format: {mac}")
    return mac

def _validate_ipv4(ip: str) -> str:
    if not IPV4_RE.match(ip):
        raise ValueError(f"Invalid IPv4 format: {ip}")
    return ip

def _validate_uuid(value: str) -> str:
    if not UUID_RE.match(value):
        raise ValueError(f"Invalid UUID format: {value}")
    return value
```

**Implementation di adapter SSH**:
```python
# ✅ CARA BENAR — validate sebelum send_command
output = conn.send_command(f"show vlan brief ethernet {_validate_port(port)}")

# ❌ DILARANG — langsung pakai input user
output = conn.send_command(f"show vlan brief ethernet {port}")
output = conn.send_command(f"show mac-address {mac}")
output = conn.send_command_timing(f"ping {ip} source {source}")
```

**Checklist setiap command yang pakai f-string**:
- [x] Port: `_validate_port()` — regex `^\d+/\d+/\d+$`
- [x] MAC: `_validate_mac()` — regex format dot
- [x] IPv4: `_validate_ipv4()` — 4 oktet
- [x] VLAN ID: `int()` cast + range check (1-4094)
- [x] Source IP: `_validate_ipv4()`

---

### S2. URL Injection Prevention — vSZ REST API

**Masalah**: `zone_id` dan `wlan_id` langsung ke URL tanpa validasi.
Bisa manipulasi path REST API.

```python
# ✅ CARA BENAR — validate UUID sebelum URL construction
def get_wlan_detail(self, zone_id: str, wlan_id: str) -> dict:
    _validate_uuid(zone_id)
    _validate_uuid(wlan_id)
    return self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")

# ❌ DILARANG
return self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")
```

---

### S3. Defense in Depth

Input ke MCP server berasal dari AI agent, BUKAN user langsung.
Tetap wajib validasi karena:
- Agent bisa di-trick via prompt injection
- Future use: web UI langsung ke MCP server
- Network exposure jika dibuka ke broader network

---

### S4. Credential Management

**Aturan ketat**:
- Tidak ada hardcoded credentials di code apapun
- Semua credential via `.env` (lihat section ENV di bawah)
- `.env` wajib di `.gitignore`
- Tidak pernah log password, token, atau service ticket
- Gunakan `.env.example` sebagai template

```python
# ✅ CARA BENAR
ticket = os.getenv("VSZ_API_TOKEN", "")
logger.debug(f"Auth method: {'token' if ticket else 'user/pass'}")
# TIDAK: logger.debug(f"Token: {ticket}")

# ❌ DILARANG
TOKEN = "abc123..."
password = "admin123"
```

---

## PRIORITY 1 — RELIABILITY (Wajib untuk stabilitas)

### R1. Error Handling — Jangan Silent Fail

**Masalah**: `vsz._request()` catch semua HTTPError lalu return `{}` (kosong).
User/agent kira tidak ada data, padahal sebenarnya error.

```python
# ✅ CARA BENAR — return error eksplisit
def _request(self, path, method="GET", payload=None):
    try:
        resp = httpx.post(url, ...)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(f"vSZ API {method} {path} failed: {exc.response.status_code}")
        return {"error": f"http_{exc.response.status_code}", "detail": str(exc)}
    except httpx.HTTPError as exc:
        logger.error(f"vSZ API {method} {path} network error: {exc}")
        return {"error": "network_error", "detail": str(exc)}

# ❌ DILARANG — silent return kosong
except httpx.HTTPError:
    return {}  # User tidak tahu kalau error
```

**Aturan**: Setiap tool function harus check `"error" in result` sebelum return.

```python
# ✅ Pattern wajib di setiap tool function
def some_tool(param):
    adapter = VsZRestAdapter()
    result = adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = adapter.get_data(param)
    if "error" in data:
        return data  # Propagate error ke caller
    return _parse_data(data)
```

---

### R2. SSH Connection Retry Logic

**Masalah**: Koneksi SSH ke ICX switch sering transient fail:
- `Error reading SSH protocol banner`
- `Invalid packet blocking`
- Timeout di high-traffic

Tanpa retry, tool return error untuk masalah sementara.

```python
import time

def _connect_with_retry(self, max_retries=2, backoff=1.5):
    """Connect SSH dengan retry dan exponential backoff."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return self._connect()
        except (NetmikoTimeoutException, SSHException) as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(f"SSH attempt {attempt+1} failed: {exc}, retrying...")
                time.sleep(backoff ** attempt)
    raise last_exc

# Usage di setiap method:
def get_device_info(self):
    try:
        with self._connect_with_retry() as conn:
            output = conn.send_command("show version", read_timeout=20)
        ...
```

---

### R3. Structured Logging

**Masalah**: Tidak ada logging satupun. Susah debug production, tidak ada audit trail.

**Standard**:
```python
import logging

logger = logging.getLogger(__name__)

# Level usage:
logger.debug("Connecting to vSZ at %s", self.config.host)
logger.info("Tool alert_events called: severity=%s, limit=%d", severity, limit)
logger.warning("SSH retry attempt %d for %s", attempt, self.host)
logger.error("vSZ API failed: %s %s — %s", method, path, exc)
```

**Wajib log di**:
- Tool entry point (INFO): parameter yang dipanggil
- Network errors (WARNING/ERROR): host, path, exception
- Login failures (ERROR): username masked
- Retry attempts (WARNING): attempt number, exception

**DILARANG log**: password, token, service ticket, MAC address user.

---

### R4. Connection Management

**vSZ**: Jangan login per tool call.
```python
# ✅ Session reuse dengan TTL
class VsZRestAdapter:
    _service_ticket: str | None = None
    _login_time: float = 0
    SESSION_TTL = 600  # 10 menit

    def _ensure_login(self):
        if self._service_ticket and (time.time() - self._login_time < self.SESSION_TTL):
            return
        result = self.login()
        if "error" in result:
            raise RuntimeError(result["error"])

# ❌ Login per tool call (current implementation)
def some_tool():
    adapter = VsZRestAdapter()
    adapter.login()  # New ticket setiap call
```

---

## PRIORITY 1 — CODE CLEANLINESS

### C1. Type Hints Wajib

```python
# ✅ CARA BENAR
def get_port_vlan(self, host: str, port: str) -> dict[str, Any]:
    ...

# ❌ Tanpa type hint
def get_port_vlan(self, host, port):
    ...
```

Semua function signature harus ada return type dan parameter types.

---

### C2. Naming Convention

| Tipe | Convention | Contoh |
|---|---|---|
| Function/method | snake_case | `get_device_info()` |
| Class | PascalCase | `VsZRestAdapter` |
| Constant | UPPER_SNAKE | `SESSION_TTL` |
| Private method | `_prefix` | `_validate_port()` |
| Import alias | `_prefix` | `import foo as _foo` |
| Tool name (MCP) | lowercase no prefix vSZ, `ruckus_` prefix ICX | `ap_status`, `ruckus_device_info` |

---

### C3. Regex Best Practice

```python
# ✅ CARA BENAR — raw string, pre-compiled
PORT_RE = re.compile(r'^\d+/\d+/\d+$')
match = PORT_RE.search(port)

# ❌ DILARANG — non-raw string
re.compile('^\\d+/\\d+/\\d+$')  # Error-prone
re.compile('^\d+/\d+/\d+$')     # SyntaxWarning
```

- Selalu gunakan `r''` (raw string) untuk regex
- Pre-compile pattern di module level (performance)
- Named groups untuk readability: `(?P<mac>...)`

---

### C4. No Duplicate Code — DRY

```python
# ✅ Helper function untuk pattern berulang
def _safe_request(self, path: str, method: str = "GET", **kwargs) -> dict:
    """Wrapper dengan error handling dan logging."""
    data = self._request(path, method=method, **kwargs)
    if "error" in data:
        logger.error("Request failed: %s %s", method, path)
    return data

# ❌ Error handling diulang di setiap tool
def tool_a():
    adapter = VsZRestAdapter()
    result = adapter.login()
    if "error" in result:
        return {"error": ...}
    # ... duplikat 38 kali
```

---

## LESSONS LEARNED — Dari Issue Historis

### L1. `.env` Parser — Inline Comment Bug
```python
# ✅ Strip komentar sebelum parsing
if "#" in _line:
    _line = _line[:_line.index("#")].strip()
```

### L2. API Version — Dynamic Path
```python
# ✅ api_path() method, bukan hardcode v10_0
def api_path(self):
    return f"/wsg/api/public/{self.api_version}"
```

### L3. Ruckus API Filter Format
```python
# ✅ extraFilters untuk SEVERITY/CATEGORY, bukan filters
body = {
    "filters": [],
    "extraFilters": [{"type": "SEVERITY", "value": "Critical", "operator": "eq"}],
}
```

### L4. Infinite Recursion — Import Shadowing
```python
# ✅ Alias import dengan prefix _
from tools.management import ap_status as _ap_status
@mcp.tool()
def ap_status():        # Tool name tetap
    return _ap_status() # Panggil via alias
```

---

## DOCKER / DEPLOYMENT

### Yang Di-Luar Docker (Volume Mount)
| File | Alasan |
|---|---|
| `.env` | Credential, beda per environment |
| `inventory/devices.yaml` | Device list khusus deployment |

### Yang Di-Dalam Docker (COPY)
- `server.py`, `adapters/`, `tools/`, `models/`, `inventory/manager.py`
- `requirements.txt`
- `.env.example`, `inventory/devices.example.yaml` (template)

### `.dockerignore`
```
venv/
.git/
__pycache__/
*.pyc
.env
inventory/devices.yaml
backups/
```

---

## CHECKLIST SEBELUM RELEASE

### Security
- [x] Semua input SSH command di-validasi (`_validate_port`, `_validate_mac`, dll)
- [x] `zone_id`, `wlan_id` di-validasi UUID sebelum URL construction
- [x] Tidak ada hardcoded credentials
- [x] Tidak ada password/token di log
- [x] `.env` di `.gitignore`
- [x] `backups/` di `.gitignore` (config backup berisi secret)

### Reliability
- [x] SSH adapter punya retry logic (2-3 attempts + backoff)
- [x] `vsz._request()` return error eksplisit, bukan `{}`
- [x] Setiap tool function check `"error" in result`
- [x] Structured logging di semua layer (adapter, tool, server)
- [x] Session reuse di vSZ adapter (TTL-based)

### Code Quality
- [ ] Semua function ada type hints
- [x] Regex pakai raw string `r''`
- [x] Tidak ada code duplikat (DRY)
- [x] Naming convention konsisten (snake_case, device_/ruckus_device_ namespace)

### Documentation
- [x] `CHANGES.md` update dengan issue tracking
- [x] `skills/ruckus.md` update untuk tool baru
- [x] `README.md` tool count sinkron (62 tools)
- [x] Tidak ada data real (MAC, IP, user ID) di dokumentasi

### Testing
- [x] 131 pytest tests pass (12 test files, mock adapters, zero real hardware)
- [x] Tool count verified: 62 tools registered
- [x] Integration tested vs production vSZ

---

**Last updated**: 2026-08-06
**Status**: Production-ready. All security checks passed. Full async. 62 tools.

## Backlog — Future Development

### High Priority
- **Device port enable/disable** — toggle ICX port admin up/down via SSH
- **Alarm lifecycle** — `alarm_ack`, `alarm_clear` (perlu admin user)
- **WLAN delete** — `delete_wlan` via API

### Medium Priority
- **Docker rebuild** — docker-compose verify after async refactor
- **AAA/RADIUS CRUD** — create/update/delete RADIUS server
- **Zone CRUD** — create/update/delete zone (admin user)
- **Rogue AP marking** — classify as Known/Malicious/Ignore

### Low Priority
- **Generic query tool** — flexible cross-domain query
- **DHCP/VLAN pool tools** — list/get pool data
- **Stats history** — time-series traffic stats

