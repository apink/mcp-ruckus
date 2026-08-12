from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import dotenv
import yaml

from models.ruckus import ICXDevice

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_PATH = BASE_DIR / "inventory" / "devices.yaml"

_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR} with os.environ[VAR], raise if env var not set."""
    if not isinstance(value, str):
        return value

    def _replacer(m: re.Match) -> str:
        var = m.group(1)
        val = os.environ.get(var)
        if val is None:
            raise KeyError(
                f"env var ${var} referenced in devices.yaml not found in .env"
            )
        return val
    return _ENV_VAR_RE.sub(_replacer, value)


def _resolve_credentials(device_dict: dict) -> dict:
    for field in ("username", "password"):
        if field in device_dict and isinstance(device_dict[field], str):
            try:
                device_dict[field] = _resolve_env_vars(device_dict[field])
            except KeyError as exc:
                logger.warning("devices.yaml %s=%s — %s, credential di-reset kosong",
                               device_dict.get("name", device_dict.get("host", "?")),
                               device_dict[field], exc)
                device_dict[field] = ""
    return device_dict


def load_inventory() -> list[ICXDevice]:
    if not INVENTORY_PATH.exists():
        return []
    with INVENTORY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    devices = []
    for item in data.get("devices", []):
        if isinstance(item, dict):
            item = _resolve_credentials(item)
            devices.append(ICXDevice(**item))
        else:
            devices.append(item)
    return devices


def get_device_record(host: str) -> ICXDevice | None:
    for device in load_inventory():
        if device.host == host or device.name == host:
            return device
    return None