"""Pure folds over the append-only event model."""

from bisect import bisect_left, insort
from collections.abc import Callable, Iterable
from math import inf
from operator import itemgetter
from typing import NamedTuple

from leaf.findings import Finding
from leaf.registry.kernel import kinds_declaring


def taken_back(events: list) -> set:
    """Event ids some later gesture took back (`undoes`).

    An undo names the gesture it withdraws and carries no counter-state, so every
    projection drops those ids. The thread an action answered is open again once
    the answer is withdrawn, and the undo walk steps back past what it has
    already taken."""
    return {e["undoes"] for e in events if e.get("undoes")}


def event_coordinate(event: dict) -> tuple[str, str, str]:
    """The owner-unit-verb coordinate an admitted action or report stands on.

    Admission stores the one part a registry-free reader cannot recover,
    `meaning.unit`; the owner and verb are the event's own `widget` and `action`."""
    return (event["widget"], event["meaning"]["unit"], event["action"])


def document_identity(scope: str, revision: int | None = None) -> dict:
    """The document a widget event is made in, from its scope and revision.

    A `page` event's document is the revision it names; a `thread` event's is the
    frozen thread markup, which lasts the page's whole lifetime and so carries no
    revision. Admission, thread folds, and the browser all key documents on this
    identity."""
    if scope == "thread":
        return {"kind": "thread"}
    return {"kind": "page", "revision": revision}


def event_document(event: dict) -> dict:
    """The document an admitted widget event was made in (`meaning.scope`)."""
    return document_identity(event["meaning"]["scope"], event["revision"])


def is_reaction(event: dict) -> bool:
    """A message carrying a token in place of words ($events, $reactions)."""
    return bool(event.get("token"))


def is_answer(event: dict) -> bool:
    """Whether an event is an agent's answer to the input its ``responds`` names.

    A thread parent locates presentation; only ``responds`` names the input an
    answer settles. User replies and progress carry none. A failure receipt names the
    input it gives up on without answering it, so an answer may still follow it.
    """
    return (
        event["kind"] == "reply"
        and event["author"] == "agent"
        and event.get("responds") is not None
        and "failure" not in event
    )


def spoken_turns(thread: dict) -> list:
    """Messages with words, including retained progress messages.

    Reactions are marks rather than words, and a message the user took back keeps
    its place with neither (`build_threads`). Presentation ranges include ephemeral
    messages; semantic turn-taking reads :func:`conversation_turns` instead.
    """
    return [m for m in thread["msgs"] if not is_reaction(m) and "withdrawn" not in m]


def conversation_turns(thread: dict) -> list:
    """Spoken messages that participate in the exchange, excluding progress messages."""
    return [message for message in spoken_turns(thread) if not message.get("ephemeral")]


def exchange(thread: dict) -> list:
    """The conversation's turns and the user's revisions of its messages, in log order.

    A user's `edit` hands the thread to the agent as a reply would, under the edit's
    id, while every surface shows it as the message's new wording rather than a
    message beside it (`build_threads`, ``revisions``). So only who owes the next word
    reads it (`unanswered_turns`, `workflows`); what a thread says, and what a question
    asked since a message waits on, read the messages (`conversation_turns`). An
    agent's edit corrects its own words and hands nothing over, so it is no turn."""
    return sorted(
        [*conversation_turns(thread), *thread["revisions"]], key=lambda m: m["seq"]
    )


def turn_message(turn: dict) -> str:
    """The message a turn is shown as: a revision's message, else the turn's own."""
    return turn["message"] if turn["kind"] == "edit" else turn["id"]


def bare_reaction(thread: dict) -> bool:
    """A reaction nobody has replied to: paint on the page, and no thread yet."""
    return is_reaction(thread["root"]) and not spoken_turns(thread)


class UndoReading:
    """Indexed eligibility for the user's one-step withdrawals.

    The browser exposes every gesture in force in one reading, so checking each
    candidate by scanning the event log again turns a linear state read into a
    quadratic one. This index computes the shared facts once, event identity and
    withdrawals, and the append door uses the same reading for its authoritative
    check, while callers that only have one candidate can keep using
    :func:`undo_error`.
    """

    def __init__(
        self,
        events: list,
        *,
        withdrawn: set | None = None,
        absorbed: frozenset,
    ):
        self.events_by_id = {event["id"]: event for event in events}
        self.withdrawn = taken_back(events) if withdrawn is None else withdrawn
        self.absorbed = absorbed

    def error(self, event: dict) -> Finding | None:
        """The finding the append door refuses one proposed ``undo`` event on."""
        named = {"undoes": event["undoes"]}
        target = self.events_by_id.get(event["undoes"])
        if target is None:
            return Finding("unknown-undo", values=named)
        named["target"] = target["kind"]
        if target["author"] != "user":
            return Finding("foreign-gesture", values=named)
        if target["id"] in self.withdrawn:
            return Finding("withdrawn-gesture", values=named)
        if target["kind"] not in kinds_declaring("undoable"):
            return Finding(
                "unundoable",
                values={**named, "undoable": sorted(kinds_declaring("undoable"))},
            )
        elif target["kind"] == "action" and target["id"] in self.absorbed:
            # The newest revision's markup places the unit
            # (`StateProjection.absorbed`), so taking the move back would restore
            # nothing; a new move changes where the unit stands.
            return Finding(
                "absorbed-move", values={**named, "revision": target["revision"]}
            )
        return None


