import json
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx
import keyring as default_keyring_backend

SERVICE_NAME = "jenkins-buildview"


class StorageBackend(Enum):
    KEYRING = "keyring"
    FALLBACK_FILE = "fallback_file"


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
    token in the OS keychain (via `keyring`).

    Some environments (e.g. headless/SSH-only Linux servers) have no
    Secret Service provider for `keyring` to talk to. When that happens,
    the token falls back to a permission-restricted file alongside the
    config, rather than silently failing to persist at all.
    """

    def __init__(self, path: Path | None = None, keyring_backend=None):
        self.path = path or config_path()
        self._keyring = keyring_backend or default_keyring_backend

    @property
    def token_fallback_path(self) -> Path:
        return self.path.parent / "token"

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

        token = None
        try:
            token = self._keyring.get_password(SERVICE_NAME, self._account(server, username))
        except Exception:
            pass

        if not token and self.token_fallback_path.exists():
            try:
                token = self.token_fallback_path.read_text().strip() or None
            except OSError:
                token = None

        if not token:
            return None

        return Credentials(server=server, username=username, token=token)

    def save(self, credentials: Credentials) -> StorageBackend:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"server": credentials.server, "username": credentials.username})
        )

        try:
            self._keyring.set_password(
                SERVICE_NAME,
                self._account(credentials.server, credentials.username),
                credentials.token,
            )
        except Exception:
            self.token_fallback_path.write_text(credentials.token)
            self.token_fallback_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            return StorageBackend.FALLBACK_FILE

        if self.token_fallback_path.exists():
            self.token_fallback_path.unlink()
        return StorageBackend.KEYRING

    def clear(self) -> None:
        existing = self.load()
        if self.path.exists():
            self.path.unlink()
        if self.token_fallback_path.exists():
            self.token_fallback_path.unlink()
        if existing is not None:
            try:
                self._keyring.delete_password(
                    SERVICE_NAME, self._account(existing.server, existing.username)
                )
            except Exception:
                pass
