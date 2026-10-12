"""Pure folds over the append-only event model."""

from collections import OrderedDict
from itertools import groupby
from typing import NamedTuple

from leaf.schema import MESSAGE_KINDS, UNDOABLE_KINDS


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


def standing_approvals(events: list, *, withdrawn: set | None = None) -> list:
    """The sign-off approvals no later undo took back, in log order."""
    if withdrawn is None:
        withdrawn = taken_back(events)
    return [
        event
        for event in events
        if event["kind"] == "done" and event["id"] not in withdrawn
    ]


def is_reaction(event: dict) -> bool:
    """A message carrying a token in place of words ($events, $reactions)."""
    return bool(event.get("token"))


def spoken_turns(thread: dict) -> list:
    """Messages with words, including retained progress messages.

    Reactions are marks rather than words. Presentation ranges include ephemeral
    messages; semantic turn-taking reads :func:`conversation_turns` instead.
    """
    return [m for m in thread["msgs"] if not is_reaction(m)]


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

    The browser exposes every standing gesture in one reading, so checking each
    candidate by folding the event log again turns a linear state read into a
    quadratic one. This index computes the shared facts once: event identity,
    withdrawals, and the reaction's thread status. The append door uses the
    same reading for its authoritative check, while callers that only have one
    candidate can keep using :func:`undo_error`.

    ``threads`` may be supplied by a caller that already folded the same log.
    Otherwise, ``within`` is required to fold the threads; it is not read when
    threads are supplied. This is a reading rather than another source of state:
    the event log and page containment remain the authorities, and this object
    only indexes their validated projection.
    """

    def __init__(
        self,
        events: list,
        *,
        threads: dict | None = None,
        within: dict | None = None,
        withdrawn: set | None = None,
        absorbed: frozenset,
    ):
        self.events_by_id = {event["id"]: event for event in events}
        self.withdrawn = taken_back(events) if withdrawn is None else withdrawn
        self.absorbed = absorbed
        if threads is None:
            if within is None:
                raise TypeError("within is required when threads are not supplied")
            # Only reactions ask about thread state. Keeping this fold lazy
            # also preserves the boundary's ability to reject a non-reaction
            # gesture without interpreting unrelated, already-validated records.
            threads = (
                build_threads(events, within, withdrawn=self.withdrawn)
                if any(
                    event.get("token")
                    for event in events
                    if event["kind"] in MESSAGE_KINDS
                )
                else {}
            )
        answered_reactions = set()
        resolved_reactions = set()
        reaction_ids = {
            event["id"]
            for event in events
            if event["id"] not in self.withdrawn
            and event["kind"] in MESSAGE_KINDS
            and is_reaction(event)
        }
        for thread in threads.values():
            messages = thread["msgs"]
            for message in messages:
                if not is_reaction(message) and message.get("parent") in reaction_ids:
                    answered_reactions.add(message["parent"])
                if thread["resolved"] and message["id"] in reaction_ids:
                    resolved_reactions.add(message["id"])
        self.answered_reactions = answered_reactions
        self.resolved_reactions = resolved_reactions

    def error(self, event: dict) -> str | None:
        """Return the existing rejection for one proposed ``undo`` event."""
        target_id = event["undoes"]
        target = self.events_by_id.get(target_id)
        if target is None:
            return f"unknown undoes {target_id!r}"
        if target["author"] != "user":
            return f"{target['kind']} {target['id']} is not the user's own gesture"
        if target["id"] in self.withdrawn:
            return f"{target['id']} has already been taken back"
        if target["kind"] in MESSAGE_KINDS:
            if not is_reaction(target):
                return (
                    f"{target['kind']} {target['id']} is not a reaction; a message "
                    "with words in it is said rather than unsaid"
                )
            if target["id"] in self.answered_reactions:
                return (
                    f"reaction {target['id']} has been answered; withdraw it in the "
                    "thread the answer opened"
                )
            if target["id"] in self.resolved_reactions:
                return f"reaction {target['id']} stands on a resolved thread"
        elif target["kind"] not in UNDOABLE_KINDS:
            return (
                f"{target['kind']} events cannot be taken back (the kinds that can "
                f"are {', '.join(sorted(UNDOABLE_KINDS))} and a reaction)"
            )
        elif target["kind"] == "action" and target["id"] in self.absorbed:
            # The newest revision's markup places the unit
            # (`StateProjection.absorbed`), so taking the move back would restore
            # nothing; a new move changes where the unit stands.
            return (
                f"move {target['id']} was made on r{target['revision']}, and a "
                "later revision's markup now places its unit; move it again instead"
            )
        return None


def undo_error(
    event: dict,
    events: list,
    within: dict,
    absorbed: frozenset,
) -> str | None:
    """Why this undo may not take back the event it names, or None.

    Checked once here, at the door the browser writes through, so nothing
    downstream asks a second time whether an `undoes` points at something real.
    Two tabs racing to take back the same event are the one case this refuses
    that nothing is wrong with: the second is a no-op, and refusing it costs a
    notice where accepting it would leave two withdrawals of one gesture in a log
    whose every other line is something the user did.

    A reaction is the one message a user takes back rather than answers,
    and only while it still paints: once a turn answers it the withdrawal
    would orphan those words, and the user's update is in the thread that
    turn opened; once its thread is resolved, resolve being its floor, there
    is nothing left to take back. The browser offers exactly the gestures
    this reading admits (`served_state.document.browser_undo_candidates`).

    `within` is the published page's containment, as every other fold of the
    threads takes it: a thread an action settled, and a version's `restated`
    inside that widget reopened, is open here as it is in `page state`.
    `absorbed` is the newest revision's absorbed moves, whose units its markup
    places."""
    return UndoReading(events, within=within, absorbed=absorbed).error(event)


def build_threads(events: list, within: dict, *, withdrawn: set | None = None) -> dict:
    """Fold threads using the admitted answer coordinate.

    Answer effects survive retirement of their source widget. An unrelated action
    of another verb cannot supersede one, while an explicit answer with null
    effect replaces a closing answer without itself closing a thread. ``anchor`` is
    the thread's current page location, and ``detached_from`` retains the last real
    anchor when a null replacement or removed passage leaves the thread detached.
    ``rewritten_from`` retains the anchor a ``reanchor`` moved off, whose quoted words a
    version rewrote, until a reply chooses the thread's place again.
    A new spoken reply resumes the thread; reactions and failure receipts
    leave its closure standing. A later resolution closes it again.
    ``revisions`` holds the user's edits in log order, each with ``was``, the words
    it replaced: each shows as its message's wording and stands in the exchange as a
    turn of its own (`exchange`), so it resumes the thread as a reply does.

    Each thread is keyed by, and carries as ``id``, the id of the message that
    opened it: the name every Question, workflow, summary, and title uses for it.
    ``root`` is the first message the log still holds. The two differ only where
    a torn line lost the opening message, and then ``root`` is the surviving
    reply that opens the thread now, under its own id, so a reply or resolve
    addressed to it names a message the log has.
    """
    if withdrawn is None:
        withdrawn = taken_back(events)
    # Every action at a coordinate competes, including a non-answer. Thread
    # settlement and visible state therefore read the same winning gesture.
    standing = Standing(within, retractions(events), withdrawn)
    for e in events:
        if e["kind"] == "action":
            standing.admit(e)
    winners = standing.winners()
    threads = {}
    thread_for = {}
    messages = {}
    for e in events:
        # A gesture the user took back settles nothing, whichever way it settled:
        # the log holds it and no reading of the log stands on it.
        if e["id"] in withdrawn:
            continue
        if e["kind"] == "comment":
            message = dict(e)
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
                "resolved": None,
            }
            threads[e["id"]] = thread
            thread_for[e["id"]] = thread
            continue
        # Read the effect at its own log position, so a person's intervening
        # resolve remains the latest closure even after an answer is superseded.
        if e["kind"] == "action":
            answered = threads.get(e["meaning"].get("answer"))
            if answered and winners.get(event_coordinate(e)) is e:
                answered["resolved"] = e
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
            if message := messages.get(e["message"]):
                # The user rewriting their words speaks again, as a reply would: the
                # agent owes the new wording an answer, and a closed thread opens. The
                # revision keeps the words it replaced, which answers already given
                # were about.
                if e["author"] != "agent":
                    thread = thread_for[e["message"]]
                    thread["revisions"].append({**e, "was": message["text"]})
                    thread["resolved"] = None
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
            # A reply whose message the log lost opens the thread that message would
            # have opened, under the id it was known by, which is the id an action
            # names in `resolves` and the one `thread_names` resolves it to. A person
            # answers it by its own surviving id; the lost one names no message and
            # `leaf thread reply` says so.
            # `read_events` skips a torn line and keeps reading, and `thread_names`
            # resolves such a reply to the lost id for the same reason: a user who
            # can see the reply is owed the rest of the page around it. Raising here
            # instead cost the whole page — `page state` and every browser state read
            # exited on the KeyError — so one torn line took down every reading of a
            # log that had already been read.
            message = dict(e)
            thread = thread_for.get(e["parent"])
            if thread is None:
                thread = {
                    "id": e["parent"],
                    "root": message,
                    "title": None,
                    "anchor": e.get("anchor"),
                    "detached_from": None,
                    "rewritten_from": None,
                    "msgs": [],
                    "revisions": [],
                    "resolved": None,
                }
                threads[e["parent"]] = thread
                thread_for[e["parent"]] = thread
            messages[e["id"]] = message
            thread["msgs"].append(message)
            if thread["title"] is None and "title" in e:
                thread["title"] = e["title"]
            if "token" not in e and "failure" not in e and not e.get("ephemeral"):
                thread["resolved"] = None
            if "anchor" in e:
                thread["detached_from"] = (
                    thread["anchor"] if e["anchor"] is None else None
                )
                thread["anchor"] = e["anchor"]
                thread["rewritten_from"] = None
            thread_for[e["id"]] = thread
        # A resolve names a message rather than opening one, so a thread the log
        # lost whole — no reply of its own survived either — leaves it nothing to close.
        elif e["kind"] == "resolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = e
        elif e["kind"] == "unresolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = None
    return threads


def active_summaries(events: list, threads: dict) -> dict[str, list[dict]]:
    """Current presentation summaries for every thread, by thread id.

    Summaries replace overlapping summaries whole. Editing a covered message
    invalidates a summary containing prose. A fold without prose keeps showing the
    revised originals. Progress messages acquire a fold when the next ordinary
    agent reply arrives. Explicit summaries own any overlap with these derived
    folds; no extra event is written. The original messages remain the authority.
    """
    edits = {}
    written = {}
    for event in events:
        if event["kind"] == "edit":
            edits[event["message"]] = event["seq"]
        elif event["kind"] == "summary" and event["thread"] in threads:
            written.setdefault(event["thread"], []).append(event)
    result = {}
    for thread_id, thread in threads.items():
        explicit = _thread_summaries(thread, written.get(thread_id, []), edits)
        covered = {identity for summary in explicit for identity in summary["covers"]}
        automatic = _thread_summaries(thread, _ephemeral_ranges(thread, covered), {})
        summaries = [*explicit, *automatic]
        positions = {
            message["id"]: index for index, message in enumerate(thread["msgs"])
        }
        result[thread_id] = sorted(
            summaries, key=lambda summary: positions[summary["from"]]
        )
    return result


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


def _ephemeral_ranges(thread: dict, covered: set) -> list[dict]:
    """Contiguous completed progress outside explicit summaries, split by conversation.

    The completing reply is also the presentation dependency: a renderer holding
    that reply must hold its folds with it.
    """
    completed = progress_completions(thread)
    ranges = []
    for reply, messages in groupby(
        spoken_turns(thread),
        key=lambda message: (
            None if message["id"] in covered else completed.get(message["id"])
        ),
    ):
        if reply is None:
            continue
        group = list(messages)
        ranges.append(
            {
                "id": f"ephemeral:{group[0]['id']}:{reply['id']}",
                "seq": reply["seq"],
                "from": group[0]["id"],
                "through": group[-1]["id"],
                "text": "",
                "label": "Previous progress messages",
                "trigger": reply["id"],
            }
        )
    return ranges


def _thread_summaries(thread: dict, summaries: list, edits: dict) -> list[dict]:
    message_ids = [message["id"] for message in thread["msgs"]]
    positions = {identity: index for index, identity in enumerate(message_ids)}
    active = []
    for event in summaries:
        start = positions.get(event["from"])
        end = positions.get(event["through"])
        if start is None or end is None or start > end:
            continue
        covers = message_ids[start : end + 1]
        covered = set(covers)
        active = [
            summary for summary in active if covered.isdisjoint(summary["covers"])
        ]
        if event["text"] and any(
            edits.get(identity, 0) > event["seq"] for identity in covers
        ):
            continue
        active.append(
            {
                "id": event["id"],
                "seq": event["seq"],
                "from": event["from"],
                "through": event["through"],
                "covers": covers,
                "text": event["text"],
                "label": event.get("label", "Earlier discussion"),
                **({"trigger": event["trigger"]} if "trigger" in event else {}),
            }
        )
    return sorted(active, key=lambda summary: positions[summary["from"]])


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
    (`exchange`)."""
    turns = exchange(thread)
    floor = -1
    newest_before = None
    for index, message in enumerate(turns):
        if message["author"] != "agent":
            newest_before = message
        elif (
            newest_before is not None and message.get("responds") == newest_before["id"]
        ):
            floor = index
            newest_before = None
    standing = turns[floor + 1 :]
    responses = {
        message.get("responds") for message in standing if message["author"] == "agent"
    }
    return [
        message
        for message in standing
        if message["author"] != "agent" and message["id"] not in responses
    ]


