"""A session's lifecycle record: prompts, stops and provider observations opening
and closing its turn, session end releasing its pages, and the prompt that serves a
resumed session's pages again."""

import contextlib
import json
import os
import socket
import subprocess
import sys

import pytest
from interact_support import (
    PLUGIN_ROOT,
    STATED_TIMEOUT,
    append_carried_log_record,
    available_loopback_port,
    declared,
    fixture_service,
    read_record,
    record_claim,
    serving,
    vendored_at_another_protocol,
    write_record,
)

from leaf import codex as codex_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import vendoring as vendoring_model
from leaf.registry import storage as registry_storage
from leaf.registry.kernel import kernel_protocol


def test_a_restarted_session_cannot_reopen_a_dead_claims_turn(
    page_dir, monkeypatch, dead_pid
):
    """A reused session id is provenance, not proof that its old turn resumed."""
    old = record_claim(page_dir, id="reused", pid=dead_pid, turn="old-turn")
    assert not service_model.claim_is_active(old)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "reused")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    assert service_model.claim_page(page_dir)
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
        key = cleanup_model.session_file(session, cleanup_model.SESSION_SUFFIX).stem
        return sorted(
            path.name.removeprefix(f"{key}.")
            for path in cleanup_model.session_file(session, "").parent.glob(f"{key}.*")
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


@pytest.mark.parametrize(
    "resumed", ["after its end", "at an older protocol", "after a crash"]
)
def test_a_resumed_sessions_first_prompt_serves_its_page_again(
    page_dir, capsys, dead_pid, resumed
):
    """A resumed session holds a claim whose lifetime has gone, and its page's
    server retired with it, leaving the service enabled. Its first prompt takes the
    page back and serves it at the recorded address, taking a page at an older page
    protocol to this Leaf's first, as `leaf server start` would. The prompt's turn
    is the claim's, even after a crash, which leaves the old generation live under
    a dead process: a claim made after the prompt opened would start a generation
    with a turn of its own. The prompt hands that turn the input the user left
    meanwhile. The session's start serves nothing: it opens no turn."""
    if resumed == "after a crash":
        record_claim(page_dir, pid=dead_pid)
    else:
        record_claim(page_dir)
        cleanup_model.end_harness_instance("s1")
    port = available_loopback_port()
    fixture_service(page_dir, port, "session")
    left = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Still there?"}
    )
    if resumed == "at an older protocol":
        vendored_at_another_protocol(page_dir)
    capsys.readouterr()

    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "SessionStart", "session_id": "s1", "source": "resume"},
    )
    assert capsys.readouterr().out == ""
    assert server_model.running_server(page_dir) is None

    prompt(prompt_id="resumed")
    running = server_model.running_server(page_dir)
    assert running is not None and running["port"] == port
    record = registry_storage.layer_record(page_dir)
    assert record is not None and record["protocol"] == kernel_protocol()
    claim = service_model.page_claim(page_dir)
    assert service_model.claim_is_active(claim)
    assert claim is not None and claim["turn"] == "resumed"
    opening, envelope, *rest = json.loads(capsys.readouterr().out)[
        "hookSpecificOutput"
    ]["additionalContext"].split("\n")
    assert opening == hook_transport_model.INLINE_OPENING
    [batch] = json.loads(envelope)["batches"]
    assert [event["id"] for event in batch["events"]] == [left["id"]]
    assert hook_transport_model.ATTENTION_OPENING not in rest


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


@pytest.mark.parametrize("cause", ["newer Leaf", "port held", "no time left"])
def test_a_prompt_says_why_a_page_did_not_start_and_tries_again(
    page_dir, capsys, monkeypatch, cause
):
    """A start refused, as for a page a newer Leaf initialized, while another
    process holds the page's port, or once the hook has no time left before its
    deadline, leaves the page as it was and tells the turn which page and why. The
    next prompt tries again, and serves the page once the cause is gone."""
    record_claim(page_dir)
    with contextlib.ExitStack() as cause_stands:
        if cause == "newer Leaf":
            fixture_service(page_dir, available_loopback_port(), "session")
            layer = page_dir / schema_model.LAYER_FILE
            recorded = layer.read_bytes()
            record = registry_storage.layer_record(page_dir)
            assert record is not None
            later = f"leaf-layer/{registry_storage.LAYER.since + 1}"
            layer.write_text(json.dumps({"format": later, **record}), encoding="utf-8")
            cause_stands.callback(layer.write_bytes, recorded)
            reason = "Use a newer Leaf"
        elif cause == "port held":
            holder = cause_stands.enter_context(socket.socket())
            holder.bind(("127.0.0.1", 0))
            holder.listen()
            fixture_service(page_dir, holder.getsockname()[1], "session")
            reason = "Address already in use"
        else:
            fixture_service(page_dir, available_loopback_port(), "session")
            bounded = cause_stands.enter_context(monkeypatch.context())
            bounded.setattr(hook_transport_model, "CONFIRM_WITHIN", 0)
            reason = "no time left"
        capsys.readouterr()
        prompt()
        context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
        opening, refused, *_ = context.split("\n")
        assert opening == hook_transport_model.ATTENTION_OPENING
        assert refused.startswith(
            f"- {page_dir.resolve()}: server was down and did not start again: "
        )
        assert reason in refused
        assert server_model.running_server(page_dir) is None
        assert read_record(page_dir / "service.json")["enabled"] is True

    prompt()
    assert server_model.running_server(page_dir) is not None
    assert capsys.readouterr().out == ""


