"""The guard on a turn's end: the Stop hook holding a turn over a page nothing
watches or a move the agent still owes, `leaf page close` refusing over input
nobody answered, and the reminders both write."""

import fcntl
import json
import os
import re
import shutil
import time
from xml.etree import ElementTree

import pytest
from click.testing import CliRunner
from conftest import hooks_run_this_tree
from interact_support import (
    PAGE,
    PAGE_GROUP,
    PICKS_PAGE,
    STATED_TIMEOUT,
    Prose,
    _start,
    _watched,
    acknowledged_through,
    adapter_lease,
    append_carried_log_record,
    append_command,
    codex_records,
    consume_pending_input,
    continued,
    declare_idle,
    declare_on_page,
    declared,
    delivered_ref,
    delivery_through,
    end_work,
    freeze_events,
    inlined,
    last_deliverable_seq,
    let_a_pick_settle_a_thread,
    obligations_on_user,
    owed,
    owed_answers,
    page_state,
    publish,
    queue_board_registry,
    receive_through,
    record_claim,
    response_reference,
    spawn_probe,
    stamp,
    state_json,
    woken,
    working,
    write_record,
    yaml_document,
)

from leaf.agents import delivery as delivery_model
from leaf.agents import thread as thread_model
from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import schema as schema_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.base.json_block import read_json_block
from leaf.base.service import PREVIEW
from leaf.commands import cli as cli_model
from leaf.commands import hooks as hooks_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.records import activity as activity_model
from leaf.records import revisioning as revisioning_model
from leaf.records import transaction as transaction_model
from leaf.source import vocabulary as vocabulary_model
from leaf.source.registry import contract as registry_contract
from leaf.source.registry import storage as registry_storage


def test_a_completed_stream_answers_its_event_even_when_the_reply_address_differs():
    obligation = {
        "input": "widget-action",
        "seq": 1,
        "queued": False,
        "answer": {
            "kind": "reply",
            "writer": "turn",
            "parent": "widget-owner-thread",
            "responds": "widget-action",
            "attempt": "leaf-delivery-1",
        },
        "response": {
            "state": "active",
            "settles": True,
            "attempt": "leaf-delivery-1",
            "turn": "leaf-turn",
        },
    }

    def blocking(obligation: dict, *, watched: bool) -> list[dict]:
        state = {
            "activity": {"obligations": [obligation]},
            "cursor": 1,
            "turn": "leaf-turn",
        }
        return activity_model.blocking_obligations(state, watched=watched)

    assert blocking(obligation, watched=True) == []
    # Nothing is left to commit the draft once its watcher is gone.
    assert blocking(obligation, watched=False) == [obligation]
    # A plain reply is `leaf thread reply`'s to write, whatever a draft says.
    plain = {**obligation, "answer": {**obligation["answer"], "writer": "agent"}}
    assert blocking(plain, watched=True) == [plain]


def test_stop_hook_does_not_borrow_a_foreign_bare_waiter_lease(page_dir, monkeypatch):
    """A page-local lease proves only an unclaimed bare-shell watch."""
    session_model.cmd_waiting(page_dir)
    bare = leases_model.take_wait_lease(page_dir / "waiter.lock")
    assert bare
    try:
        assert page_state(page_dir)["listening"]
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "harness-owner")
        hooks_run_this_tree("harness-owner")
        monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
        assert transaction_model.claim_page(page_dir)
        claim = service_model.page_claim(page_dir)
        assert claim is not None
        lease_path_4 = leases_model.waiter_lease_path(page_dir, claim["id"])
        assert lease_path_4 is not None
        assert not leases_model.lock_is_held(lease_path_4)
        assert leases_model.lock_is_held(page_dir / "waiter.lock")
        assert not page_state(page_dir)["listening"]

        cleanup_model.end_session(claim["id"])
        assert page_state(page_dir)["listening"]
    finally:
        bare.close()


def test_stop_hook_holds_a_turn_only_where_nothing_will_watch_its_page(claimed, capsys):
    """Between turns a page is either watched or idle. Under Claude Code the
    watch is the one Leaf's background Stop hook starts as the turn ends, so a
    turn ends over a page nothing watches yet. A watcher that is a process of its
    own, as a Codex task's adapter is, has to be running before the turn may end:
    without it the page keeps saying "Codex is working" over nobody."""
    session_model.cmd_waiting(claimed)
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    record_claim(claimed, harness="codex")
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert answer["decision"] == "block"
    assert (
        "no delivery adapter" in answer["reason"] and str(claimed) in answer["reason"]
    )

    # Blocking twice in a row is how a Stop hook loops, so a block already in
    # flight stands down.
    hooks_model.cmd_hook(
        "codex",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True},
    )
    assert capsys.readouterr().out == ""

    # A closed page ends the turn cleanly.
    declare_idle(claimed)
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A page a second session has since picked up is that session's to watch, so
    # s1 is no longer held to it.
    session_model.cmd_waiting(claimed)
    record_claim(claimed, harness="codex", id="s2")
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""


