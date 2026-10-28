"""The prompt, tool-boundary and Stop hooks' output for a session that owns pages.

`carry_turn` builds what the prompt hook (`UserPromptSubmit`), Claude Code's
`PostToolBatch`, and Stop add to a turn. On Claude Code and Pi these hooks carry
the user's updates to the agent (`Harness.hook_delivers`): `carry_turn` freezes
the input pending on the session's pages into a delivery and hands it over inline
or as a pointer. Codex offers its
pointers through `codex.offer_hook_delivery` instead, but uses this module's Stop
rule and reminders. `hooks` calls in here for pages the session owns and for a
reconnect notice about a page it served before.

Claude Code runs the prompt hook as every turn begins, including a turn opened by a
background task's end, and adds its output to the turn's context; the Stop hook's
output continues the turn (`Harness.hook_context`). Leaf's Pi extension
(`hooks/pi.ts`) calls both hooks and commits their output to the session.

The Stop hook continues the turn for a page with no running watcher that has
input pending or a status other than idle, and for each owed answer the turn has
not started (`activity.turn_obligations`) where no watch follows the turn
(`stop_continues`). A repeated Stop (`stop_hook_active`) continues only for a
newly delivered update that owes an answer. Where a watch follows the turn, the
turn ends on the answer it wrote rather than on one more message about the owed
update, which Claude Code's focus view would show in its place; the watch wakes a
turn of its own whose prompt hook names the update, once per delivery of it
(`session.left_owed`).

Where something that outlives the turn opens a turn of its own for the input
(`Harness.later_turn_takes_input`), Stop hands no input over: a watch wakes once
the turn closes and opens a turn whose prompt hook does, and Codex's App Server
adapter starts one. Continuing the turn for the input would have the agent write one
more message, and a harness that shows each turn's final message alone, as Claude
Code's focus view does, would show that reply in place of the answer the turn had
written. Under plain `--print`, or a Codex task that waits with `leaf wait`, nothing
opens that turn, so Stop hands the input into the turn it continues. Codex's queue
adapter would open one on a pointer Codex shows as the user's own message, which is
noisier than the extra message, so Stop hands the input in there too.

For an update already picked up and still owed an answer, the hook reminds the
agent by naming the delivery that holds its answer reference. An update the page's
current owner holds no usable reference for, as when another session received it
before the page changed hands, is deliverable again (`delivery.deliverable`), so
it is input rather than a reminder: the hook hands it over with the owner's other
input, or leaves it to the later turn that takes them.

The hook records an inline delivery as opened in the turn itself (`receive_held`),
so the updates read Delivered without waiting for the model, and the envelope's
`acknowledge` is null. It hands inline only the batches it recorded: an inline
batch left unrecorded would stay pending, and every later hook would offer it again
as new. A batch can still be refused, as when the page changed hands after
`read_plans` read it, and its input stays pending for whoever holds the page. A
delivery whose context the harness wouldn't show the model whole goes as a pointer
(`Harness.fits_hook_context`), as does one the hook recorded none of; the agent's
`leaf delivery ack` confirms it. A pointer never follows a recorded batch, whose
opened pickup would read as handed into the turn, and under Pi as received, though
the model read none of it.

A pointer's input stays unconfirmed until its reader runs `leaf delivery ack`, so a
later tool boundary of the same turn would freeze it again and point at it under a
new id, and the model would read the same input two or more times. A tool boundary
carries only new input, so the hook notes each page it points at since the turn
last opened (`POINTED`), and a later boundary hands nothing from that page until
the pointer's input is confirmed; the page's later input follows at the boundary
after the ack. Stop and a prompt that opens the turn again hand unconfirmed input
over again, as they do input Escape dropped.

Pi has the context once the hook returns, so its hook records the receipt with the
pickup. Claude Code reads it only once every hook of the event has exited, and
Escape before then drops a prompt with its context, though not a tool boundary's.
So a Claude Code hook leaves the receipt to the transcript's record of the model's
context, which every later hook reads first (`delivery.confirm_entered`). Until
then the handed input is not offered again. Once its turn reads ended, it may not
have reached the model, so it is input again (`delivery.deliverable`): Claude Code
submits a wake Escape interrupted again at once as a new prompt, and the watch
its turn's prompt started wakes for it (`hooks.cmd_watch`), or where none runs, as
after the turn that first claimed the page, the page's server nudges the session
(`presence.nudge_interrupted`). The hook of the prompt that opens confirms what the
transcript shows before it reads the page, so it hands over again only what never
reached the model, and names an update the model did read and left unanswered as
owed.

A page at an older protocol is taken to this Leaf's before it is read
(`vendoring.renew_layer`), and the turn is told why that failed or which checks
index.html now fails. A page this Leaf cannot write, because its renewal failed
or a newer Leaf initialized it, offers no input (`delivery.deliverable`), so the hook
names the refusal and records no pickup there.

A harness reads a hook's output only after the hook exits, and discards it if the
hook times out. So the hook records its handover only before `CONFIRM_WITHIN`, well
inside its timeout, and prints afterwards. It never waits for a lock past that
deadline, and a page whose lock is still held goes as a pointer. App Server turns
interrupted just after they start leave their updates Delivered.
"""

