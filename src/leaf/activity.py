"""Where the agent's work stands, projected from durable evidence and the live claim.

The log says what is owed (`obligations`, `workflows`, `todos`). This module adds what
only the claim, the turn and the harness can say, and is the one producer of `running`
and `blocked` (`standing`): for each update's delivery, each update's record and each
to-do, and for the page.

The evidence, each dated by when it was written: the agent's declaration, the newest
`status` event, opens the page or closes it (`declaration`); a start is a lease on the
item it names (`todos`); the claim proves who holds the page and when its turn opened
and closed; a pickup proves a delivery; a stream proves a step or a reply under way.

The page's reading is the agent's side of all of it, in the same words: `running`
while its turn is at work, `blocked` when what it had in hand has stopped or gone
quiet, when its turn waits on the user in its own window (`terminal`), or when nothing
takes input and an owed update is stranded, which it says in that update's own reason;
`waiting` while it owes something nobody is on, `done` when it owes nothing. Its
`next_actor` is whose move changes that: the user's for a dialog in the terminal and
for an update only a nudge will move. `presence` says whether anyone is there to take
input: `here`, `away` between turns, `gone` when no session holds the page, `closed`
once the agent declared it done with the page. Every reader, browser chrome, hooks and
agent-facing state, takes this one answer.
"""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from .obligations import response_address
from .standing import STRANDED, strength
from .state import turn_closed, turn_open

WORKING_GRACE = timedelta(minutes=15)
PICKUP_GRACE = timedelta(minutes=2)
# The steps a harness may report, whose home is the served state's `WorkKind`: the
# browser words each one, and its type makes that table name every kind.
WORK_KINDS = frozenset(
    json.loads(
        (Path(__file__).with_name("served_state") / "state.schema.json").read_text()
    )["$defs"]["WorkKind"]["enum"]
)
# Steps that wait on the user in the agent's own window, which renew nothing until
# the user answers there.
# `awaiting_user` is a dialog whose kind, approval or question, the harness does not
# say.
AWAITING_KINDS = {"awaiting_approval", "awaiting_input", "awaiting_user"}
# The step a Working status shows while the claimant's session works on after its
# turn ended (`Turn.background`).
BACKGROUND_DETAIL = "in the background"


def undeclared() -> dict:
    """The status of a page whose agent has declared nothing, such as one before any
    `leaf page open` or a copy a host serves: no work under way and nothing ended, so
    the page is open for feedback and a wait keeps watching it."""
    return {"state": "waiting"}


def declaration(events: list) -> dict:
    """The agent's declaration about the page: the state and time of the newest
    `status` event in `events`, or `undeclared` before the first.

    Work taken in hand reopens a page the agent had closed: `idle` says it was done
    with the page, and every watcher stands down for an idle page. So a start after
    an `idle` (`todos.start_reading`) reads as a bare `waiting` from that start on.
    It has no event of its own, since a declaration puts down every start before
    it."""
    from .todos import start_reading

    reopened = None
    for event in reversed(events):
        if event["kind"] == "status":
            if event["state"] == "idle" and reopened is not None:
                return {"state": "waiting", "ts": reopened["ts"]}
            return {key: event[key] for key in ("state", "ts")}
        if start_reading(event):
            reopened = event
    return undeclared()


def _moment(value: str | None) -> datetime | None:
    # Every stamp read here is Leaf's own `now_iso`, or None where nothing was stamped.
    return datetime.fromisoformat(value) if value else None


def _quiet(ts: str | None, now: datetime, grace: timedelta) -> bool:
    written = _moment(ts)
    return bool(written and now - written >= grace)


def _dropped(ts: str | None, ended: datetime | None) -> bool:
    """Whether a claim was written before the turn whose ending was seen: that turn
    no longer stands behind it."""
    written = _moment(ts)
    return bool(written and ended and written <= ended)


def canonical_stream_reply(
    present: dict, now_iso: str, reply: dict | None
) -> dict | None:
    """Project one provisional reply against its session lease and age. A withheld
    draft is written once and never renewed, so only its lease ages it."""
    if reply is None:
        return None
    result = dict(reply)
    state = result["state"]
    if state in {"active", "withheld"} and (
        result["session"] != present.get("claim_session")
        or not present["listening"]
        or (
            state == "active"
            and _quiet(
                result["updated_at"],
                datetime.fromisoformat(now_iso),
                WORKING_GRACE,
            )
        )
    ):
        result["state"] = "disconnected"
    return result


