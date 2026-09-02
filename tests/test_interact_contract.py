"""Event, registry, replay-contract, and media tests."""

import contextlib
import json
import re
import shutil
import threading
import time

import pytest
from click.testing import CliRunner
from interact_support import (
    ACCEPT,
    ADOPTED,
    COMMAND_HUB_PACKAGE,
    COMMAND_SUBJECTS,
    COMMENT,
    PAGE,
    PILOT_PURGE,
    REJECT,
    RESOLVE,
    SHELVED,
    TRIAL_CACHE,
    TRIAL_LOG,
    _body_record_with_nested_widget,
    _body_record_with_prose,
    _mutated_registry_check,
    _report_body_record,
    _report_detail_drift,
    _report_no_record,
    _report_says_attr,
    _report_undeclared_attr,
    _report_without_overruled,
    _report_without_upgrade,
    _state_with_optional_value_record,
    _tasks_version,
    assert_revendor_serializes_writer,
    check,
    comment,
    decide,
    declare_data_input,
    fetch,
    live_versions,
    logged,
    publish,
    published,
    stamp,
    styled,
    trial_version,
    widget_entry,
)
from leaf import cli as cli_model
from leaf import conversation as conversation_model
from leaf import data as data_model
from leaf import event_endpoint as event_endpoint_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import leases as leases_model
from leaf import media as media_model
from leaf import passages as passages_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import structure as structure_model
from leaf import styles as styles_model
from leaf import vendoring as vendoring_model
from leaf.registry import contract as registry_contract
from leaf.registry import layer as registry_layer
from leaf.registry import storage as registry_storage
from leaf.registry import validation as registry_validation
from leaf.render_gate import preview as render_gate_model


def test_only_declared_generated_children_add_mapping_keys_to_liveness():
    event = {
        "widget": "group",
        "detail": {
            "part": "authored-child",
            "metadata": {"coincidental-id": "ordinary mapping payload"},
            "additions": {"reader-child": "Reader supplied words"},
        },
        "generated": ["reader-child", "reader-child"],
    }
    spec = {"creates": {"field": "additions", "child": "lf-option"}}

    assert registry_contract.created_children(event, spec) == {
        "reader-child": "Reader supplied words"
    }
    assert event_folds_model.action_rests_on(event, {"authored-child": ("group",)}) == [
        "group",
        "authored-child",
        "reader-child",
    ]


def test_an_accept_carries_its_thread_resolution(page_dir):
    """One atomic event: the accept snapshots the thread it answers, because the
    honoring version retires the wrapper that held the `resolves` mapping and a
    second POST could fail alone. A reject answers nothing."""
    threads = logged(
        page_dir,
        COMMENT,
        {"kind": "comment", "id": "c2", "author": "user", "text": "the other thing"},
        ACCEPT,
        {**REJECT, "widget": "sug-b"},
    )
    assert threads["c1"]["resolved"]["widget"] == "sug-a"
    assert threads["c2"]["resolved"] is None


def test_an_answer_the_reader_took_back_leaves_its_thread_open(page_dir):
    """An action names the thread it settles, and it settles it only while the
    reader still stands behind it. Withdrawing the answer is one of the three ways
    an action stops standing — a `restated` version and a later answer from the
    same widget are the others — and the thread reading owes all three the same
    reply, or a question would read as answered by a gesture the log itself records
    as taken back."""
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "which mounts?"},
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "id": "a1",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"options": ["flag-first"], "resolves": "c1"},
            "generated": [],
        },
    )
    spk = passages_model.spoken(
        (page_dir / "versions" / "v1.html").read_text(encoding="utf-8"),
        registry_storage.require_registry(page_dir),
    )
    threads = event_folds_model.build_threads(
        events_model.read_events(page_dir), passages_model.enclosing_of(spk)
    )
    assert threads["c1"]["resolved"]["id"] == "a1"

    events_model.append_event(
        page_dir, {"kind": "undo", "author": "user", "undoes": "a1"}
    )
    threads = event_folds_model.build_threads(
        events_model.read_events(page_dir), passages_model.enclosing_of(spk)
    )
    assert threads["c1"]["resolved"] is None


def test_server_takes_back_only_a_standing_gesture_of_the_readers_own(server, page_dir):
    """`undoes` is checked completely where it enters, so nothing downstream asks a
    second time whether it points at something real. What an undo may name is one
    unwithdrawn gesture of the reader's own: an agent's `leaf resolve` is not
    theirs to take back, a comment is speech rather than state, an undo is not
    itself undoable (that would be a redo), and one gesture cannot be taken back
    twice."""
    publish(page_dir)
    posted = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": "hi"}).encode(),
        )[1]
    )["state"]["events"][-1]
    resolved = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "resolve", "parent": posted["id"]}).encode(),
        )[1]
    )["state"]["events"][-1]
    agent_closed = events_model.append_event(
        page_dir, {"kind": "resolve", "author": "claude", "parent": posted["id"]}
    )

    for bad, says in [
        ({"kind": "undo", "undoes": "nope"}, "unknown"),
        # The reader's own gestures only, and only the kinds that carry state.
        (
            {"kind": "undo", "undoes": agent_closed["id"]},
            "not the reader's own gesture",
        ),
        ({"kind": "undo", "undoes": posted["id"]}, "is not a reaction"),
        # The one field it carries, and the door refuses it in any other shape.
        ({"kind": "undo"}, "'undoes' is a required property"),
        (
            {"kind": "undo", "undoes": resolved["id"], "widget": "x"},
            "widget",
        ),
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, bad
        answer = json.loads(body)
        assert answer["ok"] is False and answer["final"] is True, bad
        assert says in answer["error"], body

    undone = {"kind": "undo", "undoes": resolved["id"]}
    status, body = fetch(f"{server}/api/event", data=json.dumps(undone).encode())
    assert status == 200, body
    took_back = json.loads(body)["state"]["events"][-1]

    # Once, and never the undo itself: repeated presses walk back through the
    # reader's history rather than toggling the last gesture on and off.
    status, body = fetch(f"{server}/api/event", data=json.dumps(undone).encode())
    assert status == 400 and "already been taken back" in json.loads(body)["error"]
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": took_back["id"]}).encode(),
    )
    assert status == 400 and "undo events cannot be taken" in json.loads(body)["error"]


def test_two_concurrent_undos_cannot_both_take_back_one_gesture(
    server, page_dir, monkeypatch
):
    """Mutable validation and append are one log transaction. Two request threads
    may arrive together, but the second must read the first withdrawal before it can
    validate its own; otherwise both can truthfully validate against a state neither
    is allowed to append beside the other."""
    publish(page_dir)
    comment = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "revision": 1, "text": "close this"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    target = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "resolve", "parent": comment["id"]}).encode(),
        )[1]
    )["state"]["events"][-1]

    # The old handler validated outside the append transaction. Let its first
    # validation wait briefly for the second: on that shape both requests read the
    # same standing target and proceed, while the transactional handler keeps the
    # second outside until the first append is visible. A bounded wait keeps the
    # correct serialization from deadlocking the probe itself.
    real_undo_error = event_endpoint_model.undo_error
    validation_lock = threading.Lock()
    second_validation = threading.Event()
    validation_calls = 0

    def expose_validation_gap(event, events, within):
        nonlocal validation_calls
        error = real_undo_error(event, events, within)
        with validation_lock:
            validation_calls += 1
            call = validation_calls
        if call == 1:
            second_validation.wait(timeout=1)
        else:
            second_validation.set()
        return error

    monkeypatch.setattr(event_endpoint_model, "undo_error", expose_validation_gap)
    start = threading.Barrier(3)
    results = []

    def withdraw(attempt):
        start.wait(timeout=5)
        results.append(
            fetch(
                f"{server}/api/event",
                data=json.dumps(
                    {
                        "kind": "undo",
                        "undoes": target["id"],
                        "attempt": attempt,
                    }
                ).encode(),
            )
        )

    threads = [
        threading.Thread(target=withdraw, args=(f"concurrent-undo-{at}",))
        for at in range(2)
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert validation_calls == 2
    assert {status for status, _ in results} == {200, 400}
    refusal = next(json.loads(body) for status, body in results if status == 400)
    assert refusal["final"] is True and "already been taken back" in refusal["error"]
    undos = [
        event
        for event in events_model.read_events(page_dir)
        if event.get("undoes") == target["id"]
    ]
    assert len(undos) == 1


def test_a_reject_after_an_accept_reopens_the_thread(page_dir):
    """A thread stands settled by its widget's standing answer, not by the fact an
    answer was once given. Turning the fix down and leaving the question filed away
    as answered by it is invisible from both sides — the fold reports the suggestion
    rejected while the panel reports the thread closed, and nothing says so.

    Read across the reject rather than after it: an assertion that the thread is open
    passes just as well on a log where the accept never settled it."""
    assert logged(page_dir, COMMENT, ACCEPT)["c1"]["resolved"]["action"] == "accept"
    assert logged(page_dir, REJECT)["c1"]["resolved"] is None


def test_an_accept_after_a_reject_settles_the_thread(page_dir):
    """The other order, which the one-way latch already got right — this pins it
    against the fix for the latch, not against the latch. A fold that kept the
    first answer per widget rather than the last reads every case here correctly
    except this one, where nothing would ever settle the thread."""
    assert logged(page_dir, COMMENT, REJECT)["c1"]["resolved"] is None
    assert logged(page_dir, ACCEPT)["c1"]["resolved"]["action"] == "accept"


def test_a_resolve_between_two_decisions_outlives_the_second(page_dir):
    """A resolve is a person saying the conversation is done, and the log cannot
    take that back the way it takes back a decision. The one-way latch got this
    right by never clearing anything; what it pins is the obvious wrong fix for the
    latch — a reject that clears whatever its widget resolved — which would wipe a
    press made in between. Settling in place is what makes it hold: the superseded
    accept never stood, so it has nothing to clear."""
    assert (
        logged(page_dir, COMMENT, ACCEPT, RESOLVE)["c1"]["resolved"]["kind"]
        == "resolve"
    )
    assert logged(page_dir, REJECT)["c1"]["resolved"]["kind"] == "resolve"


def test_taking_back_a_reject_lets_the_accept_it_superseded_stand_again(page_dir):
    """The two ways an answer stops standing compose, and this is where they meet: a
    reject supersedes the accept before it, and taking the reject back leaves the
    accept standing as the widget's answer once more. A withdrawal read only by the
    walk and not by the standing answer would leave the thread open with the log
    holding nothing that says so."""
    assert (
        logged(page_dir, COMMENT, ACCEPT, {**REJECT, "id": "r1"})["c1"]["resolved"]
        is None
    )
    undone = {"kind": "undo", "author": "user", "undoes": "r1"}
    assert logged(page_dir, undone)["c1"]["resolved"]["action"] == "accept"


def test_another_widget_s_answer_holds_a_thread_two_widgets_answered(page_dir):
    """Superseding is per widget, because the decision is. Two suggestions can answer one
    question, and deciding against the second says nothing about the first — a fold
    keyed on the thread instead of the widget would have let it."""
    threads = logged(page_dir, COMMENT, {**ACCEPT, "widget": "sug-b"}, ACCEPT, REJECT)
    assert threads["c1"]["resolved"]["widget"] == "sug-b"


def test_init_refuses_a_log_the_incoming_layer_no_longer_speaks(page_dir):
    """The log is append-only and a retired verb has no successor to map to, so
    re-vendoring over one is how recorded decisions fall silent — annabels-drafts
    holds fifteen `decide` events today's widgets would drop on the first reload.
    The re-vendor is refused rather than offering a way to discard that history."""
    # This models a page made under an older registry where lf-draft declared
    # `decide`: the tag and widget id survive, but the incoming verb does not.
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>A decision.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "d1",
            "action": "decide",
            "detail": {"decision": "approved"},
        },
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "decide" in result.output


def test_init_refuses_to_retire_a_logged_host_request_verb(page_dir):
    """A recorded request must remain interpretable for the life of the log."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-decision id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-decision></lf-task></lf-command>"
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", operation + "</section>")
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "request",
            "author": "user",
            "revision": 1,
            "widget": "commands",
            "action": "restart",
            "detail": {"target": "goal", "worker": "worker", "worktree": "tree"},
        },
    )
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-operations"]["x-request"]["verbs"]["restart"]
    registry["lf-operation"]["properties"]["verb"]["enum"].remove("restart")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "lf-operations": registry["lf-operations"],
                "lf-operation": registry["lf-operation"],
            }
        )
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "request contract" in result.output and "restart" in result.output


@pytest.mark.parametrize("receipt_requests", [["missing"], ["request-1", "request-1"]])
def test_init_refuses_a_receipt_without_one_prior_unsettled_request(
    page_dir, receipt_requests
):
    """Re-vendoring rejects orphan and duplicate terminal outcomes in log order."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-decision id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-decision></lf-task></lf-command>"
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", operation + "</section>")
    )
    publish(page_dir)
    if receipt_requests[0] != "missing":
        events_model.append_event(
            page_dir,
            {
                "id": "request-1",
                "kind": "request",
                "author": "user",
                "revision": 1,
                "widget": "commands",
                "action": "restart",
                "detail": {
                    "target": "goal",
                    "worker": "worker",
                    "worktree": "tree",
                },
            },
        )
    for index, request in enumerate(receipt_requests, 1):
        events_model.append_event(
            page_dir,
            {
                "id": f"receipt-{index}",
                "kind": "receipt",
                "author": "claude",
                "request": request,
                "status": "succeeded",
                "text": "Host operation completed",
            },
        )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "receipt contract" in result.output, result.output


