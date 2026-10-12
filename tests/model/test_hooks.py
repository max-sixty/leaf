"""The prompt and Stop hooks as a delivery route: opening and closing the session's
turn on every page it holds, handing pending input over inline or as a pointer, and
confirming what they hand over within their deadline."""

import fcntl
import json
import re
import shutil
import threading
import time
from xml.etree import ElementTree

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    _interaction_prompt_evidence,
    _watched,
    append_carried_log_record,
    codex_records,
    continued,
    declare_idle,
    delivered,
    delivered_ref,
    last_deliverable_seq,
    page_state,
    publish,
    receive_through,
    record_claim,
    serving,
    vendored_at_another_protocol,
    working,
    yaml_document,
)
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hook_transport as hook_transport_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import presence as presence_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import vendoring as vendoring_model


def test_the_stop_hook_records_the_ending_of_the_turn_behind_a_claim(claimed, capsys):
    """A `working` claim is written by a model's turn, and a turn can end at any token
    without running anything — so nothing writes its close, and the page was left to
    find an abandoned claim by outwaiting a clock. The Stop hook is the harness
    watching that same moment, which is what these hooks are for.

    It stamps whether or not it has a nudge to make, and ahead of both of the guard's
    early returns: a turn that ends with nothing outstanding is exactly the turn that
    walks away from a `working` claim. The stamp is provenance and lands on the claim
    record rather than in status.json — what the agent said it was doing stays the
    agent's to write, which is the line SessionEnd already draws."""
    working(claimed, "reading the reconnect traces")
    assert service_model.page_claim(claimed)["turn_closed"] is None
    events = events_model.read_events(claimed)
    assert presence_model.presence(claimed, events)["turn_closed"] is None

    # A live watcher: the guard has nothing to say, and the ending is recorded anyway.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
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
    claimed, tmp_path, capsys
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
    capsys.readouterr()
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
    capsys.readouterr()
    working(others, "another session's page")
    serving(others, 3)
    assert service_model.claim_page(others)
    claim = service_model.page_claim(others)
    record_claim(others, **{**claim, "id": "s2", "turn_closed": "then"})
    append_carried_log_record(
        claimed, {"kind": "comment", "id": "c2", "author": "user", "text": "two"}
    )
    # The Stop hook delivers this one into the running turn itself.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    [batch] = json.loads(reason.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == ["c2"]
    assert service_model.page_claim(others)["turn_closed"] == "then"
    declare_idle(sibling)
    declare_idle(others)


def test_the_prompt_hook_opens_the_turn_on_every_page_the_session_holds(
    claimed, tmp_path, capsys
):
    """A delivery is not the only observable opening, and it is not the one the
    banner sends the user to. The `quiet` banner says to nudge in the terminal;
    a user who does that answers where no batch is written, so no transport ever
    hands one over and nothing would clear the stamp — the page would go on telling
    them to do the thing they just did.

    `UserPromptSubmit` is the literal mirror of the `Stop` branch that stamps the
    ending: same sweep over `owned_pages`, same place ahead of the early returns,
    same session scope."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    capsys.readouterr()
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

    status_before = files_model.read_json(claimed / "status.json")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"] is None
    assert service_model.page_claim(sibling)["turn_closed"] is None
    # Only the stamp moves: what the agent said it was doing stays the agent's.
    assert files_model.read_json(claimed / "status.json") == status_before

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


def test_a_named_wait_does_not_invent_turn_entry(claimed, capsys):
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
    status_before = files_model.read_json(claimed / "status.json")

    assert session_model.cmd_wait(claimed) == 0
    capsys.readouterr()
    assert service_model.page_claim(claimed)["turn_closed"]
    assert files_model.read_json(claimed / "status.json") == status_before
    assert files_model.read_json(claimed / "cursor.json") is None
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


def test_a_stop_that_hands_over_input_keeps_the_turn_open(claimed, capsys):
    """Input that arrives as the turn ends goes into that same turn, so the Stop
    that hands it over blocks, and the turn it hands the input to is the one still
    running: not closed, and not closed and reopened as another. The repeated Stop
    that follows with nothing new is the turn really ending."""
    session_model.cmd_waiting(claimed, "")
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
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
    pickup = events_model.read_events(claimed)[-1]
    assert (pickup["kind"], pickup["turn"]) == ("pickup", session["turn"])

    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed)["turn_closed"]
    leases_model.release_lease(lease)


def test_a_repeated_stop_is_held_open_only_by_the_users_input(claimed, capsys):
    """A repeated Stop takes the user's input into the turn, and nothing else. A
    page's own errors and a worker's reports arrive unpaced, so a turn that
    blocked on each would never end; they stay pending for the next turn, and go
    in with the user's move when one arrives."""
    error = append_carried_log_record(
        claimed, {"kind": "error", "author": "page", "message": "a widget threw"}
    )
    repeated = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}

    hooks_model.cmd_hook("claude-code", repeated)
    assert capsys.readouterr().out == ""
    assert files_model.read_json(claimed / "cursor.json") is None
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
    assert files_model.read_json(claimed / "cursor.json") == {
        "seq": last_deliverable_seq(claimed)
    }


