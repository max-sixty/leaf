"""Append-only event model and its pure folds."""

import contextlib
import json
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Protocol

from leaf_interact.document import EMPTY, parse_structure
from leaf_interact.files import read_json
from leaf_interact.schema import MESSAGE_KINDS, UNDOABLE_KINDS

try:
    import fcntl
except ImportError:  # pragma: no cover - unsupported non-POSIX platform
    fcntl = None


class EventAppender(Protocol):
    """A transaction already holding the event log's append lease."""

    def append_event(self, event: dict) -> dict: ...


def require_cross_process_locking() -> None:
    """Refuse every writer/server path on a host without the log's lock."""
    if fcntl is None:
        raise RuntimeError(
            "leaf requires POSIX cross-process file locking; this platform has no fcntl"
        )


@contextlib.contextmanager
def flocked(path: Path):
    """An exclusive lock held while the block runs — the one serialization
    primitive here. The log serializes appends, cursor and status updates, and
    claim and delivery transitions. Stable purpose locks serialize contract or service
    transitions; a `.lock` beside a registry of JSON files serializes updates
    to them, since the files themselves are replaced by rename and a lock on a
    replaced inode holds nothing."""
    require_cross_process_locking()
    # comments.jsonl is the successful-init marker as well as a lease. A
    # transaction racing page deletion must not recreate it and turn a deleted
    # directory back into an initialized page. Purpose locks are disposable and
    # may be minted on first use.
    mode = "r+b" if path.name == "comments.jsonl" else "a+b"
    with open(path, mode) as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_cursor(page_dir: Path) -> int:
    """The seq the agent has acknowledged through (`leaf ack`); 0 before any."""
    return (read_json(page_dir / "cursor.json") or {"seq": 0})["seq"]


def jsonl_line(event: dict) -> str:
    """One event as one physical line. U+2028, U+2029 and U+0085 are legal raw in
    JSON strings and line breaks to any splitlines()-shaped reader, so they are
    written as escapes — a pasted comment carrying one must not decide where an
    event ends. The log's own reader splits on the "\\n" the writer puts between
    events either way; the escape is for what `wait` and `events` print, which
    stays one event per line for every consumer. json.dumps escapes every other
    line-breaking character on its own."""
    line = json.dumps(event, ensure_ascii=False)
    for ch in "\u2028\u2029\u0085":
        line = line.replace(ch, f"\\u{ord(ch):04x}")
    return line


class AttemptConflict(ValueError):
    """One browser attempt was reused for a different event payload."""


class AttemptExecution:
    """One execution shared by concurrent HTTP requests for the same attempt.

    Success is durable in the event log. The record coordinates requests while a
    handler is executing and is released once that handler finishes, so a concurrent
    retry receives the same outcome and a later one is free to be evaluated again.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.done = threading.Event()
        self.result = None


def _attempt_payload(event: dict) -> dict:
    # Kind is part of the gesture. Only fields the append boundary itself assigns
    # disappear from the equality check.
    return {
        key: value
        for key, value in event.items()
        if key not in {"id", "ts", "author", "seq"}
    }


def _matching_attempt(f, event: dict) -> dict | None:
    attempt = event.get("attempt")
    if not attempt:
        return None
    f.seek(0)
    for raw in f:
        try:
            existing = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if existing.get("attempt") != attempt:
            continue
        if _attempt_payload(existing) != _attempt_payload(event):
            raise AttemptConflict(
                f"attempt {attempt!r} already belongs to another event"
            )
        return existing
    return None


def _append_event_unlocked(f, event: dict) -> dict:
    """Append while the caller holds this log file's exclusive lease."""
    event.setdefault("id", secrets.token_hex(4))
    event.setdefault("ts", now_iso())
    # Attempt identity is checked under the log's append lock. Checking before
    # this point would leave two server threads free to observe absence together
    # and append together. Content and time deliberately play no part: an
    # intentional later identical message has a fresh attempt and is a second
    # event.
    if event.get("attempt") and (existing := _matching_attempt(f, event)):
        return existing
    # A crash can tear the previous append mid-line: SIGKILL under a buffered
    # flush, a full disk. The line discipline is the writer's, so the writer
    # restores it — without this, the next event glues onto the torn fragment
    # and one lost event becomes an unreadable line mid-file.
    f.seek(0, os.SEEK_END)
    if f.tell():
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
    f.write((jsonl_line(event) + "\n").encode())
    # To the platter before the caller is told it landed: an event is a
    # decision, the sender's 200 (or a CLI exit 0) is the claim it is kept,
    # and events are rare enough that a flush per append costs nothing.
    f.flush()
    os.fsync(f.fileno())
    return event


