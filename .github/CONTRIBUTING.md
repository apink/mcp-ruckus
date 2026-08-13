# Ruckus MCP Development Guidelines

Production-ready development guidelines for mcp-ruckus.
Focus: **Security, Reliability, Code Cleanliness**.

---

## PRIORITY 0 — SECURITY (Required before production)

### S1. Input Sanitization — Prevent Command Injection

**Issue**: User input directly passed to SSH commands without validation.
Ruckus ICX switches process `;` as command separator.
Dangerous input like `1/1/1; enable; configure terminal` can be executed on the switch.

**Rule**: VALIDATE EVERY input that goes into `send_command()` or `send_command_timing()`.

```python
import re

# Pre-compiled validators (at top of file, not inline)
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

**Implementation in SSH adapter**:
```python
# ✅ CORRECT WAY — validate before send_command
output = conn.send_command(f"show vlan brief ethernet {_validate_port(port)}")

# ❌ FORBIDDEN — directly use user input
output = conn.send_command(f"show vlan brief ethernet {port}")
output = conn.send_command(f"show mac-address {mac}")
output = conn.send_command_timing(f"ping {ip} source {source}")
```

**Checklist for every command using f-string**:
- [x] Port: `_validate_port()` — regex `^\d+/\d+/\d+$`
- [x] MAC: `_validate_mac()` — regex dot format
- [x] IPv4: `_validate_ipv4()` — 4 octets
- [x] VLAN ID: `int()` cast + range check (1-4094)
- [x] Source IP: `_validate_ipv4()`

---

### S2. URL Injection Prevention — vSZ REST API

**Issue**: `zone_id` and `wlan_id` directly to URL without validation.
Can manipulate REST API path.

```python
# ✅ CORRECT WAY — validate UUID before URL construction
def get_wlan_detail(self, zone_id: str, wlan_id: str) -> dict:
    _validate_uuid(zone_id)
    _validate_uuid(wlan_id)
    return self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")

# ❌ FORBIDDEN
return self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")
```

---

### S3. Defense in Depth

MCP server input comes from AI agent, NOT direct user.
Still required validation because:
- Agent can be tricked via prompt injection
- Future use: web UI directly to MCP server
- Network exposure if opened to broader network

---

### S4. Credential Management

**Strict rules**:
- No hardcoded credentials anywhere
- vSZ: credentials via `.env` (`VSZ_USER`, `VSZ_PASS`, `VSZ_API_TOKEN`)
- ICX: credentials via `inventory/devices.yaml` (field `username` / `password`)
- ICX credential supports env var substitution: `${VAR_NAME}` → resolve from `.env` during `load_inventory()`
- Unknown env var: `KeyError` → credential reset empty + log warning, device skip
- `.env` and `inventory/devices.yaml` must be in `.gitignore`
- Never log password, token, or service ticket
- Use `.env.example` and `inventory/devices.example.yaml` as templates

```python
# ✅ CORRECT WAY
ticket = os.getenv("VSZ_API_TOKEN", "")
logger.debug(f"Auth method: {'token' if ticket else 'user/pass'}")
# NOT: logger.debug(f"Token: {ticket}")

# ❌ FORBIDDEN
TOKEN = "abc123..."
password = "admin123"
```

---

## PRIORITY 1 — RELIABILITY (Required for stability)

### R1. Error Handling — No Silent Fail

**Issue**: `vsz._request()` catches all HTTPError then returns `{}` (empty).
User/agent thinks no data, but actually error.

```python
# ✅ CORRECT WAY — return explicit error
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

# ❌ FORBIDDEN — silent empty return
except httpx.HTTPError:
    return {}  # User doesn't know if error
```

**Rule**: Every tool function must check `"error" in result` before return.

```python
# ✅ Mandatory pattern in every tool function
def some_tool(param):
    adapter = VsZRestAdapter()
    result = adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    data = adapter.get_data(param)
    if "error" in data:
        return data  # Propagate error to caller
    return _parse_data(data)
```

---

### R2. SSH Connection Retry Logic

**Issue**: SSH connection to ICX switch often transiently fails:
- `Error reading SSH protocol banner`
- `Invalid packet blocking`
- Timeout during high-traffic

Without retry, tool returns error for temporary issues.

```python
import time

def _connect_with_retry(self, max_retries=2, backoff=1.5):
    """Connect SSH with retry and exponential backoff."""
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

# Usage in every method:
def get_device_info(self):
    try:
        with self._connect_with_retry() as conn:
            output = conn.send_command("show version", read_timeout=20)
        ...
