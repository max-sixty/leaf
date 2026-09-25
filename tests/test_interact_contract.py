"""Event, registry, replay-contract, and media tests."""

import contextlib
import json
import os
import re
import shutil
import textwrap
import threading
import time
from copy import deepcopy

import model_folds as model
import pytest
from click.testing import CliRunner
from interact_support import (
    ACCEPT,
    ADOPTED,
    COMMAND_HUB_PACKAGE,
    COMMAND_SUBJECTS,
    COMMENT,
    PAGE,
    PAGE_PACKAGES,
    PILOT_PURGE,
    SHELVED,
    TRIAL_CACHE,
    TRIAL_LOG,
    Json,
    ModelPage,
    Prose,
    _agent_verb_answers,
    _body_record_with_nested_widget,
    _body_record_with_prose,
    _mutated_registry_check,
    _report_body_record,
    _report_detail_drift,
    _report_no_record,
    _report_position_record,
    _report_says_attr,
    _report_undeclared_attr,
    _report_without_overruled,
    _report_without_upgrade,
    _tasks_version,
    _user_verb_update,
    append_command,
    assert_revendor_serializes_writer,
    check,
    comment,
    decide,
    declare_data_input,
    element_declaration,
    fetch,
    live_versions,
    publish,
    published,
    stamp,
    stamp_activation,
    styled,
    trial_version,
    yaml_block,
    yaml_document,
)
from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import conversation as conversation_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import files as files_model
from leaf import host as host_model
from leaf import media as media_model
from leaf import passages as passages_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import structure as structure_model
from leaf import styles as styles_model
from leaf import vendoring as vendoring_model
from leaf.registry import contract as registry_contract
from leaf.registry import layer as registry_layer
from leaf.registry import page as registry_page
from leaf.registry import storage as registry_storage
from leaf.registry import validation as registry_validation
from leaf.render_gate import preview as render_gate_model
from page_fixtures import package_selection_args


def test_new_words_reopen_a_thread_without_settling_a_newer_user_turn(page_dir):
    """Late answers keep their exact scope; marks and failure receipts stay closed."""
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "question", "author": "user", "text": "Why?"},
    )
    conversation_model.cmd_resolve(page_dir, "question")
    for message in (
        {"author": "user", "token": "keep"},
        {
            "author": "agent",
            "text": "Delivery failed",
            "failure": "unavailable",
            "responds": "question",
        },
    ):
        events_model.append_event(
            page_dir, {"kind": "reply", "parent": "question", **message}
        )
        threads = event_folds_model.build_threads(
            events_model.read_events(page_dir), {}
        )
        assert threads["question"]["resolved"] is not None

    answer = conversation_model.cmd_reply(
        page_dir,
        "question",
        "Here is the completed answer.",
        None,
        for_event="question",
        when_settled="post",
    )
    assert answer["responds"] == "question"
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"] is None
    assert not event_folds_model.awaits_agent(threads["question"])
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
        == {}
    )

    conversation_model.cmd_resolve(page_dir, answer["id"])
    events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "correction",
            "author": "user",
            "parent": answer["id"],
            "text": "Please address this correction too.",
        },
    )
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"] is None
    conversation_model.cmd_reply(
        page_dir,
        "question",
        "Additional detail on the original question.",
        None,
        for_event="question",
        when_settled="post",
    )
    assert delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    ) == {"correction": {"kind": "reply", "to": "correction", "for": "correction"}}
    closed = conversation_model.cmd_resolve(page_dir, "question")
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"]["id"] == closed["id"]


def test_late_answer_to_a_frozen_widget_reopens_without_repeating_its_obligation(
    server, page_dir
):
    """Reopening restores the conversation while its completed choice stays answered."""
    publish(page_dir)
    question = conversation_model.cmd_comment(
        page_dir,
        None,
        None,
        None,
        "Choose an option.",
        '<lf-ask id="thread-ask"><h2>Choose one</h2>'
        '<lf-options id="thread-picks" choose><lf-option id="thread-option">'
        "Thread option</lf-option></lf-options></lf-ask>",
    )
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": files_model.latest_revision(page_dir),
                "widget": "thread-picks",
                "action": "choose",
                "detail": {"options": ["thread-option"]},
            }
        ).encode(),
    )
    assert status == 200, body
    choice = json.loads(body)["state"]["events"][-1]
    assert choice["id"] in delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    )
    conversation_model.cmd_resolve(page_dir, question["id"])
    answer = conversation_model.cmd_reply(
        page_dir,
        question["id"],
        "I applied your choice.",
        None,
        for_event=choice["id"],
        when_settled="post",
    )
    assert answer["responds"] == choice["id"]
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads[question["id"]]["resolved"] is None
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
        == {}
    )


# One question quoted back and the same question live. The pair is what makes the
# exhibit refusal below the exhibit's doing: the two groups are the same markup
# under different holders.
STATED_KIT = """<!doctype html>
<html lang="en">
<head>
<title>Kit</title>
</head>
<body>
<main>
<lf-specimen id="last-year" label="the kit we took last year">
  <lf-options id="quoted-pick" choose>
    <lf-option id="quoted-paper"><strong>Paper maps</strong> Nothing to charge.</lf-option>
    <lf-option id="quoted-gps"><strong>Dedicated GPS</strong> Offline maps.</lf-option>
  </lf-options>
</lf-specimen>
<lf-ask id="kit-decision">
  <h2>Which navigation kit this year?</h2>
  <lf-options id="live-pick" choose>
    <lf-option id="live-paper"><strong>Paper maps</strong> Nothing to charge.</lf-option>
    <lf-option id="live-gps"><strong>Dedicated GPS</strong> Offline maps.</lf-option>
  </lf-options>
</lf-ask>
</main>
</body>
</html>
"""
STATED_LOG = [
    {
        "kind": "comment",
        "id": "c1",
        "seq": 1,
        "ts": "2026-09-19T12:00:00+00:00",
        "author": "user",
        "revision": 1,
        "text": "Which one did we take?",
    }
]
STATED_PICK = {"kind": "action", "author": "user", "revision": 1, "action": "choose"}

# A deck with two cards still queued, so its first swipe classifies and only its
# second empties the queue.
STATED_DECK = """<!doctype html>
<html lang="en">
<head>
<title>Triage</title>
</head>
<body>
<main>
<lf-ask id="triage-decision">
  <h2>Which follow-ups should we keep?</h2>
  <lf-swipe-deck id="triage">
    <lf-swipe-pile id="queue" verdict="unseen">
      <lf-swipe-card id="card-a"><strong>Rolling expiry</strong></lf-swipe-card>
      <lf-swipe-card id="card-b"><strong>Bounded fallback</strong></lf-swipe-card>
    </lf-swipe-pile>
    <lf-swipe-pile id="keep" verdict="keep"></lf-swipe-pile>
  </lf-swipe-deck>
</lf-ask>
</main>
</body>
</html>
"""
STATED_SWIPE = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "triage",
    "action": "swipe",
}


def test_a_pick_names_only_options_its_group_holds():
    """A `choose` names authored options or ones a standing `add` created.

    The user's own option travels as two sends, the `add` and then the pick of it.
    Were the `add` refused, the pick behind it would otherwise answer the Ask with an
    option nobody can see.
    """
    page = ModelPage(STATED_KIT)
    pick = {**STATED_PICK, "widget": "live-pick", "detail": {"options": ["live-mine"]}}

    def admit(log, event):
        return event_contracts_model.admitted_event(page, log, dict(event))

    with pytest.raises(events_model.EventRefused) as refused:
        admit(STATED_LOG, pick)
    assert "['live-mine'] name no member of 'live-pick'" in str(refused.value)

    add = admit(
        STATED_LOG,
        {
            **STATED_PICK,
            "widget": "live-pick",
            "action": "add",
            "detail": {"option": "live-mine", "text": "My own way"},
        },
    )
    assert add["meaning"]["unit"] == "live-mine"
    added = {**add, "id": "a1", "ts": "2026-09-19T12:01:00+00:00", "seq": 2}
    assert admit([*STATED_LOG, added], pick)["detail"] == {"options": ["live-mine"]}


def test_history_reaches_only_a_page_that_renders_it_and_keeps_a_pick_as_made():
    """The served history words a pick from the document it was made in.

    A later version that removes the question leaves the row naming the option the
    user picked, by its title, and a withdrawn pick stays a row marked undone. A page
    whose markup holds no widget declaring `x-history` is not served the reading.
    """
    question = model.leaf_page(
        "Route",
        """<h1>Route</h1>
<lf-options id="route" choose>
  <lf-option id="fast"><strong>Fast path</strong> ships on Friday.</lf-option>
  <lf-option id="slow">Slow path</lf-option>
</lf-options>
<lf-activity id="feed"></lf-activity>""",
    )
    retired = model.leaf_page(
        "Route", '<h1>Route</h1><lf-activity id="feed"></lf-activity>'
    )
    pick = {"kind": "action", "widget": "route", "action": "choose"}
    events = (
        {**pick, "detail": {"options": ["fast"]}},
        {**pick, "detail": {"options": ["slow"]}},
        {"kind": "undo", "undoes": "e2"},
    )

    history = model.reading({1: question, 2: retired}, events)["history"]
    assert [(row["id"], row["gesture"], row["undone"]) for row in history] == [
        ("e2", {"form": "choice", "chosen": ["Slow path"]}, True),
        ("e1", {"form": "choice", "chosen": ["Fast path"]}, False),
    ]

    unwatched = question.replace('<lf-activity id="feed"></lf-activity>', "")
    assert "history" not in model.reading(unwatched, events)


def test_history_words_a_pick_of_an_added_option_by_what_the_user_wrote():
    """An added option is in no document, so its words come from the `add` that
    wrote it, as its inline Markdown shows them. The pick of it reads by those
    words even after the add is undone, since that is what the user picked, and an
    id an undone add freed and a later add reused reads each gesture by the add
    standing when that gesture was made."""
    question = model.leaf_page(
        "Route",
        """<h1>Route</h1>
<lf-options id="route" choose>
  <lf-option id="fast"><strong>Fast path</strong> ships on Friday.</lf-option>
</lf-options>
<lf-activity id="feed"></lf-activity>""",
    )

    def add(text):
        return {
            "kind": "action",
            "widget": "route",
            "action": "add",
            "detail": {"option": "route-mine", "text": text},
        }

    pick = {
        "kind": "action",
        "widget": "route",
        "action": "choose",
        "detail": {"options": ["route-mine"]},
    }
    events = (
        add("**Ship** half"),
        pick,
        {"kind": "undo", "undoes": "e2"},
        {"kind": "undo", "undoes": "e1"},
        add("Ship everything"),
        pick,
    )

    history = model.reading(question, events)["history"]
    assert [(row["id"], row["gesture"]) for row in history] == [
        ("e6", {"form": "choice", "chosen": ["Ship everything"]}),
        ("e5", {"form": "add", "words": "Ship everything"}),
        ("e2", {"form": "choice", "chosen": ["Ship half"]}),
        ("e1", {"form": "add", "words": "Ship half"}),
    ]


def test_the_swipe_that_empties_the_queue_is_the_decks_answer():
    """A deck's Ask is answered by its standing state, so admission marks the swipe
    that empties the queue as the answer and no swipe before it.

    Every classification is the same verb carrying its own result, so the position
    record is what keeps a crafted one honest: its unit must be a card the deck
    actually holds, or a deck could stand answered on a classification that never
    existed.
    """
    page = ModelPage(STATED_DECK, packages=("swipe",))

    def admit(log, event):
        return event_contracts_model.admitted_event(page, log, dict(event))

    first = admit(
        [], {**STATED_SWIPE, "detail": {"card": "card-a", "to": "keep", "rank": "0i"}}
    )
    assert first["meaning"]["unit"] == "card-a"
    assert "answer" not in first["meaning"]
    log = [{**first, "id": "s1", "ts": "2026-09-19T12:01:00+00:00", "seq": 1}]
    last = admit(
        log, {**STATED_SWIPE, "detail": {"card": "card-b", "to": "keep", "rank": "0r"}}
    )
    assert last["meaning"]["answer"] is None

    with pytest.raises(events_model.EventRefused) as refused:
        admit(
            log,
            {
                **STATED_SWIPE,
                "detail": {"card": "not-a-card", "to": "keep", "rank": "0r"},
            },
        )
    assert "unknown card 'not-a-card'" in str(refused.value)


def test_admission_decides_from_the_markup_and_the_standing_log_alone():
    """The door reads a page through `PageView` and reaches past it for nothing.

    What makes an event admissible is the authored document it names, the
    vocabulary that document captured, and the log standing in front of it. So a
    page whose revisions are stated rather than stored reaches the same verdicts,
    and a test of one rule can be the markup that rule is about — which is what
    `ModelPage` is. Each verdict below comes from a different gate, so a gate
    that went back to opening a file of its own fails here.
    """
    page = ModelPage(STATED_KIT)

    def admit(event):
        return event_contracts_model.admitted_event(page, STATED_LOG, dict(event))

    def refusal(event):
        with pytest.raises(events_model.EventRefused) as refused:
            admit(event)
        return str(refused.value)

    choose_live = {
        **STATED_PICK,
        "widget": "live-pick",
        "detail": {"options": ["live-gps"]},
    }
    assert admit(choose_live)["meaning"]["unit"] == "live-pick"
    assert (
        refusal({**choose_live, "revision": 2}) == "action revision must be one of [1]"
    )
    assert "stands inside an exhibit" in refusal(
        {**STATED_PICK, "widget": "quoted-pick", "detail": {"options": ["quoted-gps"]}}
    )
    answer = {"kind": "reply", "author": "agent", "revision": 1, "text": "The GPS."}
    assert refusal({**answer, "parent": "c9"}) == "unknown parent 'c9'"
    assert admit({**answer, "parent": "c1"})["parent"] == "c1"


def test_a_created_child_is_its_actions_unit_and_its_words_stay_payload():
    # Words that happen to spell an element id never become a dependency; the
    # created id does once the markup holds it inside the sender.
    event = {
        "widget": "group",
        "detail": {"option": "user-child", "text": "authored-child"},
        "meaning": {"depends": ["group", "user-child"]},
    }
    spec = {"unit": "option", "creates": {"child": "lf-option", "words": "text"}}

    assert registry_contract.created_child(event, spec) == (
        "user-child",
        "authored-child",
    )
    assert registry_contract.created_child(event, {"unit": "option"}) is None
    assert event_folds_model.action_rests_on(event, {"authored-child": ("group",)}) == [
        "group"
    ]
    assert event_folds_model.action_rests_on(
        event, {"authored-child": ("group",), "user-child": ("group",)}
    ) == ["group", "user-child"]


