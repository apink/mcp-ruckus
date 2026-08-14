"""vSZ access point tools — status, detail, neighbors, filters."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter

logger = logging.getLogger(__name__)

_CH_FIELD_RE = re.compile(r"(\d+)\s*\((\d+)\s*MHz\)", re.IGNORECASE)
_SNR_FIELD_RE = re.compile(r"(\d+)\s*dB", re.IGNORECASE)
_CHANNEL_WIDTH_MAP: dict[int, int | str] = {0: 20, 1: 40, 2: 80, 3: 160, 4: "80+80"}
_BAND_MAP: dict[int, str] = {0: "2.4GHz", 1: "5GHz", 2: "6GHz"}


def _parse_ch(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    m = _CH_FIELD_RE.search(str(raw))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_snr(raw: str | None) -> int | None:
    if raw is None or raw == "":
        return None
    m = _SNR_FIELD_RE.search(str(raw))
    return int(m.group(1)) if m else None


def _normalize_neighbor(nb: dict[str, Any]) -> dict[str, Any]:
    ch24, w24 = _parse_ch(nb.get("channel24G"))
    ch5, w5 = _parse_ch(nb.get("channel5G"))
    ch6_raw = nb.get("channel6G")
    ch6, w6 = _parse_ch(ch6_raw) if ch6_raw else (None, None)

    result: dict[str, Any] = {
        "name": nb.get("deviceName", ""),
        "mac": nb.get("apMac", ""),
        "model": nb.get("model", ""),
    }
    ip = nb.get("ip", "")
    if ip:
        result["ip"] = ip

    if ch24 is not None:
        result["ch_24g"] = ch24
        if w24:
            result["width_24g"] = w24
        result["snr_24g"] = _parse_snr(nb.get("snr24G"))
    if ch5 is not None:
        result["ch_5g"] = ch5
        if w5:
            result["width_5g"] = w5
        result["snr_5g"] = _parse_snr(nb.get("snr5G"))
    if ch6 is not None:
        result["ch_6g"] = ch6
        if w6:
            result["width_6g"] = w6
        result["snr_6g"] = _parse_snr(nb.get("snr6G"))

    return result


def _summarize_ap_neighbors(ap: dict[str, Any], neighbors: list[dict[str, Any]]) -> dict[str, Any]:
    ap_ch24, _ = _parse_ch(ap.get("channel24G"))
    ap_ch5, _ = _parse_ch(ap.get("channel5G"))

    snr24_vals = [n["snr_24g"] for n in neighbors if n.get("snr_24g") and n["snr_24g"] > 0]
    snr5_vals = [n["snr_5g"] for n in neighbors if n.get("snr_5g") and n["snr_5g"] > 0]

    result: dict[str, Any] = {
        "ap": ap.get("deviceName", ""),
        "mac": ap.get("apMac", ""),
        "neighbors": len(neighbors),
    }
    if ap_ch24 is not None:
        result["cur_ch_24g"] = ap_ch24
    if ap_ch5 is not None:
        result["cur_ch_5g"] = ap_ch5
    if snr24_vals:
        result["best_snr_24g"] = max(snr24_vals)
        result["avg_snr_24g"] = round(sum(snr24_vals) / len(snr24_vals), 1)
    if snr5_vals:
        result["best_snr_5g"] = max(snr5_vals)
        result["avg_snr_5g"] = round(sum(snr5_vals) / len(snr5_vals), 1)
    if ap_ch24 is not None:
        co24 = sum(1 for n in neighbors if n.get("ch_24g") == ap_ch24 and n.get("snr_24g", 0) > 0)
        if co24:
            result["co_ch_24g"] = co24
    if ap_ch5 is not None:
        co5 = sum(1 for n in neighbors if n.get("ch_5g") == ap_ch5 and n.get("snr_5g", 0) > 0)
        if co5:
            result["co_ch_5g"] = co5
    return result


async def _fetch_neighbors_batch(
    adapter: VsZRestAdapter, aps: list[dict[str, Any]], max_aps: int
) -> tuple[list[tuple[dict[str, Any], list[dict[str, Any]]]], list[dict[str, Any]]]:
    results: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    errors: list[dict[str, Any]] = []
    aps_slice = aps[:max_aps]

    async def _fetch(ap: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        mac = ap.get("apMac", "") or ap.get("deviceMac", "")
        data = await adapter.get_ap_neighbors(mac)
        nb_list = data.get("list", []) if isinstance(data, dict) and "error" not in data else []
        return ap, nb_list, data

    tasks = [_fetch(ap) for ap in aps_slice]
    gathered: list[tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]] |
                    Exception | None] = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(gathered):
        ap = aps_slice[i]
        name = ap.get("deviceName", "")
        if isinstance(result, Exception):
            errors.append({"ap": name, "error": str(result)})
        else:
            ap_rec, nb_list, data = result
            if isinstance(data, dict) and "error" in data:
                errors.append({"ap": name, "error": data["error"]})
            else:
                results.append((ap_rec, nb_list))

    return results, errors


async def _ap_status(zone_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    logger.info("ap_status: zone=%s limit=%d", zone_id, limit)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return [{"error": result["error"], "detail": result.get("detail", "")}]
    aps = await adapter.get_aps_by_zone(zone_id) if zone_id else await adapter.get_all_aps()
    return [
        {
            "ap_name": ap.get("deviceName", ""),
            "mac": ap.get("deviceMac", ""),
            "serial": ap.get("serialNumber", ""),
            "model": ap.get("model", ""),
            "status": "up" if ap.get("status", "").lower() == "online" else ap.get("status", ""),
            "clients": ap.get("numClients", 0),
            "clients_24g": ap.get("numClients24G", 0),
            "clients_5g": ap.get("numClients5G", 0),
            "location": ap.get("location", ""),
            "zone": ap.get("zoneName", ""),
            "ip": ap.get("deviceIp", ""),
            "channel_24g": ap.get("channel24G", ""),
            "channel_5g": ap.get("channel5G", ""),
            "airtime_24g_pct": ap.get("airtime24G", 0),
            "airtime_5g_pct": ap.get("airtime5G", 0),
            "capacity_pct": ap.get("capacity", 0),
            "capacity_24g_pct": ap.get("capacity24G", 0),
            "capacity_5g_pct": ap.get("capacity50G", 0),
            "noise_24g_dbm": ap.get("noise24G", 0),
            "noise_5g_dbm": ap.get("noise5G", 0),
        }
        for ap in aps[:limit]
    ]


async def _ap_detail(ap_name: str) -> dict[str, Any]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    aps = await adapter.query_ap(ap_name)
    if not aps:
        return {"error": "ap_not_found", "ap_name": ap_name}
    ap = aps[0]
    return {
        "ap_name": ap.get("deviceName", ""),
        "mac": ap.get("deviceMac", ""),
        "serial": ap.get("serialNumber", ""),
        "model": ap.get("model", ""),
        "firmware": ap.get("firmwareVersion", ""),
        "status": ap.get("status", ""),
        "clients": ap.get("numClients", 0),
        "location": ap.get("location", ""),
        "zone": ap.get("zoneName", ""),
        "ip": ap.get("deviceIp", ""),
        "channel_24g": ap.get("channel24G", ""),
        "channel_5g": ap.get("channel5G", ""),
        "airtime_24g": ap.get("airtime24G", 0),
        "airtime_5g": ap.get("airtime5G", 0),
        "uptime": ap.get("uptimeInSec", 0),
        "mesh_role": ap.get("meshRole", ""),
    }


async def _ap_radio_stats(ap_name: str) -> dict[str, Any]:
    logger.info("ap_radio_stats: ap=%s", ap_name)
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}

    aps = await adapter.query_ap(ap_name)
    if not aps:
        return {"error": "ap_not_found", "ap_name": ap_name}
    ap = aps[0]
    mac = ap.get("apMac", "") or ap.get("deviceMac", "") or ""
    if not mac:
        return {"error": "ap_mac_not_found", "ap_name": ap_name}

    data = await adapter.get_ap_detail(mac)
    if "error" in data and data.get("error"):
        return {"error": data["error"], "detail": data.get("detail", "")}
    if not data.get("success", False):
        err = data.get("error") or {}
        return {"error": "apdetail_failed", "detail": err.get("message", "unknown")}

    radios_raw = data.get("data", {}).get("radios", {}).get("list", [])
    radios = []
    for r in radios_raw:
        radio_id = r.get("radioId", "")
        rid_int = int(radio_id) if str(radio_id).isdigit() else -1
        cw_val = r.get("channelWidth")
        cw = _CHANNEL_WIDTH_MAP.get(cw_val) if isinstance(cw_val, int) else None
        radios.append({
            "band": _BAND_MAP.get(rid_int, f"radio_{radio_id}"),
            "radio_id": radio_id,
            "channel": r.get("channel", ""),
            "secondary_channel": r.get("secondaryChannel"),
            "channel_width_mhz": cw,
            "mode": r.get("mode", ""),
            "tx_power": r.get("txPower", ""),
            "chainmask": r.get("chainmask", ""),
            "clients": r.get("numOfAuthorizedClients", 0),
            "noise_floor_dbm": r.get("noiseFloor"),
            "airtime_total_pct": r.get("total"),
            "airtime_busy_pct": r.get("busy"),
            "airtime_rx_pct": r.get("rx"),
            "airtime_tx_pct": r.get("tx"),
            "tx_bytes_gb": round(r.get("txBytes", 0) / 1_073_741_824, 2) if r.get("txBytes") else 0,
            "rx_bytes_gb": round(r.get("rxBytes", 0) / 1_073_741_824, 2) if r.get("rxBytes") else 0,
            "retry": r.get("retry", 0),
            "drop": r.get("drop", 0),
            "background_scan": r.get("backgroundScan"),
            "auto_cell_sizing": r.get("autoCellSizing"),
        })

    return {
        "ap_name": ap.get("deviceName", ap_name),
        "mac": mac,
        "model": ap.get("model", ""),
        "radios": radios,
    }


async def _ap_neighbors(
    ap_name: str | None = None,
    zone_id: str | None = None,
    include_detail: bool = False,
    max_aps: int = 50,
) -> dict[str, Any]:
    logger.info("ap_neighbors: ap=%s zone=%s detail=%s max=%d", ap_name, zone_id, include_detail, max_aps)

    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}

    if ap_name:
        aps = await adapter.query_ap(ap_name)
        if not aps:
            return {"error": "ap_not_found", "ap_name": ap_name}
        ap = aps[0]
        mac = ap.get("apMac", "") or ap.get("deviceMac", "")
        if not mac:
            return {"error": "ap_mac_not_found", "ap_name": ap_name}

        data = await adapter.get_ap_neighbors(mac)
        if "error" in data:
            return {"error": data["error"], "detail": data.get("detail", "")}

        raw_list = data.get("list", [])
        neighbors = [_normalize_neighbor(nb) for nb in raw_list]
        ap_ch24, ap_w24 = _parse_ch(ap.get("channel24G"))
        ap_ch5, ap_w5 = _parse_ch(ap.get("channel5G"))

        resp: dict[str, Any] = {
            "ap": ap.get("deviceName", ap_name),
            "mac": mac,
            "model": ap.get("model", ""),
            "zone": ap.get("zoneName", ""),
            "total_neighbors": len(neighbors),
            "neighbors": neighbors,
        }
        if ap_ch24 is not None:
            resp["cur_ch_24g"] = ap_ch24
            if ap_w24:
                resp["cur_width_24g"] = ap_w24
        if ap_ch5 is not None:
            resp["cur_ch_5g"] = ap_ch5
            if ap_w5:
                resp["cur_width_5g"] = ap_w5
        return resp

    if zone_id:
        aps = await adapter.get_aps_by_zone(zone_id)
        scope_label = f"zone:{zone_id}"
    else:
        aps = await adapter.get_all_aps()
        scope_label = "all"

    if not aps:
        return {"error": "no_aps_found", "scope": scope_label}

    queried = min(len(aps), max_aps)
    batch_results, errors = await _fetch_neighbors_batch(adapter, aps, max_aps)

    ap_entries: list[dict[str, Any]] = []
    for ap_rec, nb_raw in batch_results:
        neighbors = [_normalize_neighbor(nb) for nb in nb_raw]
        if include_detail:
            ap_ch24, _ = _parse_ch(ap_rec.get("channel24G"))
            ap_ch5, _ = _parse_ch(ap_rec.get("channel5G"))
            entry: dict[str, Any] = {
                "ap": ap_rec.get("deviceName", ""),
                "mac": ap_rec.get("apMac", ""),
                "neighbors": neighbors,
            }
            if ap_ch24 is not None:
                entry["cur_ch_24g"] = ap_ch24
            if ap_ch5 is not None:
                entry["cur_ch_5g"] = ap_ch5
            ap_entries.append(entry)
        else:
            ap_entries.append(_summarize_ap_neighbors(ap_rec, neighbors))

    ap_entries.sort(key=lambda x: x.get("neighbors", 0), reverse=True)

    resp: dict[str, Any] = {
        "scope": scope_label,
        "total_aps": len(aps),
        "queried": queried,
        "failed": len(errors),
        "aps": ap_entries,
    }
    if errors:
        resp["errors"] = errors
    return resp


async def _ap_down() -> list[dict[str, Any]]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return [{"error": result["error"], "detail": result.get("detail", "")}]
    all_aps = await adapter.get_all_aps()
    return [
        {
            "ap_name": ap.get("deviceName", ""),
            "status": ap.get("status", ""),
            "mac": ap.get("deviceMac", ""),
            "zone": ap.get("zoneName", ""),
        }
        for ap in all_aps
        if ap.get("status", "").lower() not in ("online", "up", "connected")
    ]


async def _ap_high_client_count(threshold: int = 50) -> list[dict[str, Any]]:
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return [{"error": result["error"], "detail": result.get("detail", "")}]
    all_aps = await adapter.get_all_aps()
    return [
        {"ap_name": ap.get("deviceName", ""), "clients": ap.get("numClients", 0), "zone": ap.get("zoneName", "")}
        for ap in all_aps
        if ap.get("numClients", 0) > threshold
    ]


async def _reboot_ap(ap_name: str, confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {"error": "confirm_required", "detail": "Set confirm=True to reboot the AP"}
    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}
    aps = await adapter.query_ap(ap_name)
    if not aps:
        return {"error": "ap_not_found", "ap_name": ap_name}
    ap = aps[0]
    mac = ap.get("apMac", "") or ap.get("deviceMac", "")
    if not mac:
        return {"error": "ap_mac_not_found", "ap_name": ap_name}
    data = await adapter.reboot_ap(mac)
    if "error" in data:
        return data
    return {
        "ap_name": ap.get("deviceName", ap_name),
        "mac": mac,
        "status": "reboot_initiated",
    }


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def ap_status(zone_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Get AP status from vSZ. Optional zone filter and limit to control response size."""
        return await _ap_status(zone_id=zone_id, limit=limit)

    @mcp.tool()
    async def ap_detail(ap_name: str) -> dict[str, Any]:
        """Get detailed info for a specific AP."""
        return await _ap_detail(ap_name)

    @mcp.tool()
    async def ap_radio_stats(ap_name: str) -> dict[str, Any]:
        """Get real-time per-radio stats (noise, airtime, retry, drop) for an AP.

        Uses SCG apdetail — richer than ap_detail: per-radio noise floor, airtime
        breakdown, retry/drop counters, tx power, chainmask.
        """
        return await _ap_radio_stats(ap_name)

    @mcp.tool()
    async def ap_neighbors(
        ap_name: str | None = None,
        zone_id: str | None = None,
        include_detail: bool = False,
        max_aps: int = 50,
    ) -> dict[str, Any]:
        """Get AP RF neighbor data for channel/power optimization.

        Three scopes: single AP (ap_name), zone (zone_id), or all APs (no filter).
        Single AP always returns full neighbor list. Zone/all return a compact
        summary per AP by default — set include_detail=True for full neighbor data.
        Summary includes co-channel count and best/avg SNR per band.
        """
        return await _ap_neighbors(ap_name=ap_name, zone_id=zone_id, include_detail=include_detail, max_aps=max_aps)

    @mcp.tool()
    async def ap_down() -> list[dict[str, Any]]:
        """Get all APs that are down."""
        return await _ap_down()

    @mcp.tool()
    async def ap_high_client_count(threshold: int = 50) -> list[dict[str, Any]]:
        """Get APs with client count above threshold."""
        return await _ap_high_client_count(threshold)

    @mcp.tool()
    async def reboot_ap(ap_name: str, confirm: bool = False) -> dict[str, Any]:
        """Reboot an access point by name.

        Args:
            ap_name: AP device name (e.g. 'REKT-AP04-41').
            confirm: Must be True to execute (safety latch).
        """
        return await _reboot_ap(ap_name, confirm=confirm)
