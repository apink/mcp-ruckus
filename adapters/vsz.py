from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx
import urllib3

from adapters.config import VsZConfig

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class VsZRestAdapter:
    SESSION_TTL = 600

    def __init__(self, config: VsZConfig | None = None) -> None:
        self.config = config or self._load_from_env()
        self._service_ticket: str | None = None
        self._login_time: float = 0
        self.base_url: str = self.config.base_url()
        self.api_path: str = self.config.api_path()
        self._logged_in = False
        self._domain_id: str | None = None
        self._token_failed = False
        rate_limit = int(os.getenv("VSZ_RATE_LIMIT", "10"))
        self._semaphore = asyncio.Semaphore(rate_limit)
        logger.info("vSZ rate limit: %d concurrent requests", rate_limit)
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(self.config.timeout, connect=10.0),
        )

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.aclose()

    @staticmethod
    def _load_from_env() -> VsZConfig:
        api_version = os.getenv("VSZ_API_VERSION", "v10_0")
        return VsZConfig(
            host=os.getenv("VSZ_HOST", ""),
            port=int(os.getenv("VSZ_PORT", "8443")),
            username=os.getenv("VSZ_USER", ""),
            password=os.getenv("VSZ_PASS", ""),
            api_token=os.getenv("VSZ_API_TOKEN", ""),
            api_version=api_version,
        )

    async def login(self) -> dict[str, Any]:
        logger.info("vSZ login to %s:%s", self.config.host or "unset", self.config.port)
        if not self.config.host:
            return {"error": "vsz_not_configured", "detail": "VSZ_HOST not set in .env"}

        if self.config.api_token and not self._token_failed:
            self._service_ticket = self.config.api_token
            self._logged_in = True
            self._login_time = time.time()
            return {"status": "token_login_ok"}

        if self.config.username and self.config.password:
            try:
                url = f"{self.base_url}{self.api_path}/serviceTicket"
                resp = await self._client.post(
                    url,
                    json={"username": self.config.username, "password": self.config.password},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                self._service_ticket = data.get("serviceTicket", "")
                if self._service_ticket:
                    self._logged_in = True
                    self._login_time = time.time()
                    logger.info("vSZ login successful")
                    return {"status": "login_ok"}
                logger.error("vSZ login: no serviceTicket in response")
                return {"error": "no_serviceTicket", "detail": str(data)}
            except httpx.HTTPError as exc:
                logger.error("vSZ login failed: %s", exc)
                return {"error": "login_failed", "detail": str(exc)}
        return {"error": "no_credentials"}

    async def _ensure_login(self) -> dict[str, Any]:
        if self._service_ticket and (time.time() - self._login_time < self.SESSION_TTL):
            return {"status": "session_reused"}
        return await self.login()

    async def _request(self, path: str, method: str = "GET", payload: dict | None = None,
                       params: dict | None = None) -> dict[str, Any]:
        async with self._semaphore:
            if not self._service_ticket or (time.time() - self._login_time >= self.SESSION_TTL):
                await self._ensure_login()
            if not self._service_ticket:
                return {"error": "not_authenticated"}

            url = f"{self.base_url}{self.api_path}{path}?serviceTicket={self._service_ticket}"
            if params:
                for k, v in params.items():
                    if v:
                        url += f"&{k}={v}"
            try:
                if method == "POST":
                    resp = await self._client.post(
                        url, json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                elif method == "DELETE":
                    resp = await self._client.delete(
                        url,
                        headers={"Content-Type": "application/json"},
                    )
                elif method in ("PUT", "PATCH"):
                    resp = await self._client.request(
                        method, url, json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = await self._client.get(
                        url,
                        headers={"Content-Type": "application/json"},
                    )
                resp.raise_for_status()
                return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401 and self.config.api_token and not self._token_failed:
                    self._token_failed = True
                    self._service_ticket = None
                    await self._ensure_login()
                    if self._service_ticket:
                        return await self._request(path, method=method, payload=payload, params=params)
                logger.error(
                    f"vSZ API {method} {path} HTTP error {exc.response.status_code}: "
                    f"{exc.response.text[:200]}"
                )
                return {"error": f"http_{exc.response.status_code}", "detail": str(exc.response.text)}
            except httpx.HTTPError as exc:
                logger.error(f"vSZ API {method} {path} network error: {exc}")
                return {"error": "network_error", "detail": str(exc)}
            except Exception as exc:
                logger.error(f"vSZ API {method} {path} unexpected error: {exc}")
                return {"error": "unexpected_error", "detail": str(exc)}

    # ── Domain Tools ──────────────────────────────────

    async def get_domains(self) -> list[dict[str, Any]]:
        data = await self._request("/domains")
        if "error" in data:
            logger.error("get_domains failed: %s", data["error"])
            return []
        return data.get("list", [])

    async def _resolve_domain_id(self) -> str | None:
        if self._domain_id is not None:
            return self._domain_id
        domains = await self.get_domains()
        if not domains:
            return None
        self._domain_id = domains[0].get("id")
        if self._domain_id:
            logger.info("Resolved domainId: %s", self._domain_id)
        return self._domain_id

    # ── Zone Tools ────────────────────────────────────

    async def get_all_aps(self) -> list[dict[str, Any]]:
        all_aps: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = {
                "filters": [],
                "fullTextSearch": {},
                "page": page,
                "limit": 1500,
            }
            data = await self._request("/query/ap", method="POST", payload=payload)
            if "error" in data:
                logger.error("get_all_aps failed: %s", data["error"])
                return all_aps if all_aps else []
            aps = data.get("list", [])
            all_aps.extend(aps)
            if not data.get("hasMore", False):
                break
            page += 1
        logger.info("get_all_aps returned %d APs", len(all_aps))
        return all_aps

    async def get_aps_by_zone(self, zone_id: str) -> list[dict[str, Any]]:
        all_aps = await self.get_all_aps()
        if not zone_id:
            return all_aps
        zid = str(zone_id).strip()
        return [
            ap for ap in all_aps
            if ap.get("zoneId") == zid or ap.get("zoneName") == zid
        ]

    async def get_zone_tree(self) -> dict[str, Any]:
        return await self._request("/group/tree/apgroup")

    def _flatten_zone_tree(self, node: dict[str, Any], zones: list[dict[str, Any]],
                           domain_name: str = "", domain_id: str = "",
                           domain_type: str = "") -> None:
        ntype = node.get("type", "")
        if ntype == "ZONE":
            zones.append({
                "id": node.get("zoneUUID") or node.get("id", ""),
                "name": node.get("zoneName") or node.get("text", ""),
                "description": "",
                "domainId": node.get("domainUUID", domain_id),
                "domainName": node.get("domainName", domain_name),
                "domainType": node.get("domainType", domain_type),
                "apCount": node.get("allCount", 0),
                "onlineCount": node.get("onlineCount", 0),
                "offlineCount": node.get("offlineCount", 0),
                "status": node.get("status", "active"),
            })
        dom_name = node.get("domainName") or domain_name
        dom_id = node.get("domainUUID") or domain_id
        dom_type = node.get("domainType") or domain_type
        for child in node.get("children", []):
            self._flatten_zone_tree(child, zones, dom_name, dom_id, dom_type)

    async def get_zones(self) -> list[dict[str, Any]]:
        tree = await self.get_zone_tree()
        if "error" not in tree:
            zones: list[dict[str, Any]] = []
            self._flatten_zone_tree(tree, zones)
            logger.info("get_zones returned %d zones (from group tree)", len(zones))
            return zones

        domain_id = await self._resolve_domain_id()
        params = {"domainId": domain_id} if domain_id else None
        data = await self._request("/rkszones", params=params)
        if "error" not in data:
            zones = data.get("list", [])
            logger.info("get_zones returned %d zones (from /rkszones)", len(zones))
            return zones

        aps = await self.get_all_aps()
        if not aps:
            logger.error("get_zones: all discovery methods exhausted")
            return []

        zones_map: dict[str, dict[str, Any]] = {}
        for ap in aps:
            zid = ap.get("zoneId")
            if not zid:
                continue
            if zid not in zones_map:
                zones_map[zid] = {
                    "id": zid,
                    "name": ap.get("zoneName") or "",
                    "description": "",
                    "apCount": 0,
                    "clientCount": 0,
                    "status": "active",
                }
            zones_map[zid]["apCount"] += 1
            zones_map[zid]["clientCount"] += ap.get("numClients", 0)

        for zid in zones_map:
            if zones_map[zid]["name"]:
                continue
            zone_detail = await self._request(f"/rkszones/{zid}")
            if "error" not in zone_detail:
                zones_map[zid]["name"] = zone_detail.get("name", "")
                zones_map[zid]["description"] = zone_detail.get("description", "")

        zones = list(zones_map.values())
        logger.info("get_zones returned %d zones (from AP data)", len(zones))
        return zones

    async def query_ap(self, search_term: str) -> list[dict[str, Any]]:
        payload = {"fullTextSearch": {"type": "AND", "value": search_term}}
        data = await self._request("/query/ap", method="POST", payload=payload)
        return data.get("list", [])

    async def get_ap_detail(self, mac: str) -> dict[str, Any]:
        if not self._service_ticket or (time.time() - self._login_time >= self.SESSION_TTL):
            await self._ensure_login()
        if not self._service_ticket:
            return {"error": "not_authenticated"}

        url = f"{self.base_url}/wsg/api/scg/aps/{mac}/apdetail?serviceTicket={self._service_ticket}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                logger.error("SCG apdetail %s non-JSON response: %s", mac, resp.text[:200])
                return {"error": "invalid_response", "detail": resp.text[:200]}
        except httpx.HTTPStatusError as exc:
            logger.error("SCG apdetail %s HTTP error %s: %s", mac, exc.response.status_code, exc.response.text[:200])
            return {"error": f"http_{exc.response.status_code}", "detail": str(exc.response.text)}
        except httpx.HTTPError as exc:
            logger.error("SCG apdetail %s network error: %s", mac, exc)
            return {"error": "network_error", "detail": str(exc)}
        except Exception as exc:
            logger.error("SCG apdetail %s unexpected error: %s", mac, exc)
            return {"error": "unexpected_error", "detail": str(exc)}

    # ── Client Tools ──────────────────────────────────

    async def query_client(self, client_id: str) -> dict[str, Any]:
        payload = {"fullTextSearch": {"type": "AND", "value": client_id}}
        return await self._request("/query/client", method="POST", payload=payload)

    async def query_clients_by_ids(self, client_ids: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for cid in client_ids:
            data = await self.query_client(cid)
            if data.get("totalCount", 0) > 0:
                results.append(data)
            else:
                results.append({"client_id": cid, "error": "Not found"})
        return results

    # ── License ───────────────────────────────────────

    async def get_license(self) -> dict[str, Any]:
        return await self._request("/license")

    # ── WLAN / SSID ────────────────────────────────────

    async def get_wlans_by_zone(self, zone_id: str) -> list[dict[str, Any]]:
        data = await self._request(f"/rkszones/{zone_id}/wlans")
        return data.get("list", [])

    async def get_wlan_detail(self, zone_id: str, wlan_id: str) -> dict[str, Any]:
        return await self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")

    async def get_radius_servers(self, zone_id: str, for_accounting: bool | None = None) -> list[dict[str, Any]]:
        path = f"/rkszones/{zone_id}/aaa/radius"
        params = {}
        if for_accounting is not None:
            params["forAccounting"] = str(for_accounting).lower()
        data = await self._request(path, params=params if params else None)
        return data.get("list", [])

    async def create_wlan(self, zone_id: str, payload: dict[str, Any], wlan_type: str = "standard") -> dict[str, Any]:
        if not self._service_ticket or (time.time() - self._login_time >= self.SESSION_TTL):
            await self._ensure_login()
        if not self._service_ticket:
            return {"error": "not_authenticated"}

        if wlan_type == "standard8021X":
            url = (
                f"{self.base_url}{self.api_path}/rkszones/{zone_id}/wlans/"
                f"standard8021X?serviceTicket={self._service_ticket}"
            )
        else:
            url = f"{self.base_url}{self.api_path}/rkszones/{zone_id}/wlans?serviceTicket={self._service_ticket}"
        try:
            resp = await self._client.post(
                url, json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            try:
                data = resp.json()
                logger.info("create_wlan: zone=%s -> id=%s", zone_id, data.get("id", "?"))
                return {"status": "ok", "id": data.get("id", ""), "name": data.get("name", ""),
                        "http_code": resp.status_code}
            except ValueError:
                return {"status": "ok", "http_code": resp.status_code}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401 and self.config.api_token and not self._token_failed:
                self._token_failed = True
                self._service_ticket = None
                await self._ensure_login()
                if self._service_ticket:
                    return await self.create_wlan(zone_id, payload, wlan_type=wlan_type)
            logger.error("create_wlan HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
            return {"error": f"http_{exc.response.status_code}", "detail": exc.response.text[:500]}
        except httpx.HTTPError as exc:
            logger.error("create_wlan network error: %s", exc)
            return {"error": "network_error", "detail": str(exc)}

    # ── AP Neighbors ──────────────────────────────────

    async def get_ap_neighbors(self, mac: str) -> dict[str, Any]:
        return await self._request(f"/aps/{mac}/apNeighbors")

    async def modify_ap(self, ap_mac: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._service_ticket or (time.time() - self._login_time >= self.SESSION_TTL):
            await self._ensure_login()
        if not self._service_ticket:
            return {"error": "not_authenticated"}

        url = f"{self.base_url}{self.api_path}/aps/{ap_mac}?serviceTicket={self._service_ticket}"
        try:
            resp = await self._client.patch(
                url, json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            if resp.text:
                try:
                    return resp.json()
                except ValueError:
                    pass
            return {"status": "ok", "http_code": resp.status_code}
        except httpx.HTTPStatusError as exc:
            logger.error("modify_ap %s HTTP %s: %s", ap_mac, exc.response.status_code, exc.response.text[:200])
            return {"error": f"http_{exc.response.status_code}", "detail": str(exc.response.text[:500])}
        except httpx.HTTPError as exc:
            logger.error("modify_ap %s network error: %s", ap_mac, exc)
            return {"error": "network_error", "detail": str(exc)}
        except Exception as exc:
            logger.error("modify_ap %s unexpected error: %s", ap_mac, exc)
            return {"error": "unexpected_error", "detail": str(exc)}

    # ── Rogue Client ────────────────────────────────────

    async def query_rogue_clients(
        self,
        domain_id: str | None = None,
        zone_id: str | None = None,
        rogue_mac: str | None = None,
        ssid: str | None = None,
        rogue_type: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        filters: list[dict[str, Any]] = []
        extra_filters: list[dict[str, Any]] = []

        if domain_id:
            filters.append({"type": "DOMAIN", "value": domain_id, "operator": "eq"})
        if zone_id:
            extra_filters.append({"type": "ZONE", "value": zone_id, "operator": "eq"})
        if rogue_mac:
            extra_filters.append({"type": "RogueMac", "value": rogue_mac, "operator": "eq"})
        if ssid:
            extra_filters.append({"type": "SSID", "value": ssid, "operator": "eq"})
        if rogue_type:
            extra_filters.append({"type": "Type", "value": rogue_type, "operator": "eq"})

        body: dict[str, Any] = {
            "filters": filters,
            "page": page,
            "limit": limit,
        }
        if extra_filters:
            body["extraFilters"] = extra_filters

        return await self._request("/rogueclients/query", method="POST", payload=body)

    async def get_alert_events(
        self,
        limit: int = 20,
        severity: str | None = None,
        category: str | None = None,
        hours_back: int | None = None,
        text_search: str | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        import time as _time

        extra_filters: list[dict[str, Any]] = []
        if severity:
            extra_filters.append({"type": "SEVERITY", "value": severity, "operator": "eq"})
        if category:
            extra_filters.append({"type": "CATEGORY", "value": category, "operator": "eq"})

        body: dict[str, Any] = {
            "filters": [],
            "sortInfo": {"sortColumn": "insertionTime", "dir": "DESC"},
            "page": page,
            "limit": limit,
        }
        if extra_filters:
            body["extraFilters"] = extra_filters

        if hours_back:
            now_ms = int(_time.time() * 1000)
            start_ms = now_ms - hours_back * 3600 * 1000
            body["extraTimeRange"] = {
                "start": start_ms,
                "end": now_ms,
                "field": "insertionTime",
            }

        if text_search:
            body["fullTextSearch"] = {"type": "AND", "value": text_search}

        return await self._request("/alert/event/list", method="POST", payload=body)

    # ── WLAN State ─────────────────────────────────────

    async def enable_disable_wlan(self, zone_id: str, wlan_id: str, enabled: bool) -> dict[str, Any]:
        path = f"/rkszones/{zone_id}/wlans/{wlan_id}/enableOrDisable"
        return await self._request(path, method="POST", payload={"enable": enabled})

    # ── AP Reboot ──────────────────────────────────────

    async def reboot_ap(self, mac: str) -> dict[str, Any]:
        return await self._request(f"/aps/{mac}/reboot", method="PUT")

    # ── Client Disconnect ───────────────────────────────

    async def disconnect_client(self, mac: str, ap_mac: str) -> dict[str, Any]:
        return await self._request(
            "/clients/disconnect", method="POST",
            payload={"mac": mac, "apMac": ap_mac},
        )

    # ── Client Traffic Queries ──────────────────────────

    async def query_clients(self, limit: int = 100, page: int = 1,
                            ssid: str | None = None, ap_name: str | None = None
                            ) -> dict[str, Any]:
        extra_filters: list[dict[str, Any]] = []
        if ssid:
            extra_filters.append({"type": "SSID", "value": ssid, "operator": "eq"})
        if ap_name:
            extra_filters.append({"type": "AP_NAME", "value": ap_name, "operator": "eq"})
        body: dict[str, Any] = {"filters": [], "limit": limit, "page": page}
        if extra_filters:
            body["extraFilters"] = extra_filters
        return await self._request("/query/client", method="POST", payload=body)

    # ── WLAN Modify ─────────────────────────────────────

    _WLAN_UNWRITABLE = frozenset({
        "id", "zoneId", "zoneVersion", "type", "oweTransWlanId", "hessid",
        "status", "wlanGroupId", "domainId", "createdTime", "insertionTime",
        "domainName", "zoneName", "atfConfig", "configStatus",
        "hotspotWalledGardenName", "installationStatus", "lastModifiedTime",
        "mpskUsage", "operationStatus", "operatorName", "profileTypeId",
        "regType", "ssidName", "venuerId", "wlanType",
    })

    _WLAN_MIN_FIELDS = frozenset({
        "maxAllowedRA", "multicastDownlinkRateLimit",
        "multicastUplinkRateLimit", "raInterval",
    })

    @classmethod
    def _clean_wlan_body(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                if v is None:
                    continue
                if isinstance(v, (int, float)) and v == 0 and k in cls._WLAN_MIN_FIELDS:
                    out[k] = 1
                elif isinstance(v, dict):
                    cleaned = cls._clean_wlan_body(v)
                    if cleaned:
                        out[k] = cleaned
                elif isinstance(v, list):
                    out[k] = [cls._clean_wlan_body(i) for i in v]
                else:
                    out[k] = v
            return out
        return obj

    async def modify_wlan(self, zone_id: str, wlan_id: str,
                          updates: dict[str, Any]) -> dict[str, Any]:
        current = await self._request(f"/rkszones/{zone_id}/wlans/{wlan_id}")
        if "error" in current:
            return current
        cleansed = {k: v for k, v in current.items()
                    if k not in self._WLAN_UNWRITABLE}
        cleansed = self._clean_wlan_body(cleansed)
        cleansed.update(updates)
        return await self._request(
            f"/rkszones/{zone_id}/wlans/{wlan_id}",
            method="PUT", payload=cleansed)

    # ── Controller Stats ────────────────────────────────

    async def controller_stats(self) -> dict[str, Any]:
        data = await self._request("/controller")
        if "error" in data:
            return data
        controllers = data.get("list", [])
        summary = []
        for c in controllers:
            uptime_days = round((c.get("uptimeInSec", 0) or 0) / 86400, 1)
            summary.append({
                "name": c.get("name", ""),
                "model": c.get("model", ""),
                "version": c.get("version", ""),
                "ap_version": c.get("apVersion", ""),
                "role": c.get("clusterRole", ""),
                "uptime_days": uptime_days,
                "control_ip": c.get("controlIp", ""),
                "serial": c.get("serialNumber", ""),
            })
        return {
            "total_nodes": data.get("totalCount", 0),
            "nodes": summary,
            "note": "CPU/memory/storage not exposed by vSZ public API",
        }
