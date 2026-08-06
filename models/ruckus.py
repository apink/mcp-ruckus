from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AccessPoint:
    id: str
    name: str
    status: str
    ip: str
    mac: str
    model: str
    firmware: str
    serial: str
    zone: str
    clients: int
    channel_utilization: float = 0.0
    uptime: str = ""
    mesh_role: str = ""
    location: str = ""
    signal: int = 0


@dataclass
class Zone:
    id: str
    name: str
    description: str
    ap_count: int
    client_count: int
    status: str


@dataclass
class vszEvent:
    id: str
    severity: str
    category: str
    message: str
    timestamp: str
    ap_name: str = ""


@dataclass
class ICXDevice:
    host: str
    name: str
    vendor: str = "ruckus"
    role: str = ""
    location: str = ""
    rack: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "name": self.name,
            "vendor": self.vendor,
            "role": self.role,
            "location": self.location,
        }


class DeviceCredentials:
    def __init__(self, credential_key: str) -> None:
        import os
        self.credential_key = credential_key
        self.username = os.getenv(f"{credential_key}_USER", "")
        self.password = os.getenv(f"{credential_key}_PASS", "")

    def is_available(self) -> bool:
        return bool(self.username and self.password)


class VsZAdapterBase(ABC):
    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def get_ap_status(self) -> list[AccessPoint]:
        pass

    @abstractmethod
    def get_ap_detail(self, ap_id: str) -> AccessPoint | None:
        pass

    @abstractmethod
    def get_zones(self) -> list[Zone]:
        pass

    @abstractmethod
    def get_events(self, minutes: int = 60) -> list[vszEvent]:
        pass

    @abstractmethod
    def get_license(self) -> dict[str, Any]:
        pass
