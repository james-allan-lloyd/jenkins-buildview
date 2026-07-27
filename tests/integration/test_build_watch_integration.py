import asyncio
from pathlib import Path

import httpx
import pytest
from textual.app import App
from textual.widgets import Tree

from buildview.screens.build_watch import ACTIVE_STATES, BuildWatchScreen, _leaf_stages

pytestmark = pytest.mark.integration

CSS_PATH = str(Path(__file__).resolve().parents[2] / "buildview" / "buildview.tcss")


class WatchApp(App):
    CSS_PATH = CSS_PATH

    def __init__(self, url: str, client: httpx.AsyncClient):
        super().__init__()
        self._url = url
        self._client = client

    async def on_mount(self) -> None:
        self.push_screen(BuildWatchScreen(self._url, self._client, allow_back=False))


def _leaf_nodes(node):
    for child in node.children:
        if child.data is not None and not child.data["children"]:
            yield child
        yield from _leaf_nodes(child)


async def _trigger_and_wait_for_completion(client: httpx.AsyncClient, job_path: str) -> None:
    """Trigger a build and block (via plain HTTP polling, no BuildWatchScreen
    involved) until it's finished -- so the test below opens a build that is
    already complete, rather than racing to catch it mid-run."""
    response = await client.post(f"/job/{job_path}/build?delay=0sec")
    queue_url = response.headers["Location"]

    build_url = None
    for _ in range(30):
        queue_data = (await client.get(queue_url + "api/json")).json()
        if "executable" in queue_data:
            build_url = queue_data["executable"]["url"]
            break
        await asyncio.sleep(1)
    assert build_url is not None, "build never left the queue"

    for _ in range(30):
        building = (
            await client.get(build_url + "api/json", params={"tree": "building"})
        ).json()["building"]
        if not building:
            return
        await asyncio.sleep(1)
    raise AssertionError("build never finished")


async def test_opening_an_already_finished_build_only_fetches_the_first_stage(jenkins_url):
    """Regression test for the "don't eagerly download every stage of an
    already-complete build" behaviour: if the build was already finished
    before BuildWatchScreen started following it (as opposed to us watching
    it run live), only the first leaf stage's log should be downloaded up
    front -- the rest are fetched lazily, only if/when the user selects
    them."""
    client = httpx.AsyncClient(
        base_url=jenkins_url,
        auth=("admin", "admin"),
        headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
    )
    try:
        await _trigger_and_wait_for_completion(client, "simple-demo")

        app = WatchApp(jenkins_url + "/job/simple-demo", client)
        async with app.run_test(size=(160, 40)) as pilot:
            screen = app.screen
            tree = screen.query_one("#build_tree", Tree)

            for _ in range(15):
                if len(list(_leaf_nodes(tree.root))) >= 3:
                    break
                await pilot.pause(1)

            leaves = list(_leaf_nodes(tree.root))
            assert len(leaves) == 3

            # Give the fast path a moment to settle, then confirm only the
            # first stage was downloaded -- not all three.
            await pilot.pause(1)
            assert screen.current_stage_id is None  # nothing is "live"
            assert list(screen.log_cache.keys()) == [leaves[0].data["id"]]
            assert screen.viewing_stage_id == leaves[0].data["id"]

            # Selecting a stage that was never eagerly downloaded fetches it
            # lazily, on demand.
            screen.on_tree_node_selected(type("Msg", (), {"node": leaves[2]})())
            for _ in range(15):
                if leaves[2].data["id"] in screen.log_cache:
                    break
                await pilot.pause(1)
            assert leaves[2].data["id"] in screen.log_cache
            assert leaves[1].data["id"] not in screen.log_cache
    finally:
        await client.aclose()


