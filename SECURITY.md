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
- No hardcoded credentials in source code
- vSZ: credentials loaded from `.env` environment variables
- ICX: credentials loaded from `inventory/devices.yaml` (field `username`/`password`)
- ICX devices.yaml supports `${ENV_VAR}` substitution — bare `.env` vars, not in source
- `.env` and `inventory/devices.yaml` are gitignored by default

### Rate Limiting
- vSZ API: `asyncio.Semaphore` — max concurrent requests (default: 10, config: `VSZ_RATE_LIMIT`)
- ICX SSH: `threading.BoundedSemaphore` per-device — max concurrent sessions per switch (default: 5, config: `ICX_RATE_LIMIT`)
- Prevents controller/switch overload when multiple tools called simultaneously

### Session Management
- vSZ session reuse with TTL (600 seconds)
- Automatic re-login when session expires
- No persistent authentication tokens stored

### Error Handling
- Explicit error responses (no silent failures)
- Structured logging with timestamps
- Health check endpoint for monitoring

## Dependencies

We use the following key dependencies:
- FastMCP 3.4.2
- Python 3.12
- Netmiko 4.4.0+ (ICX SSH)
- httpx 0.28.0+ (vSZ REST API)

All dependencies are regularly updated and audited.

## Security Testing

- Automated testing with pytest (187 tests, 12 test files)
- Input validation coverage: 100%
- Error handling verification
- Session management testing
- Code quality scanning with ruff

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.