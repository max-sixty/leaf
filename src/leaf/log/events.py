"""Pure folds over the append-only event model."""

from bisect import insort
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from functools import lru_cache
from math import inf
from operator import itemgetter
from typing import NamedTuple

from leaf.base.findings import Finding
from leaf.source.passages import holds_html, message_markup
from leaf.source.registry.kernel import kinds_declaring
from leaf.source.structure import SourceDocument


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
    message markup, which no revision carries: an edit rewrites it in place
    (`thread_structure`). Admission, thread folds, and the browser all key documents on this
    identity."""
    if scope == "thread":
        return {"kind": "thread"}
    return {"kind": "page", "revision": revision}


def event_document(event: dict) -> dict:
    """The document an admitted widget event was made in (`meaning.scope`)."""
    return document_identity(event["meaning"]["scope"], event["revision"])


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
    """Messages that say something, in words or with an emoji, including retained
    progress messages.

    A message the user took back keeps its place with nothing said
    (`build_threads`). Presentation ranges include ephemeral messages; semantic
    turn-taking reads :func:`conversation_turns` instead.
    """
    return [m for m in thread["msgs"] if "withdrawn" not in m]


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
    """A thread that holds only the reaction that opened it, which the page draws as
    a mark on what it is on rather than as a thread (`served_state.thread`)."""
    return "emoji" in thread["root"] and len(thread["msgs"]) == 1


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


class ThreadStructure(NamedTuple):
    ids: set
    by_id: dict
    fragments: dict
    # Every id any wording of an agent's message held → that message.
    holders: dict
    # Each agent message → the logged events that worded it, in force and in log
    # order: the message, then each edit of it.
    wordings: dict


def logged_fragment(event: dict) -> SourceDocument | None:
    """The parse of the markup a logged agent message, or an agent's edit of one, draws
    where its Markdown holds HTML (`passages.holds_html`, `passages.message_markup`),
    shared read-only; None for any other event.

    The log is append-only, so each wording is one immutable fragment for the page's
    lifetime, and every reader of the log takes this one parse of it. The parse is a
    function of the text alone, so it is held by that text, which names it exactly
    whichever page and log it came from. Text a writer hands in has not been admitted
    yet and is another fact: its gate parses it afresh
    (`authored_checks.admission.check_markup`)."""
    if (
        event["kind"] in ("comment", "reply", "edit")
        and event.get("author") == "agent"
        and "text" in event
    ):
        return _fragment(event["text"])
    return None


@lru_cache(maxsize=16384)
def _fragment(text: str) -> SourceDocument | None:
    return SourceDocument(message_markup(text)) if holds_html(text) else None


def thread_structure(events: list) -> ThreadStructure:
    """Each agent message's markup as it now reads, as the panel's id universe: its
    latest edit still in force, else the words it was sent with, the words
    `build_threads` shows. `fragments` is ordered by when each message's current
    wording was written, and `wordings` keeps the ones before it, which a reading of
    an earlier moment takes (`message_wording`).

    `holders` keeps every id any of a message's wordings held, a withdrawn edit's
    included, so no other message or revision takes it (`check_markup`,
    `authored_checks.source`): a gesture the user made on that id would otherwise land
    on another element. The message itself may take it back in a later edit, which is
    how an answered widget keeps its answer."""
    withdrawn = taken_back(events)
    wordings, holders, latest = {}, {}, {}
    for e in events:
        if e["kind"] == "edit":
            message = e["message"]
            if message not in wordings:
                continue
        elif (
            e["kind"] in ("comment", "reply")
            and e.get("author") == "agent"
            and "text" in e
        ):
            message = e["id"]
            wordings[message] = []
        else:
            continue
        fragment = logged_fragment(e)
        if fragment:
            for identity in fragment.ids:
                holders.setdefault(identity, message)
        if e["kind"] != "edit" or e["id"] not in withdrawn:
            wordings[message].append(e)
            latest.pop(message, None)
            latest[message] = fragment
    ids, by_id, fragments = set(), {}, {}
    for message, fragment in latest.items():
        if fragment:
            fragments[message] = fragment
            ids.update(fragment.ids)
            by_id.update(fragment.by_id)
    return ThreadStructure(ids, by_id, fragments, holders, wordings)


def message_wording(structure: ThreadStructure, message: str, seq: int) -> dict:
    """The event whose words `message` said when the log stood at `seq`: the one a
    gesture logged then was made on, so what it chose is read in the words the user
    saw (`gesture_words`). A gesture names no wording, so one a tab made before an
    edit reached it reads in the edit's words."""
    return [e for e in structure.wordings[message] if e["seq"] <= seq][-1]


