"""Stop and prompt hooks that carry a Claude Code session's page input into its
turn and enforce the agent conversation loop, and the tool hook that tells a
Claude Code session how to close a turn a background wait outlives.

Claude Code runs the prompt hook as every turn begins, including a turn the end
of a background task opens, idle or between two tool calls, and adds what the
hook returns to that turn's context; the Stop hook's block reason reaches the
model the same way. So these two hooks are the session's carrier
(`Harness.hook_delivers`): each freezes the input pending on the session's
pages, confirms it, and hands over the whole envelope, and the `leaf wait` the
model keeps running only ends to open the turn. The model reads no output file
and runs no acknowledgement.

Each hook marks that it ran for its session (`leases.mark_hooks`), and a wait
only wakes a session so marked (`Harness.hooks_carry`): a session launched
without these hooks still gets the envelope printed, rather than waking to an
empty turn. Claude Code writes a hook's context over 10,000 characters to a file
and hands the turn a preview and its path, so a delivery that large goes as a
pointer its reader confirms instead of being confirmed unseen."""

import json

from .activity import acknowledged_obligations, blocking_obligations, unanswered
from .delivery import ReceiptRefused, freeze_delivery, record_pickup
from .event_log import read_events
from .files import next_reading, read_json
from .host import Harness, claim_harness
from .leases import hooks_path, mark_hooks, name_wait_start
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    PREVIEW_FILE,
    STATUS_FILE,
)
from .served_state.page import full_state
from .service import (
    PageTransaction,
    close_session_turn,
    open_session_turn,
    owned_pages,
    page_claim,
    unacknowledged,
)
from .session import pending_batches, receive_one


def unattended_pages(
    session_id: str, *, prompt_open: bool = False, handing: list[dict] = ()
) -> list[tuple[str, str | None]]:
    """The pages this session owes something, each with what to do about it.

    A `(line, protocol)` pair per debt. The line is this page's — its path, its
    count, the ids it names — and the protocol is the same words for every page
    that owes the same kind of thing, so the composer prints it once rather than
    once per page. `None` where the line is the whole remedy.

    Two invariants hold between turns. A page is watched or idle, so anything
    else has quietly stopped listening. And every comment delivered into this
    turn has an answer under it, where `activity.blocking_obligations` says which
    moves this turn owes.

    `handing` is the input this same hook hands the turn, which is neither
    unpicked nor owed yet: the reasons describe what is left beside it."""
    handed = {
        (batch["page"], event["id"]) for batch in handing for event in batch["events"]
    }
    reasons = []
    for page_dir in owned_pages(session_id):
        page_reasons = []
        try:
            events = read_events(page_dir)
            status = read_json(page_dir / STATUS_FILE)
            state = full_state(page_dir, events, stored_status=status)
        except FileNotFoundError:
            continue
        discovered = page_claim(page_dir)
        if discovered is None:
            # A failed `server start` rolls its claim back, and discovery may
            # have read it just before. An unclaimed page is not this session's
            # to answer for.
            continue
        # The claim states which harness took the page and how its input is
        # carried, so this reads the remedies and the watch question off that
        # declaration rather than naming a harness here.
        harness = claim_harness(discovered)
        listening = state["listening"]
        carried = harness.carrier_live(listening=listening)
        # Asked of every page, watched or not, and ahead of the watch question
        # below: a watcher cannot deliver a comment the cursor has already
        # passed, so a live wait is no answer to this one.
        stale = blocking_obligations(state, carried=carried)
        if stale:
            page_reasons.append(
                (
                    f"{page_dir}: {unanswered(stale, 'acknowledged')}.",
                    ANSWER_ASK_INSTRUCTION,
                )
            )
        # A live carrier is the watch, and it prints what's pending on its own.
        # Reporting the page here would start a second waiter and print the same
        # unacknowledged events twice.
        if not carried:
            # The watcher's whole batch — user events and workers' reports — not the
            # user-facing count, which deliberately leaves reports out.
            n = sum(
                (str(page_dir), event["id"]) not in handed
                for event in unacknowledged(events, state["cursor"])
            )
            if n:
                # The harness's own remedy names this page, so it stays on the
                # line; what follows it is the same for every page in the batch.
                # The delivery that carries them says how to acknowledge it.
                page_reasons.append(
                    (
                        f"{page_dir}: {n} update{'s' if n != 1 else ''} you haven't "
                        "picked up. "
                        + harness.input_unpicked(page_dir, listening=listening),
                        None,
                    )
                )
            # Nothing is owed and nothing is listening. That is a debt on a page
            # handed to a user, and a developer preview is not one: the same
            # `preview.json` the browser chrome reads to label it a preview says
            # the page is a rendering of a tracked example, put up to be looked
            # at. A session inspecting a dozen slots would otherwise carry a
            # dozen copies of this one line into every turn. The two clauses that
            # answer for a real user stay above it, so a gesture on a preview
            # still arrives — this exempts the housekeeping, not the user.
            #
            elif (
                state["status"]["state"] != "idle"
                and not (page_dir / PREVIEW_FILE).exists()
            ):
                page_reasons.append(
                    (
                        f"{page_dir}: "
                        + harness.nothing_listening(page_dir, listening=listening),
                        None,
                    )
                )
        # Discovery is only a candidate read. Transfer can happen while the
        # hook reads status, so decide against current ownership at the end.
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim and claim["id"] == session_id:
                    # A prompt opens every acknowledged move for its turn, the
                    # queued ones included: from here they block like the rest.
                    acknowledged = acknowledged_obligations(state)
                    if prompt_open and acknowledged:
                        by_id = {event["id"]: event for event in page.events}
                        record_pickup(
                            page,
                            [
                                by_id[obligation["input"]]
                                for obligation in acknowledged
                                if obligation["input"] in by_id
                            ],
                            phase="opened",
                            session=session_id,
                            turn=claim.get("turn"),
                        )
                    reasons.extend(page_reasons)
        except FileNotFoundError:
            continue
    return reasons