def test_pages_owing_the_same_thing_carry_one_copy_of_the_protocol(
    claimed, printing, tmp_path, capsys, snapshot
):
    """Each page states its own debt; the protocol they share is stated once.

    A debt that carried the whole protocol with it would make a session holding
    three pages that owe the same thing spend three copies of the same words
    saying so — most of what the blocking message weighs, and all of it between
    one page's line and the next.
    """
    second = tmp_path / "second-page"
    shutil.copytree(claimed, second)
    assert transaction_model.claim_page(second)
    deliveries = {}
    for page, comment, label in (
        (claimed, "c1", "first"),
        (second, "c2", "second"),
    ):
        append_carried_log_record(
            page,
            {"kind": "comment", "id": comment, "author": "user", "text": "look"},
        )
        receive_through(page, last_deliverable_seq(page))
        deliveries[delivered_ref(page, comment).partition(":")[0]] = (
            f"<{label}-delivery>"
        )
        session_model.cmd_waiting(page)

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)

    assert str(claimed) in reason and str(second) in reason
    assert reason.count("acknowledged user update with no answer") == 2
    assert reason.count(schema_model.ANSWER_INSTRUCTION) == 1
    # The lines stand together, so the user reaches every page before the
    # first protocol rather than one page per protocol.
    assert reason.index(str(second)) < reason.index(schema_model.ANSWER_INSTRUCTION)
    for identity, label in deliveries.items():
        reason = reason.replace(identity, label)
    snapshot.check(
        yaml_document(
            "Two pages carry distinct debts and one shared answering instruction.",
            {
                "Stop": {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": Prose(
                            reason.replace(str(claimed), "<first-page>").replace(
                                str(second), "<second-page>"
                            )
                        ),
                    }
                }
            },
        )
    )


def test_a_preview_owes_no_watcher_but_still_carries_its_user(
    claimed, printing, capsys
):
    """A developer preview is a page put up to be looked at, not handed over.

    A session inspecting a dozen slots was carrying a dozen copies of the same
    "no watcher" line into every turn, none of which named anything a user was
    waiting on. What must survive the exemption is the user: a comment left on
    a preview is as unanswered as one left anywhere else, and the clause that
    reports it runs above this one.
    """
    # A Codex task owes its pages an adapter; a Claude Code session's watch is
    # its own Stop hook, and owes nothing here.
    session_model.cmd_waiting(claimed)
    record_claim(claimed, harness="codex")
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert "no delivery adapter" in json.loads(capsys.readouterr().out)["reason"]

    write_record(
        claimed / schema_model.PREVIEW_FILE,
        {
            "example": "triage-board",
            "checkout": "leaf",
            "interaction": "user",
            "started": "2026-09-01T10:00:00+00:00",
            "input": {"source": "triage-board", "authored": "leaf"},
        },
    )
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Presence is the whole reading. The serve path's user raises on a preview
    # file it cannot parse, and this guard fails open by saying nothing, so a
    # user here would take every page the session holds down without a word.
    PREVIEW.file(claimed / schema_model.PREVIEW_FILE).write_text(
        "{not json", encoding="utf-8"
    )
    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    record_claim(claimed)

    append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "revision": 1, "text": "is this right?"},
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = inlined(context)["batches"]
    assert batch["page"] == str(claimed)
    assert [event["text"] for event in batch["events"]] == ["is this right?"]
    assert "no watcher" not in context
    # Handed over, the comment is owed an answer, and the turn's Stop holds for it.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    assert f"{claimed}: 1 acknowledged user update with no answer" in reason
    assert "no watcher" not in reason


@pytest.mark.parametrize("rewritten", [True, False])
def test_the_turn_holds_again_when_a_version_takes_the_answer_back(
    claimed, printing, capsys, rewritten
):
    """A pick answers the question it was asked in, and a version that rewrites
    the option picked takes that answer back — so the question is open again and
    nobody has been told. This is the guard's whole subject, and it is the one
    reading that cannot load the page's vendored registry: that load is a gate,
    and the Stop hook fails open, so a raise here stands the guard down on any
    page a little older than the code and says nothing.

    Where each id sits is not the vocabulary's to answer, so the hook reads that
    much and holds the turn exactly when `page state` says the thread is open.
    The floor lands on the option rather than on the group, which is what makes
    the reading matter — a floor on the group is in the action's own name.

    The unrewritten arm is the control: the pick still stands, the thread reads
    answered, and the hook must say nothing. Without it a guard that blocked on
    every acknowledged comment would pass the other arm."""
    (claimed / "index.html").write_text(PICKS_PAGE)
    let_a_pick_settle_a_thread(claimed, "which")
    session_model.cmd_waiting(claimed)
    # Watched, so the guard's other clause is clear and what fires below can only
    # be this one.
    claim_record = service_model.page_claim(claimed)
    assert claim_record is not None
    lease_path_8 = leases_model.waiter_lease_path(claimed, claim_record["id"])
    assert lease_path_8 is not None
    lease = leases_model.take_wait_lease(lease_path_8)
    assert lease
    asked = append_carried_log_record(
        claimed,
        {"kind": "comment", "id": "which", "author": "user", "text": "which of these?"},
    )
    publish(claimed)
    append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )
    note = {
        "kind": "note",
        "author": "agent",
        "version": 2,
        "revision": 2,
        "text": "rewrote the first option" if rewritten else "tidied the prose",
    }
    if rewritten:
        note["restated"] = ["flag-first"]
    append_carried_log_record(claimed, note)
    receive_through(
        claimed,
        next(
            e["seq"]
            for e in reversed(events_model.read_events(claimed))
            if e["kind"] == "action"
        ),
    )

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    printed = capsys.readouterr().out
    if rewritten:
        answer = json.loads(printed)
        assert "decision" not in answer
        assert delivered_ref(claimed, asked["id"]) in continued(answer)
    else:
        assert printed == ""


