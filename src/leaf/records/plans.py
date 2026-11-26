"""The plan: the agent's current breakdown of the page's work, as one outline.

A plan is the newest `plan` event's `steps`, an outline in order. Each step has a
`depth`, 0 for a goal and one more for each level under it, so a step belongs to the
nearest step above it at one less depth. The schema caps depth at 8, which keeps the
served tree well within the nesting its readers and JSON encoders take. A step is a
heading, a `title` that groups the steps under it, or it names an `item`, an
obligation's id, a to-do's among them, and shows that item's title and standing, in
the fields every record uses (`standing`). `leaf task plan` writes the whole outline
each time, so reshaping the breakdown is a rewrite, and an empty outline clears it.

No step's standing is written into the plan. A step naming an item reads the item's
standing as the page serves it, a to-do's start as activity has aged it
(`WorkReading.plan`), and a heading reads the records its steps name as any place
holding several records does (`standing.leading`), and once none is open, done, or
failed where one of them failed, however deep. So the plan stays true after the agent
stops: a start that outlived its turn reads blocked (`activity`), and the steps read
what was finished and what is still owed. A standing the plan's writer sets, the
alternative, holds until the next rewrite, so a step the agent left reads under way long
after its turn ended, and the step has no end that could say where its result is. Each
step of work is therefore a record with an end of its own: the agent's a to-do, which
`leaf task end` ends with where its result is (`detail`), the user's an obligation.
`leaf task plan` opens a to-do for each step written as `todo` and names it in the plan
by its id (`tasks.cmd_plan`), so an outline of new work is one command, and a later rewrite
names that step by the id the plan printed.

The plan keeps the breakdown apart from what is owed. A to-do or an obligation keeps its
own owner, rules and end (`todos`, `obligations`); a plan only arranges them under
headings. So a rewrite that leaves out an open to-do ends nothing: the to-do stays on its
list, outside the plan, until the agent ends it. This is the shape the user chose over
giving to-dos a parent, which would have needed rules wherever a to-do ends (a stamp's
`--completes`, `leaf task end`) and left obligations out of the tree, over grouping
to-dos by the element they stand on, which shows no steps ahead, and over writing the
plan into the page's markup, which makes every reshape a revision.

Admission (`plan_error`) refuses a step naming an item the page doesn't hold, and a
heading with no step under it, whose standing nothing would decide. A step written more
than one level below the step before it reads one level below that step, and a first
step below the root reads as a goal (`_depths`), so `leaf task plan` says so beside the
plan it wrote (`skipped_levels`) rather than refusing an outline that draws whole.
Every reader takes the plan from `plan_reading`: each step with its standing
(`next_actor`, `state`, `reason`, `outcome`), the `item` it names (none for a
heading), the start `running` on a named to-do and `since`, when that start began,
`detail`, the words a finished to-do's end gave, its `steps`, and `done` of `total`,
its steps that ended done of those not dropped. A step naming an obligation a later
version removed reads as dropped.

The floating panel's On <agent> shows the plan above its list while one stands, and On
Me can group its items under the goals whose steps name them (`panel/floating-panel.js`,
`panel/queue-walk.js`). `conversation-loop.md`, "When to write", asks an agent for a plan
when its work runs to several steps and past the turn it is in.

Experimental, like to-dos and the lists; nothing outside this repository depends on it.
"""

from leaf.base.findings import Finding
from leaf.base.standing import ended, leading

_STANDING = ("next_actor", "state", "reason", "outcome")


def _item_standing(item: dict) -> dict:
    """Where a step naming `item` stands: the item's own standing, and done for an
    open one nobody owes a move on, a question whose thread was resolved
    (`obligations`)."""
    if item["state"] == "waiting" and item["next_actor"] is None:
        return ended("done")
    return {key: item[key] for key in _STANDING}


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


def plan_error(event: dict, todos: list[dict], known: set[str]) -> Finding | None:
    """Why the append door refuses a `plan` event, or None. `todos` are every to-do
    on the page and `known` the ids of every obligation a step may name, open or not
    (`WorkReading.plan_ids`)."""
    if event["kind"] != "plan":
        return None
    known = known | {todo["id"] for todo in todos}
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


def plan_reading(events: list, withdrawn: set, records: list[dict]) -> dict | None:
    """The plan in force as a tree, its items read from `records`, the page's
    obligation records, or None when the agent has written none or cleared it."""
    event = latest_plan(events, withdrawn)
    if event is None or not event["steps"]:
        return None
    by_id = {record["id"]: record for record in records}

    def node(step: dict) -> dict:
        if "item" not in step:
            # A heading's standing is the records' under it, read once they are
            # (`_settle`).
            return {"title": step["title"], "item": None}
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
            "detail": item["end"]["detail"] if item and item["end"] else None,
            "waiting_on": item["waiting_on"] if todo else None,
        }

    root: dict = {"steps": []}
    path: list[dict] = [root]
    for step, depth in zip(event["steps"], _depths(event["steps"]), strict=True):
        del path[depth + 1 :]
        child: dict = {
            "running": None,
            "since": None,
            "detail": None,
            "waiting_on": None,
            **node(step),
            "steps": [],
        }
        path[-1]["steps"].append(child)
        path.append(child)
    for goal in root["steps"]:
        _settle(goal, by_id)
    return {
        "id": event["id"],
        "ts": event["ts"],
        "agent": event.get("agent"),
        "session": event.get("session"),
        "steps": root["steps"],
    }


def _settle(node: dict, by_id: dict[str, dict]) -> list[dict]:
    """Read the standing of each heading at and under `node` from the records its steps
    name (`_heading_standing`), count each step's steps that ended done of those not
    dropped, and return the records named at and under `node`, `by_id` holding them."""
    beneath: list[dict] = []
    for child in node["steps"]:
        beneath.extend(_settle(child, by_id))
    if node["item"] is None:
        node.update(_heading_standing(beneath))
    kept = [child for child in node["steps"] if child["outcome"] != "dropped"]
    node["done"] = sum(child["outcome"] == "done" for child in kept)
    node["total"] = len(kept)
    own = by_id.get(node["item"]["id"]) if node["item"] else None
    return [*beneath, own] if own else beneath


def _heading_standing(beneath: list[dict]) -> dict:
    """A heading's standing from `beneath`, the records its steps name at any depth:
    that of the open record `leading` picks, and once none is open, dropped where every
    one was dropped, failed where one failed, and done otherwise."""
    if lead := leading(beneath):
        return {key: lead[key] for key in _STANDING}
    kept = [record for record in beneath if record["outcome"] != "dropped"]
    if not kept:
        return ended("dropped")
    failed = any(record["outcome"] == "failed" for record in kept)
    return ended("failed" if failed else "done")
