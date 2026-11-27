"""Tests scheduled by the measured cost of their boundary."""

from click.testing import CliRunner
from interact_support import append_carried_log_record, refused_on, response_reference

from leaf.commands import cli as cli_model


def test_an_undeclared_answer_names_what_lets_its_widget_ask(page_dir):
    """An agent writing a widget from memory can leave out the attribute that makes
    it ask, and satisfying the refusal with `--obligation` would leave the widget
    asking nothing. So the refusal names the attribute the widget's registry entry
    asks with."""
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which wording?"}
    )
    shown = '<lf-draft id="wording">\n<pre>\nShip on Monday.</pre></lf-draft>'
    refused = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", response_reference(page_dir, asked)]
        + ["--title", "Wording", "--text", f"Edit it?\n\n{shown}"],
    )

    assert refused_on(refused.stdout).values == {
        "tag": "lf-draft",
        "id": "wording",
        "needs": "`required`",
    }
