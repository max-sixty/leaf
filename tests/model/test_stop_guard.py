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
from interact_support import (
    PAGE,
    PICKS_PAGE,
    STATED_TIMEOUT,
    Prose,
    _interaction_prompt_evidence,
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

from leaf import activity as activity_model
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf.registry import contract as registry_contract
from leaf.registry import storage as registry_storage


def test_a_completed_stream_answers_its_event_even_when_the_reply_address_differs():
    obligation = {
        "input": "widget-action",
        "seq": 1,
        "stage": "picked_up",
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
            "claim_turn": "leaf-turn",
        }
        return activity_model.blocking_obligations(state, watched=watched)

    assert blocking(obligation, watched=True) == []
    # Nothing is left to commit the draft once its watcher is gone.
    assert blocking(obligation, watched=False) == [obligation]
    # A plain reply is `leaf thread reply`'s to write, whatever a draft says.
    plain = {**obligation, "answer": {**obligation["answer"], "writer": "agent"}}
    assert blocking(plain, watched=True) == [plain]


def test_stop_hook_keeps_codex_inside_the_exact_wait_session(
    codex_claimed_page, capsys
):
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    session = service_model.page_claim(page)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page, session["id"])
    )
    assert lease

    # A live watcher lets Claude end its turn, but Codex must keep this one active
    # and poll the unified-exec session whose output can enter this context. The
    # lease cannot say whether that session's command is the initial wait or the
    # one that acknowledged a delivery before waiting, so the remedy names both.
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "poll the existing" in reason and "write_stdin" in reason
    assert "running `leaf wait`, alone or after `leaf delivery ack`" in reason

    # The adapter's second lease proves that the watcher can deliver into a
    # later turn. With that adapter alive, this turn may end normally.
    adapter = adapter_lease("codex-thread", None)
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    assert capsys.readouterr().out == ""
    adapter.close()

    # The existing one-shot escape still prevents a hook recursion.
    hooks_model.cmd_hook(
        "codex",
        {
            "hook_event_name": "Stop",
            "session_id": "codex-thread",
            "stop_hook_active": True,
        },
    )
    assert capsys.readouterr().out == ""

    # With no watcher, the ordinary remedy starts detached same-task delivery.
    leases_model.release_lease(lease)
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "leaf page claim" in reason and str(page) in reason

    # Pending output still has to cross context: the remedy is to poll the wait
    # already running, and nothing tells this task to start one in the background.
    # The delivery the poll yields says how this harness acknowledges it.
    comment = append_carried_log_record(
        page, {"kind": "comment", "author": "user", "text": "hi"}
    )
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page, session["id"])
    )
    assert lease
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "running `leaf wait`, alone or after `leaf delivery ack`" in reason
    assert "background" not in reason
    acknowledge = session_model.wait_acknowledgement(
        harness_model.CodexHarness("codex-thread", "Codex"), page
    )("0a1b2c3d")
    assert (
        "run `leaf delivery ack 0a1b2c3d && leaf wait` in unified exec" in acknowledge
    )
    assert "background" not in acknowledge
    leases_model.release_lease(lease)

    receive_through(page, comment["seq"])
    # Answered before the page closes: an acknowledged comment with nothing
    # under it holds the turn on its own account, which is the subject of
    # test_an_acknowledged_comment_nobody_answered_holds_the_turn.
    thread_model.post_reply(
        page,
        {"parent": comment["id"], "responds": comment["id"]},
        "so it does",
    )
    declare_idle(page)
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    assert capsys.readouterr().out == ""