# How long a tool hook looks for a wait to start. The hook fires as soon as the host
# has spawned a background command, and a `leaf wait` takes its lease about 0.3s
# later warm, 2.5s after a plugin update leaves uv to sync first. While no wait runs,
# nothing but the clock says a command will start none, so one that starts none
# holds its result this long.
WAIT_START_S = 3

# Claude Code's session list reads a session's closing line, and a background wait
# holds the session at Working whatever that line says
# (`references/host-claude-code.md`, "Session list").
WAIT_STARTED = (
    "`leaf wait` is now watching your pages in the background. Claude Code's "
    "session list shows this session as Working while it runs, and groups it by "
    "the closing line of your reply. If this turn leaves anything only the user "
    "can give (an answer on the page, or a decision about other work), end your "
    "closing reply with a line `needs input: <what you want back>`. Only when "
    "nothing waits on the user or on work you still have running (this watcher "
    "aside), end it instead with a line `result: <what you delivered>`, which "
    "files the session under Completed. Keep either line to 200 characters or "
    "fewer, on its own line, not in a code block."
)


def announce_wait(session_id: str) -> bool:
    """Whether a wait has started for this session that no tool hook has named,
    naming it if so.

    The wait's own mark says so (`leases.name_wait_start`), not the command the
    hook follows. A wait already named settles it at once: a second wait is
    refused while one holds the lease. Otherwise the hook looks for
    `WAIT_START_S`, since the command it follows may be one still starting."""
    return (
        next_reading(lambda: name_wait_start(session_id), False, timeout=WAIT_START_S)
        is True
    )


# Claude Code writes a hook's context over this many characters to a file and
# hands the turn a 2 KB preview and the path instead: measured at 2.1.283, 9,990
# characters arrived whole and 10,010 did not.
HOOK_CONTEXT_LIMIT = 10_000


def pointer_acknowledgement(delivery_id: str) -> str:
    """What a delivery too large to hand over inline tells its reader."""
    return (
        "Leaf's hook handed this delivery over as a pointer, because it was too large "
        "for the turn's context; until it is confirmed, the user's moves read Sent. "
        "Once all of it is in your context, confirm it: "
        f"{Harness.run_ack(delivery_id)}: it confirms this delivery and waits for "
        "the next."
    )