# Two suggestions on one page, and the decisions a user takes on them. The
# widgets are here rather than named only in the events because a settlement
# rests on its widget: the door derives each action's coordinate and its answer
# from this markup, so a log that named a widget the page has not got would be
# refused rather than folded.
SETTLED = model.leaf_page(
    "feeders",
    """<h1 id="feeders">Feeders</h1>
<lf-suggestion id="sug-a" resolves="e1">
  <lf-old><p id="a-old">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="a-new">Refill when the camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-b" resolves="e1">
  <lf-old><p id="b-old">Check the cameras weekly.</p></lf-old>
  <lf-new><p id="b-new">Check the cameras each morning.</p></lf-new>
</lf-suggestion>""",
)
ASKED = {"kind": "comment", "text": "cameras are flaky"}
PICKED = {
    "kind": "action",
    "widget": "sug-a",
    "action": "decide",
    "detail": {"outcome": "accept"},
}
TURNED_DOWN = {
    "kind": "action",
    "widget": "sug-a",
    "action": "decide",
    "detail": {"outcome": "reject"},
}
CLOSED = {"kind": "resolve", "parent": "e1"}


def settlement(*events):
    """What the thread `e1` stands resolved by, after exactly this log."""
    return model.threads(model.reading(SETTLED, events))["e1"]["resolved"]


def test_an_accept_carries_its_thread_resolution():
    """One atomic event: admission reads the thread the accept answers off the
    widget's authored `resolves` in the document it was made on, because the honoring
    version retires the wrapper that held the mapping. A reject declines the fix and
    closes nothing."""
    threads = model.threads(
        model.reading(
            SETTLED,
            (
                ASKED,
                {"kind": "comment", "text": "the other thing"},
                PICKED,
                {**TURNED_DOWN, "widget": "sug-b"},
            ),
        )
    )
    assert threads["e1"]["resolved"]["widget"] == "sug-a"
    assert threads["e2"]["resolved"] is None
    assert threads["e1"]["resolved"]["meaning"]["answer"] == "e1"


def test_an_answer_the_user_took_back_leaves_its_thread_open(page_dir):
    """An action names the thread it settles, and it settles it only while the
    user still stands behind it. Withdrawing the answer is one of the three ways
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
            "detail": {"options": ["flag-first"]},
            "meaning": {
                "scope": "page",
                "unit": "picks",
                "depends": ["flag-first", "picks"],
                "answer": "c1",
            },
        },
    )
    spk = passages_model.spoken(
        structure_model.SourceDocument(
            (page_dir / "index.html").read_text(encoding="utf-8")
        ),
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


def test_server_takes_back_only_a_standing_gesture_of_the_users_own(server, page_dir):
    """`undoes` is checked completely where it enters, so nothing downstream asks a
    second time whether it points at something real. What an undo may name is one
    unwithdrawn gesture of the user's own: an agent's `leaf resolve` is not
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
        page_dir, {"kind": "resolve", "author": "agent", "parent": posted["id"]}
    )

    for bad, says in [
        ({"kind": "undo", "undoes": "nope"}, "unknown"),
        # The user's own gestures only, and only the kinds that carry state.
        (
            {"kind": "undo", "undoes": agent_closed["id"]},
            "not the user's own gesture",
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
    # user's history rather than toggling the last gesture on and off.
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
    real_undo_error = event_contracts_model.undo_error
    validation_lock = threading.Lock()
    second_validation = threading.Event()
    validation_calls = 0

    def expose_validation_gap(event, events, within, absorbed):
        nonlocal validation_calls
        error = real_undo_error(event, events, within, absorbed)
        with validation_lock:
            validation_calls += 1
            call = validation_calls
        if call == 1:
            second_validation.wait(timeout=1)
        else:
            second_validation.set()
        return error

    monkeypatch.setattr(event_contracts_model, "undo_error", expose_validation_gap)
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


def test_a_reject_after_an_accept_reopens_the_thread():
    """A thread stands settled by its widget's standing answer, not by the fact an
    answer was once given. Turning the fix down and leaving the question filed away
    as answered by it is invisible from both sides — the fold reports the suggestion
    rejected while the panel reports the thread closed, and nothing says so.

    Read across the reject rather than after it: an assertion that the thread is open
    passes just as well on a log where the accept never settled it."""
    assert settlement(ASKED, PICKED)["detail"] == {"outcome": "accept"}
    assert settlement(ASKED, PICKED, TURNED_DOWN) is None


def test_an_accept_after_a_reject_settles_the_thread():
    """The other order, which the one-way latch already got right — this pins it
    against the fix for the latch, not against the latch. A fold that kept the
    first answer per widget rather than the last reads every case here correctly
    except this one, where nothing would ever settle the thread."""
    assert settlement(ASKED, TURNED_DOWN) is None
    assert settlement(ASKED, TURNED_DOWN, PICKED)["detail"] == {"outcome": "accept"}


def test_a_resolve_between_two_decisions_outlives_the_second():
    """A resolve is a person saying the conversation is done, and the log cannot
    take that back the way it takes back a decision. The one-way latch got this
    right by never clearing anything; what it pins is the obvious wrong fix for the
    latch — a reject that clears whatever its widget resolved — which would wipe a
    press made in between. Settling in place is what makes it hold: the superseded
    accept never stood, so it has nothing to clear."""
    assert settlement(ASKED, PICKED, CLOSED)["kind"] == "resolve"
    assert settlement(ASKED, PICKED, CLOSED, TURNED_DOWN)["kind"] == "resolve"


def test_taking_back_a_reject_lets_the_accept_it_superseded_stand_again():
    """The two ways an answer stops standing compose, and this is where they meet: a
    reject supersedes the accept before it, and taking the reject back leaves the
    accept standing as the widget's answer once more. A withdrawal read only by the
    walk and not by the standing answer would leave the thread open with the log
    holding nothing that says so."""
    assert settlement(ASKED, PICKED, TURNED_DOWN) is None
    # The reject is the third event written, so `e3` is what the undo names.
    taken_back = {"kind": "undo", "undoes": "e3"}
    assert settlement(ASKED, PICKED, TURNED_DOWN, taken_back)["detail"] == {
        "outcome": "accept"
    }


def test_another_widget_s_answer_holds_a_thread_two_widgets_answered():
    """Superseding is per widget, because the decision is. Two suggestions can answer one
    question, and deciding against the second says nothing about the first — a fold
    keyed on the thread instead of the widget would have let it."""
    held = settlement(ASKED, {**PICKED, "widget": "sug-b"}, PICKED, TURNED_DOWN)
    assert held["widget"] == "sug-b"


def test_init_refuses_a_log_the_incoming_layer_no_longer_speaks(page_dir):
    """The log is append-only and a retired verb has no successor to map to, so
    re-vendoring over one is how recorded decisions fall silent — annabels-drafts
    holds fifteen `decide` events today's widgets would drop on the first reload.
    The re-vendor is refused rather than offering a way to discard that history."""
    # This models a page made under an older registry where lf-draft declared
    # `decide`: the tag and widget id survive, but the incoming verb does not.
    version = page_dir / "index.html"
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
            "meaning": {
                "scope": "page",
                "unit": "d1",
                "depends": ["d1"],
                "answer": None,
            },
        },
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "decide" in result.output


def test_init_refuses_to_retire_a_frozen_thread_host_request_verb(page_dir):
    """A request from frozen markup remains part of every candidate document."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-ask id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-ask></lf-task></lf-command>"
    )
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "Restart?"},
    )
    conversation_model.cmd_reply(
        page_dir,
        "c1",
        "Use this operation.",
        operation,
        for_event="c1",
    )
    append_command(
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

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "request contract" in result.output and "restart" in result.output


@pytest.mark.parametrize("receipt_requests", [["missing"], ["request-1", "request-1"]])
def test_init_does_not_revalidate_a_written_receipt_lifecycle(
    page_dir, receipt_requests
):
    """Receipt integrity is enforced at append, not by candidate validation."""
    operation = (
        '<lf-command id="hub"><lf-task id="goal" status="blocked">'
        "<strong>Goal</strong>"
        + COMMAND_SUBJECTS
        + '<lf-ask id="commands-decision"><h3>What next?</h3>'
        '<lf-operations id="commands" target="goal" worker="worker" worktree="tree">'
        '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
        "</lf-operations></lf-ask></lf-task></lf-command>"
    )
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", operation + "</section>")
    )
    publish(page_dir)
    if receipt_requests[0] != "missing":
        append_command(
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
                "author": "agent",
                "request": request,
                "status": "succeeded",
                "text": "Host operation completed",
            },
        )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output


def test_init_refuses_a_log_holding_a_token_the_incoming_layer_dropped(
    page_dir, monkeypatch
):
    """A layer may take a token off its bar (merge-patch `null`), and a page whose log
    already holds a reaction on it is refused a re-vendor the way one holding a
    retired verb is: the standing mark would have no glyph and no pill to take it
    back by. A token the layer keeps re-vendors as before."""
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)]).exit_code
        == 0
    )
    layer = page_dir.parent / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(
        json.dumps({"$reactions": {"tokens": {"shorten": None}}})
    )
    monkeypatch.chdir(page_dir.parent)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code != 0
    assert "no longer speaks" in result.output and "`shorten`" in result.output


def test_init_revendors_over_a_record_the_running_contract_would_not_admit(
    page_dir,
):
    """A record shape is not a gap re-vendoring creates, unlike the dropped token and
    retired verb above: admission is the schema's only reader, and the logged event
    replays the same either way."""
    publish(page_dir)
    events_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Codex",
            "mood": "uncertain",
            "revision": 1,
            "text": "Does this still mean anything?",
        },
    )

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert result.exit_code == 0, result.output
    after = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert after.exit_code == 0, after.output
    assert "Does this still mean anything?" in after.output


def test_init_tracks_logged_verbs_by_the_widget_that_declared_them(page_dir):
    """Another tag using the same verb cannot keep a retired contract alive."""
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"]
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "rank": "0i"},
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

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "lf-board" in result.output and "move" in result.output


def test_init_refuses_an_incoming_detail_contract_that_rejects_logged_actions(
    page_dir,
):
    """Keeping a verb's spelling is not enough if its payload no longer replays."""
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"]
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", board + "\n</section>")
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "rank": "0i"},
        },
    )

    registry["lf-board"]["x-state"]["move"]["detail"]["properties"]["rank"][
        "maxLength"
    ] = 1
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-board": registry["lf-board"]})
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "lf-board" in result.output and "move" in result.output
    assert "detail" in result.output


@pytest.mark.parametrize("mutation", ["drop", "words", "child"])
def test_init_refuses_changed_generated_child_semantics(page_dir, mutation):
    registry = json.loads((page_dir / "registry.json").read_text())
    options = (
        '<lf-ask id="route-decision"><h2>Which route?</h2>'
        '<lf-options id="route" choose>'
        '<lf-option id="route-authored">Authored route</lf-option>'
        "</lf-options></lf-ask>"
    )
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace("</section>", options + "</section>")
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "route",
            "action": "add",
            "detail": {"option": "route-user", "text": "User route"},
        },
    )

    add = registry["lf-options"]["x-state"]["add"]
    overlay_entries = {"lf-options": registry["lf-options"]}
    if mutation == "drop":
        del add["creates"]
    elif mutation == "words":
        add["creates"]["words"] = "words"
        fields = add["detail"]["properties"]
        fields["words"] = fields.pop("text")
        add["detail"]["required"] = ["option", "words"]
    else:
        registry["lf-option-alt"] = registry["lf-option"]
        add["creates"]["child"] = "lf-option-alt"
        overlay_entries["lf-option-alt"] = registry["lf-option-alt"]
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text(json.dumps(overlay_entries))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output


def test_init_refuses_a_logged_report_the_incoming_layer_no_longer_speaks(page_dir):
    """A report is the log's forever-contract exactly as an action is: an
    incoming layer that drops the widget's agent verb strands every recorded
    report, and the stamp refuses the re-vendor rather than let them fall
    silent."""
    version = page_dir / "index.html"
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
    task.pop("x-state")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-task": task}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "report contract" in result.output
    assert "lf-task" in result.output and "status" in result.output


def test_init_refuses_to_orphan_a_logged_visual_anchor(page_dir):
    """A re-vendored provider must keep every semantic target the log names."""
    version = page_dir / "index.html"
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

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "no longer speaks" in result.output
    assert "visual anchor 'node:A'" in result.output


def test_report_validation_and_append_cannot_straddle_revendoring(
    page_dir, monkeypatch
):
    _tasks_version(page_dir, "active")
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    task = registry["lf-task"]
    task.pop("x-state")
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-task": task}))

    report_validated = threading.Event()
    release_report = threading.Event()
    init_waiting = threading.Event()
    real_append = service_model.PageTransaction._append_record
    real_page_locked = vendoring_model.page_locked

    def paused_append(page, event):
        if event["kind"] == "report":
            report_validated.set()
            assert release_report.wait(5)
        return real_append(page, event)

    @contextlib.contextmanager
    def observed_page_locked(locked):
        if locked == page_dir and threading.current_thread().name == "re-vendor":
            init_waiting.set()
        with real_page_locked(locked) as held:
            yield held

    monkeypatch.setattr(service_model.PageTransaction, "_append_record", paused_append)
    monkeypatch.setattr(vendoring_model, "page_locked", observed_page_locked)
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
            vendoring_model.cmd_init(page_dir, selected=(*PAGE_PACKAGES, "./.leaf"))
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
    assert "x-state" in json.loads((page_dir / "registry.json").read_text())["lf-task"]


def test_a_preview_holds_one_contract_until_it_closes(page_dir, monkeypatch):
    before = registry_storage.layer_generation(page_dir)
    init_waiting = threading.Event()
    real_page_locked = vendoring_model.page_locked

    @contextlib.contextmanager
    def observed_page_locked(locked):
        if locked == page_dir and threading.current_thread().name == "re-vendor":
            init_waiting.set()
        with real_page_locked(locked) as held:
            yield held

    monkeypatch.setattr(vendoring_model, "page_locked", observed_page_locked)
    errors = []

    def revendoring():
        try:
            vendoring_model.cmd_init(page_dir)
        except BaseException as error:  # noqa: BLE001 - carried to the assertion
            errors.append(error)

    with render_gate_model.preview_server(
        page_dir,
        structure_model.SourceDocument((page_dir / "index.html").read_text()),
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
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "</section>", registry["lf-board"]["x-example"] + "\n</section>"
        )
    )
    publish(page_dir)
    board = registry["lf-board"]
    board["x-state"]["move"]["detail"]["properties"]["rank"]["maxLength"] = 1
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-board": board}))
    action = json.dumps(
        {
            "kind": "action",
            "revision": 1,
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "rank": "0i"},
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
    _tasks_version(page_dir, "active")
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    task = registry["lf-task"]
    task.pop("x-state")
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
    local = element_declaration("lf-local-thread")
    (overlay / "registry.json").write_text(json.dumps({"lf-local-thread": local}))
    vendoring_model.cmd_init(page_dir, selected=(*PAGE_PACKAGES, "./.leaf"))
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
        lambda: conversation_model.cmd_reply(
            page_dir, "c1", "Pick one:", markup, for_event="c1"
        ),
    )

    assert "lf-local-thread" in refusal