def test_stop_hook_does_not_borrow_a_foreign_bare_waiter_lease(page_dir, monkeypatch):
    """A page-local lease proves only an unclaimed bare-shell watch."""
    session_model.cmd_waiting(page_dir)
    bare = leases_model.take_wait_lease(page_dir / "waiter.lock")
    assert bare
    try:
        assert page_state(page_dir)["listening"]
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "harness-owner")
        monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
        assert service_model.claim_page(page_dir)
        claim = service_model.page_claim(page_dir)
        assert not leases_model.lock_is_held(
            leases_model.waiter_lease_path(page_dir, claim["id"])
        )
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

    Every debt used to carry the whole protocol with it, so a session holding
    three pages that owed the same thing spent three copies of the same ninety
    words saying so — most of what the blocking message weighed, and all of it
    between one page's line and the next.
    """
    second = tmp_path / "second-page"
    shutil.copytree(claimed, second)
    assert service_model.claim_page(second)
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
    (claimed / schema_model.PREVIEW_FILE).write_text("{not json", encoding="utf-8")
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
    [batch] = json.loads(context.split("\n")[1])["batches"]
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
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, service_model.page_claim(claimed)["id"])
    )
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
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
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
    assert service_model.page_claim(claimed)["turn_closed"] is None
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
    with service_model.PageTransaction(claimed) as page:
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
    with service_model.PageTransaction(claimed) as page:
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
    [batch] = json.loads(context.split("\n")[1])["batches"]
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
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    record = registry_storage.layer_record(claimed)
    layer = claimed / schema_model.LAYER_FILE
    layer.unlink()
    registry_storage.LAYER.write(
        layer, {**record, "packages": [*record["packages"], "./moved-package"]}
    )
    # Without this the test passes for the wrong reason: it has to be a page
    # whose layer the current Leaf really does refuse.
    with pytest.raises(registry_contract.RegistryError):
        registry_storage.load_registry(claimed)

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
            service_model.PageTransaction(claimed) as page,
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
    assert "1 acknowledged user update with no answer" in idle()


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
    events = open(  # noqa: SIM115 - held across the child transition
        page_dir / "events.jsonl", "a+b"
    )
    fcntl.flock(events, fcntl.LOCK_EX)
    probe = """\
from leaf import service as service_model

original_flocked = service_model.flocked
events = Path(os.environ["EVENTS"]).resolve()
marker = Path(os.environ["MARKER"])

@contextlib.contextmanager
def observed_flocked(path, **kwargs):
    if Path(path).resolve() == events:
        marker.write_text("requested", encoding="utf-8")
    with original_flocked(path, **kwargs) as stream:
        yield stream

service_model.flocked = observed_flocked
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
    assert "1 event nobody has picked up" in err
    assert declared(page_dir)["state"] == "waiting"


def test_a_reaction_holds_no_turn_as_an_unanswered_obligation(
    claimed, printing, capsys
):
    """A reaction is a mark, not a question: the agent answers it by acting, so an
    acknowledged one nobody replied to does not hold the turn the way a comment
    does. Nor does an `ok` the user put on the agent's answer hand the thread back
    to the agent — a reaction is not the user speaking. The user's words are."""
    session_model.cmd_waiting(claimed)
    session = service_model.page_claim(claimed)
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(claimed, session["id"])
    )
    assert lease
    append_carried_log_record(
        claimed,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    answer = thread_model.post_reply(
        claimed, {"parent": asked["id"], "responds": asked["id"]}, "because"
    )
    append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": answer["id"], "token": "keep"},
    )
    receive_through(claimed, last_deliverable_seq(claimed))

    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    assert capsys.readouterr().out == ""

    # Words under the answer are the user's last word, and hold the turn as ever.
    append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": answer["id"], "text": "but C?"},
    )
    cleanup_model.prompt_turn("s1")
    receive_through(claimed, last_deliverable_seq(claimed))
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    continued(capsys.readouterr().out)


