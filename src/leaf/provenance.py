"""Which of the user's messages waited while a version was saved.

**Where a revision stands in the log.** The log links an agent's answer to the
user's messages it settles (`events.settlements`). A reply or note that publishes a
revision names its bundle in `publication`; a read's activation, which no reply or
note names, appends an `activation` that does (`revisioning.py`). A revision's place
in the log is the seq of the first event naming its bundle (`revision_places`). A
Leaf before the activation event left a read's revision with no place, and it may
still write to a page at the same protocol, so a version with such a revision says
nothing rather than that none waited.

**What a version was saved after** (`saved_after`). A comparison of a version with
the one before it, as `v` makes, shows changes every one of which that version's
revisions made, so it asks once which messages waited while they went live. The
answer is read from the threads as they stood just before the version's last
revision went live, folded by the code every reading of them uses
(`events.build_threads`) over that much of the log: nothing written since, such as
the user taking back the comment or its rewrite, reaches it, and what was taken back
before it was taken back. A message waited at a revision's place where it had been
sent, had no answer yet, and its thread stood open there, which the thread's closure
history says (``closures``); the reply or note that answered it may itself have
published the revision. Each message is quoted in the words it had at the latest of
the version's revisions it waited at, from the thread's rewrite history
(``revisions``), not as it reads now or when the version went live, since a rewrite
made after it stopped waiting never waited across the version. Where it waited at
two in different words, the later wording is the one quoted: the user's rewrite
restates what they asked for, and the version's later revisions were made with it
waiting. It is computed when a tab asks, with the base's reading
(`served_state.service.PageStateService.page_browser_view`), and nothing of it is
kept or served otherwise.

That is an order, not a cause, and the words say it as one (change-provenance.js).
Nothing reliably knows which revision wrote a given paragraph, so a comparison across
several versions says nothing, and no change names its own revisions: placing each
changed block by the nearest element with an id credited the wrong revision to 28.5%
of changed blocks across the versions compared one by one on the pages measured
below, and changed what a first-to-newest comparison would say for 46.3% of them.

**How far the order holds.** The page logs under `~/.tmp` written in the 30 days to
5 November 2026 predate the activation event, so the rule was measured there with
each revision placed at the event naming its bundle, else just before the first event
written against it, the latest it can have gone live. On the 39 pages with pickups,
169 of 568 versions compared with the one before had a revision no event names and
say nothing. Of the other 399, 18.5% were saved while one message waited, 8.3% while
several did and 73.2% with none waiting. Of the 21 saved while one anchored comment
waited and that changed words, 15 (71%) changed the commented element, one inside it
or one around it; on those same 21 versions, 35% of the 71 pairs of the version and
an anchored comment sent before it did, or 40% weighting each version equally. That
is an association in this sample, not an effect: the 21 come from 9 pages, the
positions are inferred, and a version that changed the element a comment stands on
need not have answered it.
"""

from bisect import bisect_left, bisect_right
from operator import itemgetter

from .events import build_threads, settlements, taken_back
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
    within: dict,
    places: dict[int, int],
    revisions,
    stamped: set[int],
    base: int,
    shown: int,
) -> list[dict] | None:
    """The user's messages that waited while the version at revision `shown` was
    saved, compared with the version before it at `base`: each a message any of the
    revisions after `base` through `shown` went live while it waited, as `thread` and
    `message`, in the order they were sent, the first `QUOTED` with `words`, its
    opening line as it read at the latest of those it waited at (`opening_words`).
    None where this can't be said: where a revision `stamped` with a version stands
    between the two, or where one of those revisions has no place among `places`.

    The threads are read from the log before `shown` went live, by the fold every
    reading of them takes (`events.build_threads`), so nothing written since reaches
    the answer. A message waited at a place where it had been sent and not yet answered
    and its thread stood open there (``closures``); the reply or note that answered it
    stands at its end. Its words there are those of its latest rewrite before that
    place, from the thread's rewrite history (``revisions``), else those it was sent
    with."""
    if any(base < revision < shown for revision in stamped):
        return None
    span = [revision for revision in revisions if base < revision <= shown]
    if not span or any(revision not in places for revision in span):
        return None
    at = sorted(places[revision] for revision in span)
    prefix = events[: bisect_left(events, at[-1], key=itemgetter("seq"))]
    withdrawn = taken_back(prefix)
    # Each message that waited: its reading, its thread, the latest place it waited.
    found: dict[str, tuple[dict, dict, int]] = {}
    for thread in build_threads(prefix, within, withdrawn=withdrawn).values():
        open_at = _open_at(thread["closures"], at)
        if not open_at:
            continue
        answered = {
            turn["id"]: settlement.answer["seq"]
            for settlement in settlements(thread)
            for turn in settlement.turns
        }
        # The latest place each message waited at.
        latest: dict[str, int] = {}
        for turn in thread["turns"]:
            message = turn.get("message", turn["id"])
            if (
                turn["author"] == "agent"
                or "undoes" in turn
                or turn["id"] in withdrawn
                or message in withdrawn
            ):
                continue
            first = bisect_right(open_at, turn["seq"])
            answer = answered.get(turn["id"])
            last = len(open_at) if answer is None else bisect_right(open_at, answer)
            if first < last:
                latest[message] = max(latest.get(message, 0), open_at[last - 1])
        said = {message["id"]: message for message in thread["msgs"]}
        for message, place in latest.items():
            found[message] = (said[message], thread, place)
    waited = sorted(found.values(), key=lambda each: each[0]["seq"])
    return [
        {
            "thread": thread["id"],
            "message": message["id"],
            **(
                {"words": opening_words(_as_it_read(message, thread, place))}
                if index < QUOTED
                else {}
            ),
        }
        for index, (message, thread, place) in enumerate(waited)
    ]


def _as_it_read(message: dict, thread: dict, place: int) -> dict:
    """`message` as it read at `place`: in the words of its latest rewrite in
    `thread` before it, else those it was sent with, which its first rewrite kept."""
    rewrites = [
        each for each in thread["revisions"] if each["message"] == message["id"]
    ]
    if not rewrites:
        return message
    before = [each for each in rewrites if each["seq"] < place]
    return {**message, "text": before[-1]["text"] if before else rewrites[0]["was"]}


def _open_at(closures: list[dict], places: list[int]) -> list[int]:
    """The places among `places`, ascending, at which a thread whose closures are
    `closures` stood open."""
    open_at, at = [], 0
    for place in places:
        while (
            at < len(closures)
            and closures[at]["reopened"] is not None
            and closures[at]["reopened"] < place
        ):
            at += 1
        if at == len(closures) or closures[at]["closed"] > place:
            open_at.append(place)
    return open_at


def opening_words(message: dict) -> str:
    """A message's opening line, as its Markdown shows it, or Drawing for a drawing
    with no words."""
    text = message.get("text") or ""
    line = next((line for line in text.splitlines() if line.strip()), "")
    if not line:
        return "Drawing" if message.get("drawing") else ""
    return collapse(shown_words(line, MARKDOWN, added=False))