def test_init_refuses_a_log_holding_a_token_the_incoming_layer_dropped(
    page_dir, monkeypatch
):
    """A layer may take a token off its bar (merge-patch `null`), and a page whose log
    already holds a reaction on it is refused a re-vendor the way one holding a
    retired verb is: the standing mark would have no glyph and no pill to take it
    back by. A token the layer keeps re-vendors as before."""
    publish(page_dir)
    events_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "token": "cut"}
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)]).exit_code
        == 0
    )
    layer = page_dir.parent / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(
        json.dumps({"$reactions": {"tokens": {"cut": None}}})
    )
    monkeypatch.chdir(page_dir.parent)
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "no longer speaks" in result.output and "`cut`" in result.output


def test_init_refuses_a_logged_event_field_the_incoming_layer_no_longer_speaks(
    page_dir,
):
    """An older or custom layer may have added a field without adding a kind.
    The vocabulary stamp promises both, so retaining the kind alone cannot make
    the recorded field meaningful to the incoming runtime."""
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Codex",
            "mood": "uncertain",
            "revision": 1,
            "text": "Does this still mean anything?",
        },
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "comment" in result.output and "mood" in result.output


def test_init_tracks_logged_verbs_by_the_widget_that_declared_them(page_dir):
    """Another tag using the same verb cannot keep a retired contract alive."""
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"]
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
        },
    )

    move_spec = registry["lf-board"]["x-state"]["move"]
    board_entry = registry["lf-board"]
    board_entry.pop("x-state")
    # Reusing the generic verb on another widget leaves the global verb set
    # unchanged, but cannot make an old lf-board action meaningful there.
    registry["lf-draft"]["x-state"]["move"] = move_spec
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "lf-board": board_entry,
                "lf-draft": registry["lf-draft"],
            }
        )
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "lf-board" in result.output and "move" in result.output


def test_init_refuses_an_incoming_detail_contract_that_rejects_logged_actions(
    page_dir,
):
    """Keeping a verb's spelling is not enough if its payload no longer replays."""
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"]
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
        },
    )

    registry["lf-board"]["x-state"]["move"]["detail"]["properties"]["index"][
        "minimum"
    ] = 1
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-board": registry["lf-board"]})
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "lf-board" in result.output and "move" in result.output
    assert "detail" in result.output


@pytest.mark.parametrize("mutation", ["drop", "field", "child"])
def test_init_refuses_changed_generated_child_semantics(page_dir, mutation):
    registry = json.loads((page_dir / "registry.json").read_text())
    options = (
        '<lf-decision id="route-decision"><h2>Which route?</h2>'
        '<lf-options id="route" choose>'
        '<lf-option id="route-authored">Authored route</lf-option>'
        "</lf-options></lf-decision>"
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", options + "</section>")
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "route",
            "action": "choose",
            "detail": {
                "options": ["route-reader"],
                "additions": {"route-reader": "Reader route"},
            },
            "generated": ["route-reader"],
        },
    )

    choose = registry["lf-options"]["x-state"]["choose"]
    overlay_entries = {"lf-options": registry["lf-options"]}
    if mutation == "drop":
        del choose["creates"]
    elif mutation == "field":
        choose["creates"]["field"] = "extras"
        choose["detail"]["properties"]["extras"] = choose["detail"]["properties"][
            "additions"
        ]
    else:
        registry["lf-option-alt"] = registry["lf-option"]
        choose["creates"]["child"] = "lf-option-alt"
        overlay_entries["lf-option-alt"] = registry["lf-option-alt"]
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text(json.dumps(overlay_entries))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "action contract" in result.output


def test_init_does_not_rejudge_logged_actions_by_new_current_eligibility(page_dir):
    """Eligibility governs fresh transitions, not the log's forever-contract.

    A recorded action remains structurally meaningful even if a replacement layer
    would no longer offer that gesture in the same state. Re-vendoring must preserve
    and replay it rather than applying today's admission policy retroactively.
    """
    registry = json.loads((page_dir / "registry.json").read_text())
    options = (
        '<lf-decision id="run-status-decision"><h2>Which run status?</h2>'
        '<lf-options id="run-status" choose>'
        '<lf-option id="rs-column">Column</lf-option>'
        "</lf-options></lf-decision>"
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("</section>", options + "\n</section>")
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "run-status",
            "action": "choose",
            "detail": {"options": ["rs-column"]},
            "generated": [],
        },
    )

    registry["lf-options"]["x-state"]["choose"]["requires"] = {
        "target": "self",
        "awaiting": True,
    }
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-options": registry["lf-options"]})
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    assert [
        event["action"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "action"
    ] == ["choose"]


def test_init_refuses_a_logged_report_the_incoming_layer_no_longer_speaks(page_dir):
    """A report is the log's forever-contract exactly as an action is: an
    incoming layer that drops the widget's x-report verb strands every recorded
    report, and the stamp refuses the re-vendor rather than let them fall
    silent."""
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "</section>",
            '<lf-tasks id="tree"><lf-task id="t1" status="active">'
            "<strong>Parse</strong></lf-task></lf-tasks></section>",
        )
    )
    publish(page_dir)
    assert (
        CliRunner()
        .invoke(cli_model.cli, ["report", str(page_dir), "t1", "status", "status=done"])
        .exit_code
        == 0
    )

    registry = json.loads((page_dir / "registry.json").read_text())
    task = registry["lf-task"]
    task.pop("x-report")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-task": task}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "report contract" in result.output
    assert "lf-task" in result.output and "status" in result.output


def test_init_refuses_to_orphan_a_logged_visual_anchor(page_dir):
    """A re-vendored provider must keep every semantic target the log names."""
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            '<lf-diagram id="flow">',
            '<lf-diagram id="flow" parts="node:A node:B">',
        )
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "flow", "visual": "node:A"},
            "text": "keep this target",
        },
    )

    registry = json.loads((page_dir / "registry.json").read_text())
    diagram = registry["lf-diagram"]
    diagram.pop("x-visual")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-diagram": diagram}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "visual anchor 'node:A'" in result.output


def test_report_validation_and_append_cannot_straddle_revendoring(
    page_dir, monkeypatch
):
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    task = registry["lf-task"]
    task.pop("x-report")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-task": task}))

    transition = leases_model.transition_lock(page_dir)
    report_validated = threading.Event()
    release_report = threading.Event()
    init_waiting = threading.Event()
    real_append = service_model.PageTransaction.append_event
    real_flocked = vendoring_model.flocked

    def paused_append(page, event):
        if event["kind"] == "report":
            report_validated.set()
            assert release_report.wait(5)
        return real_append(page, event)

    @contextlib.contextmanager
    def observed_flocked(path):
        if path == transition and threading.current_thread().name == "re-vendor":
            init_waiting.set()
        with real_flocked(path) as held:
            yield held

    monkeypatch.setattr(service_model.PageTransaction, "append_event", paused_append)
    monkeypatch.setattr(vendoring_model, "flocked", observed_flocked)
    outcomes, errors = [], []

    def report():
        try:
            conversation_model.cmd_report(
                page_dir, "t-parser", "status", ("status=done",)
            )
            outcomes.append("reported")
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    def revendoring():
        try:
            vendoring_model.cmd_init(page_dir)
            outcomes.append("revendored")
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    reporting = threading.Thread(target=report, name="report")
    reporting.start()
    assert report_validated.wait(5)
    initing = threading.Thread(target=revendoring, name="re-vendor")
    initing.start()
    assert init_waiting.wait(5)
    release_report.set()
    reporting.join(timeout=5)
    initing.join(timeout=5)

    assert not reporting.is_alive() and not initing.is_alive()
    assert outcomes == ["reported"]
    assert len(errors) == 1 and "report contract" in str(errors[0])
    assert events_model.read_events(page_dir)[-1]["kind"] == "report"
    assert "x-report" in json.loads((page_dir / "registry.json").read_text())["lf-task"]


def test_a_preview_holds_one_contract_until_it_closes(page_dir, monkeypatch):
    before = registry_storage.layer_generation(page_dir)
    transition = leases_model.transition_lock(page_dir)
    init_waiting = threading.Event()
    real_flocked = vendoring_model.flocked

    @contextlib.contextmanager
    def observed_flocked(path):
        if path == transition and threading.current_thread().name == "re-vendor":
            init_waiting.set()
        with real_flocked(path) as held:
            yield held

    monkeypatch.setattr(vendoring_model, "flocked", observed_flocked)
    errors = []

    def revendoring():
        try:
            vendoring_model.cmd_init(page_dir)
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    with render_gate_model.preview_server(
        page_dir,
        (page_dir / "index.html").read_bytes(),
        1,
    ):
        initing = threading.Thread(target=revendoring, name="re-vendor")
        initing.start()
        assert init_waiting.wait(5)
        assert registry_storage.layer_generation(page_dir) == before

    initing.join(timeout=5)
    assert not initing.is_alive()
    assert errors == []
    assert registry_storage.layer_generation(page_dir) != before


def test_revendoring_cannot_pass_a_browser_action_still_entering_the_log(
    page_dir, server, monkeypatch
):
    registry = json.loads((page_dir / "registry.json").read_text())
    version = page_dir / "versions/v1.html"
    version.write_text(
        version.read_text().replace(
            "</section>", registry["lf-board"]["x-example"] + "\n</section>"
        )
    )
    publish(page_dir)
    board = registry["lf-board"]
    board["x-state"]["move"]["detail"]["properties"]["index"]["minimum"] = 1
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-board": board}))
    action = json.dumps(
        {
            "kind": "action",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
        }
    ).encode()
    (status, body), refusal = assert_revendor_serializes_writer(
        page_dir, monkeypatch, "action", lambda: fetch(f"{server}/api/event", action)
    )

    assert status == 200, body
    assert "no longer speaks" in refusal and "move" in refusal


def test_revendoring_cannot_pass_a_worker_report_still_entering_the_log(
    page_dir, monkeypatch
):
    _tasks_version(page_dir, 1, "active")
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    task = registry["lf-task"]
    task.pop("x-report")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-task": task}))
    _, refusal = assert_revendor_serializes_writer(
        page_dir,
        monkeypatch,
        "report",
        lambda: conversation_model.cmd_report(
            page_dir, "t-parser", "status", ("status=review",)
        ),
    )

    assert "no longer speaks" in refusal and "status" in refusal


def test_revendoring_cannot_pass_thread_markup_still_entering_the_log(
    page_dir, monkeypatch
):
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    local = widget_entry("lf-local-thread")
    (overlay / "registry.json").write_text(json.dumps({"lf-local-thread": local}))
    vendoring_model.cmd_init(page_dir)
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    (overlay / "registry.json").unlink()
    markup = '<lf-local-thread id="thread-local">Choose locally.</lf-local-thread>'
    _, refusal = assert_revendor_serializes_writer(
        page_dir,
        monkeypatch,
        "reply",
        lambda: conversation_model.cmd_reply(page_dir, "c1", "Pick one:", markup),
    )

    assert "lf-local-thread" in refusal


def test_revendoring_cannot_turn_logged_thread_markup_into_a_settlement(
    page_dir,
):
    """Frozen thread markup keeps the admission rules of its vendored vocabulary."""
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    markup = (
        '<lf-decision id="thread-choice-decision"><h3>Which option?</h3>'
        '<lf-options id="thread-choice" choose>'
        '<lf-option id="thread-a">A</lf-option>'
        "</lf-options></lf-decision>"
    )
    conversation_model.cmd_reply(page_dir, "c1", "Pick one:", markup)

    registry = json.loads((page_dir / "registry.json").read_text())
    option = registry["lf-option"]
    option["x-retired-when"] = "choose"
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-option": option}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "thread markup contract" in result.output
    assert "lf-options" in result.output


def test_check_refuses_a_malformed_registry(page_dir):
    (page_dir / "registry.json").write_text("{broken")
    result = check(page_dir)
    assert result.exit_code != 0
    assert "invalid JSON" in result.output


