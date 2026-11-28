"""The package-interface census reads every part's list and what uses each name."""

import json
import re

from click.testing import CliRunner

from leaf_dev import ROOT
from leaf_dev.cli import cli
from leaf_dev.commands.interface import PARTS, Tree, census, spans
from leaf_dev.styling_names import REFERENCES


def test_each_part_reads_its_list_and_its_users():
    """A part whose list or users the census stops finding prints as empty with no
    error, so a name from each part, with a use the tree has where one does, holds the
    reading. A mark only `module-input.md` gives holds the reading of every reference's
    marks, and a function from a module beside `widget-api.js` the reading of every
    module `$public-modules` admits."""
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
        ("protocol", "data-lf-focus-visible"): "packages",
        ("contracts", "text-document"): "examples",
        ("modules", "/vendor/lit.js"): "packages",
        ("functions", "whileConnected"): "packages",
        ("functions", "defineWidget"): "packages",
        ("vendored", "html"): "packages",
        ("styling", "--lf-ink"): "packages",
    }
    for (part, name), group in used.items():
        assert parts[part][name]["users"][group], f"{part} {name} has no {group} use"
    assert parts["protocol"]["lf-action"]["form"] == "event"
    assert parts["functions"]["defineWidget"]["form"] == "effect-widget.js"
    assert parts["parts"]["card"]["form"] == "Leaf's chrome"
    assert parts["styling"]["--lf-ink"]["form"] == "the theme sets it"
    assert (
        parts["contracts"]["choice"]["form"] == "default declares it; output, reference"
    )


def test_the_protocol_index_lists_each_protocol_name_a_reference_gives():
    """The census reads the widget protocol's members and events from its index in
    `module-widgets.md`, so a name another reference describes and the index
    leaves out is one the census misses. A reference gives such a name in code, by a
    shape that says what it is: a member Leaf reads off an element, `lf` then a
    capital, or an event Leaf's runtime makes or hears whose name holds a hyphen, as
    Leaf's own events' names do and the platform's never do."""
    tree = Tree.working()
    indexed = census(tree)["protocol"]
    missing = sorted(
        f"{path.name}: {name}"
        for path in (ROOT / REFERENCES).glob("*.md")
        for span in spans(path.read_text())
        # A mark's `dataset` property is the mark, which the census reads by its name
        # from every reference.
        for name in re.findall(
            r"(?<![\w$-])(?<!dataset\.)(lf[A-Z]\w*|[a-z]+(?:-[a-z]+)+)", span
        )
        if re.fullmatch(r"lf[A-Z]\w*", name) or name in tree.heard
        if name not in indexed
    )
    assert not missing, (
        "these references give a protocol name the index in module-widgets.md "
        "leaves out; list each there, pointing at the section that describes it:\n  "
        + "\n  ".join(missing)
    )


def test_a_base_reads_the_same_parts(tmp_path):
    """`--base` takes the census of a commit's files, and a path the copy of them
    leaves out empties a part without an error, so every part finds names at a
    commit."""
    result = CliRunner().invoke(cli, ["interface", "--json", "--base", "HEAD"])
    assert result.exit_code == 0, result.output
    committed = census(Tree.at("HEAD", tmp_path))
    assert [part for part in PARTS if not committed[part]] == []