@pytest.mark.parametrize("repeated", [False, True])
def test_codex_stop_leaves_quiet_input_but_delivers_the_whole_batch_with_owed_input(
    page_dir, codex_loop, capsys, repeated
):
    """A live adapter handles quiet updates after Stop. An owed user message keeps
    that turn open and brings all earlier pending updates into its one delivery.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "quiet")
    waiter = _watched(page_dir)
    adapter = leases_model.take_lease(leases_model.adapter_lease_path("codex-thread"))
    assert adapter
    try:
        asked = append_carried_log_record(
            page_dir, {"kind": "comment", "author": "user", "text": "why?"}
        )
        receive_through(page_dir, last_deliverable_seq(page_dir))
        thread_model.post_reply(
            page_dir, {"to": asked["id"], "for": asked["id"]}, "Because."
        )
        cursor = events_model.read_cursor(page_dir)
        quiet = [
            append_carried_log_record(
                page_dir, {"kind": "resolve", "author": "user", "parent": asked["id"]}
            ),
            append_carried_log_record(
                page_dir,
                {"kind": "error", "author": "page", "message": "a widget threw"},
            ),
        ]
        cleanup_model.prompt_turn("codex-thread", "quiet")
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "quiet",
                "stop_hook_active": repeated,
            },
        )
        assert capsys.readouterr().out == ""
        assert cleanup_model.session_record("codex-thread")["turn_closed"]
        assert events_model.read_cursor(page_dir) == cursor
        assert not codex_records("codex-thread")
        assert [
            event["id"]
            for event in service_model.unacknowledged(
                events_model.read_events(page_dir), cursor
            )
        ] == [event["id"] for event in quiet]

        cleanup_model.prompt_turn("codex-thread", "owed")
        comment = append_carried_log_record(
            page_dir, {"kind": "comment", "author": "user", "text": "is it broken?"}
        )
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "owed",
                "stop_hook_active": repeated,
            },
        )
        answer = json.loads(capsys.readouterr().out)
        assert answer["decision"] == "block"
        [pointer_xml] = re.findall(r"<leaf-delivery\b[^>]*?/>", answer["reason"])
        pointer = ElementTree.fromstring(pointer_xml)
        read = CliRunner().invoke(
            cli_model.cli, ["delivery", "read", pointer.attrib["id"]]
        )
        assert read.exit_code == 0, read.output
        [batch] = json.loads(read.output)["batches"]
        assert [event["id"] for event in batch["events"]] == [
            *(event["id"] for event in quiet),
            comment["id"],
        ]
        assert cleanup_model.session_record("codex-thread")["turn_closed"] is None
    finally:
        adapter.close()
        leases_model.release_lease(waiter)


def test_a_page_that_changed_hands_before_receipt_keeps_its_input(
    claimed, tmp_path, monkeypatch, capsys
):
    """The hook confirms a delivery only for the pages its session still holds as
    it confirms, and hands what it could not confirm to its reader as a pointer. A
    page another session took after capture keeps its input pending, and once this
    session holds it again, its next hook hands that input over."""
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
    [delivery_id] = re.findall(
        r"`leaf delivery read (\w+)`", continued(capsys.readouterr().out)
    )
    delivery = delivery_model.read_delivery(delivery_id)
    assert [batch["page"] for batch in delivery["batches"]] == [
        str(moved),
        str(claimed),
    ]
    assert service_model.page_claim(moved)["id"] == "s2"
    assert files_model.read_json(moved / "cursor.json") is None
    assert all(e["kind"] != "pickup" for e in events_model.read_events(moved))
    assert events_model.read_cursor(claimed) >= comments[claimed]["seq"]

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
    assert events_model.read_cursor(moved) >= comments[moved]["seq"]


def test_input_too_large_for_the_turn_goes_as_a_pointer_its_reader_confirms(
    claimed, capsys
):
    """Claude Code replaces a hook context of HOOK_CONTEXT_LIMIT characters or more
    with a preview, so confirming it on handover would confirm what the model never
    read. Input that large goes as a pointer instead: the hook confirms nothing, and
    the reader confirms after every part reaches its context."""
    comment = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "x" * hook_transport_model.HOOK_CONTEXT_LIMIT,
        },
    )

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    reason = continued(answer)
    assert len(reason) < hook_transport_model.HOOK_CONTEXT_LIMIT
    [delivery_id] = re.findall(r"`leaf delivery read (\w+)`", reason)
    assert answer[hook_transport_model.DELIVERY_FIELD] == {
        "id": delivery_id,
        "inline": False,
    }
    assert files_model.read_json(claimed / "cursor.json") is None
    assert all(e["kind"] != "pickup" for e in events_model.read_events(claimed))

    # Confirmed by a command the model runs anyway, and which only confirms: the
    # session's watch is its Stop hook, which a wait the model ran would only take
    # the lease from.
    read = CliRunner().invoke(cli_model.cli, ["delivery", "read", delivery_id])
    assert read.exit_code == 0, read.output
    pointer = json.loads(read.output)
    assert f"leaf delivery ack {delivery_id}" in pointer["acknowledge"]
    confirmed = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id])
    assert confirmed.exit_code == 0, confirmed.output
    [batch] = pointer["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert files_model.read_json(claimed / "cursor.json") == {
        "seq": last_deliverable_seq(claimed)
    }


def test_a_hooks_delivery_field_is_independent_of_its_prose(monkeypatch):
    """A hook's output names the delivery it hands over, inline or by pointer, in a
    field of its own, which Leaf's hooks module and an eval's reading of a trace
    read. Rewording the context the model reads changes neither the field nor that
    reading."""
    from leaf_dev.arms import hook_delivered

    harness = harness_model.ClaudeCodeHarness("s1", "Claude")
    delivery = {"id": "d1", "batches": []}

    def outputs() -> list[dict]:
        return [
            hook_transport_model.render(harness, "Stop", delivery, [], confirm=confirm)
            for confirm in (lambda: True, lambda: False)
        ]

    def contexts(answers: list[dict]) -> list[str]:
        return [answer["hookSpecificOutput"]["additionalContext"] for answer in answers]

    field = hook_transport_model.DELIVERY_FIELD
    before = outputs()
    monkeypatch.setattr(hook_transport_model, "INLINE_OPENING", "Reworded.")
    monkeypatch.setattr(hook_transport_model, "POINTED_OPENING", "Reworded:")
    after = outputs()
    assert all(a != b for a, b in zip(contexts(after), contexts(before), strict=True))
    assert [answer[field] for answer in after] == [
        {"id": "d1", "inline": True},
        {"id": "d1", "inline": False},
    ]
    assert [answer[field] for answer in before] == [answer[field] for answer in after]
    assert all(
        hook_delivered({"subtype": "hook_response", "output": json.dumps(answer)})
        for answer in after
    )


def test_hook_drops_a_page_transferred_after_ownership_discovery(claimed, monkeypatch):
    """Ownership transfer before the planner's page lock belongs to the new owner."""
    session_model.cmd_waiting(claimed, "")
    discover = hook_transport_model.owned_pages

    def transfer(session_id):
        pages = discover(session_id)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
        assert service_model.claim_page(claimed)
        return pages

    monkeypatch.setattr(hook_transport_model, "owned_pages", transfer)
    assert hook_transport_model.remedies(hook_transport_model.read_plans("s1")) == []