def undo_error(event: dict, events: list, absorbed: frozenset) -> Finding | None:
    """Why this undo may not take back the event it names, or None.

    Checked once here, at the door the browser writes through, so nothing
    downstream asks a second time whether an `undoes` points at something real.
    Two tabs racing to take back the same event are the one case this refuses
    that nothing is wrong with: the second is a no-op, and refusing it costs a
    notice where accepting it would leave two withdrawals of one gesture in a log
    whose every other line is something the user did.

    Every gesture of the user's own, a message or a reaction included, is theirs to
    take back however far the agent has got with it, answered or resolved: what
    answered a message keeps its place (`build_threads`), and the agent is told of the
    withdrawal as it was of the gesture (`event_contracts.admitted_event`). The browser
    offers exactly the gestures this reading admits
    (`served_state.document.browser_undo_candidates`).

    `absorbed` is the newest revision's absorbed moves, whose units its markup
    places."""
    return UndoReading(events, absorbed=absorbed).error(event)


def standing_withdrawn(events: list, withdrawn: set) -> set:
    """The withdrawn messages something still in force stands on: a message naming
    one as its parent, or a to-do attached to the thread one opened. Each keeps its
    place in its thread with nothing in it (`build_threads`), so what answered it
    keeps its context and its thread its name. A parent is always older than its
    message, so one pass from the newest event finds a chain of them."""
    standing = set()
    for event in reversed(events):
        if event["kind"] == "todo" and event["subject"]["kind"] == "thread":
            standing.add(event["subject"]["id"])
        elif (
            event["kind"] in kinds_declaring("message")
            and "parent" in event
            and (event["id"] not in withdrawn or event["id"] in standing)
        ):
            standing.add(event["parent"])
    return standing & withdrawn


def unshown(events: list, withdrawn: set) -> set:
    """The gestures taken back that no reading shows: every withdrawn id but the
    messages something still stands on (`standing_withdrawn`). A message or thread
    named by one of these is gone, and nothing new may name it."""
    return withdrawn - standing_withdrawn(events, withdrawn)


