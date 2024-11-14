from textual.reactive import reactive
from textual.widgets import Static, Tree
from textual.app import ComposeResult
from textual.containers import Vertical
import arrow

from buildview.console import Console


class BuildDisplay(Static):
    DEFAULT_CSS = """
    BuildDisplay {
        width: 1fr;
        height: 1fr;
    }
    """

    build = reactive[dict | None](None)
    changesets = reactive[dict | None](None)

    def __init__(self, id=None, client=None):
        self.client = client
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        console = Console(client=self.client)
        yield Vertical(
            Tree(id="build_tree", label="No build"),
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
            status_time = arrow.get(build["endTimeMillis"]).humanize(
                only_distance=True
            )  # startTimeMillis, durationMills
        elif "startTimeMillis" in build:
            status_time = arrow.get(build["endTimeMillis"]).humanize(
                only_distance=True
            )  # startTimeMillis, durationMills
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
            for i, stage in enumerate(new_build["stages"]):
                label = f"{stage['name']} {stage['status']} {stage['error']['message'] if 'error' in stage else ''}"
                match stage["status"]:
                    case "SUCCESS":
                        label = "[green]" + label
                    case "FAILED":
                        label = "[red]" + label
                    case "IN_PROGRESS":
                        label = "[white bold]" + label

                if i < len(tree.root.children):
                    tree.root.children[i].label = label
                else:
                    tree.root.add_leaf(label, stage)
        else:
            tree.root.label = "No build"
