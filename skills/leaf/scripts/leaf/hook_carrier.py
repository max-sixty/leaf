"""The prompt and Stop hooks as a session's carrier, under Claude Code or Pi: they
carry the page input pending on the session's pages into its turn and enforce the
agent conversation loop. `hooks` reaches this module for active ownership or a
reconnect notice about a page the session previously served.

Claude Code runs the prompt hook as every turn begins, including a turn the end
of a background task opens, idle or between two tool calls, and adds what the
hook returns to that turn's context; what the Stop hook returns reaches the
model the same way, and continues the turn (`Harness.hook_context`). Leaf's Pi
extension calls both at the same points of a run. So these two hooks are the
session's carrier (`Harness.hook_delivers`): each freezes the input pending on
the session's pages and hands over its complete envelope inline, or its
immutable pointer.

The hook confirms an inline envelope itself, as it hands it over, so the user's
moves read Picked up without waiting on the model; the envelope's `acknowledge`
is null. Two things could keep inline context from reaching the turn, and the
hook rules out both before it confirms. A harness discards the output of a hook
it times out, so the hook confirms only by a deadline well inside its timeout
(`CONFIRM_WITHIN`): it goes inline only before it, confirms only after
publishing, and leaves pending any page whose lock is still held at the deadline.
Stopped before it confirms, it has confirmed nothing, and it never waits on a
lock past the deadline into the harness's timeout. Claude Code cuts context over a limit to a preview
(`HOOK_CONTEXT_LIMIT`), so a delivery that large goes as a pointer, and so does
one the hook was too slow to confirm; the agent's `leaf delivery read` of a
pointer is its receipt, as it is of the pointer Codex's tool hook offers. What remains is a turn that ends
just after it starts, as an interrupt can; its moves then read Picked up in a
turn that ended, as an App Server turn's do."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .activity import acknowledged_obligations, turn_obligations, unanswered
from .delivery import (
    batch_data,
    freeze_delivery,
    receive_held,
    record_pickup,
)
from .harness import Harness, claim_harness
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    PREVIEW_FILE,
)
from .served_state.page import full_state
from .service import (
    PageTransaction,
    owned_pages,
    unacknowledged,
)
from .state import flocked, session_lock_path, session_record


def restart(obligations: list[dict]) -> str:
    """What to do about owed moves a start covers that this turn did not write since
    their pickup, which hold the turn until it answers them or starts them again
    (`activity.turn_obligations`): named only for such moves, so a move nobody is at
    work on is never offered a start in place of its answer."""
    moves = list(
        dict.fromkeys(
            start["item"]
            for obligation in obligations
            for start in obligation["started_by"]
        )
    )
    if not moves:
        return ""
    return (
        f"; your start on {', '.join(moves)} is older than its pickup: answer once "
        "that work is done, or while it still runs start it again with "
        '`leaf task start <page> <id> "<what is still running>"`'
    )


@dataclass(frozen=True)
class PagePlan:
    """A session-owned page read once under its transaction.

    Selected input, response debt and carrier readiness come from one log,
    cursor, status and ownership snapshot. Planning never records a pickup.
    """

    page: Path
    claim: dict
    lifecycle: dict
    harness: Harness
    state: dict
    pending: list[dict]
    batch: dict | None
    owed: list[dict]
    acknowledged: list[dict]
    carried: bool
    preview: bool


def read_plans(session_id: str) -> list[PagePlan]:
    plans = []
    for page_dir in owned_pages(session_id):
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim is None or claim["id"] != session_id:
                    continue
                harness = claim_harness(claim)
                # The lifecycle is independently published. Its revision makes
                # a concurrent prompt/ending visible without holding a session
                # lock over a page projection or taking locks in reverse order.
                while True:
                    lifecycle = session_record(session_id)
                    state = full_state(page_dir, page.events)
                    claim = page.active_claim
                    if session_record(session_id) == lifecycle:
                        break
                if claim is None or claim["id"] != session_id:
                    continue
                pending = unacknowledged(page.events, state["cursor"])
                carried = harness.carrier_live(listening=state["listening"])
                plans.append(
                    PagePlan(
                        page_dir,
                        claim,
                        lifecycle,
                        harness,
                        state,
                        pending,
                        batch_data(page_dir, page, pending)
                        if pending and harness.hooks_carry()
                        else None,
                        turn_obligations(state, carried=carried),
                        acknowledged_obligations(state),
                        carried,
                        (page_dir / PREVIEW_FILE).exists(),
                    )
                )
        except FileNotFoundError:
            continue
    return plans


def stop_continues(plans: list[PagePlan], *, repeated: bool) -> bool:
    """Continue for newly owed input, or first-report debt/carrier housekeeping.

    Repeated Stop ignores already reported housekeeping and response debt, but
    genuinely new input still enters the current turn and owes an answer.
    """
    newly_owed = any(
        "answer" in event
        for plan in plans
        if plan.batch
        for event in plan.batch["events"]
    )
    needs_attention = any(
        plan.owed
        or (
            not plan.carried
            and (
                plan.pending
                or (plan.state["status"]["state"] != "idle" and not plan.preview)
            )
        )
        for plan in plans
    )
    return newly_owed or (needs_attention and not repeated)


def remedies(
    plans: list[PagePlan], handing: list[dict] = ()
) -> list[tuple[str, str | None]]:
    """Format remedies from already-read facts, with harness wording at the edge."""
    handed = {
        (batch["page"], event["id"]) for batch in handing for event in batch["events"]
    }
    reasons = []
    for plan in plans:
        if plan.owed:
            reasons.append(
                (
                    f"{plan.page}: {unanswered(plan.owed, 'acknowledged')}{restart(plan.owed)}.",
                    ANSWER_ASK_INSTRUCTION,
                )
            )
        if not plan.carried:
            pending = sum(
                (str(plan.page), event["id"]) not in handed for event in plan.pending
            )
            if pending:
                reasons.append(
                    (
                        f"{plan.page}: {pending} update{'s' if pending != 1 else ''} you haven't picked up. "
                        + plan.harness.input_unpicked(
                            plan.page, listening=plan.state["listening"]
                        ),
                        None,
                    )
                )
            elif plan.state["status"]["state"] != "idle" and not plan.preview:
                reasons.append(
                    (
                        f"{plan.page}: "
                        + plan.harness.nothing_listening(
                            plan.page, listening=plan.state["listening"]
                        ),
                        None,
                    )
                )
    return reasons


def unattended_pages(session_id: str) -> list[tuple[str, str | None]]:
    """Read and format the session's current debt, without state transitions."""
    return remedies(read_plans(session_id))