@pytest.mark.parametrize(
    ("contracts", "message"),
    [
        ({"Bad Name": {"description": "x", "schema": {}}}, "invalid contract name"),
        ({"builds": {"schema": {}}}, "description and schema"),
        (
            {"builds": {"description": "Build facts.", "schema": {"type": "nope"}}},
            "invalid JSON Schema",
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {"$ref": "https://schemas.example/build.json"},
                }
            },
            "must be self-contained",
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {"$defs": {}, "$ref": "#/$defs/missing"},
                }
            },
            "must be self-contained",
        ),
        (
            {
                "builds": {
                    "description": "Build facts.",
                    "schema": {"type": "object"},
                    "fragments": {"items": "rows", "key": "id", "value": "id"},
                }
            },
            "fragments must name distinct",
        ),
    ],
)
def test_the_registry_door_validates_data_contracts(page_dir, contracts, message):
    """A contract is executable widget vocabulary: its name carries meaning and its
    schema admits bytes to the browser, so package checking refuses an ambiguous name,
    an undocumented contract, or a schema no boundary can run."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$data"]["contracts"] = contracts
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "$data" in result.output and message in result.output


@pytest.mark.parametrize(
    "schema",
    [
        {"const": {"$ref": "https://example.invalid/literal-value"}},
        {
            "$defs": {"row": {"type": "string"}},
            "type": "array",
            "items": {"$ref": "#/$defs/row"},
        },
    ],
)
def test_package_data_schema_allows_literal_refs_and_resolved_local_refs(
    page_dir, schema
):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$data"]["contracts"]["builds"] = {
        "description": "Build facts.",
        "schema": schema,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda entry: entry["x-data"]["data"].update(
                {"contract": "missing-contract"}
            ),
            "names unknown contract",
        ),
        (
            lambda entry: entry["properties"].pop("source"),
            "must be a canonical data source string",
        ),
        (
            lambda entry: entry["properties"]["source"].update(
                {"pattern": "^anything$"}
            ),
            "must be a canonical data source string",
        ),
        (
            lambda entry: entry.update({"x-guidance": {"author": ""}}),
            "should be non-empty",
        ),
    ],
)
def test_a_widget_data_input_is_one_complete_contract(page_dir, change, message):
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = json.loads((page_dir / "registry.json").read_text())
    change(registry["lf-test-data"])

    with pytest.raises(registry_contract.RegistryError, match=message):
        registry_validation.validate_registry(registry, "test registry")


def test_a_data_source_attribute_can_carry_ordinary_schema_metadata(page_dir):
    """x-data requires the canonical string contract, not one byte-for-byte schema;
    packages remain free to document or further constrain the attribute."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-test-data"]["properties"]["source"]["description"] = (
        "The page-owned feed id."
    )
    registry["lf-test-data"]["required"].remove("source")

    assert registry_validation.validate_registry(registry, "test registry") is registry


def test_a_data_snapshot_selector_is_a_positive_decimal_authored_binding(page_dir):
    declare_data_input(page_dir, "project-feed", {"type": "array"}, snapshot=True)
    registry = json.loads((page_dir / "registry.json").read_text())

    assert registry_validation.validate_registry(registry, "test registry") is registry

    registry["lf-test-data"]["properties"]["snapshot"]["pattern"] = "^[0-9]+$"
    with pytest.raises(
        registry_contract.RegistryError, match="must be a positive decimal string"
    ):
        registry_validation.validate_registry(registry, "test registry")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda entry: entry["x-measured"].update({"input": "missing"}),
            "is not one of its x-data inputs",
        ),
        (
            lambda entry: entry["required"].remove("source"),
            "source attribute `source` must be required",
        ),
        (
            lambda entry: entry["required"].remove("at"),
            "must be required and declare a date-time string",
        ),
        (
            lambda entry: entry["properties"]["at"].pop("format"),
            "must be required and declare a date-time string",
        ),
    ],
)
def test_a_measured_widget_joins_one_data_input_to_one_aware_instant(
    page_dir, change, message
):
    """The generic check cannot infer a widget's source or timestamp. Its registry
    declaration names both, and the registry door refuses a half-readable join before
    an authored value can silently miss the freshness advisory."""
    registry = json.loads((page_dir / "registry.json").read_text())
    change(registry["lf-num"])

    with pytest.raises(registry_contract.RegistryError, match=message):
        registry_validation.validate_registry(registry, "test registry")


def test_a_measurement_timestamp_cannot_also_be_replay_writable(page_dir):
    """The capture instant belongs to the authored version. Letting replay write it
    would give the browser a newer freshness boundary than file checks and page state
    read from the immutable document."""
    registry = json.loads((page_dir / "registry.json").read_text())
    widget = registry["lf-num"]
    widget["x-upgrade"] = True
    widget["properties"]["restated"] = {"type": "boolean"}
    widget["x-state"] = {
        "retime": {
            "detail": {
                "type": "object",
                "properties": {"at": widget["properties"]["at"]},
                "required": ["at"],
                "additionalProperties": False,
            },
            "facet": "capture",
            "unit": "widget",
            "record": {"kind": "value", "attr": "at", "value": "at"},
        }
    }

    with pytest.raises(
        registry_contract.RegistryError,
        match="x-measured timestamp attribute `at` is an authored snapshot instant",
    ):
        registry_validation.validate_registry(registry, "test registry")


def test_a_data_source_attribute_cannot_also_be_replay_writable(page_dir):
    """The authored document owns a widget's binding for that element lifetime. A
    value record on the same attribute would make replay paint a source that the
    already-mounted watcher correctly does not consume."""
    declare_data_input(page_dir, "project-feed", {"type": "array"})
    registry = json.loads((page_dir / "registry.json").read_text())
    widget = registry["lf-test-data"]
    widget["x-state"] = {
        "rebind": {
            "detail": {
                "type": "object",
                "properties": {"source": widget["properties"]["source"]},
                "required": ["source"],
                "additionalProperties": False,
            },
            "facet": "binding",
            "unit": "widget",
            "record": {"kind": "value", "attr": "source", "value": "source"},
        }
    }

    with pytest.raises(
        registry_contract.RegistryError,
        match="x-data binding attributes are authored",
    ):
        registry_validation.validate_registry(registry, "test registry")


def test_revendoring_cannot_forget_a_historical_data_binding(page_dir):
    """Clearing a replaceable value does not erase the meaning an immutable version
    gave its source id. An incoming layer must still understand that binding because a
    pinned reader can keep consuming the page's current data store."""
    declare_data_input(
        page_dir,
        "builds",
        {"type": "array"},
        contract="builds",
    )
    data_model.cmd_data_set(page_dir, "builds", [])

    refused = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert refused.exit_code != 0
    assert "immutable documents" in refused.output
    assert "source 'builds' loses its contract 'builds'" in refused.output
    assert "preserve those bindings" in refused.output
    cleared = CliRunner().invoke(
        cli_model.cli, ["data", "clear", str(page_dir), "builds"]
    )
    assert cleared.exit_code == 0, cleared.output
    still_refused = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert still_refused.exit_code != 0
    assert "source 'builds' loses its contract 'builds'" in still_refused.output


def test_revendoring_cannot_forget_an_immutable_data_selection(page_dir, tmp_path):
    declare_data_input(
        page_dir,
        "leaf-skill",
        {"type": "string"},
        contract="text-document",
        snapshot=True,
    )
    text_file = tmp_path / "SKILL.md"
    text_file.write_text("captured")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            'source="leaf-skill"', 'source="leaf-skill" snapshot="1"'
        )
    )
    activated = revisioning_model.activate_source(
        page_dir, events_model.read_events(page_dir)
    )
    assert activated.error is None
    incoming = json.loads((page_dir / "registry.json").read_text())
    del incoming["lf-test-data"]["x-data"]["data"]["snapshot"]

    with pytest.raises(SystemExit, match="changes immutable snapshot selection"):
        vendoring_model._refuse_data_contract_drift(
            page_dir, events_model.read_events(page_dir), incoming
        )

    outgoing = json.loads((page_dir / "registry.json").read_text())
    del outgoing["lf-test-data"]["x-data"]["data"]["snapshot"]
    (page_dir / "registry.json").write_text(json.dumps(outgoing))
    incoming = json.loads(json.dumps(outgoing))
    incoming["lf-test-data"]["x-data"]["data"]["snapshot"] = "snapshot"
    with pytest.raises(SystemExit, match="changes immutable snapshot selection"):
        vendoring_model._refuse_data_contract_drift(
            page_dir, events_model.read_events(page_dir), incoming
        )


def test_revendoring_cannot_swap_immutable_selections_between_inputs(
    page_dir, tmp_path
):
    declare_data_input(
        page_dir,
        "leaf-skill",
        {"type": "string"},
        contract="text-document",
        snapshot=True,
    )
    text_file = tmp_path / "SKILL.md"
    text_file.write_text("first")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)
    text_file.write_text("second")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)

    registry_path = page_dir / "registry.json"
    outgoing = json.loads(registry_path.read_text())
    widget = outgoing["lf-test-data"]
    del widget["properties"]["snapshot"]
    widget["properties"].update(
        {
            "left-snapshot": {
                "type": "string",
                "pattern": "^[1-9][0-9]*$",
            },
            "right-snapshot": {
                "type": "string",
                "pattern": "^[1-9][0-9]*$",
            },
        }
    )
    widget["x-data"] = {
        "left": {
            "contract": "text-document",
            "source": "source",
            "snapshot": "left-snapshot",
        },
        "right": {
            "contract": "text-document",
            "source": "source",
            "snapshot": "right-snapshot",
        },
    }
    registry_path.write_text(json.dumps(outgoing))
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            'source="leaf-skill"',
            'source="leaf-skill" left-snapshot="1" right-snapshot="2"',
        )
    )
    activated = revisioning_model.activate_source(
        page_dir, events_model.read_events(page_dir)
    )
    assert activated.error is None

    incoming = json.loads(json.dumps(outgoing))
    incoming["lf-test-data"]["x-data"]["left"]["snapshot"] = "right-snapshot"
    incoming["lf-test-data"]["x-data"]["right"]["snapshot"] = "left-snapshot"

    with pytest.raises(SystemExit, match="changes immutable snapshot selection"):
        vendoring_model._refuse_data_contract_drift(
            page_dir, events_model.read_events(page_dir), incoming
        )


