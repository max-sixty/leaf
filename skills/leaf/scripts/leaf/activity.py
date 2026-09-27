"""Canonical page availability and agent work projected from durable evidence.

Status is an agent declaration, claims prove ownership and turn lifetime, and pickup
events prove delivery. Delivery remains interaction evidence rather than becoming the
page's execution state. This module is the one fold that orders those facts and
supplies every reader — browser chrome, hooks, and agent-facing state — with one
answer.
"""

from datetime import datetime, timedelta
from typing import NamedTuple

WORKING_GRACE = timedelta(minutes=15)
PICKUP_GRACE = timedelta(minutes=2)
TURN_RENEWAL_GRACE = timedelta(minutes=2)
WORK_KINDS = {
    "working",
    "thinking",
    "tool",
    "awaiting_approval",
    "awaiting_input",
    "awaiting_user",
    "replying",
}
# Steps that wait on the user in the agent's own window, which renew nothing until
# the user answers there.
# `awaiting_user` is a dialog whose kind, approval or question, the host does not
# say.
AWAITING_KINDS = {"awaiting_approval", "awaiting_input", "awaiting_user"}


def _moment(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Old page-local status files were not schema-validated. They remain
        # evidence with no usable age rather than taking the whole state route down.
        return None


def _quiet(ts: str | None, now: datetime, grace: timedelta) -> bool:
    written = _moment(ts)
    return bool(written and now - written >= grace)


def _dropped(ts: str | None, ended: datetime | None, now: datetime) -> bool:
    """Whether a claim written before its turn ended has gone unrenewed past the
    renewal grace after that ending."""
    written = _moment(ts)
    return bool(
        written and ended and written <= ended and now - ended >= TURN_RENEWAL_GRACE
    )


def canonical_stream_reply(
    present: dict, now_iso: str, reply: dict | None
) -> dict | None:
    """Project one provisional reply against its session lease and age."""
    if reply is None:
        return None
    result = dict(reply)
    if result.get("state") == "active" and (
        result.get("session") != present.get("claim_session")
        or not present["listening"]
        or _quiet(
            result.get("updated_at") or result.get("ts"),
            datetime.fromisoformat(now_iso),
            WORKING_GRACE,
        )
    ):
        result["state"] = "disconnected"
    return result


def _reply_evidence(reply: dict) -> dict:
    """Keep response settlement evidence in activity without duplicating its text."""
    return {
        key: reply.get(key)
        for key in ("state", "session", "turn", "reply_to", "responds", "settles")
    } | {
        **({"attempt": reply["attempt"]} if reply.get("attempt") else {}),
        "has_text": bool(reply.get("text")),
    }


def _bind_reply(workflows: list[dict], reply: dict | None) -> None:
    """Bind provisional response progress only to the exact input it names.

    A durable response outranks it: a host's failure reply has already answered
    the input, and the turn's leftover stream must not paint it as still replying."""
    if reply is None or not reply.get("responds"):
        return
    workflow = next(
        (item for item in workflows if item.get("input") == reply["responds"]), None
    )
    if workflow is None or workflow["stage"] == "answered":
        return
    workflow["response"] = _reply_evidence(reply)
    workflow["stage"] = "replying"
    workflow["activity"] = [
        {
            "kind": "replying",
            "detail": None,
            "ts": reply.get("updated_at") or reply.get("ts"),
            "session": reply.get("session"),
            "turn": reply.get("turn"),
        }
    ]
    # `partial` is a turn that completed without a final answer: it ended with
    # the move unanswered.
    condition = {
        "disconnected": "stale",
        "interrupted": "interrupted",
        "failed": "failed",
        "partial": "ended",
    }.get(reply.get("state"))
    workflow["condition"] = (
        {"kind": condition, "operation": "response"} if condition else None
    )


def answer_command(answer: dict) -> str:
    """The one operation that writes an answer, with the id it is addressed to."""
    if answer["kind"] == "reply":
        return f"`leaf thread reply <page> --for {answer['for']}`"
    if answer["kind"] == "turn":
        return f"your turn's final message for {answer['for']}"
    return f"a stamped version whose markup records action {answer['action']}"


def unanswered(obligations: list[dict], of: str = "") -> str:
    """Say how many user moves have no answer and name what answers each. `of`
    narrows which moves these are, such as the acknowledged ones."""
    commands = "; ".join(answer_command(item["answer"]) for item in obligations)
    moves = f"user move{'s' if len(obligations) != 1 else ''}"
    return (
        f"{len(obligations)} {of + ' ' if of else ''}{moves} with no answer "
        f"({commands})"
    )


def _turn_wrote(obligation: dict, state: dict) -> bool:
    """Whether the claimant's open turn finished the reply it owes this move.

    A `turn` answer is written by the claimant's own turn, and the carrier commits
    it once the turn ends, after the agent's last command. So the move is answered
    now when the turn's final message is complete, with text, in the reply draft
    bound to it."""
    draft = obligation.get("response") or {}
    return bool(
        obligation["answer"]["kind"] == "turn"
        and draft.get("state") == "active"
        and draft.get("settles")
        and draft.get("has_text")
        and draft.get("turn") == state["claim_turn"]
    )


def acknowledged_obligations(state: dict) -> list[dict]:
    """The owed answers whose moves the page cursor has passed, which nothing will
    deliver again."""
    return [
        obligation
        for obligation in state["activity"]["obligations"]
        if obligation["seq"] <= state["cursor"]
    ]


def blocking_obligations(state: dict, *, carried: bool) -> list[dict]:
    """The owed answers that keep the agent from ending its turn or idling the page.

    The Stop hook and `leaf status idle` both refuse over exactly these: the
    acknowledged moves nothing else is set to answer. A move a carrier queued is
    answered by the later turn the queue opens, where the prompt hook records it
    `opened` and it blocks from then on. A turn answer the open turn has
    finished is committed by the claimant's carrier once the turn ends, so it is
    answered while that carrier (`carried`) is live."""
    return [
        obligation
        for obligation in acknowledged_obligations(state)
        if obligation["stage"] != "queued"
        and not (carried and _turn_wrote(obligation, state))
    ]


def transition_due(activity: dict, now_iso: str) -> bool:
    """Whether a projected activity reading has reached its refresh boundary."""
    due = _moment(activity.get("next_transition_at"))
    return bool(due and due <= datetime.fromisoformat(now_iso))


class Turn(NamedTuple):
    """The claimant session's current turn, as the one reading every rule of the
    fold takes: whether it is running; when it was seen to end, where something saw
    that; until when a running turn is believed on its stamps alone; and an observed
    step while it waits on the user in its own window, with when that wait began."""

    running: bool
    ended: datetime | None = None
    until: datetime | None = None
    step: str | None = None
    step_since: datetime | None = None


def claimant_turn(
    present: dict,
    status: dict,
    stream: dict | None,
    now: datetime,
    *,
    awaiting: bool = False,
) -> Turn:
    """Whether the claimant's turn is running, from every piece of evidence,
    each dated by when it was written, the newest deciding.

    The claim's stamps are the spine: the prompt hook or a carrier opens the turn,
    a prompt or delivery into an open turn renews its stamp, and the Stop hook or
    a carrier closes it. An interrupt runs no hook, so an open stamp is believed
    only while something in that turn renewed it within the working grace: its
    last opening, a status written during it, or the claimant's streamed
    activity. Past that nothing says whether it runs, which reads as not
    running without calling it ended.

    The host's own record (`Harness.live_turn`) adds the two things no hook
    sees, each only when newer than what it contradicts: an `idle` newer than
    every renewal ends the open turn at that moment (an interrupt), and a
    `waiting` newer than the stamps is a dialog open now, a step shown whether or
    not the stamps say a turn is open. Its `busy` is never read, since the host
    keeps it across turn endings while background work runs. `awaiting` says the
    claimant's observer reports a wait on the user right now, which holds the
    turn open for as long as that observer lives."""
    opened = _moment(present.get("turn_opened"))
    closed = _moment(present.get("turn_closed"))
    if present["session_alive"] is not True:
        return Turn(False, ended=closed)
    host = present.get("live_turn") or {}
    since = _moment(host.get("since"))
    stamped = max((moment for moment in (opened, closed) if moment), default=None)
    dialog = host.get("state") == "waiting" and since and since >= (stamped or since)
    step = {"step": "awaiting_user", "step_since": since} if dialog else {}
    if closed is not None or opened is None or present.get("claim_turn") is None:
        return Turn(False, ended=closed, **step)
    if awaiting or dialog:
        return Turn(True, **step)
    renewals = [opened, _moment(status.get("ts"))]
    if stream and stream.get("session") == present.get("claim_session"):
        renewals.append(_moment(stream.get("ts")))
    renewed = max(moment for moment in renewals if moment and moment >= opened)
    if host.get("state") == "idle" and since and since >= renewed:
        return Turn(False, ended=since)
    until = renewed + WORKING_GRACE
    return Turn(now < until, until=until)


def current_turn(
    present: dict, stream: dict | None, now: datetime
) -> tuple[Turn, bool]:
    """The claimant's turn as every reader takes it, beside whether the claimant's
    own observer streams live activity for it now.

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
        status,
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


def _canonical_workflows(
    evidence: list[dict], present: dict, now: datetime, *, held: bool, turn: Turn
) -> tuple[list[dict], dict[str, tuple[bool, bool]]]:
    """Age each workflow's evidence, and return beside them how quiet and whether
    dropped each Working claim is, which the page reading below dates by."""
    result = []
    aging = {}
    for raw in evidence:
        item = dict(raw)
        stage = item["stage"]
        if stage == "working":
            same_session = bool(
                item.get("session") and item["session"] == present.get("claim_session")
            )
            dropped = same_session and _dropped(item["ts"], turn.ended, now)
            quiet = _quiet(item["ts"], now, WORKING_GRACE) or dropped
            if quiet and held:
                item["condition"] = {"kind": "stale", "operation": "work"}
            if not held:
                if item.get("input") is None:
                    continue
                stage = item.get("fallback_stage", "sent")
                item["ts"] = item.get("fallback_ts", item["ts"])
                item["detail"] = None
                item["agent"] = None
                item["session"] = None
                item["activity"] = []
            else:
                aging[item["id"]] = (quiet, dropped)
        if stage == "sent" and _quiet(item["ts"], now, PICKUP_GRACE):
            item["condition"] = {"kind": "stale", "operation": "delivery"}
        item["stage"] = stage
        item.pop("fallback_stage", None)
        item.pop("fallback_ts", None)
        result.append(item)
    return result, aging


def canonical_activity(
    present: dict,
    interaction_evidence: list[dict],
    now_iso: str,
    stream: dict | None = None,
    reply: dict | None = None,
    bindings: dict | None = None,
) -> dict:
    """Return the one current reading of agent activity for a page snapshot.

    `bindings` are the stream's reply bindings. A reply address bound to the
    claimant's session is that session's App Server turn to write, with its own
    opening and final messages, so its workflow's answer reads as a `turn` under
    the binding's attempt: every consumer that holds the agent to an answer, or
    refuses a second writer, reads that answer rather than the binding."""
    now = datetime.fromisoformat(now_iso)
    status = present["status"]
    turn, stream_live = current_turn(present, stream, now)
    # What the host observed the agent doing now: a live stream step while its turn
    # runs, or the host's own word that the turn waits on the user in its window.
    observed = None
    if stream_live and turn.running:
        observed = stream
    elif turn.step is not None and status["state"] != "idle":
        observed = {"kind": turn.step, "detail": "", "ts": turn.step_since.isoformat()}
    status_dropped = _dropped(status.get("ts"), turn.ended, now)
    status_quiet = _quiet(status.get("ts"), now, WORKING_GRACE) or status_dropped
    unheld = present["session_alive"] is False or (
        present["session_alive"] is None and not present["listening"] and status_quiet
    )
    held = not unheld
    workflows, aging = _canonical_workflows(
        interaction_evidence, present, now, held=held, turn=turn
    )
    _bind_reply(workflows, reply)
    for item in workflows:
        binding = (bindings or {}).get(item.get("input"))
        if (
            item["answer"] is not None
            and item["answer"]["kind"] == "reply"
            and binding
            and binding["session"] == present.get("claim_session")
        ):
            item["answer"] = {
                **item["answer"],
                "kind": "turn",
                "attempt": binding["attempt"],
            }

    # Every moment at which some belief above lapses, each as a moment and the
    # grace that runs from it. Status age and the turn's ending can change ownership
    # even when the primary label remains Closed, so every such boundary counts;
    # consumers decide nothing locally and ask this fold for the next complete
    # reading when it arrives. A live host's word moves without a deadline, and the
    # presence token carries it.
    lapses = [
        (_moment(status.get("ts")), WORKING_GRACE),
        (turn.ended, TURN_RENEWAL_GRACE),
        (turn.until, timedelta()),
        *(
            (_moment(item["ts"]), grace)
            for item in workflows
            for stage, grace in (("sent", PICKUP_GRACE), ("working", WORKING_GRACE))
            if item["stage"] == stage
        ),
    ]
    if stream and stream.get("kind") not in AWAITING_KINDS:
        lapses.append((_moment(stream.get("ts")), WORKING_GRACE))
    if reply and reply.get("state") == "active":
        lapses.append(
            (_moment(reply.get("updated_at") or reply.get("ts")), WORKING_GRACE)
        )
    deadlines = [
        moment + grace for moment, grace in lapses if moment and moment + grace > now
    ]

    # Page activity counts the moves the agent owes, one per answer. A receipt
    # reports delivery for every move the user handed over, but a move that owes
    # nothing, an input a newer one in its thread answers through, and a failed
    # answer the user must resend are no work the banner may promise the agent
    # picks up.
    obligations = [item for item in workflows if item["answer"] is not None]
    active = [item for item in workflows if item["stage"] == "working"]
    active_now = [item for item in active if not aging[item["id"]][0]]
    active_moves = [
        item
        for item in obligations
        if item["stage"] in {"working", "replying"} and item["condition"] is None
    ]
    # Page work is scoped to the live claimant, not to one user input. A newer
    # delivery may remain queued or pending while the agent continues other work on
    # the page; its exact progress stays in `workflows` below.
    declared_work = status["state"] == "working" and not status_quiet
    current_work = observed is not None or declared_work
    opened = [item for item in obligations if item["stage"] == "picked_up"]
    in_this_turn = [
        item
        for item in opened
        if item.get("delivery_session") == present.get("claim_session")
        and item.get("delivery_turn") == present.get("claim_turn")
    ]
    handling = in_this_turn if turn.running else []
    for item in opened:
        if item in handling:
            continue
        # Pickup remains durable history; the condition says the exact turn it
        # entered is no longer a running turn handling it now: that turn was seen
        # to end, or nothing says whether it runs, or the move was opened in some
        # other, older turn.
        item["condition"] = {
            "kind": "ended"
            if item in in_this_turn and turn.ended is not None
            else "stale",
            "operation": "work",
        }
    queued = [item for item in obligations if item["stage"] == "queued"]
    pending = [item for item in obligations if item["stage"] == "sent"]
    # Owed moves that stalled with the agent to act: left by a turn seen to end
    # or be interrupted before answering, or still unpicked past the pickup grace.
    # With nothing taking input, these are what only a nudge will move. Work merely
    # gone quiet is left out, since a turn Leaf stopped believing in may still be
    # running a long step, which is also why admission nudges only after a seen
    # ending; unpicked input asks the user even without one, since with no record
    # to see an interrupt the user's nudge is its only remedy.
    overdue = [
        item
        for item in obligations
        if item["next_actor"] == "agent"
        and item["condition"] is not None
        and (
            item["condition"]["kind"] in {"ended", "interrupted"}
            or item["condition"]["operation"] == "delivery"
        )
    ]

    # The page's `kind` reads this wherever it asks whether anyone is there, in the
    # banner and in neighbouring pages' rows; a watch question such as the Stop
    # hook's still asks for the lease.
    taking_input = takes_input(present, turn)
    kind = "away"
    detail = ""
    ts = status.get("ts")
    dropped = status_dropped
    if status["state"] == "idle":
        kind, dropped = "closed", False
    elif unheld:
        kind = "unheld"
    elif current_work:
        kind = "working"
        # A newer queued interaction does not erase fresh evidence that the agent is
        # already working, nor does that older work floor claim the queued input. The
        # canonical counts keep the two facts separate for every consumer.
        #
        # What the work *is* comes from the agent, on every host. An observed step
        # says a session is alive and moving, which is why it can make a page working
        # over a declaration that says otherwise; it cannot say what the user is
        # waiting for, and a step that replaced the sentence would trade the one
        # reading written for them for the one that happens to be newest. So a
        # current declaration keeps the sentence and its own date, and the step
        # stands beside it as `observed`.
        if declared_work:
            detail = status.get("detail", "")
        else:
            detail, ts, dropped = observed.get("detail", ""), observed["ts"], False
    elif active_now:
        latest = max(active_now, key=lambda item: (item["seq"], item["id"]))
        detail, ts = latest.get("detail") or "", latest["ts"]
        dropped, kind = aging[latest["id"]][1], "working"
    elif handling:
        # Opening an exact delivery into the claimant's running turn proves generic
        # page work even before the agent writes a status sentence. It does not bind
        # that execution state back onto any other interaction; each receipt keeps
        # its own workflow stage.
        latest = max(handling, key=lambda item: item.get("delivery_seq") or 0)
        kind, ts, dropped = "working", latest["ts"], False
    elif active:
        latest = max(active, key=lambda item: (item["seq"], item["id"]))
        detail, ts = latest.get("detail") or "", latest["ts"]
        dropped = aging[latest["id"]][1]
        kind = "stalled" if taking_input else "away"
    elif status["state"] == "working":
        detail = status.get("detail", "")
        kind = "stalled" if taking_input else "away"
    elif taking_input:
        kind, detail, dropped = "listening", status.get("detail", ""), False
    if dropped and kind != "working":
        # A belief the turn's ending retired is dated by that ending, not by the
        # claim's own last word: "last checked in just now" beside an amber dot
        # would argue with the dot.
        ts = turn.ended.isoformat()

    return {
        "kind": kind,
        "held": held,
        "dropped": dropped,
        "detail": detail,
        # The step behind a working reading, reported whether or not it is also the
        # sentence, so a consumer can show both without asking which host this is. Only
        # under `working`: a step standing beside "last checked in 30m ago" would argue
        # with the amber dot the rest of that reading wears.
        "observed": (
            observed.get("detail", "") if observed and kind == "working" else ""
        ),
        "observed_kind": observed["kind"] if observed and kind == "working" else None,
        "counts": {
            "active": len(active_moves),
            "handling": len(handling),
            "queued": len(queued),
            "picked_up": len(opened) - len(handling),
            "pending": len(pending),
            "overdue": len(overdue),
            "total": len(obligations),
        },
        "ts": ts,
        "next_transition_at": min(deadlines).isoformat() if deadlines else None,
        "workflows": workflows,
        "obligations": obligations,
        **({"reply": _reply_evidence(reply)} if reply is not None else {}),
    }