def build_threads(
    events: list,
    within: dict,
    *,
    withdrawn: set | None = None,
    containments: Iterable[tuple[int, Callable[[], dict]]] = (),
) -> dict:
    """Fold threads using the admitted answer coordinate.

    Answer effects survive retirement of their source widget. An unrelated action
    of another verb cannot supersede one, while an explicit answer with null
    effect replaces a closing answer without itself closing a thread. ``anchor`` is
    the thread's current page location, and ``detached_from`` retains the last real
    anchor when a null replacement or removed passage leaves the thread detached.
    ``rewritten_from`` retains the anchor a ``reanchor`` moved off, whose quoted words a
    version rewrote, until a reply chooses the thread's place again.
    A new spoken reply resumes the thread; reactions and failure receipts
    leave its closure in force. A later resolution closes it again.
    ``revisions`` holds the user's edits in log order, each with ``was``, the words
    it replaced: each shows as its message's wording and stands in the exchange as a
    turn of its own (`exchange`), so it resumes the thread as a reply does.
    ``turns`` holds every turn said in the thread, the ones since taken back
    included, and each undo that took one back, in log order, as what settles a
    batch of them (`settled_through`); only the server reads it.

    Whether a thread stands closed is read at every place in the log
    (`_ClosureHistory`): the latest closing or reopening still in force decides it.
    A closing is a resolution, or an action winning its coordinate whose answer
    names the thread; a reopening is an unresolve, a spoken reply, or the user's
    rewrite of a message. Taking one back, an action superseded, or a version
    retracting it (`InForce`) leaves the one before deciding, at the place where
    that happened. ``closures`` holds each time the thread stood closed, in log order:
    the seq it ``closed`` at and the seq it ``reopened`` at, or null while it stands,
    so what a closure ended stayed ended until then (`provenance.saved_after`);
    only the server reads it. ``resolved`` is the closing that stands at the end of
    the log, or null. `containments` hands the fold, in order, each place where
    another revision's containment takes hold and a reader of it, so the history at
    each such place is the one a fold under that containment would read
    (`InForce.contain`); the containment `within` stands until the first.

    Each thread is keyed by, and carries as ``id``, the id of the comment that
    opened it, its ``root``: the name every obligation, workflow, summary, and title
    uses for it. Admission names as a parent only a message some reading shows
    (`event_contracts._parent_error`), so each reply it admits lands in a thread.

    A message the user took back leaves every reading, except where something still
    in force stands on it (`standing_withdrawn`): there it keeps its place with no
    words and no mark, and ``withdrawn`` names the undo and what it said, as a
    deleted message's ``edited`` does. It is no turn (`spoken_turns`), so nothing is
    owed it, and it names, reopens and moves nothing, and its rewrites change nothing.
    """
    if withdrawn is None:
        withdrawn = taken_back(events)
    standing = standing_withdrawn(events, withdrawn)
    undos = {e["undoes"]: e for e in events if e.get("undoes") in standing}
    # Every action at a coordinate competes, including a non-answer, so thread
    # settlement and visible state read the same winning gesture: walked in log
    # order, which ends where the final reading does (`InForce`).
    in_force = InForce(within)
    closures = _ClosureHistory()
    threads: dict[str, dict] = {}
    thread_for: dict[str, dict] = {}
    messages = {}
    said_in: dict[str, dict] = {}
    # Each message the user rewrote, with the rewrites, which reopen nothing once
    # the message is taken back; and what has been taken back so far.
    rewrites: dict[str, list[str]] = {}
    undone: set[str] = set()

    def moved(changes: Iterable[Change | None], put: list, out: list) -> None:
        # What a winner moving takes out of force, and the closing of the thread its
        # new winner answers, which it puts in.
        for change in changes:
            if change is None:
                continue
            if change.before is not None:
                out.append(change.before["id"])
            if change.after is not None and (
                answered := threads.get(change.after["meaning"].get("answer"))
            ):
                put.append((answered, change.after, True))

    # Each containment takes hold just before its place, so what it moves stands
    # there and no event at the place has happened yet.
    switches = iter(containments)
    switch = next(switches, None)
    for e in [*events, None]:
        while switch is not None and (e is None or (e.get("seq") or inf) >= switch[0]):
            put, out = [], []
            moved(in_force.contain(switch[1]), put, out)
            closures.step(switch[0] - 0.5, put, out)
            switch = next(switches, None)
        if e is None:
            break
        # Every turn said in a thread stays in its history, and so does the user
        # taking one back, so what an answer settled stays settled
        # (`settled_through`).
        home = (
            said_in.get(e["undoes"])
            if e["kind"] == "undo"
            else thread_for.get(e.get("parent", e.get("message")))
        )
        if home is not None and (turn := _turn(e)):
            home["turns"].append(turn)
            said_in[e["id"]] = home
        # Whether each thread stands closed, at this place (``closures``): what the
        # event puts in force and what it takes out of it.
        kind = e["kind"]
        put, out = [], []
        if kind == "undo":
            undone.add(e["undoes"])
            out = [e["undoes"], *rewrites.get(e["undoes"], ())]
            changes = [in_force.withdraw(e["undoes"])]
        elif kind == "action":
            changes = [in_force.admit(e)]
        else:
            changes = in_force.restate(e) if kind == "note" else []
        moved(changes, put, out)
        # A resolve naming a comment that opened a thread nothing else stands on
        # closes nothing once the user takes the comment back: the thread is gone.
        if kind in ("resolve", "unresolve") and (thread := thread_for.get(e["parent"])):
            put.append((thread, e, kind == "resolve"))
        elif (
            kind == "reply" and _resumes(e) and (thread := thread_for.get(e["parent"]))
        ):
            put.append((thread, e, False))
        elif (
            kind == "edit"
            and e["author"] != "agent"
            and e["message"] not in undone
            and (thread := thread_for.get(e["message"]))
        ):
            put.append((thread, e, False))
            rewrites.setdefault(e["message"], []).append(e["id"])
        # An event admission is still deciding has no place in the log yet.
        closures.step(e.get("seq"), put, out)
        # A gesture the user took back settles nothing, whichever way it settled:
        # the log holds it and no reading of the log stands on it.
        if e["id"] in withdrawn and e["id"] not in standing:
            # A resolve may name a reply since taken back from its thread, and still
            # closes that thread.
            if e["kind"] == "reply" and e["parent"] in thread_for:
                thread_for[e["id"]] = thread_for[e["parent"]]
            continue
        if e["kind"] == "comment":
            message = message_reading(e, undos.get(e["id"]))
            messages[e["id"]] = message
            thread = {
                "id": e["id"],
                "root": message,
                "title": e.get("title"),
                "anchor": message.get("anchor"),
                "detached_from": None,
                "rewritten_from": None,
                "msgs": [message],
                "revisions": [],
                "turns": [],
                "closures": [],
                "resolved": None,
            }
            threads[e["id"]] = thread
            thread_for[e["id"]] = thread
            if turn := _turn(e):
                thread["turns"].append(turn)
                said_in[e["id"]] = thread
            continue
        if e["kind"] == "thread_title":
            if thread := threads.get(e["thread"]):
                thread["title"] = e["title"]
            continue
        if e["kind"] == "reanchor":
            if thread := threads.get(e["thread"]):
                previous = thread["anchor"]
                thread["rewritten_from"] = previous if e["anchor"] else None
                thread["detached_from"] = previous if e["anchor"] is None else None
                thread["anchor"] = e["anchor"]
            continue
        if e["kind"] == "edit":
            message = messages.get(e["message"])
            # A rewrite of a message since taken back changes words no reading shows.
            if message is not None and "withdrawn" not in message:
                # The user rewriting their words speaks again, as a reply would: the
                # agent owes the new wording an answer, and a closed thread opens. The
                # revision keeps the words it replaced, which answers already given
                # were about.
                if e["author"] != "agent":
                    thread = thread_for[e["message"]]
                    thread["revisions"].append({**e, "was": message["text"]})
                # The message says when it was last rewritten, and what it said before,
                # so a reader of the thread alone sees which answers were about other
                # words.
                message["edited"] = {
                    **{key: e[key] for key in ("id", "seq", "ts")},
                    "was": message["text"],
                }
                message["text"] = e["text"]
            continue
        if e["kind"] == "reply":
            thread = thread_for[e["parent"]]
            message = message_reading(e, undos.get(e["id"]))
            messages[e["id"]] = message
            thread["msgs"].append(message)
            thread_for[e["id"]] = thread
            # A reply taken back keeps only its place: it names, reopens and moves
            # nothing.
            if "withdrawn" in message:
                continue
            if thread["title"] is None and "title" in e:
                thread["title"] = e["title"]
            if "anchor" in e:
                thread["detached_from"] = (
                    thread["anchor"] if e["anchor"] is None else None
                )
                thread["anchor"] = e["anchor"]
                thread["rewritten_from"] = None
    for thread in threads.values():
        thread["resolved"] = closures.standing(thread)
    return threads


