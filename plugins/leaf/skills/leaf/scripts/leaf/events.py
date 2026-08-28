"""Pure folds over the append-only event model."""

from leaf import event_log as _event_log
from leaf.schema import MESSAGE_KINDS, UNDOABLE_KINDS

AttemptConflict = _event_log.AttemptConflict
AttemptExecution = _event_log.AttemptExecution
EventAppender = _event_log.EventAppender
_append_event_unlocked = _event_log._append_event_unlocked
_attempt_payload = _event_log._attempt_payload
_matching_attempt = _event_log._matching_attempt
append_event = _event_log.append_event
flocked = _event_log.flocked
jsonl_line = _event_log.jsonl_line
now_iso = _event_log.now_iso
read_cursor = _event_log.read_cursor
read_events = _event_log.read_events
require_cross_process_locking = _event_log.require_cross_process_locking


def taken_back(events: list) -> set:
    """Event ids some later gesture took back (`undoes`).

    An undo names the gesture it withdraws and carries no counter-state, so every
    projection drops those ids. The thread an action answered is open again once
    the answer is withdrawn, and the undo walk steps back past what it has
    already taken."""
    return {e["undoes"] for e in events if e.get("undoes")}


def is_reaction(event: dict) -> bool:
    """A message carrying a token in place of words ($events, $reactions)."""
    return bool(event.get("token"))


def spoken_turns(thread: dict) -> list:
    """The thread's messages with words in them. A reaction is a mark on a
    message rather than a turn in the conversation, so readings of who spoke
    last — including the hook's unanswered asks — walk this list rather than
    `msgs`. The panel's "waiting on you" also reads explicit reply asks and
    structural thread asks in the browser after finding the last spoken turn."""
    return [m for m in thread["msgs"] if not is_reaction(m)]


def bare_reaction(thread: dict) -> bool:
    """A reaction nobody has replied to: paint on the page, and no thread yet."""
    return is_reaction(thread["root"]) and not spoken_turns(thread)


def undo_error(event: dict, events: list, within: dict) -> str | None:
    """Why this undo may not take back the event it names, or None.

    Checked once here, at the door the browser writes through, so nothing
    downstream asks a second time whether an `undoes` points at something real.
    Two tabs racing to take back the same event are the one case this refuses
    that nothing is wrong with: the second is a no-op, and refusing it costs a
    toast where accepting it would leave two withdrawals of one gesture in a log
    whose every other line is something the reader did.

    A reaction is the one message a reader takes back rather than answers,
    and only while it still paints: once a turn answers it the withdrawal
    would orphan those words, and the reader's move is in the thread that
    turn opened; once its thread is resolved, resolve being its floor, there
    is nothing left to take back. The browser offers exactly the same
    (conversation.js `reactionStanding`).

    `within` is the published page's containment, as every other fold of the
    threads takes it: a thread an action settled, and a version's `restated`
    inside that widget reopened, is open here as it is in `page state`."""
    target = next((e for e in events if e["id"] == event["undoes"]), None)
    if target is None:
        return f"unknown undoes {event['undoes']!r}"
    if target["author"] != "user":
        return f"{target['kind']} {target['id']} is not the reader's own gesture"
    if target["kind"] in MESSAGE_KINDS:
        if not is_reaction(target):
            return (
                f"{target['kind']} {target['id']} is not a reaction; a message "
                "with words in it is said rather than unsaid"
            )
        thread = next(
            t
            for t in build_threads(events, within).values()
            if any(m["id"] == target["id"] for m in t["msgs"])
        )
        if any(m.get("parent") == target["id"] for m in spoken_turns(thread)):
            return (
                f"reaction {target['id']} has been answered; withdraw it in the "
                "thread the answer opened"
            )
        if thread["resolved"]:
            return f"reaction {target['id']} stands on a resolved thread"
    elif target["kind"] not in UNDOABLE_KINDS:
        return (
            f"{target['kind']} events cannot be taken back (the kinds that can "
            f"are {', '.join(sorted(UNDOABLE_KINDS))} and a reaction)"
        )
    if target["id"] in taken_back(events):
        return f"{target['id']} has already been taken back"
    return None


