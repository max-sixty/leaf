"""Thread identity, frozen markup, and bounded delivery context."""

from functools import lru_cache
from typing import NamedTuple

from leaf.events import (
    action_rests_on,
    active_summaries,
    build_threads,
    event_coordinate,
    spoken_turns,
    taken_back,
)
from leaf.schema import MESSAGE_KINDS
from leaf.structure import SourceDocument


def thread_ids(events: list[dict]) -> set[str]:
    """The id of every thread the log holds, including one whose opening message
    it lost: the namespace a declaration naming a thread (`resolves`,
    `data-sample-threads`) is checked against."""
    return set(thread_names(events).values())


def sample_events(
    document: SourceDocument, events: list[dict], selected: set[str]
) -> list[dict]:
    """Copy the selected thread closures the log holds into a child's log.

    The selection is authored markup naming records the log owns, and the document
    is what starts a page: one served before any thread stands in it — a first
    version, or a page re-created from its source without the log it shipped beside
    — opens its samples the same as any other. So a thread the log does not hold
    reads here as absent and the child begins without it, rather than the
    template's declaration deciding whether the page works at all.

    That leaves a mistyped id to the one reader who can tell it from a page that has
    not been written into yet: `leaf-dev corpus` selects against a history it is
    generating from, where every declared thread exists by construction, and refuses
    one that names nothing."""
    names = thread_names(events)
    memberships = thread_memberships(
        events, names, thread_widgets(thread_structure(events), names), document.within
    )
    return [
        {
            **{key: value for key, value in event.items() if key != "seq"},
            **({"revision": 1} if "revision" in event else {}),
        }
        for event in events
        if selected.intersection(memberships[event["id"]])
    ]


def thread_message(events: list, thread: str, name: str) -> str:
    """The message an event written into `thread` names, when `name` reached it.

    `name` itself where it is a message of the thread. Otherwise the thread through
    its opening comment, or, where the log lost that comment, through the first
    message the thread still holds, as the panel answers it."""
    names = thread_names(events)
    logged = {event["id"] for event in events}
    if names.get(name) == thread and name in logged:
        return name
    if thread in logged:
        return thread
    return next(
        message
        for message, owner in names.items()
        if owner == thread and message != thread
    )


def id_subject(
    events: list,
    page_widgets: set[str],
    thread_by_widget: dict,
    within: dict,
    name: str,
) -> dict | None:
    """The subject any id a command takes names: `{"kind": "widget", "id"}` for a
    widget on the page, `{"kind": "thread", "id"}` for a thread. None where it names
    neither.

    A thread is named by its own id, any message in it, a widget frozen into its
    markup, or any other event whose history it is part of
    (`thread_memberships`). An event on a page widget, a move or a worker's report,
    names that widget, and an undo names what the gesture it withdraws named. A page id cannot collide with any of these:
    `validation.markup.id_errors` refuses an authored id in the shape the log mints,
    and message markup and versions refuse each other's ids."""
    if name in page_widgets:
        return {"kind": "widget", "id": name}
    names = thread_names(events)
    thread = names.get(name) or thread_by_widget.get(name)
    if thread is None:
        event = next((event for event in events if event["id"] == name), None)
        if event is None:
            return None
        if event.get("widget") in page_widgets:
            return {"kind": "widget", "id": event["widget"]}
        if event["kind"] == "undo":
            return id_subject(
                events, page_widgets, thread_by_widget, within, event["undoes"]
            )
        memberships = thread_memberships(events, names, thread_by_widget, within)
        thread = next(iter(memberships[name]), None)
    return {"kind": "thread", "id": thread} if thread is not None else None


def thread_names(events: list) -> dict:
    """Every name that reaches a thread → that thread's id.

    The names are the thread's own id and the id of each message in it, which a
    reply, edit, or resolve names. A thread's id is the id of the comment that
    opened it, and it stays so where the log lost that comment: a reply whose
    parent the log does not hold opens a thread under the parent's id, which the
    runtime's `threadNames` and `build_threads` key it on too. `read_events` skips
    a torn line and keeps reading, and a user who can see the reply is owed the
    rest of the page around it.

    Two readings of the panel's own document resolve a message to its thread, and
    they must answer alike: an Ask and a question naming different threads for one
    message is a disagreement no reader could account for. (`build_threads` walks
    the same relation to a different end — the thread object itself, with its
    resolution — so it keeps its own walk, and answers the same way where the log
    is torn.)"""
    names = {}
    for e in events:
        if e["kind"] == "comment":
            names[e["id"]] = e["id"]
        elif e["kind"] == "reply":
            names[e["id"]] = names.setdefault(e["parent"], e["parent"])
    return names


class ThreadStructure(NamedTuple):
    ids: set
    by_id: dict
    fragments: dict


