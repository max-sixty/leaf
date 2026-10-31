"""What a delivery carries: the events it freezes, the handling each event's case
asks for, the thread and widget context that makes a gesture readable, the bound
that keeps its envelope small, and its id."""

import json

import pytest
from click.testing import CliRunner
from interact_support import (
    COMMAND_SUBJECTS,
    PAGE,
    PICKS_PAGE,
    ROOT,
    SKILL_ROOT,
    _start,
    append_carried_log_record,
    append_command,
    declare_on_page,
    delivered,
    freeze_events,
    last_deliverable_seq,
    let_a_pick_settle_a_thread,
    owed_answers,
    page_state,
    printed,
    publish,
    receive_through,
    serving,
    stamp,
    state_json,
    thread_records,
    woken,
)

from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import thread as thread_model
from leaf.registry import contract as registry_contract
from leaf.registry import storage as registry_storage
from model.interact_contract import _stateful_page_declaration


def test_delivery_ids_are_short_and_rerolled_under_the_store_lock(monkeypatch):
    minted = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    widths = []
    token_hex_real = delivery_model.secrets.token_hex

    def token_hex(width):
        if width != 4:
            return token_hex_real(width)
        widths.append(width)
        return next(minted)

    monkeypatch.setattr(delivery_model.secrets, "token_hex", token_hex)
    first = delivery_model.freeze_delivery([], created_at=1)
    second = delivery_model.freeze_delivery([], created_at=2)

    assert widths == [4, 4, 4]
    assert (first["id"], second["id"]) == ("aaaaaaaa", "bbbbbbbb")


def test_each_delivered_event_says_only_what_its_own_case_asks(page_dir, capsys):
    """Shared clauses travel once, and each event names only its applicable rules:
    its kind's, then the answer it owes, and no answer's where it owes none."""
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir)
    page_pick = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "w",
        "action": "choose",
        "detail": {"value": ["a"]},
        "meaning": {
            "scope": "page",
            "unit": "w",
            "depends": ["a", "w"],
            "answer": None,
        },
    }
    thread_pick = {
        **page_pick,
        "meaning": {**page_pick["meaning"], "scope": "thread"},
    }
    drawing = {
        "strokes": [[[0, 0], [10, 10]]],
        "box": [640, 120],
        "viewport": [1200, 900],
        "scheme": "light",
    }
    for event in (
        {"kind": "comment", "id": "c1", "author": "user", "text": "hi"},
        {
            "kind": "comment",
            "id": "c2",
            "author": "user",
            "anchor": {"section": "w"},
            "drawing": drawing,
        },
        {"kind": "comment", "id": "c3", "author": "user", "text": "never mind"},
        {"kind": "resolve", "author": "user", "parent": "c3"},
        page_pick,
        thread_pick,
    ):
        append_carried_log_record(page_dir, event)

    assert service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    envelope, header, shown = delivered(capsys)
    handling = header["handling"]
    assert len(handling.values()) == len(set(handling.values()))
    assert shown[0]["handling"][0] in shown[1]["handling"]
    plain, drawn, closed, resolved, on_page, in_thread = (
        [handling[clause] for clause in event.get("handling", [])] for event in shown
    )
    declared = registry_storage.load_registry(page_dir)["$events"]
    [reading_a_drawing] = [
        c["text"]
        for c in declared["handling"]["comment"]
        if c.get("when") == {"required": ["drawing"]}
    ]
    replying = [c["text"] for c in declared["answering"]["reply"] if "when" not in c]
    # The envelope says once how this explicit wait is acknowledged; individual
    # events carry only their own handling and reply clauses.
    assert f"leaf delivery ack {envelope['id']} && leaf wait" in envelope["acknowledge"]
    assert not any("delivery ack" in text for text in handling.values())
    assert plain[-len(replying) :] == replying
    # A drawn comment is told everything a plain one is, and how to read its drawing.
    assert reading_a_drawing in drawn
    assert [clause for clause in drawn if clause != reading_a_drawing] == plain
    # A thread the user closed before capture owes nothing, so it is told nothing
    # about answering.
    assert not set(replying) & set(closed)
    assert resolved == [declared["handling"]["resolve"][0]["text"]]
    # Neither pick lands on a widget either document holds, so neither owes an
    # answer; the page's own clauses reach only the page pick.
    page_only = [
        c["text"]
        for c in declared["handling"]["action"]
        if c.get("when", {}).get("not", {}).get("required") == ["meaning"]
    ]
    assert page_only
    assert all(text in on_page and text not in in_thread for text in page_only)
    assert not set(replying) & set(on_page + in_thread)