def _reply_evidence(reply: dict) -> dict:
    """Keep response settlement evidence in activity without duplicating its text."""
    return {key: reply[key] for key in ("state", "turn", "settles", "attempt")}


def _receipt_bindings(workflows: list[dict], present: dict) -> dict[str, dict]:
    """Take each workflow's `receipt_refs` off it, and return, by input, what its
    receipts give an answer owed to it: the `ref` recorded under the page's current
    claim (`workflows`, `receipt_refs`), or nothing.

    A reference authorizes only the claim its delivery was captured under, and
    `post_reply` refuses it once another session claims the page, so a ref
    captured under an earlier owner is withheld. The update is then deliverable to
    the new owner again (`delivery.deliverable`), whose receipt records its ref."""
    bindings = {}
    for item in workflows:
        usable = item.pop("receipt_refs", {}).get(present.get("claim_session"))
        bindings[item["input"]] = {"ref": usable} if usable is not None else {}
    return bindings


def _bind_reply(workflows: list[dict], reply: dict | None) -> None:
    """Bind provisional response progress only to the exact input it names: the
    update reads `running` with reason `replying`, or `blocked` by what became of the
    reply.

    A durable response outranks it: a harness's failure reply has already answered
    the input, and the turn's leftover stream must not paint it as still replying."""
    if reply is None:
        return
    workflow = next(
        (item for item in workflows if item["input"] == reply["responds"]), None
    )
    if workflow is None or workflow["reason"] == "failed":
        return
    workflow["response"] = _reply_evidence(reply)
    # `partial` is a turn that completed without a final answer: it ended with
    # the update unanswered.
    blocked = {
        "disconnected": "quiet",
        "interrupted": "interrupted",
        "failed": "failed",
        "partial": "stopped",
    }.get(reply["state"])
    workflow["state"], workflow["reason"] = (
        ("blocked", blocked) if blocked else ("running", "replying")
    )
    workflow["seen"] = True


def reply_reservation_stands(
    reservation: dict | None, session: str | None, claim: dict | None
) -> bool:
    """Whether the exact claim turn still reserves an automatic provider answer:
    `claim` is the claim, or the page's served reading of it, which holds the turn
    under the session record's names (`state.turn_open`).

    Before the provider reply opens, its reservation names the claim turn current
    at reservation; afterward it names the delivery's turn. A different or closed
    claim turn cannot retain that reservation. A client still following its turn
    commits before closing it (`codex.TurnFold.commit`).
    """
    return bool(
        reservation
        and reservation["session"] == session
        and turn_open(claim, reservation["turn"])
    )


def answer_command(answer: dict, page_dir: Path) -> str:
    """The one operation that writes an answer on the page at `page_dir`, as every
    refusal and reminder naming an owed update says it."""
    if answer["kind"] != "reply":
        return f"a stamped version whose markup records action {answer['action']}"
    if answer.get("writer") == "turn":
        return f"your turn's final message or {reply_command(answer, page_dir)}"
    return reply_command(answer, page_dir)


def reply_command(answer: dict, page_dir: Path) -> str:
    """The `leaf thread reply` that answers a reply `answer`.

    It names the exact `ref` its update's receipt recorded where the page's owner can
    still use it (`_receipt_bindings`). An update the owner holds no ref for, as one
    the page has not received or one another session received before the page
    changed hands, is deliverable (`delivery.deliverable`). Minting a ref here would
    deliver the page's whole pending batch and mark its other input Delivered
    unseen, so the command names the `leaf wait` that delivers it, after the claim
    its receipt needs where this command's session does not hold the page
    (`service.may_receive`)."""
    if "ref" in answer:
        return f"`leaf thread reply {answer['ref']}`"
    from .harness import session_harness
    from .service import may_receive, page_claim

    harness = session_harness()
    claim = (
        ""
        if may_receive(page_claim(page_dir), harness.session if harness else None)
        else f" (`leaf page claim {page_dir}` first, since this session does "
        "not hold the page)"
    )
    return (
        "`leaf thread reply <answer.ref>` with the `answer.ref` that "
        f"`leaf wait {page_dir}` delivers for {answer['responds']}{claim}"
    )


def unanswered(obligations: list[dict], page_dir: Path, of: str = "") -> str:
    """Say how many user updates on the page at `page_dir` have no answer and name
    what answers each. `of` narrows which updates these are, such as the
    acknowledged ones."""
    commands = "; ".join(
        answer_command(item["answer"], page_dir) for item in obligations
    )
    updates = f"user update{'s' if len(obligations) != 1 else ''}"
    return (
        f"{len(obligations)} {of + ' ' if of else ''}{updates} with no answer "
        f"({commands})"
    )


