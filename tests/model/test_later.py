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
