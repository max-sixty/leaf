"""A session's lifecycle record: prompts, stops and provider observations opening
and closing its turn, session end releasing its pages, and the prompt that serves a
resumed session's pages again."""

import json
import os
import subprocess
import sys

import pytest
from conftest import hooks_run_this_tree
from interact_support import (
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    declared,
    read_record,
    record_claim,
    serving,
)

from leaf.agents import codex as codex_model
from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import hooks as hooks_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import transaction as transaction_model


def test_a_restarted_session_cannot_reopen_a_dead_claims_turn(
    page_dir, monkeypatch, dead_pid
):
    """A reused session id is provenance, not proof that its old turn resumed."""
    old = record_claim(page_dir, id="reused", pid=dead_pid, turn="old-turn")
    assert not service_model.claim_is_active(old)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "reused")
    hooks_run_this_tree("reused")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    assert transaction_model.claim_page(page_dir)
    renewed = service_model.page_claim(page_dir)
    assert renewed is not None
    assert renewed["id"] == "reused"
    assert renewed["turn"] != "old-turn"


def test_a_session_keeps_its_files_only_while_something_can_read_them(page_dir):
    """A session's end removes the files nothing will read again
    (`session-lifetime.md`, "A session's files"). A session that never used Leaf,
    as most sessions of a harness Leaf is installed in, ends without a file. An
    ended session a claim still names keeps its lifecycle and lock, which that
    claim reads. One whose page another session took keeps only a lease another
    process holds, and then nothing."""

    def files(session):
        """The session's files, each by its suffix, a record's under the name its
        readers give it (`state.record_name`)."""
        key = cleanup_model.session_file(session, cleanup_model.SESSION_SUFFIX).stem
        return sorted(
            cleanup_model.record_name(path.name).removeprefix(f"{key}.")
            for path in cleanup_model.session_file(session, "").parent.glob(
                f"{key}[.@]*"
            )
        )

    cleanup_model.end_harness_instance("never-used-leaf")
    assert files("never-used-leaf") == []

    record_claim(page_dir, id="released")
    leases_model.mark_hooks("released")
    lease_path = leases_model.waiter_lease_path(None, "released")
    assert lease_path is not None
    held = leases_model.take_wait_lease(lease_path)
    record_claim(page_dir, id="holder")
    leases_model.mark_hooks("holder")
    cleanup_model.end_harness_instance("released")
    assert files("released") == ["wait"]
    leases_model.release_lease(held)
    cleanup_model.end_harness_instance("released")
    assert files("released") == []

    cleanup_model.end_harness_instance("holder")
    assert files("holder") == ["delivery.lock", "lifecycle"]
    claim_record = service_model.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["turn_closed"] is not None


def test_desktop_codex_unloading_keeps_the_chat_page_owned(page_dir, native_codex_chat):
    """Desktop unloads idle running instances without ending the user's chat."""
    native_codex_chat("s1")
    claim = record_claim(
        page_dir, harness="codex", chat=True, ts=cleanup_model.now_iso()
    )
    before = cleanup_model.session_record("s1")
    cleanup_model.end_harness_instance("s1")
    assert service_model.claim_is_active(service_model.page_claim(page_dir))
    claim_record_2 = service_model.page_claim(page_dir)
    assert claim_record_2 is not None
    assert claim_record_2["acquisition"] == claim["acquisition"]
    turn_record = cleanup_model.session_record("s1")
    assert turn_record is not None
    assert before is not None
    assert turn_record["generation"] == before["generation"]
    turn_record_2 = cleanup_model.session_record("s1")
    assert turn_record_2 is not None
    assert turn_record_2["turn_closed"] is not None


def prompt(session: str = "s1", **fields) -> None:
    """Run Claude Code's prompt hook for `session`."""
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": session, **fields},
    )


def test_a_prompt_takes_back_a_page_whose_server_outlived_its_session(claimed, capsys):
    """A server still serving through its grace period after its session ended is
    no owner of the page's input. The resumed session's prompt claims the page
    again and keeps that server rather than binding another."""
    serving(claimed, 41000, "session")
    cleanup_model.end_harness_instance("s1")
    assert server_model.running_server(claimed)
    assert not service_model.claim_is_active(service_model.page_claim(claimed))
    capsys.readouterr()

    prompt()

    assert service_model.claim_is_active(service_model.page_claim(claimed))
    assert read_record(claimed / "service.json")["server_id"] == "fixture-server"
    assert capsys.readouterr().out == ""


