import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
import keyring as default_keyring_backend

SERVICE_NAME = "jenkins-buildview"


@dataclass
class Credentials:
    server: str
    username: str
    token: str


def config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    config_dir = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return config_dir / "jenkins-buildview" / "config.json"


def build_http_client(server: str, username: str, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=server,
        verify="/etc/ssl/certs/ca-bundle.crt",
        auth=(username, token),
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate, br, zstd",
        },
    )


async def validate(client: httpx.AsyncClient) -> bool:
    try:
        response = await client.get("/whoAmI/api/json", timeout=10)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


class CredentialStore:
    """Persists the Jenkins server/username in a config file and the API
    token in the OS keychain (via `keyring`)."""

    def __init__(self, path: Path | None = None, keyring_backend=None):
        self.path = path or config_path()
        self._keyring = keyring_backend or default_keyring_backend

    def _account(self, server: str, username: str) -> str:
        return f"{server}|{username}"

    def load(self) -> Credentials | None:
        if not self.path.exists():
            return None

        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

        server = data.get("server")
        username = data.get("username")
        if not server or not username:
            return None

        try:
            token = self._keyring.get_password(SERVICE_NAME, self._account(server, username))
        except Exception:
            return None

        if not token:
            return None

        return Credentials(server=server, username=username, token=token)

    def save(self, credentials: Credentials) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"server": credentials.server, "username": credentials.username})
        )
        self._keyring.set_password(
            SERVICE_NAME,
            self._account(credentials.server, credentials.username),
            credentials.token,
        )

    def clear(self) -> None:
        existing = self.load()
        if self.path.exists():
            self.path.unlink()
        if existing is not None:
            try:
                self._keyring.delete_password(
                    SERVICE_NAME, self._account(existing.server, existing.username)
                )
            except Exception:
                pass
