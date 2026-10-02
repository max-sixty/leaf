"""Codex task observation and the paths that serialize delivery routing.

A synchronous hook records the provider turn before the task owns any page.
Tool hooks and carriers share this observation and its revision under the same
per-task delivery lock, so a late callback cannot replace a newer prompt or
close its pages. Cold observations import no delivery, page, or App Server
code. A proven running turn reaches page activity to establish delivery
eligibility; a pointer read reaches acceptance only after that proof, under its
exact hook observation.
"""

from pathlib import Path

from .files import read_json
from .leases import session_state_path, step_hook_ran
from .session_cleanup import HOOK_TURN_SUFFIX, flocked, session_file, write_json


def delivery_dir(session_id: str) -> Path:
    return session_state_path(session_id, "deliveries")


def delivery_lock_path(session_id: str) -> Path:
    return delivery_dir(session_id).with_suffix(".delivery.lock")


def hook_turn(session_id: str) -> dict | None:
    """The latest synchronous hook's provider turn observation, even before a page.

    Async callbacks are not turn openers. This observation lets them bind a page
    acquired mid-turn without replacing a newer turn, and serializes route choice
    against a prompt or ending under the task's delivery lock.
    """
    observation = read_json(session_file(session_id, HOOK_TURN_SUFFIX))
    if (
        not isinstance(observation, dict)
        or not {"turn", "running", "revision"} <= observation.keys()
    ):
        return None
    return observation


def advance_hook_turn(session_id: str, turn_id: str, *, running: bool) -> dict:
    """Advance a provider observation while the caller holds the delivery lock.

    A new tool step renews the same turn, so turn identity alone cannot serialize
    route choice against the activity reading a queue offer took before its lock.
    """
    previous = hook_turn(session_id)
    observation = {
        "turn": turn_id,
        "running": running,
        "revision": previous["revision"] + 1 if previous else 1,
    }
    write_json(session_state_path(session_id, HOOK_TURN_SUFFIX), observation)
    return observation


def start_hook_turn(session_id: str, turn_id: str) -> None:
    with flocked(delivery_lock_path(session_id)):
        advance_hook_turn(session_id, turn_id, running=True)


def end_hook_turn(session_id: str, turn_id: str) -> None:
    """Close the current observed turn, including pages acquired mid-turn.

    A newly claimed page can still have a minted turn id if no tool hook bound
    it. The synchronous observation authorizes closing those claims too, while
    a newer prompt prevents this ending from touching that prompt's pages.
    """
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        observed = hook_turn(session_id)
        if not observed or observed["turn"] != turn_id or not observed["running"]:
            return
        ended = advance_hook_turn(session_id, turn_id, running=False)
    from .service import PageTransaction, owned_pages

    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page, flocked(lock):
                if hook_turn(session_id) != ended:
                    return
                page.close_turn(session_id)
        except FileNotFoundError:
            continue


def step_delivery_turn(session_id: str) -> str | None:
    """The observed provider turn a proven step hook can deliver into.

    Use the same dated activity reading as the page, so an interrupted or stale
    turn never holds the idle queue indefinitely. A page claimed during this turn
    may still have a local turn id: the next tool hook binds it to the observed
    provider turn. Route eligibility therefore requires a running claimant, not
    prior binding. Read outside the delivery lock: capture takes a page transaction
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