def unanswered_agent_turn(thread: dict) -> dict | None:
    """The thread's response address: the newest turn the agent owes an answer."""
    owed = unanswered_turns(thread)
    return owed[-1] if owed else None


def awaits_agent(thread: dict) -> bool:
    """Whether an open thread's next word is the agent's (`unanswered_turns`).

    This reading says nothing about whether the user owes a word: an ordinary agent
    reply may leave the open thread awaiting nobody, while an agent comment, an
    explicit prose question, or a structured widget Question awaits the user. The browser
    does not receive it: each browser Thread's `attention` aggregates this turn with
    the workflows and Questions standing on the thread, so the panel, its filters and the
    margin read one answer to whose turn it is."""
    return bool(not thread["resolved"] and unanswered_turns(thread))


def seat_root(thread: dict) -> str | None:
    """The widget whose thread seat this thread's root stands in.

    An element anchor naming that widget and carrying nothing else, which is the
    runtime's `seatRoot` and the anchor `renderSeats` collects into the seat's
    own view. Narrower than any anchor naming the widget, deliberately: a quote
    anchor points into the widget's words rather than standing in the box it offers,
    and the user can see the difference — one is a note on a phrase, the other is
    the cell.

    A reply whose root the log lost is its own root, so the thread seats where the
    thread's latest anchor points, and nowhere at all when no message carried one."""
    root = thread["root"]
    anchor = thread["anchor"]
    if root.get("about") or not anchor or len(anchor) != 1:
        return None
    return anchor.get("section")


