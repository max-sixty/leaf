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
published the revision. It is computed when a tab asks, with the base's reading
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
    revisions after `base` through `shown` went live while it waited, as `thread`,
    `message` and `words`, its opening line when `shown` went live (`opening_words`),
    in the order they were sent. None where this can't be said: where a revision
    `stamped` with a version stands between the two, or where one of those revisions
    has no place among `places`.

    The threads are read from the log before `shown` went live, by the fold every
    reading of them takes (`events.build_threads`), so nothing written since reaches
    the answer. A message waited at a place where it had been sent and not yet answered
    and its thread stood open there (``closures``); the reply or note that answered it
    stands at its end."""
    if any(base < revision < shown for revision in stamped):
        return None
    span = [revision for revision in revisions if base < revision <= shown]
    if not span or any(revision not in places for revision in span):
        return None
    at = sorted(places[revision] for revision in span)
    prefix = events[: bisect_left(events, at[-1], key=itemgetter("seq"))]
    withdrawn = taken_back(prefix)
    found: dict[str, dict] = {}
    for thread in build_threads(prefix, within, withdrawn=withdrawn).values():
        open_at = _open_at(thread["closures"], at)
        if not open_at:
            continue
        answered = {
            turn["id"]: settlement.answer["seq"]
            for settlement in settlements(thread)
            for turn in settlement.turns
        }
        said = {message["id"]: message for message in thread["msgs"]}
        for turn in thread["turns"]:
            message = turn.get("message", turn["id"])
            if (
                turn["author"] == "agent"
                or "undoes" in turn
                or turn["id"] in withdrawn
                or message in withdrawn
                or message in found
            ):
                continue
            first = bisect_right(open_at, turn["seq"])
            answer = answered.get(turn["id"])
            if first < len(open_at) and (answer is None or open_at[first] <= answer):
                found[message] = {
                    "thread": thread["id"],
                    "message": message,
                    "words": opening_words(said[message]),
                    "seq": said[message]["seq"],
                }
    return [
        {key: value for key, value in entry.items() if key != "seq"}
        for entry in sorted(found.values(), key=itemgetter("seq"))
    ]


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
