"""Which of the user's messages each revision answered, and which units of the page
each revision changed: what a change since a version says about why it was made.

**What a revision answered.** The log links an agent's answer to the user's messages it
settles (`events.settlements`) and to the revision live when it was written, the source
it checked and published (`thread.post_reply`). It names no revision a save made: a tab
reading the page activates a saved source as a revision of its own, with no event
naming it (`revisioning.py`), so `publication`, the field naming a revision a reply
made, is on the rare reply whose own check found the save first: 7 of the 184 answers
in the page logs under `~/.tmp` written in the 30 days to 5 November 2026. What the
log does order is each message against the revisions the log had named by then. So a
revision answers the messages the agent settled first after it: of the messages sent
before it, those whose answer was the first to follow it, each sent on a revision
before it and answered on it or a later one. A message the agent still owes an
answer, in a thread awaiting it, counts as answered after every revision, so a
revision made while one waits, and before any answer, stands with it, `answered`
false until the answer comes; the agent may be making it for that message, or for
none. A revision that answers nothing is absent: every message sent before it was
answered before it. The user's messages are thread messages, a rewrite of one
standing for the message; widget actions, which a stamped version takes in, are not
here.

The rule reads order, not intent, so it misattributes where the agent's order does
not follow the messages: an answer in words sent before the revision made for it
gives that revision to the next answer, and two messages answered together share
every revision made since the first. Of the 2,921 revisions of the 103 of those pages
with three or more revisions, it gave 8.5% one message, 1.7% several and 89.5% none,
most of those pages having been built from requests in the terminal. Of the 130 it
gave one anchored comment that changed any words, 68% changed the commented element,
one inside it or one around it; a comment may ask for a change elsewhere, so that
bounds how often the rule is right only loosely.

**What a revision changed.** A unit is an element with an id, and its words are the
ones directly in it (`SourceReading.own_words`), with `""` naming the words in no such
element, so a revision changed the units whose own words differ from the revision's
before it. The browser's comparison marks blocks of what the page shows, which only
it can read, and attributes each change to the revisions that changed a unit its
blocks stand in (`madeBy` in `browser/runtime/version.js`). Blocks without an id
share their element's unit, so a change to one paragraph without an id is also
attributed to each revision that changed another such paragraph beside it. A change in
markup the words don't show, such as an image's source, changes no unit, so it is
attributed to nothing.

`revision_answers` is part of every browser reading, where it costs one pass over the
log and the threads. `revision_changes` is read for a comparison's base alone
(`/api/view`), since it reads each revision's words: about 5 ms a revision on a
120,000-character page, kept with the revision's reading for later comparisons.
"""

import heapq
import math
from collections.abc import Callable, Iterable
from itertools import pairwise

from .events import awaits_agent, is_answer, settlements, unanswered_turns
from .passages import SourceReading


def revision_answers(
    events: list, threads: dict, revisions: Iterable[int], withdrawn: set
) -> dict[str, dict]:
    """For each revision that answered the user's messages, or came while one waited
    for an answer, by revision: those messages, each by its thread and its id, in the
    order the user sent them, and whether the agent has answered them."""
    by_id = {}
    # The newest revision the log had named once each event was admitted.
    named, newest = {}, 0
    for event in events:
        by_id[event["id"]] = event
        newest = max(newest, event.get("revision") or 0)
        named[event["id"]] = newest

    # Each message the user sent, as (the revision it was sent on, the revision its
    # answer was written on, its seq, its thread and message).
    asked = []
    for thread in threads.values():
        settled = [
            (turn, named[settlement.answer["id"]])
            for settlement in settlements(thread)
            if is_answer(by_id[settlement.answer["id"]])
            for turn in settlement.turns
        ]
        owed = unanswered_turns(thread) if awaits_agent(thread) else []
        asked.extend(
            (
                named[turn["id"]],
                answered_on,
                turn["seq"],
                thread["id"],
                turn.get("message", turn["id"]),
            )
            for turn, answered_on in [*settled, *((turn, math.inf) for turn in owed)]
            if turn["id"] not in withdrawn
        )

    # A sweep up the revisions: a message is a candidate from the revision after the
    # one it was sent on through the one it was answered on, and each revision takes
    # the candidates answered first.
    asked.sort()
    answers: dict[str, dict] = {}
    waiting: list[float] = []
    by_answer: dict[float, list[tuple]] = {}
    at = 0
    for revision in sorted(revisions):
        while at < len(asked) and asked[at][0] < revision:
            item = asked[at]
            if item[1] not in by_answer:
                heapq.heappush(waiting, item[1])
                by_answer[item[1]] = []
            by_answer[item[1]].append(item)
            at += 1
        while waiting and waiting[0] < revision:
            del by_answer[heapq.heappop(waiting)]
        if not waiting:
            continue
        first = waiting[0]
        messages = {}
        for _sent, _answered, _seq, thread, message in sorted(
            by_answer[first], key=lambda item: item[2]
        ):
            messages.setdefault(message, {"thread": thread, "message": message})
        answers[str(revision)] = {
            "messages": list(messages.values()),
            "answered": first != math.inf,
        }
    return answers


def changed_units(before: SourceReading | None, after: SourceReading) -> list[str]:
    """The units whose own words differ between two versions (`own_words`), the
    first version None for a page's first."""
    old = before.own_words if before is not None else {}
    new = after.own_words
    return sorted(
        unit for unit in old.keys() | new.keys() if old.get(unit) != new.get(unit)
    )


def revision_changes(
    read: Callable[[int], SourceReading], revisions: Iterable[int], since: int
) -> dict[str, list[str]]:
    """For each revision after `since`, by revision: the units it changed from the
    revision before it."""
    ordered = sorted(revisions)
    return {
        str(after): changed_units(read(before), read(after))
        for before, after in pairwise(ordered)
        if after > since
    }
