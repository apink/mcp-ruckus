from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
from paramiko.ssh_exception import SSHException

from models.ruckus import DeviceCredentials, ICXDevice

logger = logging.getLogger(__name__)

# ── Input Validators (security: prevent command injection) ──────────

PORT_RE = re.compile(r"^\d+/\d+/\d+$")
MAC_DOT_RE = re.compile(r"^[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$")
MAC_COLON_RE = re.compile(r"^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}$")
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
IPV6_RE = re.compile(r"^[0-9a-fA-F:]+$")
ROUTE_DEST_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")
ROUTE_DEST_IPV6_RE = re.compile(r"^[0-9a-fA-F:]+(/\d{1,3})?$")

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


class RuckusDeviceDriver:
    CAPABILITIES = ["ssh"]

    def __init__(self, device: ICXDevice) -> None:
        self.device = device
        self.host = device.host
        self.name = device.name
        self.credentials = DeviceCredentials("RUCKUS_ICX")

    def _connect(self) -> ConnectHandler:
        if not self.credentials.is_available():
            raise ValueError("missing RUCKUS_ICX credentials in .env")

        # Retry logic for transient SSH errors
        last_exc = None
        max_retries = 2
        backoff = 1.5

        for attempt in range(max_retries + 1):
            try:
                return ConnectHandler(
                    device_type="ruckus_fastiron",
                    host=self.host,
                    username=self.credentials.username,
                    password=self.credentials.password,
                    timeout=10,
                )
            except (NetmikoTimeoutException, SSHException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    logger.warning(f"SSH attempt {attempt+1}/{max_retries+1} failed for {self.host}: {exc}, retrying...")
                    time.sleep(backoff ** attempt)
                else:
                    raise

        raise last_exc

    @staticmethod
    def _normalize(value: str | None) -> str | None:
        if value is None or value in ("None", "N/A", "", "-"):
            return None
        return value

    def get_device_info(self) -> dict[str, Any]:
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
        try:
            with self._connect() as conn:
                output = conn.send_command("show interface brief", read_timeout=20)
            interfaces: list[dict[str, Any]] = []
            for line in output.splitlines():
                parts = line.strip().split()
                if len(parts) < 6:
                    continue
                port = parts[0]
                if not re.match(r"^\d+/\d+/\d+$|^mgmt\d+$|^ve\d+$", port):
                    continue
                link = parts[1]
                description = " ".join(parts[10:]).strip() if len(parts) > 10 else None
                status = "down" if link.lower() in ("down", "disable") else link.lower()
                interfaces.append({
                    "name": port,
                    "ip_address": "unassigned",
                    "status": status,
                    "protocol": "down" if status == "down" else "up",
                    "speed": self._normalize(parts[4] if len(parts) > 4 else None),
                    "duplex": self._normalize(parts[3] if len(parts) > 3 else None),
                    "state": self._normalize(parts[2] if len(parts) > 2 else None),
                    "description": self._normalize(description),
                })
            return interfaces
        except NetmikoTimeoutException:
            return [{"host": self.host, "error": "timeout"}]
        except Exception as exc:
            return [{"host": self.host, "error": str(exc)}]

    def get_interfaces_down(self) -> list[dict[str, Any]]:
        return [i for i in self.get_interfaces_summary()
                if isinstance(i, dict) and i.get("status") == "down" and "error" not in i]

    def get_interfaces_errors(self) -> list[dict[str, Any]]:
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
                        r"(\d+) second input rate:\s*(\d+)\s+bits/sec,\s*(\d+)\s+packets/sec,\s*([\d.]+)%\s+utilization",
                        output)
                    rate_out = re.search(
                        r"(\d+) second output rate:\s*(\d+)\s+bits/sec,\s*(\d+)\s+packets/sec,\s*([\d.]+)%\s+utilization",
                        output)
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

    def get_ipv6_interfaces(self) -> list[dict[str, Any]]:
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

    @staticmethod
    def _search(pattern: str, text: str, flags: int = 0) -> str:
        match = re.search(pattern, text, flags)
        return match.group(1).strip() if match else "unknown"
