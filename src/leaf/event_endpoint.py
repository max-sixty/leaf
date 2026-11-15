"""The browser's door onto the page event log.

Transport only: what a tab is allowed to send, how a retry is answered, and the
HTTP shape of an acceptance or a refusal. Which events the log takes, and what
they mean once it has them, is `event_contracts.append_admitted` — the one door
this endpoint shares with every other writer.
"""

from pathlib import Path

from .event_contracts import (
    EventRefused,
    append_admitted,
    browser_command_error,
)
from .event_log import AttemptConflict
from .findings import Finding
from .forks import kept_from_main_at_admission
from .harness import claim_harness
from .presence import nudge_unwatched
from .refusals import Refused
from .registry.contract import RegistryError
from .registry.kernel import kernel_event_kinds, kernel_event_ownership, kinds_declaring
from .service import PageTransaction, requires_agent_attention
from .thread_titles import name_admitted_thread

EventAnswer = tuple[int, dict]


def event_rejection(event: dict, refusal: Refused, status: int = 400) -> EventAnswer:
    """A final answer proving that this execution appended no event: the refusal's
    findings (`Refused.json`) under the words the browser shows its user."""
    body = {"ok": False, **refusal.json(), "error": refusal.user, "final": True}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return status, body


def event_fault(event: dict, error: str) -> EventAnswer:
    """An answer that withholds `final`: the fault may have landed either side of
    the append, so the next identical request finds the accepted event or executes
    the attempt again. The HTTP boundary writes it, as it writes every 500."""
    body = {"ok": False, "error": error}
    if event.get("attempt"):
        body["attempt"] = event["attempt"]
    return 500, body


def accept_event(page_dir: Path, event: dict) -> EventAnswer:
    """Validate and append one browser record. An acceptance names the event the log
    holds for it; the transport adds the state that shows it (`with_state`)."""
    return _receive_event(page_dir, event)


def with_state(answer: dict, state: dict, sent: dict) -> dict:
    """`answer` with the page's state, `state` whole and `sent` as the tab is sent it.

    The state is read after admission has released its transaction, and a refusal
    carries it too, which restores the tab from current truth, other tabs' updates
    included. An acceptance also says whether the event owes the agent an answer: its
    update stands among those the agent owes (`obligations.update_obligation`), which
    a reader such as leaf.page's Worker, starting the hosted agent's turn, takes from
    here rather than from the state, which may come as changes."""
    if answer["ok"]:
        answer = {
            **answer,
            "needs_reply": f"update:{answer['event']['id']}"
            in state["activity"]["obligations"],
        }
    return {**answer, "state": sent}


def _receive_event(page_dir: Path, event: dict) -> EventAnswer:
    # The shape check before the lease reads only the kernel's own records, which no
    # layer changes; admission inside the lease reads the page's vocabulary.
    contracts = kernel_event_kinds()
    browser_kinds = sorted(
        name for name, contract in contracts.items() if "browser" in contract
    )
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in browser_kinds:
        return event_rejection(
            event,
            EventRefused(
                Finding("unknown-kind", values={"kinds": browser_kinds}), event
            ),
        )
    # The server owns the record envelope and agent identity. Removing client
    # copies before validation prevents them from entering attempt identity too.
    for field in kernel_event_ownership()["browser_discard"]:
        event.pop(field, None)
    event["author"] = "page" if kind == "error" else "user"
    if error := browser_command_error(contracts[kind], event):
        return event_rejection(event, EventRefused(error, event))
    # A fault raises out of here, before or after the append, and the transport's
    # one fault boundary answers it with `event_fault`.
    return _execute_event(page_dir, event)


def _execute_event(
    page_dir: Path,
    event: dict,
) -> EventAnswer:
    """Admit and append as one log transaction, then release it before answering.

    `accept_event` checks the payload's declared shape before the page transaction. A
    `page init` can replace that declaration before this transaction is acquired, so the
    door reads the admitting vocabulary again inside the lease: that reading, not this
    endpoint's, is the one allowed to append beside the page's current vocabulary.

    Every decision whose validity depends on the log stays under the append lock
    through the write. In particular, two tabs cannot both validate an undo against
    the same gesture in force and append after either lock is gone.
    """
    spoken = None
    with PageTransaction(page_dir) as page:
        try:
            # A retry for an accepted attempt asks for its state; the door returns
            # that record unappended rather than repeating the gesture.
            admitted, appended = append_admitted(page, event)
        except AttemptConflict as error:
            return event_rejection(event, error, 409)
        except (EventRefused, RegistryError) as error:
            return event_rejection(event, error)
        if appended:
            claim = page.active_claim
            # Input that asks for the agent reaches it even when no watcher will,
            # unless a fork of its conversation is deciding on it, whose hand-over
            # nudges in its place (`forks`).
            if requires_agent_attention(admitted) and not kept_from_main_at_admission(
                page, admitted
            ):
                nudge_unwatched(page)
            if event["kind"] in kinds_declaring("message") and claim:
                spoken = admitted["id"], claim
    # A comment opens a thread with no name, and the claimant's harness names it from
    # its words while the agent is still reading them; a reply names a thread its
    # comment left untitled, as a reaction does. The request reads the thread under
    # the page's lock, so it starts once the lock is given back.
    if spoken and (generate := claim_harness(spoken[1]).title_generator()):
        name_admitted_thread(generate, page_dir, spoken[0], spoken[1]["id"])
    return 200, {"ok": True, "event": admitted}
