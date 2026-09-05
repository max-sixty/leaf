"""Thread identity, frozen markup, and bounded delivery context."""

from typing import NamedTuple

from leaf.events import action_rests_on, build_threads, taken_back
from leaf.structure import parse_structure


def thread_roots(events: list) -> dict:
    """Message id → the id of the comment that opened its thread.

    Two readings of the panel's own document resolve a reply to its root, and they
    must answer alike: an Ask and a question naming different conversations for one
    message is a disagreement no reader could account for. (`build_threads` walks the
    same relation to a different end — the thread object itself, with its resolution —
    so it keeps its own walk, and answers the same way where the log is torn.)

    A reply whose root the log lost stands as its own thread rather than raising.
    `read_events` skips a line nothing could be done with and keeps reading, and a
    reader who can see the reply is owed the rest of the page around it."""
    root = {}
    for e in events:
        if e["kind"] == "comment":
            root[e["id"]] = e["id"]
        elif e["kind"] == "reply":
            root[e["id"]] = root.get(e["parent"], e["parent"])
    return root


class ThreadStructure(NamedTuple):
    ids: set
    by_id: dict
    fragments: dict


def thread_structure(events: list) -> ThreadStructure:
    """Parse each logged markup fragment once into the panel's id universe."""
    ids, by_id, fragments = set(), {}, {}
    for e in events:
        if markup := e.get("markup"):
            fragment = parse_structure(markup)
            fragments[e["id"]] = fragment
            ids.update(fragment.ids)
            by_id.update(fragment.by_id)
    return ThreadStructure(ids, by_id, fragments)


def thread_widgets(structure: ThreadStructure, roots: dict) -> dict:
    """Widget id → the conversation whose frozen markup holds it.

    The relation on its own, apart from `frozen_thread_reading`, which carries it
    alongside the records and words a vocabulary supplies. A caller needing only
    this relation does not load a registry to reach it. It takes the two readings
    rather than the log, so the caller that already holds them does not parse
    every fragment a second time."""
    return {
        widget: roots[event_id]
        for event_id, fragment in structure.fragments.items()
        if event_id in roots
        for widget in fragment.by_id
    }


def event_threads(event: dict, roots: dict, widgets: dict) -> list:
    """The conversations one event belongs to — empty for news about the page.

    Every kind that belongs to a thread names it differently, and none of them
    names it outright: a message through the message it answers, a resolve
    through any message in the thread, an action two ways at once. One reading
    of that relation, so a delivery and a projection cannot put the same event
    in different conversations.

    An action or request on a sent widget belongs to the conversation that supplied
    its frozen contract. An action also belongs to the conversation it settles,
    which admitted `meaning.answer` names — the same key `build_threads` folds on to close
    one. Those are usually different threads and often only the second exists: the
    shipped settling verb is `lf-suggestion`'s accept, whose widget stands on the
    page and in no conversation at all. Reading the widget alone left the gesture
    that closes a thread as the one gesture arriving with nothing behind it.

    A `report` carries a widget too and belongs to no conversation: `cmd_report`
    validates its target against the active revision's own elements, so one
    can never name a widget an agent sent."""
    kind = event["kind"]
    if kind in {"comment", "reply"}:
        named = [roots.get(event["id"])]
    elif kind == "edit":
        named = [roots.get(event["message"])]
    elif kind in {"resolve", "unresolve"}:
        parent = event["parent"]
        named = [roots.get(parent) or (parent if parent in roots.values() else None)]
    elif kind in {"action", "request"}:
        named = [
            widgets.get(event["widget"]),
            event["meaning"].get("answer") if kind == "action" else None,
        ]
    else:
        return []
    return [thread for thread in dict.fromkeys(named) if thread]


