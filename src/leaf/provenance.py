"""How long each of the user's messages waited for the agent, as places in the log:
what a version can say about the comments it was saved after.

**Where a revision stands in the log.** The log links an agent's answer to the
user's messages it settles (`events.settlements`). A reply or note that publishes a
revision names its bundle in `publication`, but no event used to name a revision a
tab's read activated, and an event the user writes names the revision their tab
showed, which may be an older one. So a read's activation now appends an `activation`
event naming the bundle (`revisioning.py`), and a revision's place in the log is the
seq of the event that names its bundle. On the 39 pages measured below that adds
1,454 events to their 3,693, one for each revision of 1,890 that no reply or note
published.

**What a message waited across.** Each message waits (`message_waits`) from its own
seq until the agent's answer to it or the closing of its thread, by a resolution or
an answering action, whichever came first; a closing later taken back, outranked or
retracted, or a thread otherwise reopened, starts a new wait from the reopening while
the message is still unanswered. Closings and reopenings are the thread's own history
(`events.build_threads`, ``closures``), read at the place each happened, so no later
event moves a wait's ends, a gesture sends only the waits it ends or starts, and the
reading is linear in the log. A revision whose place falls inside a wait was saved
while the message waited; one placed at its end was published by the reply or note
that ended it. Each wait carries the words its message had then:
the comment's, or a rewrite's, which waits as a turn of its own. The user's messages
are thread messages; a message the user took back waits nowhere; widget actions,
which a stamped version takes in, are not here.

**What reads it.** A comparison of a version with the one before it, as `v` makes,
shows changes every one of which that version's revisions made, so it says once
which messages waited while the version was saved (change-provenance.js). That is an
order, not a cause, and the words say it as one. Nothing reliably knows which
revision wrote a given paragraph, so a comparison across several versions says
nothing of this, and no change names its own revisions: placing each changed block by
the nearest element with an id credited the wrong revision to 28.5% of changed blocks
across the versions compared one by one on the pages measured below, and changed what
a first-to-newest comparison would say for 46.3% of them.

**How far the order holds.** The page logs under `~/.tmp` written in the 30 days to
5 November 2026 predate the activation event, so the rule was measured there with
each revision placed at the event naming its bundle, else just before the first event
written against it, the latest it can have gone live. On the 39 pages with pickups,
568 versions compared with the one before: 17.6% were saved while one message waited,
8.8% while several did and 73.6% with none waiting. Of the 41 saved while one
anchored comment waited and that changed words, 83% changed the commented element,
one inside it or one around it, against 25% for every pair of a version and a
comment sent before it: over three times chance, and not enough to say a version
answers a comment. Per revision the same rule scored 71% of 116 against 17%. A
pickup that opened a turn was also tried as a scope
for which message a revision follows, and decided nothing a wait doesn't: where it
narrowed several messages to one, its one was near in 3 of 8 cases against 8 of 16,
and a revision made after a quick answer was near the answered comment in 10% of 393
cases, below chance.

`message_waits` is part of every browser reading, where it costs one pass over the
log and the threads, an entry a wait.
"""

from bisect import bisect_right

from .events import settlements
from .passages import collapse, shown_words

MARKDOWN = {"x-text-format": "markdown"}


def opening_words(event: dict) -> str:
    """A message's opening line, as its Markdown shows it, or Drawing for a drawing
    with no words."""
    text = event.get("text") or ""
    line = next((line for line in text.splitlines() if line.strip()), "")
    if not line:
        return "Drawing" if event.get("drawing") else ""
    return collapse(shown_words(line, MARKDOWN, added=False))


def message_waits(events: list, threads: dict, withdrawn: set) -> list[dict]:
    """Each wait of each message the user sent, in log order: `id`, the turn's id
    and the place the wait began; the `thread` and `message` it shows as; `words`, the
    opening line it had then (`opening_words`); and how long it waited, as places in
    the log: `from`, where it began, and `until`, where the agent answered it or its
    thread closed, whichever came first, or null while it waits. A revision placed
    after `from` and, where `until` is set, not after it was saved while the message
    waited."""
    by_id = {event["id"]: event for event in events}
    waits = []
    for thread in threads.values():
        answered = {
            turn["id"]: settlement.answer["seq"]
            for settlement in settlements(thread)
            for turn in settlement.turns
        }
        closures = thread["closures"]
        closed = [closure["closed"] for closure in closures]
        for turn in thread["turns"]:
            message = turn.get("message", turn["id"])
            if (
                turn["author"] == "agent"
                or "undoes" in turn
                or turn["id"] in withdrawn
                or message in withdrawn
            ):
                continue
            answer = answered.get(turn["id"])
            words = opening_words(by_id[turn["id"]])
            start = turn["seq"]
            while start is not None:
                at = bisect_right(closed, start)
                closure = closures[at] if at < len(closures) else None
                ends = [
                    end
                    for end in (answer, closure and closure["closed"])
                    if end is not None and end > start
                ]
                until = min(ends) if ends else None
                waits.append(
                    {
                        "id": f"{turn['id']}:{start}",
                        "thread": thread["id"],
                        "message": message,
                        "words": words,
                        "from": start,
                        "until": until,
                    }
                )
                # A closing ended the wait; a reopening before the answer starts
                # another.
                start = (
                    closure["reopened"]
                    if closure is not None
                    and until == closure["closed"]
                    and (answer is None or answer > (closure["reopened"] or answer))
                    else None
                )
    return sorted(waits, key=lambda wait: wait["from"])