def _resumes(reply: dict) -> bool:
    """Whether a reply resumes its thread: reactions, failure receipts and progress
    leave its closure in force."""
    return (
        "token" not in reply and "failure" not in reply and not reply.get("ephemeral")
    )


class _ClosureHistory:
    """Each thread's closings and reopenings in force, in log order, and when it
    stood closed (`build_threads`, ``closures``). The latest in force decides; one
    taken out leaves the one before it deciding, wherever it was put in. A step
    costs what its threads hold in force: their spoken messages, rewrites and
    closings."""

    def __init__(self):
        # thread id → (place, event id, closes, event), in log order.
        self._held: dict[str, list[tuple[float, str, bool, dict]]] = {}
        self._thread: dict[str, dict] = {}

    def standing(self, thread: dict) -> dict | None:
        """The closing that decides the thread now, or None while it is open."""
        held = self._held.get(thread["id"])
        return held[-1][3] if held and held[-1][2] else None

    def step(self, at: float | None, put: list, out: list) -> None:
        """Take out of force each event `out` names, put each `(thread, event,
        closes)` in `put` into it, and record each thread that closed or reopened
        at `at`."""
        before = {}
        for identity in out:
            if (thread := self._thread.pop(identity, None)) is not None:
                before.setdefault(thread["id"], (thread, self.standing(thread)))
                held = self._held[thread["id"]]
                held[:] = [entry for entry in held if entry[1] != identity]
        for thread, event, closes in put:
            before.setdefault(thread["id"], (thread, self.standing(thread)))
            insort(
                self._held.setdefault(thread["id"], []),
                (event.get("seq", inf), event["id"], closes, event),
                key=itemgetter(0),
            )
            self._thread[event["id"]] = thread
        for thread, was in before.values():
            now = self.standing(thread)
            if now is not None and was is None:
                thread["closures"].append({"closed": at, "reopened": None})
            elif was is not None and now is None:
                thread["closures"][-1]["reopened"] = at


def _turn(event: dict) -> dict | None:
    """What a thread's history keeps of a turn, a spoken message that is no progress
    or the user's rewrite of one (`exchange`), or of an undo, which `build_threads`
    keeps only where it takes a turn back: what settles a batch of turns. Other
    events keep nothing."""
    spoken = (
        event["kind"] in kinds_declaring("message")
        and "token" not in event
        and not event.get("ephemeral")
    )
    rewrite = event["kind"] == "edit" and event["author"] != "agent"
    if not (spoken or rewrite or event["kind"] == "undo"):
        return None
    keep = ("id", "seq", "author", "responds", "undoes", "message")
    return {key: event[key] for key in keep if key in event}


# What a message says: its words, its reaction's mark and its drawing, and whether its
# words suggest a rewrite of the page.
SAID = ("text", "token", "drawing", "suggestion")


def message_reading(event: dict, undo: dict | None) -> dict:
    """A message as a thread holds it: the record, or, where `undo` took it back and
    something still stands on it, its place with no words and no mark, `was` keeping
    the words it was sent with, or its reaction's token."""
    if undo is None:
        return dict(event)
    kept = {key: value for key, value in event.items() if key not in SAID}
    was = event.get("token", event.get("text", ""))
    return kept | {
        "text": "",
        "withdrawn": {"id": undo["id"], "ts": undo["ts"], "was": was},
    }