def compose(batches: list[dict], attention: list[str]) -> tuple[str, dict | None]:
    """The turn context for one hook, and the delivery handing it over confirms.

    A delivery that fits goes in whole, and handing it over is receipt. One that
    would not fit goes as a pointer the model reads and confirms itself, since
    Claude Code would replace it with a preview and receipt would confirm what
    the model never saw."""
    if not batches:
        return "\n".join(attention), None
    delivery = freeze_delivery(batches, carrier="hook")
    message = "\n".join(
        [
            (
                "Leaf delivered this input into your turn and confirmed it, so the "
                "user's moves read Picked up."
            ),
            json.dumps(delivery, ensure_ascii=False),
            *attention,
        ]
    )
    if len(message) < HOOK_CONTEXT_LIMIT:
        return message, delivery
    pointer = freeze_delivery(
        batches, carrier="hook", acknowledge=pointer_acknowledgement
    )
    return "\n".join(
        [
            (
                "Leaf has new input for this turn, too large to hand over inline. "
                f"Read it with `leaf delivery read {pointer['id']}`, then confirm it "
                "as its `acknowledge` says."
            ),
            *attention,
        ]
    ), None


def cmd_hook(payload: dict) -> None:
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if sid:
        # Evidence that this host runs Leaf's hooks for the session, which is what
        # lets its `leaf wait` only wake it (`Harness.hooks_carry`).
        mark_hooks(sid)
    if event == "PostToolUse":
        # A foreground wait has returned before the hook runs, so only a
        # background command can leave one running past the turn.
        if payload["tool_input"].get("run_in_background") and announce_wait(sid):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": WAIT_STARTED,
                        }
                    }
                )
            )
        return
    if event == "SessionEnd":
        hooks_path(sid).unlink(missing_ok=True)
        for page_dir in owned_pages(sid):
            try:
                with PageTransaction(page_dir) as page:
                    claim = page.claim
                    # A successor that arrived after discovery remains current.
                    # SessionEnd releases only ownership provenance: status is
                    # authored work state, while service.json and the service
                    # reaper own process lifetime.
                    if claim and claim["released"] is None and claim["id"] == sid:
                        page.release_claim()
            except FileNotFoundError:
                continue
        return
    batches = []
    if event == "UserPromptSubmit":
        open_session_turn(sid)
        batches = pending_batches(sid)
        reasons = unattended_pages(sid, prompt_open=True, handing=batches)
    elif event == "Stop":
        # Input that arrived as the turn ends goes into this same turn. A repeated
        # Stop takes only the user's: a worker's reports or a page's own errors,
        # which nobody paces, could otherwise hold a turn open without end, and
        # the next turn takes them.
        batches = pending_batches(sid)
        if payload.get("stop_hook_active") and not any(
            move["author"] == "user" for batch in batches for move in batch["events"]
        ):
            batches = []
        reasons = unattended_pages(sid, handing=batches)
        # A first Stop blocked on outstanding Leaf work does not end the
        # turn: Claude continues in the same turn with this reason as new
        # context. Stamp only a turn the hook allows to end (cleanly or on
        # the repeated stop that deliberately fails open).
        if not batches and (not reasons or payload.get("stop_hook_active")):
            close_session_turn(sid)
        # A repeated ordinary debt is the same Stop hook asking again; new
        # input is not.
        if payload.get("stop_hook_active") and not batches:
            return
    else:
        reasons = unattended_pages(sid)
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
    # The whole context is composed before anything is confirmed, and confirmed
    # just before it is printed, so a hook that fails on the way confirms
    # nothing. A page whose receipt is refused keeps its batch pending for the
    # next hook, which a page and sequence already handled treats as a retry.
    message, confirmed = compose(batches, attention)
    if confirmed:
        for batch in confirmed["batches"]:
            try:
                receive_one(batch, sid)
            except ReceiptRefused:
                continue
        open_session_turn(sid)
    if event == "Stop":
        print(json.dumps({"decision": "block", "reason": message}))
    else:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": message,
                    }
                }
            )
        )
