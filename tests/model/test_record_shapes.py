"""Each shape of a `state.Record` has a file of its own, so no Leaf reads or replaces
a record a Leaf of another shape wrote; one that arbitrates between Leaves holds while
any shape of it stands, and the agent learns what an update left in a page
(`layer-registry.md`, "Page protocol")."""

import json
import os

import pytest
from click.testing import CliRunner
from conftest import hooks_run_this_tree
from interact_support import append_carried_log_record, record_claim, serving
from model_folds import leaf_page

from leaf.base import service as service_model
from leaf.base import state as state_model
from leaf.base.refusals import Refused
from leaf.base.schema import DRAFTS_FILE, FILE_BINDINGS_FILE
from leaf.commands import session as session_model
from leaf.commands.cli import cli
from leaf.pages import vendoring as vendoring_model
from leaf.records import transaction as transaction_model
from leaf.records.revisioning import activate_source
from leaf.serving.drafts import DRAFTS
from leaf.source.file_bindings import BINDINGS, bind_file, bound_paths, unbind_file


def another_shapes(record, path, value):
    """Write `value` where a Leaf at another shape of `record` keeps it, beside this
    Leaf's file."""
    other = path.with_name(f"{path.stem}@999{path.suffix}")
    other.parent.mkdir(parents=True, exist_ok=True)
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


def test_page_check_names_the_drafts_another_version_kept(page_dir):
    """`page check` names a drafts store of another shape in the page directory, the
    user's unsent words, and says to point the user at it rather than read it. Its
    other records of other shapes are disposable, and this Leaf's own drafts are no
    leftover, so neither is named."""
    (page_dir / "index.html").write_text(leaf_page("Notes", "<p>Ship Tuesday.</p>"))
    activate_source(page_dir)

    def advised():
        checked = CliRunner().invoke(cli, ["page", "check", str(page_dir)])
        assert checked.exit_code == 0, checked.output
        return [
            finding["text"]
            for finding in json.loads(checked.output)["findings"]
            if finding["code"] == "other-version-drafts"
        ]

    DRAFTS.write(page_dir / DRAFTS_FILE, {"store": "s", "version": 0, "drafts": {}})
    another_shapes(BINDINGS, page_dir / FILE_BINDINGS_FILE, {"bindings": {}})
    assert advised() == []

    drafts = another_shapes(DRAFTS, page_dir / DRAFTS_FILE, {"store": "s"})
    [noted] = advised()
    assert str(drafts) in noted and "tell the user where they are" in noted


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


def test_taking_over_a_page_held_at_another_shape_leaves_one_owner(
    page_dir, monkeypatch
):
    """A claim of another shape holds the page even where this shape's claim names
    a session that ended, so no session-less reader takes its input. A takeover
    ends the claim it replaces at every shape, so the page is left with one owner
    rather than two that both receive its input."""
    record_claim(page_dir, id="ended")
    state_model.end_session("ended")
    payload = service_model.claim_path(page_dir)
    another_shapes(state_model.CLAIM, payload, {"page": str(page_dir)})
    claim = service_model.page_claim(page_dir)

    assert service_model.held_elsewhere(page_dir, None)
    assert not service_model.may_receive(page_dir, claim, None)

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "taker")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    hooks_run_this_tree("taker")
    assert transaction_model.claim_page(page_dir)

    assert state_model.CLAIM.others(payload) == []
    taken = service_model.page_claim(page_dir)
    assert taken is not None and taken["id"] == "taker"
    assert service_model.claim_is_active(taken)
    assert service_model.held_elsewhere(page_dir, None) == "session taker"


def test_a_wait_for_no_session_takes_no_input_from_a_page_held_at_another_shape(
    page_dir, sessionless, capsys
):
    """A wait acting for no session stops at a page whose claim is at another
    shape, as at one a session holds at this shape, naming the takeover, rather
    than handing out input it could never acknowledge."""
    serving(page_dir, 1)
    payload = service_model.claim_path(page_dir)
    another_shapes(state_model.CLAIM, payload, {"page": str(page_dir)})
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "for its holder"}
    )

    assert session_model.cmd_wait(page_dir) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "a session of another Leaf version" in printed.err
    assert f"leaf server start {page_dir}` in an agent session" in printed.err


def test_a_rolled_back_takeover_leaves_the_other_shapes_holder_in_place(
    page_dir, monkeypatch
):
    """A takeover that fails after publishing, as a Codex start whose offer fails
    does, puts back the claim of another shape it removed, so the session holding
    the page under another Leaf keeps it."""
    payload = service_model.claim_path(page_dir)
    other = another_shapes(state_model.CLAIM, payload, {"page": str(page_dir)})
    held = other.read_bytes()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "taker")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    hooks_run_this_tree("taker")

    transition = transaction_model.take_page_claim(page_dir)
    assert transition is not None and not other.exists()
    transaction_model.restore_page_claim(page_dir, transition)

    assert other.read_bytes() == held
    assert service_model.page_claim(page_dir) is None
    assert service_model.held_elsewhere(page_dir, None)