def test_session_end_cannot_release_a_page_claimed_by_its_successor(page_dir):
    serving(page_dir, 41000, "session")
    record_claim(page_dir, id="predecessor")
    record_claim(page_dir, id="successor")
    session_model.cmd_waiting(page_dir)
    cleanup_model.end_harness_instance("predecessor")
    claim_record_3 = service_model.page_claim(page_dir)
    assert claim_record_3 is not None
    assert claim_record_3["id"] == "successor"
    assert service_model.claim_is_active(service_model.page_claim(page_dir))
    assert read_record(page_dir / "service.json")["enabled"] is True
    assert declared(page_dir)["state"] == "waiting"
    assert server_model.running_server(page_dir)


def test_session_lifecycle_is_shared_without_rewriting_page_claims(
    claimed, tmp_path, capsys
):
    """Prompts precede claims; a shared ending and a resumed ID never revive old ownership."""
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "provider-turn",
        },
    )
    capsys.readouterr()
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    transaction_model.claim_page(sibling)
    before = {
        page: service_model.CLAIM.file(service_model.claim_path(page)).read_bytes()
        for page in (claimed, sibling)
    }
    claims = [service_model.page_claim(page) for page in before]
    assert all(claim is not None for claim in claims)
    assert {claim["turn"] for claim in claims if claim is not None} == {"provider-turn"}
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "Interrupt",
            "session_id": "s1",
            "turn_id": "provider-turn",
        },
    )
    claims = [service_model.page_claim(page) for page in before]
    assert all(claim is not None and claim["turn_closed"] for claim in claims)
    assert {
        page: service_model.CLAIM.file(service_model.claim_path(page)).read_bytes()
        for page in before
    } == before
    cleanup_model.end_session("s1")
    assert not any(
        service_model.claim_is_active(service_model.page_claim(page)) for page in before
    )
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "resumed-turn",
        },
    )
    transaction_model.claim_page(sibling)
    assert service_model.claim_is_active(service_model.page_claim(sibling))
    claim_record_4 = service_model.page_claim(sibling)
    assert claim_record_4 is not None
    assert claim_record_4["turn"] == "resumed-turn"
    assert not service_model.claim_is_active(service_model.page_claim(claimed))
    assert (
        service_model.CLAIM.file(service_model.claim_path(claimed)).read_bytes()
        == before[claimed]
    )
    capsys.readouterr()


def test_cold_session_end_does_not_wait_for_a_page_transaction(claimed):
    """A held page lock cannot consume the harness's three-second SessionEnd deadline.

    The transaction stays held for the whole run, so a SessionEnd that waited on it
    would never return: the suite's hang bound tells the two apart without timing
    the hook on a busy machine."""
    with transaction_model.PageTransaction(claimed):
        done = subprocess.run(
            [
                sys.executable,
                "-S",
                str(PLUGIN_ROOT / "src/leaf/base/state.py"),
            ],
            input=json.dumps({"hook_event_name": "SessionEnd", "session_id": "s1"}),
            text=True,
            capture_output=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")
        assert not service_model.claim_is_active(service_model.page_claim(claimed))


def test_a_stale_stop_cannot_plan_or_continue_a_newer_turn(claimed, capsys):
    hooks_model.cmd_hook(
        "codex",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "turn_id": "old"},
    )
    hooks_model.cmd_hook(
        "codex",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "turn_id": "new"},
    )
    capsys.readouterr()
    events_model.append_event(
        claimed, {"kind": "comment", "author": "user", "text": "for the new turn"}
    )
    before = events_model.read_events(claimed)
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "s1", "turn_id": "old"}
    )
    assert capsys.readouterr().out == ""
    assert events_model.read_events(claimed) == before
    claim_record_5 = service_model.page_claim(claimed)
    assert claim_record_5 is not None
    assert claim_record_5["turn"] == "new"
    claim_record_6 = service_model.page_claim(claimed)
    assert claim_record_6 is not None
    assert claim_record_6["turn_closed"] is None