def seats_with_agent(threads: dict) -> set[str]:
    """Widget ids whose own seat holds a thread now waiting on the agent.

    An Question whose own thread is with the agent is not one the user has to
    deal with, so a Question projection reading their list subtracts these. It is not an
    answer — the widget's state is untouched — which is why the reading that asks
    whether a Question is answered passes an empty set instead. The browser receives
    the Questions this subtraction leaves rather than subtracting again, so the banner's
    count and `page state` cannot disagree about whose turn it is.

    Whose thread it is does not enter into it: the agent may open one in the seat too,
    and once the user has answered there the question is with the agent either way.

    Takes the built fold rather than the log, because every caller already holds one:
    `build_threads` walks the whole log and tests each action against the retraction
    floors, and a second fold of the same events in the same function is that walk
    done twice for one answer."""
    return {
        seat for t in threads.values() if awaits_agent(t) and (seat := seat_root(t))
    }


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


def report_settlements(events: list, upto=None) -> dict:
    """Report event id → the greatest revision whose note settled it."""
    at = {}
    for event in events:
        if event["kind"] != "note" or (upto is not None and event["revision"] > upto):
            continue
        for identity in note_settlements(event, "report"):
            at[identity] = max(at.get(identity, 0), event["revision"])
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
    has taken back has to be absent everywhere at once. It was written out twice
    and a third reader went without: `build_threads` settled a thread on a decision
    and never asked, so a suggestion the next version rewrote came back pending
    with the thread it had answered still filed away, and the user was never asked
    the question again."""
    return any(
        floors.get(i, 0) > event["revision"] for i in action_rests_on(event, within)
    )


class Change(NamedTuple):
    """One coordinate's winner before and after a step of a `Standing` walk."""

    coordinate: tuple
    before: dict | None
    after: dict | None