def test_revendoring_distinguishes_idless_snapshot_seats_on_one_line(
    page_dir, tmp_path
):
    declare_data_input(
        page_dir,
        "leaf-skill",
        {"type": "string"},
        contract="text-document",
        snapshot=True,
    )
    text_file = tmp_path / "SKILL.md"
    text_file.write_text("first")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)
    text_file.write_text("second")
    data_model.cmd_data_capture(page_dir, "leaf-skill", text_file)

    registry_path = page_dir / "registry.json"
    outgoing = json.loads(registry_path.read_text())
    widget = outgoing["lf-test-data"]
    widget["required"].remove("id")
    widget["properties"]["alternate"] = {
        "type": "string",
        "pattern": "^[1-9][0-9]*$",
    }
    registry_path.write_text(json.dumps(outgoing))
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            '<lf-test-data id="test-data" source="leaf-skill"></lf-test-data>',
            '<lf-test-data source="leaf-skill" snapshot="1" '
            'alternate="2"></lf-test-data><lf-test-data source="leaf-skill" '
            'snapshot="2" alternate="2"></lf-test-data>',
        )
    )
    activated = revisioning_model.activate_source(
        page_dir, events_model.read_events(page_dir)
    )
    assert activated.error is None

    incoming = json.loads(json.dumps(outgoing))
    incoming["lf-test-data"]["x-data"]["data"]["snapshot"] = "alternate"
    with pytest.raises(SystemExit, match="changes immutable snapshot selection"):
        vendoring_model._refuse_data_contract_drift(
            page_dir, events_model.read_events(page_dir), incoming
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (None, "registry entries must be objects"),
        ({"type": "not-a-schema-type"}, "not a valid JSON Schema"),
    ],
)
def test_check_refuses_a_malformed_widget_schema(page_dir, entry, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"] = entry
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "lf-options" in result.output and message in result.output


def test_the_registry_door_refuses_an_open_detail_schema(page_dir):
    """A verb carries only the detail keys it declares — thread settlement
    dispatches on `resolves` being present, which is safe exactly because a
    closed schema makes carrying it a declaration."""
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["x-state"]["accept"]["detail"]["additionalProperties"]
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "additionalProperties: false" in result.output


def test_the_registry_door_holds_a_detail_schema_to_the_keys_it_names(page_dir):
    """`additionalProperties: false` closes an object only against names
    `properties` does not match, so a `patternProperties` beside it admits a
    field no declaration spells — and `resolves` is a field, which is how a
    per-card verb could come to settle a comment thread with every door that
    reads the name seeing nothing to read. Each of those doors reads the
    declaration rather than the event, so one unnamed key makes all of them
    approximate at once.

    Asked of `lf-board`, whose `move` folds per card: the thread-answer door
    holds a settling verb to the whole widget, and this is the way past it."""
    registry = json.loads((page_dir / "registry.json").read_text())
    move = registry["lf-board"]["x-state"]["move"]
    move["detail"]["patternProperties"] = {"^resolv": {"type": "string"}}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "patternProperties" in result.output


def test_the_registry_door_holds_resolves_to_a_string(page_dir):
    """`resolves` is the layer's name for the thread an action answers; a verb
    declaring it as anything else would settle threads with an unhashable key —
    a TypeError in every command that builds threads, on the first event."""
    registry = json.loads((page_dir / "registry.json").read_text())
    accept = registry["lf-suggestion"]["x-state"]["accept"]
    accept["detail"]["properties"]["resolves"] = {"type": "array"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "resolves" in result.output and "string" in result.output


def test_the_registry_door_keeps_thread_answers_out_of_the_agent_channel(page_dir):
    """Both thread builders read `resolves` off actions, so the name on a report
    verb declares an answer nothing gives: the report folds like any other and
    settles no thread ever. That is the feature nobody wired up rather than an
    error, which is the shape this door exists to turn around."""
    registry = json.loads((page_dir / "registry.json").read_text())
    entry = registry["lf-task"]
    verb = next(iter(entry["x-report"]))
    entry["x-report"][verb]["detail"]["properties"]["resolves"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "resolves" in result.output and "x-state" in result.output


def test_the_registry_door_holds_a_thread_answer_to_the_whole_widget(page_dir):
    """Both thread builders key a widget's standing answer on the widget id — the
    one key a log outlives its markup with, the honoring version having retired the
    element. A verb answering a thread while folding per part would fold per part
    and settle per widget, and the thread would read right until a second part was
    acted on. The door is where whoever writes that widget finds out.

    Asked of a board rather than a suggestion, whose own verbs are held to the
    widget by the retirement gate as well — so what fails here can only be this
    one."""
    registry = json.loads((page_dir / "registry.json").read_text())
    move = registry["lf-board"]["x-state"]["move"]
    move["detail"]["properties"]["resolves"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "resolves" in result.output and "card" in result.output


def test_containment_reads_the_same_with_a_vocabulary_and_without_one(page_dir):
    """The two halves of a `spoken` reading come from different places. Words are
    the vocabulary's word — fences, x-says, chrome — but where an element sits is
    recorded off the tag stack before anything asks the registry what it shows.
    That is the whole of what liveness asks a page, and it is why the readings
    that may not raise on the registry gate need give nothing up.

    The words are the control: they must differ, or `spoken({})` would be the
    whole reading and the distinction this rests on would not exist."""
    html = (page_dir / "versions" / "v1.html").read_text(encoding="utf-8")
    registry = registry_storage.require_registry(page_dir)
    full = passages_model.spoken(html, registry)
    assert passages_model.enclosing_ids(html) == passages_model.enclosing_of(full)
    bare = passages_model.spoken(html, {})
    assert any(full[wid].words != bare[wid].words for wid in full)


SUGGESTION_HOLDING_A_NAMESAKE = PAGE.replace(
    "<lf-diagram",
    '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p id="c1">Poll every '
    "5 minutes.</p></lf-new></lf-suggestion>\n  <lf-diagram",
)


def test_a_thread_answer_reads_the_same_wherever_it_is_folded(page_dir):
    """`resolves` names a conversation, and thread ids and page ids are separate
    namespaces that can spell the same string. Read like any other detail value it
    would rest the accept on whichever element shared the name — here a paragraph
    the suggestion itself proposes — and the version that rewrote that paragraph
    would take back an answer it has nothing to do with.

    Every fold gets the same containment, so `page state` and the transcript,
    which hold the whole page, answer as the Stop hook and a wait's delivery do,
    which hold only where each id sits. A decision cannot stand at one and be
    missing at the other.

    Flooring the widget itself is the control: it retracts in every reading, so a
    green result cannot come from a floor that never reached this fold."""
    html = SUGGESTION_HOLDING_A_NAMESAKE
    events_model.append_event(page_dir, dict(COMMENT))
    events_model.append_event(page_dir, dict(ACCEPT))
    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
            "version": 2,
            "revision": 2,
            "text": "reworded the poll interval",
            "restated": ["c1"],
        },
    )
    spk = passages_model.spoken(html, registry_storage.require_registry(page_dir))
    assert "sug-a" in spk["c1"].within  # the namesake really is inside the widget
    folds = [passages_model.enclosing_of(spk), passages_model.enclosing_ids(html)]
    events = events_model.read_events(page_dir)
    for within in folds:
        assert (
            event_folds_model.build_threads(events, within)["c1"]["resolved"]["action"]
            == "accept"
        )

    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
            "version": 3,
            "revision": 3,
            "text": "rewrote the suggestion",
            "restated": ["sug-a"],
        },
    )
    events = events_model.read_events(page_dir)
    for within in folds:
        assert event_folds_model.build_threads(events, within)["c1"]["resolved"] is None


def test_the_registry_door_demands_restated_of_a_whole_fold_widget(page_dir):
    """The words gate instructs "add `restated`" when a version rewrites decided
    words; a widget whose closed schema lacks the attribute would be told to
    write markup its own registry entry refuses — every rewrite unpublishable."""
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["properties"]["restated"]
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "restated" in result.output


def test_the_registry_door_refuses_a_drawing_that_says_an_attribute(page_dir):
    """The theme lays a drawing's box out as a row so the drawing keeps the column's
    axis, and a word the layer writes into that element is an item in the row: it stands
    beside the drawing and takes it off the axis by half its own width. That renders as a
    picture placed slightly wrong, which no other reading of the page has any way to
    notice — so the two declarations are refused together, at the door where the widget
    is described rather than on the page where it is drawn."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-diagram"]["properties"]["caption"] = {"type": "string"}
    registry["lf-diagram"]["x-says"] = {"caption": "before"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "x-wide: drawing" in result.output and "caption" in result.output


def test_check_refuses_the_runtimes_own_markers_in_authored_markup(page_dir):
    """The runtime writes data-lf-* attributes and lf- classes as its own record
    and reads them back: authored words inside .lf-chrome leave every reading,
    .lf-quiet clips them to a point nobody can see or select, and an authored
    data-lf-gen makes cells the file-side reading has no fence for.

    Both namespaces are reserved by prefix, so the fourth element here wears a
    class the runtime does not coin today and is refused all the same. A list of
    the names it happens to write is a list that admits the next one it coins:
    .lf-quiet was outside the list this once held, and the chrome stylesheet
    clipped an authored copy of it to 1x1 with both render gates skipping the
    class unconditionally, so nothing anywhere said the page's own words had
    gone. The <p class="note"> is the control: an ordinary class is the author's
    to write, and the count below is exact so a reservation that swallowed it
    would be caught here rather than in a page that stopped rendering."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><div class="lf-chrome"><p id="w">words</p></div>'
            '<p id="q" class="lf-quiet">said out of sight</p>'
            '<p id="n" class="lf-not-coined-yet">a name the runtime has not taken</p>'
            '<p id="k" class="note">an ordinary class the author owns</p>'
            '<p id="g" data-lf-gen="1">generated-looking</p>',
        )
    )
    result = check(page_dir)
    assert result.exit_code != 0
    assert result.output.count("the runtime's own markers") == 4, result.output
    # The marker list in parentheses, not the bare word: `reserved_marker_errors` names
    # the tag, the line and the markers and never the element's id, so an `id="k"`
    # conjunct here would have passed under the very fault it was written to catch. A
    # bare "note" is the opposite failure — a future message carrying "denote" or
    # "annotation" turns this red for a reason that has nothing to do with the page.
    assert "(note)" not in result.output, (
        "an ordinary authored class was refused as the runtime's own record, so "
        f"the reservation reaches past the lf- namespace: {result.output}"
    )


