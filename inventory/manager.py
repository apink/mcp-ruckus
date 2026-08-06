from __future__ import annotations

from pathlib import Path

import yaml

from models.ruckus import ICXDevice

BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_PATH = BASE_DIR / "inventory" / "devices.yaml"


def load_inventory() -> list[ICXDevice]:
    if not INVENTORY_PATH.exists():
        return []
    with INVENTORY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return [ICXDevice(**item) if isinstance(item, dict) else item
            for item in data.get("devices", [])]


def get_device_record(host: str) -> ICXDevice | None:
    for device in load_inventory():
        if device.host == host or device.name == host:
            return device
    return None