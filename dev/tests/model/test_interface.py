"""The package-interface census reads every part's list and what uses each name."""

import json

from click.testing import CliRunner

from leaf_dev.cli import cli


def test_each_part_reads_its_list_and_its_users():
    """A part whose list or users the census stops finding prints as empty with no
    error, so a name from each part, with a use the tree has, holds the reading."""
    result = CliRunner().invoke(cli, ["interface", "--json"])
    assert result.exit_code == 0, result.output
    parts = {
        part: {row["name"]: row for row in rows}
        for part, rows in json.loads(result.output)["parts"].items()
    }
    used = {
        ("keys", "verbs"): "packages",
        ("elements", "lf-suggestion"): "examples",
        ("protocol", "lf-commands"): "packages",
        ("functions", "whileConnected"): "packages",
        ("styling", "--lf-ink"): "packages",
    }
    for (part, name), group in used.items():
        assert parts[part][name]["users"][group], f"{part} {name} has no {group} use"
    assert parts["protocol"]["lf-action"]["form"] == "event"
    assert parts["styling"]["--lf-ink"]["form"] == "the theme sets it"


def test_a_base_reads_the_same_parts():
    result = CliRunner().invoke(cli, ["interface", "--json", "--base", "HEAD"])
    assert result.exit_code == 0, result.output
    change = json.loads(result.output)
    assert (
        change["added"].keys()
        == change["removed"].keys()
        == {
            "keys",
            "elements",
            "protocol",
            "functions",
            "styling",
        }
    )