async def test_stage_tailing_and_caching_against_a_live_build(jenkins_url):
    """End-to-end against the real docker/jenkins-test parallel-nested-demo
    job: drives a fresh build through BuildWatchScreen and checks that each
    leaf stage ends up with its own distinct cached log (not one shared,
    ever-growing blob), and that selecting an older stage in the tree shows
    its own snapshot and stops following the live stage."""
    client = httpx.AsyncClient(
        base_url=jenkins_url,
        auth=("admin", "admin"),
        headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
    )
    try:
        await client.post("/job/parallel-nested-demo/build?delay=0sec")

        app = WatchApp(jenkins_url + "/job/parallel-nested-demo", client)
        async with app.run_test(size=(160, 40)) as pilot:
            screen = app.screen
            tree = screen.query_one("#build_tree", Tree)

            for _ in range(30):
                if len(list(_leaf_nodes(tree.root))) >= 7:
                    break
                await pilot.pause(1)

            leaves = list(_leaf_nodes(tree.root))
            assert len(leaves) == 7

            for _ in range(60):
                build = screen.query_one("#build_display").build
                if build is not None and build.get("complete"):
                    break
                await pilot.pause(1)

            build = screen.query_one("#build_display").build
            assert build is not None and build["complete"]

            # Visit every leaf so any that were skipped as "already-finished
            # backlog" when we first attached (see the dedicated backlog
            # test below) get lazily fetched too -- the goal here is that
            # each stage ends up with its own distinct cached log, whichever
            # path populated it.
            for leaf in leaves:
                screen.on_tree_node_selected(type("Msg", (), {"node": leaf})())
                for _ in range(15):
                    if leaf.data["id"] in screen.log_cache:
                        break
                    await pilot.pause(0.5)

            assert set(screen.log_cache.keys()) == {leaf.data["id"] for leaf in leaves}
            assert all(len(text) > 0 for text in screen.log_cache.values())

            first_leaf, last_leaf = leaves[0], leaves[-1]
            screen.on_tree_node_selected(type("Msg", (), {"node": first_leaf})())
            await pilot.pause(0.2)
            assert screen.following_latest is False
            assert screen.viewing_stage_id == first_leaf.data["id"]

            screen.on_tree_node_selected(type("Msg", (), {"node": last_leaf})())
            await pilot.pause(0.2)
            assert screen.viewing_stage_id == last_leaf.data["id"]
    finally:
        await client.aclose()


async def test_opening_an_in_progress_build_skips_the_already_finished_backlog(jenkins_url):
    """Regression test for skipping to the latest node on a build that's
    already partway through: if we open (or re-open) the screen after a
    build has been running for a while -- rather than triggering it
    ourselves and watching from stage one -- any leaf stages that had
    already finished before we started following it should not be
    downloaded up front. Only the currently active stage should be watched
    live; the finished backlog is still fetchable on demand (see the
    already-finished-build test above)."""
    client = httpx.AsyncClient(
        base_url=jenkins_url,
        auth=("admin", "admin"),
        headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
    )
    try:
        await client.post("/job/parallel-nested-demo/build?delay=0sec")

        # Poll with plain HTTP (no BuildWatchScreen involved yet) until a
        # backlog has genuinely formed: at least one finished leaf stage,
        # followed by one that's currently active.
        backlog_stage_id = None
        active_stage_id = None
        for _ in range(30):
            tree = (
                await client.get("/job/parallel-nested-demo/lastBuild/stages/tree")
            ).json()["data"]
            leaves = list(_leaf_stages(tree["stages"]))
            if len(leaves) >= 2 and leaves[-1]["state"] in ACTIVE_STATES:
                backlog_stage_id = leaves[0]["id"]
                active_stage_id = leaves[-1]["id"]
                break
            await asyncio.sleep(1)
        assert backlog_stage_id is not None, "build never formed a backlog before finishing"

        app = WatchApp(jenkins_url + "/job/parallel-nested-demo", client)
        async with app.run_test(size=(160, 40)) as pilot:
            screen = app.screen

            for _ in range(15):
                if screen.current_stage_id is not None:
                    break
                await pilot.pause(0.5)

            assert screen.current_stage_id == active_stage_id
            assert backlog_stage_id not in screen.log_cache

            # The rest of the build should still progress normally from here.
            for _ in range(60):
                build = screen.query_one("#build_display").build
                if build is not None and build.get("complete"):
                    break
                await pilot.pause(1)
            build = screen.query_one("#build_display").build
            assert build is not None and build["complete"]
    finally:
        await client.aclose()
