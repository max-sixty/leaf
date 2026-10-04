"""The prompt and Stop hooks as a session's carrier, under Claude Code or Pi: they
carry the page input pending on the session's pages into its turn and enforce the
agent conversation loop. `hooks` reaches this module only for a session holding a
page.

Claude Code runs the prompt hook as every turn begins, including a turn the end
of a background task opens, idle or between two tool calls, and adds what the
hook returns to that turn's context; what the Stop hook returns reaches the
model the same way, and continues the turn (`Harness.hook_context`). Leaf's Pi
extension calls both at the same points of a run. So these two hooks are the
session's carrier
(`Harness.hook_delivers`): each freezes the input pending on the session's pages and hands over its complete
envelope or immutable pointer. The reader confirms receipt only once the whole
delivery is in context; hook completion and stdout publication prove no receipt.

Claude Code writes a hook's context over 10,000 characters to a file and hands
the turn a preview and its path, so a delivery that large goes as a pointer its
reader confirms once read. Every inline envelope requires the same confirmation."""

import json
from dataclasses import dataclass
from pathlib import Path

from .activity import acknowledged_obligations, turn_obligations, unanswered
from .delivery import (
    batch_data,
    freeze_delivery,
    record_pickup,
)
from .host import Harness, claim_harness
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


def reclaim(obligations: list[dict]) -> str:
    """What to do about owed moves a standing claim covers that this turn did not
    write since their pickup, which hold the turn until it answers them or claims
    them again (`activity.turn_obligations`): named only for such moves, so a move
    nobody is at work on is never offered a claim in place of its answer."""
    subjects = list(
        dict.fromkeys(
            obligation["subject"]["id"]
            for obligation in obligations
            if obligation["claimed_by"]
        )
    )
    if not subjects:
        return ""
    return (
        f"; the work claim on {', '.join(subjects)} is older than its pickup: "
        "answer once that work is done, or while it still runs claim it again with "
        '`leaf status <page> working "<what is still running>" --on <id>`'
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
    """Format remedies from already-read facts, with host wording at the edge."""
    handed = {
        (batch["page"], event["id"]) for batch in handing for event in batch["events"]
    }
    reasons = []
    for plan in plans:
        if plan.owed:
            reasons.append(
                (
                    f"{plan.page}: {unanswered(plan.owed, 'acknowledged')}{reclaim(plan.owed)}.",
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


def hook_acknowledgement(delivery_id: str) -> str:
    """Only the reader can prove a host hook's context reached its turn."""
    return (
        "Once this complete delivery is in your context, confirm it with "
        f"`leaf delivery ack {delivery_id}`. Until then, the user's moves read Sent."
    )


def compose(batches: list[dict], attention: list[str]) -> str:
    """Publish one reader-confirmed envelope inline, or its exact pointer.

    Hook completion cannot establish receipt: a host timeout discards stdout,
    and large context may be truncated. The model acknowledges only after the
    complete immutable delivery reached its context on either path.
    """
    if not batches:
        return "\n".join(attention)
    delivery = freeze_delivery(
        batches, carrier="hook", acknowledge=hook_acknowledgement
    )
    message = "\n".join(
        [
            "Leaf has new input for your turn. Read this complete delivery and take its acknowledge route before answering.",
            json.dumps(delivery, ensure_ascii=False),
            *attention,
        ]
    )
    if len(message.encode("utf-8")) < HOOK_CONTEXT_LIMIT:
        return message
    return "\n".join(
        [
            (
                "Leaf has new input for this turn, too large to hand over inline. "
                f"Read it with `leaf delivery read {delivery['id']}`, then confirm it as its `acknowledge` says."
            ),
            *attention,
        ]
    )


def carry_turn(
    event: str | None, sid: str, payload: dict, expected: dict | None | object = ...
) -> bool | None:
    """Answer a prompt, Stop, or other page-reading hook for a session holding a
    page: open or close its turn, hand over its pending input, and name what its
    pages are owed."""
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
    if not reasons and not batches:
        return
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
    # Publishing context proves no receipt. Its reader acknowledges the exact
    # envelope after the host accepted this output into its turn.
    message = compose(batches, attention)
    with flocked(session_lock_path(sid)):
        if session_record(sid) != expected:
            return
        print(
            json.dumps(type(plans[0].harness).hook_context(event, message)),
            flush=True,
        )
