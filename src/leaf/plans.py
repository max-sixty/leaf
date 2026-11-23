"""The plan: the agent's current breakdown of the page's work, as one outline.

A plan is the newest `plan` event's `steps`, an outline in order. Each step has a
`depth`, 0 for a goal and one more for each level under it, so a step belongs to the
nearest step above it at one less depth. The schema caps depth at 8, which keeps the
served tree well within the nesting its readers and JSON encoders take. A step is either plain, a `title` with a
`state` the agent sets (`open`, `working`, `done` or `dropped`), or it names an
`item`, an obligation's id, a to-do's among them, and shows that item's title and
standing. Every reader takes a step's standing in the fields every record uses
(`standing`): a plain step is the agent's, its `open` reads `waiting`, `working` reads
`running`, and `done` and `dropped` are how a `done` step ended.
`leaf task plan` writes the whole outline each time, so reshaping the breakdown is a
rewrite, and an empty outline clears it.

The plan keeps the breakdown apart from what is owed. A to-do or an obligation keeps its own
owner, rules and end (`todos`, `obligations`); a plan only arranges them beside plain steps.
So a rewrite that leaves out an open to-do ends nothing: the to-do stays on its list,
outside the plan. A plain step is no promise: work that must stay owed past the turn
is a to-do the plan names. This is the shape the user chose over giving
to-dos a parent, which would have needed rules wherever a to-do ends (a stamp's
`--completes`, `leaf task end`) and left obligations out of the tree, over grouping
to-dos by the element they stand on, which shows no steps ahead, and over writing the
plan into the page's markup, which makes every reshape a revision.

Admission (`plan_error`) refuses a step naming an item the page doesn't hold. A
step written more than one level below the step before it reads one level below that
step, and a first step below the root reads as a goal (`plan_reading`), so
`leaf task plan` says so beside the plan it wrote (`skipped_levels`) rather than
refusing an outline that draws whole. Every reader takes the plan from `plan_reading`:
each step with its standing (`next_actor`, `state`, `reason`, `outcome`), the `item` it
names, the start `running` on a named to-do, `since`, when a running step began, its
`steps`, and `done` of `total`, its children that ended done of those not dropped. A
step naming an obligation a later version removed reads as dropped.

The floating panel's On <agent> discloses the plan from its progress at the view's
foot, and On Me can group its items under the goals whose steps name them
(`floating-panel.js`, `queue-walk.js`). `conversation-loop.md`,
"When to write", asks an agent for a plan when its work runs to several steps, some of
which may wait on the user.

Experimental, like to-dos and the lists; nothing outside this repository depends on it.
"""

from pathlib import Path

from .findings import Finding, note
from .standing import ended, on

# Where a plain step stands by the state the agent set on it.
_PLAIN = {
    "open": on("agent"),
    "working": {**on("agent"), "state": "running"},
    "done": ended("done"),
    "dropped": ended("dropped"),
}


def _item_standing(item: dict) -> dict:
    """Where a step naming `item` stands: the item's own standing, and done for an
    open one nobody owes a move on, a question whose thread was resolved
    (`obligations`)."""
    if item["state"] == "waiting" and item["next_actor"] is None:
        return ended("done")
    return {key: item[key] for key in ("next_actor", "state", "reason", "outcome")}


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


def plan_error(event: dict, todos: list[dict], items: list[dict]) -> Finding | None:
    """Why the append door refuses a `plan` event, or None. `todos` are every to-do
    on the page and `items` every obligation, open or not."""
    if event["kind"] != "plan":
        return None
    known = {todo["id"] for todo in todos} | {item["id"] for item in items}
    for step in event["steps"]:
        if "item" in step and step["item"] not in known:
            return Finding("unknown-plan-item", values={"item": step["item"]})
    return None


def skipped_levels(steps: list[dict]) -> list[Finding]:
    """Each of `steps` more than one level below the step before it, or a first step
    below the root, which `plan_reading` places one level below that step."""
    found = []
    depth = -1
    for step in steps:
        if step["depth"] > depth + 1:
            found.append(
                Finding(
                    "plan-depth", values={"step": _label(step), "depth": step["depth"]}
                )
            )
        depth = min(step["depth"], depth + 1)
    return found


def _label(step: dict) -> str:
    return step.get("title") or step["item"]


def plan_reading(events: list, withdrawn: set, records: list[dict]) -> dict | None:
    """The plan in force as a tree, its items read from `records`, the page's
    obligation records, or None when the agent has written none or cleared it."""
    event = latest_plan(events, withdrawn)
    if event is None or not event["steps"]:
        return None
    by_id = {record["id"]: record for record in records}
    plans = [e for e in events if e["kind"] == "plan" and e["id"] not in withdrawn]

    def node(step: dict) -> dict:
        if "item" not in step:
            return {
                "title": step["title"],
                **_PLAIN[step["state"]],
                "item": None,
                "running": None,
                "since": _working_since(plans, step["title"])
                if step["state"] == "working"
                else None,
            }
        # An obligation whose source a later version removed is gone from the
        # inventory, so it reads as dropped.
        item = by_id.get(step["item"])
        todo = item is not None and item["source"]["kind"] == "todo"
        running = item["line"] if todo else None
        return {
            "title": item["prompt"]["text"] if item else None,
            **(_item_standing(item) if item else ended("dropped")),
            "item": {"kind": "todo" if todo else "obligation", "id": step["item"]},
            "running": running,
            "since": running["ts"] if running else None,
        }

    root: dict = {"steps": []}
    path = [root]
    for step in event["steps"]:
        del path[step["depth"] + 1 :]
        child = {**node(step), "steps": []}
        path[-1]["steps"].append(child)
        path.append(child)
    _count(root)
    return {
        "id": event["id"],
        "ts": event["ts"],
        "agent": event.get("agent"),
        "session": event.get("session"),
        "steps": root["steps"],
    }


def _count(node: dict) -> None:
    for child in node["steps"]:
        _count(child)
    kept = [child for child in node["steps"] if child["outcome"] != "dropped"]
    node["done"] = sum(child["outcome"] == "done" for child in kept)
    node["total"] = len(kept)


def _working_since(plans: list[dict], title: str) -> str:
    """When the plain step titled `title` began working: the earliest plan of the run
    of newest plans in which it is working throughout."""
    since = plans[-1]["ts"]
    for plan in reversed(plans):
        if not any(
            step.get("title") == title and step.get("state") == "working"
            for step in plan["steps"]
        ):
            break
        since = plan["ts"]
    return since


def cmd_plan(page_dir: Path, steps: list) -> dict:
    """Write `steps` as the page's plan; the record. A long step title is fitted
    (`thread.agent_title`), and a step that skips a level is noted
    (`skipped_levels`)."""
    from .event_contracts import append_admitted
    from .leases import contract_writer
    from .revisioning import activate_source
    from .service import PageTransaction
    from .thread import agent_title

    @contract_writer
    def write(page_dir: Path) -> dict:
        with PageTransaction(page_dir) as page:
            activate_source(page_dir, transaction=page)
            record, _ = append_admitted(
                page,
                {
                    "kind": "plan",
                    "author": "agent",
                    "steps": [
                        {**step, "title": agent_title(step["title"])}
                        if isinstance(step, dict) and isinstance(step.get("title"), str)
                        else step
                        for step in steps
                    ],
                },
            )
            note(*skipped_levels(record["steps"]))
            return record

    return write(page_dir)
