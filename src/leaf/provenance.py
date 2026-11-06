"""Which of the user's messages each revision came after, and which units of the page
each revision changed: what a change since a version can say about why it was made.

**What a revision came after.** The log links an agent's answer to the user's messages
it settles (`events.settlements`) and to the revision live when it was written, the
source it checked and published (`thread.post_reply`). It names no revision a save
made: a tab reading the page activates a saved source as a revision of its own, with
no event naming it (`revisioning.py`), so `publication`, the field naming a revision a
reply made, is on the rare reply whose own check found the save first: 7 of the 184
answers in the page logs under `~/.tmp` written in the 30 days to 5 November 2026.
What the log does order is each event against the revisions it had named by then. So
each message the user sent waits (`message_waits`) from the newest revision named when
it was sent until the newest named when the agent answered it or the user resolved
its thread, whichever came first, and a revision written in that interval came after
it. A revision's messages are a fact about its past: no later event adds one or takes
one away, so a gesture changes only the waits it ends or starts, and the reading is
linear in the log. A thread reopened after a resolution keeps its earlier messages'
waits ended, and a reply that reopens it starts a wait of its own. The user's messages
are thread messages, a rewrite of one waiting again as the message; a message the
user took back waits nowhere; widget actions, which a stamped version takes in, are
not here.

That is an order, not a cause, and what reads it says it as one ("after your
comment", change-provenance.js). On the 39 pages with pickups among those logs (1,885
revisions), of the revisions with one message waiting and changed words that the
message was an anchored comment on (116), 71% changed the commented element, one
inside it or one around it, against 17% for every pair of a revision and a comment
sent before it: four times chance, and not enough to say a change answers the
comment. 4.5% of revisions came after several messages and 83.4% after none.

The rule first given, which named only the waiting messages the agent answered first
after the revision, scored 68% of 130 with 2.7% several. Its narrowing depended on
answers yet to come, so a revision's messages changed after it, and a resolution with
no answer dropped a message from the revisions it had waited across; this rule does
neither and scores as well. A pickup that opened a turn on the user's input
(`delivery.record_pickup`) was also tried as a scope, against that first rule on the
same logs: of the messages the latest opened pickup before a revision lists, those
answered first after it, and where every one was answered before it, the last
answered, which is where a revision made after a quick answer goes. The first half
did as well (69% of 122); where the two disagreed its one message was near in 3 of 8
cases against 8 of 16 for each of the rule's several, since a pickup mid-turn lists
only what newly arrived. The second half was below chance: 10% of 393, and 14% of the
164 made while that comment's turn still ran. So a revision made after a quick answer
is not given that comment: it comes after whatever else still waits, or with none
waiting, either of which is true of it, and the pickups decide nothing here.

**What a revision changed.** A unit is an element with an id, and its words are the
ones directly in it (`SourceReading.own_words`), with `""` naming the words in no such
element, so a revision changed the units whose own words differ from the revision's
before it. The browser's comparison marks blocks of what the page shows, which only it
can read, so it narrows each change to its blocks itself (`madeBy` in
`browser/runtime/version.js`): these units name the revisions that may have made a
change, and where they name several, the comparison reads those revisions' documents
to find which one wrote each block's words. A change in markup the words don't show,
such as an image's source, changes no unit, so no revision is given it.

`message_waits` is part of every browser reading, where it costs one pass over the
log and the threads, an entry a message. `revision_changes` is read for a comparison's
base alone (`/api/view`), with each revision's document address, since it reads each
revision's words: about 5 ms a revision on a 120,000-character page, kept with the
revision's reading for later comparisons.
"""

from bisect import bisect_right
from collections.abc import Callable, Iterable
from itertools import pairwise

from .events import settlements
from .passages import SourceReading


def message_waits(
    events: list, threads: dict, withdrawn: set, latest: int
) -> list[dict]:
    """Each message the user sent, in the order they sent them: its turn's `id` (a
    rewrite's is its edit's), the `thread` and `message` it shows as, `from`, the newest
    revision the log had named when it was sent, and `until`, where the agent answered
    it or the user resolved its thread, whichever came first, or null while it waits. A
    revision came after it where it is newer than `from` and `until` is null or no
    older. An answer names the revision live when it was written, which ends the wait
    there. A resolution names none, so the wait it ends runs to the newest revision the
    log names next after it, or to `latest`, the page's newest, while none has: a
    revision the log can't place before or after a resolution counts as before it,
    since "after your comment" stays true of it either way."""
    named, newest = {}, 0
    for event in events:
        newest = max(newest, event.get("revision") or 0)
        named[event["id"]] = newest
    # The newest revision named as of the next event after each that names one.
    following, upcoming = {}, latest
    for event in reversed(events):
        following[event["id"]] = upcoming
        if event.get("revision"):
            upcoming = named[event["id"]]
    thread_of = {
        message["id"]: thread["id"]
        for thread in threads.values()
        for message in thread["msgs"]
    }
    # Each thread's resolutions, as the events' places in the log, in order.
    resolutions: dict[str, list[tuple[int, str]]] = {}
    for event in events:
        if (
            event["kind"] == "resolve"
            and event["id"] not in withdrawn
            and (thread := thread_of.get(event["parent"]))
        ):
            resolutions.setdefault(thread, []).append((event["seq"], event["id"]))

    waits = []
    for thread in threads.values():
        answered = {
            turn["id"]: named[settlement.answer["id"]]
            for settlement in settlements(thread)
            for turn in settlement.turns
        }
        resolves = resolutions.get(thread["id"], [])
        for turn in thread["turns"]:
            message = turn.get("message", turn["id"])
            if (
                turn["author"] == "agent"
                or "undoes" in turn
                or turn["id"] in withdrawn
                or message in withdrawn
            ):
                continue
            ends = [answered[turn["id"]]] if turn["id"] in answered else []
            if (after := bisect_right(resolves, (turn["seq"], ""))) < len(resolves):
                ends.append(following[resolves[after][1]])
            waits.append(
                (
                    turn["seq"],
                    {
                        "id": turn["id"],
                        "thread": thread["id"],
                        "message": message,
                        "from": named[turn["id"]],
                        "until": min(ends) if ends else None,
                    },
                )
            )
    return [wait for _seq, wait in sorted(waits, key=lambda item: item[0])]


def changed_units(before: SourceReading | None, after: SourceReading) -> list[str]:
    """The units whose own words differ between two versions (`own_words`), the
    first version None for a page's first."""
    old = before.own_words if before is not None else {}
    new = after.own_words
    return sorted(
        unit for unit in old.keys() | new.keys() if old.get(unit) != new.get(unit)
    )


def revision_changes(
    read: Callable[[int], SourceReading],
    revisions: Iterable[int],
    since: int,
    address: Callable[[int], str],
) -> dict[str, dict]:
    """For each revision after `since`, by revision: the `units` it changed from the
    revision before it, and the `url` of its document."""
    ordered = sorted(revisions)
    return {
        str(after): {
            "units": changed_units(read(before), read(after)),
            "url": address(after),
        }
        for before, after in pairwise(ordered)
        if after > since
    }
