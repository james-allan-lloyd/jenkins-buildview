from textual.widgets import Static, Label
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Horizontal

from typing import Optional


class ProjectInfo(Static):
    DEFAULT_CSS = """
    ProjectInfo {
        height: 3;
        width: 1fr;
        dock: top;
        border: solid white;
    }
    """
    project: Optional[dict] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label("Project Name", id="projectName"),
            Label("Server Name", id="serverName"),
        )

    def watch_project(self, old, new):
        projectName = self.query_one("#projectName")
        serverName = self.query_one("#serverName")
        if new is None:
            projectName.update("no project")
            serverName.update("")
        else:
            projectName.update(new["name"])
            serverName.update(new["server"])
