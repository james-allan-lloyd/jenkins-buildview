from textual.app import App, ComposeResult
from textual.widgets import RichLog

from buildview.console import Console, log_to_rich_text
from rich.text import Text


class ConsoleHostApp(App):
    def compose(self) -> ComposeResult:
        yield Console(client=None)


async def test_append_does_not_crash_on_literal_square_brackets_in_log_text():
    """Regression test: raw Jenkins console output can legitimately contain
    square brackets (e.g. a tool printing a file list like
    "[/path/a.json, /other/path/b.json]"), which used to be misparsed as
    Rich markup and raise a MarkupError."""
    app = ConsoleHostApp()
    async with app.run_test():
        console = app.query_one(Console)
        text = "Files found: [/path/a.json, /other/path/b.json]"
        console.append(text)

        rich_log = console.query_one(RichLog)
        rendered = "".join(line.text for line in rich_log.lines)
        assert text in rendered


def test_it_removes_html_links():
    input_text = "baz <a href=#>foo</a> bar"
    output_text = log_to_rich_text(input_text)

    assert output_text == Text("baz foo bar")


def test_it_handles_named_entities():
    input_text = "baz <a href=#>foo</a>&lt;bar&gt;"
    output_text = log_to_rich_text(input_text)

    assert output_text == Text("baz foo<bar>")


def test_it_handles_style_colors():
    input_text = r"""baz <span style="color: #FF0000;">foo</span> <span style="color: blue">bar</span>"""
    output_text = log_to_rich_text(input_text)

    assert output_text == Text.assemble(
        "baz ", ("foo", "#FF0000"), " ", ("bar", "blue")
    )


def test_it_condenses_whitespace():
    pass


def test_it_handles_nested_style_colors():
    input_text = r"""baz <span style="color: #FF0000;">foo <span style="color: blue">bar</span></span>"""
    output_text = log_to_rich_text(input_text)

    assert output_text == Text.assemble("baz ", ("foo ", "#FF0000"), ("bar", "blue"))


def test_it_handles_nested_arbitrary_tags():
    input_text = r"""baz <span style="color: #FF0000;">foo <a href="#"><span id="nix">bar</span><br/></a></span>"""
    output_text = log_to_rich_text(input_text)

    assert output_text == Text.assemble("baz ", ("foo bar", "#FF0000"))
