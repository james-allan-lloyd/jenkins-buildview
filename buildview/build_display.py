from textual.reactive import reactive
from textual.widgets import Static, Tree
from textual.app import ComposeResult
from textual.containers import Vertical
import arrow

from buildview.console import Console

# Colours for the stages/tree API's "state" values (queued/running/paused
# are all "still active", the rest are terminal).
STAGE_STYLE = {
    "running": "[white bold]",
    "queued": "[white bold]",
    "paused": "[white bold]",
    "success": "[green]",
    "unstable": "[yellow]",
    "failure": "[red]",
    "aborted": "[red]",
}


def _stage_label(stage: dict) -> str:
    return f"{STAGE_STYLE.get(stage['state'], '')}{stage['name']} {stage['state']}"


def _sync_stage_nodes(tree_node, stages: list[dict]) -> None:
    for i, stage in enumerate(stages):
        if i < len(tree_node.children):
            child = tree_node.children[i]
            child.label = _stage_label(stage)
            child.data = stage
        else:
            child = tree_node.add(_stage_label(stage), stage, expand=True)
        _sync_stage_nodes(child, stage["children"])


class BuildDisplay(Static):
    build = reactive[dict | None](None)
    changesets = reactive[dict | None](None)

    def __init__(self, id=None, client=None):
        self.client = client
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        console = Console(client=self.client)
        tree = Tree(id="build_tree", label="No build")
        tree.border_title = "Stages"
        yield Vertical(
            tree,
            console,
        )

    def on_mount(self) -> None:
        self.set_interval(
            1, self.update_time_since_build, name="update-time-since-build-timer"
        )

    def update_root_label(self, tree):
        build = self.build
        if build is None:
            return

        if "endTimeMillis" in build:
            status_time = arrow.get(build["endTimeMillis"]).humanize(only_distance=True)
        elif "startTimeMillis" in build:
            status_time = arrow.get(build["startTimeMillis"]).humanize(only_distance=True)
        else:
            status_time = ""

        tree.root.label = f"Build {build['name']}: {build['status']} {status_time} ago"

        change_desc = []
        if self.changesets is not None:
            for set in self.changesets:
                for commit in set.get("commits", []):
                    summary = commit["message"].partition("\n")[0]
                    change_desc.append(summary)

            change_str = ",".join(change_desc)
            tree.root.label += f" (changes: {change_str})"

    def update_time_since_build(self) -> None:
        if self.build is not None:
            tree = self.query_one("#build_tree", Tree)
            self.update_root_label(tree)

    def watch_changesets(self, _, changesets) -> None:
        tree = self.query_one("#build_tree", Tree)
        self.update_root_label(tree)

    def watch_build(self, old_build, new_build) -> None:
        tree = self.query_one("#build_tree", Tree)
        if new_build:
            if old_build is not None and new_build["id"] != old_build["id"]:
                tree.root.remove_children()
            self.update_root_label(tree)
            tree.root.expand()
            _sync_stage_nodes(tree.root, new_build["stages"])
        else:
            tree.root.label = "No build"