def test_active_handling_survives_a_broken_page_declaration(page_dir, capsys):
    """An event is delivered with the handling of the revision it was read under, so
    a page declaration the next revision cannot take leaves that handling intact."""
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None and activated.revision == 1
    registry = registry_storage.active_registry(page_dir)
    comment = {"kind": "comment", "id": "c1", "author": "user", "text": "hi"}
    active = registry_contract.event_clauses(
        {
            **comment,
            "answer": {"kind": "reply", "writer": "agent"},
            "thread": {"title": None},
        },
        registry,
    )
    (page_dir / "page").mkdir(exist_ok=True)
    (page_dir / "page" / "registry.json").write_text('{"$events": {"handling": ')

    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir)
    append_carried_log_record(page_dir, comment)

    assert service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, batch, [shown] = delivered(capsys)
    assert active and [batch["handling"][ref] for ref in shown["handling"]] == [
        c["text"] for c in active
    ]


def test_codex_delivery_carries_only_the_selected_events_handling(page_dir):
    """A later reply stays out of this delivery, including its unique clauses."""
    for event in (
        {"kind": "error", "text": "first failure"},
        {"kind": "error", "text": "second failure"},
        {"kind": "comment", "text": "first question"},
        {
            "kind": "comment",
            "text": "later drawing",
            "drawing": {
                "strokes": [[[0, 0], [1, 1]]],
                "box": [640, 120],
                "viewport": [1200, 900],
                "scheme": "light",
            },
        },
    ):
        append_carried_log_record(page_dir, {"author": "user", **event})
    with service_model.PageTransaction(page_dir) as transaction:
        selected = transaction.events[:3]
        append_batch_result = codex_model.append_batch(
            "handling-test", page_dir, transaction, transaction.events
        )
        assert append_batch_result is not None
        queued, _, _ = append_batch_result
    record = codex_model.read_record(queued)
    assert isinstance(record, (codex_model.Collecting, codex_model.Offering))
    payload = codex_model.offer_delivery(queued, record, transport="queue").payload
    [batch] = payload["batches"]
    assert [event["id"] for event in batch["events"]] == [
        event["id"] for event in selected
    ]
    registry = registry_storage.active_registry(page_dir)
    digests = {digest["id"]: digest for digest in batch["threads"]}

    def case(event):
        """The event as its clauses read it: with its thread."""
        read = dict(event)
        if event["threads"]:
            read["thread"] = digests[event["threads"][0]]
        return read

    expected = [
        registry_contract.event_clauses(case(event), registry)
        for event in batch["events"]
    ]
    assert [
        [batch["handling"][ref] for ref in event["handling"]]
        for event in batch["events"]
    ] == [[clause["text"] for clause in clauses] for clauses in expected]
    assert set(batch["handling"].values()) == {
        clause["text"] for clauses in expected for clause in clauses
    }
    assert delivery_model.read_delivery(payload["id"]) == payload


def test_delivery_without_a_layer_has_no_handling(page_dir):
    (page_dir / schema_model.LAYER_FILE).unlink()
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hello"}
    )
    [batch] = freeze_events(page_dir, [comment])["batches"]
    assert batch["handling"] == {}
    assert "handling" not in batch["events"][0]


def test_delivery_distinguishes_thread_obligations_from_closing_answered_work(page_dir):
    """The same resolve/unresolve kinds can withdraw work or merely tidy a thread.
    Changes remain deliverable after pickup and after the work they changed ends.
    """
    publish(page_dir)

    def write(kind, **fields):
        event = append_command(page_dir, {"kind": kind, "author": "user", **fields})
        log = events_model.read_events(page_dir)
        selected = service_model.unacknowledged(log, event["seq"] - 1)
        assert selected == ([event] if event["attention"] else [])
        return event

    question = write("comment", revision=1, text="Please revise the plan.")
    assert question["attention"]
    newest = write("reply", parent=question["id"], text="Keep the launch small.")
    assert newest["attention"]
    receive_through(page_dir, newest["seq"])
    assert _start(page_dir, question["id"], "Revising").exit_code == 0
    withdrawal = write("resolve", parent=question["id"])
    assert withdrawal["attention"]
    # Repeated closure has neither an answer nor a started move left to change.
    assert not write("resolve", parent=question["id"])["attention"]
    reopened = write("unresolve", parent=question["id"])
    assert reopened["attention"]
    assert write("undo", undoes=reopened["id"])["attention"]
    assert write("unresolve", parent=question["id"])["attention"]
    answered = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": newest["id"],
            "responds": newest["id"],
            "text": "The plan is revised.",
        },
    )
    assert not write("resolve", parent=question["id"])["attention"]
    assert not write("unresolve", parent=question["id"])["attention"]
    # A task begun after the answer is separate work, with no pending response, and
    # it stands through the user closing and reopening the thread.
    opened = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            question["id"],
            "--text",
            "Checking the change.",
            "--todo",
            "Check the change",
        ],
    )
    assert opened.exit_code == 0, opened.output
    assert not write("resolve", parent=question["id"])["attention"]
    assert not write("unresolve", parent=question["id"])["attention"]
    assert owed_answers(page_dir) == []
    with service_model.PageTransaction(page_dir) as page:
        page.set_status("idle")
    assert withdrawal in service_model.unacknowledged(
        events_model.read_events(page_dir), newest["seq"]
    )
    assert not write(
        "read", messages=[{"message": answered["id"], "version": answered["id"]}]
    )["attention"]