def test_revendoring_cannot_turn_logged_thread_markup_into_a_settlement(
    page_dir,
):
    """Frozen thread markup keeps the admission rules of its vendored vocabulary."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "choose"},
    )
    markup = (
        '<lf-ask id="thread-choice-decision"><h3>Which option?</h3>'
        '<lf-options id="thread-choice" choose>'
        '<lf-option id="thread-a">A</lf-option>'
        "</lf-options></lf-ask>"
    )
    conversation_model.cmd_reply(page_dir, "c1", "Pick one:", markup, for_event="c1")

    registry = json.loads((page_dir / "registry.json").read_text())
    options = registry["lf-options"]
    options["x-state"]["decide"] = {
        "detail": {
            "type": "object",
            "properties": {"outcome": {"enum": ["keep"]}},
            "required": ["outcome"],
            "additionalProperties": False,
        },
        "unit": "widget",
    }
    option = registry["lf-option"]
    option["x-retired-when"] = "keep"
    overlay = page_dir.parent / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-options": options, "lf-option": option})
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "thread markup contract" in result.output
    assert "lf-options" in result.output


def test_check_refuses_a_malformed_registry(page_dir):
    (page_dir / "registry.json").write_text("{broken")
    result = check(page_dir)
    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_page_registry_composes_declarations_and_implementations_independently(
    page_dir,
):
    layer = registry_storage.load_registry(page_dir)
    package_widget = element_declaration("lf-local", upgrade=True)
    package_widget["properties"]["package-only"] = {"type": "string"}
    layer = {**layer, "lf-local": package_widget}
    page_widget = element_declaration("lf-local", upgrade=True)
    page_widget["properties"]["page-only"] = {"type": "string"}
    declarations = {
        "lf-local": page_widget,
        "lf-page-only": element_declaration("lf-page-only", upgrade=True),
        "$languages": {"paths": {"leaf": "javascript", "py": None}},
    }
    layer_before = deepcopy(layer)
    page_before = deepcopy(declarations)
    widget_paths = {
        *(f"widgets/{path.name}" for path in (page_dir / "widgets").glob("*.js")),
        "widgets/lf-local.js",
        "page/widgets/lf-page-only.js",
        "page/widgets/lf-tabs.js",
    }

    composed = registry_page.compose_page_registry(layer, declarations, widget_paths)

    assert composed.registry["lf-local"] == page_widget
    assert "package-only" not in composed.registry["lf-local"]["properties"]
    assert composed.declaration_sources["lf-local"] == "page"
    assert composed.widget_sources["lf-local"] == "widgets/lf-local.js"
    assert composed.declaration_sources["lf-tabs"] == "layer"
    assert composed.widget_sources["lf-tabs"] == "page/widgets/lf-tabs.js"
    assert composed.declaration_sources["lf-page-only"] == "page"
    assert composed.widget_sources["lf-page-only"] == "page/widgets/lf-page-only.js"
    assert composed.registry["$languages"]["paths"] == {
        **{
            key: value
            for key, value in layer["$languages"]["paths"].items()
            if key != "py"
        },
        "leaf": "javascript",
    }
    assert layer == layer_before and declarations == page_before


@pytest.mark.parametrize(
    ("declarations", "message"),
    [
        ("{broken", "invalid JSON"),
        ("[]", "registry must be a JSON object"),
        ('{"lf-local": null}', "registry declarations must be objects"),
        ('{"$layer": {"generation": "authored"}}', r"\$layer belongs"),
        (
            json.dumps(
                {"lf-local": {**element_declaration("lf-local"), "type": "wrong"}}
            ),
            "not a valid JSON Schema",
        ),
        (
            json.dumps(
                {
                    "lf-local": {
                        **element_declaration("lf-local"),
                        "x-example": '<lf-local id="bad" unknown="bad">Example</lf-local>',
                    }
                }
            ),
            "x-example is invalid",
        ),
        (
            json.dumps({"lf-local": element_declaration("lf-local", upgrade=True)}),
            "is upgraded but its module is missing",
        ),
    ],
)
def test_page_registry_rejects_invalid_authored_contracts(
    page_dir, declarations, message
):
    authored = page_dir / "page"
    (authored / "registry.json").write_text(declarations)

    with pytest.raises(registry_contract.RegistryError, match=message):
        registry_storage.read_page_registry(page_dir)


def test_page_registry_reads_candidate_changes_without_mutating_the_layer(page_dir):
    authored = page_dir / "page"
    source = authored / "registry.json"
    declaration = element_declaration("lf-local")
    source.write_text(json.dumps({"lf-local": declaration}))
    first = registry_storage.read_page_registry(page_dir)
    assert registry_storage.read_page_registry(page_dir) is first
    declaration["description"] = "The next authored declaration."
    source.write_text(json.dumps({"lf-local": declaration}))

    second = registry_storage.read_page_registry(page_dir)

    assert second.registry["lf-local"] == declaration
    assert first.registry["lf-local"]["description"] != declaration["description"]
    assert "lf-local" not in registry_storage.load_registry(page_dir)


def test_thread_markup_must_render_in_every_pinned_revision(page_dir):
    """A current conversation remains usable in every immutable document showing it."""
    publish(page_dir)
    authored = page_dir / "page"
    (authored / "registry.json").write_text(
        json.dumps({"lf-local": element_declaration("lf-local", upgrade=True)})
    )
    widgets = authored / "widgets"
    widgets.mkdir(exist_ok=True)
    (widgets / "lf-local.js").write_text(
        "export function upgrade(element) { element.textContent = 'Loaded'; }\n"
    )
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir, version=2)

    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "comment",
            str(page_dir),
            "--text",
            "A later widget",
            "--markup",
            '<lf-local id="later-widget"></lf-local>',
        ],
    )

    assert posted.exit_code == 1, posted.output
    assert "pinned revision r1 cannot render this thread markup" in posted.output
    assert "<lf-local>" in posted.output
    assert (
        "use vocabulary shared by the active registry and every pinned revision; "
        "otherwise ask with --text" in posted.output
    )
    assert not events_model.read_events(page_dir)[-1].get("markup")


def test_page_registry_cache_follows_layer_and_widget_files(page_dir):
    first = registry_storage.read_page_registry(page_dir)
    assert registry_storage.read_page_registry(page_dir) is first

    layer_path = page_dir / "registry.json"
    layer = json.loads(layer_path.read_text())
    layer["lf-options"]["description"] = "Re-vendored options."
    files_model.replace_files([(layer_path, json.dumps(layer).encode(), False)])
    revendored = registry_storage.read_page_registry(page_dir)
    assert revendored is not first
    assert revendored.registry["lf-options"]["description"] == "Re-vendored options."

    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(exist_ok=True)
    implementation = widgets / "lf-options.js"
    implementation.write_text("export function upgrade() {}\n")
    overlaid = registry_storage.read_page_registry(page_dir)
    assert overlaid is not revendored
    assert overlaid.widget_sources["lf-options"] == "page/widgets/lf-options.js"

    implementation.write_text("export function upgrade() { return true; }\n")
    changed = registry_storage.read_page_registry(page_dir)
    assert changed is not overlaid
    assert changed.widget_sources == overlaid.widget_sources


def test_page_registry_cache_does_not_outlive_a_page_at_the_same_path(tmp_path):
    page = tmp_path / "reused"
    runner = CliRunner()
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    first = registry_storage.read_page_registry(page)

    shutil.rmtree(page)
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    second = registry_storage.read_page_registry(page)

    assert second is not first
    assert (
        second.registry["$layer"]["generation"]
        != first.registry["$layer"]["generation"]
    )


def _stateful_page_declaration(page_dir, tag="lf-local"):
    declaration = element_declaration(tag, upgrade=True)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(exist_ok=True)
    (widgets / f"{tag}.js").write_text("export function upgrade() {}\n")
    declaration["properties"].update(
        {
            "restated": {"type": "boolean"},
            "value": {"type": "string"},
        }
    )
    state = {
        "detail": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        "unit": "widget",
        "record": {"kind": "value", "attr": "value", "value": "value"},
    }
    declaration["x-state"] = {"first": state}
    return declaration


def test_candidate_vocabulary_keeps_every_page_action_an_undo_can_expose(page_dir):
    """A superseded action can become the winner again if the later action is undone."""
    from leaf.projection import page_reading
    from leaf.revision_artifact import read_artifact

    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    source = PAGE.replace(
        "</section>",
        '<lf-local id="local-choice" value="author">Local</lf-local></section>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    first = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "first"},
        },
    )
    second = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "second"},
        },
    )
    events = events_model.read_events(page_dir)
    historical = read_artifact(page_dir, revision)
    after_undo = [
        *events,
        {
            "kind": "undo",
            "id": "undo-second",
            "author": "user",
            "undoes": second["id"],
        },
    ]
    projected = page_reading(
        structure_model.SourceDocument(source),
        after_undo,
        historical.registry,
        revision,
    )
    assert next(iter(projected.projection.desired.values()))[0]["id"] == first["id"]

    declaration["x-state"]["second"] = declaration["x-state"].pop("first")
    authored.write_text(json.dumps({"lf-local": declaration}))
    refused = revisioning_model.activate_source(page_dir)

    assert refused.error and "does not declare action verb 'first'" in refused.error
    assert refused.revision == revision and not refused.created


def test_candidate_vocabulary_leaves_removed_page_widgets_to_captured_history(page_dir):
    """A retracted action on a removed sender is interpreted only in its old revision."""
    from leaf.projection import page_reading
    from leaf.revision_artifact import read_artifact

    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    original = PAGE.replace(
        "</section>",
        '<lf-local id="local-choice" value="author">Local</lf-local></section>',
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    first_revision = files_model.latest_revision(page_dir)
    action = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": first_revision,
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    restated = original.replace('value="author"', 'value="author-next" restated')
    (page_dir / "index.html").write_text(restated)
    second = stamp_activation(page_dir)
    assert second.error is None and second.created
    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": second.revision,
            "text": "Retract the local choice.",
            "restated": ["local-choice"],
        },
    )

    authored.write_text("{}")
    (page_dir / "index.html").write_text(PAGE)
    events = events_model.read_events(page_dir)
    activated = revisioning_model.activate_source(page_dir)

    assert activated.error is None and activated.created
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code == 0, revendored.output
    historical = page_reading(
        structure_model.SourceDocument(original),
        events,
        read_artifact(page_dir, first_revision).registry,
        first_revision,
    )
    assert (
        historical.projection.desired["local-choice", "local-choice", "first"][0]["id"]
        == action["id"]
    )


def test_revendoring_checks_the_effective_page_owned_vocabulary(page_dir):
    """An unchanged page declaration remains part of the candidate after re-vendoring."""
    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir)
    authored.write_text(json.dumps({"lf-local": declaration}))
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            '<lf-local id="local-choice" value="author">Local</lf-local></section>',
        )
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "local-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )

    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert revendored.exit_code == 0, revendored.output


def test_candidate_vocabulary_preserves_commands_in_frozen_thread_markup(page_dir):
    """A thread widget keeps the contract under which its user command was admitted."""
    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir, "lf-thread-local")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "Choose."},
    )
    conversation_model.cmd_reply(
        page_dir,
        "c1",
        "Use this control.",
        '<lf-thread-local id="thread-choice" value="author">Local</lf-thread-local>',
        for_event="c1",
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "thread-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    declaration["x-state"]["second"] = declaration["x-state"].pop("first")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))

    refused = revisioning_model.activate_source(page_dir)

    assert refused.error and "does not declare action verb 'first'" in refused.error
    assert refused.revision == revision and not refused.created


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
                    "records": {"items": "rows", "key": "id", "deferred": "id"},
                }
            },
            "records must name distinct",
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
    """Clearing a replaceable value does not erase the meaning a stamped version
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


def _page_owned_deferred_source(page_dir):
    schema = {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "patch": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["key", "patch", "body"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["files"],
        "additionalProperties": False,
    }
    contract = {
        "description": "Page-owned file payloads.",
        "schema": schema,
        "records": {"items": "files", "key": "key", "deferred": "patch"},
    }
    widget = element_declaration("lf-local-data")
    widget["properties"]["source"] = {
        "type": "string",
        "pattern": "^[a-z][a-z0-9-]*$",
    }
    widget["required"].append("source")
    widget["x-data"] = {"document": {"contract": "local-files", "source": "source"}}
    widget["x-example"] = (
        '<lf-local-data id="example-local-data" source="example"></lf-local-data>'
    )
    authored = page_dir / "page" / "registry.json"
    authored.write_text(
        json.dumps(
            {
                "$data": {"contracts": {"local-files": contract}},
                "lf-local-data": widget,
            }
        )
    )
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</section>",
            '<lf-local-data id="local-data" source="files"></lf-local-data></section>',
        )
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.created
    data_model.cmd_data_set(
        page_dir,
        "files",
        {"files": [{"key": "app.py", "patch": "old", "body": "new"}]},
    )
    return authored


def test_page_owned_data_contract_meaning_is_fixed_for_the_source_lifetime(page_dir):
    """A same-named contract cannot redirect old readers to a different field."""
    authored = _page_owned_deferred_source(page_dir)
    declarations = json.loads(authored.read_text())
    declarations["$data"]["contracts"]["local-files"]["records"]["deferred"] = "body"
    authored.write_text(json.dumps(declarations))

    activation = revisioning_model.activate_source(page_dir)
    assert "schema or record declaration changes" in activation.error
    with pytest.raises(data_model.DataError, match="schema or record declaration"):
        data_model.cmd_data_set(
            page_dir,
            "files",
            {"files": [{"key": "app.py", "patch": "next", "body": "other"}]},
        )
    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert revendored.exit_code != 0
    assert "schema or record declaration" in revendored.output


def test_page_owned_data_contract_description_can_improve(page_dir):
    authored = _page_owned_deferred_source(page_dir)
    declarations = json.loads(authored.read_text())
    declarations["$data"]["contracts"]["local-files"]["description"] = (
        "A clearer description of the same file payloads."
    )
    authored.write_text(json.dumps(declarations))

    activation = revisioning_model.activate_source(page_dir)

    assert activation.error is None and activation.created


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (None, "registry declarations must be objects"),
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
    """A verb carries only the detail keys it declares, so every reader of a detail
    field reads a declaration rather than whatever a client chose to send."""
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["x-state"]["decide"]["detail"]["additionalProperties"]
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


def test_the_resolves_attribute_belongs_to_a_widget_with_a_local_ask(page_dir):
    """Admission reads `resolves` off the widget whose Ask an action answers, so the
    name on a widget that asks nothing declares a thread nothing would ever close."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-board"]["properties"]["resolves"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "attribute `resolves`, a reserved name" in result.output


def test_containment_reads_the_same_with_a_vocabulary_and_without_one(page_dir):
    """The two halves of a `spoken` reading come from different places. Words are
    the vocabulary's word — fences, x-says, chrome — but where an element sits is
    recorded off the tag stack before anything asks the registry what it shows.
    That is the whole of what liveness asks a page, and it is why the readings
    that may not raise on the registry gate need give nothing up.

    The words are the control: they must differ, or `spoken({})` would be the
    whole reading and the distinction this rests on would not exist."""
    html = (page_dir / "index.html").read_text(encoding="utf-8")
    document = structure_model.SourceDocument(html)
    registry = registry_storage.require_registry(page_dir)
    full = passages_model.spoken(document, registry)
    assert passages_model.enclosing_ids(document) == passages_model.enclosing_of(full)
    bare = passages_model.spoken(document, {})
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
    document = structure_model.SourceDocument(html)
    events_model.append_event(page_dir, dict(COMMENT))
    events_model.append_event(page_dir, dict(ACCEPT))
    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "reworded the poll interval",
            "restated": ["c1"],
        },
    )
    spk = passages_model.spoken(document, registry_storage.require_registry(page_dir))
    assert "sug-a" in spk["c1"].within  # the namesake really is inside the widget
    folds = [passages_model.enclosing_of(spk), passages_model.enclosing_ids(document)]
    events = events_model.read_events(page_dir)
    for within in folds:
        assert event_folds_model.build_threads(events, within)["c1"]["resolved"][
            "detail"
        ] == {"outcome": "accept"}

    events_model.append_event(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
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
    write markup its own element declaration refuses — every rewrite unpublishable."""
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-suggestion"]["properties"]["restated"]
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code != 0
    assert "restated" in result.output