import json
import time
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
    ANSWER_INSTRUCTION,
    PREVIEW_FILE,
)
from .served_state.context import read_page
from .service import (
    PageTransaction,
    owned_pages,
    page_claim,
)
from .state import (
    STRING,
    Record,
    described,
    flocked,
    object_schema,
    session_file,
    session_lock_path,
    session_record,
)


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
        f"; your start on {', '.join(items)} predates this turn or the pickup of "
        "a newer update in its thread. Answer once that work is done, or, while it runs, start it "
        'again with `leaf task start <page> <id> --text "<what is still running>"`'
    )


@dataclass(frozen=True)
class PagePlan:
    """A session-owned page read once under its transaction.

    The deliverable batch, response debt and watcher readiness come from one log,
    cursor, status and ownership snapshot. Planning never records a pickup. The
    caller selects which pending batches its transport can hand over.
    `unwritable` says why this Leaf may record no pickup there, or is None
    (`event_contracts.write_refusal`). `unready` is what renewing the page's layer
    before the reading left for the agent, or None (`vendoring.renew_layer`).
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
                pending = deliverable(page, work.obligations)
                watched = harness.watcher_live(listening=state["listening"])
                # An owed update this owner holds no usable reference for, as when
                # another session received it before the page changed hands, is
                # deliverable again (`delivery.unreferenced`): input the hook hands
                # over or leaves to a later turn, not a debt to name. A reference
                # into a delivery an earlier Leaf wrote is no use to this one, which
                # cannot read it.
                redelivered = {event["id"] for event in pending}
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
                    if item["input"] not in redelivered
                ]
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
    plans: list[PagePlan], handing: list[dict], *, repeated: bool, reminds: bool
) -> bool:
    """Continue for newly owed input, or first-report debt/watcher housekeeping.

    Repeated Stop ignores already reported housekeeping and response debt, but
    genuinely new input still enters the current turn and owes an answer.
    `handing` contains the complete pending batches this transport proposes to
    offer. Where a watch follows the turn (`reminds`), response debt ends the turn
    on its answer, and the watch wakes a turn of its own for the reminder
    (`session.left_owed`).
    """
    newly_owed = any(
        "answer" in event for batch in handing for event in batch["events"]
    )
    needs_attention = any(
        (plan.owed and not reminds)
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
        # An owed update this output hands over is answered from that delivery.
        owed = [
            item for item in plan.owed if (str(plan.page), item["input"]) not in handed
        ]
        if owed:
            reasons.append(
                (
                    f"{plan.page}: {unanswered(owed, plan.page, 'acknowledged')}{restart(owed)}.",
                    ANSWER_INSTRUCTION,
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


# The time every harness gives the prompt and Stop hooks: each registration's
# `timeout` (`hooks/hooks.json`, `hooks/codex.json`) and Pi extension's bound
# (`hooks/pi.ts`), which `test_hook_registration` holds to this.
HOOK_TIMEOUT_S = 20

# How long after it starts a hook may still hand a delivery over inline and wait
# for the locks that record it; the hook itself takes about 0.4 s. The other half
# of its timeout covers what this clock does not see: uv's start and the
# interpreter's imports before it, and the receipt's writes and exit after it.
CONFIRM_WITHIN = HOOK_TIMEOUT_S / 2


# The words that open a delivery's context inline.
INLINE_OPENING = (
    "Leaf has new input for your turn. Read this complete delivery before answering."
)
# The words that open what a turn owes, as a reminder of its own or after a delivery.
ATTENTION_OPENING = "Leaf needs attention:"

POINTED = Record(
    "pointed",
    described(
        "The pages whose input a hook handed a session's turn by pointer, in the "
        "state home's `sessions/<digest>.pointed` (`state.session_file`).",
        object_schema(
            {
                "turn": described("The turn the pointers were handed to.", STRING),
                "opened": described(
                    "When that turn last opened (`turn_opened`): a prompt that "
                    "opens it again hands the input over anew.",
                    STRING,
                ),
                "pages": described(
                    "Each page directory, with the last log position pointed at.",
                    {"type": "object", "additionalProperties": {"type": "integer"}},
                ),
            }
        ),
    ),
    since=24,
)


def pointed(session_id: str, lifecycle: dict) -> dict[str, int]:
    """The pages a hook pointed at since `lifecycle`'s turn last opened, each with
    the last log position it pointed at."""
    record = POINTED.read(session_file(session_id, POINTED.kind))
    if record is None or (record["turn"], record["opened"]) != (
        lifecycle["turn"],
        lifecycle["turn_opened"],
    ):
        return {}
    return dict(record["pages"])


def note_pointer(
    session_id: str, lifecycle: dict, delivery: dict, *, deadline: float
) -> None:
    """Note each page `delivery` carries input from as pointed at in the turn
    `lifecycle` names, unless a newer lifecycle has replaced it. A session lock
    still held at `deadline` leaves the note unwritten, since a hook that waited
    on it could outlive its timeout and lose the pointer itself."""
    try:
        with flocked(session_lock_path(session_id), deadline=deadline):
            if session_record(session_id) != lifecycle:
                return
            pages = pointed(session_id, lifecycle)
            for batch in delivery["batches"]:
                pages[batch["page"]] = batch["through_seq"]
            POINTED.write(
                session_file(session_id, POINTED.kind),
                {
                    "turn": lifecycle["turn"],
                    "opened": lifecycle["turn_opened"],
                    "pages": pages,
                },
            )
    except TimeoutError:
        return


def carry_turn(
    harness: Harness,
    event: str | None,
    sid: str,
    payload: dict,
    expected: dict | None,
    *,
    started: float,
    reconnect_harness: str | None = None,
) -> bool | None:
    """Compose this lifecycle's page input, obligations, and reconnect context
    into the one hook output its harness reads, recording a delivery it hands
    over inline by `CONFIRM_WITHIN` after `started`, the hook's
    `time.monotonic()` as it began."""
    plans = read_plans(sid)
    if session_record(sid) != expected or any(
        plan.lifecycle != expected for plan in plans
    ):
        return
    if payload.get("turn_id") and any(
        plan.claim["turn"] != payload["turn_id"] for plan in plans
    ):
        return
    carries = event in {"UserPromptSubmit", "PostToolBatch"} or (
        event == "Stop" and not harness.later_turn_takes_input()
    )
    through = pointed(sid, expected) if event == "PostToolBatch" and expected else {}
    batches = (
        [
            plan.batch
            for plan in plans
            if plan.batch
            and plan.harness.hooks_carry()
            and not any(
                item["seq"] <= through.get(str(plan.page), 0) for item in plan.pending
            )
        ]
        if carries
        else []
    )
    if event == "PostToolBatch" and not batches:
        return
    if event == "UserPromptSubmit":
        pick_up_acknowledged(sid, plans)
    elif event == "Stop" and not stop_continues(
        plans,
        batches,
        repeated=bool(payload.get("stop_hook_active")),
        reminds=harness.watches_between_turns(),
    ):
        return True
    # A tool boundary carries only new input; response-debt and housekeeping
    # reminders belong to prompt and Stop. It neither reopens nor ends a turn.
    reminding = [] if event == "PostToolBatch" else plans
    reasons = remedies(reminding, batches)
    # The message avoids "unattended": a page can be watched and still be owed
    # an answer, and the runtime spends that word on a different fact — a page
    # served to nobody at all.
    # Each page's own line, then one copy of each protocol they share, so pages
    # owing the same thing carry one copy of its instruction into the turn.
    protocols = list(dict.fromkeys(protocol for _, protocol in reasons if protocol))
    attention = (
        [
            ATTENTION_OPENING,
            *(f"- {line}" for line, _ in reasons),
            *(f"\n{protocol}" for protocol in protocols),
        ]
        if reasons
        else []
    )
    reminders = list(
        dict.fromkeys(
            item["answer"]["ref"].partition(":")[0]
            for plan in reminding
            for item in plan.owed
            if "ref" in item["answer"]
        )
    )
    if reminders:
        attention.extend(
            [
                "Read these unanswered updates and their exact answer references:",
                *(delivery_pointer_prompt(identity) for identity in reminders),
            ]
        )
    delivery = freeze_delivery(batches) if batches else None
    deadline = started + CONFIRM_WITHIN
    from .reconnect import notices

    context = notices(reconnect_harness, sid, expected)
    if context is None:
        return
    attention = [*context, *attention]
    if delivery is None:
        message = "\n".join(attention)
    else:

        def inline(batches: list[dict]) -> str:
            return "\n".join(
                [
                    INLINE_OPENING,
                    json.dumps({**delivery, "batches": batches}, ensure_ascii=False),
                    *attention,
                ]
            )

        # Record only input the model will see whole, while the hook can still
        # exit before its timeout. A refused batch stays pending.
        recorded = (
            receive_held(
                delivery,
                sid,
                expected,
                deadline=deadline,
                confirm=harness.commits_hook_context,
            )
            if harness.fits_hook_context(inline(delivery["batches"]))
            and time.monotonic() < deadline
            else []
        )
        if recorded:
            message = inline(recorded)
        else:
            if expected:
                note_pointer(sid, expected, delivery, deadline=deadline)
            message = "\n".join([delivery_pointer_prompt(delivery["id"]), *attention])
    if message:
        print(json.dumps(harness.hook_context(event, message)), flush=True)
