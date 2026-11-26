"""Which of the user's messages waited while a version was saved.

**Where a revision stands in the log.** The log links an agent's answer to the
user's messages it settles (`events.settle`). A reply or note that publishes a
revision names its bundle in `publication`; a read's activation, which no reply or
note names, appends an `activation` that does (`revision_publication.py`), except for
a page's first revision, which no comparison shows against an earlier one and so
needs no place. A revision's place in the log is the seq of the first event naming
its bundle (`revision_places`).

**What a version was saved after** (`saved_after`). A comparison of a version with
the one before it shows changes every one of which that version's revisions made, so
it asks which messages waited at the place of any of them, each judged by the log up
to that place: a comment taken back after one revision went live waited there. `events.build_threads` can't stop between events, since it reads
which gestures were ever taken back before its pass, but its histories keep the place
of everything they hold. So one fold of the log before the version's last revision
went live, under that revision's containment, reads every message as it was said,
none taken back, and from its histories each message's waits follow, each turn of it
from its own place until the first of its answer (`events.settle`), its being
taken back, or the message's, cut where a closing answered for its thread
(``closures``). A bisect of the version's sorted
places finds the latest it waited at, after one pass over each thread's closings, so
the work grows with the log and the turns, not with the threads times the
revisions. The reply or note that answered a message may itself have published the
revision, and stands at its end.

**What the fold accepts missing.** Containment decides only whether an action rests
on an element it names for its owner to hold (`events.action_rests_on`), and so
whether a version restating that element took the action back. The fold reads every
place under the last revision's containment. So where, within one version, an
earlier revision held a restated element in another owner than the last one does,
the actions standing at that revision's place can differ from those its own
containment gives: which action wins a coordinate, and so which threads stand
closed there. The line can then name a message too many or too few, or quote one in
the words it had at another of the version's places. That takes a restated element
moving between owners within one version, beside an action naming it. Judging each
revision under its own containment would keep every action a version took back, to
judge again where another containment took hold, at a cost every reader of the log
would pay (`events.InForce`), for a line that claims an order, not a cause.

Each message is sent as its thread held it at the latest of the version's revisions
it waited at (`EventFacts.message_at`): with its latest rewrite before that place not
taken back by then, or deleted where that rewrite left no words, and not as it reads
now or when the version went live, since a rewrite made after it stopped waiting never
waited across the version, and one taken back since did. Where it waited at two in
different words, the later wording stands: the user's rewrite restates what they asked
for, and the version's later revisions were made with it waiting. The browser reads
that message as a thread reads one (features/change-provenance.js), so no reading of a
message's text lives here. It is computed when a tab asks, with the base's document
(`served_state.service.PageStateService.page_comparison`), and nothing of it is kept
or served otherwise.

That is an order, not a cause, and the words say it as one (features/change-provenance.js).
Nothing reliably knows which revision wrote a given paragraph, so a comparison across
several versions says nothing, and no change names its own revisions: placing each
changed block by the nearest element with an id can credit the wrong revision to a
changed block, and change what a first-to-newest comparison would say.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable
from math import inf
from operator import itemgetter
from typing import TYPE_CHECKING

from leaf.log.events import build_threads, settle

if TYPE_CHECKING:
    from leaf.records.event_facts import EventFacts
    from leaf.source.reading import SourceReading


def revision_places(events: list) -> dict[int, int]:
    """Each revision's place in the log: the seq of the first event naming its bundle
    in `publication`, the reply or note that published it or the `activation` a read
    appended (`revision_publication.py`). A page's first revision may have none."""
    places: dict[int, int] = {}
    for event in events:
        if event.get("publication"):
            places.setdefault(event["revision"], event["seq"])
    return places


def saved_after(
    facts: "EventFacts",
    reading: "Callable[[int], SourceReading]",
    places: dict[int, int],
    revisions,
    stamped: set[int],
    base: int,
    shown: int,
) -> list[dict] | None:
    """The user's messages that waited while the version at revision `shown` was
    saved, compared with the version before it at `base`: each a message that waited
    at the place of any revision after `base` through `shown`, in the order they were
    sent, as its `thread` and the `message` as that thread held it at the latest of
    those places (`EventFacts.message_at`), which the browser reads as a thread reads
    a message. None where a revision `stamped` with a version stands between the two;
    every revision between them has a place among `places`. `facts` reads the page's
    log, and `reading` a revision (`read_revision`).

    One fold of the log before `shown` went live (`events.build_threads`), under the
    containment `reading` gives `shown`, reads every message as it was said, none
    taken back, so its histories keep the place of each turn, answer, closing,
    reopening and rewrite, beside the place each gesture was taken back. A message
    waited at a revision's place where, by the log before it, it had been sent and not
    taken back, had no answer yet, and no closing answered for its thread
    (`events.owed_turns`); the reply or note that answered it stands at its end."""
    if any(base < revision < shown for revision in stamped):
        return None
    span = sorted(
        (places[revision], revision)
        for revision in revisions
        if base < revision <= shown
    )
    if not span:
        return None
    at = [place for place, _revision in span]
    events = facts.events
    prefix = events[: bisect_left(events, at[-1], key=itemgetter("seq"))]
    undone = {event["undoes"]: event["seq"] for event in prefix if "undoes" in event}
    threads = build_threads(prefix, reading(shown).within, withdrawn=set())
    # Each message that waited: its reading, its thread, the latest place it waited.
    found: dict[str, tuple[dict, dict, int]] = {}
    for thread in threads.values():
        latest_open = _latest_open(thread["closures"], at)
        answered = {
            turn["id"]: settlement.answer["seq"]
            for settlement in settle(thread).settlements
            for turn in settlement.turns
        }
        said = {message["id"]: message for message in thread["msgs"]}
        for turn in thread["turns"]:
            # An action on a widget sent in the thread waits in its history beside
            # the turns (`events.settle`), and is no message.
            if (
                turn["author"] == "agent"
                or "undoes" in turn
                or turn["kind"] == "action"
            ):
                continue
            message = turn.get("message", turn["id"])
            end = min(
                answered.get(turn["id"], inf),
                undone.get(turn["id"], inf),
                undone.get(message, inf),
            )
            place = latest_open(turn["seq"], end)
            if place is not None and place > found.get(message, ({}, {}, 0))[2]:
                found[message] = (said[message], thread, place)
    return [
        {"thread": thread["id"], "message": facts.message_at(message["id"], place)}
        for message, thread, place in sorted(
            found.values(), key=lambda each: each[0]["seq"]
        )
    ]


def _latest_open(
    closures: list[dict], places: list[int]
) -> Callable[[float, float], int | None]:
    """For a thread whose closures are `closures`, the latest of `places`, ascending,
    after `start` and not after `end` at which no closing answered for it, or None: by
    a bisect, after one pass over its closures for the latest such place before each
    began."""
    closed = [closure["closed"] for closure in closures]
    before: list[int | None] = []
    for index, starts in enumerate(closed):
        last = bisect_left(places, starts) - 1
        place = places[last] if last >= 0 else None
        if index and (place is None or place < closures[index - 1]["reopened"]):
            place = before[index - 1]
        before.append(place)

    def latest(start: float, end: float) -> int | None:
        last = bisect_right(places, end) - 1
        if last < 0:
            return None
        place = places[last]
        inside = bisect_right(closed, place) - 1
        if inside >= 0 and (closures[inside]["reopened"] or inf) > place:
            place = before[inside]
        return place if place is not None and place > start else None

    return latest
