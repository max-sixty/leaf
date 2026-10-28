"""The prompt and Stop hooks as a delivery route: opening and closing the session's
turn on every page it holds, handing pending input over inline or as a pointer, and
confirming what they hand over within their deadline."""

import fcntl
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    _interaction_prompt_evidence,
    acknowledged_through,
    activity_reading,
    append_carried_log_record,
    continued,
    declare_idle,
    declare_work,
    declared,
    delivered,
    delivered_ref,
    freeze_events,
    last_deliverable_seq,
    owed_answers,
    page_state,
    publish,
    receive_through,
    record_claim,
    said,
    serving,
    vendored_at_another_protocol,
    working,
    yaml_document,
)

from leaf import activity as activity_model
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import file_changes as file_changes_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import presence as presence_model
from leaf import schema as schema_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import session_runtime as session_runtime_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model
from leaf.registry.storage import LAYER, layer_record


def handed(page_dir, input_id: str) -> bool:
    """Whether a hook handed `input_id` into a turn: its opened pickup, which the page
    shows as Delivered whether or not a later hook has confirmed it."""
    return bool(
        delivery_model.pickup_receipts(
            events_model.read_events(page_dir), phase="opened", input_id=input_id
        )
    )


def test_pages_follower_without_owned_pages_does_not_open_a_watcher(
    claimed, monkeypatch, capsys
):
    cleanup_model.end_session("s1")
    assert cleanup_model.held_claims("s1")
    assert service_model.owned_pages("s1") == []

    def unexpected_watcher(*_args, **_kwargs):
        raise AssertionError("a session with no owned pages opened a watcher")

    monkeypatch.setattr(file_changes_model, "FileChanges", unexpected_watcher)
    hooks_model.cmd_pages({"session_id": "s1"})
    assert capsys.readouterr().out == "[]\n"


def test_the_stop_hook_records_the_ending_of_the_turn_behind_a_claim(claimed, capsys):
    """A `working` claim is written by a model's turn, and a turn can end at any token
    without running anything — so nothing writes its close, and the page was left to
    find an abandoned claim by outwaiting a clock. The Stop hook is the harness
    watching that same moment, which is what these hooks are for.

    It stamps whether or not it has a nudge to make, and ahead of both of the guard's
    early returns: a turn that ends with nothing outstanding is exactly the turn that
    walks away from a `working` claim. The stamp is provenance and lands on the claim
    record rather than in a status — what the agent said it was doing stays the
    agent's to write, which is the line SessionEnd already draws."""
    working(claimed, "reading the reconnect traces")
    assert service_model.page_claim(claimed)["turn_closed"] is None
    events = events_model.read_events(claimed)
    assert presence_model.presence(claimed, events)["turn_closed"] is None

    # A live watcher: the guard has nothing to say, and the ending is recorded anyway.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    assert presence_model.presence(claimed, events)["turn_closed"] == closed
    # And what the agent said it was doing is untouched by the observation of it.
    [task] = page_state(claimed)["browser"]["todos"]
    assert task["running"]["text"] == "reading the reconnect traces"

    # Re-entry after a block stands the guard down before it would speak; the stamp is
    # the turn's own and is taken on that ending too.
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    assert capsys.readouterr().out == ""
    reentered_closed = service_model.page_claim(claimed)["turn_closed"]
    assert reentered_closed >= closed

    # Another session's turn ending says nothing about a page that is not one of its
    # own — the stamp names when this claim's turn ended or it means nothing.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s2"})
    assert service_model.page_claim(claimed)["turn_closed"] == reentered_closed
    leases_model.release_lease(lease)


def test_receiving_a_batch_observes_the_session_turn_on_every_owned_page(
    claimed, printing, tmp_path, capsys
):
    """The turn is the session's, not the delivering page's. The Stop hook closes it
    across every page the session holds, so the delivery that answers it has to reach
    the same set: a session holding two leaves would otherwise leave the sibling
    stamped through a turn that is demonstrably running, and two minutes later that
    leaf tells its own user the agent left when its turn ended.

    The sibling here never speaks — the batch is the other page's, and the wait ends
    on the first page that delivers. That is exactly the page whose stamp nothing else
    would clear."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    working(claimed, "answering the first comment")
    working(sibling, "reading the sibling")
    serving(claimed, 1)
    serving(sibling, 2)
    assert service_model.claim_page(sibling)
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert service_model.page_claim(sibling)["turn_closed"]

    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c1", "author": "user", "text": "one"}
    )
    cleanup_model.prompt_turn("s1")
    assert session_model.cmd_wait() == 0
    delivered(capsys)
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert service_model.page_claim(sibling)["turn_closed"] is None

    # A page another session holds is not this turn's to speak for.
    others = tmp_path / "others"
    vendoring_model.cmd_init(others)
    working(others, "another session's page")
    serving(others, 3)
    assert service_model.claim_page(others)
    claim = service_model.page_claim(others)
    record_claim(
        others, **{**claim, "id": "s2", "turn_closed": "2026-01-01T00:00:00+00:00"}
    )
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    # The Stop hook delivers this one into the running turn itself.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == ["c2"]
    assert (
        service_model.page_claim(others)["turn_closed"] == "2026-01-01T00:00:00+00:00"
    )
    declare_idle(sibling)
    declare_idle(others)


def test_the_prompt_hook_opens_the_turn_on_every_page_the_session_holds(
    claimed, tmp_path, capsys
):
    """A delivery is not the only observable opening, and it is not the one the
    panel sends the user to. The `quiet` status says to nudge in the terminal;
    a user who does that answers where no batch is written, so no transport ever
    hands one over and nothing would clear the stamp — the page would go on telling
    them to do the thing they just did.

    `UserPromptSubmit` is the literal mirror of the `Stop` branch that stamps the
    ending: same sweep over `owned_pages`, same place ahead of the early returns,
    same session scope."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    working(claimed, "answering the first comment")
    working(sibling, "reading the sibling")
    serving(claimed, 1)
    serving(sibling, 2)
    assert service_model.claim_page(sibling)
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert service_model.page_claim(sibling)["turn_closed"]

    status_before = declared(claimed)
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert service_model.page_claim(sibling)["turn_closed"] is None
    # Only the stamp moves: what the agent said it was doing stays the agent's.
    assert declared(claimed) == status_before

    # Another session's prompt says nothing about this one's pages.
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    capsys.readouterr()
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s2"}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"] == closed
    declare_idle(sibling)


def test_a_named_wait_does_not_invent_turn_entry(claimed, printing, capsys):
    """Naming a held page observes it without reopening an ended session turn.

    That ownership action does not confirm receipt of output: the batch remains
    pending, and no pickup is recorded until the Stop hook of a turn hands the
    delivery over.
    """
    working(claimed, "answering the first comment")
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]

    serving(claimed, 1)
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c1", "author": "user", "text": "one"}
    )
    status_before = declared(claimed)

    assert session_model.cmd_wait(claimed) == 0
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert declared(claimed) == status_before
    assert acknowledged_through(claimed) == 0
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(claimed)
    )

    cleanup_model.prompt_turn("s1")
    # The Stop hook carries the batch into the turn it holds open, asked again
    # for the same turn or not.
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == ["c1"]
    assert service_model.page_claim(claimed)["turn_closed"] is None

    # A batch this session never took says nothing about its turn: the successor
    # that delivers it is the one whose turn opened.
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    capsys.readouterr()
    closed = service_model.page_claim(claimed)["turn_closed"]
    assert closed
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    cleanup_model.open_session_turn("s2")
    assert service_model.page_claim(claimed)["turn_closed"] == closed


