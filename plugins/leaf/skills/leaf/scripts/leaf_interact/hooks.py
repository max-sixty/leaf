"""Stop and prompt hooks that enforce the agent conversation loop."""

import json

from .events import build_threads, read_events, spoken
from .files import published_versions
from .http import full_state
from .schema import ACK_BATCH_INSTRUCTION, ANSWER_ASK_INSTRUCTION
from .service import PageTransaction, owned_pages, unacknowledged


def unanswered_asks(events: list, cursor: int) -> list:
    """The comments this session took delivery of and left with no answer under
    them.

    Acknowledging is what takes a comment off the batch, so an acknowledged one
    nobody answered has passed the last gate that could have caught it: the
    watcher keeps no memory of it, and re-delivery reads the same cursor. The
    reader is left looking at a question with nothing under it, and the agent
    believes the batch is dealt with.

    What it looks for is a thread whose last word is the reader's. Not a thread
    nobody but the reader has ever spoken in: the browser posts the reader's
    follow-ups as `reply` events of their own, so under that reading one agent
    message anywhere in a thread answers it forever, and a follow-up — "but why
    not C?" — acknowledged and answered in the terminal is this very bug played
    again one level down, with the gate reading green. The agent's own ask needs
    no case of its own either way round: the last word there is the agent's
    until the reader answers, and once they answer in-thread it is theirs.

    Reading the last speaker rather than the whole cast means a thread that
    needs no answer — "great, ship it" — holds a turn until the agent replies or
    runs `leaf resolve`. That is the direction to err in. Both failures are
    invisible from the browser, so the question is who can see each: a thread
    left standing over a reader's last word is visible to nobody, while "does
    this one need an answer" is a question the agent is holding the context to
    settle, and settling it costs one command.

    The log alone, with no reading of the page: `build_threads` is told there is
    no published page to settle against, which is the one thing this reader may
    not ask for. Reading the page means loading the page's vendored registry,
    and that load is a gate — a page vendored before the layer last changed
    fails it by design. Every other caller may raise on that; this one is
    reached from the Stop hook, which fails open, so a raise here would stand
    the whole guard down on any page a little older than the code, watch clause
    included, and say nothing. What the log alone costs is that a pick retracted
    by a floor on one of its parts, rather than on the widget it named, still
    reads as settling its thread — an ask that goes unmentioned, never a turn
    blocked over an answer the reader already gave.
    """
    # The last *word*: a reaction is a mark on a message, not a turn, so an `ok`
    # the reader put on the agent's answer does not hand the thread back to the
    # agent, and a reaction nobody has replied to is no thread at all — the agent
    # answers those by acting (a version, a resolve), not by a reply under each.
    asks = []
    for t in build_threads(events, {}).values():
        said = spoken(t)
        # The cursor is read against the last word, not the root: a follow-up
        # past it is a delivery the agent has yet to take, which is the
        # unacknowledged clause's to report and not this one's.
        if (
            said
            and said[-1]["author"] == "user"
            and said[-1]["seq"] <= cursor
            and not t["resolved"]
        ):
            asks.append(t["root"])
    return asks


def unattended_pages(session_id: str) -> list:
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
            state = full_state(page_dir, events, published_versions(page_dir, events))
        except FileNotFoundError:
            continue
        codex = state["host"] == "codex"
        # Asked of every page, watched or not, and ahead of the watch question
        # below: a watcher cannot deliver a comment the cursor has already
        # passed, so a live wait is no answer to this one.
        stale = unanswered_asks(events, state["cursor"])
        if stale:
            ids = ", ".join(t["id"] for t in stale)
            page_reasons.append(
                f"{page_dir}: {len(stale)} acknowledged "
                f"comment{'s' if len(stale) != 1 else ''} with no answer "
                f"({ids}). " + ANSWER_ASK_INSTRUCTION
            )
        # A live Claude `leaf wait` is the watch, and it prints what's pending on
        # its own. Reporting the page here would start a second waiter and print
        # the same unacknowledged events twice.
        if not (state["listening"] and not codex):
            # The watcher's whole batch — user events and workers' reports — not the
            # reader-facing count, which deliberately leaves reports out.
            n = len(unacknowledged(events, state["cursor"]))
            if n:
                if codex and state["listening"]:
                    remedy = (
                        "Poll the existing `leaf wait` unified-exec session with "
                        "`write_stdin`."
                    )
                elif codex:
                    remedy = (
                        "Start `leaf wait` in unified exec, retain its session id, "
                        "and poll it with `write_stdin`."
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
            elif state["status"]["state"] != "idle":
                if codex and state["listening"]:
                    page_reasons.append(
                        f"{page_dir}: the Codex page is still live. Keep this turn "
                        "active and poll the existing `leaf wait` unified-exec "
                        "session with `write_stdin`."
                    )
                elif codex:
                    page_reasons.append(
                        f"{page_dir}: no watcher. Start `leaf wait` in unified exec, "
                        "retain its session id, and keep this turn active while polling it with "
                        "`write_stdin`; or run `leaf status <page> idle` if the page "
                        "is done."
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
    if event == "Stop":
        # Ahead of both early returns below. The stamp is not a nudge and does not
        # depend on there being one: the turn that ends with nothing outstanding is
        # exactly the turn that leaves a `working` claim behind with nobody on it.
        for page_dir in owned_pages(sid):
            try:
                with PageTransaction(page_dir) as page:
                    page.close_turn(sid)
            except FileNotFoundError:
                continue
    # stop_hook_active means this hook already blocked once and Claude is running
    # again on the strength of it; blocking a second time is how a hook loops.
    # A block naming two debts and answered on one therefore ends the turn with
    # the other standing — the guard is a nudge per stop, not a barrier. What
    # carries the rest is UserPromptSubmit, which reads the same reasons, so the
    # debt opens the next turn rather than waiting for its end.
    if event == "Stop" and payload.get("stop_hook_active"):
        return
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