@pytest.mark.parametrize(("subschema", "exit_code"), [(True, 0), (False, 1)])
def test_boolean_attribute_subschemas_validate_without_crashing(
    page_dir, subschema, exit_code
):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["properties"]["choose"] = subschema
    (page_dir / "registry.json").write_text(json.dumps(registry))
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace("<lf-options>", '<lf-options id="opts" choose>')
    )

    result = check(page_dir)
    assert result.exit_code == exit_code, result.output
    assert not isinstance(result.exception, AttributeError)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("x-awaits", []),
        ("x-awaits", {"when": {"choose": True}}),
        ("x-conversation", False),
        ("x-content", "words"),
        ("x-parent", []),
        # Each of these names attributes, so an empty one declares nothing while
        # reading as a declaration.
        ("x-refers", {}),
        ("x-lines", []),
        ("x-paints", []),
        ("x-says", []),
        ("x-state", []),
        ("x-upgrade", "yes"),
        ("x-verbatim", "false"),
        ("x-work", []),
        ("x-work", {"seat": "content", "when": {"choose": True}}),
        ("x-unknown", True),
    ],
)
def test_check_refuses_malformed_registry_extensions(page_dir, key, value):
    """Custom registry keywords are executable contracts, not schema comments."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"][key] = value
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-options> registry extensions are invalid" in result.output


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda registry: registry["lf-chip"].update(
                {"x-work": {"seat": "content"}}
            ),
            "content work seat but is inline",
        ),
        (
            lambda registry: registry["lf-diagram"].update(
                {"x-work": {"seat": "content"}}
            ),
            "content work seat but x-content is data",
        ),
        (
            lambda registry: registry["lf-options"].update(
                {"x-work": {"seat": "conversation"}}
            ),
            "conversation work seat but declares no x-conversation",
        ),
    ],
)
def test_a_work_seat_declaration_is_checked_whole(page_dir, mutate, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    mutate(registry)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


def test_a_version_response_requires_a_standing_request(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-diagram"]["x-conversation"] = {
        "when": {"id": ["flow"]},
        "response": {"kind": "version", "verb": "draw"},
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert (
        "version response but declares no x-awaits standing decision" in result.output
    )

    del registry["lf-diagram"]["x-conversation"]["response"]
    registry["lf-diagram"]["x-awaits"] = {"rollup": True}
    assert registry_validation.validate_registry(registry, "test registry") is registry


def test_a_version_response_names_an_authored_answer_record(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-conversation"] = {
        "when": {"choose": [True]},
        "response": {"kind": "version", "verb": "choose"},
    }
    response = registry["lf-options"]["x-conversation"]["response"]
    response["verb"] = "answer"

    with pytest.raises(
        registry_contract.RegistryError,
        match="x-awaits does not declare as an answer verb",
    ):
        registry_validation.validate_registry(registry, "test registry")

    registry["lf-options"]["x-awaits"]["answers"].append("answer")
    with pytest.raises(
        registry_contract.RegistryError,
        match="has no attribute or value record for a version to change",
    ):
        registry_validation.validate_registry(registry, "test registry")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        # A report moves declared state only, never body words — the schema is
        # where the paint-only constraint lives, so a body record never parses.
        (_report_body_record, "registry extensions are invalid"),
        # The gate compares record forms, so a recordless report declares
        # nothing a version could be checked against.
        (_report_no_record, "registry extensions are invalid"),
        (_report_undeclared_attr, "records undeclared attribute `phase`"),
        # An x-says value is the page's words: replay writing one would change
        # what the page says while the file's reading held still.
        (_report_says_attr, "records x-says attribute `owner`"),
        # One vocabulary: the detail field speaks the attribute's own schema,
        # or the log's contract and the markup's drift apart.
        (_report_detail_drift, "must carry attribute `status`'s own schema"),
        # `overruled` is how a version keeps its state over a report; without it
        # every contradiction is unpublishable.
        (_report_without_overruled, "not the boolean `overruled`"),
        # Reports replay through applyAction, so the widget must upgrade.
        (_report_without_upgrade, "declares x-report"),
        # A value record has no action detail for an absent attribute. Requiring the
        # attribute makes every authored state projectable through applyAction.
        (_state_with_optional_value_record, "records optional attribute `owner`"),
        (_body_record_with_prose, "x-content must be data"),
        (_body_record_with_nested_widget, "admits nested widgets"),
    ],
)
def test_an_x_report_declaration_is_checked_whole(page_dir, mutate, message):
    result = _mutated_registry_check(page_dir, mutate)
    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize("tag", ["lf-options[", "LF-options", "lf_options"])
def test_check_refuses_a_widget_name_that_cannot_form_a_selector(page_dir, tag):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag] = registry.pop("lf-options")
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"invalid registry entry names: ['{tag}']" in result.output


def test_check_refuses_an_invalid_action_detail_schema(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["choose"]["detail"]["type"] = "not-a-type"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert (
        "<lf-options> x-state verb `choose` has an invalid detail schema"
        in result.output
    )


def test_generated_child_declaration_is_valid_as_shipped(page_dir):
    result = check(page_dir)
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing-member", "registry extensions are invalid"),
        ("unknown-child", "creates unknown child <lf-missing>"),
        ("required-field", "creates detail field `additions` must be optional"),
        ("wrong-map", "canonical non-empty element-id to non-empty string map"),
        ("wrong-parent", "x-parent does not admit the sender"),
        ("non-prose", "must declare x-content prose"),
        ("extra-required", "must require id and no other authored attributes"),
        ("wrong-id", "required id must use the canonical element-id schema"),
        ("report-creates", "registry extensions are invalid"),
    ],
)
def test_generated_child_declaration_closes_its_boundary(page_dir, mutation, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    choose = registry["lf-options"]["x-state"]["choose"]
    option = registry["lf-option"]
    if mutation == "missing-member":
        del choose["creates"]["child"]
    elif mutation == "unknown-child":
        choose["creates"]["child"] = "lf-missing"
    elif mutation == "required-field":
        choose["detail"]["required"].append("additions")
    elif mutation == "wrong-map":
        choose["detail"]["properties"]["additions"]["minProperties"] = 0
    elif mutation == "wrong-parent":
        option["x-parent"] = ["lf-board"]
    elif mutation == "non-prose":
        option["x-content"] = "items"
    elif mutation == "extra-required":
        option["required"].append("for")
    elif mutation == "wrong-id":
        option["properties"]["id"]["pattern"] = "^option-.+$"
    elif mutation == "report-creates":
        registry["lf-agent"]["x-report"]["state"]["creates"] = {
            "field": "doing",
            "child": "lf-option",
        }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


def test_action_detail_schemas_match_the_post_object_contract(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-state"]["accept"]["detail"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "detail schema must declare an object" in result.output


def test_request_detail_schemas_match_the_post_object_contract(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-operations"]["x-request"]["verbs"]["restart"]["detail"] = {
        "type": "string"
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "<lf-operations> x-request verb `restart` detail schema" in result.output
    assert "must declare an object" in result.output


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            "optional-field",
            "field `target`, but that field is not declared and required",
        ),
        (
            "non-string-bound-field",
            "binds detail field `target`, which must be a string",
        ),
        ("unknown-attribute", "to `missing`, which is not a declared string attribute"),
        (
            "optional-bound-attribute",
            "to `target`, which is not a required authored attribute",
        ),
        (
            "mutable-bound-attribute",
            "to `target`, which is written by x-state or x-report",
        ),
        ("optional-id", "x-request instances are addressable"),
        ("no-upgrade", "declares x-request"),
        ("unknown-offer", "x-request offers unknown widget <lf-unknown>"),
        ("wrong-parent", "does not name it in x-parent"),
        ("freeform-offer", "must be a non-empty string enum"),
        (
            "optional-offer-attribute",
            "offer <lf-operation> attribute `verb` must be required",
        ),
        ("unknown-offered-verb", "names undeclared verbs ['explode']"),
        ("unoffered-verb", "verbs ['restart'] cannot be offered"),
        ("self-framing-decision", "declares both x-decision and x-request.decision"),
        ("dual-decision-source", "declares both x-request.decision and x-awaits"),
    ],
)
def test_an_x_request_declaration_closes_its_widget_boundary(
    page_dir, mutation, message
):
    registry = json.loads((page_dir / "registry.json").read_text())
    operations = registry["lf-operations"]
    restart = operations["x-request"]["verbs"]["restart"]
    if mutation == "optional-field":
        restart["detail"]["required"] = []
    elif mutation == "non-string-bound-field":
        restart["detail"]["properties"]["target"] = {"type": "integer"}
    elif mutation == "unknown-attribute":
        restart["bind"]["target"] = "missing"
    elif mutation == "optional-bound-attribute":
        operations["required"].remove("target")
    elif mutation == "mutable-bound-attribute":
        operations["properties"]["overruled"] = {"type": "boolean"}
        operations["x-report"] = {
            "retarget": {
                "detail": {
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": ["target"],
                    "additionalProperties": False,
                },
                "facet": "target",
                "unit": "widget",
                "record": {"kind": "value", "attr": "target", "value": "target"},
            }
        }
    elif mutation == "optional-id":
        operations["required"].remove("id")
    elif mutation == "no-upgrade":
        operations["x-upgrade"] = False
    elif mutation == "unknown-offer":
        operations["x-request"]["offers"] = {"lf-unknown": "verb"}
    elif mutation == "wrong-parent":
        registry["lf-operation"]["x-parent"] = ["lf-command"]
    elif mutation == "freeform-offer":
        registry["lf-operation"]["properties"]["verb"] = {"type": "string"}
    elif mutation == "optional-offer-attribute":
        registry["lf-operation"]["required"].remove("verb")
    elif mutation == "unknown-offered-verb":
        registry["lf-operation"]["properties"]["verb"]["enum"].append("explode")
    elif mutation == "unoffered-verb":
        registry["lf-operation"]["properties"]["verb"]["enum"].remove("restart")
    elif mutation == "self-framing-decision":
        operations["x-decision"] = True
        operations["x-content"] = "prose"
    elif mutation == "dual-decision-source":
        operations["x-awaits"] = {"rollup": True}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize("subschema", [True, False])
def test_state_reader_fields_reject_boolean_subschemas(page_dir, subschema):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["choose"]["detail"]["properties"]["options"] = (
        subschema
    )
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "record value `options` must be an array of strings" in result.output


def test_fold_units_are_required_strings(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    card = registry["lf-board"]["x-state"]["move"]["detail"]["properties"]["card"]
    card["type"] = "integer"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "fold unit `card` must be a string" in result.output


@pytest.mark.parametrize(
    ("tag", "verb", "field"),
    [
        ("lf-options", "choose", "options"),
        ("lf-draft", "edit", "text"),
    ],
)
def test_per_part_state_records_positions(page_dir, tag, verb, field):
    registry = json.loads((page_dir / "registry.json").read_text())
    spec = registry[tag]["x-state"][verb]
    spec["unit"] = field
    spec["detail"]["properties"][field]["type"] = "string"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> x-state verb `{verb}` records per-part state" in result.output
    assert "only position records support that" in result.output


@pytest.mark.parametrize(
    ("tag", "verb", "field", "wanted"),
    [
        # An attribute record names the set of elements wearing it, so its detail field
        # is a list whatever the widget allows at once; the other two name one thing.
        ("lf-options", "choose", "options", "must be an array of strings"),
        ("lf-board", "move", "to", "must be a string"),
        ("lf-draft", "edit", "text", "must be a string"),
    ],
)
def test_record_values_have_the_type_the_reader_uses(
    page_dir, tag, verb, field, wanted
):
    registry = json.loads((page_dir / "registry.json").read_text())
    spec = registry[tag]["x-state"][verb]
    spec["detail"]["properties"][field] = {"type": "integer"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> x-state verb `{verb}` record value `{field}`" in result.output
    assert wanted in result.output


def test_recorded_actions_require_only_fields_authored_markup_can_restore(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    detail = registry["lf-options"]["x-state"]["choose"]["detail"]
    detail["properties"]["animate"] = {"type": "boolean"}
    detail["required"].append("animate")
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "requires detail fields ['animate']" in result.output
    assert "authored markup cannot restore" in result.output


def test_value_records_use_the_string_type_html_attributes_carry(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    numeric = {"type": "integer", "minimum": 0}
    registry["lf-agent"]["properties"]["state"] = numeric
    registry["lf-agent"]["x-report"]["state"]["detail"]["properties"]["state"] = numeric
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "record value `state` must be a string or string enum" in result.output


@pytest.mark.parametrize(
    ("change", "wanted"),
    [
        (
            lambda spec: spec.update({"update": "missing"}),
            "update field `missing` is not declared by its detail schema",
        ),
        (
            lambda spec: spec["detail"]["required"].remove("doing"),
            "update field `doing` must be required",
        ),
        (
            lambda spec: spec["detail"]["properties"].update(
                {"doing": {"type": ["string", "null"]}}
            ),
            "update field `doing` must be a string",
        ),
        (
            lambda spec: spec["detail"]["properties"]["doing"].pop("minLength"),
            "update field `doing` must set minLength to at least 1",
        ),
    ],
)
def test_report_update_words_are_declared_once(page_dir, change, wanted):
    """The canonical feed may render one report detail as prose, so the registry
    names that field explicitly and guarantees every report carries real words. A
    consumer never guesses from a field name or string-shaped value."""
    registry = json.loads((page_dir / "registry.json").read_text())
    spec = registry["lf-agent"]["x-report"]["state"]
    assert spec["update"] == "doing"
    change(spec)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert wanted in result.output


@pytest.mark.parametrize(
    ("tag", "channel", "verb", "field"),
    [
        ("lf-suggestion", "x-state", "accept", "facet"),
        ("lf-suggestion", "x-state", "accept", "unit"),
        ("lf-task", "x-report", "status", "facet"),
        ("lf-task", "x-report", "status", "unit"),
    ],
)
def test_every_fold_verb_declares_its_coordinate(page_dir, tag, channel, verb, field):
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry[tag][channel][verb][field]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert f"<{tag}> registry extensions are invalid" in result.output
    assert field in result.output


def test_same_facet_verbs_must_share_one_unit_and_record_form(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    answer = registry["lf-options"]["x-state"]["answer"]
    answer["facet"] = "selection"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "share facet `selection`" in result.output
    assert "identical record forms" in result.output

    answer["record"] = registry["lf-options"]["x-state"]["choose"]["record"]
    answer["unit"] = "option"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "share facet `selection`" in result.output
    assert "different fold units" in result.output


@pytest.mark.parametrize(
    ("tag", "channel", "verb", "slot"),
    [
        ("lf-draft", "x-state", "edit", "body"),
        ("lf-board", "x-state", "move", "position"),
        ("lf-task", "x-report", "status", "value `status`"),
        ("lf-options", "x-state", "choose", "attribute `chosen`"),
    ],
)
def test_distinct_facets_cannot_claim_one_physical_record_slot(
    page_dir, tag, channel, verb, slot
):
    registry = json.loads((page_dir / "registry.json").read_text())
    declared = registry[tag][channel][verb]
    parallel = json.loads(json.dumps(declared))
    parallel["facet"] = "parallel"
    registry[tag][channel]["parallel"] = parallel
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert (
        f"<{tag}> {channel} verb `parallel` (facet `parallel`)"
        f" and {channel} verb `{verb}` (facet `{declared['facet']}`) claim the same "
        f"physical record slot (unit `{parallel['unit']}`, {slot}); distinct facets "
        "must record independently" in result.output
    )


def test_physical_record_slots_remain_local_to_the_coordinate(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())

    # Both channels may state the same fact through the same slot.
    task = registry["lf-task"]
    task["properties"]["restated"] = {"type": "boolean"}
    task["x-state"] = {"status": task["x-report"]["status"]}

    # A different host attribute is a different value slot on the same unit.
    owner = json.loads(json.dumps(task["x-report"]["status"]))
    owner["facet"] = "owner"
    owner["detail"]["properties"] = {"owner": {"type": "string"}}
    owner["detail"]["required"] = ["owner"]
    owner["record"] = {"kind": "value", "attr": "owner", "value": "owner"}
    task["properties"]["owner"] = {"type": "string"}
    task.setdefault("required", []).append("owner")
    task["x-report"]["owner"] = owner
    registry["lf-tasks"]["x-example"] = re.sub(
        r"<lf-task(?![^>]*\bowner=)",
        '<lf-task owner="test"',
        registry["lf-tasks"]["x-example"],
    )

    # Placement is one slot only for a given declared unit.
    board = registry["lf-board"]
    arrange = json.loads(json.dumps(board["x-state"]["move"]))
    arrange["facet"] = "arrangement"
    arrange["unit"] = "to"
    arrange["detail"]["properties"].pop("card")
    arrange["detail"]["required"].remove("card")
    board["x-state"]["arrange"] = arrange
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_every_action_on_a_thread_answer_widget_shares_its_answer_facet(page_dir):
    """Thread history outlives the markup that declared the action, so its one
    durable widget key is exact only when every action on a resolves-bearing tag
    is another outcome of the same answer fact."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-state"]["reject"]["facet"] = "other"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "resolves-bearing widget" in result.output
    assert "answer facet `settlement`" in result.output


def test_registry_cross_entry_checks_wait_for_every_entry_to_validate(page_dir):
    """A child appearing first must not inspect a malformed parent half-validated."""
    registry = json.loads((page_dir / "registry.json").read_text())
    child = registry.pop("lf-old")
    registry["lf-suggestion"]["x-state"] = 42
    registry = {"lf-old": child, **registry}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-suggestion> registry extensions are invalid" in result.output


@pytest.mark.parametrize(
    ("tag", "key", "fallback"),
    [
        ("lf-options", "x-state", None),
        ("lf-note", "x-conversation", {"when": {"id": ["note"]}}),
    ],
)
def test_runtime_features_require_an_upgraded_widget(page_dir, tag, key, fallback):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = registry[tag].get(key, fallback)
    registry[tag]["x-upgrade"] = False
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> declares" in result.output
    assert key in result.output
    assert "but has no upgraded handler" in result.output