def test_an_acknowledged_comment_nobody_answered_holds_the_turn(
    claimed, printing, capsys
):
    """Acknowledging is what takes a comment off the batch, so after it no
    watcher will raise that comment again and every other gate reads the page as
    clean. The failure, from a live channel session: a comment arrived while the
    agent was mid-turn on something else, the agent acknowledged it, answered
    the person in the terminal instead of on the page, and the user was left
    with a question that nothing would ever deliver again."""
    session_model.cmd_waiting(claimed)
    # Watched, which is the whole of what clears the guard's other case and
    # clears nothing here.
    session = service_model.page_claim(claimed)
    assert session is not None
    lease_path_5 = leases_model.waiter_lease_path(claimed, session["id"])
    assert lease_path_5 is not None
    lease = leases_model.take_wait_lease(lease_path_5)
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    assert "1 acknowledged user update with no answer" in continued(answer)
    assert asked["id"] in continued(answer)
    claim_record_2 = service_model.page_claim(claimed)
    assert claim_record_2 is not None
    assert claim_record_2["turn_closed"] is None
    # An id is all this can name, to a session that may no longer hold a word of
    # what was said under it, so the instruction that reaches it has to carry the
    # reading that recovers the exchange.
    assert schema_model.ANSWER_INSTRUCTION in continued(answer)
    # The receipt recorded the delivery's reference, so the reminder names the
    # complete command rather than a placeholder nothing on hand fills.
    assert f"`leaf thread reply {delivered_ref(claimed, asked['id'])}`" in continued(
        answer
    )

    # A bound move can be answered by its provider final or an explicit addressed
    # reply. The proactive thread writer still refuses an owed move.
    with transaction_model.PageTransaction(claimed) as page:
        assert session is not None
        page.reserve_delivery_reply(session["id"], asked["id"], "a1")
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    reason = continued(capsys.readouterr().out)
    assert (
        "your turn's final message or "
        f"`leaf thread reply {delivered_ref(claimed, asked['id'])}`"
    ) in reason
    assert "leaf thread reply <page>" not in reason
    # A failure receipt waits for the turn, and its refusal names the same command.
    ref = delivered_ref(claimed, asked["id"])
    with pytest.raises(delivery_model.Refused) as refused:
        thread_model.post_response(ref, "gave up", failure="turn_failed")
    assert f"with `leaf thread reply {ref}`" in str(refused.value)
    with transaction_model.PageTransaction(claimed) as page:
        assert session is not None
        page.clear_delivery_reply_reservation(session["id"], asked["id"], "a1")

    # A reply clears it, and the thread stays open behind it: closing one is the
    # user's to do, so an open thread is not an unanswered one.
    thread_model.post_reply(
        claimed,
        {"parent": asked["id"], "responds": asked["id"]},
        "because the fold is absolute",
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The user's follow-up puts the decision back, and this is the case that picks
    # the reading. The browser posts a follow-up as a reply of the user's own,
    # so a gate asking whether anyone but them has *ever* spoken is answered
    # "yes" by the reply above and never fires for this thread again — the drop
    # this test is named for, one level down and just as permanent. Reading the
    # last word costs a thread that wants no answer one `leaf thread resolve`, which is
    # a question the agent is holding the context to settle; the other reading
    # costs the user their question, which nobody sees at all.
    follow = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "but why not C?",
        },
    )
    # The watch opens the follow-up turn, whose prompt hook carries the new input,
    # and that turn's Stop holds for an answer to the last word.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = inlined(context)["batches"]
    assert [event["id"] for event in batch["events"]] == [follow["id"]]
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert delivered_ref(claimed, follow["id"]) in continued(capsys.readouterr().out)
    thread_model.post_reply(
        claimed,
        {"parent": follow["id"], "responds": follow["id"]},
        "C is slower on the hot path",
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Closing the thread is the other way to answer for one, for the cases where
    # waiting on the user says nothing.
    moot = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "and C?"}
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert moot["id"] in continued(capsys.readouterr().out)
    thread_model.cmd_resolve(claimed, moot["id"])
    capsys.readouterr()  # cmd_resolve prints the event it wrote
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # The agent's own decision holds nothing while the user has yet to answer it:
    # the last word there is the agent's. When they answer in the thread — which
    # is where the panel's reply box puts it — the decision is the agent's again, and
    # it is the last word rather than any reading of the root that says so.
    item = append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "agent", "text": "which storage engine?"},
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    answered = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": item["id"], "text": "sqlite"},
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert delivered_ref(claimed, answered["id"]) in continued(capsys.readouterr().out)
    thread_model.post_reply(
        claimed, {"parent": answered["id"], "responds": answered["id"]}, "sqlite it is"
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""
    leases_model.release_lease(lease)


def test_the_guard_survives_a_page_whose_layer_cannot_be_composed(
    claimed, printing, capsys
):
    """Every Leaf composes a page's layer from the packages it selects, and refuses
    a selection it cannot compose — by design, since that refusal is what sends an
    agent to repair the page. The Stop hook is the one user that must never put the
    question: hook registrations fail open, so a raise here stands the *whole*
    guard down, watch clause included, on a page whose project package moved, and
    says nothing about it. Found by running the guard against a real page, where
    reading the published version to settle threads loaded that page's registry."""
    session_model.cmd_waiting(claimed)
    session = service_model.page_claim(claimed)
    assert session is not None
    lease_path_6 = leases_model.waiter_lease_path(claimed, session["id"])
    assert lease_path_6 is not None
    lease = leases_model.take_wait_lease(lease_path_6)
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    record = registry_storage.layer_record(claimed)
    (claimed / schema_model.LAYER_FILE).unlink()
    assert record is not None
    registry_storage.write_layer(
        claimed, {**record, "packages": [*record["packages"], "./moved-package"]}
    )
    # Without this the test passes for the wrong reason: it has to be a page
    # whose layer the current Leaf really does refuse.
    with pytest.raises(registry_contract.RegistryError):
        vocabulary_model.load_registry(claimed)

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    answer = json.loads(capsys.readouterr().out)
    assert "decision" not in answer
    assert asked["id"] in continued(answer)
    leases_model.release_lease(lease)


def test_idle_cannot_close_a_page_over_events_nobody_read(claimed, capsys):
    """`leaf page close PAGE` is the way out of the guard's other case, so it
    reads as the way out of this one too. The events are the user's: a page
    idled over them ends the leaf on someone still waiting for an answer, and
    from the browser that looks exactly like one that ran its course."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    refused = CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)])
    assert refused.exit_code == 1
    assert "1 event nobody has picked up" in refused.output
    # The claimant's harness names the remedy: Claude Code's hook carries them.
    assert "Leaf's hook puts them in your context" in refused.output
    assert declared(claimed)["state"] != "idle"

    # An explicit wait hands the input to its reader, which confirms it. Reading
    # it is not answering it: idle holds until the thread has something under it.
    waited = CliRunner().invoke(cli_model.cli, ["wait", str(claimed)])
    assert waited.exit_code == 0, waited.output
    woken(waited.output, "s1")
    refused = CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)])
    assert refused.exit_code == 1
    assert "1 acknowledged user update with no answer" in refused.output
    assert declared(claimed)["state"] != "idle"

    comment = events_model.read_events(claimed)[0]["id"]
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(claimed, comment),
                "--text",
                "ok",
                "--title",
                "Thread title",
            ],
        )
        .exit_code
        == 0
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)]).exit_code
        == 0
    )
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # A worker's report holds idle the same way: idling over one would freeze its
    # provisional state on the page forever, with nobody left to absorb it.
    append_carried_log_record(
        claimed,
        {
            "kind": "report",
            "author": "agent",
            "widget": "t1",
            "meaning": {
                "scope": "page",
                "unit": "t1",
                "depends": ["t1"],
            },
            "action": "status",
            "detail": {"value": "review"},
            "revision": 1,
        },
    )
    refused = CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)])
    assert refused.exit_code == 1
    assert "1 event nobody has picked up" in refused.output
    cleanup_model.prompt_turn("s1")
    report = str(events_model.read_events(claimed)[-1]["seq"])
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            ["delivery", "ack", delivery_through(claimed, int(report))],
        )
        .exit_code
        == 0
    )
    # A report is the agent's own news, so acknowledging it is the whole of what
    # it asks for; only a user's comment owes an answer as well.
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)]).exit_code
        == 0
    )


def test_idle_and_the_stop_hook_hold_the_agent_to_the_same_moves(
    claimed, printing, capsys
):
    """A move the adapter queued for a later turn is that turn's debt: the turn that
    queued it may end over it, and may idle the page over it. Once the later turn
    opens it, both the Stop hook and `leaf page close` hold the agent to it."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "one more thing"}
    )
    [comment] = events_model.read_events(claimed)
    [batch] = freeze_events(claimed, [comment])["batches"]

    def pickup(phase: str) -> None:
        with (
            transaction_model.PageTransaction(claimed) as page,
            delivery_model.receive_batch(page, batch, session_id="s1") as delivered,
        ):
            delivery_model.record_pickup(
                page,
                delivered,
                phase=phase,
                session="s1",
                refs=delivery_model.batch_refs(batch),
            )

    def idle() -> str | None:
        result = CliRunner().invoke(cli_model.cli, ["page", "close", str(claimed)])
        return None if result.exit_code == 0 else result.output

    pickup("queued")
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert "acknowledged" not in capsys.readouterr().out
    assert idle() is None

    pickup("opened")
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert "1 acknowledged user update with no answer" in capsys.readouterr().out
    value = idle()
    assert value is not None
    assert "1 acknowledged user update with no answer" in value