```

---

### R3. Structured Logging

**Issue**: No logging at all. Hard to debug production, no audit trail.

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

**Required log at**:
- Tool entry point (INFO): parameters called
- Network errors (WARNING/ERROR): host, path, exception
- Login failures (ERROR): username masked
- Retry attempts (WARNING): attempt number, exception

**FORBIDDEN to log**: password, token, service ticket, user MAC address.

---

### R4. Connection Management

**vSZ**: Don't login per tool call.
```python
# ✅ Session reuse with TTL
class VsZRestAdapter:
    _service_ticket: str | None = None
    _login_time: float = 0
    SESSION_TTL = 600  # 10 minutes

    def _ensure_login(self):
        if self._service_ticket and (time.time() - self._login_time < self.SESSION_TTL):
            return
        result = self.login()
        if "error" in result:
            raise RuntimeError(result["error"])

# ❌ Login per tool call (current implementation)
def some_tool():
    adapter = VsZRestAdapter()
    adapter.login()  # New ticket every call
```

---

### R5. Rate Limiting — Concurrency Control

**vSZ API** — `asyncio.Semaphore` limits total concurrent requests to controller:

```python
# adapters/vsz.py
self._semaphore = asyncio.Semaphore(int(os.getenv("VSZ_RATE_LIMIT", "10")))

async def _request(self, ...):
    async with self._semaphore:
        # ... HTTP request
```

**ICX SSH** — `threading.BoundedSemaphore` per device limits concurrent SSH session:

```python
# adapters/device_ssh.py
_semaphores: dict[str, threading.BoundedSemaphore] = {}

@classmethod
def _get_semaphore(cls, host):
    if host not in cls._semaphores:
        limit = int(os.environ.get("ICX_RATE_LIMIT", "5"))
        cls._semaphores[host] = threading.BoundedSemaphore(limit)
    return cls._semaphores[host]

def _connect(self):
    sem = self._get_semaphore(self.host)
    sem.acquire()
    conn = ConnectHandler(...)
    # monkey-patch disconnect to auto-release semaphore
    _orig = conn.disconnect
    conn.disconnect = lambda: (_orig(), sem.release())
    return conn
```

**Env config:**
```env
VSZ_RATE_LIMIT=10   # vSZ API concurrent (default 10)
ICX_RATE_LIMIT=5    # ICX SSH per-device concurrent (default 5)
```

**Behavior:**
- Requests queue (async for vSZ, blocking for ICX) — no error
- vSZ: single semaphore total (bottleneck at controller)
- ICX: single semaphore per device (100 switches = 100 independent semaphores)

---

## PRIORITY 1 — CODE CLEANLINESS

### C1. Type Hints Required

```python
# ✅ CORRECT WAY
def get_port_vlan(self, host: str, port: str) -> dict[str, Any]:
    ...

# ❌ Without type hint
def get_port_vlan(self, host, port):
    ...
```

All function signatures must have return type and parameter types.

---

### C2. Naming Convention

| Type | Convention | Example |
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
# ✅ CORRECT WAY — raw string, pre-compiled
PORT_RE = re.compile(r'^\d+/\d+/\d+$')
match = PORT_RE.search(port)

# ❌ FORBIDDEN — non-raw string
re.compile('^\\d+/\\d+/\\d+$')  # Error-prone
re.compile('^\d+/\d+/\d+$')     # SyntaxWarning
```

- Always use `r''` (raw string) for regex
- Pre-compile pattern at module level (performance)
- Named groups for readability: `(?P<mac>...)`

---

### C4. No Duplicate Code — DRY

```python
# ✅ Helper function for repeating pattern
def _safe_request(self, path: str, method: str = "GET", **kwargs) -> dict:
    """Wrapper with error handling and logging."""
    data = self._request(path, method=method, **kwargs)
    if "error" in data:
        logger.error("Request failed: %s %s", method, path)
    return data

# ❌ Error handling repeated in every tool
def tool_a():
    adapter = VsZRestAdapter()
    result = adapter.login()
    if "error" in result:
        return {"error": ...}
    # ... duplicate 38 times
```

---

## LESSONS LEARNED — From Historical Issues

### L1. `.env` Parser — Inline Comment Bug
```python
# ✅ Strip comment before parsing
if "#" in _line:
    _line = _line[:_line.index("#")].strip()
```

### L2. API Version — Dynamic Path
```python
# ✅ api_path() method, not hardcode v10_0
def api_path(self):
    return f"/wsg/api/public/{self.api_version}"
```