def logged_fragment(event: dict) -> SourceDocument:
    """The parse of one logged event's frozen markup, shared read-only.

    The log is append-only and a logged event is never rewritten, so its markup is
    one immutable fragment for the page's lifetime, and every reader of the log
    takes this one parse of it. The parse is a function of the markup alone, so it
    is held by that text, which names it exactly whichever page and log it came
    from. Markup a writer hands in has not been admitted yet and is another fact:
    its gate parses it afresh (`validation.admission.check_markup`)."""
    return _fragment(event["markup"])


@lru_cache(maxsize=4096)
def _fragment(markup: str) -> SourceDocument:
    return SourceDocument(markup)


def thread_structure(events: list) -> ThreadStructure:
    """Each logged markup fragment (`logged_fragment`) as the panel's id universe."""
    ids, by_id, fragments = set(), {}, {}
    for e in events:
        if e.get("markup"):
            fragment = logged_fragment(e)
            fragments[e["id"]] = fragment
            ids.update(fragment.ids)
            by_id.update(fragment.by_id)
    return ThreadStructure(ids, by_id, fragments)


def thread_widgets(structure: ThreadStructure, names: dict) -> dict:
    """Widget id → the thread whose frozen markup holds it.

    The relation on its own, apart from `frozen_thread_reading`, which carries it
    alongside the records and words a vocabulary supplies. A caller needing only
    this relation does not load a registry to reach it. It takes the two readings
    rather than the log, so the caller that already holds them does not parse
    every fragment a second time."""
    return {
        widget: names[event_id]
        for event_id, fragment in structure.fragments.items()
        if event_id in names
        for widget in fragment.by_id
    }


def event_threads(event: dict, names: dict, widgets: dict) -> list:
    """The threads one event belongs to — empty for news about the page.

    Every kind that belongs to a thread names it differently, and none of them
    names it outright: a message through the message it answers, a resolve
    through any name in `thread_names`, an action two ways at once. One reading
    of that relation, so a delivery and a projection cannot put the same event
    in different threads.

    An action on a sent widget belongs to the thread that supplied
    its frozen contract. An action also belongs to the thread it settles,
    which admitted `meaning.answer` names — the same key `build_threads` folds on to close
    one. Those are usually different threads and often only the second exists: the
    shipped settling verb is `lf-suggestion`'s decide, whose widget stands on the
    page and in no thread at all. Reading the widget alone left the gesture
    that closes a thread as the one gesture arriving with nothing behind it.

    A `report` carries a widget too and belongs to no thread: `cmd_report`
    validates its target against the active revision's own elements, so one
    can never name a widget an agent sent."""
    kind = event["kind"]
    if kind in MESSAGE_KINDS:
        named = [names.get(event["id"])]
    elif kind == "edit":
        named = [names.get(event["message"])]
    elif kind in {"summary", "thread_title"}:
        named = [event["thread"]]
    elif kind in {"resolve", "unresolve"}:
        named = [names.get(event["parent"])]
    elif kind == "action":
        named = [widgets.get(event["widget"]), event["meaning"].get("answer")]
    else:
        return []
    return [thread for thread in dict.fromkeys(named) if thread]


def thread_memberships(
    events: list, names: dict, widgets: dict, within: dict
) -> dict[str, list[str]]:
    """Event id → every thread whose history that event changes.

    Leaf owns the relation because each event kind names its thread in a
    different way. Some name none directly: a later action on one widget
    supersedes its earlier answer, an undo inherits the gesture's membership, and
    a version note can retract what an answer rested on.

    This is the shared join for wait delivery and sampled thread closures. Current
    resolution still comes from `build_threads`; membership says which raw
    records explain that fold rather than becoming another state projection.
    Read state and the history feed read the direct relation, `event_threads`:
    a move the user made in a thread, rather than every thread it changed.
    """
    memberships: dict[str, list[str]] = {}
    settled_by_coordinate: dict[tuple, list[str]] = {}
    settling_actions: list[tuple[dict, str]] = []
    for event in events:
        if event["kind"] == "undo":
            named = memberships.get(event["undoes"], [])
        else:
            named = event_threads(event, names, widgets)
        if event["kind"] == "action":
            coordinate = event_coordinate(event)
            named = [*named, *settled_by_coordinate.get(coordinate, [])]
            if answered := event["meaning"].get("answer"):
                settled_by_coordinate.setdefault(coordinate, []).append(answered)
                settling_actions.append((event, answered))
        elif event["kind"] == "note" and (restated := set(event.get("restated", []))):
            named = [
                *named,
                *(
                    answered
                    for action, answered in settling_actions
                    if event["revision"] > action["revision"]
                    and restated.intersection(action_rests_on(action, within))
                ),
            ]
        memberships[event["id"]] = list(dict.fromkeys(named))
    return memberships


# What one message is, to a wait consumer holding no page: who said it, what they said,
# the widget they sent with it, and the id an answer names. `seq` is the log
# position, which is also what marks a message as already delivered. A
# `suggestion` is the user proposing exact replacement words rather than
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
    "drawing",
    "suggestion",
    "edited",
)