def append_event(page_dir: Path | EventAppender, event: dict) -> dict:
    if not isinstance(page_dir, Path):
        return page_dir.append_event(event)
    # The path form is the low-level fixture/instrumentation seam and retains
    # its historic ability to start a log in an already-created directory.
    # Product writers pass PageTransaction, whose entry never mints the page's
    # successful-init marker.
    log = page_dir / "comments.jsonl"
    with open(log, "a", encoding="utf-8"):
        pass
    with flocked(log) as f:
        return _append_event_unlocked(f, event)


def read_events(page_dir: Path) -> list:
    path = page_dir / "comments.jsonl"
    if not path.exists():
        return []
    events = []
    # The log's grammar is events joined by "\n" — the writer's own separator,
    # not splitlines()'s wider class, which once read a U+2028 inside a comment's
    # text as a break and left half an event leading a line no parse could take.
    # Bytes, decoded per line: a crash can tear mid-character as easily as
    # mid-line (ensure_ascii=False writes multi-byte UTF-8), and one strict
    # read_text of the file would raise on the tear before any line-level
    # tolerance could reach it.
    lines = path.read_bytes().split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # The final line is a concurrent append mid-flush, complete on the
            # next read. An earlier one is the tear a crash left, standing alone
            # because append_event repairs the discipline before writing: that
            # event's sender already saw its send fail, the seqs around it hold,
            # and there is nothing anyone could do with a fragment — so it is
            # skipped, not raised over, and the page keeps reading.
            continue
        event["seq"] = i + 1
        events.append(event)
    return events


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
    message rather than a turn in the conversation, so every reading of who
    spoke last — the panel's "waiting on you", the hook's unanswered asks —
    walks this list rather than `msgs`."""
    return [m for m in thread["msgs"] if not is_reaction(m)]


def bare_reaction(thread: dict) -> bool:
    """A reaction nobody has replied to: paint on the page, and no thread yet."""
    return is_reaction(thread["root"]) and not spoken_turns(thread)


def undo_error(event: dict, events: list) -> str | None:
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
    (conversation.js `reactionStanding`)."""
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
            for t in build_threads(events, {}).values()
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


def build_threads(events: list, spk: dict) -> dict:
    """Fold the chronological log into comment threads by root id.

    `resolved` is the event that currently closes the thread, or None. Either side
    can close one, so a bool beside a second field naming who would be two readings
    of one fact; the event answers both questions and carries its own `author`.
    A thread is settled by the widget's standing answer: the last action that
    widget sent and the log still lets stand, and then only while that answer
    names the thread. Three things unseat one, and every one of them is the log's
    own word rather than a case written out here. A version that rewrites what a
    decision rested on says `restated`, publishing records the floor, and replay
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
    tab's decision unseats an answer whose widget a published version has since
    retired, leaving the fold nothing to paint and the reader's press reaching the
    thread or nothing at all. Asking the page instead would fork the two runtimes,
    which read different pages — the browser's pinned version against this side's
    last published file.

    A `resolve` is a person saying the conversation is done. An `unresolve` clears
    that closure. A superseded answer also stops closing the thread; undo and
    retraction remove it from the reading entirely.

    What `resolves` cannot say is the difference between an answer that leaves the
    thread open and an action that is not an answer at all — a reject means the
    first, and both spell it by carrying nothing. The one widget that names a
    thread has two verbs, both of them its answers, so the readings coincide; a
    press that confirms rather than answers, Done over a set of picks, would want
    the third value spelled before its widget could settle a thread.

    `spk` is the page the containment half of the retraction test is read against,
    and it is the reading of the version the outcomes were folded over, so threads
    and state cannot be settled against two different pages. Required, not
    defaulted: a caller with no published page passes `{}` and says so, because a
    default that stood down quietly is exactly where a verb naming a part of its
    own widget would have gone unfloored."""
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
            and not action_retracted(e, floors, spk)
        ):
            answers[e["widget"]] = e
            if e["detail"].get("resolves"):
                settling_actions.add(e["id"])
    threads = {}
    thread_for = {}
    for e in events:
        # A gesture the reader took back settles nothing, whichever way it settled:
        # the log holds it and no reading of the log stands on it.
        if e["id"] in withdrawn:
            continue
        if e["kind"] == "comment":
            thread = {"root": e, "msgs": [e], "resolved": None}
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
            thread["msgs"].append(e)
            thread_for[e["id"]] = thread
        # A resolve names a message rather than opening one, so a conversation the log
        # lost whole — no reply of its own survived either — leaves it nothing to close.
        elif e["kind"] == "resolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = e
        elif e["kind"] == "unresolve" and (thread := thread_for.get(e["parent"])):
            thread["resolved"] = None
    return threads


