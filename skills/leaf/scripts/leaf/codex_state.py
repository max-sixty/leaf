"""Codex task observation and the paths that serialize delivery routing.

A synchronous hook records the provider turn before the task owns any page.
Tool hooks and carriers share this observation and its revision under the same
per-task delivery lock, so a late callback cannot replace a newer prompt or
close its pages. These readings import no delivery, page, or App Server code;
only ending a matching turn reaches the claims it must close.
"""

from pathlib import Path

from .event_log import flocked
from .files import read_json, write_json
from .leases import session_state_path
from .state_paths import HOOK_TURN_SUFFIX, session_file


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
