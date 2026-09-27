"""The served thread and workflow records the runtime's Node tests build on.

`served_records.json` holds one thread and one workflow exactly as `/api/state` serves
them, folded here through `model_folds.reading` rather than written by hand, so a Node
test starts from every field the server sends and cannot omit one the runtime relies
on. `served.mjs` hands them out and lets a test change only fields the server sends.
`test_model_folds` fails when the committed file drifts from this fold; rewrite it
with:

    uv run tests/served_records.py
"""

import json
from pathlib import Path

from model_folds import leaf_page, reading

RECORDS = Path(__file__).with_name("served_records.json")


def build() -> dict:
    """A thread the agent answered and the user has read, which is nobody's turn, and
    the workflow of a comment still waiting for the agent to pick it up."""
    state = reading(
        leaf_page("Served records", '<h1 id="h">Steps</h1><p id="p">Two steps.</p>'),
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
        ),
    )
    threads = {thread["id"]: thread for thread in state["thread"]["threads"]}
    workflows = {workflow["id"]: workflow for workflow in state["workflows"]}
    return {"thread": threads["e1"], "workflow": workflows["e4"]}


def serialized() -> str:
    return json.dumps(build(), indent=2) + "\n"


if __name__ == "__main__":
    RECORDS.write_text(serialized())