def test_claude_codes_hook_confirms_the_input_it_hands_over(claimed, capsys):
    """Claude Code's prompt hook runs as every turn begins, including the one a
    background wait's ending opens, and its Stop hook as a turn ends; each hands
    the turn the whole pending delivery inline and confirms it itself, so the move
    reads Picked up as the hook hands it over, the envelope names no
    acknowledgement, and the model runs none."""
    working(claimed, "revising")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert page_state(claimed)["pending"] == 1
    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "sent"
    # A running wait changes nothing: it only wakes the session.
    session = service_model.page_claim(claimed)
    lease = leases_model.take_lease(
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
    assert page_state(claimed)["pending"] == 0
    [workflow] = page_state(claimed)["workflows"]
    assert workflow["stage"] == "picked_up"
    pickup = events_model.read_events(claimed)[-1]
    claim = service_model.page_claim(claimed)
    assert (pickup["kind"], pickup["phase"], pickup["events"]) == (
        "pickup",
        "opened",
        [comment["id"]],
    )
    assert (pickup["session"], pickup["turn"]) == (claim["id"], claim["turn"])

    # Input that arrives as the turn ends comes back into that same turn.
    later = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more"}
    )
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    blocked = json.loads(capsys.readouterr().out)
    assert "decision" not in blocked
    later_delivery = json.loads(continued(blocked).split("\n")[1])
    assert later_delivery["acknowledge"] is None
    [batch] = later_delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [later["id"]]
    assert page_state(claimed)["pending"] == 0
    pickup = events_model.read_events(claimed)[-1]
    assert (pickup["kind"], pickup["events"], pickup["turn"]) == (
        "pickup",
        [later["id"]],
        claim["turn"],
    )


