"""The plan: the agent's current breakdown of the page's work, as one outline.

A plan is the newest `plan` event's `steps`, an outline in order. Each step has a
`depth`, 0 for a goal and one more for each level under it, so a step belongs to the
nearest step above it at one less depth. The schema caps depth at 8, which keeps the
served tree well within the nesting its readers and JSON encoders take. A step is a
heading, a `title` that groups the steps under it, or it names an `item`, a to-do's
id or an obligation's id, and shows that item's title, owner and state. `leaf task
plan` writes the whole outline each time, so reshaping the breakdown is a rewrite,
and an empty outline clears it.

No step's state is written into the plan. A step naming an item reads the item's
state as the page serves it, a to-do's start included once activity has aged it
(`WorkReading.plan`), and a heading reads its steps' (`_heading_state`): done once
every step not dropped is done, under way while one is, and open otherwise. So the
plan stays true after the agent stops: a start lapses with the turn that wrote it
(`todos`), and the steps read what was finished and what is still owed. A state the plan's writer sets,
the alternative, holds until the next rewrite, so a step the agent left reads under
way long after its turn ended, and the step has no end that could say where its result
is. Each step of work is therefore a record with an end of its own: the agent's a
to-do, which `leaf task end` ends with where its result is (`detail`), the user's an
obligation. `leaf task plan` opens a to-do for each step written as `todo` and names it
in the plan by its id (`cmd_plan`), so an outline of new work is one command, and a
later rewrite names that step by the id the plan printed.

The plan keeps the breakdown apart from what is owed. A to-do or an obligation keeps its
own owner, rules and end (`todos`, `obligations`); a plan only arranges them under
headings. So a rewrite that leaves out an open to-do ends nothing: the to-do stays on its
list, outside the plan, until the agent ends it. This is the shape the user chose over
giving to-dos a parent, which would have needed rules wherever a to-do ends (a stamp's
`--completes`, `leaf task end`) and left obligations out of the tree, over grouping
to-dos by the element they stand on, which shows no steps ahead, and over writing the
plan into the page's markup, which makes every reshape a revision.

Admission (`plan_error`) refuses a step naming an item the page doesn't hold, and a
heading with no step under it, whose state nothing would decide. A step written more
than one level below the step before it reads one level below that step, and a first
step below the root reads as a goal (`_depths`), so `leaf task plan` says so beside the
plan it wrote (`skipped_levels`) rather than refusing an outline that draws whole.
Every reader takes the plan from `plan_reading`: each step with its `state`, `owner`
(none for a heading), the `item` it names, the start `running` on a named to-do and
`since`, when that start began, `detail`, the words a finished to-do's end gave, its
`steps`, and `done` of `total`, its steps that are done of those not dropped. A step
naming an obligation a later version removed reads as dropped.

The floating panel's On <agent> shows the plan above its list while one stands, and On
Me can group its items under the goals whose steps name them (`floating-panel.js`,
`queue-walk.js`). `conversation-loop.md`, "When to write", asks an agent for a plan
when its work runs to several steps and past the turn it is in.

Experimental, like to-dos and the lists; nothing outside this repository depends on it.
"""

from pathlib import Path

from .findings import Finding, note

# What an obligation's status reads as on a step. An open one nobody owes a move on,
# a question whose thread was resolved, reads done (`obligations`).
_OBLIGATION_STATES = {"open": "open", "answered": "done", "withdrawn": "dropped"}


def _obligation_state(item: dict) -> str:
    if item["status"] == "open" and item["next_actor"] is None:
        return "done"
    return _OBLIGATION_STATES[item["status"]]


def latest_plan(events: list, withdrawn: set) -> dict | None:
    """The `plan` event in force: the newest one nothing withdrew, or None."""
    return next(
        (
            event
            for event in reversed(events)
            if event["kind"] == "plan" and event["id"] not in withdrawn
        ),
        None,
    )


def _depths(steps: list[dict]) -> list[int]:
    """The depth each of `steps` reads at: as written, but at most one below the step
    before it, so a first step reads as a goal."""
    read = []
    for step in steps:
        read.append(min(step["depth"], read[-1] + 1 if read else 0))
    return read