def widget_messages(structure: ThreadStructure) -> dict:
    """Widget id → the message whose current markup declares it."""
    return {
        widget: message
        for message, fragment in structure.fragments.items()
        for widget in fragment.by_id
    }


def build_threads(events: list, within: dict, *, withdrawn: set | None = None) -> dict:
    """Fold threads using the admitted answer coordinate.

    Answer effects survive retirement of their source widget. An unrelated action
    of another verb cannot supersede one, while an explicit answer with null
    effect replaces a closing answer without itself closing a thread. ``anchor`` is
    the thread's current page location, and ``detached_from`` retains the last real
    anchor when a null replacement or removed passage leaves the thread detached.
    ``rewritten_from`` retains the anchor a ``reanchor`` moved off, whose quoted words a
    version rewrote, until a reply chooses the thread's place again.
    A new reply resumes the thread; failure receipts and progress leave its
    closure in force, and so does a message the agent sent `unannounced`
    into a thread the user resolved (`thread.post_reply`). A later resolution closes
    it again.
    ``revisions`` holds the user's edits in log order, each with ``was``, the words
    it replaced: each shows as its message's wording and stands in the exchange as a
    turn of its own (`exchange`), so it resumes the thread as a reply does.
    ``turns`` is the thread's history of the user's inputs and the agent's answers, in
    log order, which `settle` walks: every turn said in the thread, the ones since
    taken back included, each action on a widget a message in it sent, from each place
    the action comes into force (shown with that place as its ``seq``), and each undo
    that took one of them back. Only the server reads it.

    Whether a thread stands closed is read at every place in the log
    (`_ClosureHistory`): the latest closing or reopening still in force decides it.
    A closing is a resolution, or an action winning its coordinate whose answer
    names the thread; a reopening is an unresolve, a spoken reply, or the user's
    rewrite of a message. Taking one back, an action superseded, or a version
    retracting it (`InForce`) leaves the one before deciding, at the place where
    that happened. ``closures`` holds each time a closing answered for the thread
    (`_ClosureHistory.answering`), in log order: the seq it ``closed`` at and the seq
    it ``reopened`` at, or null while it stands, so what such a closing ended stayed
    ended until then (`provenance.saved_after`). The user's own resolve begins none:
    what the agent owes in the thread stays owed across it.
    ``closings`` holds each closing still in force, in log order, however the thread
    reopened since, which ends every question asked before it (`obligations`).
    ``answered_by`` is the closing that answers for a closed thread
    (`_ClosureHistory.answering`), or null (`owed_turns`), and ``closed_by_user`` says
    whether the user's own resolve is among the closings in force since the thread
    last stood open, whatever closed it after (`thread.post_reply`). Only the server
    reads these four. ``resolved`` is the closing that stands at the end of the log,
    or null.

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
    message_kinds = kinds_declaring("message")
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
    # Each widget an agent's message sends → that message.
    sent_by = widget_messages(thread_structure(events))

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

    for e in events:
        # Every turn said in a thread stays in its history, and so does the user
        # taking one back, so what an answer settled stays settled
        # (`settle`).
        home = (
            said_in.get(e["undoes"])
            if e["kind"] == "undo"
            else thread_for.get(e.get("parent", e.get("message")))
        )
        if home is not None and in_history(e, message_kinds):
            home["turns"].append(e)
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
        # An action on a widget a message in the thread sent joins the thread's
        # history wherever it comes into force: where it is made, and where an undo
        # of the action that replaced it brings it back.
        for change in changes:
            if (
                change is not None
                and (action := change.after) is not None
                and (thread := thread_for.get(sent_by.get(action["widget"])))
            ):
                thread["turns"].append(
                    action if action is e else {**action, "seq": e["seq"]}
                )
                said_in[action["id"]] = thread
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
                "closings": [],
                "resolved": None,
                "answered_by": None,
                "closed_by_user": False,
            }
            threads[e["id"]] = thread
            thread_for[e["id"]] = thread
            if in_history(e, message_kinds):
                thread["turns"].append(e)
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
                message.update(rewritten(message, e))
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
        thread["answered_by"] = closures.answering(thread)
        thread["closed_by_user"] = any(
            _users_resolve(closing) for closing in closures.since_open(thread)
        )
        thread["closings"] = closures.closings(thread)
    return threads


def _resumes(reply: dict) -> bool:
    """Whether a reply resumes its thread: failure receipts and progress leave its
    closure in force, and so does a message the agent sent into a thread
    the user resolved without asking them anything (`unannounced`,
    `thread.post_reply`)."""
    return not (
        "failure" in reply or reply.get("ephemeral") or reply.get("unannounced")
    )


def _users_resolve(closing: dict) -> bool:
    """Whether a closing is the user's own resolve, which takes the thread off their
    list and answers nothing in it (`owed_turns`)."""
    return closing["kind"] == "resolve" and closing["author"] == "user"


class _ClosureHistory:
    """Each thread's closings and reopenings in force, in log order, and when a
    closing answered for it (`build_threads`, ``closures``). The latest in force decides; one
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

    def answering(self, thread: dict) -> dict | None:
        """The newest closing that answers for the thread, of those in force since
        it last stood open, or None: any closing but the user's own resolve, which
        takes the thread off their list and settles nothing the agent owes
        (`owed_turns`). The user resolving a thread the agent already closed leaves
        the agent's closing answering for it."""
        return next(
            (
                closing
                for closing in self.since_open(thread)
                if not _users_resolve(closing)
            ),
            None,
        )

    def since_open(self, thread: dict) -> Iterator[dict]:
        """The closings in force since the thread last stood open, newest first."""
        for _place, _identity, closes, event in reversed(
            self._held.get(thread["id"], ())
        ):
            if not closes:
                return
            yield event

    def closings(self, thread: dict) -> list[dict]:
        """The thread's closings in force, in log order."""
        return [
            event for _, _, closes, event in self._held.get(thread["id"], []) if closes
        ]

    def step(self, at: float | None, put: list, out: list) -> None:
        """Take out of force each event `out` names, put each `(thread, event,
        closes)` in `put` into it, and record each thread a closing began or stopped
        answering for at `at`."""
        before = {}
        for identity in out:
            if (thread := self._thread.pop(identity, None)) is not None:
                before.setdefault(thread["id"], (thread, self.answering(thread)))
                held = self._held[thread["id"]]
                held[:] = [entry for entry in held if entry[1] != identity]
        for thread, event, closes in put:
            before.setdefault(thread["id"], (thread, self.answering(thread)))
            insort(
                self._held.setdefault(thread["id"], []),
                (event.get("seq", inf), event["id"], closes, event),
                key=itemgetter(0),
            )
            self._thread[event["id"]] = thread
        for thread, was in before.values():
            now = self.answering(thread)
            if now is not None and was is None:
                thread["closures"].append({"closed": at, "reopened": None})
            elif was is not None and now is None:
                thread["closures"][-1]["reopened"] = at


