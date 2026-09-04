from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from paramiko.ssh_exception import SSHException

from models.ruckus import ICXDevice

logger = logging.getLogger(__name__)

# ── Input Validators (security: prevent command injection) ──────────

PORT_RE = re.compile(r"^\d+/\d+/\d+$")
MAC_DOT_RE = re.compile(r"^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$")
MAC_COLON_RE = re.compile(
    r"^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}$"
)
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")
ROUTE_DEST_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")
ROUTE_DEST_IPV6_RE = re.compile(r"^[0-9a-fA-F:]+(/\d{1,3})?$")
TIMEZONE_RE = re.compile(r"^gmt([+-])(\d{1,2})(:([0-5]\d))?$")
CLOCK_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
CLOCK_DATE_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})$")

# Route type codes → name (ICX show ip route)
ROUTE_TYPE_MAP: dict[str, str] = {
    "B": "BGP", "D": "Connected", "O": "OSPF", "R": "RIP", "S": "Static",
}
# Route type codes → name (ICX show ipv6 route)
ROUTE_TYPE_MAP_V6: dict[str, str] = {
    "B": "BGP", "C": "Connected", "L": "Local", "O": "OSPF", "R": "RIP", "S": "Static",
}


def _validate_port(port: str) -> str:
    """Validate switch port format (e.g., 1/2/3)."""
    if not PORT_RE.match(port):
        raise ValueError(f"Invalid port format (expected x/y/z): {port!r}")
    return port


def _validate_mac(mac: str) -> str:
    """Validate MAC address format (dotted or colon)."""
    if not (MAC_DOT_RE.match(mac) or MAC_COLON_RE.match(mac)):
        raise ValueError(f"Invalid MAC format: {mac!r}")
    return mac


def _validate_ipv4(ip: str) -> str:
    """Validate IPv4 address format."""
    if not IPV4_RE.match(ip):
        raise ValueError(f"Invalid IPv4 format: {ip!r}")
    parts = ip.split(".")
    if any(not (0 <= int(p) <= 255) for p in parts):
        raise ValueError(f"Invalid IPv4 octet range: {ip!r}")
    return ip


def _validate_ipv6(ip: str) -> str:
    """Sanitize IPv6 address (allow hex and colons only)."""
    if not IPV6_RE.match(ip):
        raise ValueError(f"Invalid IPv6 format: {ip!r}")
    return ip


def _validate_timezone(timezone: str) -> str:
    """Validate ICX clock timezone (e.g. gmt+07 or gmt+05:30)."""
    tz = timezone.strip().lower()
    m = TIMEZONE_RE.match(tz)
    if not m:
        raise ValueError(f"Invalid timezone (expected gmt±HH[:MM]): {timezone!r}")
    if int(m.group(2)) > 14:
        raise ValueError(f"Invalid timezone hour offset (0-14): {timezone!r}")
    return tz


def _validate_clock_time(clock_time: str) -> str:
    """Validate clock time in HH:MM:SS format."""
    value = clock_time.strip()
    m = CLOCK_TIME_RE.match(value)
    if not m:
        raise ValueError(f"Invalid clock time (expected HH:MM:SS): {clock_time!r}")
    hh, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if hh > 23 or mm > 59 or ss > 59:
        raise ValueError(f"Invalid clock time range: {clock_time!r}")
    return value


def _validate_clock_date(date: str) -> str:
    """Validate clock date in 'MM-DD-YYYY' format (FastIron clock set)."""
    value = date.strip()
    m = CLOCK_DATE_RE.match(value)
    if not m:
        raise ValueError(f"Invalid clock date (expected 'MM-DD-YYYY'): {date!r}")
    month, day = int(m.group(1)), int(m.group(2))
    year = m.group(3)
    if not (1 <= month <= 12):
        raise ValueError(f"Invalid clock date month (1-12): {date!r}")
    if not (1 <= day <= 31):
        raise ValueError(f"Invalid clock date day (1-31): {date!r}")
    if len(year) == 2:
        year = f"20{year}"
    return f"{month:02d}-{day:02d}-{year}"


def _validate_vlan_id(vlan_id: int) -> int:
    """Validate VLAN ID range (1-4094)."""
    if not isinstance(vlan_id, int) or not (1 <= vlan_id <= 4094):
        raise ValueError(f"Invalid VLAN ID (1-4094): {vlan_id!r}")
    return vlan_id


def _validate_route_dest(dest: str) -> str:
    """Validate route destination (IPv4 or CIDR). Blocks hostname."""
    if not ROUTE_DEST_RE.match(dest):
        raise ValueError(f"Invalid route destination (expected IP or CIDR): {dest!r}")
    ip_part = dest.split("/")[0]
    parts = ip_part.split(".")
    if any(not (0 <= int(p) <= 255) for p in parts):
        raise ValueError(f"Invalid IPv4 octet range: {dest!r}")
    if "/" in dest:
        prefix = int(dest.split("/")[1])
        if not (0 <= prefix <= 32):
            raise ValueError(f"Invalid prefix length (0-32): {dest!r}")
    return dest


def _validate_route_dest_ipv6(dest: str) -> str:
    """Validate IPv6 route destination (address or prefix). Blocks hostname/IPv4."""
    if not ROUTE_DEST_IPV6_RE.match(dest):
        raise ValueError(f"Invalid IPv6 route destination (expected IPv6 or prefix): {dest!r}")
    if "/" in dest:
        prefix = int(dest.split("/")[1])
        if not (0 <= prefix <= 128):
            raise ValueError(f"Invalid prefix length (0-128): {dest!r}")
    return dest


def _validate_netmask(mask: str) -> str:
    """Validate dotted-quad IPv4 netmask (e.g., 255.255.255.0)."""
    if not IPV4_RE.match(mask):
        raise ValueError(f"Invalid netmask format: {mask!r}")
    if any(not (0 <= int(p) <= 255) for p in mask.split(".")):
        raise ValueError(f"Invalid netmask octet range: {mask!r}")
    return mask


def _validate_route_metric(metric: int) -> int:
    """Validate static route metric (cost, 1-16)."""
    if not isinstance(metric, int) or not (1 <= metric <= 16):
        raise ValueError(f"Invalid route metric (1-16): {metric!r}")
    return metric


def _validate_route_distance(distance: int) -> int:
    """Validate static route administrative distance (1-255)."""
    if not isinstance(distance, int) or not (1 <= distance <= 255):
        raise ValueError(f"Invalid route distance (1-255): {distance!r}")
    return distance