def test_a_stop_leaves_input_arriving_at_the_end_to_a_turn_of_its_own(
    claimed, interactive, capsys
):
    """Where a watch follows the turn, its Stop hands no input over. Continuing the
    turn would have the agent write one more message, and Claude Code's focus view
    shows a turn's final message alone, so the reply to that input would stand in
    place of the answer the turn had written. The turn ends on its answer, and the
    watch, which wakes once the turn closes, gives the input a turn whose prompt
    hook hands it over."""
    session_model.cmd_waiting(claimed)
    turn = service_model.page_claim(claimed)["turn"]
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "and this?"}
    )

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    assert acknowledged_through(claimed) < comment["seq"]

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = json.loads(context.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    claim = service_model.page_claim(claimed)
    assert claim["turn"] != turn
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    assert (pickup["kind"], pickup["turn"]) == ("pickup", claim["turn"])


def test_a_stop_that_hands_over_input_keeps_the_turn_open(claimed, printing, capsys):
    """Under plain `--print` no watch follows the run, so input that arrives as the
    turn ends goes into that same turn: the Stop that hands it over continues it,
    and the turn it hands the input to is the one still running, not closed, and
    not closed and reopened as another. The repeated Stop that follows with
    nothing new is the turn really ending."""
    session_model.cmd_waiting(claimed)
    session = service_model.page_claim(claimed)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "and this?"}
    )

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    envelope = json.loads(continued(answer).split("\n")[1])
    [batch] = envelope["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    claim = service_model.page_claim(claimed)
    assert (claim["turn"], claim["turn_closed"]) == (session["turn"], None)
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    assert (pickup["kind"], pickup["turn"]) == ("pickup", session["turn"])

    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    leases_model.release_lease(lease)


def test_a_repeated_stop_is_held_open_only_by_the_users_input(
    claimed, printing, capsys
):
    """A repeated Stop takes the user's input into the turn, and nothing else. A
    page's own errors and a worker's reports arrive unpaced, so a turn that
    blocked on each would never end; they stay pending for the next turn, and go
    in with the user's move when one arrives."""
    error = append_carried_log_record(
        claimed, {"kind": "error", "author": "page", "text": "a widget threw"}
    )
    repeated = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}

    hooks_model.cmd_hook("claude-code", repeated)
    assert capsys.readouterr().out == ""
    assert acknowledged_through(claimed) == 0
    assert [
        event["id"]
        for event in service_model.unacknowledged(events_model.read_events(claimed), 0)
    ] == [error["id"]]

    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "is it broken?"}
    )
    cleanup_model.prompt_turn("s1")
    hooks_model.cmd_hook("claude-code", repeated)
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    envelope = json.loads(continued(answer).split("\n")[1])
    [batch] = envelope["batches"]
    assert [event["id"] for event in batch["events"]] == [error["id"], comment["id"]]
    assert handed(claimed, error["id"]) and handed(claimed, comment["id"])
    assert acknowledged_through(claimed) == 0
    # The Stop that follows the continued turn confirms what it read.
    hooks_model.cmd_hook("claude-code", repeated)
    assert capsys.readouterr().out == ""
    assert acknowledged_through(claimed) == last_deliverable_seq(claimed)


def test_a_page_that_changed_hands_before_receipt_keeps_its_input(
    claimed, printing, tmp_path, monkeypatch, capsys
):
    """The hook records a delivery only for the pages its session still holds as it
    records, and hands over inline only what it recorded: a pointer in its place
    would leave opened pickups the next hook confirms though the model read none of
    them. A page another session took after capture keeps its input pending, and
    once this session holds it again, its next hook hands that input over."""
    moved = tmp_path / "a-moved"  # ahead of `claimed` in the walk's path order
    shutil.copytree(claimed, moved)
    assert service_model.claim_page(moved)
    comments = {
        page: append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": f"on {page.name}"}
        )
        for page in (moved, claimed)
    }
    freeze = hook_transport_model.freeze_delivery

    def freeze_then_transfer(batches, **kwargs):
        delivery = freeze(batches, **kwargs)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
        assert service_model.claim_page(moved)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
        return delivery

    monkeypatch.setattr(hook_transport_model, "freeze_delivery", freeze_then_transfer)
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    opening, envelope, *_ = continued(capsys.readouterr().out).split("\n")
    assert opening == hook_transport_model.INLINE_OPENING
    [batch] = json.loads(envelope)["batches"]
    assert (batch["page"], [event["id"] for event in batch["events"]]) == (
        str(claimed),
        [comments[claimed]["id"]],
    )
    assert service_model.page_claim(moved)["id"] == "s2"
    assert acknowledged_through(moved) == 0
    assert all(e["kind"] != "pickup" for e in events_model.read_events(moved))
    assert handed(claimed, comments[claimed]["id"])
    # The continued turn reads it, and its next tool boundary confirms it.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "PostToolBatch", "session_id": "s1"}
    )
    assert capsys.readouterr().out == ""
    assert acknowledged_through(claimed) >= comments[claimed]["seq"]

    monkeypatch.setattr(hook_transport_model, "freeze_delivery", freeze)
    assert service_model.claim_page(moved)
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    again = json.loads(
        json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ].split("\n")[1]
    )
    [batch] = again["batches"]
    assert (batch["page"], [event["id"] for event in batch["events"]]) == (
        str(moved),
        [comments[moved]["id"]],
    )
    assert handed(moved, comments[moved]["id"])


def test_input_too_large_for_the_turn_goes_as_a_pointer_its_reader_confirms(
    claimed, printing, capsys
):
    """Claude Code replaces a hook context over its limit with a preview, so
    confirming it on handover would confirm what the model never read. Input that
    large goes as a pointer instead: the hook confirms nothing, and the reader
    confirms after every part reaches its context."""
    harness = harness_model.ClaudeCodeHarness
    comment = append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "text": "x" * harness.hook_context_bytes},
    )

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    reason = continued(answer)
    assert harness.fits_hook_context(reason)
    [delivery_id] = re.findall(r'<leaf-delivery id="(\w+)"', reason)
    assert acknowledged_through(claimed) == 0
    assert all(e["kind"] != "pickup" for e in events_model.read_events(claimed))

    # Confirmed by a command the model runs anyway, and which only confirms: the
    # session's watch is the background Stop hook's, which a wait the model ran
    # would only take the lease from.
    read = CliRunner().invoke(cli_model.cli, ["delivery", "read", delivery_id])
    assert read.exit_code == 0, read.output
    pointer = json.loads(read.output)
    assert f"leaf delivery ack {delivery_id}" in pointer["acknowledge"]
    confirmed = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id])
    assert confirmed.exit_code == 0, confirmed.output
    [batch] = pointer["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert acknowledged_through(claimed) == last_deliverable_seq(claimed)


def test_a_pointer_is_handed_once_per_turn_until_its_reader_confirms(
    claimed, printing, capsys
):
    """A pointer leaves its input unconfirmed, so a later tool boundary of the same
    turn would freeze that input again and point at it under a new id: the model
    read the same input twice, two to four times a turn. A tool boundary carries
    only new input, so it hands nothing from a page whose pointer this turn has
    not confirmed, and the page's later input follows once the reader confirms."""
    prompt = {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    boundary = {"hook_event_name": "PostToolBatch", "session_id": "s1"}
    large = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "x" * harness_model.ClaudeCodeHarness.hook_context_bytes,
        },
    )
    hooks_model.cmd_hook("claude-code", prompt)
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [delivery_id] = re.findall(r'<leaf-delivery id="(\w+)"', context)

    later = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "And this"}
    )
    hooks_model.cmd_hook("claude-code", boundary)
    assert capsys.readouterr().out == ""
    assert acknowledged_through(claimed) < large["seq"]

    confirmed = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id])
    assert confirmed.exit_code == 0, confirmed.output
    assert acknowledged_through(claimed) == large["seq"]
    hooks_model.cmd_hook("claude-code", boundary)
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = json.loads(context.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [later["id"]]

    # A new turn's prompt hands over again whatever a pointer left unconfirmed.
    unread = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "y" * harness_model.ClaudeCodeHarness.hook_context_bytes,
        },
    )
    hooks_model.cmd_hook("claude-code", boundary)
    [pointed] = re.findall(
        r'<leaf-delivery id="(\w+)"',
        json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"],
    )
    cleanup_model.close_session_turn("s1")
    hooks_model.cmd_hook("claude-code", prompt)
    # The delivery leads; reminders of the answers owed follow it.
    again, *_ = re.findall(
        r'<leaf-delivery id="(\w+)"',
        json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"],
    )
    assert again != pointed
    [batch] = delivery_model.read_delivery(again)["batches"]
    assert [event["id"] for event in batch["events"]] == [unread["id"]]