def test_retirement_requires_a_parent(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-old"]["x-parent"]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-old> registry extensions are invalid" in result.output


def test_check_refuses_a_retirement_verb_its_parent_does_not_declare(page_dir):
    """A retirement outcome is a cross-entry reference, not a free-form label.

    If it names no verb on the parent widget, the browser's selector can never
    match and the file reading can disagree with what that widget knows how to
    settle. Refuse that vocabulary at its one ingress instead of leaving every
    consumer to rediscover the broken reference.
    """
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-old"]["x-retired-when"] = "approve"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-old> x-retired-when `approve`" in result.output
    assert "<lf-suggestion> does not declare that x-state verb" in result.output


def test_retirement_verbs_fold_by_the_parent_widget(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    accept = registry["lf-suggestion"]["x-state"]["accept"]
    # A field of its own to fold by: `resolves` is the one detail key accept already
    # declares, and a verb answering a thread is held to the widget for its own
    # reason — so borrowing it here would trip that door instead of this one.
    accept["detail"]["properties"] = {"part": {"type": "string"}}
    accept["unit"] = "part"
    accept["detail"]["required"] = ["part"]
    # Keep the settlement coordinate coherent so this reaches the separate
    # holder/slot relation being exercised here.
    reject = registry["lf-suggestion"]["x-state"]["reject"]
    reject["detail"]["properties"] = {"part": {"type": "string"}}
    reject["unit"] = "part"
    reject["detail"]["required"] = ["part"]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-old> x-retired-when `accept` must fold by widget" in result.output


def test_one_holders_retirement_outcomes_share_one_facet(page_dir):
    """Retirement is one decision even when its holder answers no thread."""
    registry = json.loads((page_dir / "registry.json").read_text())
    accept = registry["lf-suggestion"]["x-state"]["accept"]
    accept["detail"] = {"type": "object", "additionalProperties": False}
    registry["lf-suggestion"]["x-state"]["reject"]["facet"] = "alternative"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert (
        "<lf-suggestion> x-retired-when outcomes span facets (`accept` → "
        "`settlement`, `reject` → `alternative`); every retirement outcome for "
        "one holder must share one facet" in result.output
    )


def test_a_layers_own_outcome_licenses_the_ids_it_retires(trial_page):
    """The version that honors a decision drops what the outcome retired, and
    the licensing that lets it is written in terms of the registry's holder/slot
    relation — so a family the layer never heard of is licensed the day it is
    declared. It used to be written in terms of the suggestion's own slots, and
    a family like this one got every part of the loop except this: the door
    refused the declaration outright rather than let the honoring version fail
    here with "ids dropped"."""
    (trial_page / "versions" / "v2.html").write_text(
        trial_version(ADOPTED, TRIAL_LOG, PILOT_PURGE)
    )

    refused = check(trial_page, version=2)
    assert refused.exit_code == 1
    assert "cache-daily" in refused.output and "cache-now" in refused.output
    # The wrapper with them: this version keeps the proposal as settled prose, so
    # the withdrawal that would have licensed the wrapper isn't one.
    assert "trial-cache" in refused.output

    decide(trial_page, "adopt", widget="trial-cache")

    honored = stamp(trial_page, 2, "adopted")
    assert honored.exit_code == 0, honored.output
    assert live_versions(trial_page) == [1, 2]


def test_a_layers_own_widget_withdraws_as_its_entry_declares(trial_page):
    """Nothing was decided, so the author may take the question back — and
    `x-withdrawn-as` is what says which half of it was theirs to take. The other
    half is the page's own words, which only the reader's own `adopt` consents
    to losing, so a version dropping that is refused while the same version's
    withdrawal stands."""
    (trial_page / "versions" / "v2.html").write_text(
        trial_version(TRIAL_CACHE, SHELVED, PILOT_PURGE)
    )
    withdrawn = check(trial_page, version=2)
    assert withdrawn.exit_code == 0, withdrawn.output

    # v2 published nothing, so v3 stands against v1 like v2 did.
    (trial_page / "versions" / "v3.html").write_text(
        trial_version(TRIAL_CACHE, PILOT_PURGE)
    )
    result = check(trial_page, version=3)
    assert result.exit_code == 1
    issues = "\n".join(
        line for line in result.output.splitlines() if line.startswith("  -")
    )
    assert "log-daily" in issues
    assert "log-hourly" not in issues
    assert "ids dropped from revision r1: ['log-hourly', 'trial-log']" in result.output


def test_a_widget_declaring_no_withdrawal_holds_its_ids_until_it_is_answered(
    trial_page,
):
    """A withdrawal is declared, never assumed: a family that doesn't say what
    taking its question back would mean keeps every id until the reader answers
    it. <lf-proposed> is the same slot under the same verb in both families, so
    what differs is the pair — which is the shape the licensing reads, and the
    reason the declaration sits on the widget that holds the slot rather than on
    the slot."""
    (trial_page / "versions" / "v2.html").write_text(
        trial_version(TRIAL_CACHE, TRIAL_LOG)
    )

    refused = check(trial_page, version=2)
    assert refused.exit_code == 1
    assert "pilot-purge" in refused.output and "purge-weekly" in refused.output

    decide(trial_page, "shelve", widget="pilot-purge")

    answered = check(trial_page, version=2)
    assert answered.exit_code == 0, answered.output


def test_the_registry_door_refuses_a_withdrawal_that_retires_nothing(trial_page):
    """A withdrawal outcome no slot of the widget retires under promises the
    author a taking-back that would leave every id in place — and the version
    that tried it would fail as "ids dropped", a typo's distance from the
    declaration and three versions after it."""
    registry = json.loads((trial_page / "registry.json").read_text())
    registry["lf-trial"]["x-withdrawn-as"] = "shelved"
    (trial_page / "registry.json").write_text(json.dumps(registry))

    result = check(trial_page)
    assert result.exit_code != 0
    assert "<lf-trial> x-withdrawn-as `shelved` retires none of its slots" in (
        result.output
    )


@pytest.mark.parametrize(
    ("tag", "key", "declaration", "message"),
    [
        (
            "lf-options",
            "x-awaits",
            {"when": {"pick": [True]}},
            "names undeclared attribute `pick`",
        ),
        (
            "lf-options",
            "x-conversation",
            {"when": {"pick": [True]}},
            "names undeclared attribute `pick`",
        ),
        (
            "lf-options",
            "x-awaits",
            {"when": {"choose": ["yes"]}},
            "a flag is there or it isn't",
        ),
        (
            "lf-task",
            "x-awaits",
            {"when": {"status": [True]}},
            "that attribute is not a flag",
        ),
        (
            "lf-task",
            "x-awaits",
            {"when": {"status": ["reviewing"]}},
            "its own enum does not admit",
        ),
        (
            "lf-options",
            "x-conversation",
            {"when": {"id": ["NOT-VALID"]}},
            "its own schema does not admit",
        ),
        (
            "lf-suggestion",
            "x-awaits",
            {"answers": ["accept"], "all": "approve"},
            "does not declare as an x-state verb",
        ),
        (
            "lf-options",
            "x-awaits",
            {
                "answers": ["choose"],
                "until": {"verb": "submit", "when": {"multiple": [True]}},
            },
            "does not declare as an x-state verb",
        ),
        (
            "lf-options",
            "x-awaits",
            {"until": {"verb": "answer", "when": {"batch": [True]}}},
            "names undeclared attribute `batch`",
        ),
        (
            "lf-options",
            "x-awaits",
            {"answers": ["submit"]},
            "names undeclared answer verbs",
        ),
        (
            "lf-chip",
            "x-awaits",
            {"rollup": True},
            "does not require an id",
        ),
    ],
)
def test_check_refuses_a_predicate_no_page_could_carry(
    page_dir, tag, key, declaration, message
):
    """A predicate naming a value the widget cannot hold applies to nothing silently.

    The widget is simply absent from every consumer, exactly as if the feature had
    never been wired up.
    Same for a blanket answer naming a verb the widget does not speak, whose button
    would call a method nothing implements — and for an until verb, which would
    hold a thread decision open for a press no widget renders."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = declaration
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> {key}" in result.output and message in result.output


def test_rollup_false_is_omitted_instead_of_becoming_a_second_form(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-awaits"] = {"rollup": False}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "<lf-options> registry extensions are invalid" in result.output
    assert "True was expected" in result.output


def test_an_aggregate_only_rollup_declaration_is_valid(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-awaits"] = {"rollup": True}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    assert check(page_dir).exit_code == 0


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ({}, "local decision declares no answer verbs"),
        (
            {"rollup": True, "when": {"status": ["review"]}},
            "rollup also declares local decision fields ['when']",
        ),
    ],
)
def test_an_awaits_declaration_has_one_decision_role(page_dir, declaration, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-awaits"] = declaration
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize("verb", ["choose", "answer"])
def test_a_completion_verb_cannot_require_its_request_closed(page_dir, verb):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"][verb]["requires"] = {
        "target": "self",
        "awaiting": False,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "completion verbs" in result.output
    assert "require their own decision to be closed" in result.output


def test_a_completion_verb_can_follow_a_local_parent_but_not_its_rollup(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    state = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "answer",
        "unit": "widget",
    }
    registry["lf-request-parent"] = {
        "description": "A parent request used to validate sequencing.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "items",
        "x-upgrade": True,
        "x-awaits": {"answers": ["answer"]},
        "x-state": {"answer": state},
    }
    registry["lf-request-child"] = {
        "description": "A child request sequenced after its parent.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-parent": ["lf-request-parent"],
        "x-content": "none",
        "x-upgrade": True,
        "x-awaits": {"answers": ["answer"]},
        "x-state": {
            "answer": {
                **state,
                "requires": {"target": "parent", "awaiting": False},
            }
        },
    }

    assert registry_validation.validate_registry(registry, "test registry") is registry

    registry["lf-request-parent"]["x-awaits"] = {"rollup": True}
    with pytest.raises(registry_contract.RegistryError) as raised:
        registry_validation.validate_registry(registry, "test registry")
    assert "aggregate parents ['lf-request-parent']" in str(raised.value)
    assert "cannot complete it" in str(raised.value)


def test_a_parent_prerequisite_requires_addressable_targets(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["required"].remove("id")
    registry["lf-options"]["x-parent"] = ["lf-suggestion"]
    registry["lf-options"]["x-state"]["choose"]["requires"] = {
        "target": "parent",
        "awaiting": True,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "['lf-suggestion'] do not require an id" in result.output


@pytest.mark.parametrize(
    ("tag", "verb", "requires", "message"),
    [
        (
            "lf-board",
            "move",
            {"target": "self", "awaiting": True},
            "do not declare x-awaits",
        ),
        (
            "lf-options",
            "choose",
            {"target": "parent", "awaiting": True},
            "declares no x-parent",
        ),
    ],
)
def test_check_refuses_action_prerequisites_without_a_declared_request_target(
    page_dir, tag, verb, requires, message
):
    """Both runtime interpreters may assume a prerequisite passed this one door."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag]["x-state"][verb]["requires"] = requires
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert f"<{tag}> x-state verb `{verb}`" in result.output
    assert message in result.output


def test_only_reader_actions_admit_current_eligibility(page_dir):
    """Reports state agent news; they are not gestures the reader can disable."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-report"]["status"]["requires"] = {
        "target": "self",
        "awaiting": False,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "<lf-task> registry extensions are invalid" in result.output
    assert "requires" in result.output


def test_a_self_position_record_stays_within_the_declared_parent_relation(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-parent"] = ["lf-task"]
    registry["lf-options"]["x-state"]["move"] = {
        "detail": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "index": {"type": "integer", "minimum": 0},
            },
            "required": ["to", "index"],
            "additionalProperties": False,
        },
        "facet": "placement",
        "unit": "widget",
        "record": {
            "kind": "position",
            "within": "lf-column",
            "value": "to",
            "order": "index",
        },
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "records its own position within <lf-column>" in result.output
    assert "x-parent does not admit" in result.output


@pytest.mark.parametrize(
    ("tag", "key", "value", "missing"),
    [
        ("lf-event", "x-says", {"at": "before", "colour": "after"}, "colour"),
        ("lf-option", "x-refers", {"for": {}, "about": {}}, "about"),
        ("lf-task", "x-paints", ["status", "urgency"], "urgency"),
        ("lf-code", "x-lines", ["hi", "upto"], "upto"),
        ("lf-code", "x-language", "dialect", "dialect"),
        ("lf-chip", "x-tone", "shade", "shade"),
    ],
)
def test_check_refuses_a_key_naming_an_attribute_the_widget_has_not_got(
    page_dir, tag, key, value, missing
):
    """Six keys point at attributes rather than declaring them — the words a widget
    shows, the ones that name another element, the ones it paints and never words, the
    ones holding line references, and the two carrying a word its layer has to know —
    and each is read by a pass that finds the attribute absent and does nothing. That
    is the never-closed vocabulary's own failure mode: no error anywhere, the widget
    simply missing from the pass, and a page that looks authored correctly because it
    was. The door is the only place the mistake is visible, so it refuses here.

    Every one of them parametrized rather than three, because it is one rule
    (ATTRIBUTE_KEYS) and the case that would go wrong is a key left off the tuple —
    which no test of the three that were written by hand could ever see. The shapes
    differ and the rule does not: a list, a mapping keyed by the names, one name."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = value
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> {key} names undeclared attributes ['{missing}']" in result.output


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        (
            {"via": "$missing.widgets", "where": {"role": "goal"}},
            "names unknown registry map '$missing.widgets'",
        ),
        (
            {"via": "$command.widgets", "where": {"role": "imaginary"}},
            "but no declared widget matches",
        ),
    ],
)
def test_a_typed_reference_names_a_reachable_package_role(page_dir, reference, message):
    """A bad package relation fails at the registry door, not on every instance."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-option"]["x-refers"]["for"] = reference

    with pytest.raises(registry_contract.RegistryError, match=re.escape(message)):
        registry_validation.validate_registry(registry, "test registry")


@pytest.mark.parametrize("section", ["$events", "$languages", "$tones"])
def test_init_inherits_contract_members_a_layer_does_not_state(
    page_dir, tmp_path, section
):
    """$ members merge, so an empty declaration is the same statement as none.

    There is no incomplete $ replacement to refuse: what a layer doesn't state
    is inherited, and the merged registry carries the complete shipped contract."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({section: {}}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output
    merged = json.loads((page_dir / "registry.json").read_text())[section]
    shipped = json.loads((schema_model.ASSETS / "registry.json").read_text())[section]
    assert merged == shipped


