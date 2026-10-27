"""Later: the user sets an obligation aside until a time or until the agent finishes an
item on its list, and it comes back to On me then, with nothing to wake the agent."""

import model_folds as model
import pytest
from interact_support import refused_on

from leaf.event_log import EventRefused

OPTIONS = (
    '<lf-options id="{id}" choose><lf-option id="{id}-a">A</lf-option>'
    '<lf-option id="{id}-b">B</lf-option></lf-options>'
)
PAGE = model.leaf_page(
    "Questions",
    "<h2>Store</h2>"
    + OPTIONS.format(id="store")
    + "<h2>Notes</h2>"
    + OPTIONS.format(id="notes"),
)
# An hour after the fixture's clock (`model.NOW`), and a day after.
HOUR = "2026-09-19T13:00:00+00:00"
DAY = "2026-09-20T12:00:00+00:00"
MIGRATE = {
    "kind": "todo",
    "author": "agent",
    "owner": "agent",
    "agent": "Claude",
    "session": "s1",
    "subject": {"kind": "page"},
    "title": "Migrate the store",
}


def later(*obligations, **condition):
    return {"kind": "later", "obligations": list(obligations), **condition}


def view(events, now=model.NOW):
    state = model.served_reading(PAGE, events, now=now)
    return state, state["browser"]["views"]["1"]


def record(view, identity):
    return next(item for item in view["obligations"] if item["id"] == identity)


def rows(view, side):
    return [(row["id"], row["also"]) for row in view["queues"][side]]


def test_a_later_on_a_clock_sets_its_records_aside_until_the_time_comes():
    """A Later takes its records off On me onto Later, with no next actor, and names
    the moment it comes due as the reading's next transition, which every reader asks
    again at; read after that moment, the records are back on On me, saying so."""
    events = [later("widget:store", "widget:notes", until=HOUR)]
    state, now = view(events)
    assert rows(now, "on_user") == []
    assert rows(now, "later") == [("widget:store", ["widget:notes"])]
    store = record(now, "widget:store")
    assert (store["status"], store["next_actor"]) == ("open", None)
    assert store["later"] == {
        "event": {
            "id": "e1",
            "kind": "later",
            "seq": 1,
            "ts": model.NOW,
            "author": "user",
        },
        "until": HOUR,
        "after": None,
        "returned": False,
        "beneath": None,
    }
    assert state["activity"]["next_transition_at"] == HOUR

    state, back = view(events, now=HOUR)
    assert rows(back, "later") == []
    assert sorted(row["id"] for row in back["queues"]["on_user"]) == [
        "widget:notes",
        "widget:store",
    ]
    store = record(back, "widget:store")
    assert (store["next_actor"], store["later"]["returned"]) == ("user", True)
    assert state["activity"]["next_transition_at"] is None


def test_a_later_after_the_agents_item_comes_back_when_the_agent_ends_it():
    """`after` names an item on On <agent> by id; the records come back once that item is
    no longer the agent's, here its to-do ending, and not before."""
    events = [MIGRATE, later("widget:store", after="e1")]
    _, waiting = view(events)
    assert rows(waiting, "on_user") == [("widget:notes", [])]
    assert record(waiting, "widget:store")["later"]["after"] == "e1"
    ended = {
        "kind": "todo_end",
        "author": "agent",
        "agent": "Claude",
        "session": "s1",
        "todo": "e1",
        "outcome": "done",
    }
    _, back = view([*events, ended])
    assert sorted(row["id"] for row in back["queues"]["on_user"]) == [
        "widget:notes",
        "widget:store",
    ]
    assert record(back, "widget:store")["later"]["returned"] is True


def test_undo_withdraws_a_later_and_a_newer_one_replaces_its_condition():
    events = [later("widget:store", until=DAY), later("widget:store", until=HOUR)]
    state, now = view(events)
    assert record(now, "widget:store")["later"]["until"] == HOUR
    assert state["activity"]["next_transition_at"] == HOUR
    # The Later it replaced stands beneath it, so the browser can draw its undo.
    assert record(now, "widget:store")["later"]["beneath"]["until"] == DAY
    _, undone = view([*events, {"kind": "undo", "undoes": "e2"}])
    assert record(undone, "widget:store")["later"]["until"] == DAY
    _, both = view(
        [*events, {"kind": "undo", "undoes": "e2"}, {"kind": "undo", "undoes": "e1"}]
    )
    store = record(both, "widget:store")
    assert ("later" not in store, store["next_actor"]) == (True, "user")
    assert [entry["event"]["kind"] for entry in now["undo"]][:1] == ["later"]