def test_a_prompt_that_reopens_the_turn_lets_its_tool_boundary_point_again(
    claimed, printing, capsys
):
    """Escape drops a prompt with its hook's pointer, and Claude Code submits it
    again into the same turn. Whether or not that prompt's own hook hands the input
    over, the pointer the dropped one carried reached no model, so the reopened
    turn's tool boundary points at the input again."""
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "x" * harness_model.ClaudeCodeHarness.hook_context_bytes,
        },
    )

    def handed_a_pointer() -> bool:
        context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
        return bool(
            re.findall(r'<leaf-delivery id="(\w+)"', context["additionalContext"])
        )

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert handed_a_pointer()
    turn = cleanup_model.session_record("s1")["turn"]
    time.sleep(0.002)  # `turn_opened` counts milliseconds
    cleanup_model.prompt_turn("s1")
    assert cleanup_model.session_record("s1")["turn"] == turn
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "PostToolBatch", "session_id": "s1"}
    )
    assert handed_a_pointer()


def test_pi_takes_input_of_any_size_inline(page_dir, monkeypatch, capsys):
    """Leaf's Pi extension adds a hook's context to the session at any size, so
    input too large for Claude Code's context reaches Pi's whole and confirmed."""
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PI_SESSION_ID", "s1")
    monkeypatch.setenv("LEAF_PI_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    text = "x" * harness_model.ClaudeCodeHarness.hook_context_bytes
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": text}
    )

    hooks_model.cmd_hook("pi", {"hook_event_name": "Stop", "session_id": "s1"})
    opening, envelope, *_ = continued(capsys.readouterr().out).split("\n")
    assert opening == hook_transport_model.INLINE_OPENING
    [batch] = json.loads(envelope)["batches"]
    assert [(event["id"], event["text"]) for event in batch["events"]] == [
        (comment["id"], text)
    ]
    assert acknowledged_through(page_dir) == last_deliverable_seq(page_dir)


def test_hook_drops_a_page_transferred_after_ownership_discovery(claimed, monkeypatch):
    """Ownership transfer before the planner's page lock belongs to the new owner."""
    session_model.cmd_waiting(claimed)
    discover = hook_transport_model.owned_pages

    def transfer(session_id):
        pages = discover(session_id)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
        assert service_model.claim_page(claimed)
        return pages

    monkeypatch.setattr(hook_transport_model, "owned_pages", transfer)
    assert hook_transport_model.remedies(hook_transport_model.read_plans("s1")) == []


def test_one_tool_calls_hooks_do_its_work_once(monkeypatch):
    """Claude Code runs the PreToolUse registration once for each of its `if`
    rules a command matches, at once, before the call; the first opens the turn a
    claim would join, and the rest leave it as they find it. Another call's hook
    does its work again."""
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "escape_sandbox", lambda harness: None
    )

    def before(call: str) -> None:
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": "PreToolUse", "session_id": "s9", "tool_use_id": call},
        )

    before("toolu_1")
    record = cleanup_model.session_record("s9")
    assert record["turn_closed"] is None
    cleanup_model.close_session_turn("s9", None, expected=record)
    before("toolu_1")
    assert cleanup_model.session_record("s9")["turn_closed"] is not None
    before("toolu_2")
    assert cleanup_model.session_record("s9")["turn_closed"] is None


def test_claude_codes_turn_confirms_what_its_hooks_hand_over(claimed, capsys):
    """Claude Code's prompt hook runs as every turn begins, including the one a
    background wait's ending opens, and its PostToolBatch hook between steps; each hands
    the turn the whole pending delivery inline, so the move reads Delivered as the
    hook hands it over, the envelope names no acknowledgement, and the model runs
    none. Claude Code reads that output only once the hook exits and may still drop
    it, so the next hook records the receipt of what the transcript shows reached
    the model's context; until then nothing offers the move again."""
    working(claimed, "revising")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert page_state(claimed)["pending"] == 1
    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "sent"
    # A running wait changes nothing: it only wakes the session.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    leases_model.release_lease(lease)
    envelope = context.split("\n")[1]
    payload = json.loads(envelope)
    assert payload["acknowledge"] is None
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "picked_up"
    assert page_state(claimed)["pending"] == 1
    with service_model.PageTransaction(claimed) as page:
        assert delivery_model.deliverable(page) == []
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    claim = service_model.page_claim(claimed)
    assert (pickup["kind"], pickup["phase"], pickup["events"]) == (
        "pickup",
        "opened",
        [comment["id"]],
    )
    assert (pickup["session"], pickup["turn"]) == (claim["id"], claim["turn"])

    # Input that arrives during the turn enters it at its next tool boundary.
    later = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more"}
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "PostToolBatch", "session_id": "s1"}
    )
    boundary = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert boundary["hookEventName"] == "PostToolBatch"
    later_delivery = json.loads(boundary["additionalContext"].split("\n")[1])
    assert later_delivery["acknowledge"] is None
    [batch] = later_delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [later["id"]]
    # The boundary confirmed the prompt's handover and left its own to the next hook.
    assert acknowledged_through(claimed) == comment["seq"]
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    assert (pickup["kind"], pickup["events"], pickup["turn"]) == (
        "pickup",
        [later["id"]],
        claim["turn"],
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    capsys.readouterr()
    assert page_state(claimed)["pending"] == 0


def prompt_watch(prompt_id: str, monkeypatch) -> tuple[threading.Thread, list]:
    """Start the watch Claude Code's prompt registration starts in the background, and
    return once its first pass has read the pages, with the list its wake lands in."""
    started = threading.Event()
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        started.set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)
    outcome = []
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt_id": prompt_id,
    }
    watch = threading.Thread(
        target=lambda: outcome.append(hooks_model.cmd_watch("claude-code", payload))
    )
    watch.start()
    assert started.wait(STATED_TIMEOUT), "the prompt's watch never read the pages"
    return watch, outcome