def active_summaries(events: list, threads: dict) -> dict[str, list[dict]]:
    """Current presentation summaries for every thread, by thread id.

    Summaries replace overlapping summaries whole. Editing a covered message, or
    undoing an edit of it, invalidates a summary containing prose, and so does
    taking back a message its thread held when the summary was written, which the
    prose may report wherever the message stood. A fold without prose keeps showing
    the revised originals. Progress completion is separate (`progress_completions`),
    so opening a summary never restores completed progress.
    """
    edits = {}
    edited = {}
    said = {}
    taken = {}
    written = {}
    for event in events:
        if event["kind"] in kinds_declaring("message"):
            # The thread a message was said in, and when, whatever became of it since.
            thread = said[event["parent"]][0] if "parent" in event else event["id"]
            said[event["id"]] = (thread, event["seq"])
        elif event["kind"] == "edit":
            edited[event["id"]] = event["message"]
            edits[event["message"]] = event["seq"]
        elif event["kind"] == "undo" and event["undoes"] in edited:
            edits[edited[event["undoes"]]] = event["seq"]
        elif event["kind"] == "undo" and event["undoes"] in said:
            thread, made = said[event["undoes"]]
            taken.setdefault(thread, []).append((made, event["seq"]))
        elif event["kind"] == "summary" and event["thread"] in threads:
            written.setdefault(event["thread"], []).append(event)
    return {
        thread_id: _thread_summaries(
            thread, written.get(thread_id, []), edits, taken.get(thread_id, [])
        )
        for thread_id, thread in threads.items()
    }


def progress_completions(thread: dict) -> dict[str, dict]:
    """The ordinary agent reply that supersedes each completed progress message.

    The next non-failure agent reply completes all pending progress in its thread.
    Reactions and user messages do not complete it. Presentation and unread share
    this relation independently of explicit summaries and read acknowledgements.
    """
    pending = []
    completed = {}
    for message in spoken_turns(thread):
        if message.get("ephemeral"):
            pending.append(message["id"])
            continue
        if (
            message["kind"] != "reply"
            or message["author"] != "agent"
            or message.get("failure")
        ):
            continue
        completed.update((identity, message) for identity in pending)
        pending = []
    return completed


def _thread_summaries(
    thread: dict, summaries: list, edits: dict, taken: list
) -> list[dict]:
    message_ids = [message["id"] for message in thread["msgs"]]
    positions = {identity: index for index, identity in enumerate(message_ids)}
    # The summaries in force cover disjoint messages, so each message names the one
    # summary covering it, and a new summary finds the ones it replaces through the
    # messages it covers rather than by reading every earlier summary.
    active: dict[str, dict] = {}
    holder: dict[str, str] = {}
    for event in summaries:
        start = positions.get(event["from"])
        end = positions.get(event["through"])
        if start is None or end is None or start > end:
            continue
        covers = message_ids[start : end + 1]
        for replaced in {holder[identity] for identity in covers if identity in holder}:
            for identity in active.pop(replaced)["covers"]:
                del holder[identity]
        if event["text"] and (
            any(edits.get(identity, 0) > event["seq"] for identity in covers)
            or any(made < event["seq"] < undone for made, undone in taken)
        ):
            continue
        active[event["id"]] = {
            "id": event["id"],
            "seq": event["seq"],
            "from": event["from"],
            "through": event["through"],
            "covers": covers,
            "text": event["text"],
            "label": event.get("label", "Earlier discussion"),
        }
        holder.update(dict.fromkeys(covers, event["id"]))
    return sorted(active.values(), key=lambda summary: positions[summary["from"]])


def unanswered_turns(thread: dict) -> list[dict]:
    """The spoken non-agent turns the agent still owes an answer, oldest first.

    The one rule for whose turn a thread is. The newest is the thread's response
    address (`unanswered_agent_turn`): an agent reply whose `responds` names it
    settles every input accumulated through it, and a later input starts a fresh
    batch. Until then each input stays owed, and answering an older one removes
    only that input while the newer address stays owed. Mere log order is not
    settlement: an agent answering an older frozen-widget action after newer user
    input leaves that newer input with the agent.

    Not the agent, rather than the user: `author` is an open string on every message
    contract, and the two the code writes are `user` and `agent`. A line from anywhere
    else therefore reads as owed an answer, which is the direction to err in — an
    unanswered word is invisible to everyone, while one answer too many costs a reply.

    Turns, not marks: a reaction is a mark on a message rather than a word in the
    thread, so an `ok` the user puts on the agent's answer does not hand the thread
    back, and a reaction nobody has replied to is no thread at all. Resolution does
    not enter here; `awaits_agent` adds it. A user's revision is a turn here
    (`exchange`).

    The batches are those of the thread's history (`settled_through`), so taking
    back a turn an answer settled leaves the turns before it settled; only the turns
    still in the exchange can be owed."""
    floor = settled_through(thread)
    responses = {
        turn.get("responds")
        for turn in thread["turns"]
        if turn["seq"] > floor and turn["author"] == "agent"
    }
    return [
        message
        for message in exchange(thread)
        if message["seq"] > floor
        and message["author"] != "agent"
        and message["id"] not in responses
    ]