### L3. Ruckus API Filter Format
```python
# ✅ extraFilters for SEVERITY/CATEGORY, not filters
body = {
    "filters": [],
    "extraFilters": [{"type": "SEVERITY", "value": "Critical", "operator": "eq"}],
}
```

### L4. Infinite Recursion — Import Shadowing
```python
# ✅ Alias import with prefix _
from tools.management import ap_status as _ap_status
@mcp.tool()
def ap_status():        # Tool name remains
    return _ap_status() # Call via alias
```

### L5. ICX Syslog — Message Part Optional
ICX syslog entries don't always have `:message` after facility. Example:
```
Aug 6 13:53:08:I:COPY COMPLETED                # without :message
Aug 7 19:36:29:I:Security: SSH login by admin  # standard
```
Regex `([^:]+):(.+)` fails on entries without message. Use optional colon + message can be empty:
```python
# ✅ CORRECT WAY — optional colon, message can be empty
m = re.match(r"(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}):(\w):([^:]+):?(.*)$", line)
msg = m.group(4).strip() if m.group(4) else ""
```

---

## DOCKER / DEPLOYMENT

### Outside Docker (Volume Mount)
| File | Reason |
|---|---|
| `.env` | Credentials, different per environment |
| `inventory/devices.yaml` | Deployment-specific device list |

### Inside Docker (COPY)
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

## CHECKLIST BEFORE RELEASE

### Security
- [x] All SSH command inputs validated (`_validate_port`, `_validate_mac`, etc.)
- [x] `zone_id`, `wlan_id` UUID-validated before URL construction
- [x] No hardcoded credentials
- [x] No password/token in logs
- [x] `.env` in `.gitignore`
- [x] `backups/` in `.gitignore` (config backup contains secrets)

### Reliability
- [x] SSH adapter has retry logic (2-3 attempts + backoff)
- [x] `vsz._request()` returns explicit error, not `{}`
- [x] Every tool function checks `"error" in result`
- [x] Structured logging in all layers (adapter, tool, server)
- [x] Session reuse in vSZ adapter (TTL-based)

### Code Quality
- [ ] All functions have type hints
- [x] Regex uses raw string `r''`
- [x] No duplicate code (DRY)
- [x] Consistent naming convention (snake_case, device_/ruckus_device_ namespace)

### Documentation
- [x] `CHANGES.md` updated with issue tracking
- [x] `SKILL.md` updated for new tools
- [x] `README.md` tool count synced (81 tools)
- [x] 187 pytest tests pass (12 test files, mock adapters, zero real hardware)
- [x] Tool count verified: 81 tools registered
- [x] Integration tested vs production vSZ
- [x] LLDP + PoE tested live: ICX7450-24-HPOE + ICX7150-48-POEF

---

**Last updated**: 2026-08-13
**Status**: Production-ready. All security checks passed. Full async. 81 tools. Rate limiting enabled (vSZ + ICX).

## Backlog — Future Development

### Recently Completed
- **PoE port control** — `ruckus_device_poe_port(host, port, enable, priority, power_limit, power_by_class)`, toggle inline power without link interruption
- **PoE per-port status** — `ruckus_device_poe_status(host, port)` — filterable PoE budget + per-port detail
- **VLAN management** — `ruckus_device_vlan_create`/`delete`/`port` with VLAN spec parser, tagged/untagged ports, STP
- **Port enable/disable** — `ruckus_device_port_state(host, port, enable)`, SSH config mode, confirm gate
- **Dry-run preview** — All 4 ICX config tools support `dry_run=True`
- **Rate limiting (vSZ + ICX)** — semaphore-based concurrency control (VSZ_RATE_LIMIT, ICX_RATE_LIMIT)
- **ICX per-device credentials** — username/password in devices.yaml with `${ENV_VAR}` substitution

### High Priority
- **WLAN delete** — `delete_wlan` via API
- **Alarm lifecycle** — `alarm_ack`, `alarm_clear` (requires admin user)

### Medium Priority
- **Docker rebuild** — docker-compose verify after async refactor
- **AAA/RADIUS CRUD** — create/update/delete RADIUS server
- **Zone CRUD** — create/update/delete zone (admin user)
- **Rogue AP marking** — classify as Known/Malicious/Ignore

### Low Priority
- **Generic query tool** — flexible cross-domain query
- **DHCP/VLAN pool tools** — list/get pool data
- **Stats history** — time-series traffic stats