def test_delivery_distinguishes_composing_an_obligation_from_changing_input_in_hand(
    page_dir,
):
    source = PAGE.replace(
        "<lf-options>", '<lf-options id="choice" choose multiple>'
    ).replace(
        "</section>", '<lf-draft id="draft"><pre>Blue room.</pre></lf-draft></section>'
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)

    def action(widget, verb, detail):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": verb,
                "detail": detail,
            },
        )

    composing = action("choice", "choose", {"value": ["flag-first"]})
    assert not composing["attention"]
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    completed = action("choice", "answer", {})
    assert completed["attention"]
    receive_through(page_dir, completed["seq"])
    # The agent takes the answered pick on as a task on its widget.
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            ["task", "create", str(page_dir), "choice", "--title", "Build the choice"],
        )
        .exit_code
        == 0
    )
    undone = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": completed["id"]}
    )
    assert undone["attention"]
    # The obligation is unfinished again, but the agent is already acting on its pick.
    changed = action("choice", "choose", {"value": ["backfill-first"]})
    assert changed["attention"]
    assert append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": changed["id"]}
    )["attention"]
    quiet = action("draft", "edit", {"value": "Green room."})
    assert not quiet["attention"]
    assert not append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": quiet["id"]}
    )["attention"]
    quiet = action("draft", "edit", {"value": "Red room."})
    assert (
        CliRunner()
        .invoke(
            cli_model.cli,
            ["task", "create", str(page_dir), "draft", "--title", "Edit the draft"],
        )
        .exit_code
        == 0
    )
    assert action("draft", "edit", {"value": "Orange room."})["attention"]
    selected = service_model.unacknowledged(
        events_model.read_events(page_dir), completed["seq"]
    )
    assert quiet not in selected
    assert undone in selected and changed in selected


def test_recordless_requests_wake_without_user_obligations(
    page_dir, sessionless, capsys
):
    from leaf.files import latest_revision
    from leaf.served_state.context import read_page

    (page_dir / "page").mkdir(exist_ok=True)
    declaration = _stateful_page_declaration(page_dir, "lf-archive")
    verb = {
        "unit": "widget",
        "detail": {"type": "object", "properties": {}, "additionalProperties": False},
    }
    declaration["x-state"] = {
        "archive": {**verb, "attention": True},
        "edit": verb,
    }
    declare_on_page(
        page_dir, lambda registry: registry.__setitem__("lf-archive", declaration)
    )
    source = PAGE.replace(
        "</section>", '<lf-archive id="row">Archive this</lf-archive></section>'
    )
    (page_dir / "index.html").write_text(source)
    serving(page_dir, 1)
    publish(page_dir)
    session_model.cmd_waiting(page_dir)

    def action(verb, widget="row"):
        return append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": latest_revision(page_dir),
                "widget": widget,
                "action": verb,
                "detail": {},
            },
        )

    def work():
        return read_page(page_dir, events_model.read_events(page_dir)).work.durable

    assert work().all_obligations["all"] == []
    quiet = action("edit")
    assert not quiet["attention"]
    first = action("archive")
    assert first["attention"]
    assert work().all_obligations["all"] == []
    assert owed_answers(page_dir) == []
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, events = printed(capsys.readouterr().out)
    assert [event["id"] for event in events] == [first["id"]]
    assert "answer" not in events[0]
    delivery_model.receive_delivery(payload["id"])
    assert page_state(page_dir)["pending"] == 0

    repeated = action("archive")
    assert repeated["attention"]
    assert not action("edit")["attention"]
    (page_dir / "index.html").write_text(
        source.replace("Archive this", "Archive this row")
    )
    note = publish(page_dir)
    assert not note["attention"]
    assert work().workflows == []
    # A stamp settles the receipt; taking back the requested state still needs
    # to reach the agent, just as changing it again does.
    undone = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": repeated["id"]}
    )
    assert undone["attention"]
    fresh = action("archive")
    assert fresh["attention"]
    assert service_model.unacknowledged(
        events_model.read_events(page_dir), first["seq"]
    ) == [repeated, undone, fresh]

    # The same declaration belongs to a widget frozen into a thread message.
    thread = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": latest_revision(page_dir),
            "text": "An optional command:",
            "markup": '<lf-archive id="thread-row">Archive this</lf-archive>',
        },
    )
    frozen = action("archive", "thread-row")
    assert frozen["attention"]
    assert "answer" not in frozen["meaning"]
    assert owed_answers(page_dir) == []
    append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": thread["id"],
            "text": "Archived.",
        },
    )
    assert not any(item["input"] == frozen["id"] for item in work().workflows)
    assert action("archive", "thread-row")["attention"]