def _turn_wrote(obligation: dict, state: dict) -> bool:
    """Whether the claimant's open turn is done with the reply it owes this update.

    A provider-owned reply is written by the claimant's own turn, and the App Server
    client commits it once the turn ends, after the agent's last command. So the
    update is answered now when the turn's final message is complete, with text, in
    the reply draft bound to it. A draft the client `withheld`, because a user
    message shares the turn, leaves the update to the correction the client offers
    as the turn ends (`codex.carries_user_message`)."""
    draft = obligation["response"]
    return bool(
        draft
        and obligation["answer"].get("writer") == "turn"
        and (
            draft["state"] == "withheld"
            or (draft["state"] == "active" and draft["settles"])
        )
        and draft["turn"] == state["turn"]
    )


def acknowledged_obligations(state: dict) -> list[dict]:
    """The owed answers whose updates the page cursor has passed. A delivery brings
    one back only to an owner holding no usable ref for it (`delivery.unreferenced`)."""
    return [
        obligation
        for obligation in state["activity"]["obligations"]
        if obligation["seq"] <= state["cursor"]
    ]


def blocking_obligations(state: dict, *, watched: bool) -> list[dict]:
    """The owed answers that keep the agent from idling the page, and from which
    the Stop hook takes the ones that hold its turn (`turn_obligations`).

    `leaf page close` refuses over exactly these: the acknowledged updates nothing
    else is set to answer. An update the adapter queued is answered by the later turn
    the queue opens, where the prompt hook records it `opened` and it blocks from
    then on. A provider reply the open turn has finished is committed by the
    claimant's App Server client once the turn ends, so it is answered while the
    session's watcher (`watched`) is live."""
    return [
        obligation
        for obligation in acknowledged_obligations(state)
        if not obligation["queued"] and not (watched and _turn_wrote(obligation, state))
    ]


def started_in_turn(obligation: dict, state: dict) -> bool:
    """Whether the claimant's open turn took this update in hand (`todos.take_in_hand`)
    after it was delivered: a start covering the update
    (`workflows.handed_over`, `started_by`) that turn wrote since the update's
    pickup.

    Read from the covering starts rather than the update's own standing, which follows
    the one input a start names: a thread's one reply answers every input it holds,
    so a start on an earlier input there covers the newest that carries the answer."""
    if not turn_open(state):
        return False
    return _started_by_turn(obligation, state)


def _started_by_turn(obligation: dict, state: dict) -> bool:
    """Whether the claimant's current turn, open or closed, wrote a start covering
    the update since its pickup (`started_in_turn`)."""
    delivered = obligation["delivery_seq"] or obligation["seq"]
    return any(
        start["session"] == state["claim_session"]
        and start["turn"] == state["turn"]
        and start["seq"] >= delivered
        for start in obligation["started_by"]
    )


def left_owed(state: dict, reminded: Callable[[str], bool]) -> list[dict]:
    """The owed answers the claimant's turn left as it closed, which a turn of
    their own reminds the agent of where a watch follows the turn
    (`hook_transport.stop_continues`, `session.watch_between_turns`): the blocking
    ones the closed turn did not start since their pickup, with a ref the owner
    can use, that no prompt has named since their delivery (`reminded`, with an
    update's id).

    A prompt names them once, so an agent that leaves one unanswered is reminded
    once for each delivery of it rather than after every turn. An update with no
    usable ref is input again, which wakes a turn as input does
    (`delivery.deliverable`)."""
    if not turn_closed(state):
        return []
    return [
        obligation
        for obligation in blocking_obligations(state, watched=True)
        if "ref" in obligation["answer"]
        and not _started_by_turn(obligation, state)
        and not reminded(obligation["input"])
    ]


def turn_obligations(state: dict, *, watched: bool) -> list[dict]:
    """The owed answers that hold the claimant's turn open: the blocking ones its
    open turn has not started.

    A start is the agent's answer for now, shown beside the update, and work that
    outlasts the turn runs in background workers whose results wake a later turn
    (`references/conversation-loop.md`, "Long-running work"). So the turn that
    started the update may end over it. The start does not carry into the next turn:
    that turn answers the update or starts it again, and the page reports the start's
    turn ended once nothing renews it. Idling still refuses over a started update,
    since closing the page answers nothing."""
    return [
        obligation
        for obligation in blocking_obligations(state, watched=watched)
        if not started_in_turn(obligation, state)
    ]