def test_agent_sees_codex_watcher_recovery(codex_claimed_page, capsys, snapshot):
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    observations = {}

    def hook():
        hooks_model.cmd_hook(
            "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
        )
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    observations["no adapter"] = hook()
    lease = leases_model.take_wait_lease(
        leases_model.waiter_lease_path(page, "codex-thread")
    )
    assert lease
    try:
        observations["direct wait still running"] = hook()
        append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Check this."}
        )
        observations["direct wait has input"] = hook()
        adapter = adapter_lease("codex-thread", None)
        try:
            observations["adapter carries input"] = hook()
        finally:
            adapter.close()
    finally:
        leases_model.release_lease(lease)
    snapshot.check(
        yaml_document(
            "Codex Stop output: no adapter, a direct shell wait, and a live adapter.",
            _interaction_prompt_evidence(page, observations),
        )
    )


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
    the start already said. The start does not carry into the next turn, which
    answers the move or starts it again, and idling still refuses over it: closing
    the page answers nothing."""
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "sketch both?"}
    )
    receive_through(claimed, last_deliverable_seq(claimed))
    # A page task's start names no move, so the move is still not started.
    working(claimed, "sketching both")
    assert "1 acknowledged user update with no answer" in _stop(capsys)
    assert service_model.page_claim(claimed)["turn_closed"] is None

    assert _start(claimed, asked["id"], "sketching both").exit_code == 0
    assert _stop(capsys) is None
    assert service_model.page_claim(claimed)["turn_closed"]
    assert "1 acknowledged user update with no answer" in _idle(claimed).output

    # A worker's result wakes the next turn, whose prompt and Stop name the start
    # an earlier turn wrote, and offer starting it again only because it had one.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    prompt = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert (
        f"your start on {asked['id']} predates this turn" in prompt["additionalContext"]
    )
    reason = _stop(capsys)
    assert f"your start on {asked['id']} predates this turn" in reason
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
    assert f"your start on {asked['id']} predates this turn" in reason
    assert _start(claimed, follow["id"], "adding C").exit_code == 0
    assert _stop(capsys) is None

    thread_model.post_reply(
        claimed, {"parent": follow["id"], "responds": follow["id"]}, "All three are up."
    )
    end_work(claimed)
    assert _idle(claimed).exit_code == 0
    leases_model.release_lease(lease)


def test_each_owed_move_in_a_thread_takes_a_start_of_its_own(claimed, printing, capsys):
    """A thread's messages share one reply, but a move on an obligation frozen in one of its
    messages owes an answer of its own, so each is started on its own id. Once their
    replies settle them, a later move in the thread is offered no start in place of
    its answer."""
    assert revisioning_model.activate_source(claimed).error is None
    lease = _watched(claimed)
    asked = append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="thread-region" choose>'
            '<lf-option id="thread-east"><strong>East</strong></lf-option>'
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
    assert done["id"] in reason and follow["id"] in reason
    assert _start(claimed, follow["id"], "checking West").exit_code == 0
    reason = _stop(capsys)
    assert done["id"] in reason and follow["id"] not in reason
    assert _start(claimed, done["id"], "checking East").exit_code == 0
    assert _stop(capsys) is None

    for move in (done, follow):
        thread_model.post_reply(
            claimed, {"parent": move["id"], "responds": move["id"]}, "East it is."
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
    assert service_model.page_claim(claimed)["turn_closed"]
    assert [
        event["id"]
        for event in service_model.unacknowledged(
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
            with service_model.PageTransaction(page_dir) as page:
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
            envelope = json.loads(reason)
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
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>').replace(
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
    assert (receipt["input"], receipt["stage"], receipt["obligation"]) == (
        edit["id"],
        "sent",
        None,
    )
    assert edited["activity"]["obligations"] == []
    assert edited["activity"]["counts"]["total"] == 0
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
    assert state["activity"]["counts"]["total"] == 1

    delivery = delivery_through(claimed, last_deliverable_seq(claimed))
    [batch] = delivery_model.read_delivery(delivery)["batches"]
    [event] = batch["events"]
    assert edit["attention"] is False
    assert {key: event["answer"][key] for key in workflow["answer"]} == workflow[
        "answer"
    ]
    told = [batch["handling"][ref] for ref in event["handling"]]
    assert any("such as a choice group marked `settled`" in text for text in told)
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
            '<lf-option id="backfill-first">', '<lf-option id="backfill-first" chosen>'
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
    version still marking an authored option `chosen` does not."""
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>').replace(
        '<lf-option id="flag-first">', '<lf-option id="flag-first" chosen>'
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
            '<lf-option id="flag-first" chosen>', '<lf-option id="flag-first">'
        )
    )
    assert stamp(claimed, "Neither yet").exit_code == 0
    assert state_json(claimed)["workflows"] == []