def pick_up_acknowledged(session_id: str, plans: list[PagePlan]) -> None:
    """Record a prompt's entry of already-receipted debt as a separate transition.

    A later receipt revalidates captured identities independently. This pickup
    likewise checks generation and turn after reacquiring the page transaction.
    """
    for plan in plans:
        if not plan.acknowledged:
            continue
        try:
            with (
                PageTransaction(plan.page) as page,
                flocked(session_lock_path(session_id)),
            ):
                if session_record(session_id) != plan.lifecycle:
                    continue
                claim = page.active_claim
                if not claim or (claim["id"], claim["generation"], claim["turn"]) != (
                    session_id,
                    plan.claim["generation"],
                    plan.claim["turn"],
                ):
                    continue
                current = full_state(plan.page, page.events)
                still_owed = {
                    item["input"] for item in acknowledged_obligations(current)
                }
                by_id = {event["id"]: event for event in page.events}
                record_pickup(
                    page,
                    [
                        by_id[item["input"]]
                        for item in plan.acknowledged
                        if item["input"] in by_id and item["input"] in still_owed
                    ],
                    phase="opened",
                    session=session_id,
                    turn=claim["turn"],
                )
        except FileNotFoundError:
            continue


# Claude Code writes a hook's context over this size to a file and hands the turn
# a 2 KB preview and the path instead: measured at 2.1.283 with ASCII, 9,990
# characters arrived whole and 10,010 did not. Which unit it counts is unmeasured,
# so the context is held to UTF-8 bytes, the strictest reading.
HOOK_CONTEXT_LIMIT = 10_000