def test_space_capacity_is_independent_of_the_widgets_internal_layout(page_dir):
    """A capacity declaration says how much room core grants. It does not constrain the
    package's internal layout, including whether the widget also renders an attribute."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-board"]["properties"]["caption"] = {"type": "string"}
    registry["lf-board"]["x-says"] = {"caption": "before"}
    registry["lf-board"]["x-space"] = "available"
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code == 0, result.output


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
    (page_dir / "index.html").write_text(
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
    version = page_dir / "index.html"
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
        ("x-required-members", []),
        ("x-content", "words"),
        ("x-owners", []),
        # Each of these names attributes, so an empty one declares nothing while
        # reading as a declaration.
        ("x-refers", {}),
        ("x-lines", []),
        ("x-paints", []),
        ("x-says", []),
        ("x-state", []),
        ("x-thread-surface", False),
        ("x-upgrade", "yes"),
        ("x-verbatim", "false"),
        ("x-work", []),
        ("x-work", {"seat": "content"}),
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
            lambda registry: registry["lf-chip"].update({"x-work": True}),
            "declares x-work but is inline",
        ),
        (
            lambda registry: registry["lf-diagram"].update({"x-work": True}),
            "declares x-work but x-content is data",
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


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            "unknown-child",
            "x-required-members names unknown member declaration <lf-missing>",
        ),
        ("wrong-owner", "does not name it in x-owners"),
        ("optional-role", "must name a required, non-empty string enum"),
        ("open-role", "must name a required, non-empty string enum"),
        ("markup-owner", "x-required-members requires x-content: members"),
    ],
)
def test_one_each_child_declarations_are_checked_whole(page_dir, mutation, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    option = registry["lf-option"]
    option["properties"]["role"] = {"type": "string", "enum": ["first", "second"]}
    option["required"].append("role")
    registry["lf-options"]["x-required-members"] = {"lf-option": {"one-each": "role"}}

    if mutation == "unknown-child":
        registry["lf-options"]["x-required-members"] = {
            "lf-missing": {"one-each": "role"}
        }
    elif mutation == "wrong-owner":
        option["x-owners"] = ["lf-board"]
    elif mutation == "optional-role":
        option["required"].remove("role")
    elif mutation == "open-role":
        option["properties"]["role"] = {"type": "string"}
    else:
        registry["lf-options"]["x-content"] = "markup"
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        # A report moves declared state only, never body words — the schema is
        # where the paint-only constraint lives, so a body record never parses.
        (_report_body_record, "registry extensions are invalid"),
        # Nor a part's place: the stamped version owns where a unit stands, and a
        # rank is read between the neighbours a widget shows the user.
        (_report_position_record, "registry extensions are invalid"),
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
        # Reports replay through renderState, so the widget must upgrade.
        (_report_without_upgrade, "declares x-state"),
        # Only a report carries update prose.
        (_user_verb_update, "registry extensions are invalid"),
        # The user answers their own Ask; the agent's news never does.
        (_agent_verb_answers, "which are not x-state verbs the user writes"),
        (_body_record_with_prose, "x-content must be data"),
        (_body_record_with_nested_widget, "admits nested widgets"),
    ],
)
def test_an_agent_verb_declaration_is_checked_whole(page_dir, mutate, message):
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
    assert f"invalid element declaration names ['{tag}']" in result.output
    assert "an element name is `lf-` followed by" in result.output


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


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing-member", "registry extensions are invalid"),
        ("unknown-child", "creates unknown child <lf-missing>"),
        ("optional-words", "detail must be exactly the required element id"),
        ("extra-field", "detail must be exactly the required element id"),
        ("widget-unit", "fold unit must name the detail field"),
        ("wrong-owner", "x-owners does not admit the sender"),
        ("non-markup", "must declare x-content markup"),
        ("extra-required", "must require id and no other authored attributes"),
        ("wrong-id", "required id must use the canonical element-id schema"),
        ("report-creates", "registry extensions are invalid"),
    ],
)
def test_generated_child_declaration_closes_its_boundary(page_dir, mutation, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    add = registry["lf-options"]["x-state"]["add"]
    option = registry["lf-option"]
    if mutation == "missing-member":
        del add["creates"]["child"]
    elif mutation == "unknown-child":
        add["creates"]["child"] = "lf-missing"
    elif mutation == "optional-words":
        add["detail"]["required"] = ["option"]
    elif mutation == "extra-field":
        add["detail"]["properties"]["note"] = {"type": "string"}
    elif mutation == "widget-unit":
        add["unit"] = "widget"
    elif mutation == "wrong-owner":
        option["x-owners"] = ["lf-board"]
    elif mutation == "non-markup":
        option["x-content"] = "members"
    elif mutation == "extra-required":
        option["required"].append("for")
    elif mutation == "wrong-id":
        option["properties"]["id"]["pattern"] = "^option-.+$"
    elif mutation == "report-creates":
        registry["lf-agent"]["x-state"]["state"]["creates"] = {
            "child": "lf-option",
            "words": "doing",
        }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


def test_action_detail_schemas_match_the_post_object_contract(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-state"]["decide"]["detail"] = {"type": "string"}
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
            "to `target`, which is written by x-state",
        ),
        ("optional-id", "x-request instances are addressable"),
        ("no-upgrade", "declares x-request"),
        ("unknown-offer", "x-request offers unknown member <lf-unknown>"),
        ("wrong-owner", "does not name it in x-owners"),
        ("freeform-offer", "must be a non-empty string enum"),
        (
            "optional-offer-attribute",
            "offer <lf-operation> attribute `verb` must be required",
        ),
        ("unknown-offered-verb", "names undeclared verbs ['explode']"),
        ("unoffered-verb", "verbs ['restart'] cannot be offered"),
        ("self-framing-decision", "declares both x-ask-surface and x-request.ask"),
        ("dual-decision-source", "declares both x-request.ask and x-awaits"),
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
        operations["x-state"] = {
            "retarget": {
                "writer": "agent",
                "detail": {
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": ["target"],
                    "additionalProperties": False,
                },
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
    elif mutation == "wrong-owner":
        registry["lf-operation"]["x-owners"] = ["lf-command"]
    elif mutation == "freeform-offer":
        registry["lf-operation"]["properties"]["verb"] = {"type": "string"}
    elif mutation == "optional-offer-attribute":
        registry["lf-operation"]["required"].remove("verb")
    elif mutation == "unknown-offered-verb":
        registry["lf-operation"]["properties"]["verb"]["enum"].append("explode")
    elif mutation == "unoffered-verb":
        registry["lf-operation"]["properties"]["verb"]["enum"].remove("restart")
    elif mutation == "self-framing-decision":
        operations["x-ask-surface"] = True
        operations["x-content"] = "markup"
    elif mutation == "dual-decision-source":
        operations["x-awaits"] = {"answered": {"restart": {}}}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


@pytest.mark.parametrize("writer", [{}, {"writer": "agent"}])
def test_a_request_offer_attribute_is_authored_static_state(page_dir, writer):
    registry = json.loads((page_dir / "registry.json").read_text())
    operation = registry["lf-operation"]
    operation["properties"].update(
        {
            "id": deepcopy(registry["lf-operations"]["properties"]["id"]),
            "restated": {"type": "boolean"},
            "overruled": {"type": "boolean"},
        }
    )
    operation["required"].append("id")
    operation["x-upgrade"] = True
    operation["x-state"] = {
        "change-offer": {
            **writer,
            "detail": {
                "type": "object",
                "properties": {"verb": deepcopy(operation["properties"]["verb"])},
                "required": ["verb"],
                "additionalProperties": False,
            },
            "unit": "widget",
            "record": {"kind": "value", "attr": "verb", "value": "verb"},
        }
    }

    with pytest.raises(
        registry_contract.RegistryError,
        match=(
            r"<lf-operations> x-request offer <lf-operation> attribute `verb` "
            r"is written by x-state"
        ),
    ):
        registry_validation.validate_registry(registry, "test registry")


@pytest.mark.parametrize("subschema", [True, False])
def test_state_user_fields_reject_boolean_subschemas(page_dir, subschema):
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
def test_record_values_have_the_type_the_user_uses(page_dir, tag, verb, field, wanted):
    registry = json.loads((page_dir / "registry.json").read_text())
    spec = registry[tag]["x-state"][verb]
    spec["detail"]["properties"][field] = {"type": "integer"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> x-state verb `{verb}` record value `{field}`" in result.output
    assert wanted in result.output


def test_recorded_actions_can_require_fields_beyond_the_record(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    detail = registry["lf-options"]["x-state"]["choose"]["detail"]
    detail["properties"]["animate"] = {"type": "boolean"}
    detail["required"].append("animate")
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_value_records_use_the_string_type_html_attributes_carry(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    numeric = {"type": "integer", "minimum": 0}
    registry["lf-agent"]["properties"]["state"] = numeric
    registry["lf-agent"]["x-state"]["state"]["detail"]["properties"]["state"] = numeric
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
    spec = registry["lf-agent"]["x-state"]["state"]
    assert spec["update"] == "doing"
    change(spec)
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert wanted in result.output


@pytest.mark.parametrize(
    ("tag", "verb", "field"),
    [
        ("lf-suggestion", "decide", "unit"),
        ("lf-task", "status", "unit"),
    ],
)
def test_every_fold_verb_declares_its_coordinate(page_dir, tag, verb, field):
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry[tag]["x-state"][verb][field]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert f"<{tag}> registry extensions are invalid" in result.output
    assert field in result.output


@pytest.mark.parametrize(
    ("tag", "verb", "slot"),
    [
        ("lf-draft", "edit", "body"),
        ("lf-board", "move", "position"),
        ("lf-task", "status", "value `status`"),
        ("lf-options", "choose", "attribute `chosen`"),
    ],
)
def test_distinct_verbs_cannot_claim_one_physical_record_slot(
    page_dir, tag, verb, slot
):
    registry = json.loads((page_dir / "registry.json").read_text())
    declared = registry[tag]["x-state"][verb]
    parallel = json.loads(json.dumps(declared))
    registry[tag]["x-state"]["parallel"] = parallel
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert (
        f"<{tag}> x-state verbs `parallel` and `{verb}` claim the "
        f"same physical record slot (unit `{parallel['unit']}`, {slot}); distinct "
        "verbs must record independently" in result.output
    )


def test_physical_record_slots_remain_local_to_the_coordinate(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())

    # A different host attribute is a different value slot on the same unit.
    task = registry["lf-task"]
    owner = json.loads(json.dumps(task["x-state"]["status"]))
    owner["detail"]["properties"] = {"owner": {"type": "string"}}
    owner["detail"]["required"] = ["owner"]
    owner["record"] = {"kind": "value", "attr": "owner", "value": "owner"}
    task["properties"]["owner"] = {"type": "string"}
    task.setdefault("required", []).append("owner")
    task["x-state"]["owner"] = owner
    registry["lf-tasks"]["x-example"] = re.sub(
        r"<lf-task\b(?![^>]*\bowner=)",
        '<lf-task owner="test"',
        registry["lf-tasks"]["x-example"],
    )

    # Placement is one slot only for a given declared unit.
    board = registry["lf-board"]
    arrange = json.loads(json.dumps(board["x-state"]["move"]))
    arrange["unit"] = "to"
    arrange["detail"]["properties"].pop("card")
    arrange["detail"]["required"].remove("card")
    board["x-state"]["arrange"] = arrange
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 0, result.output


def test_independent_state_does_not_reopen_an_answer_even_after_retirement(
    server, page_dir
):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-state"]["label"] = {
        "detail": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "unit": "widget",
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))
    snippet = '<lf-suggestion id="proposal" resolves="c1"><lf-new><p id="proposed">Ship after validation.</p></lf-new></lf-suggestion>'
    source = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + snippet)
    (page_dir / "index.html").write_text(source)
    events_model.append_event(page_dir, dict(COMMENT))
    publish(page_dir)
    from leaf.files import latest_revision

    revision = latest_revision(page_dir)

    def send(action, detail, attempt):
        command = {
            "kind": "action",
            "revision": revision,
            "widget": "proposal",
            "action": action,
            "detail": detail,
            "attempt": attempt,
        }
        status, body = fetch(f"{server}/api/event", data=json.dumps(command).encode())
        assert status == 200, body
        return json.loads(body)["state"]["events"][-1]

    accepted = send("decide", {"outcome": "accept"}, "accepted-proposal")
    labeled = send("label", {"text": "proposed"}, "labelled-proposal")
    assert accepted["meaning"]["answer"] == "c1"
    assert "answer" not in labeled["meaning"]
    assert labeled["meaning"]["depends"] == ["proposal"]
    # Literal text matching an id is not a dependency; ancestry remains live for
    # declared identities, tested in the named-dependency contrast below.
    assert not event_folds_model.action_retracted(
        labeled, {"proposed": revision + 1}, {"proposed": ("proposal", "proposed")}
    )
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(source)),
    )
    assert result["c1"]["resolved"]["id"] == accepted["id"]
    retired = source.replace(snippet, '<p id="proposed">Ship after validation.</p>')
    (page_dir / "index.html").write_text(retired)
    publish(page_dir, 2)
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(retired)),
    )
    assert result["c1"]["resolved"]["id"] == accepted["id"]
    # The immutable old command document still admits a different answer; a reject
    # declines the fix, so it answers the Ask and reopens the thread it was for.
    rejected = send("decide", {"outcome": "reject"}, "rejected-proposal")
    assert rejected["meaning"]["answer"] is None
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(retired)),
    )
    assert result["c1"]["resolved"] is None


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
        ("lf-diff", "x-thread-surface", True),
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


def test_retirement_requires_an_owner(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    del registry["lf-old"]["x-owners"]
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-old> registry extensions are invalid" in result.output


def test_check_refuses_a_retirement_outcome_its_parent_does_not_decide(page_dir):
    """A retirement outcome is a cross-entry reference, not a free-form label.

    If it names no outcome of the parent widget's deciding verb, the browser's selector can never
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
    assert "<lf-suggestion> declares no deciding x-state verb" in result.output


