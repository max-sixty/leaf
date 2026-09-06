"""Stop and prompt hooks that enforce the agent conversation loop."""

import json

from . import codex as codex_delivery
from .event_log import read_events
from .leases import adapter_is_live
from .schema import (
    ACK_BATCH_INSTRUCTION,
    ANSWER_ASK_INSTRUCTION,
    PREVIEW_FILE,
)
from .served_state.page import full_state
from .service import (
    PageTransaction,
    close_session_turn,
    open_session_turn,
    owned_pages,
    unacknowledged,
)
from .session import record_pickup


def unattended_pages(session_id: str, *, prompt_open: bool = False) -> list:
    """The pages this session owes something, each with what to do about it.
    Two invariants hold between turns. A page is watched or idle, so anything
    else has quietly stopped listening. And every comment the session has taken
    delivery of has an answer under it, since acknowledging is what takes one
    off the batch and nothing delivers it again."""
    reasons = []
    for page_dir in owned_pages(session_id):
        page_reasons = []
        try:
            events = read_events(page_dir)
            state = full_state(page_dir, events)
        except FileNotFoundError:
            continue
        codex = state["host"] == "codex"
        adapter = codex and adapter_is_live(session_id)
        # Asked of every page, watched or not, and ahead of the watch question
        # below: a watcher cannot deliver a comment the cursor has already
        # passed, so a live wait is no answer to this one.
        stale = [
            obligation
            for obligation in state["activity"]["obligations"]
            if obligation["seq"] <= state["cursor"]
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
        # A live Claude watcher is the watch: `leaf wait` before the first batch,
        # then the `leaf ack` that re-arms it. It prints what's pending on its own.
        # Reporting the page here would start a second waiter and print the same
        # unacknowledged events twice.
        if not (state["listening"] and (not codex or adapter)):
            # The watcher's whole batch — user events and workers' reports — not the
            # reader-facing count, which deliberately leaves reports out.
            n = len(unacknowledged(events, state["cursor"]))
            if n:
                if codex and state["listening"]:
                    remedy = (
                        "Poll the existing unified-exec session — `leaf wait` before "
                        "the first batch or the rearmed `leaf ack` afterward — with "
                        "`write_stdin`."
                    )
                elif codex:
                    remedy = (
                        f"Start `leaf codex start {page_dir}` so later updates queue "
                        "new turns in this task."
                    )
                else:
                    remedy = "`leaf wait` prints them."
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
            # Presence, not `server.preview_metadata`: that reader is the serve
            # path's gate and exits the process on a file it will not accept,
            # which here — inside a guard that fails open by saying nothing —
            # would stand the whole hook down over every page this session holds.
            elif (
                state["status"]["state"] != "idle"
                and not (page_dir / PREVIEW_FILE).exists()
            ):
                if codex and state["listening"]:
                    page_reasons.append(
                        f"{page_dir}: the Codex page is still live. Keep this turn "
                        "active and poll the existing unified-exec session — `leaf "
                        "wait` before the first batch or the rearmed `leaf ack` "
                        "afterward — with `write_stdin`."
                    )
                elif codex:
                    page_reasons.append(
                        f"{page_dir}: no delivery adapter. Start `leaf codex start "
                        f"{page_dir}` so this turn can finish and later updates start "
                        "new turns; or run `leaf status <page> idle` if the page is done."
                    )
                else:
                    page_reasons.append(
                        f"{page_dir}: no watcher. Start `leaf wait` as a background "
                        "task — one wait covers every page this session holds — or "
                        "run `leaf status <page> idle` if the page is done."
                    )
        # Discovery is only a candidate read. Transfer can happen while the
        # hook reads status, so decide against current ownership at the end.
        try:
            with PageTransaction(page_dir) as page:
                claim = page.active_claim
                if claim and claim["id"] == session_id:
                    if prompt_open and stale:
                        by_id = {event["id"]: event for event in page.events}
                        record_pickup(
                            page,
                            [
                                by_id[obligation["event"]]
                                for obligation in stale
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
        codex, delivery = codex_delivery.open_turn(sid)
        if not codex:
            open_session_turn(sid)
        reasons = unattended_pages(sid, prompt_open=True)
        if delivery is not None:
            reasons.insert(
                0,
                "new Leaf input joined this turn. Process every batch in:\n" + delivery,
            )
    elif event == "Stop":
        reasons = unattended_pages(sid)
        codex_reasons = codex_delivery.finish_turn(
            sid,
            reasons,
            bool(payload.get("stop_hook_active")),
        )
        if codex_reasons is not None:
            reasons = codex_reasons
        else:
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