class Settlement(NamedTuple):
    """One of the agent's turns that settled turns of the user's (`settlements`)."""

    answer: dict
    # The user's turns it settled that no earlier answer had, oldest first.
    turns: list
    # Whether it settled the whole batch standing when it was written.
    batch: bool


def settlements(thread: dict) -> list[Settlement]:
    """Each of the agent's turns that settled turns of the user's, in log order. An
    answer whose `responds` names the newest turn of the batch standing when it was
    written settles that whole batch; one naming an older turn of it settles that
    turn alone, and the batch stands. The walk replays the thread's history
    (`build_threads`, ``turns``), so a turn taken back before the answer, with its
    rewrites, is no part of its batch, and one taken back after it leaves the batch
    settled. A failure receipt names its input as an answer does, so it settles here
    too; `is_answer` tells the two apart."""
    settled = []
    batch = []
    taken = set()
    for turn in thread["turns"]:
        if "undoes" in turn:
            gone = turn["undoes"]
            batch = [
                each for each in batch if gone not in (each["id"], each.get("message"))
            ]
        elif turn["author"] != "agent":
            batch.append(turn)
        elif batch and (responds := turn.get("responds")) is not None:
            whole = responds == batch[-1]["id"]
            named = [
                each
                for each in batch
                if (whole or each["id"] == responds) and each["id"] not in taken
            ]
            taken.update(each["id"] for each in named)
            if whole or named:
                settled.append(Settlement(turn, named, whole))
            if whole:
                batch = []
    return settled


def settled_through(thread: dict) -> int:
    """The seq of the agent's answer that settled the thread's latest batch of the
    user's turns, else 0 (`settlements`)."""
    return max(
        (each.answer["seq"] for each in settlements(thread) if each.batch), default=0
    )


def unanswered_agent_turn(thread: dict) -> dict | None:
    """The thread's response address: the newest turn the agent owes an answer."""
    owed = unanswered_turns(thread)
    return owed[-1] if owed else None


def awaits_agent(thread: dict) -> bool:
    """Whether an open thread's next word is the agent's (`unanswered_turns`).

    This reading says nothing about whether the user owes a word: an ordinary agent
    message may leave the open thread awaiting nobody, while one holding a widget
    that asks, such as an `lf-options`, awaits the user. The browser
    does not receive it: each browser Thread's `attention` aggregates this turn with
    the workflows and obligations open on the thread, so the panel, its filters and the
    margin read one answer to whose turn it is."""
    return bool(not thread["resolved"] and unanswered_turns(thread))


def seat_root(thread: dict) -> str | None:
    """The widget whose thread seat this thread's root stands in.

    An element anchor naming that widget and carrying nothing else, which is the
    runtime's `seatRoot` and the anchor `renderSeats` collects into the seat's
    own view. Narrower than any anchor naming the widget, deliberately: a quote
    anchor points into the widget's words rather than standing in the box it offers,
    and the user can see the difference — one is a note on a phrase, the other is
    the cell."""
    root = thread["root"]
    anchor = thread["anchor"]
    if root.get("about") or not anchor or len(anchor) != 1:
        return None
    return anchor.get("section")


def note_settlements(event: dict, kind: str) -> set[str]:
    """The ids one version note settles for a provisional-information kind."""
    return {
        target["id"] for target in event.get("settles", []) if target["kind"] == kind
    }


def retractions(events: list, upto=None) -> dict:
    """id → the greatest revision whose stamped transition took it back."""
    at = {}
    for event in events:
        if event["kind"] == "note" and (upto is None or event["revision"] <= upto):
            for named in event.get("restated", []):
                at[named] = max(at.get(named, 0), event["revision"])
    return at


def _report_notes(events: list, upto):
    """Each report id a note through revision `upto` settles, with that note."""
    for event in events:
        if event["kind"] == "note" and (upto is None or event["revision"] <= upto):
            for identity in note_settlements(event, "report"):
                yield identity, event


def report_settlements(events: list, upto=None) -> dict:
    """Report event id → the greatest revision whose note settled it."""
    at = {}
    for identity, note in _report_notes(events, upto):
        at[identity] = max(at.get(identity, 0), note["revision"])
    return at


def report_settled_at(events: list, upto=None) -> dict:
    """Report event id → the seq of the first note that settled it: every prefix
    of the log through that seq, and none shorter, reads it settled."""
    at = {}
    for identity, note in _report_notes(events, upto):
        at[identity] = min(at.get(identity, note["seq"]), note["seq"])
    return at