def test_a_handover_its_turn_never_confirmed_is_offered_again(
    claimed, interactive, context_record, monkeypatch, capsys
):
    """Escape while another plugin's prompt hook still runs drops the whole prompt,
    Leaf's context with it, after Leaf's hook has handed its delivery over, and the
    transcript shows none of it. Claude Code's record then reads idle, so the turn
    reads ended and what it was handed is input again, both an update that owes a
    reply and one that owes none. The watch the turn's prompt started wakes the
    session, and the prompt that opens, under a prompt id of its own, is handed it
    again; once the transcript shows it, the next hook confirms."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    withdrawn = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "never mind"}
    )
    resolve = append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": withdrawn["id"]}
    )
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    leases_model.mark_hooks("s1")
    live = {"state": "busy", "since": datetime.now().astimezone().isoformat()}
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "live_turn", lambda harness: dict(live)
    )

    def handed_over(prompt_id: str) -> list[str]:
        hooks_model.cmd_hook(
            "claude-code",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "s1",
                "prompt_id": prompt_id,
            },
        )
        context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
        [batch] = json.loads(context.split("\n")[1])["batches"]
        return [event["id"] for event in batch["events"]]

    updates = [asked["id"], withdrawn["id"], resolve["id"]]
    context_record.dropped = {"p1"}
    assert handed_over("p1") == updates
    # While the turn runs, its prompt's watch wakes nobody.
    watch, outcome = prompt_watch("p1", monkeypatch)
    assert outcome == []

    time.sleep(0.01)
    live.update(state="idle", since=datetime.now().astimezone().isoformat())
    with service_model.PageTransaction(claimed) as page:
        assert [event["id"] for event in delivery_model.deliverable(page)] == updates
    append_carried_log_record(
        claimed, {"kind": "error", "author": "page", "text": "moves the log"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")
    assert acknowledged_through(claimed) == 0

    assert handed_over("p2")[:3] == updates
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "escape_sandbox", lambda harness: None
    )
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "PreToolUse", "session_id": "s1", "prompt_id": "p2"},
    )
    assert acknowledged_through(claimed) > resolve["seq"]


def test_the_server_nudges_a_first_claiming_turn_escape_left_unwatched(
    claimed, interactive, monkeypatch
):
    """The turn that first claims a page started its prompt's watch before the
    session held one, so that watch ended at once (`hooks.cmd_watch`), and Escape
    ends the turn with no Stop hook to start another. The page's server reads the
    turn interrupted in Claude Code's record and messages the session for the
    comment that arrived meanwhile. While a watch holds the lease it sends nothing,
    since that watch wakes the session itself."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    live = {"state": "busy", "since": datetime.now().astimezone().isoformat()}
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "live_turn", lambda harness: dict(live)
    )
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(page) or True,
    )
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    server = server_rows_model.RowPublisher(claimed, "fixture-server")
    server.refresh()
    assert nudged == []

    time.sleep(0.01)
    live.update(state="idle", since=datetime.now().astimezone().isoformat())
    lease = leases_model.take_wait_lease(leases_model.waiter_lease_path(claimed, "s1"))
    server.live_until = 0
    server.refresh()
    assert nudged == []

    leases_model.release_lease(lease)
    server.live_until = 0
    server.refresh()
    assert nudged == [claimed]


def test_claude_codes_transcript_says_which_handovers_reached_the_model(tmp_path):
    """Claude Code writes a `hook_additional_context` record once a hook's output
    joins the conversation (the shape below is 2.1.310's), and none for a prompt
    Escape dropped. A reminder, another hook's context, a record still being written
    and a missing transcript show nothing."""
    delivery = {"batches": [{"events": [{"id": "e1"}, {"id": "e2"}]}]}
    inline = "\n".join(
        [hook_transport_model.INLINE_OPENING, json.dumps(delivery), "Leaf needs"]
    )
    records = [
        {"type": "user", "promptId": "p1", "message": {"content": "hi"}},
        {
            "type": "attachment",
            "attachment": {
                "type": "hook_additional_context",
                "content": [inline],
                "hookName": "PostToolBatch",
            },
        },
        {
            "type": "attachment",
            "attachment": {
                "type": "hook_additional_context",
                "content": ["Leaf needs attention: e3 is owed"],
            },
        },
    ]
    transcript = tmp_path / "session.jsonl"
    # The last record is still being written, so it ends partway through.
    being_written = json.dumps({**records[1], "uuid": "late"}).replace("e2", "e4")
    transcript.write_text(
        "".join(json.dumps(record) + "\n" for record in records)
        + being_written[: being_written.index("e4") + 5]
    )
    assert harness_model.claude_code_entered(transcript) == {"e1", "e2"}
    assert harness_model.claude_code_entered(tmp_path / "missing.jsonl") == set()
    (tmp_path / "empty.jsonl").write_text("")
    assert harness_model.claude_code_entered(tmp_path / "empty.jsonl") == set()
    assert (
        harness_model.ClaudeCodeHarness.hook_payload(
            {"hook_event_name": "Stop", "prompt_id": "p1"}
        )["turn_id"]
        == "p1"
    )


def test_receipt_never_passes_a_handover_the_transcript_does_not_show(
    claimed, interactive, monkeypatch, capsys
):
    """A Claude Code before 2.1.196 names no turn in its hooks, so the prompt it
    submits again after Escape dropped one renews Leaf's turn rather than opening
    another, and the comment handed into the dropped prompt still reads as awaiting
    its receipt. A comment the next tool boundary hands over then reaches the
    transcript alone. The cursor passes an input only with every one before it, so
    the receipt stops short of the dropped comment, and once the turn ends that
    comment is input again rather than received unseen."""
    shown: set[str] = set()
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "entered_context",
        lambda harness, payload: set(shown),
    )

    def hook(event: str) -> str:
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": event, "session_id": "s1"}
        )
        return capsys.readouterr().out

    dropped = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    assert dropped["id"] in hook("UserPromptSubmit")
    # Escape drops that prompt, and Claude Code submits it again.
    hook("UserPromptSubmit")
    later = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more"}
    )
    assert later["id"] in hook("PostToolBatch")
    shown.add(later["id"])
    hook("PostToolBatch")
    assert acknowledged_through(claimed) < dropped["seq"]

    hook("Stop")
    with service_model.PageTransaction(claimed) as page:
        assert dropped["id"] in [
            event["id"] for event in delivery_model.deliverable(page)
        ]


def test_a_step_opens_a_claude_code_turn_no_prompt_hook_named(claimed, capsys):
    """A claim's new lifetime mints a turn before any hook names one, and a prompt
    the user types while a turn runs gets its prompt hook at once under that turn's
    `prompt_id`, after which Escape submits it as a turn of its own under a new one
    (Claude Code 2.1.310). Either way the next step names a turn no prompt hook did,
    and it opens that turn, so its tool boundaries hand over input and its Stop hook
    closes it rather than passing over a turn Leaf does not know."""

    def hook(event: str, prompt: str) -> str:
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": event, "session_id": "s1", "prompt_id": prompt},
        )
        return capsys.readouterr().out

    assert not cleanup_model.session_record("s1")["provider"]
    hook("PostToolBatch", "p9")
    assert cleanup_model.session_record("s1")["turn"] == "p9"
    hook("Stop", "p9")
    assert cleanup_model.session_record("s1")["turn_closed"] is not None

    hook("UserPromptSubmit", "p10")
    # Typed while p10 runs; Escape ends p10 and the typed prompt runs as p11.
    hook("UserPromptSubmit", "p10")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    assert comment["id"] in hook("PostToolBatch", "p11")
    assert cleanup_model.session_record("s1")["turn"] == "p11"
    hook("Stop", "p11")
    assert cleanup_model.session_record("s1")["turn_closed"] is not None


