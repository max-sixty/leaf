"""The prompt and Stop hooks as a session's transport and response reminder.

Claude Code and Pi carry pending page input here; Codex reserves its new-input
pointers through `codex`. All three use this module's continuation policy and
reminders for already-receipted work. A reminder names the immutable deliveries
whose receipt references the current owner can use. Only owed inputs with no usable
reference are captured again, as when another session takes the page. A reminder
does not make those inputs pending again or reserve another Codex transport offer.
A Stop hook continues the turn for each owed answer this turn has not started
(`activity.turn_obligations`), and for a
page whose watcher is not running while it has input pending or is not idle
(`stop_continues`). A repeated Stop (`stop_hook_active`) continues the turn only for
a newly delivered update that owes an answer.

`hooks` reaches this module for active ownership or a reconnect notice about a
page the session previously served.

Claude Code runs the prompt hook as every turn begins, including a turn the end
of a background task opens, idle or between two tool calls, and adds what the
hook returns to that turn's context; what the Stop hook returns reaches the
model the same way, and continues the turn (`Harness.hook_context`). Leaf's Pi
extension calls the prompt hook as accepted incoming messages are finalized or
at live turn ends, and Stop before settling. It commits their context to the
persisted session. These two hooks are the
session's transport (`Harness.hook_delivers`): each freezes the input pending on
the session's pages and hands over its complete envelope inline, or its
immutable pointer.

The hook confirms an envelope it hands over inline itself, so the user's updates
read Picked up without waiting on the model; the envelope's `acknowledge` is null,
and its reader confirms nothing. So it hands an envelope over inline only once it
has confirmed every batch: an inline envelope it could not confirm would leave its
input pending, and every later hook and watch would offer it again as new. A
batch's receipt can still be refused, as when the page changed hands after the plan
read it, so whatever the hook could not confirm goes as a pointer, whose reader's
explicit `leaf delivery ack` either confirms it or shows the refusal. A page vendored
at another protocol, whose log this Leaf may not write
(`event_contracts.write_refusal`), is re-vendored before it is read
(`vendoring.renew_layer`), and the turn's attention carries what the re-vendor left
for the agent: why it was refused, or the checks index.html now fails. One it could
not re-vendor offers no new input at all (`delivery.deliverable`): the hook records
no pickup there and names the refusal, so it never fails on a page it cannot write,
nor offers input it could never confirm.
Claude Code cuts context over a limit to a preview (`HOOK_CONTEXT_LIMIT`), so a
delivery that large goes as a pointer too, unconfirmed, as do pointers Codex's tool
hook offers.

A harness reads a hook's output only once it exits, and discards it for a hook it
times out, so the hook confirms only by a deadline well inside its timeout
(`CONFIRM_WITHIN`) and prints once confirmation is settled. Stopped before it
confirms, it has confirmed nothing; it never waits on a lock past the deadline
into the harness's timeout, and a page whose lock is still held then goes
unconfirmed. What remains is a turn that ends just after it starts, as an
interrupt can; its updates then read Picked up in a turn that ended, as an App
Server turn's do.

Confirmed input can still miss the context, as when Leaf's Claude Code hooks module
calls this hook for a wake and finds its session ended before it appends the
result (`hooks/claude-code.ts`). It is not offered again as new: an update that
owes an answer stays owed on the page, and the next prompt or first Stop hook of
whichever session owns the page names its original pointer, or captures a recovery
reading if that owner has no usable reference (`PagePlan.recovery`), while one that
owes none is lost. Confirming
only once the module has appended was rejected: a confirmation refused or never
run after the append would leave input the turn already holds pending, and every
later hook would offer it again as new."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .activity import acknowledged_obligations, turn_obligations, unanswered
from .delivery import (
    batch_data,
    deliverable,
    delivery_pointer_prompt,
    freeze_delivery,
    reads_reference,
    receive_held,
    record_pickup,
)
from .event_contracts import write_refusal
from .findings import Finding
from .harness import Harness, claim_harness
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    PREVIEW_FILE,
)
from .served_state.context import read_page
from .service import (
    PageTransaction,
    owned_pages,
    page_claim,
)
from .state import flocked, session_lock_path, session_record


def restart(obligations: list[dict]) -> str:
    """What to do about owed updates a start covers that this turn did not write since
    their pickup, which hold the turn until it answers them or starts them again
    (`activity.turn_obligations`): named only for such updates, so an update nobody is at
    work on is never offered a start in place of its answer."""
    items = list(
        dict.fromkeys(
            start["item"]
            for obligation in obligations
            for start in obligation["started_by"]
        )
    )
    if not items:
        return ""
    return (
        f"; your start on {', '.join(items)} came before this turn, or before a "
        "newer update in its thread was picked up. Answer once that work is done, "
        "or, while it still runs, start it again in this turn with "
        '`leaf task start <page> <id> "<what is still running>"`'
    )


@dataclass(frozen=True)
class PagePlan:
    """A session-owned page read once under its transaction.

    Pending and recovery batches, response debt and watcher readiness come from
    one log, cursor, status and ownership snapshot. Planning never records a
    pickup. The caller selects which pending batches its transport can hand over.
    `unwritable` says why this Leaf may record no pickup there, or is None
    (`event_contracts.write_refusal`). `unready` is what re-vendoring the page
    before the reading left for the agent, or None (`vendoring.renew_layer`).
    """

    page: Path
    claim: dict
    lifecycle: dict
    harness: Harness
    state: dict
    pending: list[dict]
    batch: dict | None
    recovery: dict | None
    owed: list[dict]
    acknowledged: list[dict]
    watched: bool
    preview: bool
    unwritable: Finding | None
    unready: Finding | None


def read_plans(session_id: str) -> list[PagePlan]:
    from .vendoring import renew_layer

    plans = []
    for page_dir in owned_pages(session_id):
        # The claim's harness, since a hook's environment does not name its
        # session, and only while the claim is still this session's.
        held = page_claim(page_dir)
        unready = (
            renew_layer(page_dir, claim_harness(held))
            if held and held["id"] == session_id
            else None
        )
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
                    work = read_page(page_dir, page.events).work
                    state = {**work.presence, "activity": work.activity}
                    claim = page.active_claim
                    if session_record(session_id) == lifecycle:
                        break
                if claim is None or claim["id"] != session_id:
                    continue
                pending = deliverable(page)
                watched = harness.watcher_live(listening=state["listening"])
                # A reference into a delivery an earlier Leaf wrote is no use to
                # this one, which cannot read it, so its update is captured again.
                owed = [
                    {
                        **item,
                        "answer": {
                            key: value
                            for key, value in item["answer"].items()
                            if key != "ref"
                        },
                    }
                    if "ref" in item["answer"]
                    and not reads_reference(item["answer"]["ref"])
                    else item
                    for item in turn_obligations(state, watched=watched)
                ]
                recovery_ids = {
                    item["input"] for item in owed if "ref" not in item["answer"]
                }
                responses = {item["input"]: item["answer"] for item in work.obligations}
                plans.append(
                    PagePlan(
                        page_dir,
                        claim,
                        lifecycle,
                        harness,
                        state,
                        pending,
                        batch_data(page_dir, page, pending, responses=responses)
                        if pending
                        else None,
                        batch_data(
                            page_dir,
                            page,
                            [
                                event
                                for event in page.events
                                if event["id"] in recovery_ids
                            ],
                            responses=responses,
                        )
                        if recovery_ids
                        else None,
                        owed,
                        acknowledged_obligations(state),
                        watched,
                        (page_dir / PREVIEW_FILE).exists(),
                        write_refusal(page_dir),
                        unready,
                    )
                )
        except FileNotFoundError:
            continue
    return plans


def stop_continues(
    plans: list[PagePlan], handing: list[dict], *, repeated: bool
) -> bool:
    """Continue for newly owed input, or first-report debt/watcher housekeeping.

    Repeated Stop ignores already reported housekeeping and response debt, but
    genuinely new input still enters the current turn and owes an answer.
    `handing` contains the complete pending batches this transport proposes to
    offer; acknowledged recovery snapshots never count as new input.
    """
    newly_owed = any(
        "answer" in event for batch in handing for event in batch["events"]
    )
    needs_attention = any(
        plan.owed
        or plan.unready
        or (
            not plan.watched
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
        if plan.unready or plan.unwritable:
            reasons.append((str(plan.unready or plan.unwritable), None))
        if plan.owed:
            reasons.append(
                (
                    f"{plan.page}: {unanswered(plan.owed, plan.page, 'acknowledged')}{restart(plan.owed)}.",
                    ANSWER_ASK_INSTRUCTION,
                )
            )
        if not plan.watched:
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


def pick_up_acknowledged(session_id: str, plans: list[PagePlan]) -> None:
    """Record a prompt's entry of already-receipted debt as a separate transition.

    A later receipt revalidates captured identities independently. This pickup
    likewise checks generation and turn after reacquiring the page transaction.
    A page this Leaf may not write records none; `remedies` tells the turn why.
    """
    for plan in plans:
        if not plan.acknowledged or plan.unwritable:
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
                work = read_page(plan.page, page.events).work
                current = {**work.presence, "activity": work.activity}
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


# The words that open a delivery's context, inline or by pointer: prose for the
# model alone. What reads a hook's output for its delivery reads `DELIVERY_FIELD`.
# TODO: without the hooks module, Claude Code prints a Stop hook's inline delivery
# in full in the terminal. Hiding it there means handing over a pointer, which
# needs a record of offered, unread deliveries that a repeated Stop and the watch
# both respect; otherwise each re-offers it as new. Moot once the module is Claude
# Code's only watcher and transport.
INLINE_OPENING = (
    "Leaf has new input for your turn. Read this complete delivery before answering."
)
POINTED_OPENING = "Leaf has new input for this turn. Read it with"

# The hook output's field naming the delivery its context hands the turn: its
# `id`, and whether it went `inline` or as a pointer. Claude Code leaves a field
# it does not know out of what it hands the model and a hooks module, and keeps
# the hook's whole stdout in a trace's `hook_response` (measured at 2.1.296). So
# the field reaches Leaf's hooks module, which runs the Stop hook itself to read
# it (`hooks/claude-code.ts`), and an eval's reading of a trace
# (`leaf_dev.arms.hook_delivered`).
DELIVERY_FIELD = "leaf_delivery"


def render(
    harness: Harness,
    event: str | None,
    delivery: dict | None,
    attention: list[str],
    *,
    confirm: Callable[[], bool],
) -> dict | None:
    """The hook's output, or None where it puts nothing in the turn. It hands
    `delivery` over inline only where the whole message fits under
    `HOOK_CONTEXT_LIMIT` and `confirm` then confirms every batch; otherwise it hands
    over the pointer its reader's `leaf delivery ack` confirms after complete
    reading. Either way `DELIVERY_FIELD` names what it handed over."""
    if delivery is None:
        return harness.hook_context(event, "\n".join(attention)) if attention else None
    message = "\n".join(
        [INLINE_OPENING, json.dumps(delivery, ensure_ascii=False), *attention]
    )
    inline = len(message.encode("utf-8")) < HOOK_CONTEXT_LIMIT and confirm()
    if not inline:
        message = "\n".join(
            [
                (
                    f"{POINTED_OPENING} `leaf delivery read {delivery['id']}` "
                    "and follow its receipt instruction."
                ),
                *attention,
            ]
        )
    return {
        **harness.hook_context(event, message),
        DELIVERY_FIELD: {"id": delivery["id"], "inline": inline},
    }


def carry_turn(
    harness: Harness,
    event: str | None,
    sid: str,
    payload: dict,
    expected: dict | None | object = ...,
    *,
    started: float,
    reconnect_harness: str | None = None,
) -> bool | None:
    """Compose this lifecycle's page input, obligations, and reconnect context
    into the one hook output its harness reads, confirming a delivery it hands
    over inline by `CONFIRM_WITHIN` after `started`, the hook's
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
        [plan.batch for plan in plans if plan.batch and plan.harness.hooks_carry()]
        if event in {"UserPromptSubmit", "Stop"}
        else []
    )
    if event == "UserPromptSubmit":
        pick_up_acknowledged(sid, plans)
    elif event == "Stop" and not stop_continues(
        plans, batches, repeated=bool(payload.get("stop_hook_active"))
    ):
        return True
    reasons = remedies(plans, batches)
    # The message avoids "unattended": a page can be watched and still be owed
    # an answer, and the runtime spends that word on a different fact — a page
    # served to nobody at all.
    # Each page's own line, then one copy of each protocol they share, so pages
    # owing the same thing carry one copy of its instruction into the turn.
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
    reminders = list(
        dict.fromkeys(
            item["answer"]["ref"].partition(":")[0]
            for plan in plans
            for item in plan.owed
            if "ref" in item["answer"]
        )
    )
    recovery = [plan.recovery for plan in plans if plan.recovery]
    if recovery:
        # The cursor already passed these inputs, but their receipts gave this
        # owner no usable refs. Recovery advances no cursor or transport offer.
        reminders.append(freeze_delivery(recovery)["id"])
    if reminders:
        attention.extend(
            [
                "Read these unanswered updates and their exact answer references:",
                *(delivery_pointer_prompt(identity) for identity in reminders),
            ]
        )
    delivery = freeze_delivery(batches) if batches else None
    deadline = started + CONFIRM_WITHIN
    from .reconnect import publishing_notices

    with publishing_notices(reconnect_harness, sid, expected) as context:
        if context is None:
            return
    # Receipt takes the page and session locks the notices hold, so it follows them,
    # and confirms only into the lifecycle they were read under.
    output = render(
        harness,
        event,
        delivery,
        [*context, *attention],
        confirm=lambda: (
            time.monotonic() < deadline
            and receive_held(delivery, sid, expected, deadline=deadline)
        ),
    )
    if output:
        print(json.dumps(output), flush=True)
