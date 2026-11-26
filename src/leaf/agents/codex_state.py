"""Codex delivery eligibility and paths for its serialized transport reservations.

The session lifecycle owner records provider identity, lifetime and revision.
This module derives an observation from that authority, and proves eligibility
with the page's dated activity rather than maintaining another running flag.
A delivery acknowledgement proves entry through its exact hook reservation and lifecycle revision.
A turn Codex resumes without a user prompt reaches that authority from Codex's
native transcript (`codex_transcript.py`).

The prompt hook records the provider turn. Once the session has claimed a page
(`state.held_claims`), its PostToolUse hook identifies an unknown session-scoped turn
once, or renews only the provider turn already observed running, and offers one
immutable envelope between steps (`codex.offer_hook_delivery`).
The observation's revision advances on a prompt, an ending or a tool step, and the
queue rechecks it under the delivery lock before reserving its transport, so even a
renewed step in the same turn invalidates an idle reading taken before it. Completing
a hook does not prove the model read its output: `leaf delivery ack` in the owning task
confirms complete receipt and records the opened pickup (`codex.confirm_codex_pointer`),
through `codex.accept_codex_delivery` as every transport's acceptance does. Stop or
Interrupt closes the observed turn, including for a page acquired before its first tool
hook.
Stale provider callbacks are refused before planning or printing context, and a newer
prompt protects its generation and turn.
"""

from pathlib import Path

from leaf.base.state import (
    session_file,
    session_lock_path,
    session_record,
    turn_open,
)


def delivery_dir(session_id: str) -> Path:
    return session_file(session_id, "deliveries")


def delivery_lock_path(session_id: str) -> Path:
    return session_lock_path(session_id)


def hook_turn(session_id: str) -> dict | None:
    """The canonical session observation for transport reservation revision checks.

    Running is derived from the dated session lifecycle, never stored by a
    second Codex writer. Page activity still proves current delivery eligibility.
    """
    record = session_record(session_id)
    if record is None:
        return None
    return {**record, "running": turn_open(record)}


def delivery_turn(session_id: str) -> str | None:
    """The observed provider turn eligible for hook delivery.

    Use the same dated activity reading as the page, so an interrupted or stale
    turn never holds the idle queue indefinitely. Claims derive the current
    provider turn from the session lifecycle; delivery hooks renew it and offer
    updates. Read outside the delivery lock: capture takes a page transaction
    before that lock.
    """
    observed = hook_turn(session_id)
    if not observed or not observed["running"]:
        return None
    from leaf.agents.presence import session_turn_running

    return observed["turn"] if session_turn_running(session_id) else None