def action_rests_on(event: dict, within: dict) -> list:
    """Declared direct identities under the document's current containment.

    The event keeps the identities the command named, not their ancestor path.
    Moving a named element out of the owner therefore changes its applicability
    (`_holds`). A child the action created (`meaning.creates`) is its fold unit,
    which it rests on whether or not a document holds it yet (`_always_rests`).
    Literal detail values never acquire identity by coinciding with an HTML id.
    """
    owner, *created = _always_rests(event)
    return list(
        dict.fromkeys(
            [
                owner,
                *(
                    identity
                    for identity in event["meaning"]["depends"]
                    if _holds(event, identity, within)
                ),
                *created,
            ]
        )
    )


def _always_rests(event: dict) -> list:
    """What an action rests on whatever a document holds: its owner, and the child
    it created (`meaning.creates`), its fold unit."""
    return [
        event["widget"],
        *([event["meaning"]["unit"]] if event["meaning"].get("creates") else []),
    ]


def _holds(event: dict, identity: str, within: dict) -> bool:
    """Whether the action's owner holds `identity` under the containment `within`:
    the condition on which an action rests on an element it names."""
    return event["widget"] in within.get(identity, ())


def action_retracted(event: dict, floors: dict, within: dict) -> bool:
    """Whether a retraction has taken this action back: true when any id it rests
    on carries a floor from a version later than the one the action was made on.

    One predicate for every reader of liveness — the fold's survival test, the
    words gate's, and the thread a decision settles — because a decision the log
    has taken back has to be absent everywhere at once. It was written out twice
    and a third reader went without: `build_threads` settled a thread on a decision
    and never asked, so a suggestion the next version rewrote came back pending
    with the thread it had answered still filed away, and the user was never asked
    the question again."""
    return any(
        floors.get(i, 0) > event["revision"] for i in action_rests_on(event, within)
    )


class Change(NamedTuple):
    """One coordinate's winner before and after a step of an `InForce` walk."""

    coordinate: tuple
    before: dict | None
    after: dict | None


