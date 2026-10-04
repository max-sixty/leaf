"""The served thread and workflow records the runtime's Node tests build on.

`served_records.json` holds records exactly as `/api/state` serves them, folded here
through `model_folds.reading` rather than written by hand, so a Node test starts from
every field the server sends and cannot omit one the runtime relies on. `thread` and
`workflow` are one record of each, which `served.mjs` hands out for a test to change
only the fields the server sends; `readings` holds whole served readings whose
premise is the case under test. `test_model_folds` fails when the committed file
drifts from this fold; rewrite it with:

    uv run tests/served_records.py
"""

import json
from pathlib import Path

from interact_support import model_layer
from leaf.agent_state import queues
from model_folds import leaf_page, reading

RECORDS = Path(__file__).with_name("served_records.json")
PAGE = leaf_page("Served records", '<h1 id="h">Steps</h1><p id="p">Two steps.</p>')


def _served(events: tuple[dict, ...]) -> dict:
    state = reading(PAGE, events)
    return {"threads": state["thread"]["threads"], "workflows": state["workflows"]}


def build() -> dict:
    """A thread the agent answered and the user has read, which is nobody's turn, and
    the workflow of a comment still waiting for the agent to pick it up; then the
    readings named for their case."""
    records = _served(
        (
            {"kind": "comment", "text": "Is the second step right?"},
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Agent",
                "parent": "e1",
                "responds": "e1",
                "text": "Yes.",
            },
            {"kind": "read", "messages": [{"message": "e2", "version": "e2"}]},
            {"kind": "comment", "text": "And the third?"},
        )
    )
    threads = {thread["id"]: thread for thread in records["threads"]}
    workflows = {workflow["id"]: workflow for workflow in records["workflows"]}
    return {
        "thread": threads["e1"],
        "workflow": workflows["e4"],
        "readings": {
            # The agent asks a question over a board it sent, and the user moves a
            # card on it without answering: the thread is the user's to answer, and
            # the move, which owes nothing, stands in it without holding it.
            "frozen move owes nothing": _served(
                (
                    {"kind": "comment", "text": "Lay the feeder work out on a board."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e1",
                        "responds": "e1",
                        "text": "Here is the board. Which card goes first?",
                        "awaits": True,
                        "markup": model_layer()["lf-board"]["x-example"],
                    },
                    {
                        "kind": "action",
                        "widget": "feeder-board",
                        "action": "move",
                        "detail": {
                            "card": "card-baffle",
                            "to": "col-doing",
                            "rank": "0i",
                        },
                    },
                )
            ),
            # Something on each side: an open Ask, a question left in prose and a
            # reply that failed are on the user; a comment owed a reply and a task
            # on an answered thread are on the agent.
            "queues on both sides": _queued(
                (
                    {"kind": "comment", "text": "Weekly?"},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e1",
                        "responds": "e1",
                        "text": "Weekly or daily?",
                        "awaits": True,
                    },
                    {"kind": "comment", "text": "Tighten this."},
                    {"kind": "comment", "text": "Rebuild the chart."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e4",
                        "responds": "e4",
                        "text": "On it after CI.",
                    },
                    {
                        "kind": "task",
                        "author": "agent",
                        "agent": "Agent",
                        "session": "served-records",
                        "subject": {"kind": "thread", "id": "e4"},
                        "title": "Rebuild the chart",
                    },
                    {"kind": "comment", "text": "Retitle it."},
                    {
                        "kind": "reply",
                        "author": "agent",
                        "agent": "Agent",
                        "parent": "e7",
                        "responds": "e7",
                        "failure": "turn_failed",
                        "text": "No answer is coming.",
                    },
                )
            ),
        },
    }


ASK_PAGE = leaf_page(
    "Served queues",
    '<lf-ask id="pick-ask"><h2>Which one?</h2><lf-options id="pick" choose>'
    '<lf-option id="one">One</lf-option><lf-option id="two">Two</lf-option>'
    "</lf-options></lf-ask>",
)


def _queued(events: tuple[dict, ...]) -> dict:
    """The four readings `agent_state.queues` selects from, as the browser is handed
    them, and the two queues Python selects from them."""
    state = reading(ASK_PAGE, events)
    asks = state["views"]["1"]["document"]["asks"]["user"]
    asks += state["thread"]["asks"]["user"]
    served = {
        "asks": asks,
        "threads": state["thread"]["threads"],
        "workflows": state["workflows"],
        "tasks": state["tasks"],
    }
    return {**served, "queues": queues(**served)}


def serialized() -> str:
    return json.dumps(build(), indent=2) + "\n"


if __name__ == "__main__":
    RECORDS.write_text(serialized())