@pytest.mark.parametrize("fault", ["per-part", "agent-written"])
def test_retirement_verbs_fold_by_the_parent_widget(page_dir, fault):
    """The deciding verb is the user's whole-widget decision: a verb folding per part,
    or one the agent writes, cannot say which members leave the page."""
    registry = json.loads((page_dir / "registry.json").read_text())
    suggestion = registry["lf-suggestion"]
    decide = suggestion["x-state"]["decide"]
    if fault == "per-part":
        decide["detail"]["properties"]["part"] = {"type": "string"}
        decide["detail"]["required"].append("part")
        decide["unit"] = "part"
    else:
        # An agent verb never answers an Ask, so the suggestion stops asking one.
        suggestion.pop("x-awaits")
        suggestion["properties"].pop("resolves")
        decide["writer"] = "agent"
        decide["record"] = {"kind": "value", "attr": "outcome", "value": "outcome"}
        suggestion["properties"]["outcome"] = decide["detail"]["properties"]["outcome"]
        suggestion["properties"]["overruled"] = {"type": "boolean"}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert "<lf-suggestion> x-state verb `decide` declares detail field `outcome`" in (
        result.output
    )
    assert "the deciding verb folds by widget" in result.output


def test_a_layers_own_outcome_licenses_the_ids_it_retires(trial_page):
    """The version that honors a decision drops what the outcome retired, and
    the licensing that lets it is written in terms of the registry's owner/member
    relation — so a family the layer never heard of is licensed the day it is
    declared. It used to be written in terms of the suggestion's own slots, and
    a family like this one got every part of the loop except this: the door
    refused the declaration outright rather than let the honoring version fail
    here with "ids dropped"."""
    (trial_page / "index.html").write_text(
        trial_version(ADOPTED, TRIAL_LOG, PILOT_PURGE)
    )

    refused = check(trial_page)
    assert refused.exit_code == 1
    assert "cache-daily" in refused.output and "cache-now" in refused.output
    # The wrapper with them: this version keeps the proposal as settled prose, so
    # the withdrawal that would have licensed the wrapper isn't one.
    assert "trial-cache" in refused.output

    decide(trial_page, "adopt", widget="trial-cache")

    honored = stamp(trial_page, "adopted")
    assert honored.exit_code == 0, honored.output
    assert live_versions(trial_page) == [1, 2]


def test_a_layers_own_widget_withdraws_as_its_entry_declares(trial_page):
    """Nothing was decided, so the author may take the question back — and
    `x-withdrawn-as` is what says which half of it was theirs to take. The other
    half is the page's own words, which only the user's own `adopt` consents
    to losing, so a version dropping that is refused while the same version's
    withdrawal stands."""
    (trial_page / "index.html").write_text(
        trial_version(TRIAL_CACHE, SHELVED, PILOT_PURGE)
    )
    withdrawn = check(trial_page)
    assert withdrawn.exit_code == 0, withdrawn.output

    # v2 published nothing, so v3 stands against v1 like v2 did.
    (trial_page / "index.html").write_text(trial_version(TRIAL_CACHE, PILOT_PURGE))
    result = check(trial_page)
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
    taking its question back would mean keeps every id until the user answers
    it. <lf-proposed> is the same slot under the same verb in both families, so
    what differs is the pair — which is the shape the licensing reads, and the
    reason the declaration sits on the widget that holds the slot rather than on
    the slot."""
    (trial_page / "index.html").write_text(trial_version(TRIAL_CACHE, TRIAL_LOG))

    refused = check(trial_page)
    assert refused.exit_code == 1
    assert "pilot-purge" in refused.output and "purge-weekly" in refused.output

    decide(trial_page, "shelve", widget="pilot-purge")

    answered = check(trial_page)
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
            "lf-options",
            "x-awaits",
            {"answered": {"answer": {"when": {"batch": [True]}}}},
            "names undeclared attribute `batch`",
        ),
        (
            "lf-options",
            "x-awaits",
            {"answered": {"submit": {}}},
            "which are not x-state verbs the user writes",
        ),
        (
            "lf-suggestion",
            "x-awaits",
            {"answered": {"decide": {}}, "all": "approve"},
            "blanket answer `approve` is not an outcome",
        ),
    ],
)
def test_check_refuses_a_predicate_no_page_could_carry(
    page_dir, tag, key, declaration, message
):
    """A predicate naming a value the widget cannot hold applies to nothing silently.

    The widget is simply absent from every consumer, exactly as if the feature had
    never been wired up.
    Same for an answering verb the widget does not declare, which would hold its
    Ask open for a state no gesture writes."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry[tag][key] = declaration
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)
    assert result.exit_code != 0
    assert f"<{tag}> {key}" in result.output and message in result.output


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ({}, "local Ask declares no `answered` condition"),
    ],
)
def test_a_local_ask_declares_its_answered_condition(page_dir, declaration, message):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-awaits"] = declaration
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert message in result.output


def test_a_part_scoped_answering_verb_needs_an_empty_condition(page_dir):
    """A part record does not answer its whole Ask merely by standing."""
    registry = json.loads((page_dir / "registry.json").read_text())
    swipe = json.loads(
        (schema_model.BUNDLED_PACKAGES / "swipe" / "registry.json").read_text()
    )
    registry.update(swipe)
    registry["lf-swipe-deck"]["x-awaits"]["answered"]["swipe"].pop("empty")

    with pytest.raises(
        registry_contract.RegistryError,
        match="folds on a part rather than the widget",
    ):
        registry_validation.validate_registry(registry, "test registry")


def test_a_position_record_places_a_part_and_never_the_widget(page_dir):
    """A rank lies between the unit's neighbours, which only the widget holding the
    container can read, so a widget cannot record its own position."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["move"] = {
        "detail": {
            "type": "object",
            "properties": {"to": {"type": "string"}, "rank": {"type": "string"}},
            "required": ["to", "rank"],
            "additionalProperties": False,
        },
        "unit": "widget",
        "record": {
            "kind": "position",
            "within": "lf-column",
            "value": "to",
            "rank": "rank",
        },
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code != 0
    assert "its unit must be the part it places, not the widget" in result.output


def _value_verb(attr):
    """A widget-unit verb that records one attribute's value."""
    return {
        "detail": {
            "type": "object",
            "properties": {attr: {"type": "string"}},
            "required": [attr],
            "additionalProperties": False,
        },
        "unit": "widget",
        "record": {"kind": "value", "attr": attr, "value": attr},
    }


@pytest.mark.parametrize(
    ("arrangement", "refusal"),
    [
        ("own-verb", None),
        ("recording-column", "'card' is not owned by action widget 'board'"),
    ],
)
def test_the_widget_that_records_a_parts_position_is_the_one_that_places_it(
    server, page_dir, arrangement, refusal
):
    """A card has one place and the nearest recording widget above it records it. A
    verb the card records of its own is a coordinate of the card's, so the board still
    moves it. A column that records stands between the board and the card."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-column"]["properties"]["tint"] = {"type": "string"}
    card_verbs = {"flag": _value_verb("flag")}
    recorders = {"lf-card": ("flag", card_verbs)}
    if arrangement == "recording-column":
        recorders["lf-column"] = ("tint", {"tint": _value_verb("tint")})
    for tag, (attr, verbs) in recorders.items():
        entry = registry[tag]
        entry["properties"] |= {
            attr: {"type": "string"},
            "restated": {"type": "boolean"},
        }
        entry["required"] = sorted({*entry["required"], attr})
        entry["x-state"] = verbs
        entry["x-upgrade"] = True
        (page_dir / "widgets" / f"{tag}.js").write_text("export default class {}\n")
    (page_dir / "registry.json").write_text(json.dumps(registry))
    result = check(page_dir)
    assert result.exit_code == 0, result.output

    board = (
        '<lf-board id="board"><lf-column id="todo" label="To do" tint="plain">'
        '<lf-card id="card" flag="no">Card</lf-card></lf-column>'
        '<lf-column id="done" label="Done" tint="plain"></lf-column></lf-board>'
    )
    html = re.sub(r"<main>.*?</main>", f"<main>{board}</main>", PAGE, flags=re.DOTALL)
    (page_dir / "index.html").write_text(html)
    publish(page_dir)
    revision = events_model.read_events(page_dir)[-1]["revision"]

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": revision,
                "widget": "board",
                "action": "move",
                "detail": {"card": "card", "to": "done", "rank": "0i"},
            }
        ).encode(),
    )
    if refusal is None:
        assert status == 200, body
    else:
        assert status == 400, body
        assert refusal in json.loads(body)["error"]


@pytest.mark.parametrize(
    ("tag", "key", "value", "missing"),
    [
        (
            "lf-chronology-entry",
            "x-says",
            {"at": "before", "colour": "after"},
            "colour",
        ),
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

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    merged = json.loads((page_dir / "registry.json").read_text())[section]
    shipped = json.loads((schema_model.ASSETS / "registry.json").read_text())[section]
    assert merged == shipped


def test_a_layer_restates_one_kind_s_handling_and_inherits_the_rest(page_dir, tmp_path):
    """`$events.handling` merges by kind like `$reactions.tokens`: a project layer
    replaces one kind's clauses, deletes one with null, and inherits every other."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "$events": {
                    "handling": {
                        "comment": [{"text": "Reply in French."}],
                        "reply": None,
                    }
                }
            }
        )
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    merged = json.loads((page_dir / "registry.json").read_text())["$events"]["handling"]
    shipped = json.loads((schema_model.ASSETS / "registry.json").read_text())[
        "$events"
    ]["handling"]
    assert merged["comment"] == [{"text": "Reply in French."}]
    assert "reply" not in merged
    assert merged["resolve"] == shipped["resolve"]


@pytest.mark.parametrize(
    "handling",
    [
        {"bogus-kind": [{"text": "A clause for no kind."}]},
        {"comment": []},
        {"comment": "Reply in French."},
        {"comment": [{"text": ""}]},
        {"comment": [{"text": "Reply in French.", "tone": "warm"}]},
        {"comment": [{"text": "Reply in French.", "when": {"type": 5}}]},
        "Reply in French.",
        None,
    ],
)
def test_init_refuses_handling_that_a_batch_could_not_carry(
    page_dir, tmp_path, handling
):
    """Every delivered event reads `$events.handling` directly, so the door holds a
    layer to declared kinds and well-formed clauses rather than passing junk to the
    agent."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"$events": {"handling": handling}})
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code != 0
    assert (
        "$events.handling must map declared kinds to a non-empty list of clauses"
        in result.output
    )


HANDLING_WALKTHROUGH = """\
What the agent is told when a user acts on a page
===================================================

A test records this file; nobody writes it by hand. The lines starting with `#`
explain it, and everything else is the recorded data. The walkthrough below is
one real run: the test serves a page, posts a comment to it the way the browser
does, and runs `leaf wait`. Only the id, the times and the page's path are
pinned, so the file stays the same from run to run.

How this text reaches the agent, by example
-------------------------------------------

1. The page's `plan` section reads "The nightly backfill moves to Tuesdays so it
   stops colliding with the report run." The user selects "moves to Tuesdays"
   and comments "why here?". The page's JavaScript sends this to the page's
   server as POST /api/event:

@POSTED@

2. The server checks the comment against the page, adds who wrote it (`author`),
   when (`ts`) and an `id`, and appends it to the page's event log, events.jsonl,
   as this one line:

@LOGGED@

3. Earlier, the agent started `leaf wait` in the background and went idle. The
   agent does nothing in this step: `leaf wait`, a leaf process, notices the new
   line and builds a delivery for it. The comment is owed a reply, which the
   delivery records as its `answer` (step 4): a `reply` for `leaf reply` here,
   where the Codex App Server route would record a `turn`, which the turn's own
   messages write. For the instructions, `leaf wait` reads the clauses under
   `$events.handling.comment` in the page's copy of registry.json, then those
   under `$events.answering.reply`, the answer it owes. Each clause has a `text`
   and may have a `when`, a JSON Schema that must hold for the clause to apply.
   It is tested against the log line together with its `answer` and its
   `conversation`'s entry in the delivery's `conversations` (step 4). There are
   @COUNT@; here they all are, with whether the comment satisfies each `when`:

@CLAUSES@

4. `leaf wait` prints the delivery as JSON and exits. The agent's host hands that
   output to the agent as the result of the background command, which wakes it.
   The delivery's event is the log line from step 2 less @DROPPED@, the
   browser's retry key, and with these fields added:
   @ADDED@.
   The batch's `handling` maps clause ids to their text, each distinct text
   appearing once. The event's `handling` names its applicable clauses in order.
   The envelope's `acknowledge` says once, for the whole delivery, how the agent
   confirms it. The whole output, indented here (leaf prints it on one line):

@DELIVERY@

5. The agent follows `acknowledge`: it starts `leaf wait --ack <delivery-id>` to
   confirm receipt and wait for the next one. It follows `handling`: it replies in
   the thread with `leaf reply` and edits the page if warranted.

What this file records
----------------------

Step 3, for one example of every case, using the clauses in
skills/leaf/assets/registry.json (the file `leaf page init` copies into a page).
Each top-level key below names a case and holds:

  event:  the input: a log line's `kind`, the kind of answer its delivery
          says it owes (`answer`), and the fields some `when` reads, its
          `conversation`'s among them, and nothing else. A field no `when`
          names, such as a comment's `anchor` or `text`, cannot change what
          the agent is told, so it is left out; the test checks both halves of
          that.
  told:   the output, the clauses that apply to that line, in order. Each
          clause has a `text` and may have a `when`:
  when:   the clause's `when`, exactly as registry.json writes it: a JSON
          Schema the log line must satisfy for the clause to apply. A clause
          with no `when` always applies, and has no `when` key here either.
  text:   the clause's text.

The walkthrough's comment is the first case. No `when` reads any field of its
log line from step 2 except `kind`, so the case is that line cut down to `kind`,
the reply it owes and its new conversation's missing title, and it gets the
clauses marked "applies" in step 3. It is recorded as:

@RECORDED@

After changing a clause, re-record this file and review the diff:

  uv run pytest --regtest-reset -n0 tests/test_interact_contract.py::test_each_case_of_an_event_is_told_what_the_snapshot_shows"""

WALKTHROUGH_PAGE = """<!doctype html>
<html lang="en">
<head>
<title>Backfill</title>
</head>
<body>
<main>
<section id="plan">
  <h2>Plan</h2>
  <p>The nightly backfill moves to Tuesdays so it stops colliding with the report run.</p>
