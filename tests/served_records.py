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
        },
    }


def serialized() -> str:
    return json.dumps(build(), indent=2) + "\n"


if __name__ == "__main__":
    RECORDS.write_text(serialized())