class Turn(NamedTuple):
    """The claimant session's current turn, as the one reading every rule of the
    fold takes: whether it is running; when it was seen to end, where something saw
    that; until when a running turn is believed on its stamps alone; an observed
    step while it waits on the user in its own window, with when that wait began;
    and whether the session still works in the background after its turn ended."""

    running: bool
    ended: datetime | None = None
    until: datetime | None = None
    step: str | None = None
    step_since: datetime | None = None
    background: bool = False


def claimant_turn(
    present: dict,
    declared: str | None,
    stream: dict | None,
    now: datetime,
    *,
    awaiting: bool = False,
) -> Turn:
    """Whether the claimant's turn is running, from every piece of evidence,
    each dated by when it was written, the newest deciding.

    The claim's stamps are the spine: the prompt hook or an App Server client opens
    the turn, a prompt or delivery into an open turn renews its stamp, and the Stop
    hook or an App Server client closes it. Not every harness runs a hook on interruption, so an open stamp is believed
    only while something in that turn renewed it within the working grace: its
    last opening, the agent's newest declaration (`declared`: a status or a start
    written during it), or the claimant's streamed activity. Past that nothing says whether it runs, which reads as not
    running without calling it ended.

    The harness's own record (`Harness.live_turn`) adds the two things no hook
    sees, each only when newer than what it contradicts: an `idle` newer than
    every renewal ends the open turn at that moment (an interrupt), and a
    `waiting` newer than the stamps is a dialog open now, a step shown whether or
    not the stamps say a turn is open. Its `busy` never says a turn runs, since
    the harness keeps it across turn endings while background work runs; after a
    turn the stamps closed, it says the session works on in the background
    (`Turn.background`), for as long as the record keeps it, which keeps the
    session's last start standing (`_start_age`). `awaiting` says the claimant's observer
    reports a wait on the user right now, which holds the turn open for as long as
    that observer lives."""
    opened = _moment(present.get("turn_opened"))
    closed = _moment(present.get("turn_closed"))
    if present["session_alive"] is not True:
        return Turn(False, ended=closed)
    live = present.get("live_turn") or {}
    since = _moment(live.get("since"))
    stamped = max((moment for moment in (opened, closed) if moment), default=None)
    dialog = live.get("state") == "waiting" and since and since >= (stamped or since)
    step = "awaiting_user" if dialog else None
    step_since = since if dialog else None
    if not turn_open(present) or opened is None:
        background = closed is not None and live.get("state") == "busy"
        return Turn(
            False, ended=closed, background=background, step=step, step_since=step_since
        )
    if awaiting or dialog:
        return Turn(True, step=step, step_since=step_since)
    renewals = [opened, _moment(declared)]
    if stream and stream.get("session") == present.get("claim_session"):
        renewals.append(_moment(stream.get("ts")))
    renewed = max(moment for moment in renewals if moment and moment >= opened)
    if live.get("state") == "idle" and since and since >= renewed:
        return Turn(False, ended=since)
    until = renewed + WORKING_GRACE
    return Turn(now < until, until=until)


def declared_at(present: dict, events: list) -> str | None:
    """When the agent last declared anything about the page: its newest status, or
    the newest start in the log (`todos.last_start`)."""
    from .todos import last_start

    moments = [
        (parsed, moment)
        for moment in (present["status"].get("ts"), last_start(events))
        if (parsed := _moment(moment)) is not None
    ]
    return max(moments, key=lambda pair: pair[0])[1] if moments else None


def current_turn(
    present: dict, declared: str | None, stream: dict | None, now: datetime
) -> tuple[Turn, bool]:
    """The claimant's turn as every reader takes it, beside whether the claimant's
    own observer streams live activity for it now. `declared` is `declared_at`.

    Streamed activity proves itself live by the wait lease its observer holds. A
    wait on the user (an approval, a question) sends nothing until the user
    answers, so it stands for as long as its observer does; every other step has
    to be renewed within the working grace."""
    status = present["status"]
    stream_live = bool(
        stream
        and stream.get("session") == present.get("claim_session")
        and stream.get("kind") in WORK_KINDS
        and present["listening"]
        and status["state"] != "idle"
        and (
            stream.get("kind") in AWAITING_KINDS
            or not _quiet(stream.get("ts"), now, WORKING_GRACE)
        )
    )
    turn = claimant_turn(
        present,
        declared,
        stream,
        now,
        awaiting=stream_live and stream.get("kind") in AWAITING_KINDS,
    )
    return turn, stream_live


