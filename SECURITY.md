# Security Policy

## Supported Versions

We will only provide security updates for the latest stable release.

## Reporting Security Issues

Please report security vulnerabilities via the project's GitHub Security Advisory page.

## Vulnerability Disclosure

We follow responsible disclosure practices. We ask that you:

1. **Do not disclose publicly** any vulnerabilities until we've had a chance to address them
2. **Provide clear, detailed information** about the vulnerability
3. **Allow reasonable time** for us to release a fix

## Security Features

### Input Validation
All user inputs are validated before processing:
- Port format: `\d+/\d+/\d+`
- MAC addresses: Dotted or colon format
- IPv4/IPv6: Format and range validation
- VLAN IDs: 1-4094 range

### Credential Management
- No controller/device credentials in source code
- vSZ: credentials from `.env`; ICX: from `inventory/devices.yaml` (supports `${ENV_VAR}` substitution)
- Admin GUI accounts and per-client API keys: stored in SQLite (`data/admin.db`) with scrypt-hashed passwords
- Admin GUI default superadmin is `admin` / `digantiYA_30` and is forced to change its password on first login (override with `MCP_ADMIN_INIT_PASS`)
- `.env`, `inventory/devices.yaml`, and `data/` are gitignored by default
- Implementation rules: [CONTRIBUTING.md §S4](.github/CONTRIBUTING.md)

### Rate Limiting
Semaphore-based concurrency control (vSZ API + ICX SSH) prevents controller/switch overload when multiple tools are called simultaneously. Defaults: `VSZ_RATE_LIMIT=10`, `ICX_RATE_LIMIT=5`. Implementation details: [CONTRIBUTING.md §R5](.github/CONTRIBUTING.md)

### Session Management
- vSZ session reuse with TTL (600 seconds)
- Automatic re-login when session expires
- No persistent authentication tokens stored

### Error Handling
- Explicit error responses (no silent failures)
- Structured logging with timestamps
- Health check endpoint for monitoring

### Per-Client API Keys
- Authentication is required by default (fail-closed): every request must carry a Bearer token; `/health` stays open for monitoring. With no keys configured, the endpoint rejects all tool calls with `401` and logs a startup warning.
- Each AI assistant (or team) gets its own key, stored in SQLite (`data/admin.db`, gitignored) and managed via the admin GUI (`python3 admin.py`)
- Per-key `allowed_tools` allowlist and `allow_destructive` gate (destructive tools blocked by default)
- `MCP_API_KEY` remains as a fallback single key (unrestricted `"default"` client)
- Keys take effect immediately — the MCP server resolves them live per request (no restart)
- New/regenerated keys are revealed once via a signed session flash, never in the URL query string
- Implementation: [CONTRIBUTING.md §S4](.github/CONTRIBUTING.md)

### Audit Trail
- Every tool call is recorded to the SQLite `audit_log` table (`data/admin.db`)
- Each record: timestamp, client name, client IP, tool, redacted arguments, outcome, duration, destructive flag
- Sensitive argument values (passwords, tokens, keys) are redacted; the API key itself is never logged
- Audit logging runs for all authenticated clients (per-key and `MCP_API_KEY` fallback)
- Audit events rotate automatically: `MCP_AUDIT_RETENTION_DAYS` (default `90`, `0` = keep forever) prunes older events on startup and periodically at runtime
- Browse and filter the audit trail in the admin GUI (`/audit`)

### Admin GUI Config & Restart
- The admin GUI's **Config** page can edit `.env` (superadmin only) and set/rotate secrets (write-only — secrets are never shown back).
- `.env` writes are validated, written atomically with a timestamped backup, and protected against concurrent manual edits (base-hash conflict detection).
- The **Restart MCP** button runs `systemctl restart <MCP_SYSTEMD_UNIT>` (superadmin only). Deployment should scope this with a polkit rule granting only the GUI's OS user permission to manage that single unit — see [deploy/systemd.md](deploy/systemd.md).
- All admin form submissions are CSRF-protected.

## Dependencies

We use the following key dependencies:
- FastMCP 3.4.2
- Python 3.12
- Netmiko 4.4.0+ (ICX SSH)
- httpx 0.28.0+ (vSZ REST API)

All dependencies are regularly updated and audited.

## Security Testing

- Automated testing with pytest (352 tests, 19 test files)
- Input validation coverage: 100%
- Error handling verification
- Session management testing
- Per-client API key + audit trail testing
- Admin GUI auth + role-gating testing
- Code quality scanning with ruff

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.