def test_a_prompt_reopens_the_acknowledged_move_it_carries_into_the_new_turn(
    claimed, capsys
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
    activity = page_state(claimed)["activity"]
    assert activity["kind"] == "working"
    assert activity["obligations"][0]["stage"] == "picked_up"
    assert activity["obligations"][0]["delivery_turn"] == claim["turn"]
    assert activity["obligations"][0]["condition"] is None


def test_agent_sees_the_complete_interaction_recovery(claimed, capsys, snapshot):
    """The real hook and CLI outputs, from the move's arrival through settlement:
    the Stop hook's watch wakes the session, and the prompt hook of the turn that
    opens hands the move over."""
    page = claimed
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    (page / "index.html").write_text(source)
    publish(page)
    session_model.cmd_waiting(page, "")
    observations = {}

    def hook(name):
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": name, "session_id": "s1"}
        )
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    def idle():
        result = CliRunner().invoke(cli_model.cli, ["status", str(page), "idle"])
        return {"exit": result.exit_code, "output": result.output}

    # The turn ends over the page, and its Stop hook watches from here.
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
    lease = leases_model.take_lease(leases_model.waiter_lease_path(page, session["id"]))
    assert lease
    try:
        observations["acknowledged at stop"] = hook("Stop")
        observations["idle before answer"] = idle()
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "response",
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
            "Complete agent-facing outputs through real hooks, wait and response commands.\n"
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