def test_claim_rollback_tracks_acquisition_independently_of_turn(claimed):
    previous = service_model.page_claim(claimed)
    harness = harness_model.session_harness()
    with transaction_model.PageTransaction(claimed) as page:
        expected = page.take_claim(harness)
        cleanup_model.prompt_turn("s1", "provider")
        page.restore_claim(expected)
        assert previous is not None
        assert page.claim["acquisition"] == previous["acquisition"]
        first = page.take_claim(harness)
        successor = page.take_claim(harness)
        assert first.claim["acquisition"] != successor.claim["acquisition"]
        page.restore_claim(first)
        assert page.claim["acquisition"] == successor.claim["acquisition"]
        # A Leaf of another claim shape replaced the claim, which this Leaf reads
        # none of and leaves as it was.
        path = service_model.claim_path(claimed)
        other = path.with_name(f"{path.stem}@999{path.suffix}")
        service_model.CLAIM.remove(path)
        cleanup_model.write_json(other, {**successor.claim, "format": "leaf-claim/999"})
        held = other.read_bytes()
        page.restore_claim(successor)
        assert page.claim is None
        assert other.read_bytes() == held


def test_provider_observation_cannot_replace_a_newer_prompt(claimed):
    cleanup_model.prompt_turn("s1", "old")
    cleanup_model.close_session_turn("s1", "old")
    old = cleanup_model.session_record("s1")
    cleanup_model.prompt_turn("s1", "new")
    new = cleanup_model.session_record("s1")
    assert not codex_model.TurnFold(
        "s1", "old", lifecycle=cleanup_model.session_record("s1")
    ).open()
    assert cleanup_model.session_record("s1") == new
    assert cleanup_model.start_session_turn("s1", "late-start", old) is None
    assert cleanup_model.session_record("s1") == new
    adopted = cleanup_model.start_session_turn("s1", "legitimate-start", new)
    assert adopted is not None
    assert adopted["turn"] == "legitimate-start"


def test_no_page_stop_cannot_close_a_prompt_that_arrives_during_discovery(monkeypatch):
    newer = []

    def pages(_sid):
        newer.append(cleanup_model.prompt_turn("never-claimed"))
        return []

    monkeypatch.setattr(hooks_model, "owned_pages", pages)
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "Stop", "session_id": "never-claimed"}
    )
    assert cleanup_model.session_record("never-claimed") == newer[0]


@pytest.mark.parametrize("resumed", [False, True])
def test_first_claim_enriches_prompt_provenance_without_replacing_it(
    page_dir, monkeypatch, resumed
):
    if resumed:
        old = cleanup_model.ensure_session("before-claim", {"pid": os.getpid() + 1})
        cleanup_model.end_session("before-claim")
    before = cleanup_model.prompt_turn("before-claim", "provider")
    assert before is not None
    assert before["lifetime"] == {}
    if resumed:
        assert before is not None
        assert before["generation"] != old["generation"]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "before-claim")
    hooks_run_this_tree("before-claim")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert transaction_model.claim_page(page_dir)
    after = cleanup_model.session_record("before-claim")
    assert after is not None
    assert (after["generation"], after["turn"], after["provider"]) == (
        before["generation"],
        "provider",
        True,
    )
    assert after["lifetime"] == {"pid": os.getpid()}


def test_closed_provider_prompt_never_reopens_its_identity(claimed, capsys):
    cleanup_model.prompt_turn("s1", "completed")
    cleanup_model.close_session_turn("s1", "completed")
    ended = cleanup_model.session_record("s1")
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "turn_id": "completed",
        },
    )
    assert cleanup_model.session_record("s1") == ended
    assert capsys.readouterr().out == ""


def test_an_unnamed_prompt_after_the_session_ended_opens_a_turn(claimed):
    """A session resumed after its end, under a harness that names no turn, has a
    turn of Leaf's from its first prompt, which pickups and starts name."""
    cleanup_model.prompt_turn("s1")
    cleanup_model.end_session("s1")
    assert not cleanup_model.session_live(cleanup_model.session_record("s1"))
    resumed = cleanup_model.prompt_turn("s1")
    assert cleanup_model.session_live(resumed) and cleanup_model.turn_open(resumed)