def test_done_hands_over_a_pick_the_markup_must_still_record(claimed):
    """Done finishes a multiple-choice answer without replacing it: the version that
    takes the answer in still marks the authored picks `chosen`, beside an added option
    that stays the log's, and a version without them leaves the answer owed."""
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose multiple>')
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
            '<lf-option id="flag-first">', '<lf-option id="flag-first" chosen>'
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
            lambda registry: registry["lf-options"]["x-awaits"].update(
                answered={"answer": {}}
            ),
        )
    source = PAGE.replace("<lf-options>", '<lf-options id="choice" choose multiple>')
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
    assert ticked["activity"]["counts"]["total"] == 0
    assert ticked["activity"]["counts"]["pending"] == 0

    assert service_model.unacknowledged(events_model.read_events(claimed), 0) == []
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


QUEUE_PAGE = PAGE.replace(
    "</section>",
    """<lf-ask id="triage-decision"><h3>Which follow-ups should we keep?</h3>
  <lf-board id="triage">
    <lf-column id="queue" label="Queued">
      <lf-card id="card-a"><strong>Rolling expiry</strong></lf-card>
      <lf-card id="card-b"><strong>Bounded fallback</strong></lf-card>
      <lf-card id="card-c"><strong>Retry budget</strong></lf-card>
    </lf-column>
    <lf-column id="keep" label="Kept"></lf-column>
    <lf-column id="pass" label="Passed"></lf-column>
  </lf-board>
</lf-ask></section>""",
)


def test_a_finished_queue_owes_every_card_the_user_moved(page_dir):
    """Completing a queue owes every moved card, not just the final one."""
    declare_on_page(
        page_dir, lambda registry: registry.update(queue_board_registry(registry))
    )
    (page_dir / "index.html").write_text(QUEUE_PAGE)
    publish(page_dir)

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
    assert state_json(page_dir)["workflows"] == []

    sort("card-c", "w")
    owed_cards = sorted(item["coordinate"][1] for item in owed(state_json(page_dir)))
    assert owed_cards == ["card-a", "card-b", "card-c"]


def test_a_queue_in_a_thread_owes_nothing_until_it_is_finished(page_dir):
    """A move leaving cards queued keeps the thread's obligation on the user."""
    declare_on_page(
        page_dir, lambda registry: registry.update(queue_board_registry(registry))
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Sort these follow-ups.",
            "markup": '<lf-board id="triage">'
            '<lf-column id="queue" label="Queued">'
            '<lf-card id="card-a"><strong>Rolling expiry</strong></lf-card>'
            '<lf-card id="card-b"><strong>Retry budget</strong></lf-card>'
            "</lf-column>"
            '<lf-column id="keep" label="Kept"></lf-column>'
            '<lf-column id="pass" label="Passed"></lf-column>'
            "</lf-board>",
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
    sorting = state_json(page_dir)
    assert sorting["workflows"] == []
    assert [item["widget"] for item in obligations_on_user(sorting)] == ["triage"]

    sort("card-b", "r")
    finished = state_json(page_dir)
    assert obligations_on_user(finished) == []
    assert sorted(item["coordinate"][1] for item in owed(finished)) == [
        "card-a",
        "card-b",
    ]