def test_a_later_carries_no_attention():
    """Setting a question aside asks the agent for nothing, so admission stamps the
    Later without attention and it wakes no one."""
    _, now = view([later("widget:store", until=HOUR)])
    [entry] = now["undo"]
    assert (entry["event"]["kind"], entry["event"]["attention"]) == ("later", False)


@pytest.mark.parametrize(
    ("events", "code"),
    [
        (
            [
                {
                    "kind": "action",
                    "widget": "store",
                    "action": "choose",
                    "detail": {"value": ["store-a"]},
                },
                later("widget:store", until=HOUR),
            ],
            "later-obligation",
        ),
        ([later("widget:missing", until=HOUR)], "later-obligation"),
        ([later("widget:store", until="2026-09-19T11:00:00+00:00")], "later-past"),
        ([later("widget:store", after="nothing")], "later-after"),
    ],
    ids=["answered", "unknown", "past", "not-on-the-agents-list"],
)
def test_the_door_refuses_a_later_that_would_set_nothing_aside(events, code):
    with pytest.raises(EventRefused) as refused:
        view(events)
    assert refused_on(refused.value).code == code


def test_a_later_names_one_condition():
    with pytest.raises(EventRefused) as refused:
        view([later("widget:store", until=HOUR, after="e1")])
    assert refused_on(refused.value).code == "invalid-event"


COMMENT = {"kind": "comment", "text": "Retitle it."}
FAILED = {
    "kind": "reply",
    "author": "agent",
    "agent": "Claude",
    "parent": "e1",
    "responds": "e1",
    "failure": "turn_failed",
    "text": "No answer is coming.",
}
ANSWER = {
    "kind": "reply",
    "author": "agent",
    "agent": "Claude",
    "parent": "e1",
    "responds": "e3",
    "text": "Retitled and shortened.",
}


def test_a_later_after_an_update_waits_for_the_reply_through_a_follow_up():
    """`after` an update the agent owes waits for its reply. A follow-up the user sends
    in that thread moves the debt to the newest input, which the older input's workflow
    names, so the Later keeps waiting until the reply that answers both, and not
    longer: the next comment in the thread is new work, not the item waited for."""
    events = [COMMENT, later("widget:store", after="update:e1")]
    _, waiting = view(events)
    assert rows(waiting, "later") == [("widget:store", [])]
    follow_up = {"kind": "reply", "parent": "e1", "text": "And shorten it."}
    _, followed = view([*events, follow_up])
    assert [row["id"] for row in followed["queues"]["on_agent"]] == ["update:e3"]
    assert rows(followed, "later") == [("widget:store", [])]
    _, answered = view([*events, follow_up, ANSWER])
    assert record(answered, "widget:store")["later"]["returned"] is True
    assert "widget:store" in [row["id"] for row in answered["queues"]["on_user"]]
    again = {"kind": "reply", "parent": "e1", "text": "One more thing."}
    _, newer = view([*events, follow_up, ANSWER, again])
    assert record(newer, "widget:store")["later"]["returned"] is True


def test_a_later_after_an_update_comes_back_when_the_update_is_handed_back():
    events = [COMMENT, later("widget:store", after="update:e1")]
    _, handed_back = view([*events, FAILED])
    assert record(handed_back, "widget:store")["later"]["returned"] is True


def test_an_update_handed_back_to_send_again_can_be_set_aside():
    """A resend On me lists is set aside like any record waiting on the user, and the
    agent's reading of it is unchanged."""
    events = [COMMENT, FAILED]
    _, now = view(events)
    assert [row["id"] for row in now["queues"]["on_user"]] == [
        "widget:store",
        "widget:notes",
        "update:e1",
    ]
    state, aside = view([*events, later("update:e1", until=HOUR)])
    assert rows(aside, "later") == [("update:e1", [])]
    assert "update:e1" not in [row["id"] for row in aside["queues"]["on_user"]]
    assert record(aside, "update:e1")["next_actor"] is None
    assert state["activity"]["next_transition_at"] == HOUR


def test_a_later_ends_once_the_user_acts_on_what_it_set_aside():
    """Answering a set-aside widget spends its Later: undoing the answer leaves the
    widget waiting on the user, not hidden until the old condition holds."""
    chosen = {
        "kind": "action",
        "widget": "store",
        "action": "choose",
        "detail": {"value": ["store-a"]},
    }
    events = [
        later("widget:store", until=DAY),
        chosen,
        {"kind": "undo", "undoes": "e2"},
    ]
    _, now = view(events)
    store = record(now, "widget:store")
    assert (store["status"], store["next_actor"], "later" in store) == (
        "open",
        "user",
        False,
    )
    # A Later set after the act stands.
    _, again = view([*events, later("widget:store", until=DAY)])
    assert record(again, "widget:store")["next_actor"] is None