def plan_error(event: dict, todos: list[dict], items: list[dict]) -> Finding | None:
    """Why the append door refuses a `plan` event, or None. `todos` are every to-do
    on the page and `items` every obligation, open or not."""
    if event["kind"] != "plan":
        return None
    known = {todo["id"] for todo in todos} | {item["id"] for item in items}
    steps = event["steps"]
    depths = _depths(steps)
    for at, step in enumerate(steps):
        if "item" in step and step["item"] not in known:
            return Finding("unknown-plan-item", values={"item": step["item"]})
        if "title" in step and (at + 1 == len(steps) or depths[at + 1] <= depths[at]):
            return Finding("plan-empty-heading", values={"title": step["title"]})
    return None


def skipped_levels(steps: list[dict]) -> list[Finding]:
    """Each of `steps` more than one level below the step before it, or a first step
    below the root, which `plan_reading` places one level below that step."""
    return [
        Finding("plan-depth", values={"step": _label(step), "depth": step["depth"]})
        for step, depth in zip(steps, _depths(steps), strict=True)
        if step["depth"] > depth
    ]


def _label(step: dict) -> str:
    return step.get("title") or step["item"]


def plan_reading(
    events: list, withdrawn: set, todos: list[dict], items: list[dict]
) -> dict | None:
    """The plan in force as a tree, its items read from `todos` and `items`, or None
    when the agent has written none or cleared it."""
    event = latest_plan(events, withdrawn)
    if event is None or not event["steps"]:
        return None
    todos_by_id = {todo["id"]: todo for todo in todos}
    obligations_by_id = {item["id"]: item for item in items}

    def node(step: dict) -> dict:
        if "item" not in step:
            # A heading's state is its steps', read once they are (`_settle`).
            return {"title": step["title"], "owner": None, "item": None}
        if todo := todos_by_id.get(step["item"]):
            running = todo["running"]
            outcome = todo["outcome"]
            return {
                "title": todo["title"],
                "state": "working" if running else todo["state"],
                "owner": "agent",
                "item": {"kind": "todo", "id": todo["id"]},
                "running": running,
                "since": running["ts"] if running else None,
                "detail": outcome["detail"] if outcome else None,
            }
        # An obligation whose source a later version removed is gone from `obligations`, so it
        # reads as withdrawn.
        item = obligations_by_id.get(step["item"])
        return {
            "title": item["prompt"]["text"] if item else None,
            "state": _obligation_state(item) if item else "dropped",
            "owner": "user",
            "item": {"kind": "obligation", "id": step["item"]},
        }

    root: dict = {"steps": []}
    path: list[dict] = [root]
    for step, depth in zip(event["steps"], _depths(event["steps"]), strict=True):
        del path[depth + 1 :]
        child: dict = {
            "running": None,
            "since": None,
            "detail": None,
            **node(step),
            "steps": [],
        }
        path[-1]["steps"].append(child)
        path.append(child)
    for goal in root["steps"]:
        _settle(goal)
    return {
        "id": event["id"],
        "ts": event["ts"],
        "agent": event.get("agent"),
        "session": event.get("session"),
        "steps": root["steps"],
    }


def _settle(node: dict) -> None:
    """Read the state of each heading under and at `node` from its steps, and count
    each step's steps that are done of those not dropped."""
    for child in node["steps"]:
        _settle(child)
    kept = [child for child in node["steps"] if child["state"] != "dropped"]
    if node["item"] is None:
        node["state"] = _heading_state(kept)
    node["done"] = sum(child["state"] == "done" for child in kept)
    node["total"] = len(kept)


def _heading_state(kept: list[dict]) -> str:
    """A heading's state from `kept`, its steps not dropped: dropped with none, under
    way while one is, open while one waits, failed where one failed and the rest are
    done, else done."""
    if not kept:
        return "dropped"
    states = {step["state"] for step in kept}
    return next(
        (state for state in ("working", "open", "failed") if state in states), "done"
    )


def cmd_plan(page_dir: Path, steps: list) -> dict:
    """Write `steps` as the page's plan; the record. Each step written as `todo` opens
    a to-do with that title on the page, which the plan names by its id; the to-dos
    and the plan land together or not at all (`append_all_admitted`). A long title is
    fitted (`thread.agent_title`), and a step that skips a level is noted
    (`skipped_levels`)."""
    from .event_contracts import append_all_admitted
    from .event_log import new_event_id
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction
    from .thread import agent_title

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

    @contract_writer
    def write(page_dir: Path) -> dict:
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

    return write(page_dir)