def in_history(event: dict, messages: frozenset[str]) -> bool:
    """Whether a thread's history keeps an event as a turn: a message, of
    `messages`' kinds, that is no progress, or the user's rewrite of one
    (`exchange`), or an undo, which `build_threads` keeps only where it takes a turn
    back: what settles a batch of turns."""
    kind = event["kind"]
    if kind in messages:
        return not event.get("ephemeral")
    return kind == "undo" or (kind == "edit" and event["author"] != "agent")


# What a message says: its words, its reaction's emoji and its drawing, and whether its
# words suggest a rewrite of the page.
SAID = ("text", "emoji", "drawing", "suggestion")


def rewritten(message: dict, edit: dict) -> dict:
    """What a rewrite changes of a message as a thread holds it (`message_reading`):
    its words, and `edited`, when it was last rewritten and what it said before, so a
    reader of the thread alone sees which answers were about other words. A rewrite to
    no words deletes the message (`deleted` in state/thread/model.js)."""
    return {
        "text": edit["text"],
        "edited": {
            **{key: edit[key] for key in ("id", "seq", "ts")},
            "was": message["text"],
        },
    }


def message_reading(event: dict, undo: dict | None) -> dict:
    """A message as a thread holds it: the record, or, where `undo` took it back and
    something still stands on it, its place with no words and no mark, `was` keeping
    the words it was sent with, or its reaction's emoji."""
    if undo is None:
        return dict(event)
    kept = {key: value for key, value in event.items() if key not in SAID}
    was = event.get("emoji", event.get("text", ""))
    return kept | {
        "text": "",
        "withdrawn": {"id": undo["id"], "ts": undo["ts"], "was": was},
    }