# How much of one thread a wait digest carries: the message that opened it,
# because it holds the question the thread is about, and the most recent, being
# what a new one answers. `leaf page state <page> <thread>` pages through the
# exchange when a reader needs the middle.
#
# The bound is the point. A delivery reprints the entire thread every time,
# because the agent it is for may hold none of it — so unbounded, the header
# grows with the thread until it alone outgrows the output it prints
# into. That is the one shape acknowledgement cannot recover from: the ack rule
# says to rerun with more capacity, and a rerun prints the same oversize header,
# so nothing can ever be acked and the wait repeats forever.
SHOWN = 8

# What one gesture on a sent widget is, unfolded. `author` for the same reason a
# message carries one: who did it is part of what happened, and the alternative
# is this reading asserting that only the user ever can.
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
    """One thread as a reader away from the panel needs it: its current page
    location or prior anchor when detached, who closed it, and what was said.

    `omit` drops messages by log sequence, which is how a delivery carries the
    exchange its own events land in without printing them twice. `pin` keeps a
    message the bound would otherwise drop. `elided` says how many went, so a
    reader can tell a short thread from a shortened one and knows to
    page through the rest with `leaf page state <page> <thread> --after`."""
    kept = [m for m in thread["msgs"] if m["seq"] not in omit]
    shown = ends_kept(kept, pin)
    return {
        "id": thread["id"],
        "title": thread["title"],
        "anchor": thread["anchor"],
        "detached_from": thread["detached_from"],
        # Who closed it, or null for a thread still open — a thread an agent
        # closed is one the user may never have answered.
        "resolved": thread["resolved"] and thread["resolved"]["author"],
        "elided": {"messages": len(kept) - len(shown), "actions": 0},
        "messages": [
            {key: m[key] for key in MESSAGE_FIELDS if key in m} for m in shown
        ],
    }


def batch_threads(events: list, batch: list, within: dict) -> list:
    """The threads a delivered batch lands in, with what was said before it.

    Every named thread carries its current metadata, even when the batch
    contains all of its messages. An event alone does not carry its title.
    A reply names the message it
    answers, an action its widget and whatever it settles, an undo an event.
    Those ids are the session's own memory of the exchange, and a session that
    has compacted, or one picking the page up, no longer holds it — so the news
    arrives with nothing behind it and the reply goes out against half a
    thread. The envelope carries the rest, once per thread however many of
    its events the batch holds, and leaves out the batch's own messages because
    they follow on the next lines.

    A widget an agent sent is part of the thread too, so `actions` carries
    what the user did to one: without it the question reaches the agent and
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
    as masking one: the user sees their question reopened while the agent is
    told it was answered, and neither side can see the disagreement.

    The actions are unfolded because folding wants the declarations that say
    what a verb's unit is, and they need no window: thread markup is
    frozen, so no version bounds it and no retraction floor reaches it, and undo
    is the whole of what unseats one."""
    names = thread_names(events)
    structure = thread_structure(events)
    widgets = thread_widgets(structure, names)
    memberships = thread_memberships(events, names, widgets, within)
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
    summaries_for = active_summaries(events, threads)
    carried = []
    for t in named:
        if t not in threads:
            continue
        acted = ends_kept(gestures.get(t, []))
        spoken_for = {a["widget"] for a in acted}
        spoken_for |= {
            e["widget"]
            for e in batch
            if e["kind"] == "action" and widgets.get(e["widget"]) == t
        }
        pin = frozenset(
            sent
            for sent, fragment in structure.fragments.items()
            if fragment.by_id.keys() & spoken_for
        )
        digest = thread_digest(threads[t], delivered, pin)
        summaries = summaries_for[t]
        digest["summaries"] = summaries
        covered = {identity for summary in summaries for identity in summary["covers"]}
        # Keep the newest exchange verbatim. The suggested range is one exact,
        # contiguous uncovered run before it, so following the hint can never hide
        # a new message or create a summary on top of one already standing.
        prefix = spoken_turns(threads[t])[:-2]
        runs = []
        run = []
        for message in prefix:
            if message["id"] in covered:
                if run:
                    runs.append(run)
                    run = []
            else:
                run.append(message)
        if run:
            runs.append(run)
        candidate = max(runs, key=len, default=[])
        characters = sum(len(message.get("text", "")) for message in candidate)
        if len(candidate) >= 2 and (len(candidate) >= 8 or characters >= 4000):
            # The range only: what the agent does with it is a `handling` clause.
            digest["summary_hint"] = {
                "from": candidate[0]["id"],
                "through": candidate[-1]["id"],
            }
        digest["elided"]["actions"] = len(gestures.get(t, [])) - len(acted)
        digest["actions"] = acted
        carried.append(digest)
    return carried
