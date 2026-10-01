"""The prompt and Stop hooks as a Claude Code session's carrier: they carry the
page input pending on the session's pages into its turn and enforce the agent
conversation loop. `hooks` reaches this module only for a session holding a page.

Claude Code runs the prompt hook as every turn begins, including a turn the end
of a background task opens, idle or between two tool calls, and adds what the
hook returns to that turn's context; what the Stop hook returns reaches the
model the same way, and continues the turn (`Harness.continue_turn`). So these
two hooks are the session's carrier
(`Harness.hook_delivers`): each freezes the input pending on the session's
pages, confirms it, and hands over the whole envelope, and the `leaf wait` the
model keeps running only ends to open the turn. The model reads no output file
and runs no acknowledgement.

Claude Code writes a hook's context over 10,000 characters to a file and hands
the turn a preview and its path, so a delivery that large goes as a pointer its
reader confirms instead of being confirmed unseen."""

import json

from .activity import acknowledged_obligations, turn_obligations, unanswered
from .delivery import (
    ReceiptRefused,
    freeze_delivery,
    pending_batches,
    receive_one,
    record_pickup,
)
from .event_log import read_events
from .host import Harness, claim_harness
from .schema import (
    ANSWER_ASK_INSTRUCTION,
    PREVIEW_FILE,
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


def unattended_pages(
    session_id: str, *, prompt_open: bool = False, handing: list[dict] = ()
) -> list[tuple[str, str | None]]:
    """The pages this session owes something, each with what to do about it.

    A `(line, protocol)` pair per debt. The line is this page's — its path, its
    count, the ids it names — and the protocol is the same words for every page
    that owes the same kind of thing, so the composer prints it once rather than
    once per page. `None` where the line is the whole remedy.

    Two invariants hold between turns. A page is watched or idle, so anything
    else has quietly stopped listening. And every move delivered into this turn
    has an answer, or a work claim this turn wrote for it, where
    `activity.turn_obligations` says which moves this turn owes.

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
            state = full_state(page_dir, events)
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
        stale = turn_obligations(state, carried=carried)
        if stale:
            page_reasons.append(
                (
                    f"{page_dir}: {unanswered(stale, 'acknowledged')}{reclaim(stale)}.",
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


def stop_harness(session_id: str) -> type[Harness]:
    """The harness this session's hooks run under, as its page claims record it:
    every claim a session takes names the one harness it runs in. Should every
    claim have gone since this hook read them, a block continues the turn on any
    host."""
    for page_dir in owned_pages(session_id):
        claim = page_claim(page_dir)
        if claim is not None and claim["id"] == session_id:
            return type(claim_harness(claim))
    return Harness


# Claude Code writes a hook's context over this size to a file and hands the turn
# a 2 KB preview and the path instead: measured at 2.1.283 with ASCII, 9,990
# characters arrived whole and 10,010 did not. Which unit it counts is unmeasured,
# so the context is held to UTF-8 bytes, the strictest reading.
HOOK_CONTEXT_LIMIT = 10_000


def pointer_acknowledgement(delivery_id: str) -> str:
    """What a delivery too large to hand over inline tells its reader, who confirms
    it once read."""
    return (
        "Leaf's hook handed this delivery over as a pointer, because it was too "
        "large for the turn's context; until it is confirmed, the user's moves "
        "read Sent. Once all of it is in your context, confirm it with "
        f"`leaf delivery ack {delivery_id}`."
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
    if len(message.encode("utf-8")) < HOOK_CONTEXT_LIMIT:
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


def carry_turn(event: str | None, sid: str, payload: dict) -> None:
    """Answer a prompt, Stop, or other page-reading hook for a session holding a
    page: open or close its turn, hand over its pending input, and name what its
    pages are owed."""
    batches = []
    if event == "UserPromptSubmit":
        # Codex names the turn (`turn_id`), and its App Server names the same one,
        # so this and a carrier following the turn open one identity.
        open_session_turn(sid, payload.get("turn_id"))
        batches = pending_batches(sid)
        reasons = unattended_pages(sid, prompt_open=True, handing=batches)
    elif event == "Stop":
        # The Stop hook keeps a turn going only for what that turn owes: input
        # that arrived as it ends and is owed an answer, or a debt it names.
        # Input that owes nothing, such as a resolve, a worker's report or a
        # page's own error, reaches the agent through its watcher like any other,
        # and rides along when the turn goes on anyway. A repeated Stop has said
        # its debts once already, and only newly owed input keeps it going again:
        # the other input nobody paces, and could hold a turn open without end.
        batches = pending_batches(sid)
        owed = any("answer" in move for batch in batches for move in batch["events"])
        reasons = unattended_pages(sid, handing=batches)
        # A Stop that speaks does not end the turn: the host continues the same
        # turn with what it says as new context. Stamp only a turn the hook lets
        # end.
        if not owed and (not reasons or payload.get("stop_hook_active")):
            close_session_turn(sid)
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
    refused = []
    for batch in confirmed["batches"] if confirmed else ():
        try:
            receive_one(batch, sid)
        except (ReceiptRefused, FileNotFoundError):
            # Changed hands or went away since it was read: nothing is confirmed
            # for it, and whoever holds it now takes that input.
            refused.append(batch["page"])
    if refused:
        message += "\n" + "\n".join(
            f"- {page} changed hands before Leaf could confirm its input, so it is "
            "not yours to answer: leave it to the page's new owner."
            for page in refused
        )
    if event == "Stop":
        print(json.dumps(stop_harness(sid).continue_turn(message)))
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