def test_a_long_step_keeps_its_line_while_its_turn_runs_tools(claimed, capsys):
    """A start stands for as long as its turn is seen working, however long the step
    it names takes, so the status keeps the agent's line through a long stretch of
    tool calls rather than stalling once the line is a quarter of an hour old. The
    hook after each batch of tool calls shows the turn still working, and the turn,
    not the start's age, says whether the work goes on."""

    def hook(event: str) -> None:
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": event, "session_id": "s1", "prompt_id": "p1"},
        )
        capsys.readouterr()

    hook("UserPromptSubmit")
    long_ago = (
        datetime.now().astimezone()
        - activity_model.WORKING_GRACE
        - timedelta(minutes=1)
    )
    cleanup_model.write_session(
        {**cleanup_model.session_record("s1"), "turn_opened": long_ago.isoformat()}
    )
    mark = cleanup_model.session_file("s1", cleanup_model.HOOKS_SUFFIX)
    os.utime(mark, (long_ago.timestamp(), long_ago.timestamp()))
    long_ago = long_ago.isoformat(timespec="seconds")
    declare_work(
        claimed, "running the browser suite", ts=long_ago, session="s1", turn="p1"
    )
    assert activity_reading(claimed)["kind"] != "working"

    hook("PostToolBatch")
    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "running the browser suite",
    )


def test_a_boundary_handover_escape_kept_is_never_handed_over_twice(
    claimed, interactive, context_record, monkeypatch, capsys
):
    """Escape during a tool boundary's hooks keeps that boundary's context, so the
    transcript shows the comment the boundary handed over, and the turn ends with
    no later hook (Claude Code 2.1.308 and 2.1.310). The watch the turn's prompt
    started wakes the session once Claude Code reads the turn ended, since the
    comment may not have reached the model. The woken prompt's hook confirms what
    the transcript shows first, so it names the comment as owed rather than handing
    the delivery over again."""
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "escape_sandbox", lambda harness: None
    )
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    leases_model.mark_hooks("s1")
    live = {"state": "busy", "since": datetime.now().astimezone().isoformat()}
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "live_turn", lambda harness: dict(live)
    )
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt_id": "p1"},
    )
    capsys.readouterr()
    watch, outcome = prompt_watch("p1", monkeypatch)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "PostToolBatch", "session_id": "s1", "prompt_id": "p1"},
    )
    boundary = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert asked["id"] in boundary["additionalContext"]

    assert outcome == []
    time.sleep(0.01)
    live.update(state="idle", since=datetime.now().astimezone().isoformat())
    append_carried_log_record(
        claimed, {"kind": "error", "author": "page", "text": "moves the log"}
    )
    watch.join(timeout=STATED_TIMEOUT)
    [woke] = outcome
    assert woke.startswith(f"{claimed} has new input")

    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt_id": "p2"},
    )
    reminder = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert acknowledged_through(claimed) == asked["seq"]
    assert asked["id"] in reminder
    # The widget error that moved the log goes inline; the comment only as owed.
    [batch] = json.loads(reminder.split("\n")[1])["batches"]
    assert asked["id"] not in [event["id"] for event in batch["events"]]


def test_a_turn_ends_on_its_answer_and_a_turn_of_its_own_names_what_it_owes(
    claimed, interactive, capsys
):
    """Claude Code's focus view shows a turn's last message alone, so a Stop that
    continued a turn over an unanswered comment had the agent's note about it stand
    in place of the answer the turn had written. Where a watch follows the turn,
    Stop lets it end, and the watch wakes a turn of its own whose prompt names the
    owed answer. That prompt is the reminder on record, so a turn that ends owing
    the same answer again wakes nothing more."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "which ships first?"}
    )
    prompt = {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    stop = {"hook_event_name": "Stop", "session_id": "s1"}

    def left_owed() -> list[str]:
        with service_model.PageTransaction(claimed) as page:
            return [event["id"] for event in session_model.left_owed(page)]

    hooks_model.cmd_hook("claude-code", prompt)
    capsys.readouterr()
    assert left_owed() == []
    hooks_model.cmd_hook("claude-code", stop)
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    assert left_owed() == [asked["id"]]

    woke = hooks_model.cmd_watch("claude-code", stop)
    assert woke.startswith(f"{claimed} has an update still owed an answer")
    hooks_model.cmd_hook("claude-code", prompt)
    reminder = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert asked["id"] in reminder["additionalContext"]
    assert left_owed() == []

    hooks_model.cmd_hook("claude-code", stop)
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    assert left_owed() == []


def test_a_prompt_reopens_the_acknowledged_move_it_carries_into_the_new_turn(
    claimed, printing, capsys
):
    """The prompt hook's reminder is delivery evidence, not only prose.

    An unanswered move acknowledged in an earlier turn enters the next turn through
    additional context. Its receipt and page activity therefore advance to that new
    turn together instead of continuing to report only the turn that ended.
    """
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "still working on it?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    assert service_model.page_claim(claimed)["turn_closed"]

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    prompt = json.loads(capsys.readouterr().out)
    assert asked["id"] in prompt["hookSpecificOutput"]["additionalContext"]
    claim = service_model.page_claim(claimed)
    activity = activity_reading(claimed)
    assert activity["kind"] == "working"
    assert activity["obligations"][0]["stage"] == "picked_up"
    assert activity["obligations"][0]["delivery_turn"] == claim["turn"]
    assert activity["obligations"][0]["condition"] is None


def test_a_compaction_sends_the_agent_back_to_the_skill(claimed, capsys):
    """A compaction can drop the leaf skill, whose rules, such as putting every
    question for the user on On me, the agent follows while it holds a page. The
    SessionStart after one names the skill to read again; no other start or prompt
    does."""

    def start_context(source: str) -> str:
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": "SessionStart", "session_id": "s1", "source": source},
        )
        out = capsys.readouterr().out
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""

    skill = str(schema_model.SKILL_FILE)
    assert schema_model.SKILL_FILE.is_file()
    assert skill in start_context("compact")
    assert skill not in start_context("resume")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert skill not in capsys.readouterr().out


def test_agent_sees_the_complete_interaction_recovery(claimed, capsys, snapshot):
    """The real hook and CLI outputs, from the move's arrival through settlement:
    the Stop hook's watch wakes the session, and the prompt hook of the turn that
    opens hands the move over. That turn ends without answering it, so the watch
    wakes another, whose prompt names the answer it owes."""
    page = claimed
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    (page / "index.html").write_text(source)
    publish(page)
    session_model.cmd_waiting(page)
    observations = {}

    def hook(name):
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": name, "session_id": "s1"}
        )
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    def idle():
        result = CliRunner().invoke(cli_model.cli, ["page", "close", str(page)])
        return {
            "exit": result.exit_code,
            "stdout": result.stdout,
            "stderr": said(result.stderr),
        }

    # The turn ends over the page, and Leaf watches it from here.
    assert hook("Stop") is None
    sent = append_carried_log_record(
        page,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Add the camera first.",
        },
    )
    observations["idle before pickup"] = idle()
    serving(page, 1)
    observations["the watch wakes the session"] = hooks_model.cmd_watch(
        "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
    )
    # The context is an instruction line, the delivery on the next, then what the
    # turn owes; shown apart so the delivery reads as data.
    context = hook("UserPromptSubmit")["hookSpecificOutput"]["additionalContext"]
    instruction, delivery, *attention = context.split("\n")
    observations["delivered at prompt"] = {
        "instruction": instruction,
        "delivery": json.loads(delivery),
        "attention": "\n".join(attention),
    }
    envelope = json.loads(delivery)
    assert envelope["batches"][0]["events"][0]["id"] == sent["id"]
    session = service_model.page_claim(page)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page, session["id"])
    )
    assert lease
    try:
        # The turn ends on its own answer, and the watch wakes a turn of its own
        # whose prompt names what the comment is owed.
        observations["acknowledged at stop"] = hook("Stop")
        observations["the watch wakes the session to remind it"] = (
            hooks_model.cmd_watch(
                "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
            )
        )
        observations["reminded at prompt"] = hook("UserPromptSubmit")
        observations["idle before answer"] = idle()
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                envelope["batches"][0]["events"][0]["answer"]["ref"],
                "--text",
                "I will add the camera first.",
            ],
        )
        assert result.exit_code == 0, result.output
        observations["answer"] = (
            json.loads(result.output)
            if result.output.startswith("{")
            else result.output
        )
        observations["answered at stop"] = hook("Stop")
    finally:
        leases_model.release_lease(lease)
    snapshot.check(
        yaml_document(
            "Complete agent-facing outputs through real hooks, wait and thread reply commands.\n"
            "Only page paths, event/delivery/attempt and claim identities, and timestamps are normalized.\n"
            "A null hook output means the turn can end without a reminder.",
            _interaction_prompt_evidence(
                page,
                json.loads(
                    json.dumps(observations).replace(envelope["id"], "<delivery>")
                ),
            ),
        )
    )


def test_prompt_and_stop_reuse_the_original_unanswered_delivery(
    claimed, printing, capsys
):
    """A reminder recovers immutable input without capturing it again."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, asked["seq"])
    ref = delivered_ref(claimed, asked["id"])
    original = delivery_model.delivery_path(ref.partition(":")[0])
    captured = original.read_bytes()
    deliveries = set(original.parent.glob("*.json"))
    for name in ("UserPromptSubmit", "UserPromptSubmit", "Stop"):
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": name, "session_id": "s1"}
        )
        output = json.loads(capsys.readouterr().out)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert re.findall(r'<leaf-delivery id="(\w+)"', context) == [original.stem]
        assert set(original.parent.glob("*.json")) == deliveries
        assert original.read_bytes() == captured
        assert delivered_ref(claimed, asked["id"]) == ref


