"""Stop and prompt hooks that enforce the agent conversation loop."""

import json

from .event_log import read_events
from .files import read_json
from .host import claim_harness
from .schema import (
    ACK_BATCH_INSTRUCTION,
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
from .session import record_pickup


def _stream_answers(reply: dict | None, obligation: dict, state: dict) -> bool:
    """Whether App Server finished the exact answer this Stop is closing."""
    return bool(
        reply
        and reply.get("state") == "active"
        and reply.get("settles")
        and reply.get("has_text")
        and reply.get("session") == state["claim_session"]
        and reply.get("turn") == state["claim_turn"]
        and reply.get("responds") == obligation["event"]
    )


def unattended_pages(session_id: str, *, prompt_open: bool = False) -> list:
    """The pages this session owes something, each with what to do about it.
    Two invariants hold between turns. A page is watched or idle, so anything
    else has quietly stopped listening. And every comment delivered into this
    turn has an answer under it. A comment a carrier has queued belongs to its
    later turn even though queue acceptance has advanced the page cursor."""
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
        acknowledged = [
            obligation
            for obligation in state["activity"]["obligations"]
            if obligation["seq"] <= state["cursor"]
        ]
        # Queue acceptance belongs to the originating turn, so it is not debt
        # there. The later UserPromptSubmit still opens it below; from that
        # point its ordinary unanswered debt is enforced again.
        # A draft reply counts as the answer only while the carrier that would
        # commit it is alive; otherwise nothing will finish it.
        reply = state["activity"].get("reply") if carried else None
        stale = [
            obligation
            for obligation in acknowledged
            if obligation["phase"] != "queued"
            and not _stream_answers(reply, obligation, state)
        ]
        if stale:
            ids = ", ".join(
                obligation["target"]["id"]
                if obligation["target"]["kind"] == "thread"
                else obligation["event"]
                for obligation in stale
            )
            page_reasons.append(
                f"{page_dir}: {len(stale)} acknowledged "
                f"reader move{'s' if len(stale) != 1 else ''} with no answer "
                f"({ids}). " + ANSWER_ASK_INSTRUCTION
            )
        # A live carrier is the watch, and it prints what's pending on its own.
        # Reporting the page here would start a second waiter and print the same
        # unacknowledged events twice.
        if not carried:
            # The watcher's whole batch — user events and workers' reports — not the
            # reader-facing count, which deliberately leaves reports out.
            n = len(unacknowledged(events, state["cursor"]))
            if n:
                remedy = harness.input_unpicked(page_dir, listening=listening)
                remedy += (
                    f" {ACK_BATCH_INSTRUCTION} If this task is the consumer, then address "
                    "every event."
                )
                page_reasons.append(
                    f"{page_dir}: {n} update{'s' if n != 1 else ''} you haven't picked up. "
                    + remedy
                )
            # Nothing is owed and nothing is listening. That is a debt on a page
            # handed to a reader, and a developer preview is not one: the same
            # `preview.json` the browser chrome reads to label it a preview says
            # the page is a rendering of a tracked example, put up to be looked
            # at. A session inspecting a dozen slots would otherwise carry a
            # dozen copies of this one line into every turn. The two clauses that
            # answer for a real reader stay above it, so a gesture on a preview
            # still arrives — this exempts the housekeeping, not the reader.
            #
            elif (
                state["status"]["state"] != "idle"
                and not (page_dir / PREVIEW_FILE).exists()
            ):
                page_reasons.append(
                    f"{page_dir}: "
                    + harness.nothing_listening(page_dir, listening=listening)
                )
        # Discovery is only a candidate read. Transfer can happen while the
        # hook reads status, so decide against current ownership at the end.
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim and claim["id"] == session_id:
                    if prompt_open and acknowledged:
                        by_id = {event["id"]: event for event in page.events}
                        record_pickup(
                            page,
                            [
                                by_id[obligation["event"]]
                                for obligation in acknowledged
                                if obligation["event"] in by_id
                            ],
                            phase="opened",
                            session=session_id,
                            turn=claim.get("turn"),
                        )
                    reasons.extend(page_reasons)
        except FileNotFoundError:
            continue
    return reasons


def cmd_hook(payload: dict) -> None:
    event, sid = payload.get("hook_event_name"), payload.get("session_id") or ""
    if event == "SessionEnd":
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
    if event == "UserPromptSubmit":
        open_session_turn(sid)
        reasons = unattended_pages(sid, prompt_open=True)
    elif event == "Stop":
        reasons = unattended_pages(sid)
        # A first Stop blocked on outstanding Leaf work does not end the
        # turn: Claude continues in the same turn with this reason as new
        # context. Stamp only a turn the hook allows to end (cleanly or on
        # the repeated stop that deliberately fails open).
        if not reasons or payload.get("stop_hook_active"):
            close_session_turn(sid)
        # A repeated ordinary debt is the same Stop hook asking again.
        if payload.get("stop_hook_active"):
            return
    else:
        reasons = unattended_pages(sid)
    if not reasons:
        return
    # The message avoids "unattended": a page can be watched and still be owed
    # an answer, and the runtime spends that word on a different fact — a page
    # served to nobody at all.
    message = (
        "leaf — a page of this session's has something outstanding:\n"
        + "\n".join(f"- {r}" for r in reasons)
    )
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