def test_idle_cannot_race_past_an_event_arriving_after_its_pending_check(
    page_dir, spawn
):
    """The pending check and idle transition are one decision.

    A browser post serialized after the check but before the status write must
    keep the page open. Otherwise Stop sees an idle page, permits the turn to
    end, and leaves the newly appended event with no watcher to deliver it.
    """
    session_model.cmd_waiting(page_dir)
    marker = page_dir / "status-lock-requested"
    events = open(page_dir / "events.jsonl", "a+b")
    fcntl.flock(events, fcntl.LOCK_EX)
    probe = """\
from leaf.records import transaction as transaction_model

original_flocked = transaction_model.flocked
events = Path(os.environ["EVENTS"]).resolve()
marker = Path(os.environ["MARKER"])

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if Path(path).resolve() == events:
        marker.write_text("requested", encoding="utf-8")
    with original_flocked(path, **kwargs) as stream:
        yield stream

transaction_model.flocked = observed_flocked
sys.argv = ["leaf", "page", "close", os.environ["PAGE"]]
cli_model.cli()
"""
    process = spawn_probe(
        spawn,
        page_dir,
        probe,
        EVENTS=page_dir / "events.jsonl",
        MARKER=marker,
    )

    deadline = time.monotonic() + STATED_TIMEOUT
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not marker.exists():
        events.close()
        pytest.fail("the idle command never requested the held event-log lock")

    # The marker is immediately before the command's lock acquisition. In the
    # broken ordering it appears only after the empty pending read; in the fixed
    # ordering it appears before that read. Appending while this process owns the
    # lock therefore makes the old command idle and the fixed command refuse.
    events.seek(0, os.SEEK_END)
    events.write(
        (
            events_model.jsonl_line(
                {
                    "kind": "comment",
                    "id": "c1",
                    "author": "user",
                    "text": "one last thing",
                    "attention": True,
                }
            )
            + "\n"
        ).encode()
    )
    events.flush()
    os.fsync(events.fileno())
    fcntl.flock(events, fcntl.LOCK_UN)
    events.close()

    out, err = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 1, f"{out}{err}"
    assert "1 event nobody has picked up" in out
    assert declared(page_dir)["state"] == "waiting"


