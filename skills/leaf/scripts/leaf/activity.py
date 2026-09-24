"""Canonical page availability and agent work projected from durable evidence.

Status is an agent declaration, claims prove ownership and turn lifetime, and pickup
events prove delivery. Delivery remains interaction evidence rather than becoming the
page's execution state. This module is the one fold that orders those facts and
supplies every reader — browser chrome, hooks, and agent-facing state — with one
answer.
"""

from datetime import datetime, timedelta

WORKING_GRACE = timedelta(minutes=15)
PICKUP_GRACE = timedelta(minutes=2)
TURN_RENEWAL_GRACE = timedelta(minutes=2)
WORK_KINDS = {
    "working",
    "thinking",
    "tool",
    "awaiting_approval",
    "awaiting_input",
    "replying",
}


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


def _dropped(ts: str | None, closed: str | None, now: datetime) -> bool:
    written, ended = _moment(ts), _moment(closed)
    return bool(
        written and ended and written <= ended and now - ended >= TURN_RENEWAL_GRACE
    )


def _deadline(ts: str | None, grace: timedelta, now: datetime) -> datetime | None:
    written = _moment(ts)
    if written is None:
        return None
    due = written + grace
    return due if due > now else None


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
    condition = {
        "disconnected": "stale",
        "interrupted": "interrupted",
        "failed": "failed",
    }.get(reply.get("state"))
    workflow["condition"] = (
        {"kind": condition, "operation": "response"} if condition else None
    )


def answer_command(answer: dict) -> str:
    """The one command that writes an answer, with the id it is addressed to."""
    if answer["kind"] == "reply":
        return f"`leaf reply <page> --for {answer['for']}`"
    if answer["kind"] == "receipt":
        return f"`leaf receipt <page> {answer['request']} succeeded|failed`"
    return f"a stamped version whose markup records action {answer['action']}"


def unanswered(obligations: list[dict], of: str = "") -> str:
    """Say how many user moves have no answer and name what answers each,
    addressed as its writer takes it: the command, or, for a reply bound to the
    claimant's App Server turn, that turn's final message. `of` narrows which
    moves these are, such as the acknowledged ones."""
    commands = "; ".join(
        f"your final message answers {item['input']}"
        if item.get("turn_answers")
        else answer_command(item["answer"])
        for item in obligations
    )
    moves = f"user move{'s' if len(obligations) != 1 else ''}"
    return (
        f"{len(obligations)} {of + ' ' if of else ''}{moves} with no answer "
        f"({commands})"
    )


def transition_due(activity: dict, now_iso: str) -> bool:
    """Whether a projected activity reading has reached its refresh boundary."""
    due = _moment(activity.get("next_transition_at"))
    return bool(due and due <= datetime.fromisoformat(now_iso))


def _canonical_workflows(
    evidence: list[dict], present: dict, now: datetime, *, held: bool
) -> list[dict]:
    result = []
    for raw in evidence:
        item = dict(raw)
        stage = item["stage"]
        quiet = False
        dropped = False
        if stage == "working":
            same_session = bool(
                item.get("session") and item["session"] == present.get("claim_session")
            )
            dropped = same_session and _dropped(
                item["ts"], present.get("turn_closed"), now
            )
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
                quiet = dropped = False
        if stage == "sent" and _quiet(item["ts"], now, PICKUP_GRACE):
            quiet = True
            item["condition"] = {"kind": "stale", "operation": "delivery"}
        item["stage"] = stage
        item["quiet"] = quiet
        item["dropped"] = dropped
        item.pop("fallback_stage", None)
        item.pop("fallback_ts", None)
        result.append(item)
    return result