def thread_memberships(
    events: list, roots: dict, widgets: dict, within: dict
) -> dict[str, list[str]]:
    """Event id → every conversation whose history that event changes.

    Leaf owns the relation because each event kind names its conversation in a
    different way. Some name none directly: a later action on one widget
    supersedes its earlier answer, an undo inherits the gesture's membership, and
    a version note can retract what an answer rested on.

    This is the shared join for exact event selection and wait delivery. Current
    resolution still comes from `build_threads`; membership says which raw
    records explain that fold rather than becoming another state projection.
    """
    memberships: dict[str, list[str]] = {}
    settled_by_coordinate: dict[tuple, list[str]] = {}
    settling_actions: list[tuple[dict, str]] = []
    for event in events:
        if event["kind"] == "undo":
            named = memberships.get(event["undoes"], [])
        elif event["kind"] == "receipt":
            named = memberships.get(event["request"], [])
        else:
            named = event_threads(event, roots, widgets)
        if event["kind"] == "action":
            coordinate = tuple(event["meaning"]["coordinate"])
            named = [*named, *settled_by_coordinate.get(coordinate, [])]
            if root := event["meaning"].get("answer"):
                settled_by_coordinate.setdefault(coordinate, []).append(root)
                settling_actions.append((event, root))
        elif event["kind"] == "note" and (restated := set(event.get("restated", []))):
            named = [
                *named,
                *(
                    root
                    for action, root in settling_actions
                    if event["revision"] > action["revision"]
                    and restated.intersection(action_rests_on(action, within))
                ),
            ]
        memberships[event["id"]] = list(dict.fromkeys(named))
    return memberships


# What one message is, to a wait consumer holding no page: who said it, what they said,
# the widget they sent with it, and the id an answer names. `seq` is the log
# position, which is also what marks a message as already delivered. A
# `suggestion` is the reader proposing exact replacement words rather than
# describing a change, and the loop owes it a different answer — taken verbatim,
# or declined with a reason — so a digest that dropped the flag rendered it as
# ordinary prose and lost the obligation with it.
MESSAGE_FIELDS = (
    "id",
    "seq",
    "author",
    "agent",
    "text",
    # A reaction says its word where a comment says its text, so a thread that
    # grew out of a mark reads as the mark it started from rather than as a
    # message with nothing in it.
    "token",
    "markup",
    "suggestion",
    "edited",
)

# How much of one conversation a wait digest carries: the message that opened it,
# because it holds the question the thread is about, and the most recent, being
# what a new one answers. `leaf events --thread` selects the exchange whole when
# a reader needs the middle.
#
# The bound is the point. A delivery reprints the entire thread every time,
# because the agent it is for may hold none of it — so unbounded, the header
# grows with the conversation until it alone outgrows the output it prints
# into. That is the one shape acknowledgement cannot recover from: the ack rule
# says to rerun with more capacity, and a rerun prints the same oversize header,
# so nothing can ever be acked and the wait repeats forever.
SHOWN = 8

# What one gesture on a sent widget is, unfolded. `author` for the same reason a
# message carries one: who did it is part of what happened, and the alternative
# is this reading asserting that only the reader ever can.
ACTION_FIELDS = ("id", "seq", "author", "widget", "action", "detail")


def ends_kept(items: list, pin: frozenset = frozenset()) -> list:
    """The first, anything pinned, and the most recent, where a run outgrows
    `SHOWN`.

    A pin outranks the bound because some of what the bound would drop is what
    the rest is read against. Pins come from the actions the same digest
    carries, which the bound has already capped, so the whole stays bounded at
    twice `SHOWN`."""
    if len(items) <= SHOWN:
        return items
    keep = {0, *range(len(items) - SHOWN + 1, len(items))}
    keep |= {i for i, item in enumerate(items) if item.get("id") in pin}
    return [items[i] for i in sorted(keep)]