def build_threads(events: list, within: dict) -> dict:
    """Fold the chronological log into comment threads by root id.

    `resolved` is the event that currently closes the thread, or None. Either side
    can close one, so a bool beside a second field naming who would be two readings
    of one fact; the event answers both questions and carries its own `author`.
    A thread is settled by the widget's standing answer: the last action that
    widget sent and the log still lets stand, and then only while that answer
    names the thread. Three things unseat one, and every one of them is the log's
    own word rather than a case written out here. A version that rewrites what a
    decision rested on says `restated`, stamping records the floor, and replay
    drops the action — `action_retracted`, the same test the fold and the words
    gate ask. The reader can take the answer back where they stand, which is the
    `undo` naming it and `taken_back` reading it. And a later action on the same
    widget supersedes the one before it, exactly as the state fold reads a second
    `move` on one card. Without that last one, a reject after an accept left the
    reader's question filed away as answered by the fix they had just turned down,
    while the fold reported the suggestion rejected: the log held one thing, the
    panel showed another, and nothing on either side said so.

    An ask is a widget instance ($awaits), so what answers one is that widget's
    own last word — and the widget id is also the only key the log carries by
    itself. That is why the state fold cannot serve here: it drops an action whose
    widget the current page no longer holds, and the version that honors a
    decision retires the widget that made it, precisely when the thread it settled
    must stay settled. `x-state` holds a verb declaring `resolves` to a
    widget-absolute unit, so the two keys are one key.

    Standing says nothing about the page, and that silence cuts both ways: a stale
    tab's decision unseats an answer whose widget a later revision has since
    retired, leaving the fold nothing to paint and the reader's press reaching the
    thread or nothing at all. Asking the page instead would fork the two runtimes,
    which read different pages — the browser's pinned version against this side's
    active revision.

    A `resolve` is a person saying the conversation is done. An `unresolve` clears
    that closure. A superseded answer also stops closing the thread; undo and
    retraction remove it from the reading entirely.

    What `resolves` cannot say is the difference between an answer that leaves the
    thread open and an action that is not an answer at all — a reject means the
    first, and both spell it by carrying nothing. The one widget that names a
    thread has two verbs, both of them its answers, so the readings coincide; a
    press that confirms rather than answers, Done over a set of picks, would want
    the third value spelled before its widget could settle a thread.

    `within` is where each id sits on the page the outcomes were folded over, so
    threads and state cannot be settled against two different pages. It is the
    whole of what the retraction test asks of a page, and `enclosing_ids` answers
    it with no vocabulary loaded — which is what lets the readings that may not
    raise on the registry gate settle a thread the way `page state` does rather
    than approximately. Required, not defaulted: a caller with no published page
    passes `{}` and says so, that being a fact about the page rather than a
    reader standing down."""
    floors = retractions(events)
    withdrawn = taken_back(events)
    # widget id -> its last action the log still lets stand: not one the reader
    # took back, and not one a version retracted under it.
    answers = {}
    settling_actions = set()
    for e in events:
        if (
            e["kind"] == "action"
            and e["id"] not in withdrawn
            and not action_retracted(e, floors, within)
        ):
            answers[e["widget"]] = e
            if e["detail"].get("resolves"):
                settling_actions.add(e["id"])
    threads = {}
    thread_for = {}
    messages = {}
    for e in events:
        # A gesture the reader took back settles nothing, whichever way it settled:
        # the log holds it and no reading of the log stands on it.
        if e["id"] in withdrawn:
            continue
        if e["kind"] == "comment":
            message = dict(e)
            messages[e["id"]] = message
            thread = {"root": message, "msgs": [message], "resolved": None}
            threads[e["id"]] = thread
            thread_for[e["id"]] = thread
            continue
        # A surviving answer closes the thread it names. The detail carrying
        # `resolves` is the whole of that condition — a second widget that answers
        # a thread joins by declaring the field, not by being read here by name.
        # The sender snapshots the mapping into the action because the honoring
        # version retires the element that held it, so nothing later can look it up.
        #
        # Folded here, at the answer's own place in the log, rather than after the
        # walk: a resolve pressed between two decisions is the last current word on
        # the thread.
        if e["kind"] == "action":
            answered = threads.get(e["detail"].get("resolves"))
            if (
                answered
                and e["id"] in settling_actions
                and answers.get(e["widget"]) is e
            ):
                answered["resolved"] = e
            continue
        if e["kind"] == "edit":
            if message := messages.get(e["message"]):
                message["text"] = e["text"]
                message["edited"] = {key: e[key] for key in ("id", "seq", "ts")}
            continue
        if e["kind"] == "reply":
            # A reply whose message the log lost opens the thread that message would
            # have opened, under the id it was known by, which is the id an action
            # names in `resolves` and the one `thread_roots` resolves it to. A person
            # answers it by its own surviving id; the lost one names no message and
            # `leaf reply` says so.
            # `read_events` skips a torn line and keeps reading, and `thread_roots`
            # resolves such a reply to the lost id for the same reason: a reader who
            # can see the reply is owed the rest of the page around it. Raising here
            # instead cost the whole page — `page state` exited on the KeyError, and
            # the browser's own walk, which mirrors this one, threw where it builds
            # the panel — so one torn line took down every reading of a log that had
            # already been read.
            thread = thread_for.get(e["parent"])
            if thread is None:
                thread = {"root": e, "msgs": [], "resolved": None}
                threads[e["parent"]] = thread
                thread_for[e["parent"]] = thread
            message = dict(e)
            messages[e["id"]] = message
            thread["msgs"].append(message)
            thread_for[e["id"]] = thread
        # A resolve names a message rather than opening one, so a conversation the log
        # lost whole — no reply of its own survived either — leaves it nothing to close.
        elif e["kind"] == "resolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = e
        elif e["kind"] == "unresolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = None
    return threads