def test_widget_actions_withdrawals_reports_and_errors_remain_deliverable(page_dir):
    source = PAGE.replace(
        "</section>",
        '<lf-options id="permit" choose><lf-option id="publish">Publish</lf-option>'
        '<lf-option id="hold">Keep it private</lf-option></lf-options></section>',
    )
    source = source.replace(
        "</section>",
        '<lf-test-tasks id="tasks"><lf-test-task id="task" status="active"><strong>Check</strong></lf-test-task></lf-test-tasks></section>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    done = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "permit",
            "action": "choose",
            "detail": {"value": ["publish"]},
        },
    )
    undo = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": done["id"]}
    )
    report = append_command(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "revision": 1,
            "widget": "task",
            "action": "status",
            "detail": {"value": "done"},
        },
    )
    error = append_command(
        page_dir,
        {
            "kind": "error",
            "author": "page",
            "revision": 1,
            "text": "The task view failed.",
        },
    )
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == [
        done,
        undo,
        report,
        error,
    ]
    assert all(event["attention"] for event in (done, undo, report, error))
    assert page_state(page_dir)["pending"] == 2


@pytest.mark.parametrize("title", [None, "Workshop venue"])
def test_first_delivery_carries_thread_title_without_repeating_messages(
    page_dir, title
):
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which space will be easier for everyone to find?",
        },
    )
    if title is not None:
        named = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "edit",
                str(page_dir),
                root["id"],
                "--title",
                title,
            ],
        )
        assert named.exit_code == 0, named.output
    assert service_model.claim_page(page_dir)
    waited = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert waited.exit_code == 0, waited.output
    _, header, shown = woken(waited.output)
    assert [event["id"] for event in shown] == [root["id"]]
    assert header["threads"] == [
        {
            "id": root["id"],
            "title": title,
            "anchor": None,
            "detached_from": None,
            "resolved": None,
            "elided": {"messages": 0, "actions": 0},
            "messages": [],
            "summaries": [],
            "actions": [],
        }
    ]


def test_a_delivered_reply_carries_the_thread_it_lands_in(page_dir, capsys):
    """A reply event names the message it answers and nothing else about its
    thread, and the agent's own answers are never delivered at all — they are
    not the user's news. So a follow-up reaches a session that has compacted, or
    one picking the page up, as an id it cannot resolve, and the answer goes out
    against half a thread. The envelope carries the rest: the anchor the
    thread hangs on and the messages the lines below it do not repeat."""
    serving(page_dir, 1)
    opened = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "why forty rather than four?",
            "anchor": {"section": "s-1", "quote": "one in about 40"},
        },
    )
    answered = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": opened["id"],
            "text": "the vendor has acknowledged it without naming a date",
        },
    )
    # Acknowledged, so the opening comment is off every later batch. That and
    # the agent's own answer — which, being nobody's news, was never on one —
    # leave the envelope as the only route to what was said.
    receive_through(page_dir, 1)
    followed = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": answered["id"],
            "text": "and if their release slips?",
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [followed["id"]]
    assert {key: shown[0]["answer"][key] for key in ("kind", "parent", "responds")} == {
        "kind": "reply",
        "parent": followed["id"],
        "responds": followed["id"],
    }
    assert delivery_model.response_address(shown[0]["answer"]["ref"])["page"] == str(
        page_dir
    )
    [thread] = header["threads"]
    assert thread["id"] == opened["id"]
    assert thread["anchor"] == {"section": "s-1", "quote": "one in about 40"}
    assert thread["resolved"] is None
    assert [(m["id"], m["author"]) for m in thread["messages"]] == [
        (opened["id"], "user"),
        (answered["id"], "agent"),
    ]
    assert "without naming a date" in thread["messages"][1]["text"]

    # A new thread carries its metadata without repeating the opening message.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "separately — the rollout"},
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, fresh, _ = delivered(capsys)
    [new_thread] = fresh["threads"]
    assert new_thread["title"] is None
    assert new_thread["messages"] == []

    # The user closing a thread from the panel posts a resolve, whose only
    # pointer at the thread is the message it names.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": followed["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, closed_batch, _ = delivered(capsys)
    [closed] = closed_batch["threads"]
    assert (closed["id"], closed["resolved"]) == (opened["id"], "user")