def takes_input(present: dict, turn: Turn) -> bool:
    """Whether the claimant takes input now: its wait lease is held, or its turn
    runs under a harness whose hooks carry input into the turn. A wait that ends
    to deliver a comment has left the lease, and the turn it reaches, or the one
    it opens, takes the comment."""
    return present["listening"] or (turn.running and present["turn_takes_input"])


def nudge_due(present: dict, turn: Turn) -> bool:
    """Whether input arriving now is put in front of the claimant
    (`presence.nudge_unwatched`): nothing takes it, and its turn was seen to end.
    A turn Leaf only stopped believing in may still be running a long step, whose
    Stop hook refuses to end with the input unpicked."""
    return turn.ended is not None and not takes_input(present, turn)


def _start_age(
    start: dict, present: dict, now: datetime, turn: Turn
) -> tuple[bool, bool]:
    """How quiet a start is, and whether dropped: a start the claimant's ended turn
    wrote, from the moment that ending is seen, or any start unheard for the working
    grace.

    Whether the agent works is the harness's to say, and what it works on the
    agent's: so a start stands while its turn runs, and past the turn's end only
    while the harness says the session still works in the background
    (`Turn.background`), as a coordinator's workers do. Without that word the page
    stops reading as working once the turn is seen to end, rather than holding the
    agent's last line under a grace in case a later turn takes it up."""
    same_session = bool(
        start.get("session") and start["session"] == present.get("claim_session")
    )
    dropped = same_session and not turn.background and _dropped(start["ts"], turn.ended)
    return _quiet(start["ts"], now, WORKING_GRACE) or dropped, dropped


def _stand_workflows(
    evidence: list[dict],
    present: dict,
    now: datetime,
    *,
    held: bool,
    turn: Turn,
    owed: set[str],
) -> tuple[list[dict], dict[str, tuple[dict, bool, bool]], list[str]]:
    """Say where each workflow stands (`standing`) from its delivery evidence and the
    claimant's turn. Returned beside them: for each update a start holds, that start
    and how quiet and whether dropped it is, which the page reading below dates by;
    and when each update no harness has carried was sent, whose pickup grace is a
    moment the reading changes at.

    A start that stands is the agent at work. One gone quiet or dropped leaves the
    update `blocked`, `stopped` where its turn was seen to end and `quiet` where
    nothing says. Without a start, an update a turn took in waits while that turn
    runs; once it was seen to end with an answer still owed (`owed`, the records the
    agent owes) the update is `stopped`, and taken in by any other turn, `quiet`. One
    no harness has carried is `undelivered` past the pickup grace. A fork of the
    agent's conversation that took a waiting update on is at work on it
    (`forks.forked`). Nobody holding the page has nothing in hand, so an unheld page's
    updates read from their delivery alone.

    One reply answers every input its record holds, so a start standing on one of
    them covers the rest: an input a turn took in is no more stopped than the work on
    its answer is, and waits, delivered, while that work runs."""
    result = []
    aging = {}
    sent = []
    left = []
    forked = frozenset(present.get("forked", ()))
    for raw in evidence:
        item = dict(raw)
        start = item.pop("held_by")
        pickup = item.pop("pickup")
        state, reason, seen = "waiting", None, pickup == "opened"
        handling = False
        if item.pop("handed_back"):
            state, reason, seen = "blocked", "failed", True
        elif start is not None and held:
            quiet, dropped = _start_age(start, present, now, turn)
            aging[item["id"]] = (start, quiet, dropped)
            item["ts"] = start["ts"]
            seen = True
            if quiet:
                state, reason = "blocked", "stopped" if dropped else "quiet"
            else:
                state = "running"
        else:
            if start is not None:
                item.update(detail=None, detail_seq=None, agent=None, session=None)
            if pickup == "opened":
                in_turn = (
                    item["delivery_session"] == present.get("claim_session")
                    and item["delivery_turn"] == present["turn"]
                )
                handling = in_turn and turn.running
                if not handling and item["obligation"] in owed:
                    state = "blocked"
                    reason = (
                        "stopped" if in_turn and turn.ended is not None else "quiet"
                    )
                    left.append(item)
            elif pickup is None:
                sent.append(item["ts"])
                if _quiet(item["ts"], now, PICKUP_GRACE):
                    state, reason = "blocked", "undelivered"
            if state == "waiting" and item["input"] in forked:
                state = "running"
        item.update(
            state=state,
            reason=reason,
            seen=seen,
            # A start on a queued update is the agent taking it up ahead of the queue.
            queued=pickup == "queued" and not (start is not None and held),
            handling=handling,
        )
        result.append(item)
    covered = {item["obligation"] for item in result if item["state"] == "running"}
    for item in left:
        if item["obligation"] in covered:
            item["state"], item["reason"] = "waiting", None
    return result, aging, sent


