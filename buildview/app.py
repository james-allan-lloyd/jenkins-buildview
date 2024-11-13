import httpx
import asyncio
import sys
import os
import textual
from textual import work, events
from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.reactive import reactive
from urllib.parse import urljoin, urlparse
import json

from buildview.build_display import BuildDisplay
from buildview.console import Console
from buildview.project_info import ProjectInfo


class JenkinsBuildViewApp(App):
    """An app to watch Jenkins builds"""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
        ("b", "build", "Build"),
    ]

    CSS_PATH = "buildview.tcss"

    url = reactive("")
    latest_build_url = reactive("")
    current_stage_url = reactive[str | None](None)

    def __init__(self):
        from dotenv import load_dotenv

        super().__init__()

        load_dotenv()
        auth = (os.environ["USERNAME"], os.environ["TOKEN"])
        self.client = httpx.AsyncClient(
            verify="/etc/ssl/certs/ca-bundle.crt",
            auth=auth,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Encoding": "gzip, deflate, br, zstd",
            },
        )

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Footer()
        yield ProjectInfo(id="project_info")
        yield BuildDisplay(id="build_display", client=self.client)

    def watch_url(self, _, new) -> None:
        if new is not None:
            parsed_url = urlparse(new)
            self.server = parsed_url.hostname
            if parsed_url.port:
                self.server += ":" + str(parsed_url.port)

    async def on_mount(self) -> None:
        self.update_latest_build()

    def on_tree_node_selected(self, message):
        if message.node.data is not None:
            self.current_stage_url = urljoin(
                self.latest_build_url, message.node.data["_links"]["self"]["href"]
            )
            tree = self.query_one("#build_tree")
            self.query_one("#console", Console).push_focus(tree)

    async def watch_current_stage_url(self, _, new):
        self.query_one("#console", Console).set_stage_url(new)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    @work(exclusive=True)
    async def update_latest_build(self) -> None:
        job_data = await self.client.get(
            self.url + "/api/json?tree=lastBuild[url],fullDisplayName"
        )
        try:
            job_data = job_data.json()
        except json.JSONDecodeError:
            raise Exception(f"Couldn't decode data: {job_data.content}")

        project_info = self.query_one("#project_info", ProjectInfo)
        project_info.project = {
            "name": job_data["fullDisplayName"],
            "server": self.server,
        }

        self.latest_build_url = job_data["lastBuild"]["url"]
        self.set_timer(3, self.update_latest_build, name="latest-build-update-timer")

    async def watch_latest_build_url(self, _, new_url):
        if len(new_url):
            self.update_build()

    @work(exclusive=True)
    async def update_build(self) -> None:
        # build_display = self.query_one("#build_display", BuildDisplay)

        currently_watched_build_url = None

        # while True:
        if currently_watched_build_url != self.latest_build_url:
            currently_watched_build_url = self.latest_build_url
            console = self.query_one("#console", Console)
            console.clear()

            response = await self.client.get(self.latest_build_url + "/wfapi/describe")

            build = response.json()
            textual.log(build)

            stages: list = build["stages"]

            while len(stages):
                stage = stages.pop(0)
                console.append("[yellow]--- " + stage["name"] + " ---[/yellow]")

                response = await self.client.get(
                    urljoin(
                        currently_watched_build_url, stage["_links"]["self"]["href"]
                    )
                )
                data = response.json()
                pending = False

                nodes = data["stageFlowNodes"]
                for node in nodes:
                    pending = True
                    while pending:
                        log_url = urljoin(
                            currently_watched_build_url,
                            # node["_links"]["log"]["href"],
                            "pipeline-console/consoleOutput",
                        )
                        # textual.log(log_url)
                        response = await self.client.get(
                            log_url, params={"nodeId": node["id"]}
                        )
                        textual.log(response.json())
                        log_data = response.json()["data"]

                        if node["status"] in ["IN_PROGRESS", "PENDING"]:
                            console.append(log_data.get("text", ""))
                            pending = True
                        else:
                            pending = False
                            console.append(log_data.get("text", ""))

            # response = await self.client.get(url)

            # response = await self.client.get(
            #     self.latest_build_url + "/wfapi/changesets"
            # )

            # build_display.changesets = response.json()

            # textual.log(build_display.build)

            # await asyncio.sleep(1)

        # build_display.build = latest_build_data

        # if latest_build_data["status"] in ["IN_PROGRESS", "NOT_EXECUTED"]:
        #     self.set_timer(2.5, self.update_build, name="build-update-timer")

    async def action_quit(self):
        self.exit()

    async def action_build(self) -> None:
        await self.client.post(self.url + "/build?delay=0sec")


app = JenkinsBuildViewApp()
app.url = sys.argv[1]


def main():
    app.run()


if __name__ == "__main__":
    main()