def active_summaries(events: list, threads: dict) -> dict[str, list[dict]]:
    """Current presentation summaries for every thread, by thread id.

    A summary stands until a later one overlapping it replaces it whole, or until a
    message bounding its range leaves the thread. An edit or a take-back of any other
    message, the user's or the agent's, leaves it standing as written: the agent hears
    of the change, judges whether the summary still holds, and summarizes the range
    again where it doesn't. `thread.cmd_edit` names the summary over a message the
    agent edits, and the handling of the user's edit in a thread that holds a summary
    asks the agent to check it (the kernel registry's `edit` clauses). The maintainer
    chose this. Retiring a summary on the user's change,
    which a later change might reach for so that no summary hides the user's words,
    decides for the agent whether the summary still holds, as root `AGENTS.md`'s
    "Leaf's role" says code doesn't. A summary folds no progress: the thread shows
    only the steps nothing has superseded, as working messages
    (`progress_completions`).
    """
    written = {}
    for event in events:
        if event["kind"] == "summary" and event["thread"] in threads:
            written.setdefault(event["thread"], []).append(event)
    return {
        thread_id: _thread_summaries(thread, written.get(thread_id, []))
        for thread_id, thread in threads.items()
    }


def progress_completions(thread: dict) -> dict[str, dict]:
    """The agent message that supersedes each progress message of `thread`: the next
    one the agent says in it, a step, an answer or a failure. A step the user wrote
    after waits for the agent's next message that is more than a step, so a step said
    below the user's message leaves the one above it standing. So the thread holds at
    most one step it hasn't superseded between two of the user's messages, its newest,
    and a step never moves the user's message by ending above it. The turn that wrote a step can end it too, which the log doesn't say
    (`served_state.thread.progress_ends`)."""
    pending = None
    spoken_after: list[str] = []
    completed = {}
    for message in spoken_turns(thread):
        if message["author"] != "agent":
            if pending is not None:
                spoken_after.append(pending)
            pending = None
            continue
        if pending is not None:
            completed[pending] = message
        if message.get("ephemeral"):
            pending = message["id"]
            continue
        completed.update((step, message) for step in spoken_after)
        pending, spoken_after = None, []
    return completed


def _thread_summaries(thread: dict, summaries: list) -> list[dict]:
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
        active[event["id"]] = {
            "id": event["id"],
            "seq": event["seq"],
            "from": event["from"],
            "through": event["through"],
            "covers": covers,
            "text": event["text"],
            **({"label": event["label"]} if "label" in event else {}),
        }
        holder.update(dict.fromkeys(covers, event["id"]))
    return sorted(active.values(), key=lambda summary: positions[summary["from"]])