def _stand_todos(
    todos: list[dict], present: dict, now: datetime, *, held: bool, turn: Turn
) -> tuple[list[dict], dict[str, tuple[dict, bool, bool]]]:
    """Say where each open to-do stands as an update a start holds does, and return
    beside them, for each to-do a start ran on, that start and how quiet and whether
    dropped it is. A to-do nothing has started waits; one whose start went quiet or
    was dropped is `blocked` and keeps the line it last said. Nobody holding the page
    has nothing in hand, so an unheld page's to-dos wait with no line."""
    result = []
    aging = {}
    for raw in todos:
        todo = dict(raw)
        start = todo["line"]
        if start is not None and held:
            quiet, dropped = _start_age(start, present, now, turn)
            aging[todo["id"]] = (start, quiet, dropped)
            todo["state"], todo["reason"] = (
                ("blocked", "stopped" if dropped else "quiet")
                if quiet
                else ("running", None)
            )
        else:
            todo["line"] = None
        result.append(todo)
    return result, aging


def _stand_records(updates: list[dict], workflows: list[dict]) -> list[dict]:
    """Each update's record standing where the strongest workflow serving it does
    (`standing.strength`, then the newer input), which `workflow` names."""
    serving: dict[str, list[dict]] = {}
    for item in workflows:
        if item["obligation"] is not None:
            serving.setdefault(item["obligation"], []).append(item)
    records = []
    for record in updates:
        record = dict(record)
        if record["state"] != "done" and (held := serving.get(record["id"])):
            strongest = max(held, key=lambda item: (strength(item), item["seq"]))
            record.update(
                state=strongest["state"],
                reason=strongest["reason"],
                seen=strongest["seen"],
                workflow=strongest["id"],
            )
        records.append(record)
    return records