def thread_digest(
    thread: dict, omit: frozenset = frozenset(), pin: frozenset = frozenset()
) -> dict:
    """One conversation as a reader away from the panel needs it: the passage it
    hangs on, who closed it, and what was said.

    `omit` drops messages by log sequence, which is how a delivery carries the
    exchange its own events land in without printing them twice. `pin` keeps a
    message the bound would otherwise drop. `elided` says how many went, so a
    reader can tell a short conversation from a shortened one and knows to
    read the exact records with `leaf events --thread`."""
    kept = [m for m in thread["msgs"] if m["seq"] not in omit]
    shown = ends_kept(kept, pin)
    return {
        "id": thread["root"]["id"],
        "anchor": thread["root"].get("anchor"),
        # Who closed it, or null for a thread still open — a thread an agent
        # closed is one the reader may never have answered.
        "resolved": thread["resolved"] and thread["resolved"]["author"],
        "elided": {"messages": len(kept) - len(shown), "actions": 0},
        "messages": [
            {key: m[key] for key in MESSAGE_FIELDS if key in m} for m in shown
        ],
    }


def batch_threads(events: list, batch: list, within: dict) -> list:
    """The conversations a delivered batch lands in, with what was said before it.

    A root comment states its own anchor and needs no history, and that is the
    whole of what a delivered event carries: a reply names the message it
    answers, an action its widget and whatever it settles, an undo an event.
    Those ids are the session's own memory of the exchange, and a session that
    has compacted, or one picking the page up, no longer holds it — so the news
    arrives with nothing behind it and the reply goes out against half a
    conversation. The envelope carries the rest, once per thread however many of
    its events the batch holds, and leaves out the batch's own messages because
    they follow on the next lines.

    A widget an agent sent is part of the conversation too, so `actions` carries
    what the reader did to one: without it the question reaches the agent and
    the answer does not, and the reply reopens something already settled.
    `page state` gets none of these, because it folds them into its own `state`
    list with the thread named, and one fact read twice in one object is a fact
    that can differ from itself.

    `within` is the published page's containment, which the caller reads without
    a vocabulary. A delivery may not raise, and loading a page's vendored
    registry is a gate — a page vendored before the layer last changed fails it
    by design — but containment was never the vocabulary's to answer. Folding
    with no page at all was the alternative, and it would show a settlement a
    floor had taken back as standing, and a superseder taken back the same way
    as masking one: the reader sees their question reopened while the agent is
    told it was answered, and neither side can see the disagreement.

    The actions are unfolded because folding wants the declarations that say
    what a verb's unit and facet are, and they need no window: thread markup is
    frozen, so no version bounds it and no retraction floor reaches it, and undo
    is the whole of what unseats one."""
    roots = thread_roots(events)
    structure = thread_structure(events)
    widgets = thread_widgets(structure, roots)
    memberships = thread_memberships(events, roots, widgets, within)
    named = []
    for event in batch:
        for thread in memberships[event["id"]]:
            if thread not in named:
                named.append(thread)
    threads = build_threads(events, within)
    delivered = frozenset(event["seq"] for event in batch)
    withdrawn = taken_back(events)
    gestures: dict = {}
    for event in events:
        if (
            event["kind"] == "action"
            and event["id"] not in withdrawn
            and event["seq"] not in delivered
            and (thread := widgets.get(event["widget"]))
        ):
            gestures.setdefault(thread, []).append(
                {key: event[key] for key in ACTION_FIELDS}
            )
    # A gesture names a widget, and what that widget asked lives only in the
    # message that sent it — page markup is a file read away, thread markup is
    # nowhere but the log. So the message declaring a widget any carried or
    # delivered gesture names is pinned past the bound; eliding it leaves an
    # action naming ids nothing in the envelope spells out, which is the defect
    # this whole reading exists to fix, surviving in the long-thread case.
    carried = []
    for t in named:
        if t not in threads:
            continue
        acted = ends_kept(gestures.get(t, []))
        spoken_for = {a["widget"] for a in acted}
        spoken_for |= {
            e["widget"]
            for e in batch
            if e["kind"] in {"action", "request"} and widgets.get(e["widget"]) == t
        }
        pin = frozenset(
            sent
            for sent, fragment in structure.fragments.items()
            if fragment.by_id.keys() & spoken_for
        )
        digest = thread_digest(threads[t], delivered, pin)
        digest["elided"]["actions"] = len(gestures.get(t, [])) - len(acted)
        digest["actions"] = acted
        if digest["messages"] or digest["actions"]:
            carried.append(digest)
    return carried