def _validate_route_name(name: str) -> str:
    """Validate static route name (alphanumeric, 1-32 chars)."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,32}", name):
        raise ValueError(f"Invalid route name (1-32 alphanumeric/_/./-): {name!r}")
    return name


def _validate_route_tag(tag: int) -> int:
    """Validate static route tag (0-4294967295)."""
    if not isinstance(tag, int) or not (0 <= tag <= 4294967295):
        raise ValueError(f"Invalid route tag (0-4294967295): {tag!r}")
    return tag


def _normalize_next_hop(next_hop: str) -> str:
    """Normalize a static route next-hop token (IP, null0, or interface)."""
    nh = (next_hop or "").strip()
    if not nh:
        raise ValueError("Empty next hop")
    if nh == "null0":
        return nh
    if nh.startswith("ethernet "):
        return f"ethernet {_validate_port(nh.split(None, 1)[1])}"
    if nh.startswith("lag "):
        raw = nh.split(None, 1)[1]
        if not raw.isdigit() or not (1 <= int(raw) <= 255):
            raise ValueError(f"Invalid LAG id (1-255): {next_hop!r}")
        return f"lag {raw}"
    if nh.startswith("ve "):
        raw = nh.split(None, 1)[1]
        if not raw.isdigit() or not (1 <= int(raw) <= 4096):
            raise ValueError(f"Invalid VE id (1-4096): {next_hop!r}")
        return f"ve {raw}"
    return _validate_ipv4(nh)


def _normalize_next_hop_ipv6(next_hop: str) -> str:
    """Normalize an IPv6 static route next-hop (IPv6, null0, or interface)."""
    nh = (next_hop or "").strip()
    if not nh:
        raise ValueError("Empty next hop")
    if nh == "null0":
        return nh
    if nh.startswith("ethernet "):
        return f"ethernet {_validate_port(nh.split(None, 1)[1])}"
    if nh.startswith("lag "):
        raw = nh.split(None, 1)[1]
        if not raw.isdigit() or not (1 <= int(raw) <= 255):
            raise ValueError(f"Invalid LAG id (1-255): {next_hop!r}")
        return f"lag {raw}"
    if nh.startswith("ve "):
        raw = nh.split(None, 1)[1]
        if not raw.isdigit() or not (1 <= int(raw) <= 4096):
            raise ValueError(f"Invalid VE id (1-4096): {next_hop!r}")
        return f"ve {raw}"
    if nh.startswith("tunnel "):
        raw = nh.split(None, 1)[1]
        if not raw.isdigit() or not (1 <= int(raw) <= 65535):
            raise ValueError(f"Invalid tunnel id (1-65535): {next_hop!r}")
        return f"tunnel {raw}"
    return _validate_ipv6(nh)


# ICX CLI error fragments — used to detect rejected config commands so a
# silently-ignored "added: true" is never returned.
CLI_ERROR_RE = re.compile(
    r"(unrecognized command|invalid input|incomplete command|ambiguous command|"
    r"must be enabled|error:|not found|access denied|permission denied|"
    r"invalid .* (range|value|id)|in use|already exists)",
    re.IGNORECASE,
)


def _extract_cli_error(text: str) -> str | None:
    """Return the first CLI error line from command output, else None."""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped and CLI_ERROR_RE.search(stripped):
            return stripped
    return None


def _parse_vlan_spec(vlan_spec: str) -> list[int]:
    """Parse VLAN spec to list of VLAN IDs.

    Supports: single ('200'), range ('210 to 213'),
    multi ('200 210 220'), mixed ('16 17 20 to 24').
    """
    tokens = vlan_spec.strip().split()
    if not tokens:
        raise ValueError(f"Empty VLAN spec: {vlan_spec!r}")
    vlan_ids: list[int] = []
    i = 0
    while i < len(tokens):
        part = tokens[i]
        if part == "to" and vlan_ids and i + 1 < len(tokens):
            start = vlan_ids.pop()
            end = int(tokens[i + 1])
            if start >= end:
                raise ValueError(f"Invalid VLAN range: {start} to {end}")
            if not (1 <= start <= 4094) or not (1 <= end <= 4094):
                raise ValueError(f"VLAN range out of bounds (1-4094): {start} to {end}")
            vlan_ids.extend(range(start, end + 1))
            i += 1
        else:
            try:
                vlan_id = int(part)
                if not (1 <= vlan_id <= 4094):
                    raise ValueError(f"VLAN out of bounds (1-4094): {vlan_id}")
                vlan_ids.append(vlan_id)
            except ValueError:
                raise ValueError(f"Invalid VLAN spec token: {part!r}")
        i += 1
    if not vlan_ids:
        raise ValueError(f"Empty VLAN spec: {vlan_spec!r}")
    return vlan_ids


def _validate_ports_spec(ports_spec: str) -> str:
    """Validate port list specification for ICX commands.

    Checks that every non-keyword token matches port format (x/y/z).
    Keywords: 'to', 'ethernet'.
    """
    if not ports_spec.strip():
        return ""
    for token in ports_spec.strip().split():
        if token.lower() in ("to", "ethernet"):
            continue
        _validate_port(token)
    return ports_spec


class RuckusDeviceDriver:
    CAPABILITIES = ["ssh"]
    _semaphores: dict[str, threading.BoundedSemaphore] = {}
    _default_ssh_limit = 5

    @classmethod
    def _get_semaphore(cls, host: str) -> threading.BoundedSemaphore:
        if host not in cls._semaphores:
            limit = int(os.environ.get("ICX_RATE_LIMIT", cls._default_ssh_limit))
            cls._semaphores[host] = threading.BoundedSemaphore(limit)
        return cls._semaphores[host]

    def __init__(self, device: ICXDevice) -> None:
        self.device = device
        self.host = device.host
        self.name = device.name
        self.username = device.username
        self.password = device.password

    def _connect(self) -> ConnectHandler:
        if not self.username or not self.password:
            raise ValueError(
                "missing ICX credentials — set username/password in devices.yaml"
            )

        sem = self._get_semaphore(self.host)
        acquired = sem.acquire(blocking=False)
        if not acquired:
            raise RuntimeError(
                f"ICX_RATE_LIMIT reached for {self.host} — "
                f"all {sem._initial_value} SSH slots in use, retry later"
            )

        last_exc = None
        max_retries = 2
        backoff = 1.5

        try:
            for attempt in range(max_retries + 1):
                try:
                    conn = ConnectHandler(
                        device_type="ruckus_fastiron",
                        host=self.host,
                        username=self.username,
                        password=self.password,
                        timeout=15,
                        global_delay_factor=2,
                        session_log='session.log',
                    )
                    _orig_disconnect = conn.disconnect

                    def _wrapped_disconnect():
                        _orig_disconnect()
                        sem.release()

                    conn.disconnect = _wrapped_disconnect
                    return conn
                except (NetmikoTimeoutException, SSHException) as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        logger.warning(
                            "SSH attempt %d/%d failed for %s: %s, retrying...",
                            attempt + 1, max_retries + 1, self.host, exc,
                        )
                        time.sleep(backoff ** attempt)
                    else:
                        raise
            raise last_exc
        except Exception:
            sem.release()
            raise

    def _send_config(self, commands: list[str]) -> str:
        """Send config-mode commands over one session; return combined output."""
        outputs: list[str] = []
        with self._connect() as conn:
            for cmd in commands:
                outputs.append(
                    conn.send_command_timing(cmd, delay_factor=2, read_timeout=10)
                )
        return "\n".join(outputs)

    @staticmethod
    def _normalize(value: str | None) -> str | None:
        if value is None or value in ("None", "N/A", "", "-"):
            return None
        return value

    def get_device_info(self) -> dict[str, Any]:
        """Get basic device info — model, serial, version, uptime."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show version", read_timeout=20)
            return {
                "host": self.host,
                "name": self.name,
                "vendor": "ruckus",
                "os": "icx",
                "version": self._search(r"SW:\s+Version\s+(\S+)", output),
                "model": self._search(r"HW:\s+(?:Stackable\s+)?(\S+)", output),
                "uptime": self._search(r"system uptime is\s+(.+?)$", output, re.MULTILINE),
                "serial": self._search(r"Serial\s*#:?\s*(\S+)", output),
                "license": self._search(r"Current License:\s*(\S+)", output),
                "role": self.device.role,
                "location": self.device.location,
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except NetmikoAuthenticationException:
            return {"host": self.host, "error": "authentication_failed"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_interfaces_summary(self) -> list[dict[str, Any]]:
        """Get interface summary — name, status, VLAN, type for all ports."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show interface brief wide", read_timeout=20)
            interfaces: list[dict[str, Any]] = []
            for line in output.splitlines():
                parts = line.strip().split()
                if len(parts) < 9:
                    continue
                port = parts[0]
                if not re.match(r"^\d+/\d+/\d+$|^mgmt\d+$|^ve\d+$|^lg\d+$", port):
                    continue
                link = parts[1]
                status = "down" if link.lower() in ("down", "disable") else link.lower()
                name = " ".join(parts[10:]).strip() if len(parts) > 10 else ""
                interfaces.append({
                    "port": port,
                    "link": status,
                    "state": self._normalize(parts[2]),
                    "duplex": self._normalize(parts[3]),
                    "speed": self._normalize(parts[4]),
                    "trunk": self._normalize(parts[5]),
                    "tag": self._normalize(parts[6]),
                    "pvid": parts[7],
                    "priority": parts[8] if parts[8].isdigit() else self._normalize(parts[8]),
                    "mac": parts[9] if len(parts) > 9 else "",
                    "description": name,
                })
            return interfaces
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_interfaces_down(self) -> list[dict[str, Any]]:
        """List interfaces that are administratively or operationally down."""
        return [i for i in self.get_interfaces_summary()
                if isinstance(i, dict) and i.get("link") == "down" and "error" not in i]

    def get_interfaces_errors(self) -> list[dict[str, Any]]:
        """List interfaces with input/output error counters."""
        ports = [i["name"] for i in self.get_interfaces_summary()
                 if isinstance(i, dict) and "error" not in i and PORT_RE.match(i["name"])]
        results: list[dict[str, Any]] = []
        if not ports:
            return results
        try:
            with self._connect() as conn:
                for port in ports:
                    output = conn.send_command(
                        f"show interfaces ethernet {_validate_port(port)}", read_timeout=20)
                    ie = int(m.group(1)) if (m := re.search(r"(\d+)\s+input errors", output)) else 0
                    oe = int(m.group(1)) if (m := re.search(r"(\d+)\s+output errors", output)) else 0
                    crc = int(m.group(1)) if (m := re.search(r"(\d+)\s+CRC", output)) else 0
                    if ie > 0 or oe > 0 or crc > 0:
                        results.append({
                            "host": self.host, "name": port,
                            "input_errors": ie, "output_errors": oe, "crc": crc,
                        })
            return results
        except (NetmikoTimeoutException, Exception) as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_interfaces_stats(self) -> list[dict[str, Any]]:
        """Get per-interface traffic stats — rx/tx bytes and rates."""
        ports = [i["name"] for i in self.get_interfaces_summary()
                 if isinstance(i, dict) and "error" not in i and PORT_RE.match(i["name"])]
        results: list[dict[str, Any]] = []
        if not ports:
            return results
        try:
            with self._connect() as conn:
                for port in ports:
                    output = conn.send_command(
                        f"show interfaces ethernet {_validate_port(port)}", read_timeout=20)
                    ie = int(m.group(1)) if (m := re.search(r"(\d+)\s+input errors", output)) else 0
                    oe = int(m.group(1)) if (m := re.search(r"(\d+)\s+output errors", output)) else 0
                    crc = int(m.group(1)) if (m := re.search(r"(\d+)\s+CRC", output)) else 0

                    rate_in = re.search(
                        r"(\d+) second input rate:\s*(\d+)\s+bits/sec,\s*(\d+)"
                        r"\s+packets/sec,\s*([\d.]+)%\s+utilization",
                        output,
                    )
                    rate_out = re.search(
                        r"(\d+) second output rate:\s*(\d+)\s+bits/sec,\s*(\d+)"
                        r"\s+packets/sec,\s*([\d.]+)%\s+utilization",
                        output,
                    )
                    pkts_in = re.search(r"(\d+)\s+packets input,\s*(\d+)\s+bytes", output)
                    pkts_out = re.search(r"(\d+)\s+packets output,\s*(\d+)\s+bytes", output)
                    bcast_in = re.search(r"Received\s+(\d+)\s+broadcasts,\s*(\d+)\s+multicasts", output)
                    bcast_out = re.search(r"Transmitted\s+(\d+)\s+broadcasts,\s*(\d+)\s+multicasts", output)

                    results.append({
                        "host": self.host, "name": port,
                        "input_errors": ie, "output_errors": oe, "crc": crc,
                        "input_rate_bps": int(rate_in.group(2)) if rate_in else 0,
                        "input_rate_pps": int(rate_in.group(3)) if rate_in else 0,
                        "input_util_pct": float(rate_in.group(4)) if rate_in else 0.0,
                        "output_rate_bps": int(rate_out.group(2)) if rate_out else 0,
                        "output_rate_pps": int(rate_out.group(3)) if rate_out else 0,
                        "output_util_pct": float(rate_out.group(4)) if rate_out else 0.0,
                        "packets_in": int(pkts_in.group(1)) if pkts_in else 0,
                        "bytes_in": int(pkts_in.group(2)) if pkts_in else 0,
                        "packets_out": int(pkts_out.group(1)) if pkts_out else 0,
                        "bytes_out": int(pkts_out.group(2)) if pkts_out else 0,
                        "broadcasts_in": int(bcast_in.group(1)) if bcast_in else 0,
                        "multicasts_in": int(bcast_in.group(2)) if bcast_in else 0,
                        "broadcasts_out": int(bcast_out.group(1)) if bcast_out else 0,
                        "multicasts_out": int(bcast_out.group(2)) if bcast_out else 0,
                    })
            return results
        except (NetmikoTimeoutException, Exception) as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_device_status(self) -> dict[str, Any]:
        """Get device health status — CPU, memory, temperature, fans, PSU."""
        info = self.get_device_info()
        if "error" in info:
            return {"host": self.host, "status": "down", "error": info["error"]}
        return {"host": self.host, "status": "up", "name": self.name, "role": self.device.role}

    def get_config(self, config_type: str = "running") -> dict[str, Any]:
        """Get switch configuration as raw text + metadata (sha256, size, lines).

        Args:
            config_type: "running" (RAM, live) or "startup" (flash, boot).
        """
        try:
            cmd = "show configuration" if config_type == "startup" else "show running-config"
            with self._connect() as conn:
                self._no_page(conn)
                output = conn.send_command(cmd, read_timeout=120, delay_factor=4, cmd_verify=False)
            config = output.strip()
            if not config or "invalid input" in config.lower():
                return {"host": self.host, "error": "config_fetch_failed", "detail": output[:200]}
            return {
                "host": self.host,
                "config_type": config_type,
                "config": config,
                "sha256": hashlib.sha256(config.encode("utf-8")).hexdigest(),
                "size_bytes": len(config.encode("utf-8")),
                "line_count": len(config.splitlines()),
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def _no_page(self, conn) -> None:
        """Disable pagination on Ruckus ICX for reliable output reading."""
        conn.send_command_timing("skip-page-display", delay_factor=1, read_timeout=3)

    def get_ip_addresses(self) -> list[dict[str, Any]]:
        """List IP addresses configured on the device."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show ip address", read_timeout=20, cmd_verify=False)
            results: list[dict[str, Any]] = []
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("IP Address") or line_s.startswith("-"):
                    continue
                parts = line_s.split()
                if len(parts) < 4:
                    continue
                results.append({
                    "ip_address": parts[0],
                    "type": parts[1],
                    "lease": parts[2],
                    "interface": " ".join(parts[3:]),
                })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_ip_routes(self, destination: str | None = None) -> dict[str, Any]:
        """Get IP routing table (show ip route). Optional longest-prefix lookup by destination."""
        try:
            cmd = "show ip route"
            if destination:
                cmd = f"show ip route {_validate_route_dest(destination)}"
            with self._connect() as conn:
                self._no_page(conn)
                output = conn.send_command_timing(cmd, delay_factor=4, read_timeout=60)

            if "can't find matching entry" in output.lower():
                return {
                    "host": self.host, "destination": destination,
                    "total_routes": 0, "routes": [], "note": "no matching entry",
                }

            total_match = re.search(r"Total number of IP routes:\s*(\d+)", output)
            total = int(total_match.group(1)) if total_match else 0

            route_re = re.compile(
                r"^(\d+)\s+(\S+)\s+(\S+)\s+(.+?)\s+(\d+/\d+)\s+(\S+)\s+(\S+)\s*$"
            )
            routes: list[dict[str, Any]] = []
            for line in output.splitlines():
                m = route_re.match(line.strip())
                if not m:
                    continue
                cost = m.group(5)
                cost_parts = cost.split("/")
                routes.append({
                    "line": int(m.group(1)),
                    "destination": m.group(2),
                    "gateway": m.group(3),
                    "port": m.group(4).strip(),
                    "cost": cost,
                    "distance": int(cost_parts[0]) if len(cost_parts) == 2 else None,
                    "metric": int(cost_parts[1]) if len(cost_parts) == 2 else None,
                    "type": m.group(6),
                    "type_name": ROUTE_TYPE_MAP.get(m.group(6), m.group(6)),
                    "uptime": m.group(7),
                })
            return {
                "host": self.host,
                "destination": destination,
                "total_routes": total if total else len(routes),
                "routes": routes,
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_ipv6_routes(self, destination: str | None = None) -> dict[str, Any]:
        """Get IPv6 routing table (show ipv6 route). Optional longest-prefix lookup."""
        try:
            cmd = "show ipv6 route"
            if destination:
                cmd = f"show ipv6 route {_validate_route_dest_ipv6(destination)}"
            with self._connect() as conn:
                self._no_page(conn)
                output = conn.send_command_timing(cmd, delay_factor=4, read_timeout=60)

            if "can't find matching entry" in output.lower():
                return {
                    "host": self.host, "destination": destination,
                    "total_routes": 0, "routes": [], "note": "no matching entry",
                }

            total_match = re.search(r"IPv6 Routing Table\s*-\s*(\d+)\s*entries", output)
            total = int(total_match.group(1)) if total_match else 0

            # Normalize: join wrapped prefix lines. IPv6 prefix can wrap to next line
            # when too long (e.g. /128). Merge continuation lines (start with spaces, no type code).
            lines = output.splitlines()
            merged: list[str] = []
            for line in lines:
                line_s = line.rstrip()
                if not line_s:
                    continue
                stripped = line_s.strip()
                # New route line starts with a type code (B/C/L/O/R/S) + whitespace
                if re.match(r"^[BCLOSRScdefis]\s+\S", stripped):
                    merged.append(stripped)
                elif merged and stripped and not stripped.startswith(("Type", "BGP", "OSPF", "STATIC")):
                    # Continuation: append prefix to previous route line
                    merged[-1] = merged[-1] + " " + stripped

            # Parse: TYPE PREFIX NEXTHOP INTERFACE COST UPTIME
            route_re = re.compile(
                r"^([BCLOSRScdefis])\s+(\S+)\s+(\S+)\s+(.+?)\s+(\d+/\d+)\s+(\S+)\s*$"
            )
            routes: list[dict[str, Any]] = []
            for line in merged:
                m = route_re.match(line)
                if not m:
                    continue
                cost = m.group(5)
                cost_parts = cost.split("/")
                routes.append({
                    "type": m.group(1),
                    "type_name": ROUTE_TYPE_MAP_V6.get(m.group(1).upper(), m.group(1)),
                    "destination": m.group(2),
                    "gateway": m.group(3),
                    "port": m.group(4).strip(),
                    "cost": cost,
                    "distance": int(cost_parts[0]) if len(cost_parts) == 2 else None,
                    "metric": int(cost_parts[1]) if len(cost_parts) == 2 else None,
                    "uptime": m.group(6),
                })
            return {
                "host": self.host,
                "destination": destination,
                "total_routes": total if total else len(routes),
                "routes": routes,
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_vlan_summary(self) -> dict[str, Any]:
        """Get VLAN summary — VLAN IDs, names, and member ports."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show vlan brief", read_timeout=15)
            total_match = re.search(r"Total Number of Vlan Configured\s*:\s*(\d+)", output)
            total = int(total_match.group(1)) if total_match else 0
            vlan_list_match = re.search(r"VLANs Configured\s*:\s*(.+)", output)
            return {
                "host": self.host,
                "total_vlans": total,
                "vlans_configured": vlan_list_match.group(1).strip() if vlan_list_match else "",
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_port_vlan(self, port: str) -> dict[str, Any]:
        """Get VLAN membership for a single port."""
        try:
            with self._connect() as conn:
                output = conn.send_command(
                    f"show vlan brief ethernet {_validate_port(port)}", read_timeout=10
                )
            untagged_match = re.search(r"Untagged VLAN\s*:\s*(\S+)", output)
            tagged_match = re.search(r"Tagged\s+VLANs\s*:\s*(.+)", output)
            return {
                "host": self.host,
                "port": port,
                "untagged_vlan": untagged_match.group(1) if untagged_match else None,
                "tagged_vlans": tagged_match.group(1).strip() if tagged_match else None,
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "port": port, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    def get_mac_table_vlan(self, vlan_id: int) -> list[dict[str, Any]]:
        """Get MAC address table entries for a VLAN."""
        try:
            with self._connect() as conn:
                output = conn.send_command(
                    f"show mac-address vlan {_validate_vlan_id(vlan_id)}", read_timeout=15
                )
            results: list[dict[str, Any]] = []
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or "MAC-Address" in line_s or line_s.startswith("-"):
                    continue
                parts = line_s.split()
                if len(parts) < 3:
                    continue
                # format: mac port type vlan
                mac = parts[0]
                port = parts[1] if len(parts) > 1 else ""
                entry_type = parts[2] if len(parts) > 2 else ""
                if re.match(r"[0-9a-fA-F.]{12,}", mac):
                    results.append({
                        "mac": mac,
                        "port": port,
                        "type": entry_type,
                        "vlan": vlan_id,
                    })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def find_mac(self, mac: str) -> list[dict[str, Any]]:
        """Locate a MAC address across the MAC table."""
        try:
            with self._connect() as conn:
                output = conn.send_command(
                    f"show mac-address {_validate_mac(mac)}", read_timeout=10
                )
            results: list[dict[str, Any]] = []
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or "MAC-Address" in line_s or line_s.startswith("-"):
                    continue
                parts = line_s.split()
                if len(parts) < 3:
                    continue
                if re.match(r"[0-9a-fA-F.]{12,}", parts[0]):
                    results.append({
                        "mac": parts[0],
                        "port": parts[1] if len(parts) > 1 else "",
                        "type": parts[2] if len(parts) > 2 else "",
                        "vlan": parts[3] if len(parts) > 3 else "",
                    })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_lag_summary(self) -> list[dict[str, Any]]:
        """Get LAG (link aggregation) group summary."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show lag brief", read_timeout=15)
            results: list[dict[str, Any]] = []
            in_table = False
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("-"):
                    continue
                if "LAG" in line_s and "Type" in line_s:
                    in_table = True
                    continue
                if not in_table:
                    if "Total" in line_s:
                        results.append({"summary": line_s})
                        continue
                parts = re.split(r'\s+', line_s)
                if len(parts) < 5:
                    continue
                results.append({
                    "lag_name": parts[0],
                    "type": parts[1],
                    "deploy": parts[2],
                    "trunk_id": parts[3],
                    "lag_interface": parts[4],
                    "port_list": " ".join(parts[5:]) if len(parts) > 5 else "",
                })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_chassis_health(self) -> dict[str, Any]:
        """Get chassis health — fans, PSUs, and temperature sensors."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show chassis", read_timeout=15)
            health: dict[str, Any] = {"host": self.host, "units": []}
            current_unit: dict[str, Any] | None = None
            for line in output.splitlines():
                line_s = line.strip()
                if "stack unit" in line_s.lower() and "chassis info" in line_s.lower():
                    unit_match = re.search(r"stack unit\s+(\d+)", line_s, re.IGNORECASE)
                    if unit_match:
                        if current_unit:
                            health["units"].append(current_unit)
                        current_unit = {"unit": int(unit_match.group(1))}
                elif current_unit is not None:
                    if "Power supply" in line_s and "present" in line_s:
                        ps_match = re.search(
                            r"Power supply\s+(\d+)\s*\(\S+\)\s*(\S+), status (\S+)",
                            line_s,
                        )
                        if ps_match:
                            current_unit.setdefault("power_supplies", []).append({
                                "id": ps_match.group(1),
                                "present": ps_match.group(2),
                                "status": ps_match.group(3),
                            })
                    elif "Fan controlled temperature" in line_s:
                        temp_match = re.search(r"([\d.]+)\s+deg-C", line_s)
                        if temp_match:
                            current_unit["fan_temp_c"] = float(temp_match.group(1))
                    elif line_s.startswith("Slot") and "Current Temperature" in line_s:
                        slot_match = re.search(
                            r"Slot\s+(\d+)\s+Current Temperature:\s+(.+)",
                            line_s,
                        )
                        if slot_match:
                            temps = re.findall(r"([\d.]+)\s+deg-C", slot_match.group(2))
                            current_unit.setdefault("slot_temps", []).append({
                                "slot": int(slot_match.group(1)),
                                "temperatures_celsius": [float(t) for t in temps],
                            })
                    elif "Warning level" in line_s:
                        warn = re.search(r"([\d.]+)\s+deg-C", line_s)
                        if warn:
                            current_unit["temp_warning_c"] = float(warn.group(1))
                    elif "Shutdown level" in line_s:
                        shut = re.search(r"([\d.]+)\s+deg-C", line_s)
                        if shut:
                            current_unit["temp_shutdown_c"] = float(shut.group(1))
            if current_unit:
                health["units"].append(current_unit)
            return health
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_lldp_neighbors(self) -> list[dict[str, Any]]:
        """Get LLDP neighbors — remote device, port, and description."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show lldp neighbors", read_timeout=15)
            results: list[dict[str, Any]] = []
            in_table = False
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s:
                    continue
                if line_s.startswith("Lcl Port") or line_s.startswith("---"):
                    in_table = True
                    continue
                if not in_table:
                    continue
                parts = re.split(r"\s+", line_s)
                if len(parts) < 5:
                    continue
                results.append({
                    "local_port": parts[0],
                    "chassis_id": parts[1],
                    "port_id": parts[2],
                    "port_description": " ".join(parts[3:-1]) if len(parts) > 5 else parts[3],
                    "system_name": parts[-1],
                })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_sfp_info(self, port: str | None = None) -> list[dict[str, Any]]:
        """Get SFP/transceiver info — port type, vendor, serial. Optional port filter."""
        try:
            with self._connect() as conn:
                if port:
                    _validate_port(port)
                    cmd = f"show media ethernet {port}"
                else:
                    cmd = "show media"
                output = conn.send_command(cmd, read_timeout=15)
            results: list[dict[str, Any]] = []
            for match in re.finditer(
                r"Port\s+(\S+):\s+Type\s*:\s*(.+?)(?:\n|$)",
                output,
            ):
                port_name = match.group(1)
                port_type = match.group(2).strip()
                results.append({
                    "port": port_name,
                    "type": port_type,
                })
            if port and not results:
                return [{"host": self.host, "port": port, "error": "port_not_found_or_no_sfp"}]
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_cable_diag(self, port: str) -> dict[str, Any]:
        """Run TDR cable diagnostics on a copper port."""
        _validate_port(port)
        try:
            with self._connect() as conn:
                output = conn.send_command(
                    f"show cable-diag tdr {port}",
                    read_timeout=30,
                )
            result: dict[str, Any] = {"host": self.host, "port": port, "pairs": []}
            if "No TDR" in output:
                result["note"] = "TDR not supported on this port (fiber or disabled)"
                return result

            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("Port") or line_s.startswith("----"):
                    continue
                m = re.match(
                    r"(?:1/\d+/\d+\s+(?:\d+G\s*)?)?"
                    r"Pair\s+(\S+)\s+Pair\s+(\S+)\s+(\S+)",
                    line_s,
                )
                if not m:
                    continue
                result["pairs"].append({
                    "local_pair": m.group(1),
                    "remote_pair": m.group(2),
                    "pair_status": m.group(3),
                })
            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "port": port, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    def get_syslog(self, lines: int = 50, severity: str = "",
                   dedup: bool = True) -> dict[str, Any]:
        """Token-optimized syslog: parsed, deduplicated, severity-filtered."""
        lines = max(1, min(lines, 500))
        try:
            with self._connect() as conn:
                output = conn.send_command("show log", read_timeout=35)
            entries: list[dict[str, Any]] = []
            seen = output.split("Dynamic Log Buffer")
            raw = seen[-1] if len(seen) > 1 else output
            log_lines = raw.strip().splitlines()
            log_lines = [ln for ln in log_lines if ln.strip()
                         and not ln.strip().startswith("Syslog")
                         and not ln.strip().startswith("Buffer")
                         and not ln.strip().startswith("level")
                         and not ln.strip().startswith("Static")
                         and not ln.strip().startswith("(")]

            if severity:
                severity_set = set(severity.upper())
            else:
                severity_set = set()

            last_msg = ""
            last_entry: dict[str, Any] | None = None

            for line in log_lines:
                line_s = line.strip()
                m = re.match(
                    r"(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}):(\w):([^:]+):?(.*)$",
                    line_s,
                )
                if not m:
                    continue
                sev = m.group(2)
                if severity_set and sev not in severity_set:
                    continue
                msg = m.group(4).strip() if m.group(4) else ""
                entry = {
                    "timestamp": f"{m.group(1)}",
                    "severity": sev,
                    "facility": m.group(3).strip(),
                    "message": msg,
                }
                if dedup and last_entry and msg == last_msg:
                    if "count" not in last_entry:
                        last_entry["timestamp"] = f"{last_entry['timestamp']} (first)"
                        last_entry["count"] = 2
                    else:
                        last_entry["count"] += 1
                    last_entry["last_ts"] = entry["timestamp"]
                    continue
                entries.append(entry)
                last_msg = msg
                last_entry = entry

            total = len(entries)
            entries = entries[-lines:]
            return {
                "host": self.host,
                "returned": len(entries),
                "total": total,
                "severity_filter": severity or "all",
                "entries": entries,
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_optic_info(self, port: str) -> dict[str, Any]:
        """Get SFP optic DOM info — temperature, voltage, tx/rx power."""
        _validate_port(port)
        try:
            with self._connect() as conn:
                dm = conn.send_command(f"show optic {port}", read_timeout=12)
                thresh = conn.send_command(
                    f"show optic thresholds {port}", read_timeout=12)
            result: dict[str, Any] = {"host": self.host, "port": port}
            if "not enabled" in dm.lower() and "not enabled" in thresh.lower():
                result["note"] = "Optical monitoring not enabled"
                return result
            self._parse_optic_dom(result, dm, port)
            self._parse_optic_thresholds(result, thresh)
            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "port": port, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    @staticmethod
    def _parse_optic_dom(result: dict[str, Any], output: str, port: str) -> None:
        for line in output.splitlines():
            line_s = line.strip()
            if not line_s.startswith(port):
                continue
            parts = re.findall(r"(-?\d+\.\d+)\s+(\S+)", line_s)
            if len(parts) >= 5:
                for i, (val, unit) in enumerate(parts[:5]):
                    name = ["temperature", "voltage", "tx_power",
                            "rx_power", "tx_bias"][i]
                    result[name] = float(val)
                    result[f"{name}_unit"] = unit
                break

    @staticmethod
    def _parse_optic_thresholds(result: dict[str, Any], output: str) -> None:
        patterns = {
            "temperature": r"Temperature\s+(High|Low)\s+(alarm|warning)\s+\S+\s+(-?[\d.]+)\s+\S",
            "voltage": r"Supply Voltage\s+(High|Low)\s+(alarm|warning)\s+\S+\s+(-?[\d.]+)\s+\S",
            "tx_bias": r"TX Bias\s+(High|Low)\s+(alarm|warning)\s+\S+\s+(-?[\d.]+)\s+\S",
            "tx_power": r"TX Power\s+(High|Low)\s+(alarm|warning)\s+\S+\s+(-?[\d.]+)\s+\S",
            "rx_power": r"RX Power\s+(High|Low)\s+(alarm|warning)\s+\S+\s+(-?[\d.]+)\s+\S",
        }
        thresholds: dict[str, dict[str, float]] = {}
        for field, pattern in patterns.items():
            for m in re.finditer(pattern, output, re.IGNORECASE):
                severity = f"{m.group(1).lower()}_{m.group(2).lower()}"
                thresholds.setdefault(field, {})[severity] = float(m.group(3))
        if thresholds:
            result["thresholds"] = thresholds

    def get_device_time(self) -> dict[str, Any]:
        """Get device clock and NTP sync status."""
        try:
            with self._connect() as conn:
                clk = conn.send_command("show clock", read_timeout=10, expect_string=r"#")
                ntp = conn.send_command("show ntp status", read_timeout=10, expect_string=r"#")
                peers = conn.send_command("show ntp associations", read_timeout=10, expect_string=r"#")
            result: dict[str, Any] = {"host": self.host}

            m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d+)\s+(\S+)\s+(\w{3})\s+(\w{3})\s+(\d{2})\s+(\d{4})", clk)
            if m:
                result["current_time"] = (
                    f"{m.group(3)} {m.group(4)} {m.group(5)} {m.group(6)} "
                    f"{m.group(1)} {m.group(2)}"
                )

            if "unsynchronized" in ntp.lower():
                result["ntp_synced"] = False
                result["ntp_status"] = "unsynchronized — no reference clock"
            elif "synchronized" in ntp.lower():
                result["ntp_synced"] = True

            ntp_parts = ntp.strip().split("\n")
            for line in ntp_parts:
                if "server mode" in line.lower():
                    result["ntp_server_enabled"] = "enabled" in line.lower() and "dis" not in line.lower()
                if "client mode" in line.lower():
                    result["ntp_client_enabled"] = "enabled" in line.lower() and "dis" not in line.lower()
                if "master mode" in line.lower():
                    result["ntp_master_enabled"] = "enabled" in line.lower() and "dis" not in line.lower()
                if "panic mode" in line.lower():
                    result["ntp_in_panic"] = "not in panic" not in line.lower()

            peer_list: list[dict[str, Any]] = []
            for line in peers.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("address") or line_s.startswith("* synced"):
                    continue
                parts = re.split(r"\s+", line_s)
                if len(parts) >= 11:
                    peer_list.append({
                        "address": parts[1] if parts[0] == "~" else parts[0],
                        "ref_clock": parts[3] if len(parts) > 3 else "",
                        "stratum": parts[4] if len(parts) > 4 else "",
                        "reachable": parts[7] != "0" if len(parts) > 7 else False,
                        "delay": parts[8] if len(parts) > 8 else "",
                        "offset": parts[9] if len(parts) > 9 else "",
                    })
            result["ntp_peers"] = peer_list

            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_spanning_tree(self, vlan: str | None = None) -> dict[str, Any]:
        """Get spanning-tree topology — root bridge, port roles, states."""
        try:
            with self._connect() as conn:
                cmd = f"show span vlan {vlan}" if vlan else "show span"
                output = conn.send_command(cmd, read_timeout=15)
            result: dict[str, Any] = {"host": self.host, "ports": []}

            if "not configured" in output:
                m = re.search(r"port-vlan (\d+)", output)
                result["stp_configured"] = False
                result["vlan"] = int(m.group(1)) if m else None
                return result

            result["stp_configured"] = True

            m = re.search(
                r"(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+(\S+)",
                output,
            )
            if m:
                result["vlan"] = int(m.group(1))
                result["root_id"] = m.group(2)
                result["root_cost"] = int(m.group(3))
                result["root_port"] = m.group(4)
                result["bridge_priority"] = m.group(5)
                result["bridge_address"] = m.group(6)

            for line in output.splitlines():
                line_s = line.strip()
                m = re.match(
                    r"(\d+/\d+/\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
                    line_s,
                )
                if not m:
                    continue
                result["ports"].append({
                    "port": m.group(1),
                    "priority": m.group(2),
                    "path_cost": int(m.group(3)) if m.group(3).isdigit() else m.group(3),
                    "state": m.group(4),
                    "fwd_transitions": int(m.group(5)) if m.group(5).isdigit() else 0,
                    "designated_cost": m.group(6),
                    "designated_root": m.group(7),
                    "designated_bridge": m.group(8),
                })

            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_access_lists(self, name: str | None = None, brief: bool = False) -> dict[str, Any]:
        """Get IP access lists with their rules."""
        try:
            with self._connect() as conn:
                if brief:
                    cmd = "show ip access-list brief"
                elif name:
                    cmd = f"show ip access-list {name}"
                else:
                    cmd = "show ip access-list"
                output = conn.send_command(cmd, read_timeout=12)
            result: dict[str, Any] = {"host": self.host, "acls": []}

            if "Incomplete" in output or "Invalid" in output:
                return {"host": self.host, "error": "command_not_supported"}

            if brief:
                for line in output.splitlines():
                    m = re.match(r"(Standard|Extended) IP access list (\S+): (\d+) entries", line)
                    if m:
                        result["acls"].append({
                            "type": m.group(1),
                            "name": m.group(2),
                            "entries": int(m.group(3)),
                        })
                return result

            current = None
            for line in output.splitlines():
                line_s = line.strip()
                m = re.match(r"(Standard|Extended) IP access list (\S+): (\d+) entries", line_s)
                if m:
                    current = {
                        "type": m.group(1),
                        "name": m.group(2),
                        "entries": int(m.group(3)),
                        "rules": [],
                    }
                    result["acls"].append(current)
                    continue
                if current and name and current["name"] != name:
                    continue
                r = re.match(r"(\d+):\s+(permit|deny)\s+(.+)$", line_s)
                if r and current:
                    current["rules"].append({
                        "sequence": int(r.group(1)),
                        "action": r.group(2),
                        "match": r.group(3).strip(),
                    })

            if not result["acls"]:
                result["note"] = "No IP ACLs configured"
            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_device_resources(self) -> dict[str, Any]:
        """Get CPU and memory utilization."""
        try:
            with self._connect() as conn:
                cpu_out = conn.send_command("show cpu", read_timeout=15)
                mem_out = conn.send_command("show memory", read_timeout=15)
            result: dict[str, Any] = {"host": self.host, "cpus": []}

            for match in re.finditer(
                r"cpu(\d+):[\s\S]*?300\s+sec avg:\s*(\d+) percent busy",
                cpu_out, re.IGNORECASE,
            ):
                result["cpus"].append({
                    "cpu_id": int(match.group(1)),
                    "pct_busy_1sec": 0,
                    "pct_busy_5sec": 0,
                    "pct_busy_60sec": 0,
                    "pct_busy_300sec": int(match.group(2)),
                })
            for sec, field in [("1", "pct_busy_1sec"), ("5", "pct_busy_5sec"), ("60", "pct_busy_60sec")]:
                values = re.findall(
                    rf"cpu(\d+):[\s\S]*?{sec}\s+sec avg:\s*(\d+) percent busy",
                    cpu_out, re.IGNORECASE,
                )
                for cpu_id_str, val in values:
                    cpu_id = int(cpu_id_str)
                    for cpu in result["cpus"]:
                        if cpu["cpu_id"] == cpu_id:
                            cpu[field] = int(val)

            mem_total = re.search(r"Total DRAM:\s*(\d+)\s*bytes", mem_out)
            mem_free = re.search(r"Dynamic memory:.*?(\d+)\s*bytes free", mem_out)
            mem_pct = re.search(r"(\d+)%\s*used", mem_out)

            if mem_total and mem_free:
                result["memory_total_bytes"] = int(mem_total.group(1))
                result["memory_free_bytes"] = int(mem_free.group(1))
                result["memory_used_bytes"] = result["memory_total_bytes"] - result["memory_free_bytes"]
                result["memory_used_pct"] = round(
                    result["memory_used_bytes"] / result["memory_total_bytes"] * 100, 1,
                )
            elif mem_total and mem_pct:
                result["memory_total_bytes"] = int(mem_total.group(1))
                result["memory_used_pct"] = int(mem_pct.group(1))
            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_arp_table(self) -> list[dict[str, Any]]:
        """Get ARP table — IP-to-MAC-to-port mapping."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show arp", read_timeout=15)
            results: list[dict[str, Any]] = []
            in_table = False
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s:
                    continue
                if line_s.startswith("No.") and "IP Address" in line_s:
                    in_table = True
                    continue
                if not in_table:
                    continue
                if re.match(r"^\d+\s+", line_s):
                    parts = re.split(r"\s+", line_s)
                    if len(parts) >= 6:
                        results.append({
                            "ip": parts[1],
                            "mac": parts[2],
                            "type": parts[3],
                            "age": int(parts[4]) if parts[4].isdigit() else 0,
                            "port": parts[5],
                            "status": parts[6] if len(parts) > 6 else "",
                        })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_users(self) -> list[dict[str, Any]]:
        """Get local user accounts (password hash not exposed)."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show users", read_timeout=15)
            results: list[dict[str, Any]] = []
            in_table = False
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s:
                    continue
                if "Username" in line_s and "Password" in line_s:
                    in_table = True
                    continue
                if line_s.startswith("==="):
                    continue
                if not in_table:
                    continue
                parts = re.split(r"\s+", line_s)
                if len(parts) < 5:
                    continue
                results.append({
                    "username": parts[0],
                    "encrypt": parts[2] if len(parts) > 2 else "",
                    "privilege": parts[3] if len(parts) > 3 else "",
                    "status": parts[4] if len(parts) > 4 else "",
                    "expire_time": parts[5] if len(parts) > 5 else "",
                })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_ssh_status(self) -> dict[str, Any]:
        """Get SSH server status — version, host key, active sessions."""
        try:
            with self._connect() as conn:
                output = conn.send_command("show ip ssh", read_timeout=15)
            result: dict[str, Any] = {"host": self.host, "sessions": []}

            server = re.search(
                r"SSH-(v\d+(?:\.\d+)?)\s+(\w+)", output, re.IGNORECASE
            )
            if server:
                result["ssh_version"] = server.group(1)
                result["ssh_enabled"] = server.group(2).lower() == "enabled"
            hostkey = re.search(r"hostkey:\s*(.+)", output, re.IGNORECASE)
            if hostkey:
                result["host_key"] = hostkey.group(1).strip()

            section = "unknown"
            in_header = False
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s:
                    continue
                if line_s.lower().startswith("inbound"):
                    section = "inbound"
                    in_header = True
                    continue
                if line_s.lower().startswith("outbound"):
                    section = "outbound"
                    in_header = True
                    continue
                if in_header and "Connection" in line_s and "Version" in line_s:
                    in_header = False
                    continue
                if in_header:
                    in_header = False
                if section not in ("inbound", "outbound"):
                    continue
                if line_s.startswith("SSH-"):
                    continue
                parts = re.split(r"\s+", line_s)
                if len(parts) < 3:
                    continue
                if not parts[0].isdigit():
                    continue
                result["sessions"].append({
                    "direction": section,
                    "connection": int(parts[0]),
                    "version": parts[1],
                    "encryption": parts[2],
                    "username": parts[3] if len(parts) > 3 else "",
                    "hmac": parts[4] if len(parts) > 4 else "",
                    "server_hostkey": parts[5] if len(parts) > 5 else "",
                    "source_ip": parts[6] if len(parts) > 6 else "",
                })

            if "ssh_enabled" not in result:
                result["note"] = "no parseable SSH server info"
            return result
        except NetmikoTimeoutException:
            return {"host": self.host, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

    def get_ipv6_interfaces(self) -> list[dict[str, Any]]:
        """Get IPv6 interface addresses and status."""
        try:
            with self._connect() as conn:
                self._no_page(conn)
                output = conn.send_command("show ipv6 interface", read_timeout=20, cmd_verify=False)
            results: list[dict[str, Any]] = []
            for line in output.splitlines():
                line_s = line.strip()
                if not line_s or "Interface" in line_s or "Routing Protocols" in line_s:
                    continue
                parts = line_s.split()
                if len(parts) < 3:
                    continue
                results.append({
                    "interface": parts[0],
                    "status": parts[1] if len(parts) > 1 else "",
                    "global_unicast": parts[2] if len(parts) > 2 else "",
                    "vrf": parts[-1] if len(parts) > 3 and parts[-1].startswith("default") else "",
                })
            return results
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def device_ping(self, ip: str, source: str | None = None) -> dict[str, Any]:
        """Ping test via ICMP (IPv4) with optional source."""
        try:
            cmd = f"ping {_validate_ipv4(ip)}"
            if source:
                cmd += f" source {_validate_ipv4(source)}"
            with self._connect() as conn:
                output = conn.send_command_timing(cmd, delay_factor=2, read_timeout=10)
            # Parse output
            reply_match = re.search(r"Reply from\s+(\S+)\s*:\s*bytes=\d+\s+time=(\d+)ms", output)
            success_match = re.search(r"Success rate is\s+(\d+)\s+percent\s*\((\d+)/(\d+)\)", output)
            rtt_match = re.search(r"round-trip min/avg/max=(\d+)/(\d+)/(\d+)\s*ms", output)
            if reply_match and success_match:
                return {
                    "host": self.host,
                    "target_ip": ip,
                    "source_ip": source if source else "default",
                    "reached": True,
                    "reply_bytes": 16,
                    "rtt_ms": int(reply_match.group(2)),
                    "success_rate_pct": int(success_match.group(1)),
                    "packets_sent": int(success_match.group(3)),
                    "packets_received": int(success_match.group(2)),
                    "rtt_min_ms": int(rtt_match.group(1)) if rtt_match else None,
                    "rtt_avg_ms": int(rtt_match.group(2)) if rtt_match else None,
                    "rtt_max_ms": int(rtt_match.group(3)) if rtt_match else None,
                }
            return {
                "host": self.host,
                "target_ip": ip,
                "source_ip": source if source else "default",
                "reached": False,
                "error": "no_reply",
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "target_ip": ip, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "target_ip": ip, "error": str(exc)}

    def device_ping_ipv6(self, ip: str) -> dict[str, Any]:
        """Ping test via ICMPv6."""
        try:
            with self._connect() as conn:
                output = conn.send_command_timing(f"ping ipv6 {_validate_ipv6(ip)}", delay_factor=2, read_timeout=10)
            reply_match = re.search(r"Reply from\s+(\S+)\s*:\s*bytes=\d+\s+time=(\d+)ms\s+Hop Limit=(\d+)", output)
            success_match = re.search(r"Success rate is\s+(\d+)\s+percent\s*\((\d+)/(\d+)\)", output)
            rtt_match = re.search(r"round-trip min/avg/max=(\d+)/(\d+)/(\d+)\s*ms", output)
            if reply_match and success_match:
                return {
                    "host": self.host,
                    "target_ip": ip,
                    "reached": True,
                    "reply_bytes": 16,
                    "rtt_ms": int(reply_match.group(2)),
                    "hop_limit": int(reply_match.group(3)),
                    "success_rate_pct": int(success_match.group(1)),
                    "packets_sent": int(success_match.group(3)),
                    "packets_received": int(success_match.group(2)),
                    "rtt_min_ms": int(rtt_match.group(1)) if rtt_match else None,
                    "rtt_avg_ms": int(rtt_match.group(2)) if rtt_match else None,
                    "rtt_max_ms": int(rtt_match.group(3)) if rtt_match else None,
                }
            return {
                "host": self.host,
                "target_ip": ip,
                "reached": False,
                "error": "no_reply",
            }
        except NetmikoTimeoutException:
            return {"host": self.host, "target_ip": ip, "error": "timeout"}
        except Exception as exc:
            return {"host": self.host, "target_ip": ip, "error": str(exc)}

    def device_traceroute(
        self, target: str, source_ip: str | None = None, max_ttl: int = 30
    ) -> list[dict[str, Any]]:
        """Traceroute (IPv4). Forward hostname raw to device — device resolves DNS, or returns error."""
        try:
            _ip_or_hostname = _validate_ipv4(target) if IPV4_RE.match(target) else target
            cmd = f"traceroute {_ip_or_hostname}"
            if source_ip:
                cmd += f" source-ip {_validate_ipv4(source_ip)}"
            cmd += f" maxttl {max_ttl}"
            with self._connect() as conn:
                output = conn.send_command_timing(cmd, delay_factor=8, read_timeout=90)
            err = self._detect_traceroute_error(output)
            if err:
                return [{"host": self.host, "target_ip": target, **err}]
            return self._parse_traceroute_output(output)
        except NetmikoTimeoutException:
            return [{"host": self.host, "target_ip": target, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "target_ip": target, "error": str(exc)}]

    def device_traceroute_ipv6(
        self, target: str, max_ttl: int = 30
    ) -> list[dict[str, Any]]:
        """Traceroute IPv6. Forward hostname raw to device — device resolves DNS, or returns error."""
        try:
            _target = _validate_ipv6(target) if IPV6_RE.match(target) else target
            cmd = f"traceroute ipv6 {_target} maxttl {max_ttl}"
            with self._connect() as conn:
                output = conn.send_command_timing(cmd, delay_factor=8, read_timeout=90)
            err = self._detect_traceroute_error(output)
            if err:
                return [{"host": self.host, "target_ip": target, **err}]
            return self._parse_traceroute_output(output)
        except NetmikoTimeoutException:
            return [{"host": self.host, "target_ip": target, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "target_ip": target, "error": str(exc)}]

    @staticmethod
    def _detect_traceroute_error(output: str) -> dict[str, str] | None:
        """Detect device-side errors in ICX traceroute output (before parsing)."""
        low = output.lower()
        if "inactive source ip" in low or "errno" in low and "source ip" in low:
            return {"error": "inactive_source_ip", "detail": output.strip()}
        if "invalid input" in low:
            return {"error": "invalid_input", "detail": output.strip()}
        if "bad ip" in low or "unresolved" in low:
            return {"error": "invalid_target", "detail": output.strip()}
        if "failed dns" in low or "dns request" in low or "failed to initialize dns" in low:
            return {"error": "dns_resolution_failed", "detail": output.strip()}
        return None

    @staticmethod
    def _parse_traceroute_output(output: str) -> list[dict[str, Any]]:
        """Parse full ICX traceroute output (shared by v4 + v6)."""
        results: list[dict[str, Any]] = []
        in_trace = False
        for line in output.splitlines():
            line_s = line.strip()
            if "Tracing the route" in line_s:
                in_trace = True
                continue
            if not in_trace:
                continue
            if "Type Control-c" in line_s or not line_s:
                continue
            parsed = RuckusDeviceDriver._parse_traceroute_line(line_s)
            if parsed:
                results.append(parsed)
        return results

    @staticmethod
    def _parse_traceroute_line(line: str) -> dict[str, Any] | None:
        """Parse one hop line from ICX traceroute output.

        Handles reachable, timeout ('* * * ?'), and DNS-resolved ('host(1.2.3.4)').
        Returns None for non-hop lines.
        """
        parts = line.split()
        if not parts or not parts[0].isdigit():
            return None
        hop = int(parts[0])

        rtts: list[str] = []
        dest_tokens: list[str] = []
        for tok in parts[1:]:
            if tok == "ms":
                continue
            if tok == "*" or tok.startswith("<") or re.match(r"^\d+(?:\.\d+)?$", tok):
                rtts.append(tok)
            else:
                dest_tokens.append(tok)

        while len(rtts) < 3:
            rtts.append("*")
        if not dest_tokens:
            dest_tokens.append("*")

        dest_raw = " ".join(dest_tokens).strip()
        status = "reachable"
        hop_ip: str | None
        hostname: str | None = None

        if dest_raw in ("*", "?") or not dest_raw:
            status = "timeout"
            hop_ip = None
        else:
            ip_m = re.search(r"\((\d{1,3}(?:\.\d{1,3}){3})\)", dest_raw)
            if ip_m:
                hop_ip = ip_m.group(1)
                hostname = dest_raw.split("(")[0].strip() or None
            elif re.match(r"^\d{1,3}(\.\d{1,3}){3}$", dest_raw):
                hop_ip = dest_raw
            else:
                hop_ip = dest_raw

        return {
            "hop": hop,
            "ip": hop_ip,
            "hostname": hostname,
            "rtt1_ms": RuckusDeviceDriver._parse_rtt(rtts[0]),
            "rtt2_ms": RuckusDeviceDriver._parse_rtt(rtts[1]),
            "rtt3_ms": RuckusDeviceDriver._parse_rtt(rtts[2]),
            "status": status,
        }

    @staticmethod
    def _parse_rtt(value: str) -> float | None:
        if not value or value == "*":
            return None
        if value == "<1":
            return 0.5
        value = value.replace("ms", "")
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def set_port_state(
        self, port: str, enable: bool, dry_run: bool = False,
    ) -> dict[str, Any]:
        """Enable or disable an Ethernet port."""
        _validate_port(port)
        state = "enabled" if enable else "disabled"
        commands = [
            "configure terminal",
            f"interface ethernet {port}",
            "enable" if enable else "disable",
            "end",
        ]
        if dry_run:
            return {"host": self.host, "port": port, "dry_run": True,
                    "state": state, "commands": commands}
        logger.info(
            "set_port_state: host=%s port=%s %s", self.host, port, state,
        )
        try:
            with self._connect() as conn:
                conn.send_command_timing(
                    "configure terminal", delay_factor=2, read_timeout=10,
                )
                conn.send_command_timing(
                    f"interface ethernet {port}", delay_factor=2, read_timeout=10,
                )
                conn.send_command_timing(
                    "enable" if enable else "disable",
                    delay_factor=2, read_timeout=10,
                )
                conn.send_command_timing("end", delay_factor=2, read_timeout=10)
            return {"host": self.host, "port": port, "state": state}
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "port": port, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    # ── VLAN Tools ────────────────────────────────────────────────

    def create_vlan(
        self,
        vlan_spec: str,
        name: str | None = None,
        tagged_ports: str = "",
        untagged_ports: str = "",
        spanning_tree: bool = False,
        stp_priority: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create a VLAN, optionally with a name and tagged/untagged ports."""
        vlan_ids = _parse_vlan_spec(vlan_spec)
        _validate_ports_spec(tagged_ports)
        _validate_ports_spec(untagged_ports)
        is_single = len(vlan_ids) == 1
        if name and not is_single:
            raise ValueError("VLAN name only supported for single VLAN, not range/multi")
        if stp_priority is not None and not is_single:
            raise ValueError("STP priority only supported for single VLAN")

        cmd_vlan = f"vlan {vlan_spec}"
        if name:
            cmd_vlan += f" name {name}"
        commands = ["configure terminal", cmd_vlan]
        if untagged_ports:
            commands.append(f"untagged {untagged_ports}")
        if tagged_ports:
            commands.append(f"tagged {tagged_ports}")
        if spanning_tree:
            if is_single:
                commands.append("spanning-tree")
                if stp_priority is not None:
                    commands.append(f"spanning-tree priority {stp_priority}")
            else:
                commands.append("spanning-tree 802-1w")
        commands.append("end")

        if dry_run:
            return {"host": self.host, "vlan_spec": vlan_spec,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": commands}

        logger.info(
            "create_vlan: host=%s spec=%s name=%s tagged=%s untagged=%s stp=%s",
            self.host, vlan_spec, name, tagged_ports, untagged_ports, spanning_tree,
        )
        try:
            with self._connect() as conn:
                for cmd in commands:
                    conn.send_command_timing(
                        cmd, delay_factor=2, read_timeout=10,
                    )
            return {
                "host": self.host, "vlan_spec": vlan_spec,
                "vlan_ids": vlan_ids, "created": True,
            }
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "vlan_spec": vlan_spec, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "vlan_spec": vlan_spec, "error": str(exc)}

    def delete_vlan(
        self, vlan_spec: str, dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete one or more VLANs."""
        vlan_ids = _parse_vlan_spec(vlan_spec)
        commands = [
            "configure terminal",
            f"no vlan {vlan_spec}",
            "end",
        ]
        if dry_run:
            return {"host": self.host, "vlan_spec": vlan_spec,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": commands}
        logger.info("delete_vlan: host=%s spec=%s", self.host, vlan_spec)
        try:
            with self._connect() as conn:
                for cmd in commands:
                    conn.send_command_timing(
                        cmd, delay_factor=2, read_timeout=10,
                    )
            return {
                "host": self.host, "vlan_spec": vlan_spec,
                "vlan_ids": vlan_ids, "deleted": True,
            }
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "vlan_spec": vlan_spec, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "vlan_spec": vlan_spec, "error": str(exc)}

    def modify_vlan_port(
        self, port: str, vlan_spec: str, action: str, tagged: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add or remove VLAN membership on a port."""
        _validate_port(port)
        vlan_ids = _parse_vlan_spec(vlan_spec)
        if action not in ("add", "remove"):
            raise ValueError(f"Invalid action: {action!r} (expected 'add' or 'remove')")

        commands: list[str] = []
        commands.append("configure terminal")
        if action == "add":
            if tagged:
                commands.append(f"interface ethernet {port}")
                commands.append(f"vlan-config add tagged-vlan {vlan_spec}")
                commands.append("exit")
            else:
                for vlan_id in vlan_ids:
                    commands.append(f"vlan {vlan_id}")
                    commands.append(f"untagged ethernet {port}")
                    commands.append("exit")
        else:
            for vlan_id in vlan_ids:
                commands.append(f"vlan {vlan_id}")
                prefix = "tagged" if tagged else "untagged"
                commands.append(f"no {prefix} ethernet {port}")
                commands.append("exit")
        commands.append("end")

        if dry_run:
            return {"host": self.host, "port": port, "action": action,
                    "dry_run": True, "vlan_ids": vlan_ids, "commands": commands}
        logger.info(
            "modify_vlan_port: host=%s port=%s action=%s spec=%s tagged=%s",
            self.host, port, action, vlan_spec, tagged,
        )
        try:
            with self._connect() as conn:
                for cmd in commands:
                    conn.send_command_timing(
                        cmd, delay_factor=2, read_timeout=20 if "vlan-config" in cmd else 10,
                    )
            return {
                "host": self.host, "port": port, "action": action,
                "vlan_spec": vlan_spec, "vlan_ids": vlan_ids, "success": True,
            }
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "port": port, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    def set_poe_port(
        self,
        port: str,
        enable: bool,
        priority: int | None = None,
        power_limit: int | None = None,
        power_by_class: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Enable/disable PoE with optional priority, power-limit, or power-by-class."""
        _validate_port(port)
        if priority is not None and priority not in (1, 2, 3):
            raise ValueError(f"Invalid priority {priority} (must be 1=critical, 2=high, 3=low)")
        if power_by_class is not None:
            if not enable:
                raise ValueError("power_by_class only valid when enable=True")
            if not (0 <= power_by_class <= 8):
                raise ValueError(f"Invalid power class {power_by_class} (must be 0-8)")
        if power_limit is not None:
            if not enable:
                raise ValueError("power_limit only valid when enable=True")
            if power_limit <= 0:
                raise ValueError(f"Invalid power_limit {power_limit} (must be > 0)")

        if (power_limit is not None or power_by_class is not None) and priority is None:
            raise ValueError(
                "priority is required when setting power_limit or power_by_class "
                "(ICX syntax requires priority first)"
            )

        # Build inline power command
        if not enable:
            power_cmd = "no inline power"
            action = "disable"
        elif priority is not None:
            parts = [f"inline power priority {priority}"]
            if power_by_class is not None:
                parts.append(f"power-by-class {power_by_class}")
            elif power_limit is not None:
                parts.append(f"power-limit {power_limit}")
            power_cmd = " ".join(parts)
            action = "enable"
        else:
            power_cmd = "inline power"
            action = "enable"

        commands = [
            "configure terminal",
            f"interface ethernet {port}",
            power_cmd,
            "end",
        ]
        if dry_run:
            return {"host": self.host, "port": port, "dry_run": True,
                    "action": action, "command": power_cmd, "commands": commands}
        logger.info(
            "set_poe_port: host=%s port=%s cmd=%s", self.host, port, power_cmd,
        )
        try:
            with self._connect() as conn:
                for cmd in commands:
                    conn.send_command_timing(
                        cmd, delay_factor=2, read_timeout=10,
                    )
            result: dict[str, Any] = {"host": self.host, "port": port,
                                       "action": action, "success": True}
            if priority is not None:
                result["priority"] = priority
            if power_limit is not None:
                result["power_limit_mw"] = power_limit
            if power_by_class is not None:
                result["power_by_class"] = power_by_class
            return result
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "port": port, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "port": port, "error": str(exc)}

    # ── Static Route Tools ────────────────────────────────────────

    def add_static_route(
        self,
        dest: str,
        mask: str,
        next_hop: str,
        metric: int | None = None,
        distance: int | None = None,
        name: str | None = None,
        tag: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add an IPv4 static route (ip route <dest> <mask> <next-hop>)."""
        _validate_ipv4(dest)
        _validate_netmask(mask)
        next_hop_cmd = _normalize_next_hop(next_hop)

        cmd = f"ip route {dest} {mask} {next_hop_cmd}"
        if metric is not None:
            cmd += f" {_validate_route_metric(metric)}"
        if distance is not None:
            cmd += f" distance {_validate_route_distance(distance)}"
        if name is not None:
            cmd += f" name {_validate_route_name(name)}"
        if tag is not None:
            cmd += f" tag {_validate_route_tag(tag)}"

        commands = ["configure terminal", cmd, "end"]
        if dry_run:
            return {"host": self.host, "dest": dest, "mask": mask,
                    "next_hop": next_hop_cmd, "dry_run": True, "commands": commands}

        logger.info(
            "add_static_route: host=%s dest=%s/%s next_hop=%s",
            self.host, dest, mask, next_hop_cmd,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "dest": dest, "mask": mask, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "dest": dest, "mask": mask, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "dest": dest, "mask": mask,
                    "next_hop": next_hop_cmd, "error": cli_error}
        return {"host": self.host, "dest": dest, "mask": mask,
                "next_hop": next_hop_cmd, "added": True}

    def delete_static_route(
        self,
        dest: str,
        mask: str,
        next_hop: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete an IPv4 static route (no ip route <dest> <mask> <next-hop>)."""
        _validate_ipv4(dest)
        _validate_netmask(mask)
        next_hop_cmd = _normalize_next_hop(next_hop)

        cmd = f"no ip route {dest} {mask} {next_hop_cmd}"
        commands = ["configure terminal", cmd, "end"]
        if dry_run:
            return {"host": self.host, "dest": dest, "mask": mask,
                    "next_hop": next_hop_cmd, "dry_run": True, "commands": commands}

        logger.info(
            "delete_static_route: host=%s dest=%s/%s next_hop=%s",
            self.host, dest, mask, next_hop_cmd,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "dest": dest, "mask": mask, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "dest": dest, "mask": mask, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "dest": dest, "mask": mask,
                    "next_hop": next_hop_cmd, "error": cli_error}
        return {"host": self.host, "dest": dest, "mask": mask,
                "next_hop": next_hop_cmd, "deleted": True}

    def add_static_route_ipv6(
        self,
        dest: str,
        next_hop: str,
        metric: int | None = None,
        distance: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add an IPv6 static route (ipv6 route <dest>/<prefix> <next-hop>)."""
        _validate_route_dest_ipv6(dest)
        next_hop_cmd = _normalize_next_hop_ipv6(next_hop)

        cmd = f"ipv6 route {dest} {next_hop_cmd}"
        if metric is not None:
            cmd += f" {_validate_route_metric(metric)}"
        if distance is not None:
            cmd += f" distance {_validate_route_distance(distance)}"

        commands = ["configure terminal", cmd, "end"]
        if dry_run:
            return {"host": self.host, "dest": dest,
                    "next_hop": next_hop_cmd, "dry_run": True, "commands": commands}

        logger.info(
            "add_static_route_ipv6: host=%s dest=%s next_hop=%s",
            self.host, dest, next_hop_cmd,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "dest": dest, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "dest": dest, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "dest": dest,
                    "next_hop": next_hop_cmd, "error": cli_error}
        return {"host": self.host, "dest": dest,
                "next_hop": next_hop_cmd, "added": True}

    def delete_static_route_ipv6(
        self,
        dest: str,
        next_hop: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete an IPv6 static route (no ipv6 route <dest>/<prefix> <next-hop>)."""
        _validate_route_dest_ipv6(dest)
        next_hop_cmd = _normalize_next_hop_ipv6(next_hop)

        cmd = f"no ipv6 route {dest} {next_hop_cmd}"
        commands = ["configure terminal", cmd, "end"]
        if dry_run:
            return {"host": self.host, "dest": dest,
                    "next_hop": next_hop_cmd, "dry_run": True, "commands": commands}

        logger.info(
            "delete_static_route_ipv6: host=%s dest=%s next_hop=%s",
            self.host, dest, next_hop_cmd,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "dest": dest, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "dest": dest, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "dest": dest,
                    "next_hop": next_hop_cmd, "error": cli_error}
        return {"host": self.host, "dest": dest,
                "next_hop": next_hop_cmd, "deleted": True}

    def set_ipv6_unicast_routing(
        self, enable: bool = True, dry_run: bool = False,
    ) -> dict[str, Any]:
        """Enable or disable IPv6 unicast routing globally on the switch."""
        action = "enable" if enable else "disable"
        command = "ipv6 unicast-routing" if enable else "no ipv6 unicast-routing"
        commands = ["configure terminal", command, "end"]
        if dry_run:
            return {"host": self.host, "action": action,
                    "dry_run": True, "commands": commands}

        logger.info(
            "set_ipv6_unicast_routing: host=%s action=%s", self.host, action,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "action": action, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "action": action, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "action": action, "error": cli_error}
        return {"host": self.host, "action": action, "success": True}

    # ── Time / NTP Config Tools ─────────────────────────────────

    def set_timezone(self, timezone: str, dry_run: bool = False) -> dict[str, Any]:
        """Set the system timezone (e.g. 'gmt+07')."""
        timezone = _validate_timezone(timezone)
        commands = ["configure terminal", f"clock timezone gmt {timezone}", "end"]
        if dry_run:
            return {"host": self.host, "timezone": timezone,
                    "dry_run": True, "commands": commands}
        logger.info("set_timezone: host=%s timezone=%s", self.host, timezone)
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "timezone": timezone, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "timezone": timezone, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "timezone": timezone, "error": cli_error}
        return {"host": self.host, "timezone": timezone, "success": True}

    def set_clock(self, time: str, date: str, dry_run: bool = False) -> dict[str, Any]:
        """Set the system date and time manually (privileged exec, no config mode)."""
        time = _validate_clock_time(time)
        date = _validate_clock_date(date)
        commands = [f"clock set {time} {date}"]
        if dry_run:
            return {"host": self.host, "time": time, "date": date,
                    "dry_run": True, "commands": commands}
        logger.info("set_clock: host=%s time=%s date=%s", self.host, time, date)
        try:
            with self._connect() as conn:
                output = conn.send_command_timing(
                    commands[0], delay_factor=2, read_timeout=10,
                )
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "time": time, "date": date, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "time": time, "date": date, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "time": time, "date": date, "error": cli_error}
        return {"host": self.host, "time": time, "date": date, "success": True}

    def set_ntp_server(
        self, server: str, action: str = "add", dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add or remove an NTP server (IPv4)."""
        _validate_ipv4(server)
        if action not in ("add", "remove"):
            raise ValueError(f"Invalid action (expected 'add' or 'remove'): {action!r}")
        ntp_cmd = f"server {server}" if action == "add" else f"no server {server}"
        commands = ["configure terminal", "ntp", ntp_cmd, "end"]
        if dry_run:
            return {"host": self.host, "server": server, "action": action,
                    "dry_run": True, "commands": commands}
        logger.info(
            "set_ntp_server: host=%s server=%s action=%s", self.host, server, action,
        )
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "server": server, "action": action,
                    "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "server": server, "action": action,
                    "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "server": server, "action": action,
                    "error": cli_error}
        return {"host": self.host, "server": server, "action": action, "success": True}

    def set_ntp_state(self, enable: bool = True, dry_run: bool = False) -> dict[str, Any]:
        """Enable or disable the NTP service."""
        state = "enabled" if enable else "disabled"
        ntp_cmd = "no disable" if enable else "disable"
        commands = ["configure terminal", "ntp", ntp_cmd, "end"]
        if dry_run:
            return {"host": self.host, "state": state,
                    "dry_run": True, "commands": commands}
        logger.info("set_ntp_state: host=%s state=%s", self.host, state)
        try:
            output = self._send_config(commands)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "state": state, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "state": state, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "state": state, "error": cli_error}
        return {"host": self.host, "state": state, "success": True}

    def save_config(self, dry_run: bool = False) -> dict[str, Any]:
        """Persist the running configuration to startup config (write memory)."""
        commands = ["write memory"]
        if dry_run:
            return {"host": self.host, "dry_run": True, "commands": commands}
        logger.info("save_config: host=%s", self.host)
        try:
            with self._connect() as conn:
                output = conn.send_command_timing(
                    "write memory", delay_factor=2, read_timeout=15,
                )
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}
        cli_error = _extract_cli_error(output)
        if cli_error:
            return {"host": self.host, "error": cli_error}
        return {"host": self.host, "success": True, "saved": True}

    def get_poe_status(
        self, port: str | None = None,
    ) -> dict[str, Any]:
        """Get PoE status — budget summary and per-port power. Optional port filter."""
        capacity_re = re.compile(r"Total is (\d+) mWatts.*?Free is (\d+) mWatts")
        # port admin oper consumed allocated pd_type pd_class pri fault
        port_re = re.compile(
            r"^\s*(\d+/\d+/\d+)\s+(On|Off)\s+(On|Off|Non-PD)\s+"
            r"(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s*(.*?)$",
        )
        logger.info("get_poe_status: host=%s port=%s", self.host, port)
        try:
            with self._connect() as conn:
                raw = conn.send_command("show inline power", read_timeout=20)
        except (NetmikoTimeoutException, NetmikoAuthenticationException) as exc:
            return {"host": self.host, "error": str(exc)}
        except Exception as exc:
            return {"host": self.host, "error": str(exc)}

        cap = capacity_re.search(raw)
        total_mw = int(cap.group(1)) if cap else None
        free_mw = int(cap.group(2)) if cap else None

        ports: list[dict[str, Any]] = []
        for line in raw.splitlines():
            m = port_re.match(line)
            if not m:
                continue
            entry = {
                "port": m.group(1),
                "admin_state": m.group(2),
                "oper_state": m.group(3),
                "power_consumed_mw": int(m.group(4)),
                "power_allocated_mw": int(m.group(5)),
                "pd_type": m.group(6),
                "pd_class": m.group(7),
                "priority": int(m.group(8)),
                "fault": m.group(9).strip() or None,
            }
            if port and entry["port"] != port:
                continue
            ports.append(entry)

        result: dict[str, Any] = {
            "host": self.host,
            "power_capacity_total_mw": total_mw,
            "power_capacity_free_mw": free_mw,
        }
        if port:
            result["port"] = port
            if ports:
                result["status"] = ports[0]
            else:
                result["status"] = None
        else:
            result["ports"] = ports
        return result

    @staticmethod
    def _search(pattern: str, text: str, flags: int = 0) -> str:
        match = re.search(pattern, text, flags)
        return match.group(1).strip() if match else "unknown"