def anchored_ids(events: list, within: dict) -> set:
    """Element ids an unresolved thread still points at. A reaction nobody has
    answered is a mark and not a thread, so it holds no id: a reaction never
    gates a version, and its anchor re-resolves or detaches like a comment's."""
    return {
        (t["root"].get("anchor") or {}).get("section")
        for t in build_threads(events, within).values()
        if not t["resolved"] and not bare_reaction(t)
    } - {None}


def awaits_agent(thread: dict) -> bool:
    """Whether a thread's next word is the agent's.

    Anyone other than the agent spoke last and it waits on the agent. An agent-last
    thread and a resolved thread do not. This reading deliberately says nothing about
    whether the reader owes a word: an ordinary agent reply may leave the open thread
    awaiting nobody, while an agent comment, an explicit prose ask, or a structured
    widget ask awaits the reader. The runtime's `awaitsAgent` is the same sentence,
    and it has to be: the panel telling the reader a seated thread is with the agent
    while the banner counts the same question as theirs is one fact told two ways.

    Not the agent, rather than the reader: `author` is an open string on every message
    contract, and the two the code writes are `user` and `claude`. A line from anywhere
    else therefore reads as owed an answer, which is the direction to err in — an
    unanswered word is invisible to everyone, while one answer too many costs a reply.

    Turns, not marks: a reaction is a mark on a message rather than a word in the
    conversation, so an `ok` the reader puts on the agent's answer does not hand the
    thread back, and a reaction nobody has replied to is no conversation at all. The
    runtime's `awaitsAgent` reads the same list for the same reason."""
    said = spoken_turns(thread)
    return not thread["resolved"] and bool(said) and said[-1]["author"] != "claude"


def seat_root(thread: dict) -> str | None:
    """The widget whose conversation seat this thread's root stands in.

    An element anchor naming that widget and carrying nothing else, which is the
    runtime's `seatRoot` and the anchor `renderConversations` collects into the seat's
    own view. Narrower than `anchored_ids`, deliberately: a quote anchor points into
    the widget's words rather than standing in the box it offers, and the reader can
    see the difference — one is a note on a phrase, the other is the cell.

    A reply whose root the log lost is its own root and carries no anchor, so it seats
    nowhere. No cell on the page shows it either."""
    root = thread["root"]
    anchor = root.get("anchor")
    if root.get("about") or not anchor or len(anchor) != 1:
        return None
    return anchor.get("section")


