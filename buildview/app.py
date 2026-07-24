import httpx
import sys
import os
import textual
import asyncio
from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Footer, RichLog, Tree
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
        self.positions = {}

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

    def scroll_console_to_node(self, node):
        position = self.positions.get(node.data["name"])
        self.query_one("#console RichLog", RichLog).scroll_to(0, position, duration=1)

        # def on_tree_node_highlighted(self, message):
        #     if message.node.data is not None:
        #         # self.current_stage_url = urljoin(
        #         #     self.latest_build_url, message.node.data["_links"]["self"]["href"]
        #         # )
        #         if self.focused == self.query_one("#build_tree"):
        #             self.scroll_console_to_node(message.node)
        #

    def set_current_node_by_label(self, label):
        tree = self.query_one("#build_tree", Tree)
        nodes = list(
            filter(
                lambda x: x.data is not None and x.data["name"] == label,
                tree.root.children,
            )
        )
        tree.move_cursor(nodes[0])

    def on_tree_node_selected(self, message):
        if message.node.data is not None:
            tree = self.query_one("#build_tree")
            self.query_one("#console", Console).push_focus(tree)
            self.scroll_console_to_node(message.node)

    def on_console_line_changed(self, message):
        label = None
        # textual.log(message.line)
        sorted_positions = sorted(self.positions.items(), key=lambda p: p[1])
        # textual.log(sorted_positions)
        for position in sorted_positions:
            if label is None or message.line >= position[1]:
                label = position[0]
            else:
                break
        self.set_current_node_by_label(label)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    @work(exclusive=True, exit_on_error=True, group="latest_build")
    async def update_latest_build(self) -> None:
        exiting = False
        while not exiting:
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

            if job_data["lastBuild"]["url"] != self.latest_build_url:
                self.latest_build_url = job_data["lastBuild"]["url"]
                self.update_build()

            await asyncio.sleep(1)

    async def watch_stage(self, stage):
        pending = False
        node_index = 0
        startByte = 0
        while True:
            response = await self.client.get(
                urljoin(self.latest_build_url, stage["_links"]["self"]["href"])
            )
            stage_data = response.json()
            # textual.log(stage_data)
            if node_index >= len(stage_data["stageFlowNodes"]):
                break
            node = stage_data["stageFlowNodes"][node_index]
            pending = True
            status_url = urljoin(self.latest_build_url, node["_links"]["self"]["href"])
            response = await self.client.get(status_url)
            node = response.json()

            log_url = urljoin(
                self.latest_build_url,
                # "pipeline-console/consoleOutput",
                "pipeline-overview/log",
            )
            textual.log(log_url)
            response = await self.client.get(
                log_url,
                params={"nodeId": node["id"], "startByte": startByte},
            )
            textual.log(response)
            # log_data = response.json()["data"]
            text = response.text

            # textual.log(node)
            pending = stage_data["status"] in ["IN_PROGRESS", "PENDING"]
            # startByte = log_data["endByte"]
            self.query_one("#console", Console).append_html(text)

            if pending:
                textual.log("sleeping, waiting for logs")
                await asyncio.sleep(1)
                textual.log("awake")
            else:
                node_index += 1
                startByte = 0

        textual.log("Stage finished: " + stage["name"])

    @work(exclusive=True, group="build_update")
    async def update_build(self) -> None:
        try:
            console = self.query_one("#console", Console)
            console.clear()

            while True:
                response = await self.client.get(
                    self.latest_build_url + "/wfapi/describe"
                )
                build_display = self.query_one("#build_display", BuildDisplay)
                build = response.json()
                build_display.build = build
                await asyncio.sleep(1)
                if len(build["stages"]) > 0:
                    break

            stages: list = build["stages"]
            self.positions = {}
            known_stages = set(s["name"] for s in stages)

            while len(stages):
                stage = stages.pop(0)
                self.positions[stage["name"]] = console.current_position
                console.append("[yellow]--- " + stage["name"] + " ---[/yellow]")

                self.set_current_node_by_label(stage["name"])

                await self.watch_stage(stage)

                response = await self.client.get(
                    self.latest_build_url + "/wfapi/describe"
                )
                build = response.json()
                build_display.build = build
                stages.extend(
                    filter(lambda s: s["name"] not in known_stages, build["stages"])
                )
                known_stages = set(s["name"] for s in build["stages"])
                while build["status"] in ["IN_PROGRESS"] and len(stages) == 0:
                    await asyncio.sleep(1)
                    response = await self.client.get(
                        self.latest_build_url + "/wfapi/describe"
                    )
                    build = response.json()
                    build_display.build = build
                    stages.extend(
                        filter(lambda s: s["name"] not in known_stages, build["stages"])
                    )
                    known_stages = set(s["name"] for s in build["stages"])

        except asyncio.CancelledError as e:
            textual.log("Cancelled with " + str(e))
            raise
        textual.log("Build finished")

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