def unanswered_turns(thread: dict) -> list[dict]:
    """The spoken non-agent turns the agent still owes an answer, oldest first: the
    turns still waiting in the thread's history (`settle`).

    Not the agent, rather than the user: `author` is an open string on every message
    contract, and the two the code writes are `user` and `agent`. A line from anywhere
    else therefore reads as owed an answer, which is the direction to err in — an
    unanswered word is invisible to everyone, while one answer too many costs a reply.

    A reaction is a turn as words are, so a 👍 the user puts on the agent's answer
    hands the thread back, and the agent's emoji answers as a reply in words does
    (`events.md`, "Reactions"). Resolution does not enter here: `owed_turns` says
    which closings settle these turns. A user's revision is a turn here
    (`exchange`), and only the turns still in the exchange can be owed.

    The newest of these is not always where the thread's answer goes: an owed action
    on a widget sent in the thread waits beside them, and where it came last the
    answer is addressed to it (`workflows.handed_over`)."""
    waiting = {turn["id"] for turn in settle(thread).waiting}
    return [
        message
        for message in exchange(thread)
        if message["author"] != "agent" and message["id"] in waiting
    ]


class Settlement(NamedTuple):
    """One of the agent's turns that settled inputs of the user's (`settle`)."""

    answer: dict
    # The inputs it settled, oldest first.
    turns: list


class Settled(NamedTuple):
    """A thread's history walked (`settle`): each of the agent's turns that settled
    inputs of the user's, in log order, the inputs still waiting, oldest first, and
    the place each input last entered the waiting list, taken back or not."""

    settlements: list[Settlement]
    waiting: list[dict]
    places: dict[str, int]


def settle(thread: dict) -> Settled:
    """Which of the user's inputs in a thread each of the agent's turns settled, and
    which still wait.

    The inputs are the user's turns and their actions on widgets sent in the thread,
    each at its place in the thread's history (`build_threads`, ``turns``). An agent
    turn whose `responds` names an input settles every input waiting at or before
    that input's place: a write at a reference goes in only while it names the
    thread's newest standing input (`thread.post_reply`), so it answers everything
    the thread held up to there. An input taken back before the answer, with its rewrites, is no part
    of what it settles, and one taken back after it leaves the settlement standing.
    An action an undo brings back enters again at the place it came back, whether it
    was still waiting or settled, so a write at the thread's newest input after it
    answers it. A reference names an input by id, so a write still holding the
    reference the action had before it changed and came back answers up to the
    later place too.
    A failure receipt names its input as an answer does, so it settles here too;
    `is_answer` tells the two apart.

    The history comes from the log alone, so every reader settles a thread the same
    way, with a registry or without one. It holds every action on a widget sent in the
    thread, one that owes nothing included, such as a pick still waiting for its
    group's Done; `workflows` decides which waiting actions are owed."""
    settled = []
    waiting: OrderedDict[str, dict] = OrderedDict()
    places: dict[str, int] = {}
    # Each message → the ids of its rewrites still waiting, which leave with it.
    rewrites: dict[str, list[str]] = {}
    for turn in thread["turns"]:
        if "undoes" in turn:
            gone = turn["undoes"]
            for identity in [gone, *rewrites.pop(gone, ())]:
                waiting.pop(identity, None)
        elif turn["author"] != "agent":
            if turn["id"] in waiting:
                waiting.move_to_end(turn["id"])
            elif turn["kind"] == "edit":
                rewrites.setdefault(turn["message"], []).append(turn["id"])
            waiting[turn["id"]] = turn
            places[turn["id"]] = turn["seq"]
        elif (responds := turn.get("responds")) in places:
            taken = []
            while waiting and places[next(iter(waiting))] <= places[responds]:
                taken.append(waiting.popitem(last=False)[1])
            if taken:
                settled.append(Settlement(turn, taken))
    return Settled(settled, list(waiting.values()), places)