</section>
</main>
</body>
</html>
"""


def test_each_case_of_an_event_is_told_what_the_snapshot_shows(
    snapshot, page_dir, server, capsys
):
    """The snapshot is the table a developer reads to see what the agent is told for
    each case: every kind, and every condition a clause's `when` names, resolved
    through the shipped layer clause by clause, each under the condition that let it
    in. A wording or condition change shows up as a diff per case. The assertions
    keep the table whole: every declared kind has a case, and every clause reaches
    at least one case, so no `when` is dead. Its header walks one real comment from
    the HTTP route through `leaf wait`, and holds that the clauses it lists as
    applying are exactly the `handling` the delivery carries."""
    registry = json.loads((schema_model.ASSETS / "registry.json").read_text())
    # Each case holds its `kind` and the fields some `when` reads, and nothing else:
    # a field no `when` names cannot change what the agent is told.
    on_page = {"scope": "page"}

    def owes(kind):
        return {"answer": {"kind": kind}}

    untitled = {"conversation": {"title": None}}
    titled = {"conversation": {"title": "Tuesday backfill"}}
    cases = {
        "comment": {"kind": "comment", **untitled, **owes("reply")},
        "comment over App Server": {"kind": "comment", **untitled, **owes("turn")},
        "comment with a drawing": {
            "kind": "comment",
            "drawing": {"format": "leaf-drawing/2", "strokes": [[[0, 0], [9, 9]]]},
            **owes("reply"),
        },
        "comment with a pasted image": {
            "kind": "comment",
            "text": "this looks off ![screenshot](/media/0a1b2c.png)",
            **owes("reply"),
        },
        "comment a newer message answers through": {"kind": "comment"},
        "suggestion": {"kind": "comment", "suggestion": True, **owes("reply")},
        "design comment": {"kind": "comment", "about": "design", **owes("reply")},
        "reaction on the page": {"kind": "comment", "token": "+1"},
        "reply": {"kind": "reply", **titled, **owes("reply")},
        "reply in an untitled thread": {
            "kind": "reply",
            **untitled,
            **owes("reply"),
        },
        "reply with a pasted image": {
            "kind": "reply",
            "text": "like this ![sketch](/media/3d4e5f.png)",
            **owes("reply"),
        },
        "reply in a long thread": {
            "kind": "reply",
            "conversation": {
                "title": "Tuesday backfill",
                "summary_hint": {"from": "m1", "through": "m8"},
            },
            **owes("reply"),
        },
        "reaction on a message": {"kind": "reply", "token": "+1"},
        "pick on the page": {"kind": "action", "meaning": on_page, **owes("markup")},
        "option the user added": {
            "kind": "action",
            "action": "add",
            "meaning": on_page,
        },
        "pick before Done": {"kind": "action", "meaning": on_page},
        "decided suggestion": {
            "kind": "action",
            "action": "decide",
            "meaning": on_page,
            **owes("markup"),
        },
        "pick inside a thread": {
            "kind": "action",
            "meaning": {"scope": "thread"},
            **owes("reply"),
        },
        "pick inside a thread over App Server": {
            "kind": "action",
            "meaning": {"scope": "thread"},
            **owes("turn"),
        },
        "resolve": {"kind": "resolve"},
        "unresolve": {"kind": "unresolve"},
        "done": {"kind": "done"},
        "request": {"kind": "request", **owes("receipt")},
        "undo": {"kind": "undo"},
        "report": {"kind": "report"},
        "error": {"kind": "error"},
    }
    told = {
        name: registry_contract.event_clauses(event, registry)
        for name, event in cases.items()
    }

    declared = registry["$events"]["handling"]
    answering = registry["$events"]["answering"]
    assert {event["kind"] for event in cases.values()} == set(declared)

    def owed(event):
        return event.get("answer", {}).get("kind")

    assert {owed(event) for event in cases.values()} - {None} == set(answering)
    read = {
        field
        for clauses in (*declared.values(), *answering.values())
        for clause in clauses
        if "when" in clause
        for field in fields_named(clause["when"])
    }
    for name, event in cases.items():
        unread = set(event) - {"kind", "answer"} - read
        assert not unread, (name, unread)
    for kind, clauses in declared.items():
        reached = [told[name] for name, event in cases.items() if event["kind"] == kind]
        for clause in clauses:
            assert any(clause in matched for matched in reached), (kind, clause)
    for kind, clauses in answering.items():
        reached = [told[name] for name, event in cases.items() if owed(event) == kind]
        for clause in clauses:
            assert any(clause in matched for matched in reached), (kind, clause)

    # The walkthrough: one comment through the real HTTP route and `leaf wait`.
    (page_dir / "index.html").write_text(WALKTHROUGH_PAGE)
    publish(page_dir)
    session_model.cmd_status(page_dir, "waiting", "")
    posted = {
        "kind": "comment",
        "revision": 1,
        "text": "why here?",
        "anchor": {"section": "plan", "quote": "moves to Tuesdays"},
        "attempt": "9f86d081884c7d659a2feaa0c55ad015",
    }
    status, answer = fetch(f"{server}/api/event", data=json.dumps(posted).encode())
    assert status == 200, answer
    logged = (page_dir / "events.jsonl").read_text().splitlines()[-1]
    capsys.readouterr()
    assert session_model.cmd_wait(page_dir) == 0
    printed = capsys.readouterr().out
    record, envelope = json.loads(logged), json.loads(printed)
    [batch] = envelope["batches"]
    [delivered] = batch["events"]
    page_events = registry_storage.load_registry(page_dir)["$events"]
    page_clauses = [
        *page_events["handling"]["comment"],
        *page_events["answering"][delivered["answer"]["kind"]],
    ]
    [conversation] = batch["conversations"]
    applying = registry_contract.event_clauses(
        {
            **record,
            "answer": delivered["answer"],
            "conversation": conversation,
        },
        registry_storage.load_registry(page_dir),
    )
    assert [clause["text"] for clause in applying] == [
        batch["handling"][ref] for ref in delivered["handling"]
    ]
    # The full line, anchor and all, gets exactly the `comment` case's clauses.
    assert applying == told["comment"]

    pinned = {
        record["id"]: "1946b466",
        record["ts"]: "2026-09-21T20:12:30-07:00",
        envelope["id"]: "e8417b8a-6e03-45ad-b7bd-c0f0eceb1a92",
        str(page_dir): "/path/to/page",
    }
    envelope["created_at"] = 1790046750.29

    def pin(shown: str) -> str:
        for actual, steady in pinned.items():
            shown = shown.replace(actual, steady)
        return shown

    def indented(block: str) -> str:
        return textwrap.indent(block, " " * 5)

    listing = []
    for number, clause in enumerate(page_clauses, 1):
        verdict = "applies" if clause in applying else "does not apply"
        listing.append(f"clause {number}, {verdict}:")
        if "when" in clause:
            listing.append(f"  when: {json.dumps(clause['when'])}")
        else:
            listing.append("  (no `when`, so it always applies)")
        listing.append(
            textwrap.fill(
                clause["text"],
                79,
                initial_indent="  text: ",
                subsequent_indent=" " * 8,
                break_on_hyphens=False,
            )
        )
    added = [f"`{key}`" for key in delivered if key not in record]
    [dropped] = [f"`{key}`" for key in record if key not in delivered]
    header = (
        HANDLING_WALKTHROUGH.replace("@POSTED@", indented(json.dumps(posted)))
        .replace("@LOGGED@", indented(pin(logged)))
        .replace("@COUNT@", str(len(page_clauses)))
        .replace("@CLAUSES@", indented("\n".join(listing)))
        .replace("@ADDED@", ", ".join(added[:-1]) + " and " + added[-1])
        .replace("@DROPPED@", dropped)
        .replace("@DELIVERY@", indented(pin(json.dumps(envelope, indent=2))))
    )

    recorded = {
        name: {
            "event": event,
            "told": [
                {
                    **({"when": Json(clause["when"])} if "when" in clause else {}),
                    "text": Prose(clause["text"]),
                }
                for clause in told[name]
            ],
        }
        for name, event in cases.items()
    }
    header = header.replace(
        "@RECORDED@", indented(yaml_block({"comment": recorded["comment"]}).rstrip())
    )
    snapshot.check(yaml_document(header, recorded))


CARRIER_WALKTHROUGH = """\
What each carrier hands the agent for one comment
===================================================

A test records this file; nobody writes it by hand. The lines starting with `#`
explain it, and everything else is the recorded data. The run below serves the
page from test_each_case_of_an_event_is_told_what_the_snapshot_shows, posts the
same comment ("why here?" on "moves to Tuesdays") through POST /api/event, and
then lets each of Leaf's three carriers deliver it. Only ids, times and the
page's path are pinned, so the file stays the same from run to run.

A carrier is the route that takes new user input to the agent's task:

  leaf wait          The agent runs `leaf wait` in the background. It prints
                     the delivery as JSON and exits, and the host hands that
                     output to the agent as the command's result, which wakes
                     it. The agent acknowledges the delivery itself, with
                     `leaf wait --ack <delivery-id>`, and answers with
                     `leaf reply`. Claude Code uses this carrier, and so does a
                     Codex task running without Leaf's adapter.
  Codex queue        Leaf's adapter freezes the delivery and runs `codex queue`
                     with a pointer to it as the task's next user message. The
                     agent reads the delivery with `leaf delivery read <id>`,
                     which prints it as indented JSON, and answers with
                     `leaf reply`. The adapter acknowledges the delivery once
                     Codex's queue accepts it.
  Codex App Server   Leaf starts a turn with `turn/start`, carrying the
                     delivery as a `leaf_delivery` tool output, and binds the
                     turn's opening and final messages as the reply. Leaf
                     acknowledges the delivery once it enters that turn.
                     leaf.page's hosted agent and a `leaf codex launch`
                     terminal use this carrier.

Each carrier freezes a delivery of its own. The envelope's shape is the same on
all three, and it names its `carrier`. Two things differ, each stated once:
`acknowledge` says how the agent confirms the delivery, or is null where the
carrier confirmed it; and the comment's `answer` is a `reply`, for `leaf reply`,
except on App Server, where it is a `turn` the turn's own messages write. The
`handling` follows from the answer, so each agent is told only its own route.
The agent's standing instructions (its host contract, and on leaf.page the
developer instructions) are not part of a delivery; test_website_server records
leaf.page's.

What this file records
----------------------

One top-level key per carrier, holding exactly what reaches the agent's task:

  leaf wait:         its output.
  Codex queue:       the `--message` given to `codex queue`, and the output of
                     the `leaf delivery read` it points at.
  Codex App Server:  the `turn/start` params. `toolOutput.output` is the
                     delivery serialized as one line of JSON; it is shown
                     decoded here.

JSON is shown as YAML, and each clause in a batch's `handling` as wrapped prose,
so the three read side by side. Every text is exactly what the agent receives.

After changing what a carrier sends, re-record this file and review the diff:

  uv run pytest --regtest-reset -n0 tests/test_interact_contract.py::test_each_carrier_hands_the_agent_what_the_snapshot_shows"""


def test_each_carrier_hands_the_agent_what_the_snapshot_shows(
    snapshot, page_dir, server, capsys
):
    """The snapshot is the page a developer reads to compare what one comment puts
    in front of the agent on each carrier: `leaf wait`, the Codex
    queue's pointer and the delivery it names, and the Codex App Server turn. Each
    is taken from the code that carrier runs, after one real POST, so a change to
    any carrier's framing or to a delivery's contents shows up as a diff under the
    carrier it reaches."""
    (page_dir / "index.html").write_text(WALKTHROUGH_PAGE)
    publish(page_dir)
    posted = {
        "kind": "comment",
        "revision": 1,
        "text": "why here?",
        "anchor": {"section": "plan", "quote": "moves to Tuesdays"},
    }
    status, answer = fetch(f"{server}/api/event", data=json.dumps(posted).encode())
    assert status == 200, answer
    logged = json.loads((page_dir / "events.jsonl").read_text().splitlines()[-1])

    session_model.cmd_status(page_dir, "waiting", "")
    capsys.readouterr()
    assert session_model.cmd_wait(page_dir) == 0
    waited = capsys.readouterr().out

    # The adapter's queue route: collect the batch, then offer its pointer.
    with service_model.PageTransaction(page_dir) as transaction:
        path, _, _ = codex_model.append_batch(
            "codex-queue-task",
            page_dir,
            transaction,
            service_model.unacknowledged(transaction.events, transaction.cursor),
        )
    queued = codex_model.offer_delivery(path, files_model.read_json(path), "queue")
    delivery_model.cmd_delivery_read(queued.payload["id"])
    read = capsys.readouterr().out

    thread = "codex-thread"
    prepared = codex_model.prepare_codex_delivery(
        page_dir, host_model.EmbeddedHarness(thread, "Codex", os.getpid())
    )
    started = codex_model.app_server_turn_start_params(thread, prepared.payload)
    delivery_model.cmd_delivery_read(prepared.payload["id"])
    assert json.loads(started["toolOutput"]["output"]) == json.loads(
        capsys.readouterr().out
    )

    pinned = {
        logged["id"]: "1946b466",
        logged["ts"]: "2026-09-21T20:12:30-07:00",
        json.loads(waited)["id"]: "11111111",
        queued.payload["id"]: "22222222",
        prepared.payload["id"]: "33333333",
        # The turn's reply attempt is derived from the delivery id.
        service_model.delivery_reply_attempt(
            prepared.payload["id"]
        ): service_model.delivery_reply_attempt("33333333"),
        str(page_dir): "/path/to/page",
    }

    def pin(shown: str) -> str:
        for actual, steady in pinned.items():
            shown = shown.replace(actual, steady)
        return shown

    def readable(printed: str) -> dict:
        delivery = json.loads(pin(printed))
        delivery["created_at"] = 1790046750.29
        if delivery["acknowledge"] is not None:
            delivery["acknowledge"] = Prose(delivery["acknowledge"])
        for batch in delivery["batches"]:
            batch["handling"] = {
                ref: Prose(text) for ref, text in batch["handling"].items()
            }
        return delivery

    started = json.loads(pin(json.dumps(started)))
    started["toolOutput"]["output"] = readable(started["toolOutput"]["output"])
    snapshot.check(
        yaml_document(
            CARRIER_WALKTHROUGH,
            {
                "leaf wait": {"output": readable(waited)},
                "Codex queue": {
                    "codex queue --message": Prose(pin(queued.prompt)),
                    "leaf delivery read 22222222": readable(read),
                },
                "Codex App Server": {"turn/start": started},
            },
        )
    )


def fields_named(schema: dict) -> set[str]:
    """Every event field a `when` schema names at its top level, through `not`,
    `anyOf` and `allOf`."""
    named = set(schema.get("required", [])) | set(schema.get("properties", {}))
    for part in [
        *([schema["not"]] if "not" in schema else []),
        *schema.get("anyOf", []),
        *schema.get("allOf", []),
    ]:
        named |= fields_named(part)
    return named


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

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
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
        json.dumps({"$keys": {"x-space": "wider, in this project", "x-nope": "?"}})
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code != 0
    assert "unadmitted ['x-nope']" in result.output

    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"x-space": "wider, in this project"}})
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    keys = json.loads((page_dir / "registry.json").read_text())["$keys"]
    assert keys["x-space"] == "wider, in this project"
    assert keys["x-says"]  # the rest of the shipped members stand


def test_event_kinds_are_the_kernel_contract_not_a_layer_extension(page_dir, tmp_path):
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["$events"]["kinds"]["signal"] = registry["$events"]["kinds"]["error"]
    (overlay / "registry.json").write_text(json.dumps(registry))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )

    assert result.exit_code != 0
    assert "$events.kinds is Leaf's fixed transport contract" in result.output

    (overlay / "registry.json").write_text(json.dumps({"$events": {"kinds": None}}))
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*PAGE_PACKAGES, "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code != 0
    assert "$events.kinds is Leaf's fixed transport contract" in result.output

    with pytest.raises(
        registry_contract.RegistryError,
        match=r"\$events.kinds must equal Leaf's fixed transport contract",
    ):
        registry_validation.validate_registry(registry, "incoming")


def test_an_empty_host_name_uses_the_host_default(page_dir, sessionless, monkeypatch):
    published(page_dir)
    monkeypatch.setenv("LEAF_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "")

    result = comment(page_dir, "--text", "Which worker said this?")

    assert result.exit_code == 0, result.output
    event = events_model.read_events(page_dir)[-1]
    assert (event["agent"], event["session"]) == ("Codex", "worker-1")


def test_a_widget_nobody_has_touched_is_not_the_gate_s_business(page_dir):
    """The gate is about decisions, so it holds nothing against a version that
    rewrites a widget the user never acted on."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>First words.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>Quite different words.</pre></lf-draft>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_requires_the_vendored_layer(tmp_path):
    d = tmp_path / "bare"
    d.mkdir(parents=True)
    (d / "index.html").write_text(PAGE)
    result = check(d)
    assert result.exit_code == 1
    assert "run `leaf page init` to vendor the layer" in result.output