def canonical_activity(
    present: dict,
    interaction_evidence: list[dict],
    now_iso: str,
    stream: dict | None = None,
    reply: dict | None = None,
    bindings: dict | None = None,
) -> dict:
    """Return the one current reading of agent activity for a page snapshot.

    `bindings` are the stream's reply bindings: a response address bound to the
    claimant's session is answered by that session's App Server turn, whose
    final message is the reply, and its workflow says so as `turn_answers`."""
    now = datetime.fromisoformat(now_iso)
    status = present["status"]
    stream_quiet = bool(stream and _quiet(stream.get("ts"), now, WORKING_GRACE))
    stream_current = bool(
        stream
        and stream.get("session") == present.get("claim_session")
        and stream.get("kind") in WORK_KINDS
        and present["listening"]
        and present.get("turn_closed") is None
        and not stream_quiet
        and status["state"] != "idle"
    )
    status_quiet = _quiet(status.get("ts"), now, WORKING_GRACE)
    status_dropped = _dropped(status.get("ts"), present.get("turn_closed"), now)
    status_quiet = status_quiet or status_dropped
    unheld = present["session_alive"] is False or (
        present["session_alive"] is None and not present["listening"] and status_quiet
    )
    held = not present.get("unattended") and not unheld
    workflows = _canonical_workflows(interaction_evidence, present, now, held=held)
    _bind_reply(workflows, reply)
    for item in workflows:
        binding = (bindings or {}).get(item.get("input"))
        if binding and binding["session"] == present.get("claim_session"):
            item["turn_answers"] = True

    deadlines = []
    # Status age and turn closure can change ownership even when the primary label
    # remains Closed. Emit every such boundary; consumers decide nothing locally and
    # ask this fold for the next complete reading when it arrives.
    if due := _deadline(status.get("ts"), WORKING_GRACE, now):
        deadlines.append(due)
    if stream and (due := _deadline(stream.get("ts"), WORKING_GRACE, now)):
        deadlines.append(due)
    if (
        reply
        and reply.get("state") == "active"
        and (
            due := _deadline(
                reply.get("updated_at") or reply.get("ts"), WORKING_GRACE, now
            )
        )
    ):
        deadlines.append(due)
    if due := _deadline(present.get("turn_closed"), TURN_RENEWAL_GRACE, now):
        deadlines.append(due)
    for item in workflows:
        if item["stage"] == "sent":
            if due := _deadline(item["ts"], PICKUP_GRACE, now):
                deadlines.append(due)
        elif item["stage"] == "working":
            if due := _deadline(item["ts"], WORKING_GRACE, now):
                deadlines.append(due)
            if item.get("session") == present.get("claim_session") and (
                due := _deadline(present.get("turn_closed"), TURN_RENEWAL_GRACE, now)
            ):
                deadlines.append(due)

    # Page activity counts the moves the agent owes, one per answer. A receipt
    # reports delivery for every move the user handed over, but a move that owes
    # nothing, an input a newer one in its thread answers through, and a failed
    # answer the user must resend are no work the banner may promise the agent
    # picks up.
    obligations = [item for item in workflows if item["answer"] is not None]
    active = [item for item in workflows if item["stage"] == "working"]
    active_now = [item for item in active if not item["quiet"]]
    active_moves = [
        item for item in obligations if item["stage"] in {"working", "replying"}
    ]
    # Page work is scoped to the live claimant, not to one user input. A newer
    # delivery may remain queued or pending while the agent continues other work on
    # the page; its exact progress stays in `workflows` below.
    declared_work = status["state"] == "working" and not status_quiet
    current_work = stream_current or declared_work
    opened = [item for item in obligations if item["stage"] == "picked_up"]
    handling = [
        item
        for item in opened
        if item.get("delivery_session") == present.get("claim_session")
        and item.get("delivery_turn") == present.get("claim_turn")
        and present.get("turn_closed") is None
    ]
    left_in_old_turn = [item for item in opened if item not in handling]
    for item in left_in_old_turn:
        # Keep the interaction-local receipt and page-wide summary on the same
        # reading. Pickup remains durable history, while this flag says the exact
        # turn it entered is no longer the turn handling it now.
        item["dropped"] = True
        if (
            item.get("delivery_session") == present.get("claim_session")
            and item.get("delivery_turn") == present.get("claim_turn")
            and present.get("turn_closed") is not None
        ):
            item["condition"] = {"kind": "ended", "operation": "work"}
        else:
            item["condition"] = {"kind": "stale", "operation": "work"}
    queued = [item for item in obligations if item["stage"] == "queued"]
    pending = [item for item in obligations if item["stage"] == "sent"]

    kind = "away"
    detail = ""
    ts = status.get("ts")
    quiet = status_quiet
    dropped = status_dropped
    if present.get("unattended"):
        kind, quiet, dropped, ts = "unattended", False, False, None
    elif status["state"] == "idle":
        kind, quiet, dropped = "closed", False, False
    elif unheld:
        kind = "unheld"
    elif current_work:
        kind = "working"
        # A newer queued interaction does not erase fresh evidence that the agent is
        # already working, nor does that older work floor claim the queued input. The
        # canonical counts keep the two facts separate for every consumer.
        #
        # What the work *is* comes from the agent, on every host. An observed tool step
        # says a session is alive and moving, which is why it can make a page working
        # over a declaration that says otherwise; it cannot say what the user is
        # waiting for, and a step that replaced the sentence would trade the one reading
        # written for them for the one that happens to be newest. So a current
        # declaration keeps the sentence and its own date, and the step stands beside it
        # as `observed`. Leaf's own wording, written so a claimed move says something at
        # once, is not that sentence: a step the transport watched says more. Nor is a
        # declaration with no words at all, which `leaf status <page> working` writes.
        if declared_work and status.get("stated", True) and status.get("detail"):
            detail = status.get("detail", "")
        elif stream_current:
            detail, ts, quiet, dropped = (
                stream.get("detail", ""),
                stream.get("ts"),
                False,
                False,
            )
        else:
            detail = status.get("detail", "")
    elif active_now:
        latest = max(active_now, key=lambda item: (item["seq"], item["id"]))
        detail, ts = latest.get("detail") or "", latest["ts"]
        quiet, dropped, kind = False, latest["dropped"], "working"
    elif handling:
        # Opening an exact delivery into the claimant's current open turn proves
        # generic page work even before the agent writes a status sentence. It does
        # not bind that execution state back onto any other interaction; each receipt
        # keeps its own workflow stage below.
        latest = max(handling, key=lambda item: item.get("delivery_seq") or 0)
        kind, ts, quiet, dropped = "working", latest["ts"], False, False
    elif active:
        latest = max(active, key=lambda item: (item["seq"], item["id"]))
        detail, ts = latest.get("detail") or "", latest["ts"]
        quiet, dropped = latest["quiet"], latest["dropped"]
        kind = "stalled" if present["listening"] else "away"
    elif status["state"] == "working":
        detail = status.get("detail", "")
        kind = "stalled" if present["listening"] else "away"
    elif present["listening"]:
        kind, detail, quiet, dropped = (
            "listening",
            status.get("detail", ""),
            False,
            False,
        )

    return {
        "kind": kind,
        "held": held,
        "quiet": quiet,
        "dropped": dropped,
        "detail": detail,
        # The step behind a working reading, reported whether or not it is also the
        # sentence, so a consumer can show both without asking which host this is. Only
        # under `working`: a step standing beside "last checked in 30m ago" would argue
        # with the amber dot the rest of that reading wears.
        "observed": (
            stream.get("detail", "") if stream_current and kind == "working" else ""
        ),
        "observed_kind": (
            stream["kind"] if stream_current and kind == "working" else None
        ),
        "counts": {
            "active": len(active_moves),
            "handling": len(handling),
            "queued": len(queued),
            "picked_up": len(left_in_old_turn),
            "pending": len(pending),
            "total": len(obligations),
        },
        "ts": ts,
        "next_transition_at": min(deadlines).isoformat() if deadlines else None,
        "workflows": workflows,
        "obligations": obligations,
        **({"reply": _reply_evidence(reply)} if reply is not None else {}),
    }
