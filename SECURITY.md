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
- All credentials loaded from environment variables
- `.env` files are gitignored by default

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

- Automated testing with pytest (131 tests, 12 test files)
- Input validation coverage: 100%
- Error handling verification
- Session management testing
- Code quality scanning with ruff

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.