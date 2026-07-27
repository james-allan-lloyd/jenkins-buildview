import asyncio
import json
from urllib.parse import urlparse

import httpx
import textual
from textual import work
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Tree

from buildview.build_display import BuildDisplay
from buildview.console import Console
from buildview.project_info import ProjectInfo

# Stage/step "state" values (from the pipeline-graph-view stages API) that
# mean a node is still active and its log/status needs to keep being polled.
ACTIVE_STATES = {"queued", "running", "paused"}


def _leaf_stages(stages: list[dict]):
    """Depth-first walk of a stages/tree response, yielding only stages with
    no children -- those are the ones that actually run steps and have their
    own console log. Container stages (nested or parallel parents) are only
    used for display."""
    for stage in stages:
        if stage["children"]:
            yield from _leaf_stages(stage["children"])
        else:
            yield stage


def _find_stage(stages: list[dict], stage_id: str) -> dict | None:
    for stage in stages:
        if stage["id"] == stage_id:
            return stage
        found = _find_stage(stage["children"], stage_id)
        if found is not None:
            return found
    return None


class BuildWatchScreen(Screen):
    """Follows a single Jenkins job, tailing its latest build's console
    output stage by stage."""

    BINDINGS = [
        ("b", "build", "Build"),
        ("escape", "back", "Back to jobs"),
    ]

    url = reactive("")
    latest_build_url = reactive("")

    def __init__(self, url: str, client: httpx.AsyncClient, allow_back: bool = True):
        super().__init__()
        self.client = client
        self.server = None
        self.allow_back = allow_back
        # Raw log text downloaded so far per stage id, so revisiting a stage
        # (or a stage that already finished before the user looked at it)
        # doesn't need to hit the network again.
        self.log_cache: dict[str, str] = {}
        self.current_stage_id: str | None = None
        self.viewing_stage_id: str | None = None
        self.following_latest = True
        self.url = url

    def compose(self) -> ComposeResult:
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

    def action_back(self) -> None:
        if self.allow_back:
            self.app.pop_screen()

    def _find_tree_node(self, node_id: str):
        def walk(node):
            for child in node.children:
                if child.data is not None and child.data["id"] == node_id:
                    return child
                found = walk(child)
                if found is not None:
                    return found
            return None

        return walk(self.query_one("#build_tree", Tree).root)

    def set_current_node_by_id(self, node_id: str) -> None:
        node = self._find_tree_node(node_id)
        if node is not None:
            self.query_one("#build_tree", Tree).move_cursor(node)

    def on_tree_node_selected(self, message):
        stage = message.node.data
        if stage is not None:
            tree = self.query_one("#build_tree")
            self.query_one("#console", Console).push_focus(tree)
            # Selecting the stage that's actually running resumes live
            # tailing; selecting any other (necessarily finished) stage just
            # shows a snapshot of its cached log until the user selects the
            # live stage again.
            self.following_latest = stage["id"] == self.current_stage_id
            self.show_stage_log(stage)

    def show_stage_log(self, stage: dict) -> None:
        self.viewing_stage_id = stage["id"]
        console = self.query_one("#console", Console)
        console.set_title(stage["name"])
        console.clear()
        cached = self.log_cache.get(stage["id"])
        if cached:
            console.append(cached)
        elif stage["id"] != self.current_stage_id:
            # Not cached, and not the stage watch_stage() is already polling
            # -- e.g. a finished stage in an already-complete build that we
            # never eagerly downloaded. Fetch it on demand instead.
            self._fetch_stage_log_once(stage["id"])

    @work()
    async def _fetch_stage_log_once(self, node_id: str) -> None:
        await self._tail_stage_log(node_id)

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

            last_build = job_data.get("lastBuild")
            if last_build is not None and last_build["url"] != self.latest_build_url:
                self.latest_build_url = last_build["url"]
                self.update_build()

            await asyncio.sleep(1)

    async def _fetch_build_view(self) -> dict:
        """Combine the core Jenkins build API (name/status/timing, which the
        pipeline-graph-view plugin doesn't provide) with its stages/tree
        endpoint (stage structure) into the shape BuildDisplay expects."""
        build_response = await self.client.get(
            self.latest_build_url + "/api/json",
            params={"tree": "id,displayName,result,building,timestamp,duration"},
        )
        build_json = build_response.json()

        tree_response = await self.client.get(self.latest_build_url + "/stages/tree")
        tree_json = tree_response.json()["data"]

        status = (
            "IN_PROGRESS"
            if build_json["building"]
            else (build_json["result"] or "UNKNOWN")
        )

        build_view = {
            "id": build_json["id"],
            "name": build_json["displayName"],
            "status": status,
            "startTimeMillis": build_json["timestamp"],
            "stages": tree_json["stages"],
            "complete": tree_json["complete"],
        }
        if not build_json["building"]:
            build_view["endTimeMillis"] = (
                build_json["timestamp"] + build_json["duration"]
            )
        return build_view

    async def _tail_stage_log(self, node_id: str) -> None:
        """Fetch a stage's log (the stages/log endpoint has no offset param,
        so it always returns the full text from the start) and merge in only
        what's new since the last fetch. Streams the response instead of
        buffering it whole, so a large/growing log renders into the console
        progressively as bytes arrive rather than one big blocking write."""
        cached = self.log_cache.get(node_id, "")
        known_length = len(cached)
        seen = 0
        new_pieces = []
        console = self.query_one("#console", Console)

        async with self.client.stream(
            "GET", self.latest_build_url + "/stages/log", params={"nodeId": node_id}
        ) as response:
            async for chunk in response.aiter_text():
                chunk_start = seen
                seen += len(chunk)
                if seen <= known_length:
                    continue
                if chunk_start < known_length:
                    chunk = chunk[known_length - chunk_start :]
                if not chunk:
                    continue
                new_pieces.append(chunk)
                if self.viewing_stage_id == node_id:
                    console.append(chunk)

        if new_pieces:
            self.log_cache[node_id] = cached + "".join(new_pieces)

    async def watch_stage(self, stage: dict) -> None:
        node_id = stage["id"]
        self.current_stage_id = node_id
        if self.following_latest:
            self.show_stage_log(stage)

        while True:
            await self._tail_stage_log(node_id)

            tree_response = await self.client.get(
                self.latest_build_url + "/stages/tree"
            )
            current = _find_stage(tree_response.json()["data"]["stages"], node_id)
            if current is None or current["state"] not in ACTIVE_STATES:
                break

            await asyncio.sleep(1)

    @work(exclusive=True, group="build_update")
    async def update_build(self) -> None:
        try:
            console = self.query_one("#console", Console)
            console.clear()
            console.set_title()
            build_display = self.query_one("#build_display", BuildDisplay)

            while True:
                build = await self._fetch_build_view()
                build_display.build = build
                if len(build["stages"]) > 0:
                    break
                await asyncio.sleep(1)

            self.log_cache = {}
            self.current_stage_id = None
            self.viewing_stage_id = None
            self.following_latest = True

            if build["complete"]:
                # Already-finished build (e.g. we just opened a job whose
                # latest build had already ended, rather than watching it
                # run) -- downloading every stage's log up front is wasted
                # work if the user only ever looks at one or two. Just show
                # the first stage; the rest are fetched lazily on selection.
                leaves = list(_leaf_stages(build["stages"]))
                if leaves:
                    self.set_current_node_by_id(leaves[0]["id"])
                    self.show_stage_log(leaves[0])
                return

            processed_ids: set[str] = set()

            # The build was already partway through when we started
            # following it (e.g. we just opened this screen rather than
            # triggering the build ourselves), so there may already be a
            # backlog of finished stages. Don't replay them one by one --
            # jump straight to the most recent leaf stage and follow that
            # live. The skipped stages are still fetchable on demand if the
            # user selects them (see show_stage_log).
            for stage in list(_leaf_stages(build["stages"]))[:-1]:
                processed_ids.add(stage["id"])

            while True:
                build = await self._fetch_build_view()
                build_display.build = build

                pending = [
                    stage
                    for stage in _leaf_stages(build["stages"])
                    if stage["id"] not in processed_ids
                ]

                if not pending:
                    if build["complete"]:
                        break
                    await asyncio.sleep(1)
                    continue

                stage = pending[0]
                self.set_current_node_by_id(stage["id"])

                await self.watch_stage(stage)
                processed_ids.add(stage["id"])

        except asyncio.CancelledError as e:
            textual.log("Cancelled with " + str(e))
            raise

    async def action_build(self) -> None:
        await self.client.post(self.url + "/build?delay=0sec")
