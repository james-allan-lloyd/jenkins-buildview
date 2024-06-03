from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from textual import work
from urllib.parse import urljoin
from rich.text import Text


class Console(Static):
    def __init__(self, client):
        self.client = client
        self.current_stage_url = None
        super().__init__(id="console")

    def compose(self) -> ComposeResult:
        log = RichLog(wrap=True, min_width=120)
        log.border_title = "Console"
        yield log

    def clear(self):
        self.query_one(RichLog).clear()

    def set_stage_url(self, url):
        if url is None:
            self.query_one(RichLog).clear()
        else:
            if self.current_stage_url != url:
                self.current_stage_url = url
                self.get_logs(self.current_stage_url)

    @work
    async def get_logs(self, url):
        from textual import log

        data = self.client.get(url).json()
        if url == self.current_stage_url:
            self.query_one(RichLog).clear()

            for node in data["stageFlowNodes"]:
                log_data = self.client.get(
                    urljoin(url, node["_links"]["log"]["href"])
                ).json()

                log(log_data)

                if "text" in log_data:
                    import html

                    self.query_one(RichLog).write(
                        Text.from_ansi(html.unescape(log_data["text"])),
                        # expand=True,
                        shrink=True,
                    )
