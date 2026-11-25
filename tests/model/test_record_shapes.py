"""Each shape of a `state.Record` has a file of its own, so no Leaf reads or replaces
a record a Leaf of another shape wrote; one that arbitrates between Leaves holds while
any shape of it stands, and the agent learns what an update left in a page
(`layer-registry.md`, "Page protocol")."""

import json

import pytest
from click.testing import CliRunner
from model_folds import leaf_page

from leaf import service as service_model
from leaf import state as state_model
from leaf import vendoring as vendoring_model
from leaf.cli import cli
from leaf.drafts import DRAFTS
from leaf.file_bindings import BINDINGS, bind_file, bound_paths, unbind_file
from leaf.refusals import Refused
from leaf.revisioning import activate_source
from leaf.schema import DRAFTS_FILE, FILE_BINDINGS_FILE


def another_shapes(record, path, value):
    """Write `value` where a Leaf at another shape of `record` keeps it, beside this
    Leaf's file."""
    other = path.with_name(f"{path.stem}@999{path.suffix}")
    other.write_text(json.dumps({"format": f"leaf-{record.kind}/999", **value}))
    return other


def test_grants_another_shape_recorded_grant_nothing_and_go_with_a_withdrawal(
    page_dir, tmp_path
):
    """Grants a Leaf of another shape recorded grant nothing here, and this Leaf's go
    in a file of their own, so that Leaf keeps its grants whatever this one grants.
    A withdrawal is the user's for every Leaf, so it removes that Leaf's record too."""
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
    assert other.read_bytes() == held

    unbind_file(page_dir, "second")
    assert not other.exists()


def test_page_check_names_what_another_version_left_in_the_page(page_dir):
    """`page check` names each record of another shape the page directory holds, so
    the agent can remove them once no Leaf of that version runs, and where one holds
    the user's unsent drafts, says to point the user at it rather than read it. It
    names none of this Leaf's own."""
    (page_dir / "index.html").write_text(leaf_page("Notes", "<p>Ship Tuesday.</p>"))
    activate_source(page_dir)

    def advised():
        checked = CliRunner().invoke(cli, ["page", "check", str(page_dir)])
        assert checked.exit_code == 0, checked.output
        return [
            finding["text"]
            for finding in json.loads(checked.output)["findings"]
            if finding["code"] == "other-version-records"
        ]

    assert advised() == []
    grants = another_shapes(BINDINGS, page_dir / FILE_BINDINGS_FILE, {"bindings": {}})
    [noted] = advised()
    assert str(grants) in noted and "drafts" not in noted

    drafts = another_shapes(DRAFTS, page_dir / DRAFTS_FILE, {"store": "s"})
    [noted] = advised()
    assert str(drafts) in noted and "tell the user where it is" in noted


@pytest.mark.parametrize("left", ["lifecycle", "claim"])
def test_a_page_a_session_holds_at_another_shape_stays_held(claimed, monkeypatch, left):
    """A session holding its page across an update that changes its lifecycle's or
    its claim's shape still holds the page for this Leaf, which can't read either
    record of that shape: a terminal can't re-initialize it, a `leaf wait` with no
    session can't take its input, and the refusal names the takeover."""
    if left == "lifecycle":
        lifecycle = state_model.session_file("s1", state_model.SESSION_SUFFIX)
        state_model.SESSION.file(lifecycle).rename(
            lifecycle.with_name(f"{lifecycle.stem}@999{lifecycle.suffix}")
        )
    else:
        payload = service_model.claim_path(claimed)
        state_model.CLAIM.file(payload).rename(
            payload.with_name(f"{payload.stem}@999{payload.suffix}")
        )
    claim = service_model.page_claim(claimed)

    assert not service_model.claim_is_active(claim)
    assert service_model.held_elsewhere(claimed, None)
    assert not service_model.may_receive(claimed, claim, None)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    with pytest.raises(Refused, match="leaf server start"):
        vendoring_model.cmd_init(claimed, ())
