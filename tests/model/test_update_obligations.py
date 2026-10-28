"""The obligation a user's update publishes: one record per update an operation
answers, named by every workflow that delivers toward it, and listed once on the lists
by its next actor."""

import model_folds as model
from interact_support import (
    PAGE,
    append_carried_log_record,
    append_command,
    declare_on_page,
    last_deliverable_seq,
    publish,
    queue_board_registry,
    receive_through,
    state_json,
)

from leaf import activity as activity_model
from leaf import event_log as events_model
from leaf import thread as thread_model
from leaf.served_state.context import read_page


def _owed_answers(page_dir, reading):
    """The answers `reading` (`blocking_obligations` or `turn_obligations`) holds the
    agent to, by input and operation, with the delivery's reference left off."""
    work = read_page(page_dir, events_model.read_events(page_dir)).work
    state = {**work.presence, "activity": work.activity}
    return [
        (
            item["input"],
            {
                key: value
                for key, value in item["answer"].items()
                if key in {"kind", "parent", "responds", "action"}
            },
        )
        for item in reading(state, watched=False)
    ]


def test_two_messages_in_a_row_publish_one_record_both_workflows_name(page_dir):
    """The reply to the newer message answers both, so only the newer one publishes a
    record, and the older one's workflow delivers toward it too."""
    publish(page_dir)
    first = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "A"}
    )
    second = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": first["id"], "text": "B"},
    )
    state = state_json(page_dir)
    [record] = [
        item for item in state["obligations"] if item["source"]["kind"] == "update"
    ]
    assert (record["id"], record["status"], record["next_actor"]) == (
        f"update:{second['id']}",
        "open",
        "agent",
    )
    assert sorted(
        (item["input"], item["obligation"]) for item in state["workflows"]
    ) == sorted([(first["id"], record["id"]), (second["id"], record["id"])])
    assert [row["id"] for row in state["queues"]["on_agent"]] == [record["id"]]
    assert [item["id"] for item in state["activity"]["obligations"]] == [record["id"]]

    thread_model.post_reply(
        page_dir,
        {"parent": second["id"], "responds": second["id"]},
        "Answered together",
    )
    answered = state_json(page_dir)
    assert answered["workflows"] == []
    assert answered["queues"]["on_agent"] == []
    [done] = [
        item for item in answered["obligations"] if item["source"]["kind"] == "update"
    ]
    assert (done["id"], done["status"], done["next_actor"]) == (
        record["id"],
        "answered",
        None,
    )


OPTIONS = (
    '<lf-options id="choice" choose><lf-option id="a">A</lf-option>'
    '<lf-option id="b">B</lf-option></lf-options>'
)


def _listed_once(state) -> dict:
    """The lists of view 1, checked against the rule that keeps a widget the user
    discussed from being listed twice: a record stands on at most one list, On <agent>
    lists update records and to-dos alone, and every widget record the agent holds
    stands beside an open update record the agent owes in the same thread."""
    view = state["views"]["1"]
    queues = view["queues"]
    records = {record["id"]: record for record in view["obligations"]}
    listed = [row["id"] for row in queues["on_user"] + queues["on_agent"]]
    assert len(listed) == len(set(listed))
    assert {row["kind"] for row in queues["on_agent"]} <= {"update", "todo"}
    owing = [
        record
        for record in records.values()
        if record["source"]["kind"] == "update" and record["next_actor"] == "agent"
    ]
    for record in records.values():
        if record["source"]["kind"] == "widget" and record["next_actor"] == "agent":
            assert any(
                record["thread"] is None or other["thread"] == record["thread"]
                for other in owing
            )
    return {
        "on_user": [row["id"] for row in queues["on_user"]],
        "on_agent": [row["id"] for row in queues["on_agent"]],
        "agents": sorted(
            record["id"]
            for record in records.values()
            if record["status"] == "open" and record["next_actor"] == "agent"
        ),
    }


def test_a_widget_the_user_discusses_is_listed_once_through_the_comment():
    """A comment on a widget's obligation, or a reply after a widget an agent sent
    into a thread, hands the widget to the agent until the agent answers. The widget's
    record turns the agent's and the user's message publishes its own; On <agent> lists
    the message's alone, and On me no longer lists the widget."""
    document = model.leaf_page("Questions", OPTIONS)
    comment = {
        "kind": "comment",
        "id": "c1",
        "author": "user",
        "text": "What does this mean?",
        "anchor": {"section": "a", "quote": "A"},
    }
    assert _listed_once(model.reading(document, [comment])) == {
        "on_user": [],
        "on_agent": ["update:c1"],
        "agents": ["update:c1", "widget:choice"],
    }

    opened = {"kind": "comment", "id": "t", "author": "user", "text": "Help me pick."}
    asked = {
        "kind": "reply",
        "id": "asked",
        "author": "agent",
        "parent": "t",
        "responds": "t",
        "text": "Which route?",
        "markup": OPTIONS.replace('id="', 'id="t-'),
    }
    later = {"kind": "reply", "id": "r", "author": "user", "parent": "t", "text": "C?"}
    frozen = model.leaf_page("Questions", "<p>Nothing to answer here.</p>")
    assert _listed_once(model.reading(frozen, [opened, asked, later])) == {
        "on_user": [],
        "on_agent": ["update:r"],
        "agents": ["update:r", "widget:t-choice"],
    }


def test_stop_and_idle_hold_the_agent_to_the_answers_it_owed_before(claimed):
    """The answers that hold the turn and refuse idling are the ones the page owed
    before updates published records: the newest of two messages in a row, each card
    of a finished queue frozen in a thread, a pick on a page obligation, and nothing for
    a draft edit or a message a harness handed back."""
    declare_on_page(
        claimed, lambda registry: registry.update(queue_board_registry(registry))
    )
    (claimed / "index.html").write_text(
        PAGE.replace("<lf-options>", '<lf-options id="choice" choose>').replace(
            "</section>",
            '<lf-draft id="note"><pre>Blue room.</pre></lf-draft></section>',
        )
    )
    publish(claimed)
    first = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "A"}
    )
    second = append_carried_log_record(
        claimed,
        {"kind": "reply", "author": "user", "parent": first["id"], "text": "B"},
    )
    handed_back = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "C"}
    )
    thread_model.post_reply(
        claimed,
        {"parent": handed_back["id"], "responds": handed_back["id"]},
        "The agent's turn ended without an answer. Send it again to retry.",
        failure="turn_failed",
    )
    board = append_carried_log_record(
        claimed,
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
            "</lf-board>",
        },
    )
    moves = [
        append_command(
            claimed,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "triage",
                "action": "move",
                "detail": {"unit": card, "value": "keep", "rank": rank},
            },
        )
        for card, rank in (("card-a", "i"), ("card-b", "r"))
    ]
    append_command(
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
    receive_through(claimed, last_deliverable_seq(claimed))

    expected = [
        (
            second["id"],
            {"kind": "reply", "parent": second["id"], "responds": second["id"]},
        ),
        *(
            (
                move["id"],
                {"kind": "reply", "parent": board["id"], "responds": move["id"]},
            )
            for move in moves
        ),
        (picked["id"], {"kind": "markup", "action": picked["id"]}),
    ]
    assert _owed_answers(claimed, activity_model.blocking_obligations) == expected
    assert _owed_answers(claimed, activity_model.turn_obligations) == expected
