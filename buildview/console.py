import textual
from textual import events
from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from textual import work
from urllib.parse import urljoin
from rich.text import Text

from html.parser import HTMLParser


class HtmlToRichParser(HTMLParser):
    def __init__(self):
        self._condense_whitespace = False
        self.output = Text()
        self.style_stack = [None]
        self.tags_since_last_style = 0
        self.current_text = ""
        import re

        self.whitespace_regex = re.compile(r"\s+")
        super().__init__()

    def parse_style(self, style_string):
        result = {}
        for item in style_string.split(";"):
            key, _, value = item.partition(":")
            result[key.strip()] = value.strip()

        return result

    def _flush_current_text(self):
        if len(self.current_text):
            output_text = (
                self.whitespace_regex.sub(" ", self.current_text)
                if self._condense_whitespace
                else self.current_text
            )
            self.output.append(
                output_text,
                self.style_stack[-1],
            )
            self.current_text = ""

    def handle_starttag(self, tag, attrs):
        has_style = False
        for attr in attrs:
            if attr[0] == "style":
                self._flush_current_text()
                style = self.parse_style(attr[1])
                self.style_stack.append(style["color"])
                has_style = True

        if not has_style:
            self.tags_since_last_style += 1

    def handle_endtag(self, tag):
        if self.tags_since_last_style == 0:
            self._flush_current_text()
            del self.style_stack[-1]
        else:
            self.tags_since_last_style -= 1

    def handle_data(self, data):
        self.current_text += data

    def finalized_output(self):
        self._flush_current_text()
        return self.output

    def handle_comment(self, data):
        pass


def log_to_rich_text(input: str) -> str:
    parser = HtmlToRichParser()
    parser.feed(input)

    return parser.finalized_output()


class Console(Static):
    def __init__(self, client):
        self.client = client
        self.current_stage_url = None
        self.current_stage_complete_nodes = set()
        self.current_completed_text = ""
        self.prev_focus = None
        super().__init__(id="console")

    def on_key(self, event: events.Key) -> None:
        if event.name == "escape":
            if self.prev_focus:
                self.prev_focus.focus()

    def push_focus(self, prev_focus):
        self.query_one(RichLog).focus()
        self.prev_focus = prev_focus

    def compose(self) -> ComposeResult:
        log = RichLog(wrap=True, min_width=120, max_lines=None)
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
                self.current_completed_text = ""
                self.current_stage_complete_nodes.clear()
                self.get_logs(self.current_stage_url)

    @work
    async def get_logs(self, url):
        response = await self.client.get(url)
        data = response.json()
        if url == self.current_stage_url:
            partial_text = ""
            pending = False

            for node in data["stageFlowNodes"]:
                if node["id"] not in self.current_stage_complete_nodes:
                    response = await self.client.get(
                        urljoin(url, node["_links"]["log"]["href"])
                    )
                    log_data = response.json()

                    if node["status"] in ["IN_PROGRESS", "PENDING"]:
                        partial_text = log_data.get("text", "")
                        pending = True
                        break
                    else:
                        self.current_completed_text += log_data.get("text", "")
                        self.current_stage_complete_nodes.add(node["id"])

            rich_log = self.query_one(RichLog)
            rich_log.clear()
            rich_log.write(
                log_to_rich_text(self.current_completed_text + partial_text),
                shrink=True,
            )

            if pending:
                self.get_logs(url)