def inline_delivery(context: str) -> dict:
    """The delivery a hook handed over inline, from the context it added."""
    opening, envelope, *_ = context.split("\n")
    assert opening == hook_transport_model.INLINE_OPENING
    return json.loads(envelope)


def test_a_new_owners_prompt_delivers_the_update_its_predecessor_left_unanswered(
    claimed, capsys, monkeypatch
):
    """An update the previous owner received and left unanswered comes to the new
    owner with its other input, at a reference the new owner can answer through."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, asked["seq"])
    original = delivered_ref(claimed, asked["id"])
    with service_model.PageTransaction(claimed) as page:
        page.take_claim(harness_model.ClaudeCodeHarness("s2", "Claude"))
    assert (
        "ref"
        not in delivery_model.current_responses(
            claimed, events_model.read_events(claimed)
        )[asked["id"]]
    )
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    fresh = [
        append_carried_log_record(
            claimed, {"kind": "comment", "author": "user", "text": text}
        )
        for text in ("why C?", "why D?")
    ]
    captured = freeze_events(claimed, fresh)
    cleanup_model.open_session_turn("s2")
    delivery_model.receive(captured, "s2")

    cleanup_model.prompt_turn("s2")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s2"}
    )
    output = json.loads(capsys.readouterr().out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert re.findall(r'<leaf-delivery id="(\w+)"', context) == [captured["id"]]
    handed = inline_delivery(context)
    assert handed["id"] != original.partition(":")[0]
    [batch] = delivery_model.read_delivery(handed["id"])["batches"]
    assert [event["id"] for event in batch["events"]] == [asked["id"]]
    ref = delivered_ref(claimed, asked["id"])
    assert ref.startswith(f"{handed['id']}:")
    assert all(
        delivered_ref(claimed, event["id"]).startswith(f"{captured['id']}:")
        for event in fresh
    )
    reply = CliRunner().invoke(
        cli_model.cli, ["thread", "reply", "--done", ref, "--text", "Because."]
    )
    assert reply.exit_code == 0, reply.output
    assert asked["id"] not in {item["input"] for item in owed_answers(claimed)}


def test_hook_snapshot_serializes_receipt_and_reply(claimed, monkeypatch):
    """Receipt/reply cannot cross between the hook's log and cursor reading."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    [batch] = [
        plan.batch for plan in hook_transport_model.read_plans("s1") if plan.batch
    ]
    [frozen] = delivery_model.freeze_delivery([batch])["batches"]
    projected = hook_transport_model.read_page
    lock_proved = threading.Event()
    errors = []
    writers = []

    def read_while_settlement_waits(page_dir, events):
        def settle():
            try:
                with open(page_dir / schema_model.EVENTS_FILE, "r+b") as held:
                    try:
                        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        lock_proved.set()
                    else:
                        errors.append(
                            "receipt could enter between hook log and cursor reads"
                        )
                        lock_proved.set()
                delivery_model.receive_one(frozen, "s1")
                thread_model.post_reply(
                    page_dir,
                    {"parent": asked["id"], "responds": asked["id"]},
                    "Because B preserves the invariant",
                )
            except Exception as error:  # noqa: BLE001 - forward worker failures to assertion
                errors.append(error)

        writer = threading.Thread(target=settle, daemon=True)
        writers.append(writer)
        writer.start()
        assert lock_proved.wait(timeout=STATED_TIMEOUT), (
            "the settlement writer never tried the held lock"
        )
        return projected(page_dir, events)

    monkeypatch.setattr(hook_transport_model, "read_page", read_while_settlement_waits)
    plans = hook_transport_model.read_plans("s1")
    for writer in writers:
        writer.join(timeout=STATED_TIMEOUT)
        assert not writer.is_alive()
    assert not errors
    assert not plans[0].owed
    assert [event["id"] for event in plans[0].pending] == [asked["id"]]
    with service_model.PageTransaction(claimed) as page:
        assert not projected(claimed, page.events).work.obligations
        assert page.cursor >= asked["seq"]


def test_prompt_pickup_does_not_restamp_a_response_settled_after_planning(claimed):
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Already handled"}
    )
    [batch] = [
        plan.batch for plan in hook_transport_model.read_plans("s1") if plan.batch
    ]
    [frozen] = delivery_model.freeze_delivery([batch])["batches"]
    delivery_model.receive_one(frozen, "s1")
    plans = hook_transport_model.read_plans("s1")
    assert plans[0].acknowledged
    thread_model.post_reply(
        claimed, {"parent": asked["id"], "responds": asked["id"]}, "Handled"
    )
    before = events_model.read_events(claimed)
    hook_transport_model.pick_up_acknowledged("s1", plans)
    assert events_model.read_events(claimed) == before


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("pending", [False, True])
def test_newer_prompt_supersedes_hook_policy_before_effects(
    claimed, monkeypatch, capsys, named, pending
):
    turn = "provider" if named else None
    cleanup_model.prompt_turn("s1", turn)
    if pending:
        append_carried_log_record(
            claimed, {"kind": "comment", "author": "user", "text": "For the new prompt"}
        )
    policy = hook_transport_model.stop_continues
    newer = []

    def supersede(plans, handing, **policy_input):
        newer.append(cleanup_model.prompt_turn("s1", turn))
        return policy(plans, handing, **policy_input)

    monkeypatch.setattr(hook_transport_model, "stop_continues", supersede)
    hooks_model.cmd_hook(
        "claude-code",
        {
            "hook_event_name": "Stop",
            "session_id": "s1",
            **({"turn_id": turn} if turn else {}),
        },
    )
    assert capsys.readouterr().out == ""
    assert cleanup_model.session_record("s1") == newer[0]
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(claimed)
    )
    assert acknowledged_through(claimed) == 0