def test_check_takes_column_width_from_vendored_theme(page_dir):
    # theme.css sets a 720px main column; a wider fixed-width element must fail.
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", '<h2>Plan</h2><svg width="900" height="10"></svg>'
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "exceeds column (720px)" in result.output


def test_check_advises_page_css_that_scrolls_a_box_or_places_a_layout_element(
    page_dir,
):
    """Page CSS stays free, so both are advice: a scroller Leaf did not make is one its
    reading features cannot reach, and a grid the page places is geometry the layout
    no longer owns. Styling a cell, or text inside one, is neither."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<title>t</title>",
            "<title>t</title><style>.feed { overflow-y: auto; max-height: 20rem }"
            " main lf-grid { display: flex } lf-grid > p { color: red }"
            " .wide { overflow-x: auto } lf-grid::before { display: block }"
            " #cells { grid-template-columns: 1fr }</style>",
        ).replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-grid id="cells"><p>One</p><p>Two</p></lf-grid>'
            '<div class="feed" style="overflow: scroll"><p>Log</p></div>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "rule `.feed` sets overflow-y to scroll" in result.output
    assert "sets overflow to scroll" in result.output
    assert "rule `main lf-grid` sets display on <lf-grid>" in result.output
    assert "rule `#cells` sets grid-template-columns on <lf-grid>" in result.output
    assert "lf-grid > p" not in result.output
    assert ".wide" not in result.output
    assert "lf-grid::before" not in result.output


def test_check_advises_the_same_css_in_a_stylesheet_the_page_links(page_dir):
    """A stylesheet the page links from page/, and one that sheet imports, are page CSS
    as much as its <style>, so the advice reads them and names the file."""
    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "app.css").write_text(
        '@import "grid.css";\n.feed { overflow-y: auto }\n'
    )
    (page_dir / "page" / "grid.css").write_text("#cells { display: flex }\n")
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<title>t</title>",
            '<title>t</title><link rel="stylesheet" href="/page/app.css">',
        ).replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-grid id="cells"><p>One</p><p>Two</p></lf-grid>'
            '<div class="feed"><p>Log</p></div>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    assert "/page/app.css rule `.feed` sets overflow-y to scroll" in result.output
    assert "/page/grid.css rule `#cells` sets display on <lf-grid>" in result.output


def test_check_rejects_an_invalid_bound_and_loose_grid_text(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><pre data-bound="bottom">log</pre>'
            '<lf-grid id="cells">loose<p>Two</p></lf-grid>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert (
        "data-bound='bottom'> (line 9) has an invalid value; expected one of start, "
        in (result.output)
    )
    assert "x-reading-role grid holds its cells as elements" in result.output


def test_check_rejects_an_unknown_authored_width(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><table data-width="full"><tr><td>A</td></tr></table>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert (
        "<table data-width='full'> (line 9) has an invalid value; expected one of "
        "column, wide, available" in result.output
    )


def test_check_takes_a_rail_only_on_main_and_only_by_name(page_dir):
    """`data-rail` says whether the page keeps a rail, so it stands on `main` and names
    one of the two answers; anywhere else it would silently declare nothing."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<main>", '<main data-rail="none">')
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    (page_dir / "index.html").write_text(
        PAGE.replace("<main>", '<main data-rail="left">').replace(
            "<h2>Plan</h2>", '<h2>Plan</h2><section data-rail="none"><p>A</p></section>'
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "data-rail='left'> (line" in result.output
    assert "expected one of right, none" in result.output
    assert "data-rail> (line" in result.output
    assert "belongs on <main>" in result.output


def test_activation_rechecks_changed_css_while_the_document_stays_identical(page_dir):
    """Reused CSS readings must follow theme bytes, including tokens and diagnostics."""
    theme = page_dir / "theme.css"
    original = theme.read_text()
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p style="width: var(--pin)">Measured.</p>',
        )
    )

    def activate(css):
        theme.write_text(original + css)
        return revisioning_model.activate_source(page_dir)

    css = ":root { --pin: 700px; --col: 720px } main { --lf-reading-column: 1; max-width: var(--col) }"
    initial = activate(css)
    assert initial.error is None
    assert activate(css).error is None

    overwide = activate(css.replace("700px", "900px"))
    assert "style> (line " in overwide.error
    assert "sets width: 900px (column is 720px)" in overwide.error
    assert overwide.revision == initial.revision

    wider_column = css.replace("700px", "900px").replace("720px", "960px")
    widened = activate(wider_column)
    assert widened.error is None
    from leaf.validation.source import check_source

    assert check_source(page_dir, []).column == 960
    assert widened.created
    assert widened.revision == initial.revision + 1

    broken = activate(wider_column + " .broken { color red }")
    assert "theme.css syntax error" in broken.error
    assert activate(wider_column).error is None


def test_check_reads_a_column_the_theme_states_as_a_token():
    """A width naming a root token is a width the stylesheet stated, so the column reads
    it. The theme keeps its own constants in `:root` and more than one rule now wants the
    measure; a reading that stopped at the name would fall back to a default column and
    go on printing a number, which is a check that stops measuring exactly when the file
    it measures gets tidier.

    Only the root, and only what is stated outright. A token declared inside a query is
    that condition's, the same reason the column will not read a media query's width, and
    a token nothing declares leaves the `var()`'s own fallback — the browser's answer."""
    column = "--lf-reading-column: 1;"
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
    the block that sets the width — `--lf-reading-column: 1` beside the max-width, so the cascade
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
        styles_model._column_width(
            "", ".prose { --lf-reading-column: 1; max-width: 560px }"
        )
        == 560
    ), "a column named anything at all is still not readable, so the claim is ignored"

    assert (
        styles_model._column_width(
            "main { --lf-reading-column: 1; max-width: 500px }", ""
        )
        == 500
    ), "a page's own <style> no longer states the column it is measured against"

    theme = (schema_model.ASSETS / "theme.css").read_text()
    assert (
        styles_model._column_width("main { --lf-reading-column: 1 }", theme) == 720
    ), (
        "a claim with no width of its own stopped the reading where it stood, so a "
        "page could take the measure off itself by claiming and then saying nothing"
    )


def test_check_measures_a_width_named_from_the_layer_s_own_tokens(page_dir):
    """A page pinning `var(--wide)` is stating the vocabulary's own breakout width, which
    is wider than the column by design. The page's `<style>` declares no such token, so
    the reading resolves it against the layer the page vendored — the order the cascade
    reads the two roots in. Without the layer behind it, a page could take any width the
    theme names and never be measured for it."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p id="w" style="width: var(--wide)">Wide by name.</p>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert "<p style> (line " in result.output
    assert "sets width: 1080px (column is 720px)" in result.output


def test_the_strip_floor_is_one_number():
    """Margin posture is a query of the CSS-owned shell, with no mirrored runtime veto."""
    css = (schema_model.ASSETS / "theme.css").read_text()
    assert "container: lf-shell / inline-size" in css
    assert re.search(r"@container\s+lf-shell\s*\(min-width:\s*1152px\)", css)
    assert "data-lf-cramped" not in css


def test_the_sidebar_and_note_floor_is_their_sum():
    """Two opposite margin residents need the largest sidebar claim and ordinary floor.

    Media queries cannot read custom properties, so the combined breakpoint is written
    as a pixel value beside the sidebar rule. Hold that necessary copy to the two tokens
    it represents instead of letting a later width change silently squeeze the prose."""
    css = (schema_model.ASSETS / "theme.css").read_text()
    floor = 1152
    sidebar = re.search(r"--sidebar-max:\s*(\d+)px", css)
    assert sidebar
    combined = floor + int(sidebar[1])
    default_theme = (
        schema_model.ASSETS.parent / "packages" / "default" / "theme.css"
    ).read_text()
    assert "--lf-sidebar-claim: var(--sidebar-max)" in default_theme
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
    assert fetch(server + "/events.jsonl")[0] == 404


def test_a_media_digest_can_never_change_the_bytes_behind_an_existing_name(
    page_dir, tmp_path, monkeypatch
):
    """The public name's immutable meaning survives even a digest collision."""

    class CollidingDigest:
        def hexdigest(self):
            return "a" * 64

    monkeypatch.setattr(media_model.hashlib, "sha256", lambda data: CollidingDigest())
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first pixels")
    second.write_bytes(b"different pixels")
    path = media_model.cmd_media(page_dir, [first])[0][1]

    with pytest.raises(RuntimeError, match="media digest collision"):
        media_model.cmd_media(page_dir, [second])

    assert (page_dir / path.lstrip("/")).read_bytes() == first.read_bytes()


def test_check_names_a_media_reference_the_directory_cannot_answer(page_dir):
    """A broken image is silent in the file and obvious on the page. The render gate
    would see the 404, but it runs once; this runs on every version, and whether a
    file is there is as deterministic as whether an id is."""
    (page_dir / "index.html").write_text(
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
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><p>Write it as <code>"/media/deadbeefdeadbeef.png"</code>.</p>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_source_reading_preserves_foreign_graphics_as_exact_markup():
    graphic = (
        '<svg id="plot" viewBox="0 0 10 10">\r\n'
        '<circle cx="5" cy="5" r="4"/>\r\n'
        '<svg><text x="0">A &amp; B</text></svg>'
        "<foreignObject><p>HTML <strong>inside</strong></p></foreignObject>\r\n"
        "</svg >"
    )
    html = "<main>Préface\r\n" + graphic + '<p id="after">After</p></main>'
    parser = structure_model.SourceDocument(html)
    [main] = parser.content
    _, image, after = main["content"]
    assert image["markup"] == graphic
    assert image["content"] == []
    assert image["line"] == 2
    assert after["attrs"]["id"] == "after"
    assert after["content"] == ["After"]


def test_source_reading_keeps_a_specimen_out_of_its_parent_identity_space():
    """Child documents keep their own ids, widgets, passages, and validation reading."""
    html = (
        '<main><p id="visible">Visible words.</p>'
        '<template id="practice" data-specimen><lf-ask id="nested-ask">'
        '<h2>Hidden question</h2><lf-options id="nested-options" choose>'
        '<lf-option id="nested-choice">Hidden answer</lf-option>'
        "</lf-options></lf-ask></template></main>"
    )
    parser = structure_model.SourceDocument(html)

    assert parser.errors == []
    assert parser.lf_elements == []
    assert "nested-options" not in parser.by_id
    assert passages_model.page_passages(parser).text == "Visible words."
    [specimen] = parser.specimens
    assert "nested-options" in specimen["document"].by_id
    assert specimen["document"].main_elements == [(1, True)]


@pytest.mark.parametrize(
    ("markup", "error"),
    [
        ("<noscript>invisible</noscript>", "the browser renders none of its content"),
        ('<lf-unknown id="bad">Unknown</lf-unknown>', "unknown widget"),
        ('<lf-draft id="change" restated><pre>Text</pre></lf-draft>', "restated"),
        ("<template data-specimen><h1>Child</h1></template>", "needs a stable id"),
        ('<p id="duplicate">One</p><p id="duplicate">Two</p>', "duplicate"),
        (
            '<template id="nested" data-specimen><noscript>hidden</noscript></template>',
            "specimen 'nested'",
        ),
    ],
)
def test_check_validates_each_specimen_document(page_dir, markup, error):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            f'<template id="practice" data-specimen>{markup}</template></main>',
        )
    )
    result = check(page_dir)
    assert result.exit_code != 0, result.output
    assert "specimen 'practice'" in result.output
    assert error in result.output


@pytest.mark.parametrize("nested", [False, True])
def test_specimen_diagnostics_report_authored_lines(page_dir, nested):
    markup = '<lf-unknown\n id="bad">Unknown</lf-unknown>\n<noscript>Hidden</noscript>'
    if nested:
        markup = f'<template\n id="nested"\n data-specimen>\n{markup}</template>'
    source = PAGE.replace(
        "</main>",
        f'<template\n id="practice"\n data-specimen>\n{markup}</template></main>',
    )
    (page_dir / "index.html").write_text(source)
    result = check(page_dir)
    assert result.exit_code != 0, result.output
    assert "specimen 'practice'" in result.output
    if nested:
        assert "specimen 'nested'" in result.output
    line = source[: source.index("<noscript>")].count("\n") + 1
    assert f"<noscript> at line {line}:" in result.output


def test_check_keeps_parent_and_sibling_specimen_ids_independent(page_dir):
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            '<p id="shared">Parent</p>'
            '<template id="first" data-specimen><h1 id="shared">First</h1></template>'
            '<template id="second" data-specimen><h1 id="shared">Second</h1></template></main>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 0, result.output


def test_specimen_data_bindings_use_copied_data_but_not_parent_history(page_dir):
    declare_data_input(
        page_dir, "shared", {"type": "string"}, contract="parent", tag="lf-parent-data"
    )
    source = (page_dir / "index.html").read_text()
    declare_data_input(
        page_dir,
        "shared",
        {"type": "number"},
        contract="child",
        tag="lf-child-data",
        activate=False,
    )
    child = '<lf-child-data id="test-data" source="shared"></lf-child-data>'
    markup = source.replace(
        "</main>", f'<template id="practice" data-specimen>{child}</template></main>'
    )
    (page_dir / "index.html").write_text(markup)
    result = check(page_dir)
    assert result.exit_code == 0, result.output

    # A child may bind the same name differently, but cannot reinterpret the stored
    # value it copies from the parent.
    data_model.cmd_data_set(page_dir, "shared", "parent value")
    result = check(page_dir)
    assert result.exit_code != 0
    assert "specimen 'practice'" in result.output
    assert "it was recorded with 'parent'" in result.output