def test_a_delivered_gesture_on_a_sent_widget_carries_its_thread(page_dir, capsys):
    """An action names a widget, and a widget an agent sent lives in frozen
    thread markup rather than in any version. Neither the id nor the option it
    chose means anything without the message that asked, so the envelope
    resolves the widget to its thread and brings the markup along. An undo
    belongs to the thread holding the gesture it takes back."""
    subjects = (
        '<lf-test-plan id="hub"><lf-test-task id="goal" status="active">'
        "<strong>Goal</strong>" + COMMAND_SUBJECTS + "</lf-test-task></lf-test-plan>"
    )
    (page_dir / "index.html").write_text(
        PAGE.replace("</section>", subjects + "</section>")
    )
    publish(page_dir)
    serving(page_dir, 1)
    # A second thread carrying a widget of its own, so resolving the acted
    # widget to its thread is a result and not the only answer available.
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "And which region first?",
            "markup": '<lf-options id="rg" choose>'
            '<lf-option id="r-eu"><strong>EU</strong></lf-option>'
            "</lf-options>",
        },
    )
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which mitigations should I carry into the patch?",
            "markup": '<lf-options id="gm" choose>'
            '<lf-option id="m-cap"><small class="tag">recommended</small>'
            "<strong>Cap retries</strong> Bound retry load.</lf-option>"
            '<lf-option id="m-alert"><strong>Alert</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"value": ["m-cap"]},
        },
    )

    assert service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [chose["id"]]
    [thread] = header["threads"]
    assert thread["id"] == asked["id"]
    # The markup, because `m-cap` is a word only the question spells out.
    assert 'id="m-cap"' in thread["messages"][0]["markup"]
    # And the pick in words, read from that frozen message: the group is left
    # out because it only encloses the option chosen in it.
    assert shown[0]["says"] == {"m-cap": "recommended Cap retries Bound retry load."}
    assert shown[0]["names"] == {"m-cap": "Cap retries"}

    # In force, so a later delivery in this thread carries what the user
    # settled. Without it the agent meets the question with no answer under it
    # and replies reopening a list they have already ticked.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": asked["id"],
            "text": "that is the list",
        },
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, batch, _ = delivered(capsys)
    [carried] = batch["threads"]
    assert [
        (a["author"], a["widget"], a["action"], a["detail"]) for a in carried["actions"]
    ] == [("user", "gm", "choose", {"value": ["m-cap"]})]

    # Taken back, and the thread stops carrying it — the log keeps the
    # gesture, and no reading of the log stands on it.
    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": chose["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, withdrawn_batch, _ = delivered(capsys)
    [withdrawn] = withdrawn_batch["threads"]
    assert withdrawn["id"] == asked["id"]
    assert withdrawn["actions"] == []