def test_a_reaction_holds_the_turn_as_words_do(claimed, printing, capsys):
    """A reaction is the user speaking: a 👍 they put on the agent's answer, once
    acknowledged and unanswered, holds the turn as words under the answer do."""
    session_model.cmd_waiting(claimed)
    session = service_model.page_claim(claimed)
    assert session is not None
    lease_path_7 = leases_model.waiter_lease_path(claimed, session["id"])
    assert lease_path_7 is not None
    lease = leases_model.take_wait_lease(lease_path_7)
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    answer = thread_model.post_reply(
        claimed, {"parent": asked["id"], "responds": asked["id"]}, "because"
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": answer["id"], "emoji": "👍"},
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)


def _stop(capsys):
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    output = capsys.readouterr().out
    return continued(output) if output else None


def _idle(page_dir):
    return CliRunner().invoke(cli_model.cli, ["page", "close", str(page_dir)])


def test_a_move_the_turn_started_lets_that_turn_end(claimed, printing, capsys):
    """A start on a delivered move is the agent's answer for now: the move reads
    Working, with the start's line beside it. Work longer than a few minutes goes to
    background workers whose results wake a later turn, so the turn that started the
    move may end over it. Holding that turn made agents post a reply saying only what
    the start already said. With no background work the harness reports to carry it,
    the start does not carry into the next turn, which answers the move or starts it
    again, and idling still refuses over it: closing the page answers nothing."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "sketch both?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    # A page task's start names no move, so the move is still not started.
    working(claimed, "sketching both")
    assert "1 acknowledged user update with no answer" in _stop(capsys)
    claim_record_3 = service_model.page_claim(claimed)
    assert claim_record_3 is not None
    assert claim_record_3["turn_closed"] is None

    assert _start(claimed, asked["id"], "sketching both").exit_code == 0
    assert _stop(capsys) is None
    claim_record_4 = service_model.page_claim(claimed)
    assert claim_record_4 is not None
    assert claim_record_4["turn_closed"]
    assert "1 acknowledged user update with no answer" in _idle(claimed).output

    # A worker's result wakes the next turn, whose prompt and Stop name the start
    # an earlier turn wrote, and offer starting it again only because it had one.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    prompt = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert (
        f"your start on {asked['id']} lapsed: no agent of yours carried it"
        in prompt["additionalContext"]
    )
    reason = _stop(capsys)
    assert f"your start on {asked['id']} lapsed: no agent of yours carried it" in reason
    assert f"`leaf thread reply {delivered_ref(claimed, asked['id'])}`" in reason

    assert _start(claimed, asked["id"], "the second sketch").exit_code == 0
    # A task notification reaching the turn mid-way says nothing about it either.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert capsys.readouterr().out == ""
    assert _stop(capsys) is None

    # A follow-up in the thread carries its answer now. The start on the message
    # that prompted the work covers it all the same, since the thread's one reply
    # answers both; written before the follow-up's pickup, it holds the turn until the
    # agent starts again.
    follow = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "and C?"},
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    consume_pending_input("s1")
    reason = _stop(capsys)
    assert f"`leaf thread reply {delivered_ref(claimed, follow['id'])}`" in reason
    assert f"your start on {asked['id']} lapsed: no agent of yours carried it" in reason
    assert _start(claimed, follow["id"], "adding C").exit_code == 0
    assert _stop(capsys) is None

    thread_model.post_reply(
        claimed, {"parent": follow["id"], "responds": follow["id"]}, "All three are up."
    )
    end_work(claimed)
    assert _idle(claimed).exit_code == 0
    leases_model.release_lease(lease)


def test_a_threads_messages_and_moves_share_one_start_and_one_reply(
    claimed, printing, capsys
):
    """A move on an obligation in a thread's message and the user's message after it
    share the thread's one reply, addressed to the newer, so a start on that one
    holds both. Once the reply settles them, a later message in the thread is
    offered no start in place of its answer."""
    assert revisioning_model.activate_source(claimed).error is None
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": 'Which region?\n\n<lf-options id="thread-region">'
            '<lf-option id="thread-east" label="East"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    for action, detail in (("choose", {"value": ["thread-east"]}), ("answer", {})):
        done = append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "thread-region",
                "action": action,
                "detail": detail,
            },
        )
    follow = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "and West?"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    reason = _stop(capsys)
    assert follow["id"] in reason and done["id"] not in reason
    assert _start(claimed, follow["id"], "checking West").exit_code == 0
    assert _stop(capsys) is None

    thread_model.post_reply(
        claimed, {"parent": follow["id"], "responds": follow["id"]}, "East, and West."
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    again = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": asked["id"], "text": "why?"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    reason = _stop(capsys)
    assert delivered_ref(claimed, again["id"]) in reason
    assert "your start" not in reason
    leases_model.release_lease(lease)


def test_a_stop_keeps_the_turn_going_only_for_owed_input(claimed, capsys):
    """Input that arrives as a turn ends goes into that turn when it is owed an
    answer. A resolve owes none, so the turn ends and the input waits for the
    watcher to wake the next one, whose prompt hands it over: holding the turn to
    say a thread closed spent a turn on nothing."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    thread_model.post_reply(
        claimed, {"parent": asked["id"], "responds": asked["id"]}, "Because."
    )
    resolve = append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": asked["id"]}
    )
    assert _stop(capsys) is None
    claim_record_5 = service_model.page_claim(claimed)
    assert claim_record_5 is not None
    assert claim_record_5["turn_closed"]
    assert [
        event["id"]
        for event in transaction_model.unacknowledged(
            events_model.read_events(claimed),
            acknowledged_through(claimed),
        )
    ] == [resolve["id"]]

    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert resolve["id"] in context["additionalContext"]
    leases_model.release_lease(lease)


