"""Canonical agent activity projected from durable page evidence.

Status is an agent declaration, claims prove ownership and turn lifetime, and pickup
events prove delivery. None is current state by itself. This module is the one fold
that orders those facts and supplies every reader — browser chrome, hooks, and
agent-facing state — with one answer.
"""

from datetime import datetime, timedelta

WORKING_GRACE = timedelta(minutes=15)
PICKUP_GRACE = timedelta(minutes=2)
TURN_RENEWAL_GRACE = timedelta(minutes=2)


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


def transition_due(activity: dict, now_iso: str) -> bool:
    """Whether a projected activity reading has reached its refresh boundary."""
    due = _moment(activity.get("next_transition_at"))
    return bool(due and due <= datetime.fromisoformat(now_iso))


def _canonical_interactions(
    evidence: list[dict], present: dict, now: datetime, *, held: bool
) -> list[dict]:
    result = []
    for raw in evidence:
        item = dict(raw)
        phase = item["phase"]
        quiet = False
        dropped = False
        if phase == "active":
            same_session = bool(
                item.get("session") and item["session"] == present.get("claim_session")
            )
            dropped = same_session and _dropped(
                item["ts"], present.get("turn_closed"), now
            )
            quiet = _quiet(item["ts"], now, WORKING_GRACE) or dropped
            if not held:
                if item.get("event") is None:
                    continue
                phase = item.get("fallback_phase", "sent")
                item["ts"] = item.get("fallback_ts", item["ts"])
                item["detail"] = None
                item["agent"] = None
                item["session"] = None
                quiet = dropped = False
        if phase == "sent" and _quiet(item["ts"], now, PICKUP_GRACE):
            phase = "waiting"
        item["phase"] = phase
        item["quiet"] = quiet
        item["dropped"] = dropped
        item.pop("fallback_phase", None)
        item.pop("fallback_ts", None)
        result.append(item)
    return result


def canonical_activity(
    present: dict, interaction_evidence: list[dict], now_iso: str
) -> dict:
    """Return the one current reading of agent activity for a page snapshot."""
    now = datetime.fromisoformat(now_iso)
    status = present["status"]
    status_quiet = _quiet(status.get("ts"), now, WORKING_GRACE)
    status_dropped = _dropped(status.get("ts"), present.get("turn_closed"), now)
    status_quiet = status_quiet or status_dropped
    unheld = present["session_alive"] is False or (
        present["session_alive"] is None and not present["listening"] and status_quiet
    )
    held = not present.get("unattended") and not unheld
    interactions = _canonical_interactions(
        interaction_evidence, present, now, held=held
    )

    deadlines = []
    # Status age and turn closure can change the primary activity reading for any
    # non-idle declaration. Emit every such boundary; consumers decide nothing
    # locally and ask this fold for the next reading when it arrives.
    if status["state"] != "idle":
        if due := _deadline(status.get("ts"), WORKING_GRACE, now):
            deadlines.append(due)
        if due := _deadline(present.get("turn_closed"), TURN_RENEWAL_GRACE, now):
            deadlines.append(due)
    for item in interactions:
        if item["phase"] == "sent":
            if due := _deadline(item["ts"], PICKUP_GRACE, now):
                deadlines.append(due)
        elif item["phase"] == "active":
            if due := _deadline(item["ts"], WORKING_GRACE, now):
                deadlines.append(due)
            if item.get("session") == present.get("claim_session") and (
                due := _deadline(present.get("turn_closed"), TURN_RENEWAL_GRACE, now)
            ):
                deadlines.append(due)

    # Every unsettled reader move contributes to page activity. ``obligations``
    # is the narrower subset that must receive an agent reply before a turn may
    # end; widget actions can instead be settled by the authored document.
    outstanding = [item for item in interactions if item.get("event") is not None]
    obligations = [item for item in outstanding if item["requires_response"]]
    active = [item for item in interactions if item["phase"] == "active"]
    active_moves = [item for item in active if item.get("event") is not None]
    newest_position = max(
        (item.get("delivery_seq") or item["seq"] for item in outstanding),
        default=0,
    )
    status_after = status.get("after", 0)
    current_work = (
        status["state"] == "working"
        and not status_quiet
        and status_after >= newest_position
    )
    opened = [item for item in outstanding if item["phase"] == "picked_up"]
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
    queued = [item for item in outstanding if item["phase"] == "queued"]
    pending = [item for item in outstanding if item["phase"] in {"sent", "waiting"}]

    kind = "away"
    detail = ""
    ts = status.get("ts")
    count = 0
    quiet = status_quiet
    dropped = status_dropped
    if present.get("unattended"):
        kind, quiet, dropped, ts = "unattended", False, False, None
    elif status["state"] == "idle":
        kind, quiet, dropped = "closed", False, False
    elif unheld:
        kind = "unheld"
    elif current_work:
        kind, detail = "working", status.get("detail", "")
    elif active:
        latest = max(active, key=lambda item: (item["seq"], item["id"]))
        detail, ts = latest.get("detail") or "", latest["ts"]
        quiet, dropped = latest["quiet"], latest["dropped"]
        kind = (
            "stalled"
            if quiet and present["listening"]
            else ("away" if quiet else "working")
        )
    elif handling:
        latest = max(handling, key=lambda item: item.get("delivery_seq") or 0)
        kind, ts, quiet, dropped = "handling", latest["ts"], False, False
        count = len(handling)
    elif queued:
        latest = max(queued, key=lambda item: item.get("delivery_seq") or 0)
        kind, ts, quiet, dropped = "queued", latest["ts"], False, False
        count = len(queued)
    elif left_in_old_turn:
        latest = max(left_in_old_turn, key=lambda item: item.get("delivery_seq") or 0)
        kind, ts, quiet, dropped = "picked_up", latest["ts"], False, True
        count = len(left_in_old_turn)
    elif status["state"] == "working":
        if status_quiet:
            detail = status.get("detail", "")
            kind = "stalled" if present["listening"] else "away"
        elif present["listening"]:
            kind = "listening"
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
        "count": count,
        "counts": {
            "active": len(active_moves),
            "handling": len(handling),
            "queued": len(queued),
            "picked_up": len(left_in_old_turn),
            "pending": len(pending),
            "total": len(outstanding),
        },
        "ts": ts,
        "next_transition_at": min(deadlines).isoformat() if deadlines else None,
        "interactions": interactions,
        "obligations": obligations,
    }
