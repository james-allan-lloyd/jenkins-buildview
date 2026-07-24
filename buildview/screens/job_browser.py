from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from buildview.jobs import JobEntry, fetch_jobs, filter_jobs


class JobBrowserScreen(Screen):
    """Lists jobs available on the configured Jenkins server, filterable
    by a search box. Selecting one starts following its builds."""

    BINDINGS = [("q", "app.quit", "Quit")]

    def __init__(self):
        super().__init__()
        self._all_jobs: list[JobEntry] = []

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Select a job to follow", id="browser_title"),
            Input(placeholder="Search jobs...", id="job_search"),
            Label("Loading jobs...", id="browser_status"),
            OptionList(id="job_list"),
            id="browser_form",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#job_search", Input).focus()
        self.load_jobs()

    @work(exclusive=True, group="load_jobs")
    async def load_jobs(self) -> None:
        status = self.query_one("#browser_status", Label)
        try:
            self._all_jobs = await fetch_jobs(self.app.client, self.app.server_url)
        except Exception as exc:
            status.update(f"Failed to load jobs: {exc}")
            return

        if not self._all_jobs:
            status.update("No jobs found")
        else:
            status.update("")
        self._refresh_list(self._all_jobs)

    def _refresh_list(self, jobs: list[JobEntry]) -> None:
        option_list = self.query_one("#job_list", OptionList)
        option_list.clear_options()
        for job in jobs:
            option_list.add_option(Option(job.path, id=job.url))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "job_search":
            self._refresh_list(filter_jobs(self._all_jobs, event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "job_search":
            option_list = self.query_one("#job_list", OptionList)
            if option_list.option_count > 0:
                option = option_list.get_option_at_index(0)
                self.app.handle_job_selected(option.id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.handle_job_selected(event.option.id)