def test_a_hook_stopped_before_receipt_has_confirmed_nothing(
    claimed, printing, tmp_path, monkeypatch, capsys
):
    """A harness discards the output of a hook it stops, and reads it only once the
    hook exits, so a hook stopped as it begins confirming has handed nothing over
    and confirmed nothing, and the next hook hands the same input over again."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    for page in (claimed, sibling):
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
    receive = hook_transport_model.receive_held

    def stopped_before_receipt(delivery, session_id, expected, **_):
        raise SystemExit("the harness's timeout")

    monkeypatch.setattr(hook_transport_model, "receive_held", stopped_before_receipt)
    with pytest.raises(SystemExit):
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
        )
    assert capsys.readouterr().out == ""
    assert all(acknowledged_through(page) == 0 for page in (claimed, sibling))

    monkeypatch.setattr(hook_transport_model, "receive_held", receive)
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    retry = json.loads(
        json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ].split("\n")[1]
    )
    assert [len(batch["events"]) for batch in retry["batches"]] == [1, 1]
    assert all(
        handed(page, event["id"])
        for batch in retry["batches"]
        for page in [Path(batch["page"])]
        for event in batch["events"]
    )


def test_a_hook_confirms_nothing_into_a_turn_that_replaced_its_own(
    claimed, printing, monkeypatch, capsys
):
    """A hook reads its session's lifecycle once, and receipt follows that reading.
    A prompt that opens a newer turn in between leaves the input to that turn's
    own hook: the older one confirms nothing and hands what it read to its reader."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    receive = hook_transport_model.receive_held

    def prompted_first(delivery, session_id, expected, **kwargs):
        cleanup_model.close_session_turn(session_id)
        assert cleanup_model.prompt_turn(session_id) != expected
        return receive(delivery, session_id, expected, **kwargs)

    monkeypatch.setattr(hook_transport_model, "receive_held", prompted_first)
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert re.findall(r'<leaf-delivery id="(\w+)"', continued(capsys.readouterr().out))
    assert acknowledged_through(claimed) < comment["seq"]
    assert all(e["kind"] != "pickup" for e in events_model.read_events(claimed))


def test_a_watch_delivers_nothing_from_a_page_its_leaf_cannot_write(claimed):
    """Input on a page vendored at another protocol waits for a Leaf that can write
    the page: no receipt could be recorded for it here, so a watch that delivered it
    woke the session again on every pass, and a Codex watch offered it as a new turn
    each time. The prompt still names the page and the re-vendor that frees it."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    vendored_at_another_protocol(claimed)

    def delivered(reading):
        pytest.fail(f"{reading.page_dir} delivered input its Leaf cannot receipt")

    watch = session_model.Watch(harness_model.session_harness())
    try:
        assert watch.acquire()
        ticks = list(watch.tick())
        session_model.read_watch_pass(watch, None, delivered)
    finally:
        watch.release()
    assert [tick.batch for tick in ticks if tick.page_dir == claimed] == [[]]


def test_a_prompt_reminds_of_debt_on_a_page_its_leaf_cannot_write(claimed, capsys):
    """A prompt records the entry of acknowledged, unanswered updates into its turn
    as a pickup. On a page a newer Leaf vendored, which this Leaf may neither write
    nor take back, it records nothing and still reminds the turn of what it owes,
    naming why, rather than failing the hook and handing the turn nothing."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "still working?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    cleanup_model.close_session_turn("s1")
    vendored_at_another_protocol(claimed, newer=True)
    logged = events_model.read_events(claimed)

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "page protocol" in context
    [reminder] = re.findall(r'<leaf-delivery id="(\w+)"', context)
    [batch] = delivery_model.read_delivery(reminder)["batches"]
    assert [event["id"] for event in batch["events"]] == [asked["id"]]
    assert events_model.read_events(claimed) == logged


def test_a_prompt_re_vendors_a_page_an_older_leaf_vendored_and_hands_over_its_input(
    claimed, capsys, monkeypatch
):
    """A plugin update that bumps the page protocol leaves the session's page on the
    older Leaf's layer. The first prompt under the new Leaf re-vendors it, keeping its
    log, and hands over the input waiting there, so the user's comment reaches the
    turn with nothing asked of the agent first. The re-vendor runs inside the hook's
    time, which a loaded host can stretch past CONFIRM_WITHIN; that bound has its
    own tests."""
    monkeypatch.setattr(hook_transport_model, "CONFIRM_WITHIN", 600.0)
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    vendored_at_another_protocol(claimed)

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert context.startswith(hook_transport_model.INLINE_OPENING)
    assert "page protocol" not in context
    assert handed(claimed, comment["id"])
    assert event_contracts_model.write_refusal(claimed) is None
    assert session_runtime_model.selected_launcher("s1") is None


@pytest.mark.parametrize("selected", [False, True])
def test_a_checkout_that_re_vendors_a_page_delivers_for_its_session(
    claimed, tmp_path, selected
):
    """A command from a checkout, such as a worktree's `bin/leaf`, that re-vendors
    a page becomes its session's delivering Leaf, whether the session had no
    selection, as an installed plugin's doesn't, or had selected another, so its
    hooks and watch can still read the page."""
    if selected:
        other = tmp_path / "installed" / "bin" / "leaf"
        other.parent.mkdir(parents=True)
        other.write_text("#!/bin/sh\n")
        other.chmod(0o755)
        session_runtime_model.select_launcher("s1", other)
    vendored_at_another_protocol(claimed)

    vendoring_model.renew_layer(claimed, harness_model.session_harness(), command=True)

    assert event_contracts_model.write_refusal(claimed) is None
    own = session_runtime_model.own_launcher()
    assert session_runtime_model.selected_launcher("s1") == own