def test_a_delivered_gesture_says_what_the_user_chose_on_their_version(
    page_dir, capsys
):
    """A page gesture is recorded as ids, and the agent reading the batch may
    hold none of the page: it compacted, or another session wrote it. The
    envelope spells out the elements the gesture names, from the revision the
    user pressed on, so a later version that rewords an option does not
    change what they chose. A gesture naming only its widget says the whole
    widget, and an undo says what it takes back."""
    asked = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
    (page_dir / "index.html").write_text(asked)
    publish(page_dir)
    (page_dir / "index.html").write_text(
        asked.replace("Ship dark.", "Ship behind the flag, reworded.").replace(
            "<strong>Flag first</strong>", "<strong>Reworded choice</strong>"
        )
    )
    advanced = stamp(page_dir, "Reworded the first plan")
    assert advanced.exit_code == 0, advanced.output
    serving(page_dir, 1)

    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 2,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    assert service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    _, _, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [answered["id"]]
    assert chose["attention"] is False
    [chosen] = freeze_events(page_dir, [chose])["batches"][0]["events"]
    assert chosen["names"] == {"flag-first": "Flag first"}
    [(widget, whole)] = shown[0]["says"].items()
    assert widget == "plan-choice"
    assert "Ship behind the flag, reworded." in whole and "Backfill first" in whole

    receive_through(page_dir, last_deliverable_seq(page_dir))
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": chose["id"]}
    )
    assert session_model.cmd_wait(page_dir) == 0
    _, _, [undone] = delivered(capsys)
    assert undone["says"] == {
        "flag-first": "effort: low risk: med Flag first Ship dark."
    }
    assert undone["names"] == {"flag-first": "Flag first"}