class InForce:
    """The actions in force at each owner-unit-verb coordinate, in log order, the
    last of them its winner.

    The one reading of which action decides a coordinate. An action stands from its
    admission until an undo withdraws it or a version note retracts what it rests on
    (`action_retracted`), and the latest action in force wins, one answering nothing
    included. A reader of the final state admits the log's actions with `withdrawn`
    and the log's whole `floors` given (the projection fold); a reader of what each
    event changed walks the log in order instead, handing undos to `withdraw` and
    notes to `restate` where they fall (`thread_memberships`, `build_threads`). The
    two agree on where the walk ends.

    What an action rests on depends on the document's containment where it names an
    element its owner must hold (`action_rests_on`), so a reader of the page as each
    revision stood hands each revision's containment to `contain` where it takes
    hold, and every action, retracted or not, is judged again under it: the state
    after `contain` is the one a walk under that containment from the start would
    reach. So a retracted action is kept, with how many of the elements it rests on
    a version has restated since it was made, and stands again where that falls to
    none.

    A step reports a `Change` only where the winner moved: taking out an action
    that was not winning changes no coordinate's reading.

    Each step costs what it touches: a note reaches the actions naming what it
    restates through an index of them, never every action; a containment reaches only
    the actions whose owner gained or lost a restated element they name; and a
    coordinate's winner is the last of its standing actions in log order. A walk is
    therefore linear in the log however many actions one coordinate collects."""

    def __init__(self, within: dict, floors: dict | None = None, withdrawn=frozenset()):
        self.within = within
        self.floors = dict(floors or {})
        self.withdrawn = withdrawn
        self._actions: dict[str, dict] = {}
        self._coordinate: dict[str, tuple] = {}
        # Each kept action's place in log order, which orders a coordinate's standing.
        self._order: dict[str, int] = {}
        self._admitted = 0
        # Each kept action's elements it always rests on, and those it rests on only
        # while its owner holds them (`_always_rests`, `_holds`).
        self._always: dict[str, frozenset] = {}
        self._named: dict[str, frozenset] = {}
        # How many elements each kept action rests on that a version restated since.
        self._retracting: dict[str, int] = {}
        # coordinate → its standing actions, as (order, id), in log order.
        self._standing: dict[tuple, list[tuple[int, str]]] = {}
        # identity → the kept actions naming it, whether or not they rest on it.
        self._naming: dict[str, dict[str, None]] = {}
        # identity → owner → the kept actions that name it as an element their owner
        # must hold, and rest on it only while it does.
        self._held: dict[str, dict[str, dict[str, None]]] = {}
        # The elements so named that a version has restated: all a containment
        # can judge otherwise.
        self._contested: set[str] = set()

    def winner(self, coordinate: tuple) -> dict | None:
        standing = self._standing.get(coordinate)
        return self._actions[standing[-1][1]] if standing else None

    def winners(self) -> dict:
        """Coordinate → its winner, for every coordinate an action stands at."""
        return {
            coordinate: self._actions[standing[-1][1]]
            for coordinate, standing in self._standing.items()
            if standing
        }

    def ids(self) -> frozenset:
        """Every action in force."""
        return frozenset(
            identity for standing in self._standing.values() for _, identity in standing
        )

    def admit(self, action: dict) -> Change | None:
        """Keep `action` at its coordinate, standing unless a version had already
        retracted what it rests on, as from a tab showing an older version; an action
        `withdrawn` is not kept."""
        if action["id"] in self.withdrawn:
            return None
        identity = action["id"]
        coordinate = event_coordinate(action)
        self._actions[identity] = action
        self._coordinate[identity] = coordinate
        self._order[identity] = self._admitted
        self._admitted += 1
        self._retracting[identity] = sum(
            self.floors.get(rested, 0) > action["revision"]
            for rested in action_rests_on(action, self.within)
        )
        always = self._always[identity] = frozenset(_always_rests(action))
        named = self._named[identity] = frozenset(action["meaning"]["depends"]) - always
        for element in always | named:
            self._naming.setdefault(element, {})[identity] = None
        for element in named:
            self._held.setdefault(element, {}).setdefault(action["widget"], {})[
                identity
            ] = None
            if self.floors.get(element):
                self._contested.add(element)
        if self._retracting[identity]:
            return None
        before = self.winner(coordinate)
        self._stand(identity)
        return Change(coordinate, before, action)

    def withdraw(self, identity: str) -> Change | None:
        """Take the action `identity` names out, where it stands."""
        action = self._actions.get(identity)
        if action is None:
            return None
        coordinate = self._coordinate[identity]
        before = self.winner(coordinate)
        if not self._retracting[identity]:
            self._fall(identity)
        for element in self._always[identity] | self._named[identity]:
            del self._naming[element][identity]
        for element in self._named[identity]:
            del self._held[element][action["widget"]][identity]
        for kept in (
            self._actions,
            self._coordinate,
            self._order,
            self._retracting,
            self._always,
            self._named,
        ):
            del kept[identity]
        after = self.winner(coordinate)
        return Change(coordinate, before, after) if after is not before else None

    def restate(self, note: dict) -> list[Change]:
        """Retract what a version note restates from every action made on an
        earlier version, and raise its floors for actions admitted after it."""
        moves: dict[str, int] = {}
        for element in note.get("restated", []):
            floor = self.floors.get(element, 0)
            self.floors[element] = max(floor, note["revision"])
            if element in self._held:
                self._contested.add(element)
            for identity in self._naming.get(element, {}):
                action = self._actions[identity]
                if floor <= action["revision"] < note["revision"] and (
                    element in self._always[identity]
                    or _holds(action, element, self.within)
                ):
                    moves[identity] = moves.get(identity, 0) + 1
        return self._retract(moves)

    def contain(self, within: Callable[[], dict]) -> list[Change]:
        """Judge every kept action again under the containment `within` reads, where
        it differs from the one before for an element a version restated and an
        action names as its owner's: its owner gaining that element retracts what
        rests on it, and losing it lets that stand again. `within` is read only where
        some action could be judged otherwise."""
        if not self._contested:
            return []
        now = within()
        if now is self.within:
            return []
        moves: dict[str, int] = {}
        for element in self._contested:
            was, holds = self.within.get(element, ()), now.get(element, ())
            if was == holds:
                continue
            for owner in set(was).symmetric_difference(holds):
                for identity in self._held[element].get(owner, {}):
                    if self.floors[element] > self._actions[identity]["revision"]:
                        step = 1 if owner in holds else -1
                        moves[identity] = moves.get(identity, 0) + step
        self.within = now
        return self._retract(moves)

    def _retract(self, moves: dict[str, int]) -> list[Change]:
        """Move each action's count of restated elements it rests on by `moves`,
        standing it where that falls to none and taking it out where it rises from
        none, and report each coordinate whose winner moved."""
        before: dict[tuple, dict | None] = {}
        for identity, step in moves.items():
            was = self._retracting[identity]
            self._retracting[identity] = was + step
            if bool(was) == bool(was + step):
                continue
            coordinate = self._coordinate[identity]
            before.setdefault(coordinate, self.winner(coordinate))
            if was:
                self._stand(identity)
            else:
                self._fall(identity)
        return [
            Change(coordinate, winner, after)
            for coordinate, winner in before.items()
            if (after := self.winner(coordinate)) is not winner
        ]

    def _stand(self, identity: str) -> None:
        insort(
            self._standing.setdefault(self._coordinate[identity], []),
            (self._order[identity], identity),
        )

    def _fall(self, identity: str) -> None:
        standing = self._standing[self._coordinate[identity]]
        del standing[bisect_left(standing, (self._order[identity], identity))]