@pytest.mark.parametrize("seeded", [False, True])
@pytest.mark.parametrize("available", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_specimen_references_see_only_selected_conversations(
    page_dir, seeded, available, nested
):
    if available:
        events_model.append_event(
            page_dir,
            {
                "kind": "comment",
                "id": "aabb0011",
                "author": "user",
                "text": "A question",
            },
        )
    selection = ' data-specimen-threads="aabb0011"' if seeded else ""
    child = '<lf-suggestion id="answer" resolves="aabb0011"><lf-new>Answer</lf-new></lf-suggestion>'
    if nested:
        child = f'<template id="nested" data-specimen{selection}>{child}</template>'
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            f'<template id="practice" data-specimen{selection}>{child}</template></main>',
        )
    )
    result = check(page_dir)
    assert (result.exit_code == 0) == seeded, result.output
    if not seeded:
        assert "names no comment in this document" in result.output


def test_specimen_checks_available_history_beside_forward_conversation_references(
    page_dir,
):
    events_model.append_event(
        page_dir,
        {"kind": "comment", "id": "aabb0011", "author": "user", "text": "A question"},
    )
    events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "parent": "aabb0011",
            "author": "agent",
            "text": "An answer",
            "markup": '<lf-code id="duplicate" language="python"><pre>1</pre></lf-code>',
        },
    )
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</main>",
            '<template id="practice" data-specimen data-specimen-threads="aabb0011 aabb0022">'
            '<h1 id="duplicate">Child</h1></template></main>',
        )
    )
    result = check(page_dir)
    assert result.exit_code != 0
    assert (
        "ids already taken by widget markup in a reply: ['duplicate']" in result.output
    )


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
    (page_dir / "index.html").write_text(html)
    parser = structure_model.SourceDocument(html)
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
        (page_dir / "index.html").write_text(styled(css))
        return check(page_dir)

    assert (
        "sets width: 900px" in checked("@media print { .wide { width: 900px } }").output
    )
    assert (
        "sets width: 900px"
        in checked('.wide::before { content: "}"; width: 900px }').output
    )
    assert checked("/* .wide { width: 900px } */").exit_code == 0


def test_check_reports_css_syntax_errors_in_every_source_the_page_carries(page_dir):
    """The page's own <style>, each inline style, and every sheet it vendors.
    shadow.css is the sheet each widget's shadow root adopts, so a malformed rule
    there reaches the user as an unstyled widget with nothing said about it."""
    for name in ("theme.css", "shadow.css"):
        sheet = page_dir / name
        sheet.write_text(f"{sheet.read_text()}\n.vendored {{ color red; }}\n")
    (page_dir / "index.html").write_text(
        styled(
            '.page { color: "unterminated\n; }',
            '<p style="color red">Every CSS input is malformed.</p>',
        )
    )

    result = check(page_dir)

    assert result.exit_code == 1
    assert "page <style> syntax error" in result.output
    assert re.search(r"<p style> \(line \d+\) syntax error", result.output)
    assert "theme.css syntax error" in result.output
    assert "shadow.css syntax error" in result.output
    assert result.output.count("syntax error") == 4


def test_check_takes_its_column_from_what_a_page_states_outright(page_dir):
    """A rule inside an at-rule applies only when a condition this check never evaluates
    holds, which cuts both ways. It cannot set the column, because the column is the
    baseline everything else is measured against — reading it there let one line of print
    CSS measure every screen element against 2000px and pass the page. It can overflow
    one, because a pin is a risk rather than a baseline: it is too wide whenever its
    condition holds."""
    (page_dir / "index.html").write_text(
        styled(
            "main { --lf-reading-column: 1; max-width: 760px }"
            " @media print { main { --lf-reading-column: 1; max-width: 2000px } }",
            '<svg width="900" height="10"></svg>',
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    assert re.search(
        r'<svg width="900"> \(line \d+\) exceeds column \(760px\)', result.output
    )

    # And nesting is not a condition: a column stated on a rule that also wraps one stands.
    (page_dir / "index.html").write_text(
        styled(
            "main { --lf-reading-column: 1; max-width: 1000px; & p { color: red } }",
            '<svg width="900" height="10"></svg>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_counts_only_a_width_fixed_in_pixels(page_dir):
    """A length is a typed value, not a string ending in `px`. A percentage or a vw
    scales to whatever contains it, and a calc() with a px term inside it is arithmetic
    rather than a pin — only a lone pixel length can overflow the column."""
    (page_dir / "index.html").write_text(
        styled(".a { width: 200% } .b { width: 90vw } .c { width: calc(100% - 900px) }")
    )
    assert check(page_dir).exit_code == 0

    (page_dir / "index.html").write_text(styled(".d { width: 900px !important }"))
    assert "sets width: 900px" in check(page_dir).output


def test_check_measures_against_the_column_the_page_sets_for_itself(page_dir):
    """A page-local <style> is the page's own answer to how wide it reads, so it wins
    over the vendored theme's 720px and an element wider than the theme allows passes.

    It answers by claiming the column, the same way the theme's own rule does. A page
    that only sets a width sets a width: which rule is the measure everything else is
    read against is a thing a stylesheet says, not a thing a reader works out from how
    the rule is spelled."""
    (page_dir / "index.html").write_text(
        styled(
            "main { --lf-reading-column: 1; max-width: 1000px }",
            '<svg width="900" height="10"></svg>',
        )
    )
    assert check(page_dir).exit_code == 0


def test_check_reads_widths_where_the_document_states_them(page_dir):
    """A width is what an attribute or a <style> block states. Scanning the file's text
    for one instead read a rule quoted in the page's prose as a rule the page applies,
    and never saw a style="" written with the other quote character."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>", "<h2>Plan</h2><div style='width:900px'>wide</div>"
        )
    )
    result = check(page_dir)
    assert result.exit_code == 1
    # The finding names the element and its line, so an author with forty
    # style attributes knows which one it means.
    assert re.search(
        r"<div style> \(line \d+\) sets width: 900px \(column is 720px\)",
        result.output,
    )

    (page_dir / "index.html").write_text(
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
        "x-content": "markup",
        "x-awaits": {"when": {"open": [True]}, "answered": {"answer": {}}},
        "x-state": {
            "answer": {
                "detail": {"type": "object", "additionalProperties": False},
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
    version = page_dir / "index.html"
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


def test_shared_package_declarations_compose_by_member():
    """One package can extend a shared declaration without copying its peers."""
    board = {"role": "holder", "state": "status"}
    lane = {"role": "holder", "state": "phase"}
    merged = {"$workflow": {"widgets": {"lf-board": board}}}

    registry_layer.merge_layer_declarations(
        merged, {"$workflow": {"widgets": {"lf-lane": lane}}}
    )

    assert merged["$workflow"]["widgets"] == {
        "lf-board": board,
        "lf-lane": lane,
    }


def test_x_awaits_names_the_verbs_that_answer_it(page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-suggestion"]["x-awaits"]["answered"] = {"missing": {}}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 1
    assert "x-awaits answers with verbs ['missing'], which are not x-state" in (
        result.output
    )


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
    (page_dir / "index.html").write_text(PAGE.replace("</main>", shot + "</main>"))
    refused = check(page_dir)
    assert refused.exit_code == 1
    assert "/media/nope.png isn't in the page directory" in refused.output, (
        f"the version door stopped asking, so the comparison below is empty: "
        f"{refused.output}"
    )

    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    opened = comment(page_dir, "--text", "show me?")
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


def test_the_text_door_refuses_a_picture_the_page_directory_has_not_got(page_dir):
    """A message names its picture in Markdown, where the markup reading cannot see it.

    `check_markup` runs only when `--markup` is given, and the reference it asks about
    lives in an attribute. An agent sending a screenshot writes it in the words instead,
    so the shape `media_errors` was written for — here is what it looks like now — came
    through the one door that never asked, and the log is append-only: a picture the
    directory hasn't got is broken for as long as the page exists.

    The reading is the link or image destination the runtime resolves rather than a scan
    of the words, so the same path quoted in a sentence — a page explaining leaf writes
    one, and `version check` has always let it through — stays the author's prose. Every
    `/media/…` destination is asked about, the predicate the markup door's attribute
    harvest already keeps: the directory holds digest-named files and nothing else, so a
    destination that isn't one renders as a picture no request will ever answer."""
    publish(page_dir)
    missing = "/media/deadbeefdeadbeef.png"
    posted = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", f"the panel now:\n\n![shot]({missing})"],
    )
    assert posted.exit_code == 1, (
        f"the comment door froze a picture the page has not got into the log:\n"
        f"{posted.output}"
    )
    assert f"{missing} isn't in the page directory" in posted.output, posted.output
    assert not [e for e in events_model.read_events(page_dir) if e["kind"] == "comment"]

    mention = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", f"write it as `{missing}` in the message"],
    )
    assert mention.exit_code == 0, (
        f"a path named in a sentence is the author's words, the reading the markup "
        f"door already keeps, not a picture the page owes:\n{mention.output}"
    )

    quoted = CliRunner().invoke(
        cli_model.cli,
        [
            "comment",
            str(page_dir),
            "--text",
            f"Here is the source:\n\n```md\n![shot]({missing})\n```\n\n[unused]: {missing}",
        ],
    )
    assert quoted.exit_code == 0, (
        f"code and an unused reference definition render no media, so neither "
        f"requires a file:\n{quoted.output}"
    )

    linked = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", f'[the panel](<{missing}> "shot")'],
    )
    assert linked.exit_code == 1, (
        f"a link destination points at the same file an image does, angle brackets "
        f"and title included:\n{linked.output}"
    )

    referenced = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", f"![shot][ref]\n\n[ref]: {missing}"],
    )
    assert referenced.exit_code == 1, (
        f"a reference definition is where a reference-style image keeps its "
        f"destination, and the runtime renders it as the inline form:\n"
        f"{referenced.output}"
    )

    unnamed = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", "look:\n\n![shot](/media/screenshot.png)"],
    )
    assert unnamed.exit_code == 1, (
        f"the directory holds digest-named files and nothing else, so a destination "
        f"under /media/ that isn't one is a picture it can never answer — the reading "
        f"the markup door's attribute harvest already keeps:\n{unnamed.output}"
    )

    (page_dir / "media").mkdir(exist_ok=True)
    (page_dir / "media" / "deadbeefdeadbeef.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    answered = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(page_dir), "--text", f"the panel now:\n\n![shot]({missing})"],
    )
    assert answered.exit_code == 0, (
        f"a reference the directory answers is the whole point of the door:\n"
        f"{answered.output}"
    )


def test_the_door_admits_a_reaction_only_as_a_token_the_layer_declares(
    server, page_dir
):
    """A reaction is a comment or reply carrying `token` in place of `text`: one of
    the two and never both, a word the merged vocabulary declares, and no
    suggestion, hold, or markup riding beside it. What the door lets through it
    also lets the user take back — while it is still a mark. An answer under it
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
            {"kind": "comment", "revision": 1, "token": "keep", "text": "and"},
            "valid under each of",
        ),
        ({"kind": "comment", "revision": 1}, "not valid under any"),
        (
            {"kind": "comment", "revision": 1, "token": "keep", "suggestion": True},
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
                    "token": "shorten",
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
                {"kind": "reply", "revision": 1, "parent": root["id"], "token": "keep"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert nod["token"] == "keep" and nod["parent"] == root["id"]

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
    # the answer; the user's move is in the thread it opened.
    conversation_model.cmd_reply(
        page_dir,
        reaction["id"],
        "Which part is long?",
        None,
        for_event=None,
    )
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": reaction["id"]}).encode(),
    )
    assert status == 400 and "has been answered" in json.loads(body)["error"]


def test_admission_names_dependencies_and_revendoring_preserves_their_meaning(
    server, page_dir
):
    """Recorded identities become dependencies, literal detail text does not, and a
    re-vendor may not change the fold unit or record form the fold reads the
    admitted command through."""
    from copy import deepcopy

    from leaf.files import latest_revision
    from leaf.validation.compatibility import candidate_vocabulary_gaps

    registry = json.loads((page_dir / "registry.json").read_text())
    choose = registry["lf-options"]["x-state"]["choose"]
    choose["detail"]["properties"]["annotation"] = {"type": "string"}
    (page_dir / "registry.json").write_text(json.dumps(registry))
    source = PAGE.replace("<lf-options>", '<lf-options id="picks" choose>')
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    revision = latest_revision(page_dir)
    command = {
        "kind": "action",
        "revision": revision,
        "widget": "picks",
        "action": "choose",
        "detail": {
            "options": ["flag-first"],
            "annotation": "plan-choice-decision",
        },
        "attempt": "named-dependencies",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(command).encode())
    assert status == 200, body
    events = json.loads(body)["state"]["events"]
    accepted = events[-1]
    assert set(accepted["meaning"]["depends"]) == {"picks", "flag-first"}
    within = passages_model.enclosing_ids(structure_model.SourceDocument(source))
    assert event_folds_model.action_retracted(
        accepted, {"flag-first": revision + 1}, within
    )
    moved = {**within, "flag-first": ("elsewhere", "flag-first")}
    assert not event_folds_model.action_retracted(
        accepted, {"flag-first": revision + 1}, moved
    )
    document = structure_model.SourceDocument(source)
    assert (
        candidate_vocabulary_gaps(page_dir, events, document, registry, revision) == []
    )
    recordless = deepcopy(registry)
    del recordless["lf-options"]["x-state"]["choose"]["record"]
    assert "changes its admitted record form" in "\n".join(
        candidate_vocabulary_gaps(page_dir, events, document, recordless, revision)
    )
    # The fold unit decides the shape a verb's state takes, so a candidate that moves
    # it would fold the admitted command into a different reading.
    reunited = deepcopy(registry)
    reunited["lf-options"]["x-state"]["choose"]["unit"] = "annotation"
    assert "changes its admitted fold unit" in "\n".join(
        candidate_vocabulary_gaps(page_dir, events, document, reunited, revision)
    )


def test_an_independent_verb_leaves_a_decisions_thread_resolved(page_dir):
    """Each verb is its own coordinate, so another verb on the deciding widget stands
    beside the decision: neither the thread it closed nor its membership moves."""
    from copy import deepcopy

    from leaf.projection import page_reading
    from leaf.thread_context import thread_memberships

    registry = registry_storage.require_registry(page_dir)
    registry = deepcopy(registry)
    registry["lf-suggestion"]["x-state"]["label"] = {
        "detail": {"type": "object"},
        "unit": "widget",
    }
    event = {
        "kind": "action",
        "id": "label1",
        "seq": 3,
        "author": "user",
        "revision": 1,
        "widget": "sug-a",
        "action": "label",
        "detail": {},
        "meaning": {
            "scope": "page",
            "unit": "sug-a",
            "depends": ["sug-a"],
        },
    }
    events = [{**COMMENT, "seq": 1}, {**ACCEPT, "id": "accept1", "seq": 2}, event]
    html = '<lf-suggestion id="sug-a"><lf-new><p>Proposed</p></lf-new></lf-suggestion>'
    page = page_reading(structure_model.SourceDocument(html), events, registry, 1)
    winner, _ = page.projection.actions[("sug-a", "sug-a", "decide")]
    assert winner["id"] == "accept1"
    threads = event_folds_model.build_threads(events, page.within)
    assert threads["c1"]["resolved"]["id"] == "accept1"
    memberships = thread_memberships(events, {"c1": "c1"}, {}, {})
    assert memberships["label1"] == []
