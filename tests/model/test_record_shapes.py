"""Each shape of a `state.Record` has a file of its own, so no Leaf reads, replaces
or removes a record a Leaf of another shape wrote, and the agent finds what an update
left (`layer-registry.md`, "Page protocol")."""

import json

from click.testing import CliRunner
from model_folds import leaf_page

from leaf.cli import cli
from leaf.file_bindings import BINDINGS, bind_file, bound_paths, unbind_file
from leaf.revisioning import activate_source
from leaf.schema import FILE_BINDINGS_FILE
from leaf.server import ACCESS
from leaf.state import CLAIM, state_home


def another_shapes(record, path, value):
    """Write `value` where a Leaf at another shape of `record` keeps it, beside this
    Leaf's file."""
    other = path.with_name(f"{path.stem}@999{path.suffix}")
    other.write_text(json.dumps({"format": f"leaf-{record.kind}/999", **value}))
    return other


def test_a_record_another_shape_wrote_stays_as_that_leaf_left_it(page_dir, tmp_path):
    """Grants a Leaf of another shape recorded grant nothing here, and this Leaf's
    go in a file of their own, so that Leaf finds its record as it left it whatever
    this one grants or withdraws."""
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    first.write_text("first\n")
    second.write_text("second\n")
    grants = page_dir / FILE_BINDINGS_FILE
    other = another_shapes(
        BINDINGS, grants, {"bindings": {"first": str(first.resolve())}}
    )
    held = other.read_bytes()

    assert bound_paths(page_dir) == {}
    bind_file(page_dir, "second", second)
    assert set(bound_paths(page_dir)) == {"second"}
    unbind_file(page_dir, "second")
    assert other.read_bytes() == held
    assert BINDINGS.others(grants) == [other]


def test_the_agent_is_told_of_the_records_another_version_left(page_dir, tmp_path):
    """`page check` names each record of another shape the page directory holds, and
    `leaf page list` each the state home holds, by their files, format and count, so
    the agent can remove them once no Leaf of that version runs. Neither names a
    record of this Leaf's own shape."""
    (page_dir / "index.html").write_text(leaf_page("Notes", "<p>Ship Tuesday.</p>"))
    activate_source(page_dir)
    notes = tmp_path / "notes.md"
    notes.write_text("notes\n")
    bind_file(page_dir, "notes", notes)

    def advised():
        checked = CliRunner().invoke(cli, ["page", "check", str(page_dir)])
        assert checked.exit_code == 0, checked.output
        return [
            finding
            for finding in json.loads(checked.output)["findings"]
            if finding["code"] == "other-version-records"
        ]

    def listed():
        result = CliRunner().invoke(cli, ["page", "list"])
        assert result.exit_code == 0, result.output
        return json.loads(result.output)["other_version_records"]

    assert advised() == []
    assert listed() == []

    another_shapes(BINDINGS, page_dir / FILE_BINDINGS_FILE, {"bindings": {}})
    [noted] = advised()
    assert (
        f"{page_dir}/files@999.json (leaf-file-bindings/999, 1, last" in noted["text"]
    )

    another_shapes(ACCESS, state_home() / "access.json", {"token": "an older key"})
    claims = state_home() / "claims"
    claims.mkdir(exist_ok=True)
    for key in ("a" * 64, "b" * 64):
        another_shapes(CLAIM, claims / f"{key}.json", {"page": str(page_dir)})
    key, held = listed()
    assert key["files"] == [str(state_home() / "access@999.json")]
    assert (key["format"], key["count"]) == ("leaf-access/999", 1)
    # Several files of one shape that one pattern names alone are named by it.
    assert held["files"] == [str(claims / "*@999.json")]
    assert (held["format"], held["count"]) == ("leaf-claim/999", 2)
