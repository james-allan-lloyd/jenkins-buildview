from textual.widgets import Static, Label
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Horizontal

from typing import Optional


class ProjectInfo(Static):
    project = reactive[Optional[dict]](None)

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("Project Name", id="projectName"),
            Label("Server Name", id="serverName"),
        )

    def watch_project(self, _, new):
        projectName = self.query_one("#projectName", Label)
        serverName = self.query_one("#serverName", Label)
        if new is None:
            projectName.update("no project")
            serverName.update("")
        else:
            projectName.update(new["name"])
            serverName.update(new["server"])
