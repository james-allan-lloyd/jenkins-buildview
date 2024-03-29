import httpx
import sys
import os
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, Static
from textual.reactive import reactive
from urllib.parse import urljoin
import json

from buildview.build_display import BuildDisplay


class JenkinsBuildViewApp(App):
    """An app to watch Jenkins builds"""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
        ("b", "build", "Build"),
    ]

    url = reactive("")
    latest_build_url = reactive("")
    current_stage_url: str | None = reactive(None)

    def __init__(self, initial_url=None):
        super().__init__()
        auth = (os.environ["USERNAME"], os.environ["TOKEN"])
        self.client = httpx.Client(verify="/etc/ssl/certs/ca-bundle.crt", auth=auth)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Footer()
        display = BuildDisplay(id="build_display")
        display.client = self.client
        yield display

    async def on_mount(self) -> None:
        self.update_latest_build()

    def on_tree_node_selected(self, message):
        if message.node.data is not None:
            log = self.query_one("#step_log")
            log.styles.display = "block"
            self.current_stage_url = urljoin(
                self.latest_build_url, message.node.data["_links"]["self"]["href"]
            )

    async def watch_current_stage_url(self, old, new):
        if new is None:
            log = self.query_one("#step_log")
            log.clear()
        else:
            self.get_logs(new)

    @work
    async def get_logs(self, url):
        data = self.client.get(url).json()
        if url == self.current_stage_url:
            log = self.query_one("#step_log")
            log.clear()

            for node in data["stageFlowNodes"]:
                log_data = self.client.get(
                    urljoin(url, node["_links"]["log"]["href"])
                ).json()
                if "text" in log_data:
                    log.write(log_data["text"])

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    @work(exclusive=True)
    async def update_latest_build(self) -> None:
        job_data = self.client.get(self.url + "/api/json")
        try:
            job_data = job_data.json()
        except json.JSONDecodeError:
            raise Exception(f"Couldn't decode data: {job_data.content}")
        builds = sorted(job_data["builds"], key=lambda x: x["number"])
        self.latest_build_url = builds[-1]["url"]
        self.set_timer(3, self.update_latest_build, name="latest-build-update-timer")

    async def watch_latest_build_url(self, old_url, new_url):
        if len(new_url):
            self.update_build()

    @work(exclusive=True)
    async def update_build(self) -> None:
        build_display = self.query_one("#build_display", Static)

        latest_build_data = self.client.get(
            self.latest_build_url + "/wfapi/describe"
        ).json()
        build_display.build = latest_build_data

        if (
            latest_build_data["status"] == "IN_PROGRESS"
            or latest_build_data["status"] == "NOT_EXECUTED"
        ):
            self.set_timer(2.5, self.update_build, name="build-update-timer")

    def action_quit(self) -> None:
        self.exit()

    async def action_build(self) -> None:
        self.client.post(self.url + "/build?delay=0sec")


def main():
    from dotenv import load_dotenv

    load_dotenv()
    app = JenkinsBuildViewApp()
    app.url = sys.argv[1]
    app.run()


if __name__ == "__main__":
    main()
