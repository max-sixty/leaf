"""The `leaf task` commands, the agent's writes about its own work: a to-do
(`cmd_create`), a start taking an item in hand (`cmd_start`), a to-do's end
(`cmd_end`) and the plan (`cmd_plan`). Each activates the page's saved source
(`revisioning.activate_source`), then appends through the append door
(`event_contracts`).

What each record means, and what admission accepts of it, is `todos`' and `plans`'.
"""

from pathlib import Path

from leaf.agents.thread import agent_title, fitted
from leaf.base.findings import Finding, Rejected, note
from leaf.base.harness import message_identity
from leaf.base.leases import contract_writer
from leaf.base.state import acting_turn
from leaf.log.event_log import new_event_id
from leaf.records.event_contracts import append_admitted, append_all_admitted
from leaf.records.plans import skipped_levels
from leaf.records.revisioning import activate_source
from leaf.records.todos import PAGE_SUBJECT
from leaf.records.transaction import PageTransaction
from leaf.records.work import page_element, page_subject
from leaf.source.registry.kernel import wait_limit


@contract_writer
def cmd_create(
    page_dir: Path, subject: str, title: str, waiting_on: str | None = None
) -> dict:
    """Create a to-do titled `title` on what `subject` names: a page widget, thread,
    any other element of the page by its id, or `page` for the page as a whole, with
    what its work waits on (`waiting_on`, `todos`) where given; the record. A thread
    attachment supplies discussion context without making a reply complete the task.
    A long title or wait is fitted (`thread.agent_title`, `thread.fitted`)."""
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        named = (
            {"kind": "page"}
            if subject == PAGE_SUBJECT
            else page_subject(page_dir, page.events, subject)
            or page_element(page_dir, subject)
        )
        if named is None:
            raise Rejected(
                [
                    Finding(
                        "unknown-subject",
                        values={"subject": subject, "page": PAGE_SUBJECT},
                    )
                ]
            )
        record, _ = append_admitted(
            page,
            {
                "kind": "todo",
                "author": "agent",
                "subject": named,
                "title": agent_title(title),
                **(
                    {"waiting_on": fitted(waiting_on, wait_limit())}
                    if waiting_on is not None
                    else {}
                ),
            },
        )
        return record


def take_in_hand(page, item: str, text: str, identity: dict) -> dict:
    """Append the start taking `item` in hand with `text` as its line, written as
    `identity`, within `page`, an open `transaction.PageTransaction`; the record.

    The start names the turn the command acts in when the posting session holds the
    page (`state.acting_turn`): the claimant's. That is what lets the turn end over the
    update it started, and what ends the start's hold once that turn has ended and no
    background work of the session carries it on (`activity.start_holds`). Another
    session's start names none. A Claude Code subagent runs as its
    parent's session, so a worker's start is the main thread's.
    `leaf task start` writes this explicit event. Addressed ephemeral replies
    carry their start on the message itself (`thread.post_reply`), and every
    start consumer reads either form through `todos.start_reading`. A start on a page
    declared `idle` reopens it (`activity.declaration`)."""
    turn = acting_turn(page.claim, identity.get("session"))
    record, _ = append_admitted(
        page,
        {
            "kind": "start",
            "author": "agent",
            **identity,
            "item": item,
            "text": text,
            **({"turn": turn} if turn else {}),
        },
    )
    return record


@contract_writer
def cmd_start(page_dir: Path, item: str, text: str) -> dict:
    """Take `item`, an update's event id or an open to-do's id, in hand with `text` as
    its line (`take_in_hand`); the record."""
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        return take_in_hand(page, item, text, message_identity())


@contract_writer
def cmd_end(page_dir: Path, todo: str, outcome: str, detail: str | None) -> dict:
    """End `todo` with `outcome`, `detail` saying where the result is or why there
    is none; the record."""
    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        record, _ = append_admitted(
            page,
            {
                "kind": "todo_end",
                "author": "agent",
                "todo": todo,
                "outcome": outcome,
                **({"detail": detail} if detail is not None else {}),
            },
        )
        return record


@contract_writer
def cmd_plan(page_dir: Path, steps: list) -> dict:
    """Write `steps` as the page's plan; the record. Each step written as `todo` opens
    a to-do with that title on the page, which the plan names by its id; the to-dos
    and the plan land together or not at all (`append_all_admitted`). A long title is
    fitted (`thread.agent_title`), and a step that skips a level is noted
    (`plans.skipped_levels`)."""

    # A step naming an item too says two things, so it goes to the door as written,
    # as does a plan that isn't a list, and the door says what is wrong.
    def opens(step) -> bool:
        return (
            isinstance(step, dict)
            and isinstance(step.get("todo"), str)
            and "item" not in step
        )

    def written(step, ids) -> dict:
        if opens(step):
            kept = {key: value for key, value in step.items() if key != "todo"}
            return {**kept, "item": next(ids)}
        if isinstance(step, dict) and isinstance(step.get("title"), str):
            return {**step, "title": agent_title(step["title"])}
        return step

    with PageTransaction(page_dir) as page:
        activate_source(page_dir, transaction=page)
        listed = steps if isinstance(steps, list) else []
        todos: list[dict] = []
        for step in filter(opens, listed):
            todos.append(
                {
                    "kind": "todo",
                    "author": "agent",
                    "id": new_event_id([*page.events, *todos]),
                    "subject": {"kind": "page"},
                    "title": agent_title(step["todo"]),
                }
            )
        named = iter(todo["id"] for todo in todos)
        plan = {
            "kind": "plan",
            "author": "agent",
            "steps": [written(step, named) for step in listed]
            if isinstance(steps, list)
            else steps,
        }
        *_, record = append_all_admitted(page, [*todos, plan])
        note(*skipped_levels(record["steps"]))
        return record
