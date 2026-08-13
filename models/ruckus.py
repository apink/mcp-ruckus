from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ICXDevice:
    host: str
    name: str
    vendor: str = "ruckus"
    role: str = ""
    location: str = ""
    rack: str = ""
    username: str = ""
    password: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "name": self.name,
            "vendor": self.vendor,
            "role": self.role,
            "location": self.location,
        }
