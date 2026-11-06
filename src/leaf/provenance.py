"""Which of the user's messages each revision came after, and which units of the page
each revision changed: what a change since a version can say about why it was made.

**What a revision came after.** The log links an agent's answer to the user's messages
it settles (`events.settlements`), and no event names a revision a tab's read
activated, while one a user writes names the revision their tab showed, which may be
an older one. So the log alone can't order a revision against the messages: each
revision records where in the log it went live, the seq of the last event before it
(`revision_artifact.ACTIVATION`), and each message waits (`message_waits`) from its own
seq until the seq of the agent's answer to it or of the user's resolution of its
thread, whichever came first. A revision that went live in that interval was written
while the message waited, and came after it. Both ends are places in the log, which
no later event or revision moves, so a revision's messages are a fact about its past,
a gesture sends only the waits it ends or starts, and the reading is linear in the
log. A thread reopened after a resolution keeps its earlier messages' waits ended, and
a reply that reopens it starts a wait of its own. The user's messages are thread
messages, a rewrite of one waiting again as the message; a message the user took back
waits nowhere; widget actions, which a stamped version takes in, are not here.

That is an order, not a cause, and what reads it says it as one ("after your
comment", change-provenance.js). The page logs under `~/.tmp` written in the 30 days to
5 November 2026 predate the activation record, so the rule was measured there with
each revision placed by the events that name it: on the 39 pages with pickups (1,885
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
can read, and gives each change the revisions that changed a unit its blocks stand in
(`madeBy` in `browser/runtime/version.js`). A block without an id of its own shares its
element's unit, so a change also names each revision that wrote only a block beside
it. On the same pages, comparing each version with the one before it, as `v` does (567
comparisons, 8,411 changed blocks), that gave 28.5% of changed blocks a revision that
wrote only another surviving block of their unit, but the extra revision changed what
the label says for 2.2% of them, in 10 comparisons, since it was mostly written while
the same messages waited and landed in the same version. Comparing the first version
with the newest (34 comparisons, 5,059 blocks), the label changed for 46.3%. A change
in markup the words don't show, such as an image's source, changes no unit, so no
revision is given it.

`message_waits` is part of every browser reading, where it costs one pass over the
log and the threads, an entry a message. `revision_changes` is read for a comparison's
base alone (`/api/view`), since it reads each revision's words: about 5 ms a revision
on a 120,000-character page, kept with the revision's reading for later comparisons.
"""

from bisect import bisect_right
from collections.abc import Callable, Iterable
from itertools import pairwise

from .events import settlements
from .passages import SourceReading


def message_waits(events: list, threads: dict, withdrawn: set) -> list[dict]:
    """Each message the user sent, in the order they sent them: its turn's `id` (a
    rewrite's is its edit's), the `thread` and `message` it shows as, and how long it
    waited for the agent, as places in the log: `from`, its own seq, and `until`, the
    seq of the agent's answer to it or of the user's resolution of its thread,
    whichever came first, or null while it waits. A revision was written while it
    waited where the revision went live at or after `from` and before `until`, by the
    revision's own place in the log (`revision_artifact.ACTIVATION`)."""
    thread_of = {
        message["id"]: thread["id"]
        for thread in threads.values()
        for message in thread["msgs"]
    }
    # Each thread's resolutions, as places in the log, in order.
    resolutions: dict[str, list[int]] = {}
    for event in events:
        if (
            event["kind"] == "resolve"
            and event["id"] not in withdrawn
            and (thread := thread_of.get(event["parent"]))
        ):
            resolutions.setdefault(thread, []).append(event["seq"])

    waits = []
    for thread in threads.values():
        answered = {
            turn["id"]: settlement.answer["seq"]
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
            if (after := bisect_right(resolves, turn["seq"])) < len(resolves):
                ends.append(resolves[after])
            waits.append(
                {
                    "id": turn["id"],
                    "thread": thread["id"],
                    "message": message,
                    "from": turn["seq"],
                    "until": min(ends) if ends else None,
                }
            )
    return sorted(waits, key=lambda wait: wait["from"])


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
    place: Callable[[int], int | None],
) -> dict[str, dict]:
    """For each revision after `since`, by revision: the `units` it changed from the
    revision before it, and `after`, where in the log it went live (`place`,
    `revision_artifact.ACTIVATION`)."""
    ordered = sorted(revisions)
    return {
        str(later): {
            "units": changed_units(read(earlier), read(later)),
            "after": place(later),
        }
        for earlier, later in pairwise(ordered)
        if later > since
    }
