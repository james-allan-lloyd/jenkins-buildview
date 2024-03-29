from textual.reactive import reactive
from textual.widgets import Static, Tree, RichLog
from textual.app import ComposeResult
import arrow


class BuildDisplay(Static):

    build: dict | None = reactive(None)

    def compose(self) -> ComposeResult:
        yield Tree(id="build_tree", label="No build")
        log = RichLog(id="step_log", wrap=True)
        log.styles.display = "none"
        yield log

    def on_mount(self) -> None:
        self.set_interval(
            1, self.update_time_since_build, name="update-time-since-build-timer"
        )

    def update_root_label(self, tree, build):
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

    def update_time_since_build(self) -> None:
        if self.build is not None:
            tree = self.query_one("#build_tree", Tree)
            self.update_root_label(tree, self.build)

    def watch_build(self, old_build, new_build) -> None:
        tree = self.query_one("#build_tree", Tree)
        if new_build:
            self.update_root_label(tree, new_build)
            tree.root.remove_children()
            tree.root.expand()
            for stage in new_build["stages"]:
                label = f"{stage['name']} {stage['status']} {stage['error']['message'] if 'error' in stage else ''}"
                match stage["status"]:
                    case "SUCCESS":
                        label = "[green]" + label
                    case "FAILED":
                        label = "[red]" + label
                    case "IN_PROGRESS":
                        label = "[white bold]" + label

                tree.root.add_leaf(label, stage)
        else:
            tree.root.label = "No build"