@pytest.mark.parametrize("names", ["ok", ["ok", "ok"], ["ok", 1]])
def test_init_requires_tones_to_be_a_list_membership_can_be_tested_against(
    page_dir, tmp_path, names
):
    """Presence is not enough, because the tone check asks this list for membership.
    A string answers by substring, so a layer declaring `"names": "ok"` would pass
    `tone="o"` and paint nothing — the invisible failure the tone check exists to
    catch, arriving through the very entry that declares the vocabulary."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"$tones": {"names": names}}))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "$tones.names must be a unique list of strings" in result.output


def test_init_holds_the_key_docs_to_the_keys_the_lint_admits(page_dir, tmp_path):
    """$keys documents each x- key an entry may declare, and exactly those: a member
    for a key the lint doesn't admit is documentation of nothing, and one missing is a
    key the registry then leaves unsaid. A project layer overrides a member (its own
    reading of a key) and adds none — the set is closed where the keys are checked."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"x-wide": "wider, in this project", "x-nope": "?"}})
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "unadmitted ['x-nope']" in result.output

    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"x-wide": "wider, in this project"}})
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output
    keys = json.loads((page_dir / "registry.json").read_text())["$keys"]
    assert keys["x-wide"] == "wider, in this project"
    assert keys["x-says"]  # the rest of the shipped members stand


@pytest.mark.parametrize("field", ["restated", "session"])
def test_init_requires_the_event_vocabulary_the_layer_writes(page_dir, tmp_path, field):
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["$events"]["kinds"]["note"]["record"]["properties"][field]
    (overlay / "registry.json").write_text(json.dumps(registry))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "current layer writes" in result.output
    assert "note" in result.output
    assert field in result.output


def test_the_registry_door_validates_event_schemas(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$events"]["kinds"]["comment"]["record"]["properties"]["text"] = {
        "type": "not-a-type"
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "$events kind `comment` record is not a valid JSON Schema" in result.output


def test_registry_refuses_hidden_event_record_constraints(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$events"]["kinds"]["comment"]["record"]["not"] = {
        "required": ["author"],
        "properties": {"author": {"const": "claude"}},
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "record must use only type, properties, required" in result.output


def test_an_empty_host_name_uses_the_host_default(page_dir, sessionless, monkeypatch):
    published(page_dir)
    monkeypatch.setenv("LEAF_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "")

    result = comment(page_dir, "--text", "Which worker said this?")

    assert result.exit_code == 0, result.output
    event = events_model.read_events(page_dir)[-1]
    assert (event["agent"], event["session"]) == ("Codex", "worker-1")


def test_event_required_order_is_not_a_contract_change(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    required = registry["$events"]["kinds"]["comment"]["record"]["required"]
    required.reverse()
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_an_event_kind_contract_replaces_whole_across_layers():
    """A kind is one schema contract. Merging its record and browser members from
    different layers would produce a contract neither layer authored."""
    old = {"record": {"const": "old"}, "browser": {"const": "old"}}
    replacement = {"record": {"const": "new"}}
    merged = {"$events": {"kinds": {"signal": old}}}

    registry_layer.merge_layer_entries(
        merged, {"$events": {"kinds": {"signal": replacement}}}
    )

    assert merged["$events"]["kinds"]["signal"] == replacement


def test_a_record_contract_does_not_open_a_browser_event_kind(server, page_dir):
    """The log may carry a kind written through another door. Browser authorship
    is a separate assertion and must be opted into on the kind itself."""
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    contract = json.loads(json.dumps(registry["$events"]["kinds"]["error"]))
    del contract["browser"]
    contract["record"]["properties"]["kind"] = {"const": "signal"}
    registry["$events"]["kinds"]["signal"] = contract
    (page_dir / "registry.json").write_text(json.dumps(registry))

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "signal", "text": "hello"}).encode(),
    )

    assert status == 400, body
    assert "kind must be one of" in json.loads(body)["error"]


def test_an_overlay_cannot_silently_drop_an_event_kind(page_dir, tmp_path):
    """Layers are additive: $ members merge by key, so an overlay omitting a
    kind leaves the shipped one standing rather than deleting it. A whole
    vocabulary genuinely missing one is still refused at the registry door."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["$events"]["kinds"]["note"]
    (overlay / "registry.json").write_text(json.dumps(registry))
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output
    merged = json.loads((page_dir / "registry.json").read_text())
    assert "note" in merged["$events"]["kinds"]

    with pytest.raises(registry_contract.RegistryError, match="current layer writes"):
        registry_validation.validate_registry(registry, "incoming")


def test_a_widget_nobody_has_touched_is_not_the_gate_s_business(page_dir):
    """The gate is about decisions, so it holds nothing against a version that
    rewrites a widget the user never acted on."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>First words.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    (page_dir / "versions" / "v2.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>Quite different words.</pre></lf-draft>',
        )
    )
    assert check(page_dir, version=2).exit_code == 0


def test_check_requires_the_vendored_layer(tmp_path):
    d = tmp_path / "bare"
    (d / "versions").mkdir(parents=True)
    (d / "versions" / "v1.html").write_text(PAGE)
    result = check(d)
    assert result.exit_code == 1
    assert "run `leaf page init` to vendor the layer" in result.output


def test_check_takes_column_width_from_vendored_theme(page_dir):
    # theme.css sets a 720px main column; a wider fixed-width element must fail.
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", '<h2>Plan</h2><svg width="900" height="10"></svg>'
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "exceeds column (720px)" in result.output


def test_check_reads_a_column_the_theme_states_as_a_token():
    """A width naming a root token is a width the stylesheet stated, so the column reads
    it. The theme keeps its own constants in `:root` and more than one rule now wants the
    measure; a reading that stopped at the name would fall back to a default column and
    go on printing a number, which is a check that stops measuring exactly when the file
    it measures gets tidier.

    Only the root, and only what is stated outright. A token declared inside a query is
    that condition's, the same reason the column will not read a media query's width, and
    a token nothing declares leaves the `var()`'s own fallback — the browser's answer."""
    column = "--lf-column: 1;"
    stated = ":root { --col: 640px }\nmain { " + column + " max-width: var(--col) }"
    assert styles_model._column_width("", stated) == 640

    conditional = (
        "@media screen { :root { --col: 640px } }\nmain { "
        + column
        + " max-width: var(--col) }"
    )
    assert styles_model._column_width("", conditional) == styles_model.COLUMN_FALLBACK

    fallback = "main { " + column + " max-width: var(--col, 512px) }"
    assert styles_model._column_width("", fallback) == 512

    # The shipped theme is the case that motivated this: it must still read as itself.
    assert (
        styles_model._column_width("", (schema_model.ASSETS / "theme.css").read_text())
        == 720
    )


def test_the_column_is_the_rule_that_claims_it_and_not_a_rule_that_looks_like_one():
    """Which rule is the readable column is the stylesheet's to say, and it says it in
    the block that sets the width — `--lf-column: 1` beside the max-width, so the cascade
    wins the claim and the width together.

    Seven container names stood in for that answer before, and a name list is wrong in
    both directions. Too wide: the column is the baseline every other width on the page
    is measured against, so an unrelated rule spelled `.content` moved it, and moving it
    up takes the overflow check quiet — which reads not as a broken check but as a page
    with nothing wrong in it. Too narrow: a page whose column is `.prose` was measured
    against the fallback and failed for widths that fit inside it.

    The last case is the one that keeps this honest. A rule that claims the column with
    no width to give states nothing, so the reading must fall through to the next
    stylesheet rather than settle on a claim it cannot measure."""
    assert (
        styles_model._column_width("", "main { max-width: 1400px }")
        == styles_model.COLUMN_FALLBACK
    ), "an unclaimed rule still set the column, so the name is still doing the deciding"

    assert (
        styles_model._column_width("", ".content { max-width: 1400px }")
        == styles_model.COLUMN_FALLBACK
    ), "a rule that merely looks like a container still doubled the page's baseline"

    assert (
        styles_model._column_width("", ".prose { --lf-column: 1; max-width: 560px }")
        == 560
    ), "a column named anything at all is still not readable, so the claim is ignored"

    assert (
        styles_model._column_width("main { --lf-column: 1; max-width: 500px }", "")
        == 500
    ), "a page's own <style> no longer states the column it is measured against"

    theme = (schema_model.ASSETS / "theme.css").read_text()
    assert styles_model._column_width("main { --lf-column: 1 }", theme) == 720, (
        "a claim with no width of its own stopped the reading where it stood, so a "
        "page could take the measure off itself by claiming and then saying nothing"
    )


def test_check_measures_a_width_named_from_the_layer_s_own_tokens(page_dir):
    """A page pinning `var(--wide)` is stating the vocabulary's own breakout width, which
    is wider than the column by design. The page's `<style>` declares no such token, so
    the reading resolves it against the layer the page vendored — the order the cascade
    reads the two roots in. Without the layer behind it, a page could take any width the
    theme names and never be measured for it."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p id="w" style="width: var(--wide)">Wide by name.</p>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "inline style width: 1080px (column is 720px)" in result.output


def test_the_strip_floor_is_one_number():
    """Margin posture is a query of the CSS-owned shell, with no mirrored runtime veto."""
    css = (schema_model.ASSETS / "theme.css").read_text()
    assert "container: lf-shell / inline-size" in css
    assert re.search(r"@container\s+lf-shell\s*\(min-width:\s*1152px\)", css)
    assert "data-lf-cramped" not in css


def test_the_sidebar_and_note_floor_is_their_sum():
    """Two opposite margin residents need both strips as well as the ordinary floor.

    Media queries cannot read custom properties, so the combined breakpoint is written
    as a pixel value beside the sidebar rule. Hold that necessary copy to the two tokens
    it represents instead of letting a later width change silently squeeze the prose."""
    css = (schema_model.ASSETS / "theme.css").read_text()
    floor = 1152
    sidebar = re.search(r"--sidebar:\s*(\d+)px", css)
    assert sidebar
    combined = floor + int(sidebar[1])
    assert re.search(rf"@container\s+lf-shell\s*\(min-width:\s*{combined}px\)", css), (
        f"a sidebar and sidenote need {combined}px together, but no shell query grants "
        "their composed posture at that floor"
    )


def test_media_names_a_file_by_its_bytes_and_serves_it(page_dir, tmp_path, server):
    """An image reaches a page by reference, because the page's author is a language
    model and a screenshot is a megabyte of base64 it cannot type. The name is the
    hash of the bytes, which is what lets the page directory keep its promise while
    holding content: two versions showing the same screenshot share the one file, and
    a name the user has already approved can never come to mean different pixels."""
    shot = tmp_path / "nav.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"pretend pixels")
    (url,) = [u for _, u in media_model.cmd_media(page_dir, [shot])]
    assert re.fullmatch(r"/media/[a-f0-9]{16}\.png", url)
    # Re-adding the same bytes is the same file, not a second copy of it.
    assert media_model.cmd_media(page_dir, [shot])[0][1] == url
    assert len(list((page_dir / "media").iterdir())) == 1

    status, body = fetch(server + url)
    assert (status, body) == (200, shot.read_bytes())
    # And nothing else out of the directory: the log is not a served path.
    assert fetch(server + "/comments.jsonl")[0] == 404


def test_check_names_a_media_reference_the_directory_cannot_answer(page_dir):
    """A broken image is silent in the file and obvious on the page. The render gate
    would see the 404, but it runs once; this runs on every version, and whether a
    file is there is as deterministic as whether an id is."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p><img alt="x" src="/media/deadbeefdeadbeef.png"></p>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "/media/deadbeefdeadbeef.png isn't in the page directory" in result.output

    # A mention is not a reference: a page explaining leaf writes one of these
    # paths in its prose, and reading the markup rather than the attributes would
    # send its author hunting for a screenshot the page never asks for.
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p>Write it as <code>"/media/deadbeefdeadbeef.png"</code>.</p>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_reads_only_the_page_stylesheet_and_stays_near_free(page_dir):
    """A version's CSS is what its <style> blocks hold. Reading the whole file as one
    made a megabyte of base64 (one screenshot as a data: URI) into a stylesheet to
    tokenize, and the rule scanner reading it used to backtrack quadratically across any
    long brace-free run, which took the better part of an hour. The clock bound is three
    orders of magnitude above the fixed cost, so it fails on a re-introduced quadratic
    and not on a slow machine; the assertion above it fails on the shape that fed it the
    page."""
    blob = "A" * 1_000_000
    html = PAGE.replace(
        "<h2>Plan</h2>",
        f'<h2>Plan</h2><p><img alt="shot" src="data:image/png;base64,{blob}"></p>',
    )
    (page_dir / "versions" / "v1.html").write_text(html)
    parser = structure_model._StructParser()
    parser.feed(html)
    parser.close()
    assert parser.css == ""

    started = time.monotonic()
    assert check(page_dir).exit_code == 0
    assert time.monotonic() - started < 10