def test_a_recovery_reading_records_the_refs_an_older_receipt_lacked(claimed, capsys):
    """A receipt an older Leaf wrote carries no refs. The prompt re-presents the
    owed message, recording its pickup in this turn, and hands a recovery reading
    with fresh references; confirming that reading in the same turn records them,
    though the transition itself is already on record."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    [batch] = [
        plan.batch for plan in hook_transport_model.read_plans("s1") if plan.batch
    ]
    with (
        service_model.PageTransaction(claimed) as page,
        delivery_model.receive_batch(page, batch, session_id="s1") as events,
    ):
        delivery_model.record_pickup(page, events, session="s1")
    assert (
        "ref"
        not in delivery_model.current_responses(
            claimed, events_model.read_events(claimed)
        )[asked["id"]]
    )

    cleanup_model.prompt_turn("s1")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [recovery] = re.findall(r'<leaf-delivery id="(\w+)"', context)
    delivery_model.receive_delivery(recovery)
    assert delivered_ref(claimed, asked["id"]).startswith(f"{recovery}:")


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
                    {"to": asked["id"], "for": asked["id"]},
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
    thread_model.post_reply(claimed, {"to": asked["id"], "for": asked["id"]}, "Handled")
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

    def supersede(plans, handing, *, repeated):
        newer.append(cleanup_model.prompt_turn("s1", turn))
        return policy(plans, handing, repeated=repeated)

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
    assert events_model.read_cursor(claimed) == 0


def test_a_hook_stopped_before_receipt_has_confirmed_nothing(
    claimed, tmp_path, monkeypatch, capsys
):
    """A harness discards the output of a hook it stops, and reads it only once the
    hook exits, so a hook stopped as it begins confirming has handed nothing over
    and confirmed nothing, and the next hook hands the same input over again."""
    sibling = tmp_path / "sibling"
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    capsys.readouterr()
    for page in (claimed, sibling):
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Please answer"}
        )
    receive = hook_transport_model.receive_held

    def stopped_before_receipt(delivery, session_id, expected, *, deadline):
        raise SystemExit("the harness's timeout")

    monkeypatch.setattr(hook_transport_model, "receive_held", stopped_before_receipt)
    with pytest.raises(SystemExit):
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
        )
    assert capsys.readouterr().out == ""
    assert all(events_model.read_cursor(page) == 0 for page in (claimed, sibling))

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
    assert all(events_model.read_cursor(page) > 0 for page in (claimed, sibling))


def test_a_hook_confirms_nothing_into_a_turn_that_replaced_its_own(
    claimed, monkeypatch, capsys
):
    """A hook reads its session's lifecycle once, and receipt follows that reading.
    A prompt that opens a newer turn in between leaves the input to that turn's
    own hook: the older one confirms nothing and hands what it read to its reader."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    receive = hook_transport_model.receive_held

    def prompted_first(delivery, session_id, expected, *, deadline):
        cleanup_model.close_session_turn(session_id)
        assert cleanup_model.prompt_turn(session_id) != expected
        return receive(delivery, session_id, expected, deadline=deadline)

    monkeypatch.setattr(hook_transport_model, "receive_held", prompted_first)
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert re.findall(r"`leaf delivery read (\w+)`", continued(capsys.readouterr().out))
    assert events_model.read_cursor(claimed) < comment["seq"]
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
    as a pickup. On a page vendored at another protocol, which this Leaf may not
    write, it records nothing and still reminds the turn of what it owes, naming
    why, rather than failing the hook and handing the turn nothing."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "still working?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    cleanup_model.close_session_turn("s1")
    vendored_at_another_protocol(claimed)
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