def anchored_ids(events: list, spk: dict) -> set:
    """Element ids an unresolved thread still points at. A reaction nobody has
    answered is a mark and not a thread, so it holds no id: a reaction never
    gates a version, and its anchor re-resolves or detaches like a comment's."""
    return {
        (t["root"].get("anchor") or {}).get("section")
        for t in build_threads(events, spk).values()
        if not t["resolved"] and not bare_reaction(t)
    } - {None}


def note_settlements(event: dict, kind: str) -> set[str]:
    """The ids one version note settles for a provisional-information kind."""
    return {
        target["id"] for target in event.get("settles", []) if target["kind"] == kind
    }


def work_claim_version(claim: dict, events: list) -> int:
    """The published page at a claim's sole stored temporal boundary."""
    return max(
        event["version"]
        for event in events
        if event["kind"] == "note" and event["seq"] <= claim["after"]
    )


def standing_work_claims(
    status: dict, events: list, *, include_resolved: bool = False
) -> list:
    """The transient work claims the durable exchange has not ended.

    A claim starts after one exact log sequence. Thread work ends at the agent's
    next reply in that conversation; widget work ends at a later version note
    that explicitly settles its id. The sequence boundary matters in both
    directions: renewing work after an answer creates a new claim, and an old
    answer cannot settle it merely because it names the same subject.

    Resolution only hides a thread claim. An unresolve can make it visible again,
    so callers carrying status across a rewrite ask to include resolved threads;
    presence does not. A reply and a widget settlement are permanent log answers and
    are filtered in both readings.
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
            if replied or (thread["resolved"] and not include_resolved):
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


def thread_roots(events: list) -> dict:
    """Message id → the id of the comment that opened its thread.

    Two readings of the panel's own document resolve a reply to its root, and they
    must answer alike: a decision and an ask naming different conversations for one
    message is a disagreement no reader could account for. (`build_threads` walks the
    same relation to a different end — the thread object itself, with its resolution —
    so it keeps its own walk, and answers the same way where the log is torn.)

    A reply whose root the log lost stands as its own thread rather than raising.
    `read_events` skips a line nothing could be done with and keeps reading, and a
    reader who can see the reply is owed the rest of the page around it."""
    root = {}
    for e in events:
        if e["kind"] == "comment":
            root[e["id"]] = e["id"]
        elif e["kind"] == "reply":
            root[e["id"]] = root.get(e["parent"], e["parent"])
    return root


class ThreadStructure(NamedTuple):
    ids: set
    by_id: dict
    fragments: dict


def thread_structure(events: list) -> ThreadStructure:
    """Parse each logged markup fragment once into the panel's id universe."""
    ids, by_id, fragments = set(), {}, {}
    for e in events:
        if markup := e.get("markup"):
            fragment = parse_structure(markup)
            fragments[e["id"]] = fragment
            ids.update(fragment.ids)
            by_id.update(fragment.by_id)
    return ThreadStructure(ids, by_id, fragments)


def retractions(events: list, upto=None) -> dict:
    """id → the greatest version whose `restated` note took back its decision."""
    at = {}
    for event in events:
        if event["kind"] == "note" and (upto is None or event["version"] <= upto):
            for named in event.get("restated", []):
                at[named] = max(at.get(named, 0), event["version"])
    return at


def report_settlements(events: list, upto=None) -> dict:
    """Report event id → the greatest version whose note settled it."""
    at = {}
    for event in events:
        if event["kind"] != "note" or (upto is not None and event["version"] > upto):
            continue
        for identity in note_settlements(event, "report"):
            at[identity] = max(at.get(identity, 0), event["version"])
    return at


def action_rests_on(event: dict, spk: dict) -> list:
    """The runtime's restsOn, read the same way here: the sending widget plus
    every detail id it contains. This is the one key space for liveness — fold
    survival, retraction floors, and the earning of `restated` all go through
    it, in both runtimes — while `action_subjects` stays the words gate's finer,
    subject-keyed view of the same containment. Two views, one containment test;
    a third keying would fork the JS/Python twin a third way."""
    widget = event["widget"]
    parts = [
        v
        for field in event["detail"].values()
        for v in (field if isinstance(field, list) else [field])
        if isinstance(v, str) and widget in spk.get(v, EMPTY).within
    ]
    return [widget, *parts]


def action_retracted(event: dict, floors: dict, spk: dict) -> bool:
    """Whether a retraction has taken this action back: true when any id it rests
    on carries a floor from a version later than the one the action was made on.

    One predicate for every reader of liveness — the fold's survival test, the
    words gate's, and the thread a decision settles — because a decision the log
    has taken back has to be absent everywhere at once. It was written out twice
    and a third reader went without: `build_threads` settled a thread on an accept
    and never asked, so a suggestion the next version rewrote came back pending
    with the thread it had answered still filed away, and the user was never asked
    the question again."""
    return any(floors.get(i, 0) > event["version"] for i in action_rests_on(event, spk))