def test_check_reads_a_page_stylesheet_as_css(page_dir):
    """Grammar, not brace-counting. A `}` inside a string is a character, and counting it
    as the end of a block drops every declaration after it in that rule. A comment's
    braces are not braces either. And an @media wraps rules of its own, which a walk that
    read the sheet as one flat run of blocks would attribute to the query."""

    def checked(css):
        (page_dir / "versions" / "v1.html").write_text(styled(css))
        return check(page_dir)

    assert (
        "sets width: 900px" in checked("@media print { .wide { width: 900px } }").output
    )
    assert (
        "sets width: 900px"
        in checked('.wide::before { content: "}"; width: 900px }').output
    )
    assert checked("/* .wide { width: 900px } */").exit_code == 0


def test_check_reports_css_syntax_errors_in_every_authored_source(page_dir):
    theme = page_dir / "theme.css"
    theme.write_text(theme.read_text() + "\n.theme { color red; }\n")
    (page_dir / "versions" / "v1.html").write_text(
        styled(
            '.page { color: "unterminated\n; }',
            '<p style="color red">All three CSS inputs are malformed.</p>',
        )
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "page <style> syntax error" in result.output
    assert "inline style #1 syntax error" in result.output
    assert "theme.css syntax error" in result.output
    assert result.output.count("syntax error") == 3


def test_check_takes_its_column_from_what_a_page_states_outright(page_dir):
    """A rule inside an at-rule applies only when a condition this check never evaluates
    holds, which cuts both ways. It cannot set the column, because the column is the
    baseline everything else is measured against — reading it there let one line of print
    CSS measure every screen element against 2000px and pass the page. It can overflow
    one, because a pin is a risk rather than a baseline: it is too wide whenever its
    condition holds."""
    (page_dir / "versions" / "v1.html").write_text(
        styled(
            "main { --lf-column: 1; max-width: 760px }"
            " @media print { main { --lf-column: 1; max-width: 2000px } }",
            '<svg width="900" height="10"></svg>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert '<svg width="900"> exceeds column (760px)' in result.output

    # And nesting is not a condition: a column stated on a rule that also wraps one stands.
    (page_dir / "versions" / "v1.html").write_text(
        styled(
            "main { --lf-column: 1; max-width: 1000px; & p { color: red } }",
            '<svg width="900" height="10"></svg>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_counts_only_a_width_fixed_in_pixels(page_dir):
    """A length is a typed value, not a string ending in `px`. A percentage or a vw
    scales to whatever contains it, and a calc() with a px term inside it is arithmetic
    rather than a pin — only a lone pixel length can overflow the column."""
    (page_dir / "versions" / "v1.html").write_text(
        styled(".a { width: 200% } .b { width: 90vw } .c { width: calc(100% - 900px) }")
    )
    assert check(page_dir).exit_code == 0

    (page_dir / "versions" / "v1.html").write_text(
        styled(".d { width: 900px !important }")
    )
    assert "sets width: 900px" in check(page_dir).output


def test_check_measures_against_the_column_the_page_sets_for_itself(page_dir):
    """A page-local <style> is the page's own answer to how wide it reads, so it wins
    over the vendored theme's 720px and an element wider than the theme allows passes.

    It answers by claiming the column, the same way the theme's own rule does. A page
    that only sets a width sets a width: which rule is the measure everything else is
    read against is a thing a stylesheet says, not a thing a reader works out from how
    the rule is spelled."""
    (page_dir / "versions" / "v1.html").write_text(
        styled(
            "main { --lf-column: 1; max-width: 1000px }",
            '<svg width="900" height="10"></svg>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_reads_widths_where_the_document_states_them(page_dir):
    """A width is what an attribute or a <style> block states. Scanning the file's text
    for one instead read a rule quoted in the page's prose as a rule the page applies,
    and never saw a style="" written with the other quote character."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", "<h2>Plan</h2><div style='width:900px'>wide</div>"
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "inline style width: 900px (column is 720px)" in result.output

    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            "<h2>Plan</h2><p>Write it as <code>.wide { width: 900px }</code>.</p>",
        )
    )
    assert check(page_dir).exit_code == 0


def test_an_ask_role_declares_an_addressable_instance(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-idless-decision"] = {
        "description": "A decision without an address.",
        "type": "object",
        "properties": {"open": {"type": "boolean"}},
        "additionalProperties": False,
        "x-content": "prose",
        "x-awaits": {"when": {"open": [True]}, "answers": ["answer"]},
        "x-state": {
            "answer": {
                "detail": {"type": "object", "additionalProperties": False},
                "facet": "answer",
                "unit": "widget",
            }
        },
        "x-upgrade": False,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 1
    assert "x-awaits instances are addressable" in result.output


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2026-08-21T08:00:00Z", True),
        ("2026-08-21t08:00:00z", True),
        ("2026-08-21T08:00:00+01:30", True),
        ("2026-08-21T08:00:00", False),
        ("2026-08-21 08:00:00+00:00", False),
    ],
)
def test_date_time_format_is_an_absolute_rfc3339_instant(value, valid):
    schema = {"type": "string", "format": "date-time"}

    assert registry_contract.json_validator(schema).is_valid(value) is valid


def test_init_refuses_to_drop_the_contract_of_a_held_comment(page_dir):
    """A hold is recorded against the declaration that admitted it."""
    package = page_dir.parent / "mutable-command-hub"
    shutil.copytree(COMMAND_HUB_PACKAGE, package)
    # An explicit selection replaces the recorded one, so it restates `diagram` for
    # PAGE's lf-diagram beside the copy of command-hub this test mutates.
    selected = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "./mutable-command-hub",
            "--package",
            "diagram",
            str(page_dir),
        ],
    )
    assert selected.exit_code == 0, selected.output
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        PAGE.replace(
            "</section>",
            '<lf-tasks id="work"><lf-task id="goal" status="active" talk>'
            "<strong>Goal</strong></lf-task></lf-tasks></section>",
        )
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Pause after this pass.",
            "anchor": {"section": "goal"},
            "holds": "goal",
        },
    )
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    del registry["lf-task"]["x-conversation"]["hold"]
    registry_path.write_text(json.dumps(registry))

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "x-conversation hold target" in result.output


def test_init_refuses_to_drop_the_contract_of_a_version_response(page_dir):
    version = page_dir / "versions" / "v1.html"
    version.write_text(PAGE.replace("<lf-options>", '<lf-options id="choice" choose>'))
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-options"]["x-conversation"] = {
        "when": {"choose": [True]},
        "response": {"kind": "version", "verb": "choose"},
    }
    registry_path.write_text(json.dumps(registry))
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Add the camera first.",
            "anchor": {"section": "choice"},
            "response": {"kind": "version", "verb": "choose"},
        },
    )
    registry = json.loads(registry_path.read_text())
    del registry["lf-options"]["x-conversation"]["response"]
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text(
        json.dumps({"lf-options": registry["lf-options"]})
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "x-conversation response target" in result.output


def test_shared_package_declarations_compose_by_member():
    """One package can extend a shared declaration without copying its peers."""
    board = {"role": "holder", "state": "status"}
    lane = {"role": "holder", "state": "phase"}
    merged = {"$workflow": {"widgets": {"lf-board": board}}}

    registry_layer.merge_layer_entries(
        merged, {"$workflow": {"widgets": {"lf-lane": lane}}}
    )

    assert merged["$workflow"]["widgets"] == {
        "lf-board": board,
        "lf-lane": lane,
    }


def test_x_awaits_names_the_verbs_that_answer_it(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-awaits"]["answers"] = ["missing"]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 1
    assert "x-awaits names undeclared answer verbs ['missing']" in result.output


def test_the_reply_door_refuses_a_picture_the_page_directory_has_not_got(page_dir):
    """The two markup doors ask the same thing of a reference to a file.

    A widget carrying pictures is exactly the shape an agent sends in a reply — here
    is how it looks now, and after — and `/media/…` is how markup names one. A version
    naming a file the directory cannot answer is refused, and the same markup in a
    reply was accepted and frozen: the log is append-only, so it is two broken images
    for as long as the page exists, and no check afterwards would ever mention them.

    The version door is the control. It is the same reading, so a difference between
    them can only be one of the two having stopped asking."""
    shot = (
        '<lf-shot id="ps-shot" alt="the panel before and after" '
        'before="/media/nope.png" after="/media/gone.png"></lf-shot>'
    )
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace("</main>", shot + "</main>")
    )
    refused = check(page_dir)
    assert refused.exit_code == 1
    assert "/media/nope.png isn't in the page directory" in refused.output, (
        f"the version door stopped asking, so the comparison below is empty: "
        f"{refused.output}"
    )

    (page_dir / "versions" / "v1.html").write_text(PAGE)
    publish(page_dir)
    opened = CliRunner().invoke(
        cli_model.cli, ["comment", str(page_dir), "--text", "show me?"]
    )
    assert opened.exit_code == 0, opened.output
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            json.loads(opened.output)["id"],
            "--text",
            "here:",
            "--markup",
            shot,
        ],
    )
    assert posted.exit_code == 1, (
        f"the reply door froze a picture the page has not got into the log:\n"
        f"{posted.output}"
    )
    assert "/media/nope.png isn't in the page directory" in posted.output, posted.output
    assert not [e for e in events_model.read_events(page_dir) if e["kind"] == "reply"]


def test_the_door_admits_a_reaction_only_as_a_token_the_layer_declares(
    server, page_dir
):
    """A reaction is a comment or reply carrying `token` in place of `text`: one of
    the two and never both, a word the merged vocabulary declares, and no
    suggestion, hold, or markup riding beside it. What the door lets through it
    also lets the reader take back — while it is still a mark. An answer under it
    makes it a conversation, and a message with words in it was never a mark."""
    publish(page_dir)
    root = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "revision": 1, "text": "why?"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    for bad, says in [
        (
            {"kind": "comment", "revision": 1, "token": "shrug"},
            "unknown reaction token 'shrug'",
        ),
        (
            {"kind": "comment", "revision": 1, "token": "ok", "text": "and"},
            "valid under each of",
        ),
        ({"kind": "comment", "revision": 1}, "not valid under any"),
        (
            {"kind": "comment", "revision": 1, "token": "ok", "suggestion": True},
            "suggestion",
        ),
        (
            {"kind": "reply", "revision": 1, "parent": root["id"], "token": "nope"},
            "unknown",
        ),
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, (bad, body)
        assert says in json.loads(body)["error"], (bad, body)

    reaction = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "token": "cut",
                    "anchor": {"section": "plan", "quote": "Ship dark"},
                }
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert reaction["author"] == "user" and "text" not in reaction
    nod = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "reply", "revision": 1, "parent": root["id"], "token": "ok"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert nod["token"] == "ok" and nod["parent"] == root["id"]

    # A message with words in it is said rather than unsaid.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": root["id"]}).encode(),
    )
    assert status == 400 and "is not a reaction" in json.loads(body)["error"]
    # The mark on the thread comes off with one press.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": nod["id"]}).encode(),
    )
    assert status == 200, body
    # And comes off once, however the second press gets here — the racing tab of the
    # door's own docstring. A withdrawn reaction is gone from `build_threads`, so the
    # kind's thread walk had nothing to find and raised out of the door instead: a 500
    # the browser is told to retry, against a state that will never answer differently.
    # The no-op costs a notice, which is what a final refusal is.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": nod["id"]}).encode(),
    )
    assert status == 400, body
    answer = json.loads(body)
    assert answer["final"] is True, body
    assert "already been taken back" in answer["error"], body
    # Answered, the page reaction is a conversation, and the withdrawal would orphan
    # the answer; the reader's move is in the thread it opened.
    conversation_model.cmd_reply(page_dir, reaction["id"], "Which part is long?", None)
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": reaction["id"]}).encode(),
    )
    assert status == 400 and "has been answered" in json.loads(body)["error"]