def test_a_stop_holds_for_a_request_the_user_resolved(claimed, printing, capsys):
    """The user's resolve takes the thread off their list and leaves the request
    owed, so the turn that took it in holds for its answer, and the answer lets the
    turn end."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    append_carried_log_record(
        claimed,
        {
            "kind": "resolve",
            "author": "user",
            "parent": asked["id"],
            "attention": False,
        },
    )
    assert delivered_ref(claimed, asked["id"]) in _stop(capsys)
    thread_model.post_reply(
        claimed, {"parent": asked["id"], "responds": asked["id"]}, "Because."
    )
    assert _stop(capsys) is None
    leases_model.release_lease(lease)


@pytest.mark.parametrize("history", ["handoff", "lost-pointer", "newest-in-thread"])
def test_a_stop_reminder_recovers_the_exact_reply_address(
    page_dir, codex_loop, capsys, history
):
    """The reminder recovers captured input and a usable response address, including
    after ownership changes. Consecutive user messages owe the newest one answer.
    An update the previous owner received is offered to the new one as new input,
    which, with a queue adapter running, Stop hands into the ending turn.
    """
    codex_loop(page_dir)
    cleanup_model.prompt_turn("codex-thread", "active")
    waiter = _watched(page_dir)
    adapter = adapter_lease("codex-thread", None)
    try:
        latest = append_carried_log_record(
            page_dir, {"kind": "comment", "author": "user", "text": "why here?"}
        )
        if history == "newest-in-thread":
            latest = append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": "user",
                    "parent": latest["id"],
                    "text": "and when?",
                },
            )
        if history == "lost-pointer":
            receive_through(page_dir, latest["seq"])
        else:
            with transaction_model.PageTransaction(page_dir) as page:
                page.take_claim(
                    harness_model.EmbeddedHarness("prior", "Prior owner", os.getpid())
                )
            cleanup_model.open_session_turn("prior")
            original = delivery_model.read_delivery(
                delivery_through(page_dir, latest["seq"])
            )
            delivery_model.receive(original, "prior")
            codex_loop(page_dir)
        cursor = acknowledged_through(page_dir)
        deliveries = set(
            delivery_model.state_home().joinpath("deliveries").glob("*.json")
        )

        cleanup_model.prompt_turn("codex-thread", "active")
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "active",
            },
        )
        reason = json.loads(capsys.readouterr().out)["reason"]
        if history == "lost-pointer":
            [pointer_xml] = re.findall(r"<leaf-delivery\b[^>]*?/>", reason)
            pointer = ElementTree.fromstring(pointer_xml)
            assert pointer.attrib["operation"] == "delivery read"
            read = CliRunner().invoke(
                cli_model.cli, ["delivery", "read", pointer.attrib["id"]]
            )
            assert read.exit_code == 0, read.output
            envelope = json.loads(read.output)
            assert (
                set(delivery_model.delivery_path(envelope["id"]).parent.glob("*.json"))
                == deliveries
            )
            assert not codex_records("codex-thread")
        else:
            # The new owner is offered the update as Codex offers new input.
            envelope, _ = read_json_block(reason)
            assert envelope == delivery_model.cmd_delivery_read(envelope["id"])
            assert envelope["id"] != original["id"]
            [(offered, _)] = codex_records("codex-thread")
            assert offered.stem == envelope["id"]
        assert acknowledged_through(page_dir) == cursor
        [batch] = envelope["batches"]
        [event] = batch["events"]
        assert event["id"] == latest["id"]
        assert event["text"] == latest["text"]
        reply = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                event["answer"]["ref"],
                "--text",
                "Here, next week.",
                "--title",
                "Thread title",
            ],
        )
        assert reply.exit_code == 0, reply.output
        assert not owed_answers(page_dir)
        cleanup_model.prompt_turn("codex-thread", "active")
        hooks_model.cmd_hook(
            "codex",
            {
                "hook_event_name": "Stop",
                "session_id": "codex-thread",
                "turn_id": "active",
            },
        )
        assert capsys.readouterr().out == ""
    finally:
        adapter.close()
        leases_model.release_lease(waiter)


def test_a_page_pick_holds_the_turn_until_the_markup_records_it(
    claimed, printing, capsys
):
    """A pick on a page obligation is owed a version that writes it in. The delivery says
    so, the Stop hook and `idle` hold the agent to it, and the stamped version whose
    markup records the pick settles it — one rule, read by every consumer. An edit
    to a draft that asks nothing is carried by the log and owes nothing: it keeps a
    receipt that reports its delivery, which no count, Stop or `idle` reads, and the
    next version retires it without writing the edit in."""
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="choice">').replace(
        "</section>", '<lf-draft id="note"><pre>Blue room.</pre></lf-draft></section>'
    )
    (claimed / "index.html").write_text(source)
    publish(claimed)
    lease = _watched(claimed)
    edit = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note",
            "action": "edit",
            "detail": {"value": "Green room."},
        },
    )
    edited = state_json(claimed)
    [receipt] = edited["workflows"]
    assert (
        receipt["input"],
        receipt["state"],
        receipt["seen"],
        receipt["obligation"],
    ) == (edit["id"], "waiting", False, None)
    assert edited["activity"]["obligations"] == []
    assert edited["activity"]["counts"] == {
        "running": 0,
        "waiting": 0,
        "blocked": 0,
        "unseen": 0,
    }
    picked = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["backfill-first"]},
        },
    )
    state = state_json(claimed)
    [workflow] = owed(state)
    assert workflow["answer"] == {"kind": "markup", "action": picked["id"]}
    assert state["activity"]["counts"] == {
        "running": 0,
        "waiting": 0,
        "blocked": 0,
        "unseen": 1,
    }

    delivery = delivery_through(claimed, last_deliverable_seq(claimed))
    [batch] = delivery_model.read_delivery(delivery)["batches"]
    [event] = batch["events"]
    assert edit["attention"] is False
    assert {key: event["answer"][key] for key in workflow["answer"]} == workflow[
        "answer"
    ]
    told = [batch["handling"][ref] for ref in event["handling"]]
    assert any("such as an `lf-options` marked `settled`" in text for text in told)
    receive_through(claimed, last_deliverable_seq(claimed))

    assert f"records action {picked['id']}" in _stop(capsys)
    refused = _idle(claimed)
    assert refused.exit_code == 1
    assert f"records action {picked['id']}" in refused.output
    # Started as the work the pick selects, it lets the turn end while that work
    # runs, and still owes the version.
    assert _start(claimed, picked["id"], "building it").exit_code == 0
    assert _stop(capsys) is None
    assert f"records action {picked['id']}" in _idle(claimed).output

    (claimed / "index.html").write_text(
        source.replace(
            '<lf-option id="backfill-first" label="Backfill first">',
            '<lf-option id="backfill-first" label="Backfill first" selected>',
        )
    )
    assert stamp(claimed, "Backfill leads").exit_code == 0
    assert state_json(claimed)["workflows"] == []
    assert _stop(capsys) is None
    assert _idle(claimed).exit_code == 0
    leases_model.release_lease(lease)


def test_a_pick_of_an_added_option_settles_without_writing_the_option_in(claimed):
    """An option the user added stands in its group from the log, where the user put
    it, so no version has to place it in the markup. A pick of it is owed a stamped
    version all the same, and a version that leaves the option out settles it; a
    version still marking an authored option `selected` does not."""
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="choice">').replace(
        '<lf-option id="flag-first" label="Flag first">',
        '<lf-option id="flag-first" label="Flag first" selected>',
    )
    (claimed / "index.html").write_text(source)
    publish(claimed)
    for action, detail in [
        ("add", {"option": "choice-option-mine", "text": "Neither yet."}),
        ("choose", {"value": ["choice-option-mine"]}),
    ]:
        picked = append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "choice",
                "action": action,
                "detail": detail,
            },
        )
    assert {"kind": "markup", "action": picked["id"]} in [
        workflow["answer"] for workflow in owed(state_json(claimed))
    ]

    (claimed / "index.html").write_text(source.replace("Ship dark.", "Ship it dark."))
    assert stamp(claimed, "Still marks flag-first").exit_code == 0
    assert [workflow["input"] for workflow in owed(state_json(claimed))] == [
        picked["id"]
    ]

    (claimed / "index.html").write_text(
        source.replace(
            '<lf-option id="flag-first" label="Flag first" selected>',
            '<lf-option id="flag-first" label="Flag first">',
        )
    )
    assert stamp(claimed, "Neither yet").exit_code == 0
    assert state_json(claimed)["workflows"] == []


def test_done_hands_over_a_pick_the_markup_must_still_record(claimed):
    """Done finishes a multiple-choice answer without replacing it: the version that
    takes the answer in still marks the authored picks `selected`, beside an added option
    that stays the log's, and a version without them leaves the answer owed."""
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="choice" multiple>')
    (claimed / "index.html").write_text(source)
    publish(claimed)
    for action, detail in [
        ("add", {"option": "choice-option-mine", "text": "Both, staged."}),
        ("choose", {"value": ["flag-first", "choice-option-mine"]}),
        ("answer", {}),
    ]:
        done = append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "choice",
                "action": action,
                "detail": detail,
            },
        )
    [workflow] = owed(state_json(claimed))
    assert workflow["answer"] == {"kind": "markup", "action": done["id"]}

    (claimed / "index.html").write_text(source.replace("Ship dark.", "Ship it dark."))
    assert stamp(claimed, "Forgot the pick").exit_code == 0
    assert [item["input"] for item in owed(state_json(claimed))] == [done["id"]]

    (claimed / "index.html").write_text(
        source.replace(
            '<lf-option id="flag-first" label="Flag first">',
            '<lf-option id="flag-first" label="Flag first" selected>',
        )
    )
    assert stamp(claimed, "Flag first, staged").exit_code == 0
    assert state_json(claimed)["workflows"] == []