# How long after it starts a hook may still hand a delivery over inline and wait
# for the locks that confirm it. Every registration of the prompt and Stop hooks
# allows 20 s (`hooks/hooks.json`, `hooks/pi.ts`), and the hook takes about 0.4 s.
# The other half covers what this clock does not see: uv's start and the
# interpreter's imports before it, and the receipt's writes and exit after it.
CONFIRM_WITHIN = 10.0


def render(
    delivery: dict | None, attention: list[str], *, inline: bool
) -> tuple[str, bool]:
    """The hook's context, and whether it hands `delivery` over inline, which
    confirms it: only where `inline` allows and the whole message fits under
    `HOOK_CONTEXT_LIMIT`. Otherwise it hands over the pointer its reader's
    `leaf delivery read` confirms."""
    if delivery is None:
        return "\n".join(attention), False
    message = "\n".join(
        [
            "Leaf has new input for your turn. Read this complete delivery before answering.",
            json.dumps(delivery, ensure_ascii=False),
            *attention,
        ]
    )
    if inline and len(message.encode("utf-8")) < HOOK_CONTEXT_LIMIT:
        return message, True
    return "\n".join(
        [
            (
                "Leaf has new input for this turn. Read it with "
                f"`leaf delivery read {delivery['id']}`, which confirms it."
            ),
            *attention,
        ]
    ), False


def carry_turn(
    harness: type[Harness],
    event: str | None,
    sid: str,
    payload: dict,
    expected: dict | None | object = ...,
    *,
    started: float,
    reconnect_harness: str | None = None,
) -> bool | None:
    """Compose this lifecycle's page input, obligations, and reconnect context
    into the one hook output its harness reads, and confirm the delivery it
    hands over inline by `CONFIRM_WITHIN` after `started`, the hook's
    `time.monotonic()` as it began."""
    expected = session_record(sid) if expected is ... else expected
    plans = read_plans(sid)
    if session_record(sid) != expected or any(
        plan.lifecycle != expected for plan in plans
    ):
        return
    if payload.get("turn_id") and any(
        plan.claim["turn"] != payload["turn_id"] for plan in plans
    ):
        return
    batches = (
        [plan.batch for plan in plans if plan.batch]
        if event in {"UserPromptSubmit", "Stop"}
        else []
    )
    if event == "UserPromptSubmit":
        pick_up_acknowledged(sid, plans)
    elif event == "Stop" and not stop_continues(
        plans, repeated=bool(payload.get("stop_hook_active"))
    ):
        return True
    reasons = remedies(plans, batches)
    # The message avoids "unattended": a page can be watched and still be owed
    # an answer, and the runtime spends that word on a different fact — a page
    # served to nobody at all.
    # Each page's own line, then one copy of each protocol they share. Three
    # pages owing the same thing used to carry three copies of the same
    # instruction into the turn, which is most of what the message weighed.
    protocols = list(dict.fromkeys(protocol for _, protocol in reasons if protocol))
    attention = (
        [
            "Leaf needs attention:",
            *(f"- {line}" for line, _ in reasons),
            *(f"\n{protocol}" for protocol in protocols),
        ]
        if reasons
        else []
    )
    delivery = freeze_delivery(batches, carrier="hook") if batches else None
    deadline = started + CONFIRM_WITHIN
    from .reconnect import publishing_notices

    with publishing_notices(reconnect_harness, sid, expected) as context:
        if context is None:
            return
        message, inline = render(
            delivery,
            [*context, *attention],
            inline=time.monotonic() < deadline,
        )
        if message:
            print(
                json.dumps(harness.hook_context(event, message)),
                flush=True,
            )
    if inline:
        receive_held(delivery, sid, deadline=deadline)
