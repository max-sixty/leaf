"""Which of the user's messages each revision came after, and which units of the page
each revision changed: what a change since a version can say about why it was made.

**What a revision came after.** The log links an agent's answer to the user's messages
it settles (`events.settlements`) and to the revision live when it was written, the
source it checked and published (`thread.post_reply`). It names no revision a save
made: a tab reading the page activates a saved source as a revision of its own, with
no event naming it (`revisioning.py`), so `publication`, the field naming a revision a
reply made, is on the rare reply whose own check found the save first: 7 of the 184
answers in the page logs under `~/.tmp` written in the 30 days to 5 November 2026.
What the log does order is each message against the revisions the log had named by
then. So a revision is given the messages it came after that were still waiting for
an answer, and of those the ones the agent answered first after it, each sent on a
revision before it and answered on it or a later one; a message the agent still owes,
in a thread awaiting it, counts as answered after every revision. A revision absent
from the reading came with none of the user's messages waiting. The user's messages
are thread messages, a rewrite of one standing for the message; widget actions,
which a stamped version takes in, are not here.

That is an order, not a cause, and what reads it says it as one ("after your
comment", change-provenance.js). On the 39 pages with pickups among those logs, of
the revisions this rule gives one anchored comment and that changed words (130), 68%
changed the commented element, one inside it or one around it, against 17% for every
pair of a revision and a comment sent before it: four times chance, and not enough to
say a change answers the comment. 2.8% of revisions are given several messages, two
answered together sharing every revision made since the first, and 83.6% none.

A pickup that opened a turn on the user's input (`delivery.record_pickup`) was tried
as a scope for the same choice and measured on the same logs: of the messages the
latest opened pickup before a revision lists, those answered first after it, and where
every one was answered before it, the last answered, which is where a revision made
after a quick answer goes. The first half did as well as this rule (69% of 122) and
gave fewer revisions several messages (0.5%), but where the two disagreed its one
message was near in 3 of 8 cases, against 8 of 16 for each of this rule's several: a
pickup mid-turn lists only what newly arrived, not what the turn handles, so the
narrowing showed no gain. The second half was below chance: of the 393 revisions with
changed words it gave one such comment, 10% were near, and 14% of the 164 made while
that comment's turn still ran. So a revision made after a quick answer is not given
that comment: it comes after the next message still waiting, or with none waiting,
either of which is true of it, and the pickups decide nothing here.

**What a revision changed.** A unit is an element with an id, and its words are the
ones directly in it (`SourceReading.own_words`), with `""` naming the words in no such
element, so a revision changed the units whose own words differ from the revision's
before it. The browser's comparison marks blocks of what the page shows, which only it
can read, and gives each change the revisions that changed a unit its blocks stand in
(`madeBy` in `browser/runtime/version.js`). Blocks without an id share their element's
unit, so a change to one paragraph without an id is also given each revision that
changed another such paragraph beside it. A change in markup the words don't show,
such as an image's source, changes no unit, so no revision is given it.

`revision_messages` is part of every browser reading, where it costs one pass over the
log and the threads (19 ms for 4,000 threads). `revision_changes` is read for a
comparison's base alone (`/api/view`), since it reads each revision's words: about
5 ms a revision on a 120,000-character page, kept with the revision's reading for
later comparisons.
"""

import heapq
import math
from collections.abc import Callable, Iterable
from itertools import pairwise

from .events import awaits_agent, is_answer, settlements, unanswered_turns
from .passages import SourceReading


def revision_messages(
    events: list, threads: dict, revisions: Iterable[int], withdrawn: set
) -> dict[str, list[dict]]:
    """For each revision that came after one of the user's messages still waiting for
    an answer, by revision: those of them the agent answered first after it, each by
    its thread and its id, in the order the user sent them."""
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
    given: dict[str, list[dict]] = {}
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
        given[str(revision)] = list(messages.values())
    return given


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
