"""`leaf delivery ack`: the reader's confirmation that a whole delivery is in its
context, recorded through the transport that offered it.

The acknowledgement proves the consumer is running even if its prompt hook failed,
so it opens the session's turn (`state.open_session_turn`) before it records
anything. Where the session's input travels through a delivery record its hooks
offer from (`Harness.adapter`), a pointer is confirmed on that record, which keeps
the exact turn a hook offered it to (`codex.confirm_codex_pointer`); every other
delivery takes its page receipts directly (`delivery.receive`). Explicit
confirmation is strict: a transferred page or an ended turn refuses rather than
accepting a partial receipt. Hooks (`delivery.receive_held`) and Codex's provider
receipts (`delivery.receive_batch`) observe an already-open turn instead.
"""

from pathlib import Path

from leaf.agents.delivery import (
    acting_on_delivery,
    earlier_pickup,
    read_delivery,
    receive,
)
from leaf.base.findings import note
from leaf.base.harness import session_harness
from leaf.base.refusals import Refused
from leaf.base.state import open_session_turn


def receive_delivery(delivery_id: str) -> list[Path]:
    """Confirm a reader's complete input and record its entry into that turn."""
    payload = read_delivery(delivery_id)
    acting_on_delivery(payload)
    harness = session_harness()
    if harness:
        open_session_turn(harness.session)
        if payload["acknowledge"] is None and harness.adapter:
            # The Codex transport registers its App Server's exit handler as it
            # loads, so only a session whose input it carries loads it.
            from leaf.agents.codex import confirm_codex_pointer

            return confirm_codex_pointer(harness.session, payload)
    return receive(payload, harness.session if harness else None)


def cmd_delivery_ack(delivery_id: str) -> None:
    """Accept the reader's attestation that every part reached its context. A
    page the delivery names that has gone refuses it in the system's own words. A
    delivery an earlier turn already picked up is noted as a repeat
    (`delivery.earlier_pickup`)."""
    try:
        receive_delivery(delivery_id)
    except FileNotFoundError as error:
        raise Refused(str(error)) from error
    harness = session_harness()
    if harness and (
        repeat := earlier_pickup(read_delivery(delivery_id), harness.session)
    ):
        note(repeat)