@pytest.mark.parametrize("declared", ["shipped", "done-only"])
def test_a_tick_before_done_hands_nothing_to_the_agent(claimed, capsys, declared):
    """A multiple-choice obligation finishes with Done. Until then a tick is the user's
    own unfinished answer: it is not agent work, the panel does not count it as an
    update waiting, no delivery is prepared, and Stop does not
    hold the turn. Done hands the obligation over, and the answer it owes is a version.

    The tick is held because it is a move on a widget whose obligation stands open, not
    because `choose` happens to answer some other group: a layer answering the
    group only by its Done holds the tick the same way."""
    if declared == "done-only":
        declare_on_page(
            claimed,
            lambda registry: registry["lf-options"]["awaits"].update(
                answered={"answer": {}}
            ),
        )
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="choice" multiple>')
    (claimed / "index.html").write_text(source)
    publish(claimed)
    lease = _watched(claimed)
    append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )
    ticked = state_json(claimed)
    assert [item["widget"] for item in obligations_on_user(ticked)] == ["choice"]
    assert ticked["workflows"] == []
    assert ticked["activity"]["counts"] == {
        "running": 0,
        "waiting": 0,
        "blocked": 0,
        "unseen": 0,
    }

    assert transaction_model.unacknowledged(events_model.read_events(claimed), 0) == []
    assert _stop(capsys) is None

    done = append_command(
        claimed,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "choice",
            "action": "answer",
            "detail": {},
        },
    )
    finished = state_json(claimed)
    assert obligations_on_user(finished) == []
    [workflow] = owed(finished)
    assert workflow["answer"] == {"kind": "markup", "action": done["id"]}
    delivery = delivery_through(claimed, done["seq"])
    [batch] = delivery_model.read_delivery(delivery)["batches"]
    assert [event["id"] for event in batch["events"]] == [done["id"]]
    leases_model.release_lease(lease)