def test_a_prompt_captures_again_an_update_whose_delivery_an_older_leaf_wrote(
    claimed, capsys
):
    """An update an older Leaf delivered and the turn has not answered owes its
    answer through the reference that delivery printed, which this Leaf cannot
    read once the page protocol moved. So the update has no usable reference, and
    the prompt delivers it again rather than pointing the turn at a delivery it can
    neither read nor reply through."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "still working?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    old = delivered_ref(claimed, asked["id"]).partition(":")[0]
    written = delivery_model.delivery_path(old)
    envelope = json.loads(written.read_text(encoding="utf-8"))
    cleanup_model.write_json(written, {**envelope, "format": "leaf-delivery/0"})
    cleanup_model.close_session_turn("s1")

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert old not in context
    handed = inline_delivery(context)["id"]
    [batch] = delivery_model.read_delivery(handed)["batches"]
    assert [event["id"] for event in batch["events"]] == [asked["id"]]
    # Its receipt records the new ref, so no later hook hands it over again.
    assert delivered_ref(claimed, asked["id"]).startswith(f"{handed}:")
    with service_model.PageTransaction(claimed) as page:
        assert delivery_model.deliverable(page) == []


def test_a_hook_renews_no_page_another_session_took_after_it_listed_its_pages(
    claimed, monkeypatch
):
    """A hook lists its session's pages and then re-vendors each, and another session
    can take one in between. The re-vendor is then that session's to make, under its
    own Leaf, so this hook leaves the page as it found it."""
    vendored = vendored_at_another_protocol(claimed)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    service_model.claim_page(claimed)
    monkeypatch.setattr(hook_transport_model, "owned_pages", lambda _: [claimed])

    assert hook_transport_model.read_plans("s1") == []
    assert layer_record(claimed)["protocol"] == vendored


def test_a_re_vendor_a_newer_leaf_made_first_is_not_taken_back(claimed, monkeypatch):
    """Two versions of Leaf can each find the page vendored at a protocol they do not speak and
    each set out to re-vendor it. Whichever takes the page lock second finds the page
    the other left, and an older Leaf finding a newer Leaf's page leaves it there."""
    vendored_at_another_protocol(claimed)
    locked = vendoring_model.page_locked
    raced = iter([True])

    def newer_leaf_first(page_dir):
        if next(raced, False):
            # Another Leaf's own `page init` reaches the page before this one.
            record = layer_record(page_dir)
            (page_dir / schema_model.LAYER_FILE).unlink()
            LAYER.write(
                page_dir / schema_model.LAYER_FILE,
                {**record, "protocol": record["protocol"] + 2},
            )
        return locked(page_dir)

    monkeypatch.setattr(vendoring_model, "page_locked", newer_leaf_first)
    newer = layer_record(claimed)["protocol"] + 2

    assert (
        vendoring_model.renew_layer(
            claimed, harness_model.session_harness(), command=True
        )
        is None
    )
    assert layer_record(claimed)["protocol"] == newer


def test_a_prompt_offers_no_new_input_from_a_page_its_leaf_cannot_write(
    claimed, capsys
):
    """A prompt hands over no delivery of fresh input on a page a newer Leaf
    vendored, whose receipt this Leaf would refuse and which it does not take back:
    a pointer to it could never be confirmed, so every later prompt or Stop offered
    the same input again. It names the page protocol and the re-vendor instead, and
    the input waits on the page for the first prompt after the page is writable
    again."""
    stamp = claimed / schema_model.LAYER_FILE
    vendored = layer_record(claimed)
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    vendored_at_another_protocol(claimed, newer=True)

    def prompt() -> str:
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
        )
        return json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]

    refused = prompt()
    assert "page protocol" in refused
    assert hook_transport_model.INLINE_OPENING not in refused
    assert acknowledged_through(claimed) < comment["seq"]

    stamp.unlink()
    LAYER.write(stamp, vendored)
    assert prompt().startswith(hook_transport_model.INLINE_OPENING)
    assert handed(claimed, comment["id"])


def test_a_hook_waits_on_no_receipt_lock_past_its_deadline(
    claimed, printing, tmp_path, monkeypatch, capsys
):
    """A hook that waited on a page's lock into its harness's timeout would have
    its output discarded after confirming the pages before it. So it waits for a
    receipt's locks only until CONFIRM_WITHIN, hands over the pages it recorded, and
    leaves the input of a page still locked then pending for a later hook."""
    monkeypatch.setattr(hook_transport_model, "CONFIRM_WITHIN", 2.0)
    # Only lock waits advance this clock: page preparation must not spend the
    # budget before the test reaches the contended receipt lock.
    elapsed = 0.0

    def advance(seconds):
        nonlocal elapsed
        elapsed += seconds

    clock = SimpleNamespace(monotonic=lambda: elapsed, sleep=advance)
    for module in (hooks_model, hook_transport_model, cleanup_model):
        monkeypatch.setattr(module, "time", clock)
    sibling = tmp_path / "sibling"  # after `claimed` in the walk's path order
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    for page in (claimed, sibling):
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
    freeze = hook_transport_model.freeze_delivery
    held = service_model.PageTransaction(sibling)

    def freeze_then_lock_sibling(batches, **kwargs):
        delivery = freeze(batches, **kwargs)
        held.__enter__()
        return delivery

    monkeypatch.setattr(
        hook_transport_model, "freeze_delivery", freeze_then_lock_sibling
    )
    try:
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
        )
        assert elapsed == pytest.approx(hook_transport_model.CONFIRM_WITHIN)
        _, envelope, *_ = continued(capsys.readouterr().out).split("\n")
        assert [batch["page"] for batch in json.loads(envelope)["batches"]] == [
            str(claimed.resolve())
        ]
    finally:
        held.__exit__(None, None, None)
    assert any(e["kind"] == "pickup" for e in events_model.read_events(claimed))
    assert acknowledged_through(sibling) == 0
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(sibling))
    # Past the deadline even a free lock is not taken, so nothing is confirmed late.
    with (
        pytest.raises(TimeoutError),
        service_model.PageTransaction(sibling, deadline=clock.monotonic()),
    ):
        pass


def test_a_hook_too_slow_to_confirm_hands_over_a_pointer(
    claimed, printing, monkeypatch, capsys
):
    """A hook past CONFIRM_WITHIN may be past its harness's timeout by the time it
    exits, which would discard what it printed, so it confirms nothing and hands
    over a pointer; the session confirms after reading it. Reading after the turn
    ended changes nothing; explicit confirmation observes a fresh unnamed turn."""
    monkeypatch.setattr(hook_transport_model, "CONFIRM_WITHIN", 0)
    event = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    [delivery_id] = re.findall(
        r'<leaf-delivery id="(\w+)"', continued(capsys.readouterr().out)
    )
    assert acknowledged_through(claimed) < event["seq"]
    assert delivery_model.read_delivery(delivery_id)["acknowledge"] is None

    cleanup_model.close_session_turn("s1")
    closed = cleanup_model.session_record("s1")
    read = CliRunner().invoke(cli_model.cli, ["delivery", "read", delivery_id])
    assert read.exit_code == 0, read.output
    assert json.loads(read.output)["id"] == delivery_id
    assert cleanup_model.session_record("s1") == closed
    assert acknowledged_through(claimed) < event["seq"]
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(claimed))

    confirmed = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id])
    assert confirmed.exit_code == 0, confirmed.output
    current = cleanup_model.session_record("s1")
    assert current["turn"] != closed["turn"]
    assert current["turn_closed"] is None
    assert acknowledged_through(claimed) == event["seq"]
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    assert (pickup["kind"], pickup["events"], pickup["turn"]) == (
        "pickup",
        [event["id"]],
        cleanup_model.session_record("s1")["turn"],
    )


def test_a_hooks_handover_commits_its_pickup_before_session_end(
    claimed, printing, monkeypatch, capsys
):
    event = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    attempting = threading.Event()
    ended = threading.Event()

    def end():
        attempting.set()
        cleanup_model.end_session("s1")
        ended.set()

    thread = threading.Thread(target=end)
    pickup = delivery_model.record_pickup

    def pickup_while_end_attempts(*args, **kwargs):
        thread.start()
        assert attempting.wait(STATED_TIMEOUT), (
            "the session end never attempted its lock"
        )
        # Observe the actual lock ownership, rather than relying on scheduling
        # an end call to happen before this short receipt transaction completes.
        with (
            open(cleanup_model.session_lock_path("s1"), "a+") as lock,
            pytest.raises(BlockingIOError),
        ):
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not ended.is_set()
        assert cleanup_model.session_record("s1")["ended"] is None
        return pickup(*args, **kwargs)

    monkeypatch.setattr(delivery_model, "record_pickup", pickup_while_end_attempts)
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)
    thread.join(STATED_TIMEOUT)
    assert not thread.is_alive(), "the session end never finished"
    assert ended.is_set()
    assert handed(claimed, event["id"])