def test_one_action_can_belong_to_its_widget_thread_and_the_thread_it_resolves(
    page_dir, capsys
):
    """A sent widget lives in one thread and may answer another. The raw
    event is stored once, while exact selection and wait expose both semantic
    memberships without duplicating the event in a delivered batch."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    target = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "c-target",
            "author": "user",
            "revision": 1,
            "text": "Should we replace this wording?",
        },
    )
    origin = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Here is the proposed answer.",
            "markup": '<lf-suggestion id="thread-answer" resolves="c-target">'
            "<lf-old><p>Old words.</p></lf-old>"
            "<lf-new><p>New words.</p></lf-new>"
            "</lf-suggestion>",
        },
    )
    target_seq = next(
        event["seq"]
        for event in events_model.read_events(page_dir)
        if event["id"] == target["id"]
    )
    receive_through(page_dir, target_seq)
    capsys.readouterr()
    accepted = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-answer",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    payload, header, shown = delivered(capsys)
    assert [event["id"] for event in shown] == [accepted["id"]]
    assert shown[0]["threads"] == [origin["id"], target["id"]]
    assert shown[0]["answer"] == {
        "kind": "reply",
        "parent": origin["id"],
        "responds": accepted["id"],
        "ref": f"{payload['id']}:0:{accepted['id']}",
        "writer": "agent",
    }
    assert [thread["id"] for thread in header["threads"]] == [
        origin["id"],
        target["id"],
    ]
    for thread, expected in (
        (origin["id"], [origin["id"], accepted["id"]]),
        (target["id"], [target["id"], accepted["id"]]),
    ):
        assert thread_records(page_dir, thread) == expected

    reply = thread_model.post_reply(
        page_dir,
        {"parent": origin["id"], "responds": accepted["id"]},
        "Applied the accepted wording.",
    )
    assert reply["parent"] == origin["id"]


def test_a_delivered_gesture_on_a_sent_widget_keeps_its_message_in_a_long_thread(
    page_dir, sessionless, capsys
):
    """A pick is meaningful only beside the message that declared its widget. Keep
    that message even when a long thread would normally elide it from the delivery
    envelope."""
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "How should I recover this branch?",
        },
    )
    parent = root["id"]
    asking_message = None
    for index in range(11):
        message = {
            "kind": "reply",
            "author": "agent",
            "parent": parent,
            "text": f"Recovery context {index}.",
        }
        if index == 2:
            message["markup"] = (
                '<lf-options id="thread-commands" choose>'
                '<lf-option id="restart"><strong>Restart</strong></lf-option>'
                '<lf-option id="park"><strong>Park</strong></lf-option>'
                "</lf-options>"
            )
        sent = append_carried_log_record(page_dir, message)
        parent = sent["id"]
        if index == 2:
            asking_message = sent
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-commands",
            "action": "choose",
            "detail": {"value": ["restart"]},
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, shown = printed(capsys.readouterr().out)
    assert header is not None
    assert [event["id"] for event in shown] == [chose["id"]]
    [thread] = header["threads"]
    assert thread["id"] == root["id"]
    assert asking_message is not None
    carried = next(
        message
        for message in thread["messages"]
        if message["id"] == asking_message["id"]
    )
    assert 'id="thread-commands"' in carried["markup"]


@pytest.mark.parametrize("rewritten", [True, False])
def test_a_delivery_and_page_state_agree_on_what_a_floor_took_back(
    page_dir, capsys, rewritten
):
    """An answer rests on the widget that sent it and on the ids that widget's
    detail names inside itself, so a version rewriting one of those takes the
    answer back and the question stands open again. `page state` has always read
    it that way, holding the whole page. A delivery holds the log and may not
    raise on the gate that loading a page's vendored registry is — but where an
    element sits was never the vocabulary's to answer, so it reads that much and
    agrees.

    Told otherwise the two disagree silently, and in the worst direction: the
    user watches their question reopen while the agent is told, in the same
    breath as their follow-up, that they had already answered it.

    The floor lands on the option rather than the group. Before a new reply,
    only a rewritten answer reopens the thread; the user's subsequent question
    resumes either thread, and delivery agrees with page state."""
    (page_dir / "index.html").write_text(PICKS_PAGE)
    let_a_pick_settle_a_thread(page_dir, "which")
    serving(page_dir, 1)
    opened = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": "which",
            "author": "user",
            "text": "which of these?",
            "anchor": {"section": "picks"},
        },
    )
    publish(page_dir)
    answered = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
        },
    )
    # Rewriting the option they picked retracts the pick: the thing they chose is
    # not the thing on the page any more. Leaving it alone is the other arm.
    note = {
        "kind": "note",
        "author": "agent",
        "version": 2,
        "revision": 2,
        "text": "rewrote the first option" if rewritten else "tidied the prose",
    }
    if rewritten:
        note["restated"] = ["flag-first"]
    append_carried_log_record(page_dir, note)
    # By seq off the log: `append_event` hands back what it was given plus an id,
    # and a seq is the line the log gave it.
    logged_seq = {e["id"]: e["seq"] for e in events_model.read_events(page_dir)}
    receive_through(page_dir, logged_seq[answered["id"]])
    [before_reply] = state_json(page_dir)["threads"]
    assert (before_reply["resolved"] is None) is rewritten
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": opened["id"],
            "text": "so which is it now?",
        },
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    [delivered_thread] = header["threads"]
    assert delivered_thread["id"] == opened["id"]
    [served] = state_json(page_dir)["threads"]
    assert delivered_thread["resolved"] == served["resolved"]
    # The new spoken turn resumes either thread, regardless of its old answer.
    assert delivered_thread["resolved"] is None


def test_the_bound_keeps_the_message_a_carried_gesture_needs(page_dir, capsys):
    """A gesture names a widget, and what that widget asked lives only in the
    message that sent it: page markup is a file read away, thread markup is
    nowhere but the log. So a long thread whose question sits early would
    otherwise deliver `choose m-cap` with nothing saying what `gm` asked or what
    `m-cap` said — the defect this reading exists to fix, surviving the bound."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    root = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "text": "how?"}
    )
    asked = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "text": "Which mitigations?",
            "markup": '<lf-options id="gm" choose multiple>'
            '<lf-option id="m-cap"><strong>Cap retries</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "gm",
            "action": "choose",
            "detail": {"value": ["m-cap"]},
        },
    )
    # Bury the question: enough later exchange that the bound would drop it.
    parent = root["id"]
    for turn in range(12):
        parent = append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "user" if turn % 2 else "agent",
                "parent": parent,
                "text": f"turn {turn}",
            },
        )["id"]
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()
    append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": parent, "text": "so, settled?"},
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, batch, _ = delivered(capsys)
    [thread] = batch["threads"]
    assert thread["elided"]["messages"] > 0, "the bound did not engage"
    assert [a["widget"] for a in thread["actions"]] == ["gm"]
    # The question survives the elision that took its neighbours.
    carrying = [m for m in thread["messages"] if m.get("markup")]
    assert [m["id"] for m in carrying] == [asked["id"]], json.dumps(thread["messages"])
    assert 'id="m-cap"' in carrying[0]["markup"]
    assert chose["id"] == thread["actions"][0]["id"]


def test_a_settling_reaction_wakes_only_when_it_answers_the_agent(
    page_dir, sessionless, capsys
):
    serving(page_dir, 1)
    publish(page_dir)
    session_model.cmd_waiting(page_dir)
    question = thread_model.cmd_comment(
        page_dir, "", "", "", "Forty?", "", obligation=True
    )
    quiet = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "token": "shorten"},
    )
    assert quiet["attention"] is False
    assert service_model.unacknowledged(events_model.read_events(page_dir), 0) == []
    answer = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": question["id"], "token": "keep"},
    )
    assert answer["attention"] is True
    assert session_model.cmd_wait(page_dir) == 0
    payload, _, events = printed(capsys.readouterr().out)
    [shown] = events
    assert shown["id"] == answer["id"] and shown["token"] == "keep"
    assert "answer" not in shown
    assert page_state(page_dir)["pending"] == 1
    delivery_model.receive_delivery(payload["id"])
    assert page_state(page_dir)["pending"] == 0
    restored = append_command(
        page_dir, {"kind": "undo", "author": "user", "undoes": answer["id"]}
    )
    assert restored["attention"] is True
    ordinary = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": question["id"],
            "text": "No further question.",
        },
    )
    mark = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": ordinary["id"], "token": "keep"},
    )
    assert mark["attention"] is False


