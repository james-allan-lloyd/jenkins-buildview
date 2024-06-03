from buildview.console import log_to_rich_text
from rich.text import Text


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
