from __future__ import annotations

import asyncio
import time
from typing import Any


async def ping_device(host: str, count: int = 4) -> dict[str, Any]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", str(count), "-W", "2", host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode()

        if proc.returncode != 0:
            return {"host": host, "reachable": False, "error": "unreachable"}

        import re
        rx = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+received", output)
        rtt = re.search(r"min/avg/max(?:/mdev)?\s*=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)", output)

        return {
            "host": host,
            "reachable": True,
            "packets_sent": int(rx.group(1)) if rx else count,
            "packets_received": int(rx.group(2)) if rx else 0,
            "packet_loss_pct": round((1 - int(rx.group(2)) / int(rx.group(1))) * 100) if rx else 100,
            "rtt_min_ms": float(rtt.group(1)) if rtt else None,
            "rtt_avg_ms": float(rtt.group(2)) if rtt else None,
            "rtt_max_ms": float(rtt.group(3)) if rtt else None,
        }
    except asyncio.TimeoutError:
        return {"host": host, "reachable": False, "error": "timeout"}
    except Exception as exc:
        return {"host": host, "reachable": False, "error": str(exc)}


async def check_port(host: str, port: int, timeout: int = 3) -> dict[str, Any]:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"host": host, "port": port, "status": "open"}
    except asyncio.TimeoutError:
        return {"host": host, "port": port, "status": "timeout"}
    except ConnectionRefusedError:
        return {"host": host, "port": port, "status": "closed"}
    except Exception as exc:
        return {"host": host, "port": port, "status": "error", "detail": str(exc)}


async def http_latency(url: str, timeout: int = 5) -> dict[str, Any]:
    import httpx
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        latency = round((time.monotonic() - start) * 1000, 2)
        return {
            "url": url,
            "status_code": resp.status_code,
            "latency_ms": latency,
        }
    except httpx.TimeoutException:
        return {"url": url, "error": "timeout"}
    except Exception as exc:
        return {"url": url, "error": str(exc)}


def register_tools(mcp):
    """Register local connectivity test tools."""

    @mcp.tool()
    async def ping_device(host: str, count: int = 4) -> dict[str, Any]:
        """Ping ICMP from MCP server to host."""
        return await globals()["ping_device"](host, count)

    @mcp.tool()
    async def check_port(host: str, port: int, timeout: int = 3) -> dict[str, Any]:
        """Check TCP port from MCP server."""
        return await globals()["check_port"](host, port, timeout)

    @mcp.tool()
    async def http_latency(url: str, timeout: int = 5) -> dict[str, Any]:
        """Measure HTTP GET latency from MCP server."""
        return await globals()["http_latency"](url, timeout)