@pytest.mark.parametrize("where", ["page", "thread"])
def test_a_queue_owes_nothing_until_it_is_finished_and_then_every_card_moved(
    page_dir, where
):
    """A move leaving cards queued keeps the obligation on the user, and completing the
    queue hands over every moved card, not just the final one."""
    declare_on_page(
        page_dir, lambda registry: registry.update(queue_board_registry(registry))
    )
    board = (
        '<lf-board id="triage">'
        '<lf-column id="queue" label="Queued">'
        '<lf-card id="card-a" label="Rolling expiry"><strong>Rolling expiry</strong></lf-card>'
        '<lf-card id="card-b" label="Bounded fallback"><strong>Bounded fallback</strong></lf-card>'
        '<lf-card id="card-c" label="Retry budget"><strong>Retry budget</strong></lf-card>'
        "</lf-column>"
        '<lf-column id="keep" label="Kept"></lf-column>'
        '<lf-column id="pass" label="Passed"></lf-column>'
        "</lf-board>"
    )
    if where == "page":
        (page_dir / "index.html").write_text(
            PAGE.replace(
                "</section>",
                '<lf-group id="triage-decision" label="Which follow-ups should we keep?"><h3 id="triage-decision-h">Which follow-ups should we keep?</h3>'
                f"{board}</lf-group></section>",
            )
        )
        publish(page_dir)
    else:
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None and activated.revision == 1
        append_carried_log_record(
            page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "text": f"Sort these follow-ups.\n\n{board}",
            },
        )

    def sort(card, rank):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "triage",
                "action": "move",
                "detail": {"unit": card, "value": "keep", "rank": rank},
            },
        )

    sort("card-a", "i")
    sort("card-b", "r")
    sorting = state_json(page_dir)
    assert sorting["workflows"] == []
    assert [item["widget"] for item in obligations_on_user(sorting)] == ["triage"]

    sort("card-c", "w")
    finished = state_json(page_dir)
    assert obligations_on_user(finished) == []
    moved = ["card-a", "card-b", "card-c"]
    assert sorted(item["coordinate"][1] for item in finished["workflows"]) == moved
    # On the page the version that writes each move in answers it; in a thread, the
    # reply to the newest answers them all.
    assert sorted(item["coordinate"][1] for item in owed(finished)) == (
        moved if where == "page" else ["card-c"]
    )
