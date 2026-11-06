"""Which of the user's messages waited while a version was saved.

**Where a revision stands in the log.** The log links an agent's answer to the
user's messages it settles (`events.settlements`). A reply or note that publishes a
revision names its bundle in `publication`; a read's activation, which no reply or
note names, appends an `activation` that does (`revisioning.py`). A revision's place
in the log is the seq of the first event naming its bundle (`revision_places`). The
activation event came with protocol 43, so a Leaf that skips it can't write the page;
a page taken to 43 keeps its earlier revisions without a place, and they add none to
their version.

**What a version was saved after** (`saved_after`). A comparison of a version with
the one before it, as `v` makes, shows changes every one of which that version's
revisions made, so it asks which messages waited at the place of any of them, each
judged by the log up to that place: a comment taken back after one revision went
live waited there. `events.build_threads` can't stop between events, since it reads
which gestures were ever taken back before its pass, but its histories keep the place
of everything they hold. So one fold of the log before the version's last revision
went live reads every message as it was said, none taken back, and from its
histories each message's waits follow, each turn of it from its own place until the
first of its answer (`events.settlements`), its being taken back, or the message's,
cut where its thread stood closed (``closures``). A bisect of the version's sorted
places finds the latest it waited at, after one pass over each thread's closings, so
the work grows with the log and the turns, not with the threads times the
revisions. The reply or note that answered a message may itself have published the
revision, and stands at its end.

Each message is quoted in the words it had at the latest of the version's revisions
it waited at, from the thread's rewrite history (``revisions``) less the rewrites
taken back by then, not as it reads now or when the version went live, since a
rewrite made after it stopped waiting never waited across the version. Where it
waited at two in different words, the later wording is the one quoted: the user's
rewrite restates what they asked for, and the version's later revisions were made
with it waiting. It is computed when a tab asks, with the base's document
(`served_state.service.PageStateService.page_comparison`), and nothing of it is kept
or served otherwise.

That is an order, not a cause, and the words say it as one (change-provenance.js).
Nothing reliably knows which revision wrote a given paragraph, so a comparison across
several versions says nothing, and no change names its own revisions: placing each
changed block by the nearest element with an id credited the wrong revision to 28.5%
of changed blocks across the versions compared one by one on the pages measured
below, and changed what a first-to-newest comparison would say for 46.3% of them.

**How far the order holds.** The page logs under `~/.tmp` written in the 30 days to
5 November 2026 predate the activation event, so the rule was measured there with
each revision placed at the event naming its bundle, else just before the first event
written against it, the latest it can have gone live, and each comment's anchor read
from the log before the version went live, as the threads stood then. On the 39
pages with pickups, 169 of 568 versions compared with the one before had a revision
no event names and were left out. Of the other 399, 18.5% were saved while one
message waited, 8.3% while several did and 73.2% with none waiting. Of the 28 saved
while one anchored comment waited and that changed words, 18 (64%) changed the
commented element, one inside it or one around it; on those same 28 versions, 42% of
the 79 pairs of the version and an anchored comment sent before it went live did,
and 42% weighting each version equally. That is an association in this sample, not
an effect: the 28 come from 9 pages, the positions are inferred, and a version that
changed the element a comment stands on need not have answered it.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Callable
from math import inf
from operator import itemgetter

from .events import action_rests_on, build_threads, settlements
from .passages import collapse, shown_words

MARKDOWN = {"x-text-format": "markdown"}
# The most messages a version's line quotes; it counts the rest (change-provenance.js).
# Only those are read into words, which is most of the answer's cost where many wait.
QUOTED = 3


def revision_places(events: list) -> dict[int, int]:
    """Each revision's place in the log: the seq of the first event naming its bundle
    in `publication`, the reply or note that published it or the `activation` a read
    appended (`revisioning.py`)."""
    places: dict[int, int] = {}
    for event in events:
        if event.get("publication"):
            places.setdefault(event["revision"], event["seq"])
    return places


def saved_after(
    events: list,
    containment: Callable[[int], dict],
    places: dict[int, int],
    revisions,
    stamped: set[int],
    base: int,
    shown: int,
) -> list[dict] | None:
    """The user's messages that waited while the version at revision `shown` was
    saved, compared with the version before it at `base`: each a message that waited
    at the place of any revision after `base` through `shown`, as `thread` and
    `message`, in the order they were sent, the first `QUOTED` with `words`, its
    opening line as it read at the latest of those (`opening_words`). None where a
    revision `stamped` with a version stands between the two; every revision between
    them has a place among `places`. `containment` reads a revision's (`within`).

    A fold of the log before a revision went live (`events.build_threads`), under that
    revision's containment, reads every message as it was said, none taken back, and
    its histories keep the place of each turn, answer, closing, reopening and rewrite,
    beside the place each gesture was taken back. A message waited at a revision's
    place where, by the log before it, it had been sent and not taken back, had no
    answer yet, and its thread stood open; the reply or note that answered it stands
    at its end. Its words there are those of its latest rewrite before that place not
    yet taken back, else those it was sent with.

    Containment reaches the fold only through what each action rests on
    (`events.action_rests_on`), so the revisions that agree on that for every action
    the log holds read alike, and one fold, to the last of them, serves them all: one
    for a page whose versions move no element an action names, one more for each
    reading of them that differs."""
    if any(base < revision < shown for revision in stamped):
        return None
    span = sorted(
        (places[revision], revision)
        for revision in revisions
        if base < revision <= shown
    )
    if not span:
        return None
    prefix = events[: bisect_left(events, span[-1][0], key=itemgetter("seq"))]
    undone = {event["undoes"]: event["seq"] for event in prefix if "undoes" in event}
    actions = [event for event in prefix if event["kind"] == "action"]
    readings: dict[tuple, tuple[dict, list[int]]] = {}
    for place, revision in span:
        within = containment(revision) if actions else {}
        rests = tuple(tuple(action_rests_on(action, within)) for action in actions)
        readings.setdefault(rests, (within, []))[1].append(place)
    # Each message that waited: its reading, its thread, the latest place it waited.
    found: dict[str, tuple[dict, dict, int]] = {}
    for within, at in readings.values():
        cut = prefix[: bisect_left(prefix, at[-1], key=itemgetter("seq"))]
        for thread in build_threads(cut, within, withdrawn=set()).values():
            latest_open = _latest_open(thread["closures"], at)
            answered = {
                turn["id"]: settlement.answer["seq"]
                for settlement in settlements(thread)
                for turn in settlement.turns
            }
            said = {message["id"]: message for message in thread["msgs"]}
            for turn in thread["turns"]:
                if turn["author"] == "agent" or "undoes" in turn:
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
    waited = sorted(found.values(), key=lambda each: each[0]["seq"])
    return [
        {
            "thread": thread["id"],
            "message": message["id"],
            **(
                {"words": opening_words(_as_it_read(message, thread, place, undone))}
                if index < QUOTED
                else {}
            ),
        }
        for index, (message, thread, place) in enumerate(waited)
    ]


def _latest_open(
    closures: list[dict], places: list[int]
) -> Callable[[float, float], int | None]:
    """For a thread whose closures are `closures`, the latest of `places`, ascending,
    after `start` and not after `end` at which it stood open, or None: by a bisect,
    after one pass over its closures for the latest open place before each began."""
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


def _as_it_read(message: dict, thread: dict, place: int, undone: dict) -> dict:
    """`message` as it read at `place`: in the words of its latest rewrite in
    `thread` before it and not taken back by then, else those it was sent with, which
    its first rewrite kept."""
    rewrites = [
        each for each in thread["revisions"] if each["message"] == message["id"]
    ]
    if not rewrites:
        return message
    standing = [
        each
        for each in rewrites
        if each["seq"] < place and undone.get(each["id"], inf) > place
    ]
    return {**message, "text": standing[-1]["text"] if standing else rewrites[0]["was"]}


def opening_words(message: dict) -> str:
    """A message's opening line, as its Markdown shows it, or Drawing for a drawing
    with no words."""
    text = message.get("text") or ""
    line = next((line for line in text.splitlines() if line.strip()), "")
    if not line:
        return "Drawing" if message.get("drawing") else ""
    return collapse(shown_words(line, MARKDOWN, added=False))