def unanswered_agent_turn(thread: dict) -> dict | None:
    """The newest turn the agent owes an answer (`unanswered_turns`)."""
    owed = unanswered_turns(thread)
    return owed[-1] if owed else None


def owed_turns(thread: dict) -> list[dict]:
    """The turns the agent owes an answer now, in a closed thread as in an open one,
    oldest first (`unanswered_turns`).

    The user's resolve takes a thread off their list and settles nothing the agent
    owes in it. A request made before it stays owed, and the reply that answers it
    goes into the thread and leaves it closed unless it asks (`thread.post_reply`,
    `unannounced`).
    The user chose
    this over a resolve that dropped the request, which left nothing on the page
    saying the agent owed it; cancelling a request takes their words. Every other
    closing answers for the thread: the
    agent's own resolve, which says the thread wants no answer, and the user's
    answer on a widget whose `resolves` names the thread, the decision the agent
    offered them there. From such a closing until the thread reopens it owes
    nothing (``answered_by``), and reopening it puts the turns back.

    This reading says nothing about whether the user owes a word: an ordinary agent
    message may leave the thread awaiting nobody, while one holding a widget that
    asks, such as an `lf-options`, awaits the user. The browser does not receive it:
    each browser Thread's `attention` aggregates this turn with the workflows and
    obligations open on the thread, so the panel, its filters and the margin read
    one answer to whose turn it is."""
    return [] if thread["answered_by"] else unanswered_turns(thread)


def unlined(thread: dict, through: int | None = None) -> list[dict]:
    """The user's turns waiting in `thread` (`unanswered_turns`), oldest first, while
    the thread stands open and the agent has said nothing in it since the oldest of
    them, by a message or a rewrite of one: a round that awaits the line fork's line
    (`forks`); else none.

    `through` reads the round as it stood at that seq, as the follower reads it as
    its newest turn arrived (`forks.look`) and a delivery as the message it carries
    did (`thread_context.batch_threads`). That reading counts the agent's messages
    alone: the fold keeps only a message's latest rewrite, so counting rewrites
    would let a later one change what an earlier moment read, and the follower and
    a delivery must read each round the same way for good. A rewrite counts where
    it matters, in the reading that decides whether the line goes in."""
    if thread["resolved"]:
        return []
    waiting = [
        turn
        for turn in unanswered_turns(thread)
        if through is None or turn["seq"] <= through
    ]
    if not waiting or any(
        waiting[0]["seq"] < said and (through is None or said <= through)
        for message in spoken_turns(thread)
        if message["author"] == "agent"
        for said in (
            (message["seq"], message.get("edited", {}).get("seq", 0))
            if through is None
            else (message["seq"],)
        )
    ):
        return []
    return waiting


