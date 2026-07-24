import os
import sys
from urllib.parse import urlparse

import httpx
from textual.app import App

from buildview.auth import CredentialStore, Credentials, StorageBackend, build_http_client, validate
from buildview.screens.build_watch import BuildWatchScreen
from buildview.screens.job_browser import JobBrowserScreen
from buildview.screens.login import LoginScreen


class JenkinsBuildViewApp(App):
    """An app to watch Jenkins builds"""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]

    CSS_PATH = "buildview.tcss"

    def __init__(self, direct_url: str | None = None):
        super().__init__()
        self.direct_url = direct_url
        self.credential_store = CredentialStore()
        self.client: httpx.AsyncClient | None = None
        self.server_url: str | None = None

    async def on_mount(self) -> None:
        if self.direct_url:
            await self._start_direct_mode()
        else:
            await self._start_login_flow()

    async def _start_direct_mode(self) -> None:
        """Legacy behaviour: watch a single job URL passed on the command
        line, authenticating from USERNAME/TOKEN in the environment/.env."""
        from dotenv import load_dotenv

        load_dotenv()
        username = os.environ["USERNAME"]
        token = os.environ["TOKEN"]
        parsed = urlparse(self.direct_url)
        server = f"{parsed.scheme}://{parsed.netloc}"

        self.server_url = server
        self.client = build_http_client(server, username, token)
        self.push_screen(BuildWatchScreen(self.direct_url, self.client, allow_back=False))

    async def _start_login_flow(self) -> None:
        credentials = self.credential_store.load()
        if credentials is not None:
            client = build_http_client(credentials.server, credentials.username, credentials.token)
            if await validate(client):
                self.client = client
                self.server_url = credentials.server
                self.push_screen(JobBrowserScreen())
                return
            await client.aclose()

        self.push_screen(LoginScreen())

    def handle_login(self, credentials: Credentials, client: httpx.AsyncClient) -> None:
        self.client = client
        self.server_url = credentials.server
        try:
            backend = self.credential_store.save(credentials)
        except Exception as exc:
            self.notify(
                f"{exc}\n\nYou'll need to log in again next time.",
                title="Could not save credentials",
                severity="warning",
                timeout=10,
            )
        else:
            if backend is StorageBackend.FALLBACK_FILE:
                self.notify(
                    "No OS keychain available here (common on headless/SSH-only "
                    f"servers) — token saved to {self.credential_store.token_fallback_path} "
                    "instead, readable only by you.",
                    title="Credentials saved without OS keychain",
                    severity="information",
                    timeout=8,
                )
        self.pop_screen()
        self.push_screen(JobBrowserScreen())

    def handle_job_selected(self, job_url: str) -> None:
        self.push_screen(BuildWatchScreen(job_url, self.client))

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    async def action_quit(self) -> None:
        self.exit()


app = JenkinsBuildViewApp(direct_url=sys.argv[1] if len(sys.argv) > 1 else None)


def main():
    app.run()


if __name__ == "__main__":
    main()