def test_a_prompt_serves_only_a_page_its_session_still_means_to_serve(page_dir, capsys):
    """A retained record alone cannot have a prompt serve a page the agent stopped,
    one served persistently or as a preview, one another session or harness holds,
    one whose records this Leaf can't read, or one never served. Nor does a
    session's start serve the session's own page, whatever brought it back."""
    service = {
        "host": "127.0.0.1",
        "bind": "127.0.0.1",
        "port": available_loopback_port(),
        "enabled": True,
        "lifetime": "session",
        "server_id": "retired-server",
    }
    for case in (
        "stop",
        "persistent",
        "preview",
        "transferred",
        "foreign-harness",
        "obsolete-claim",
        "obsolete-service",
        "missing-service",
        "uninitialized-page",
        "new-session",
    ):
        sid = f"reconnect-{case}"
        record_claim(page_dir, id=sid)
        write_record(page_dir / "service.json", service)
        claim_path = service_model.claim_path(page_dir)
        raw = files_model.read_json(claim_path)
        events = (page_dir / "events.jsonl").read_bytes()
        if case == "stop":
            assert not hosting_model.cmd_stop(page_dir)
        elif case == "persistent":
            write_record(
                page_dir / "service.json", {**service, "lifetime": "persistent"}
            )
        elif case == "preview":
            cleanup_model.write_json(page_dir / "preview.json", {})
        elif case == "transferred":
            record_claim(page_dir, id="successor")
        elif case == "foreign-harness":
            record_claim(page_dir, id=sid, harness="codex")
        elif case == "obsolete-claim":
            cleanup_model.write_json(
                claim_path,
                {**raw, "format": "leaf-claim/0"},
            )
        elif case == "obsolete-service":
            cleanup_model.write_json(
                page_dir / "service.json",
                {
                    **files_model.read_json(page_dir / "service.json"),
                    "format": "leaf-service/0",
                },
            )
        elif case == "missing-service":
            (page_dir / "service.json").unlink()
        elif case == "uninitialized-page":
            (page_dir / "events.jsonl").unlink()
        elif case == "new-session":
            sid = "never-claimed-a-leaf"
        claimed_before = claim_path.read_bytes()
        prompt(sid)
        assert "did not start again" not in capsys.readouterr().out, case
        assert server_model.running_server(page_dir) is None, case
        assert claim_path.read_bytes() == claimed_before, case
        (page_dir / "events.jsonl").write_bytes(events)
        (page_dir / "preview.json").unlink(missing_ok=True)

    record_claim(page_dir, id="reconnect-control")
    write_record(page_dir / "service.json", service)
    for source in ("startup", "compact", "resume"):
        hooks_model.cmd_hook(
            "claude-code",
            {
                "hook_event_name": "SessionStart",
                "session_id": "reconnect-control",
                "source": source,
            },
        )
        assert server_model.running_server(page_dir) is None, source
    prompt("reconnect-control")
    assert server_model.running_server(page_dir) is not None


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
    service_model.claim_page(sibling)
    before = {
        page: service_model.claim_path(page).read_bytes() for page in (claimed, sibling)
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
        page: service_model.claim_path(page).read_bytes() for page in before
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
    service_model.claim_page(sibling)
    assert service_model.claim_is_active(service_model.page_claim(sibling))
    claim_record_4 = service_model.page_claim(sibling)
    assert claim_record_4 is not None
    assert claim_record_4["turn"] == "resumed-turn"
    assert not service_model.claim_is_active(service_model.page_claim(claimed))
    assert service_model.claim_path(claimed).read_bytes() == before[claimed]
    capsys.readouterr()


def test_cold_session_end_does_not_wait_for_a_page_transaction(claimed):
    """A held page lock cannot consume the harness's three-second SessionEnd deadline.

    The transaction stays held for the whole run, so a SessionEnd that waited on it
    would never return: the suite's hang bound tells the two apart without timing
    the hook on a busy machine."""
    with service_model.PageTransaction(claimed):
        done = subprocess.run(
            [
                sys.executable,
                "-S",
                str(PLUGIN_ROOT / "src/leaf/state.py"),
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
    with service_model.PageTransaction(claimed) as page:
        _, expected = page.take_claim(harness)
        cleanup_model.prompt_turn("s1", "provider")
        page.restore_claim(expected, previous)
        assert previous is not None
        assert page.claim["acquisition"] == previous["acquisition"]
        _, first = page.take_claim(harness)
        _, successor = page.take_claim(harness)
        assert first["acquisition"] != successor["acquisition"]
        page.restore_claim(first, previous)
        assert page.claim["acquisition"] == successor["acquisition"]
        incompatible = {
            key: value for key, value in successor.items() if key != "acquisition"
        }
        cleanup_model.write_json(service_model.claim_path(claimed), incompatible)
        page.restore_claim(successor, previous)
        assert page.claim is None
        assert files_model.read_json(service_model.claim_path(claimed)) == incompatible


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
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
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