def test_a_prompt_offers_no_new_input_from_a_page_its_leaf_cannot_write(
    claimed, capsys
):
    """A prompt hands over no delivery of fresh input on a page vendored at another
    protocol, whose receipt this Leaf would refuse: a pointer to it could never be
    confirmed, so every later prompt or Stop offered the same input again. It names
    the page protocol and the re-vendor instead, and the input waits on the page for
    the first prompt after the page is writable again."""
    stamp = claimed / "registry.json"
    vendored = stamp.read_text(encoding="utf-8")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Please answer"}
    )
    vendored_at_another_protocol(claimed)

    def prompt() -> dict:
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
        )
        out = capsys.readouterr().out
        return json.loads(out) if out else {}

    refused = prompt()
    assert "page protocol" in refused["hookSpecificOutput"]["additionalContext"]
    assert hook_transport_model.DELIVERY_FIELD not in refused
    assert events_model.read_cursor(claimed) < comment["seq"]

    cleanup_model.write_json(stamp, json.loads(vendored))
    assert hook_transport_model.DELIVERY_FIELD in prompt()
    assert events_model.read_cursor(claimed) >= comment["seq"]


def test_a_hook_waits_on_no_receipt_lock_past_its_deadline(
    claimed, tmp_path, monkeypatch, capsys
):
    """A hook that waited on a page's lock into its harness's timeout would have
    its output discarded after confirming the pages before it. So it waits for a
    receipt's locks only until CONFIRM_WITHIN, and leaves a page still locked then
    to the reader of the pointer it hands over, having confirmed the rest."""
    monkeypatch.setattr(hook_transport_model, "CONFIRM_WITHIN", 2.0)
    sibling = tmp_path / "sibling"  # after `claimed` in the walk's path order
    vendoring_model.cmd_init(sibling)
    service_model.claim_page(sibling)
    capsys.readouterr()
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
        started = time.monotonic()
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "Stop", "session_id": "s1"}
        )
        assert time.monotonic() - started < 2 * hook_transport_model.CONFIRM_WITHIN
        [delivery_id] = re.findall(
            r"`leaf delivery read (\w+)`", continued(capsys.readouterr().out)
        )
        envelope = delivery_model.read_delivery(delivery_id)
        assert [batch["page"] for batch in envelope["batches"]] == [
            str(claimed.resolve()),
            str(sibling.resolve()),
        ]
    finally:
        held.__exit__(None, None, None)
    assert events_model.read_cursor(claimed) > 0
    assert events_model.read_cursor(sibling) == 0
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(sibling))
    # Past the deadline even a free lock is not taken, so nothing is confirmed late.
    with (
        pytest.raises(TimeoutError),
        service_model.PageTransaction(sibling, deadline=time.monotonic()),
    ):
        pass


def test_a_hook_too_slow_to_confirm_hands_over_a_pointer(claimed, monkeypatch, capsys):
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
        r"`leaf delivery read (\w+)`", continued(capsys.readouterr().out)
    )
    assert events_model.read_cursor(claimed) < event["seq"]
    assert delivery_model.read_delivery(delivery_id)["acknowledge"] is None

    cleanup_model.close_session_turn("s1")
    closed = cleanup_model.session_record("s1")
    read = CliRunner().invoke(cli_model.cli, ["delivery", "read", delivery_id])
    assert read.exit_code == 0, read.output
    assert json.loads(read.output)["id"] == delivery_id
    assert cleanup_model.session_record("s1") == closed
    assert events_model.read_cursor(claimed) < event["seq"]
    assert not any(e["kind"] == "pickup" for e in events_model.read_events(claimed))

    confirmed = CliRunner().invoke(cli_model.cli, ["delivery", "ack", delivery_id])
    assert confirmed.exit_code == 0, confirmed.output
    current = cleanup_model.session_record("s1")
    assert current["turn"] != closed["turn"]
    assert current["turn_closed"] is None
    assert events_model.read_cursor(claimed) == event["seq"]
    pickup = events_model.read_events(claimed)[-1]
    assert (pickup["kind"], pickup["events"], pickup["turn"]) == (
        "pickup",
        [event["id"]],
        cleanup_model.session_record("s1")["turn"],
    )


def test_a_hooks_receipt_commits_pickup_and_cursor_before_session_end(
    claimed, monkeypatch, capsys
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
    assert events_model.read_cursor(claimed) == event["seq"]