class Standing:
    """The actions standing at each owner-unit-verb coordinate, in log order, the
    last of them its winner.

    The one reading of which action decides a coordinate. An action stands from its
    admission until an undo withdraws it or a version note retracts what it rests on
    (`action_retracted`), and the latest action standing wins, one answering nothing
    included. A reader of the final state admits the log's actions with `withdrawn`
    and the log's whole `floors` given (`build_threads`, the projection fold); a
    reader of what each event changed walks the log in order instead, handing undos
    to `withdraw` and notes to `restate` where they fall (`thread_memberships`). The
    two agree on where the walk ends.

    A step reports a `Change` only where the winner moved: taking out an action
    that was not winning changes no coordinate's reading.

    Each step costs what it touches: a note reaches the actions resting on what it
    restates through an index of them, never every action standing, and a
    coordinate's winner is the tail of a linked order, which taking actions out
    leaves constant to reach. A walk is therefore linear in the log however many
    actions one coordinate collects."""

    def __init__(self, within: dict, floors: dict | None = None, withdrawn=frozenset()):
        self.within = within
        self.floors = dict(floors or {})
        self.withdrawn = withdrawn
        self._at: dict[tuple, OrderedDict[str, dict]] = {}
        self._coordinate: dict[str, tuple] = {}
        # identity → the standing actions resting on it, in log order.
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
        """Every action standing."""
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