def canonical_activity(
    present: dict,
    interaction_evidence: list[dict],
    events: list,
    now_iso: str,
    stream: dict | None = None,
    reply: dict | None = None,
    reservations: dict | None = None,
    *,
    todo_reading=None,
    updates: dict,
) -> dict:
    """Return the one current reading of agent activity for a page snapshot.

    `interaction_evidence` are the page's workflows and `updates` the records the
    user's updates publish (`workflows.handed_over`), and `events` the log they were
    read from, which holds the agent's open to-dos and the starts running on them
    (`todos.TodoReading`). Each comes back saying where it stands (`standing`):
    `workflows`, `records` for the updates, and `todos` for the open to-dos.

    `obligations` are the answers the agent owes: for each update record whose next
    actor is the agent, the workflow of the input it names, carrying the record's id as
    `obligation`, whether a harness queue holds it (`queued`) and, as `answer`, the
    operation that answers it (`obligations.response_address`) with what its receipts
    give it (`_receipt_bindings`). `reservations` reserve automatic replies from the
    claimant's exact App Server turn (`reply_reservation_stands`); an answer they
    reserve adds `writer: "turn"` and the reservation's attempt. An explicit addressed
    answer may commit first; the automatic final then yields to it.

    `counts` are the answers owed by where their update stands, and of them all the
    `unseen` ones no turn has taken in.

    `detail_source` preserves the selected start's event and item identity when
    its authored words supply the status's detail. Harness observations and general
    status declarations have no exact input source. Consumers never recover one
    by matching the displayed words."""
    from .todos import TodoReading

    log = todo_reading or TodoReading(events)
    now = datetime.fromisoformat(now_iso)
    status = present["status"]
    declared = declared_at(present, events)
    turn, stream_live = current_turn(present, declared, stream, now)
    closed = status["state"] == "idle"
    # What the harness observed the agent doing now: a live stream step while its turn
    # runs, the harness's own word that the turn waits on the user in its window, or
    # that work the ended turn left, such as a coordinator's workers, still runs.
    observed = None
    if stream_live and turn.running:
        observed = stream
    elif turn.step is not None and not closed:
        assert turn.step_since is not None
        observed = {"kind": turn.step, "detail": "", "ts": turn.step_since.isoformat()}
    elif turn.background and not closed:
        assert turn.ended is not None
        observed = {
            "kind": "working",
            "detail": BACKGROUND_DETAIL,
            "ts": turn.ended.isoformat(),
        }
    status_dropped = _dropped(status.get("ts"), turn.ended)
    declared_quiet = _quiet(declared, now, WORKING_GRACE) or _dropped(
        declared, turn.ended
    )
    unheld = present["session_alive"] is False or (
        present["session_alive"] is None and not present["listening"] and declared_quiet
    )
    held = not unheld
    owing = {
        record["source"]["id"]: record
        for record in updates["all"]
        if record["next_actor"] == "agent"
    }
    workflows, aging, sent = _stand_workflows(
        interaction_evidence,
        present,
        now,
        held=held,
        turn=turn,
        owed={record["id"] for record in owing.values()},
    )
    todos, todo_aging = _stand_todos(log.owed, present, now, held=held, turn=turn)
    bindings = _receipt_bindings(workflows, present)
    _bind_reply(workflows, reply)

    def owed_answer(item: dict) -> dict:
        answer = {
            **response_address(owing[item["input"]]),
            **bindings[item["input"]],
        }
        reservation = (reservations or {}).get(item["input"])
        if answer["kind"] == "reply" and reply_reservation_stands(
            reservation,
            present.get("claim_session"),
            present,
        ):
            assert reservation is not None
            answer.update(writer="turn", attempt=reservation["attempt"])
        return answer

    # The items in hand: each update a start holds, unless its reply now streams, and
    # each to-do a start runs on, each beside how quiet and whether dropped that start
    # is. Their newest start is the line the page's status shows.
    in_hand: list[tuple[dict, tuple[bool, bool]]] = [
        (aging[item["id"]][0], aging[item["id"]][1:])
        for item in workflows
        if item["id"] in aging and item["response"] is None
    ] + [(start, (quiet, dropped)) for start, quiet, dropped in todo_aging.values()]

    # A dialog in the agent's own window holds whatever its turn has in hand: the
    # user's answer there is the move that frees it.
    terminal = bool(observed and observed["kind"] in AWAITING_KINDS)
    if terminal:
        for item in (*workflows, *todos):
            start = (aging.get(item["id"]) or todo_aging.get(item["id"]) or (None,))[0]
            if (
                item["state"] == "running"
                and start is not None
                and start.get("session") == present.get("claim_session")
                and start.get("turn") == present["turn"]
            ):
                item["state"], item["reason"] = "blocked", "terminal"

    # Every moment at which some belief above lapses, each as a moment and the
    # grace that runs from it. Status age and the turn's ending can change ownership
    # even when the page still reads closed, so every such boundary counts;
    # consumers decide nothing locally and ask this fold for the next complete
    # reading when it arrives. A live harness's word moves without a deadline, and the
    # presence token carries it.
    lapses = [
        (_moment(status.get("ts")), WORKING_GRACE),
        (_moment(declared), WORKING_GRACE),
        (turn.until, timedelta()),
        *((_moment(ts), PICKUP_GRACE) for ts in sent),
        *((_moment(start["ts"]), WORKING_GRACE) for start, _age in in_hand),
    ]
    if stream and stream.get("kind") not in AWAITING_KINDS:
        lapses.append((_moment(stream.get("ts")), WORKING_GRACE))
    if reply and reply["state"] == "active":
        lapses.append((_moment(reply["updated_at"]), WORKING_GRACE))
    deadlines = [
        moment + grace for moment, grace in lapses if moment and moment + grace > now
    ]

    # Page activity counts the updates the agent owes, one per record. A receipt
    # reports delivery for every update the user handed over, but an update that owes
    # nothing, an input a newer one in its thread answers through, and a failed
    # answer the user must resend are no work the status may promise the agent
    # picks up.
    obligations = [item for item in workflows if item["input"] in owing]
    in_hand_now = [(start, age) for start, age in in_hand if not age[0]]
    # The updates the claimant's running turn took in and has neither started nor
    # begun to answer.
    handling = [
        item for item in obligations if item["handling"] and item["response"] is None
    ]
    # Owed updates that stalled with the agent to act: left by a turn seen to end
    # or be interrupted before answering, or still unpicked past the pickup grace.
    # With nothing taking input, these are what only a nudge will move. Work merely
    # gone quiet is left out, since a turn Leaf stopped believing in may still be
    # running a long step, which is also why admission nudges only after a seen
    # ending; unpicked input asks the user even without one, since with no record
    # to see an interrupt the user's nudge is its only remedy.
    stranded = [
        item
        for item in obligations
        if item["state"] == "blocked" and item["reason"] in STRANDED
    ]

    # `presence` reads this wherever it asks whether anyone is there; a watch
    # question such as the Stop hook's still asks for the lease.
    # Nor is the agent away where the nudge the next input gets starts a turn
    # (`Harness.input_wakes`).
    taking_input = takes_input(present, turn) or (
        nudge_due(present, turn) and present["input_wakes"]
    )
    presence = (
        "closed" if closed else "gone" if unheld else "here" if taking_input else "away"
    )
    attended = presence in {"here", "away"}
    state = "waiting" if obligations or todos else "done"
    reason = None
    detail = ""
    detail_source = None
    ts = status.get("ts")
    dropped = status_dropped and not closed
    if attended and in_hand_now:
        # What the work *is* comes from the agent, on every harness: the line of the
        # newest item it has in hand. An observed step says a session is alive and
        # moving; it cannot say what the user is waiting for, and a step that replaced
        # the line would trade the one reading written for them for the one that
        # happens to be newest. So it stands beside the line as `observed`.
        start, (_, dropped) = max(in_hand_now, key=lambda pair: pair[0]["seq"])
        state, detail, ts = "running", start["text"], start["ts"]
        detail_source = {"event_id": start["id"], "item": start["item"]}
    elif attended and observed is not None:
        # A step the harness observed is Leaf's account, not the agent's line, so it
        # stands only as `observed` and the line stays empty for the agent to write.
        state, dropped, ts = "running", False, observed["ts"]
    elif attended and handling:
        # Opening an exact delivery into the claimant's running turn proves generic
        # page work even before the agent starts an item. It does not bind that
        # execution state back onto any other interaction; each update keeps its own
        # standing.
        latest = max(handling, key=lambda item: item.get("delivery_seq") or 0)
        state, ts, dropped = "running", latest["ts"], False
    elif attended and in_hand:
        # Items still in hand whose turn has gone quiet or ended: the page is blocked
        # on the newest one's line.
        start, (_, dropped) = max(in_hand, key=lambda pair: pair[0]["seq"])
        state, detail, ts = "blocked", start["text"], start["ts"]
        detail_source = {"event_id": start["id"], "item": start["item"]}
    elif presence == "here":
        dropped = False
    working = state == "running"
    if working and terminal:
        state, reason = "blocked", "terminal"
    elif not working:
        # The stranded update the page is blocked on where nothing is in hand: the
        # page says why in that update's own reason, as its thread does.
        lead = None
        if presence != "here" and stranded:
            state = "blocked"
            if not in_hand:
                lead = max(stranded, key=strength)
        if state == "blocked":
            reason = "stopped" if dropped else lead["reason"] if lead else "quiet"
        if dropped:
            # A belief the turn's ending retired is dated by that ending, not by the
            # start's own last word: "last checked in just now" beside an amber dot
            # would argue with the dot.
            assert turn.ended is not None
            ts = turn.ended.isoformat()
        elif lead and lead["reason"] != "undelivered":
            # So is an update a turn left: by that turn's ending where it was seen,
            # else by the update's own last evidence.
            ts = turn.ended.isoformat() if turn.ended is not None else lead["ts"]
    # Whose move changes the reading: the user's where a dialog in the agent's own
    # window holds the turn, or where only their nudge will move a stranded update.
    next_actor = (
        None
        if state == "done"
        else "user"
        if reason == "terminal"
        or (state == "blocked" and stranded and presence != "here")
        else "agent"
    )

    served_obligations = [
        {
            **item,
            "obligation": owing[item["input"]]["id"],
            "answer": owed_answer(item),
        }
        for item in obligations
    ]
    for item in workflows:
        del item["queued"], item["handling"]
    return {
        "presence": presence,
        "state": state,
        "reason": reason,
        "next_actor": next_actor,
        "detail": detail,
        "detail_source": detail_source,
        # The step behind a working reading, reported whether or not it is also the
        # sentence, so a consumer can show both without asking which harness this is.
        # Only while the turn is at work or held by its own dialog: a step standing
        # beside "last checked in 30m ago" would argue with the amber dot the rest of
        # that reading wears.
        "observed": (observed.get("detail", "") if observed and working else ""),
        "observed_kind": observed["kind"] if observed and working else None,
        "counts": {
            "running": sum(item["state"] == "running" for item in obligations),
            "waiting": sum(item["state"] == "waiting" for item in obligations),
            "blocked": sum(item["state"] == "blocked" for item in obligations),
            "unseen": sum(not item["seen"] for item in obligations),
        },
        "ts": ts,
        "next_transition_at": min(deadlines).isoformat() if deadlines else None,
        "workflows": workflows,
        "todos": todos,
        "records": _stand_records(updates["all"], workflows),
        "obligations": served_obligations,
    }