def test_successful_replies_require_an_exact_agent_answer():
    from leaf.thread import successful_replies

    comment = {
        "kind": "comment",
        "author": "user",
        "id": "input",
    }
    answer = {
        "kind": "reply",
        "author": "agent",
        "seq": 2,
        "parent": "root",
        "responds": comment["id"],
        "text": "Checked",
    }
    for changes, success in (
        ({}, True),
        ({"failure": "turn_failed"}, False),
        ({"parent": "input", "responds": "later-input"}, False),
        ({"parent": "input", "responds": None}, False),
        ({"author": "user"}, False),
        ({"kind": "comment"}, False),
    ):
        reply = {**answer, **changes}
        events = [comment, reply]
        expected = [reply] if success else []
        assert successful_replies(events, "input") == expected


def test_the_reference_names_each_field_a_delivered_event_adds():
    """`references/event-batches.md` lists what a delivery adds to each logged event;
    `DELIVERY` declares the same fields."""
    import re

    text = (SKILL_ROOT / "references" / "event-batches.md").read_text()
    listed = text.split("Events keep their stored fields", 1)[1].split("\n\n", 2)[1]
    named = set(re.findall(r"`([a-z_]+)\b", listed))
    items = delivery_model.DELIVERY.schema["properties"]["batches"]["items"]
    declared = items["properties"]["events"]["items"]["properties"]
    assert set(declared) <= named
    assert set(re.findall(r"^- `([a-z_]+)`", listed, re.MULTILINE)) <= set(declared)


def test_every_delivery_an_eval_pastes_is_the_envelope_leaf_writes():
    """An eval case that pastes a delivery scores the shipped instructions against
    that envelope, so a change to `DELIVERY` fails here until the case is frozen
    again with `freeze_delivery`."""
    import yaml

    from leaf.registry.schema import schema_error, with_leaf_resources

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict | list):
            for item in value.values() if isinstance(value, dict) else value:
                yield from strings(item)

    pasted = [
        (case.parent.name, json.loads(line))
        for case in sorted((ROOT / "evals").glob("*/case.yaml"))
        for text in strings(yaml.safe_load(case.read_text()))
        for line in text.splitlines()
        if line.lstrip().startswith('{"format"') and "leaf-delivery/" in line
    ]
    assert pasted
    for case, envelope in pasted:
        assert envelope.pop("format") == delivery_model.DELIVERY.format, case
        error = schema_error(
            with_leaf_resources(delivery_model.DELIVERY.schema), envelope
        )
        assert error is None, f"{case}: {error}"


def test_a_pick_carries_the_questions_still_waiting_about_its_decision(page_dir):
    """An action on a decision carries, in `waiting`, the agent's questions that still
    wait on the user in a thread about that decision, so the agent can judge which the
    pick settles; a question in a thread elsewhere stays out."""
    source = PAGE.replace(
        "</section>",
        '</section><section id="ship-ask"><h2>Ship on Friday?</h2>'
        '<lf-options id="permit" choose><lf-option id="publish">Publish</lf-option>'
        '<lf-option id="hold">Keep it private</lf-option></lf-options></section>'
        '<p id="aside">An aside.</p>',
    )
    (page_dir / "index.html").write_text(source)
    publish(page_dir)

    def asked(anchor):
        root = append_carried_log_record(
            page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Show me.",
                "anchor": {"section": anchor},
            },
        )
        return append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "revision": 1,
                "parent": root["id"],
                "responds": root["id"],
                "text": "Try it before choosing.",
                "obligation": True,
            },
        )["id"]

    about = asked("ship-ask")
    asked("aside")
    pick = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "permit",
            "action": "choose",
            "detail": {"value": ["publish"]},
        },
    )
    [batch] = freeze_events(page_dir, [pick])["batches"]
    [event] = batch["events"]
    assert event["waiting"] == [
        {"id": f"message:{about}", "text": "Try it before choosing."}
    ]
    assert any("`waiting`" in batch["handling"][clause] for clause in event["handling"])