def seat_root(thread: dict) -> str | None:
    """The widget whose thread seat this thread's root stands in.

    An element anchor naming that widget and carrying nothing else, which is the
    runtime's `seatRoot` and the thread a widget is offered an outlet of its own
    for (`threadOutlets`). Narrower than any anchor naming the widget, deliberately:
    a quote anchor points into the widget's words rather than standing in the place
    it offers, and the user can see the difference — one is a note on a phrase, the
    other is the cell."""
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
    Moving a named element out of the owner therefore changes its applicability.
    A child the action created (`meaning.creates`) is its fold unit, which it rests
    on whether or not a document holds it yet. Literal detail values never acquire
    identity by coinciding with an HTML id.
    """
    widget = event["widget"]
    return list(
        dict.fromkeys(
            [
                widget,
                *(
                    identity
                    for identity in event["meaning"]["depends"]
                    if widget in within.get(identity, ())
                ),
                *(
                    [event["meaning"]["unit"]]
                    if event["meaning"].get("creates")
                    else []
                ),
            ]
        )
    )


def action_retracted(event: dict, floors: dict, within: dict) -> bool:
    """Whether a retraction has taken this action back: true when any id it rests
    on carries a floor from a version later than the one the action was made on.

    One predicate for every reader of liveness — the fold's survival test, the
    words gate's, and the thread a decision settles — because a decision the log
    has taken back has to be absent everywhere at once. A reader that goes without,
    as `build_threads` settling a thread on a decision without asking would, brings
    a suggestion the next version rewrote back pending with the thread it answered
    still filed away, and the user is never asked the question again."""
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

    A step reports a `Change` only where the winner moved: taking out an action
    that was not winning changes no coordinate's reading.

    Each step costs what it touches: a note reaches the actions resting on what it
    restates through an index of them, never every action in force, and a
    coordinate's winner is the tail of a linked order, which taking actions out
    leaves constant to reach. A walk is therefore linear in the log however many
    actions one coordinate collects."""

    def __init__(self, within: dict, floors: dict | None = None, withdrawn=frozenset()):
        self.within = within
        self.floors = dict(floors or {})
        self.withdrawn = withdrawn
        self._at: dict[tuple, OrderedDict[str, dict]] = {}
        self._coordinate: dict[str, tuple] = {}
        # identity → the actions in force resting on it, in log order.
        self._resting: dict[str, OrderedDict[str, None]] = {}

    def winner(self, coordinate: tuple) -> dict | None:
        actions = self._at.get(coordinate)
        return actions[next(reversed(actions))] if actions else None

    def winners(self) -> dict:
        """Coordinate → its winner, for every coordinate an action stands at."""
        return {
            coordinate: actions[next(reversed(actions))]
            for coordinate, actions in self._at.items()
            if actions
        }

    def ids(self) -> frozenset:
        """Every action in force."""
        return frozenset(self._coordinate)

    def admit(self, action: dict) -> Change | None:
        """Stand `action` at its coordinate, unless it was withdrawn or a version had
        already retracted it on arrival, as from a tab showing an older version."""
        if action["id"] in self.withdrawn or action_retracted(
            action, self.floors, self.within
        ):
            return None
        coordinate = event_coordinate(action)
        before = self.winner(coordinate)
        self._at.setdefault(coordinate, OrderedDict())[action["id"]] = action
        self._coordinate[action["id"]] = coordinate
        for identity in action_rests_on(action, self.within):
            self._resting.setdefault(identity, OrderedDict())[action["id"]] = None
        return Change(coordinate, before, action)

    def withdraw(self, identity: str) -> Change | None:
        """Take the action `identity` names out, where it stands."""
        coordinate = self._coordinate.get(identity)
        if coordinate is None:
            return None
        before = self.winner(coordinate)
        self._remove(identity)
        after = self.winner(coordinate)
        return Change(coordinate, before, after) if after is not before else None

    def restate(self, note: dict) -> list[Change]:
        """Retract what a version note restates from every action made on an
        earlier version, and raise its floors for actions admitted after it."""
        restated = note.get("restated", [])
        for identity in restated:
            self.floors[identity] = max(self.floors.get(identity, 0), note["revision"])
        hit: dict[tuple, dict[str, None]] = {}
        for identity in restated:
            for action_id in self._resting.get(identity, {}):
                coordinate = self._coordinate[action_id]
                if self._at[coordinate][action_id]["revision"] < note["revision"]:
                    hit.setdefault(coordinate, {})[action_id] = None
        changes = []
        for coordinate, retracted in hit.items():
            before = self.winner(coordinate)
            for action_id in retracted:
                self._remove(action_id)
            if (after := self.winner(coordinate)) is not before:
                changes.append(Change(coordinate, before, after))
        return changes

    def _remove(self, identity: str) -> None:
        coordinate = self._coordinate.pop(identity)
        action = self._at[coordinate].pop(identity)
        for rested in action_rests_on(action, self.within):
            self._resting[rested].pop(identity, None)
