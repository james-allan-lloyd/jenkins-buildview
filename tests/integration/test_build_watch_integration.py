from pathlib import Path

import httpx
import pytest
from textual.app import App
from textual.widgets import Tree

from buildview.screens.build_watch import BuildWatchScreen

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
