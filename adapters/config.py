from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VsZConfig:
    host: str
    port: int = 8443
    username: str = ""
    password: str = ""
    api_token: str = ""
    api_version: str = "v10_0"
    verify_ssl: bool = False
    timeout: int = 30

    def base_url(self) -> str:
        protocol = "https" if self.port == 8443 else "http"
        return f"{protocol}://{self.host}:{self.port}"

    def api_path(self) -> str:
        return f"/wsg/api/public/{self.api_version}"
