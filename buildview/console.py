from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from textual import work
from urllib.parse import urljoin
from rich.text import Text

from html.parser import HTMLParser
from html.entities import name2codepoint


class MyHTMLParser(HTMLParser):
    def __init__(self):
        self.output = Text()
        # self.output_stack = []
        self.style_stack = [None]
        self.tags_since_last_style = 0
        super().__init__()

    def parse_style(self, style_string):
        result = {}
        for item in style_string.split(";"):
            key, _, value = item.partition(":")
            result[key.strip()] = value.strip()

        return result

    def handle_starttag(self, tag, attrs):
        print("Start tag:", tag)
        has_style = False
        for attr in attrs:
            if attr[0] == "style":
                style = self.parse_style(attr[1])
                self.style_stack.append(style["color"])
                has_style = True

        if not has_style:
            self.tags_since_last_style += 1

    def handle_endtag(self, tag):
        print("End tag  :", tag)
        if self.tags_since_last_style == 0:
            del self.style_stack[-1]
        else:
            self.tags_since_last_style -= 1

    def handle_data(self, data):
        print("Data     :", data, self.style_stack[-1])
        import re

        data = re.sub(r"\s+", " ", data)
        self.output.append(data, self.style_stack[-1])

    def handle_comment(self, data):
        print("Comment  :", data)


def log_to_rich_text(input: str) -> str:
    parser = MyHTMLParser()
    parser.feed(input)

    return parser.output


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
                    self.query_one(RichLog).write(
                        log_to_rich_text(log_data["text"]),
                        # expand=True,
                        shrink=True,
                    )
