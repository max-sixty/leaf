"""Codex delivery eligibility and paths for its serialized route reservations.

The session lifecycle owner records provider identity, lifetime and revision.
This module derives an observation from that authority, and proves eligibility
with the page's dated activity rather than maintaining another running flag.
A pointer read reaches acceptance only after that proof under its exact revision.
"""

from pathlib import Path

from .leases import session_state_path, step_hook_ran
from .state import session_lock_path, session_record


def delivery_dir(session_id: str) -> Path:
    return session_state_path(session_id, "deliveries")


def delivery_lock_path(session_id: str) -> Path:
    return session_lock_path(session_id)


def hook_turn(session_id: str) -> dict | None:
    """The canonical session observation for delivery route revision checks.

    Running is derived from the dated session lifecycle, never stored by a
    second Codex writer. Page activity still proves current delivery eligibility.
    """
    record = session_record(session_id)
    if record is None:
        return None
    return {
        **record,
        "running": bool(
            record["ended"] is None
            and record["turn"] is not None
            and record["turn_closed"] is None
        ),
    }


def step_delivery_turn(session_id: str) -> str | None:
    """The observed provider turn a proven step hook can deliver into.

    Use the same dated activity reading as the page, so an interrupted or stale
    turn never holds the idle queue indefinitely. Claims derive the current
    provider turn from the session lifecycle; tool hooks renew it and offer
    feedback. Read outside the delivery lock: capture takes a page transaction
    before that lock.
    """
    observed = hook_turn(session_id)
    if not step_hook_ran(session_id) or not observed or not observed["running"]:
        return None
    from .presence import claimant_reading
    from .service import PageTransaction, owned_pages

    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                present, turn = claimant_reading(page_dir, page.events)
                if present["claim_session"] == session_id and turn.running:
                    return observed["turn"]
        except FileNotFoundError:
            continue
    return None


def accept_codex_delivery_read(delivery_id: str) -> None:
    """Use the owning task's pointer read as evidence of entry into its exact turn.

    Reading an envelope alone authorizes no receipt. The hook observation is
    rechecked under the acceptance lock, so queue reservation or a newer turn
    invalidates this proof before any delivery record changes.
    """
    from .host import session_harness

    harness = session_harness()
    if harness is None or (turn := step_delivery_turn(harness.session)) is None:
        return
    observation = hook_turn(harness.session)
    if not observation or observation["turn"] != turn or not observation["running"]:
        return
    from .codex import accept_codex_delivery

    accept_codex_delivery(
        harness.session, delivery_id, turn, hook_observation=observation
    )
