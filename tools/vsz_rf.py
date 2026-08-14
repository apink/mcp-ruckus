"""vSZ RF optimization tools — optimize, apply recommendations, manual config."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from fastmcp import FastMCP

from adapters.vsz import VsZRestAdapter
from tools.optimization import _secondary_channel
from tools.optimization import optimize as _optimize_rf
from tools.rf_state import load_optimization, save_optimization

logger = logging.getLogger(__name__)

_FLOOR_RE = re.compile(r"AP(\d+)", re.IGNORECASE)
_CH_FIELD_RE = re.compile(r"(\d+)\s*\((\d+)\s*MHz\)", re.IGNORECASE)

_CHANNEL_WIDTH_MAP: dict[int, int | str] = {0: 20, 1: 40, 2: 80, 3: 160, 4: "80+80"}

_POWER_MAP: dict[str, str] = {
    "max": "Full", "full": "Full",
    "high": "-3dB(1/2)",
    "half": "-6dB(1/4)",
    "quarter": "-9dB(1/8)",
    "min": "Min",
}


def _parse_ch(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    m = _CH_FIELD_RE.search(str(raw))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _extract_floor(ap_name: str) -> str | None:
    m = _FLOOR_RE.search(ap_name)
    return m.group(1) if m else None


def _resolve_power(power: str) -> str:
    p = power.lower().strip()
    return _POWER_MAP.get(p, power)


def _build_radio_payload(
    band: str,
    channel: int,
    channel_width: int,
    power: str | None = None,
    secondary: int | None = None,
) -> dict[str, Any]:
    radio_key = "radio5g" if band == "5g" else "radio24g"
    radio: dict[str, Any] = {
        "channel": channel,
        "channelWidth": channel_width if channel_width > 0 else 20,
        "autoChannelSelection": {"channelSelectMode": "None"},
    }
    if power:
        radio["txPower"] = _resolve_power(power)
    if band == "5g" and secondary is not None and channel_width > 20:
        radio["secondaryChannel"] = secondary
    return {"radioConfig": {radio_key: radio}}


async def _apply_to_aps(
    adapter: VsZRestAdapter,
    ap_targets: list[tuple[str, str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for ap_name, mac, payload in ap_targets:
        if not mac:
            results.append({"ap": ap_name, "status": "skipped", "reason": "MAC not found"})
            continue
        logger.warning("apply_ap: %s (%s) payload=%s", ap_name, mac, payload)
        resp = await adapter.modify_ap(mac, payload)
        if "error" in resp:
            results.append({"ap": ap_name, "mac": mac, "status": "failed", "error": resp["error"]})
        else:
            results.append({"ap": ap_name, "mac": mac, "status": "applied"})
    return results


def _normalize_neighbor(nb: dict[str, Any]) -> dict[str, Any]:
    from tools.vsz_aps import _normalize_neighbor as _norm
    return _norm(nb)


async def _fetch_neighbors_batch(
    adapter: VsZRestAdapter, aps: list[dict[str, Any]], max_aps: int
) -> tuple[list[tuple[dict[str, Any], list[dict[str, Any]]]], list[dict[str, Any]]]:
    from tools.vsz_aps import _fetch_neighbors_batch as _fnb
    return await _fnb(adapter, aps, max_aps)


async def _collect_neighbor_data(
    adapter: VsZRestAdapter,
    aps: list[dict[str, Any]],
    band: str,
    max_aps: int,
) -> dict[str, dict[str, Any]]:
    batch_results, _ = await _fetch_neighbors_batch(adapter, aps, max_aps)
    data: dict[str, dict[str, Any]] = {}

    for ap_rec, nb_raw in batch_results:
        name = ap_rec.get("deviceName", "")
        if not name:
            continue

        mac = ap_rec.get("apMac", "") or ap_rec.get("deviceMac", "")
        ch24, w24 = _parse_ch(ap_rec.get("channel24G"))
        ch5, w5 = _parse_ch(ap_rec.get("channel5G"))

        ap_data: dict[str, Any] = {"neighbors": []}
        if mac:
            ap_data["mac"] = mac
        if ch24 is not None:
            ap_data["ch_24g"] = ch24
            if w24:
                ap_data["width_24g"] = w24
        if ch5 is not None:
            ap_data["ch_5g"] = ch5
            if w5:
                ap_data["width_5g"] = w5

        for nb in nb_raw:
            n = _normalize_neighbor(nb)
            ap_data["neighbors"].append(n)

        data[name] = ap_data

    return data


async def _optimize_wifi_rf(
    zone_id: str | None = None,
    floor: str | None = None,
    ap_names: str | None = None,
    band: str = "5g",
    channel_width: int = 0,
    allow_dfs: bool = False,
    max_aps: int = 100,
    channels: list[int] | None = None,
) -> dict[str, Any]:
    logger.info("optimize_wifi_rf: zone=%s floor=%s aps=%s band=%s width=%d dfs=%s",
                zone_id, floor, ap_names, band, channel_width, allow_dfs)

    if band not in ("5g", "2.4g"):
        return {"error": "invalid_band", "detail": "band must be '5g' or '2.4g'"}

    adapter = VsZRestAdapter()
    result = await adapter.login()
    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}

    if ap_names:
        target_names = [n.strip() for n in ap_names.split(",") if n.strip()]
        aps_data: list[dict[str, Any]] = []
        for name in target_names:
            found = await adapter.query_ap(name)
            if found:
                aps_data.extend(found)
        scope_label = f"aps:{len(target_names)}"
    elif zone_id:
        aps_data = await adapter.get_aps_by_zone(zone_id)
        zone_name = ""
        zones = await adapter.get_zones()
        for z in zones:
            if str(z.get("id", "")) == zone_id:
                zone_name = z.get("name", "")
                break
        scope_label = f"zone:{zone_name or zone_id}"
    else:
        aps_data = await adapter.get_all_aps()
        scope_label = "all"

    if not aps_data:
        return {"error": "no_aps_found", "scope": scope_label}

    if floor:
        aps_data = [ap for ap in aps_data if _extract_floor(ap.get("deviceName", "")) == floor]
        scope_label += f":floor-{floor}"

    if not aps_data:
        return {"error": "no_aps_matched", "scope": scope_label, "floor": floor}

    optimizable_names = {ap.get("deviceName", "") for ap in aps_data if ap.get("deviceName")}
    aps_data = aps_data[:max_aps]

    neighbor_data = await _collect_neighbor_data(adapter, aps_data, band, max_aps)
    if not neighbor_data:
        return {"error": "no_neighbor_data", "scope": scope_label}

    opt_result = await asyncio.to_thread(
        _optimize_rf,
        ap_neighbors_data=neighbor_data,
        band=band,
        channel_width=channel_width,
        allow_dfs=allow_dfs,
        optimizable=optimizable_names,
        channels=channels,
    )

    if "error" in opt_result:
        return opt_result

    ap_mac_map: dict[str, str] = {}
    for ap_name, ap_data in neighbor_data.items():
        mac = ap_data.get("mac", "")
        if mac:
            ap_mac_map[ap_name] = mac
    opt_result["ap_mac_map"] = ap_mac_map

    opt_result["scope"] = scope_label
    opt_result["mode"] = "dry_run"
    opt_result["note"] = "Review recommendations before applying. No config changed."

    opt_id = save_optimization(opt_result)
    opt_result["optimization_id"] = opt_id

    return opt_result


async def _apply_rf_recommendation(
    optimization_id: str,
    ap_names: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {"error": "safety_latch", "detail": "confirm must be True to apply changes"}

    cached = load_optimization(optimization_id)
    if not cached:
        return {"error": "optimization_expired_or_not_found", "optimization_id": optimization_id}

    band = cached.get("band", "5g")
    recs = cached.get("recommendations", [])
    ap_mac_map = cached.get("ap_mac_map", {})

    selected = set(ap_names.split(",")) if ap_names.strip() else None
    to_apply = [r for r in recs if r.get("changed") and (selected is None or r["ap"] in selected)]
    if not to_apply:
        return {"error": "no_aps_to_apply", "detail": "no changed APs match the selection"}

    adapter = VsZRestAdapter()
    login = await adapter.login()
    if "error" in login:
        return {"error": login["error"], "detail": login.get("detail", "")}

    targets: list[tuple[str, str, dict[str, Any]]] = []
    for rec in to_apply:
        ap_name = rec["ap"]
        mac = ap_mac_map.get(ap_name, "")
        payload = _build_radio_payload(
            band=band,
            channel=rec["rec_ch"],
            channel_width=rec["rec_width"],
            power=rec.get("rec_power"),
            secondary=rec.get("rec_secondary"),
        )
        targets.append((ap_name, mac, payload))

    results = await _apply_to_aps(adapter, targets)
    applied = sum(1 for r in results if r["status"] == "applied")
    failed = sum(1 for r in results if r["status"] == "failed")

    return {
        "optimization_id": optimization_id,
        "band": band,
        "total_selected": len(to_apply),
        "applied": applied,
        "failed": failed,
        "results": results,
    }


async def _apply_ap_config(
    zone_id: str | None = None,
    ap_names: str | None = None,
    band: str = "5g",
    channel: int = 0,
    channel_width: int = 0,
    power: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {"error": "safety_latch", "detail": "confirm must be True to apply changes"}

    if channel == 0:
        return {"error": "missing_channel", "detail": "channel is required (e.g. 36, 149, 1)"}

    if band not in ("5g", "2.4g"):
        return {"error": "invalid_band", "detail": "band must be '5g' or '2.4g'"}

    if not zone_id and not ap_names:
        return {"error": "no_target", "detail": "specify zone_id or ap_names"}

    adapter = VsZRestAdapter()
    login = await adapter.login()
    if "error" in login:
        return {"error": login["error"], "detail": login.get("detail", "")}

    if ap_names:
        names = [n.strip() for n in ap_names.split(",") if n.strip()]
        aps_data: list[dict[str, Any]] = []
        for name in names:
            found = await adapter.query_ap(name)
            aps_data.extend(found)
        scope = f"aps:{len(names)}"
    else:
        aps_data = await adapter.get_aps_by_zone(str(zone_id))
        scope = f"zone:{zone_id}"

    if not aps_data:
        return {"error": "no_aps_found", "scope": scope}

    secondary = None
    if band == "5g" and channel_width > 20:
        secondary = _secondary_channel(channel, channel_width)

    payload = _build_radio_payload(
        band=band, channel=channel, channel_width=channel_width,
        power=power, secondary=secondary,
    )

    targets: list[tuple[str, str, dict[str, Any]]] = []
    for ap in aps_data:
        ap_name = ap.get("deviceName", "")
        mac = ap.get("apMac", "") or ap.get("deviceMac", "")
        targets.append((ap_name, mac, dict(payload)))

    results = await _apply_to_aps(adapter, targets)
    applied = sum(1 for r in results if r["status"] == "applied")
    failed = sum(1 for r in results if r["status"] == "failed")

    return {
        "scope": scope,
        "band": band,
        "channel": channel,
        "channel_width": channel_width or 20,
        "power": _resolve_power(power) if power else "unchanged",
        "total_aps": len(aps_data),
        "applied": applied,
        "failed": failed,
        "results": results,
    }


def register_tools(mcp: FastMCP) -> None:
    """Register vSZ RF optimization tools."""
    @mcp.tool()
    async def optimize_wifi_rf(
        zone_id: str | None = None,
        floor: str | None = None,
        ap_names: str | None = None,
        band: str = "5g",
        channel_width: int = 0,
        allow_dfs: bool = False,
        max_aps: int = 100,
        channels: list[int] | None = None,
    ) -> dict[str, Any]:
        """Optimize WiFi RF channel and power (dry-run — no config changes).

        DSATUR + Tabu Search channel assignment, SNR-based power tuning.
        Scope by zone, floor (AP name pattern AP{floor}), or explicit AP list.
        Out-of-scope audible APs are preserved as read-only anchors.

        Args:
            channels: Custom channel pool (overrides allow_dfs). e.g. [36,40,44,48]
                for UNII-1 only, or [149,153,157,161] for UNII-3 without 165.
        """
        return await _optimize_wifi_rf(
            zone_id=zone_id, floor=floor, ap_names=ap_names,
            band=band, channel_width=channel_width, allow_dfs=allow_dfs, max_aps=max_aps,
            channels=channels,
        )

    @mcp.tool()
    async def apply_rf_recommendation(
        optimization_id: str,
        ap_names: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Apply RF optimization recommendations to APs (push to vSZ).

        Requires a prior optimize_wifi_rf run. Uses optimization_id from that result
        to load cached recommendations and PATCH channel/power to each AP.

        Args:
            optimization_id: ID returned by optimize_wifi_rf.
            ap_names: Comma-separated AP names (empty = all changed APs).
            confirm: Must be True to execute.
        """
        return await _apply_rf_recommendation(optimization_id=optimization_id, ap_names=ap_names, confirm=confirm)

    @mcp.tool()
    async def apply_ap_config(
        zone_id: str | None = None,
        ap_names: str | None = None,
        band: str = "5g",
        channel: int = 0,
        channel_width: int = 0,
        power: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Apply manual RF config to APs via vSZ (channel/power override).

        Sets channel, width, and/or TX power on APs. Disables auto channel selection.

        Args:
            zone_id: Apply to ALL APs in this zone.
            ap_names: Comma-separated AP names (overrides zone_id).
            band: '5g' or '2.4g'.
            channel: Target channel (required, e.g. 36, 149, 1).
            channel_width: MHz (0 = default 20).
            power: TX power — label (max/half/quarter/min) or API value (Full, -3dB(1/2)).
            confirm: Must be True to execute.
        """
        return await _apply_ap_config(
            zone_id=zone_id, ap_names=ap_names, band=band,
            channel=channel, channel_width=channel_width, power=power, confirm=confirm,
        )