def seats_with_agent(threads: dict) -> set[str]:
    """Widget ids whose own seat holds a conversation now waiting on the agent.

    A request whose own conversation is with the agent is not one the reader has to
    deal with, so an ask projection reading their list subtracts these. It is not an
    answer — the widget's state is untouched — which is why the reading that asks
    whether a request is answered passes an empty set instead. The runtime builds the
    same set from `awaitsAgent` over `seatRoot`, so the banner's count and `page state`
    cannot disagree about whose turn it is.

    Whose thread it is does not enter into it: the agent may open one in the seat too,
    and once the reader has answered there the question is with the agent either way.

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


def work_claim_revision(claim: dict, _events: list) -> int:
    """The exact working document on which widget work was claimed."""
    return claim["revision"]


def standing_work_claims(status: dict, events: list) -> list:
    """The transient work claims the durable exchange has not ended.

    A claim starts after one exact log sequence. Thread work ends at the agent's
    next reply in that conversation; widget work ends at a later version note
    that explicitly settles its id. The sequence boundary matters in both
    directions: renewing work after an answer creates a new claim, and an old
    answer cannot settle it merely because it names the same subject.

    A reply and a widget settlement are permanent log answers, and they are the
    whole test. Resolution is not one: it only hides a thread claim and an
    unresolve shows it again, so both callers asked for the resolved threads back
    and the question was never really being asked. What this reading wants of a
    conversation is who has spoken in it since the claim, so it reads the
    messages and never the resolution — which is why it names no page.
    """
    threads = build_threads(events, {})
    standing = []
    for claim in status.get("work", []):
        subject = claim["subject"]
        after = claim["after"]
        if subject["kind"] == "thread":
            thread = threads.get(subject["id"])
            if thread is None:
                continue
            replied = any(
                msg["kind"] == "reply"
                and msg["author"] == "claude"
                and msg["seq"] > after
                for msg in thread["msgs"]
            )
            if replied:
                continue
        elif subject["kind"] == "widget":
            if any(
                event["kind"] == "note"
                and event["seq"] > after
                and subject["id"] in note_settlements(event, "work")
                for event in events
            ):
                continue
        else:
            continue
        standing.append(claim)
    return standing


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
    """The runtime's restsOn, read the same way here: the sending widget plus
    every detail id it contains, `resolves` aside. This is the one key space for
    liveness — fold survival, retraction floors, and the earning of `restated`
    all go through it, in both runtimes — while `action_subjects` stays the
    words gate's finer, subject-keyed view of the same containment. Two views,
    one containment test; a third keying would fork the JS/Python twin a third
    way.

    `within` is where each id sits, and nothing else about the page. Liveness
    never asks what an element says, and the difference is not tidiness: words
    are the vocabulary's word, where an element sits is not, so a reading that
    asks only this one can be had without loading a layer.

    `resolves` names a conversation, and a conversation is not on the page to be
    contained — so the only thing containment could find under that key is an
    element inside the widget spelled the same, and a floor on it would retract
    an answer that has nothing to do with it."""
    widget = event["widget"]
    parts = [
        v
        for field, named in event["detail"].items()
        if field != "resolves"
        for v in (named if isinstance(named, list) else [named])
        if isinstance(v, str) and widget in within.get(v, ())
    ]
    return [widget, *parts]


def action_retracted(event: dict, floors: dict, within: dict) -> bool:
    """Whether a retraction has taken this action back: true when any id it rests
    on carries a floor from a version later than the one the action was made on.

    One predicate for every reader of liveness — the fold's survival test, the
    words gate's, and the thread a decision settles — because a decision the log
    has taken back has to be absent everywhere at once. It was written out twice
    and a third reader went without: `build_threads` settled a thread on an accept
    and never asked, so a suggestion the next version rewrote came back pending
    with the thread it had answered still filed away, and the user was never asked
    the question again."""
    return any(
        floors.get(i, 0) > event["revision"] for i in action_rests_on(event, within)
    )
