"""Page activity: what the panel says the agent is doing, read from the status
declaration, the claim and its turn, the harness's own session record, pickups and
live App Server streams, and the served state that dates it."""

import json
import os
import time
from datetime import datetime, timedelta

from click.testing import CliRunner
from interact_support import (
    _interaction_prompt_evidence,
    _start,
    activity_reading,
    append_carried_log_record,
    consume_pending_input,
    declare,
    declare_work,
    declared,
    delivered,
    end_work,
    owed,
    page_state,
    read_record,
    record_claim,
    response_reference,
    said,
    serving,
    state_json,
    working,
    write_record,
    yaml_document,
)
from interact_support import declare as declare_status

from leaf import activity as activity_model
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import obligations as obligations_model
from leaf import presence as presence_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf.served_state import context as read_context
from leaf.served_state import page as served_page


def test_a_claimant_inside_a_turn_is_listening_between_two_waits(claimed):
    """A wait that ends to wake the session leaves no lease behind, but the turn it
    reaches, or opens, takes the input, so the status keeps reading listening rather
    than telling the user the agent is away. Once the turn has closed, it is away."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    cleanup_model.open_session_turn(claim["id"])
    assert page_state(claimed)["listening"] is False
    assert activity_reading(claimed)["kind"] == "listening"

    cleanup_model.close_session_turn(claim["id"])
    assert activity_reading(claimed)["kind"] == "away"


def test_a_session_the_next_input_wakes_reads_listening(page_dir, tmp_path):
    """With no watch after its turn ended, a session is away only if the nudge the
    next input gets (`ClaudeCodeHarness.nudge`) might not start a turn. A background
    job whose daemon retired its idle worker, and the watch with it, is resumed with
    that input as its prompt. A live session takes it from its socket as a turn
    where the user's settings accept other sessions' messages; elsewhere the message
    may wait behind a dialog."""
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "s1"})
    record_claim(page_dir, job=str(job), turn_closed=cleanup_model.now_iso())
    assert activity_reading(page_dir)["kind"] == "listening"

    sessions = harness_model.claude_code_sessions()
    sessions.mkdir(exist_ok=True)
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    worker = {
        "pid": os.getpid(),
        "sessionId": "s1",
        "cwd": str(project / "src"),
        "messagingSocketPath": str(tmp_path / "peer.sock"),
    }
    cleanup_model.write_json(sessions / f"{os.getpid()}.json", worker)
    cleanup_model.write_json(sessions / f"{os.getpid()}.k.key", {"peerToken": "t"})
    assert activity_reading(page_dir)["kind"] == "away"

    cleanup_model.write_json(
        harness_model.claude_code_config() / "settings.json",
        {"crossSessionInbound": "accept"},
    )
    assert activity_reading(page_dir)["kind"] == "listening"

    # A project can narrow the user's accept, from the repository's root too.
    (project / ".claude").mkdir()
    cleanup_model.write_json(
        project / ".claude" / "settings.local.json", {"crossSessionInbound": "hold"}
    )
    assert activity_reading(page_dir)["kind"] == "away"

    # Only the user's settings grant it.
    cleanup_model.write_json(
        project / ".claude" / "settings.local.json", {"crossSessionInbound": "accept"}
    )
    cleanup_model.write_json(harness_model.claude_code_config() / "settings.json", {})
    assert activity_reading(page_dir)["kind"] == "away"


def test_only_a_fresh_turn_whose_hooks_take_input_reads_listening(
    claimed, codex_claimed_page
):
    """Listening between two waits rests on the open turn taking the input, which
    only a session whose hooks hand it over does, and only while the turn is
    plausibly running. A Codex task's open turn takes input once a tool hook has
    proven its hooks run, since the tool hook then offers the pointer between
    steps; before that, with no adapter lease, it is nobody listening. A Claude Code turn
    no Stop closed, as an interrupted one, stops counting once nothing in it has
    renewed it for the working grace: its opening, or a status written during it."""
    now = datetime.now().astimezone()
    for page in (claimed, codex_claimed_page):
        declare(page, ts=now.isoformat())
    codex = page_state(codex_claimed_page)
    # Every other clause of the rule holds, so only the watcher can read it away.
    assert codex["session_alive"] is True
    assert codex["claim_turn"] and codex["turn_closed"] is None
    assert codex["turn_opened"] and not codex["turn_takes_input"]
    assert codex["listening"] is False
    assert codex["activity"]["kind"] == "away"
    leases_model.mark_hooks("codex-thread")
    codex = page_state(codex_claimed_page)
    assert codex["turn_takes_input"] and codex["listening"] is False
    assert codex["activity"]["kind"] == "listening"

    assert activity_reading(claimed)["kind"] == "listening"
    claim = service_model.page_claim(claimed)

    # A stale status does not mask the open turn's own deadline: with the status
    # already quiet, listening's only remaining source is the turn, so its own
    # working-grace boundary must still be scheduled, or the browser is left
    # showing Listening past the point the turn can plausibly still be running.
    opened = (now - timedelta(minutes=1)).replace(microsecond=0)
    assert claim is not None
    record_claim(claimed, **{**claim, "turn_opened": opened.isoformat()})
    declare(claimed, ts="2020-01-01T00:00:00+00:00")
    listening = activity_reading(claimed)
    assert listening["kind"] == "listening"
    assert (
        listening["next_transition_at"]
        == (opened + activity_model.WORKING_GRACE).isoformat()
    )

    # The fresh turn is someone there under a start gone stale too, so that old work
    # reads stalled rather than away, until its task ends.
    old_start = declare_work(
        claimed, "an old task", ts="2020-01-01T00:00:00+00:00", session="s1"
    )
    assert activity_reading(claimed)["kind"] == "stalled"
    ended = CliRunner().invoke(
        cli_model.cli, ["task", "end", str(claimed), old_start["item"], "done"]
    )
    assert ended.exit_code == 0, ended.output
    claim = service_model.page_claim(claimed)
    opened = now - activity_model.WORKING_GRACE - timedelta(minutes=1)
    assert claim is not None
    record_claim(
        claimed, **{**claim, "turn_opened": opened.isoformat(timespec="seconds")}
    )
    declare(claimed, ts=opened.isoformat())
    stale = page_state(claimed)
    assert (stale["turn_takes_input"], stale["turn_closed"]) == (True, None)
    assert stale["activity"]["kind"] == "away"

    # A status the turn writes renews it: the agent is there to have written it.
    declare(claimed, ts=now.isoformat())
    assert activity_reading(claimed)["kind"] == "listening"

    # A claim an older Leaf wrote, with no `turn_opened`, owes no belief either.
    lifecycle = cleanup_model.session_record("s1")
    assert lifecycle is not None
    cleanup_model.write_json(
        cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX),
        {key: value for key, value in lifecycle.items() if key != "turn_opened"},
    )
    assert activity_reading(claimed)["kind"] == "unheld"


def test_direct_delivery_progress_does_not_become_page_activity(claimed, capsys):
    """Delivery stays exact interaction evidence while page activity continues to
    describe the claimant's availability and independently declared work."""
    serving(claimed, 1)
    declare_work(claimed, "an old task", ts="2020-01-01T00:00:00+00:00")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "new input"}
    )

    assert session_model.cmd_wait(claimed) == 0
    delivered(capsys)
    activity = activity_reading(claimed)
    assert activity["kind"] == "working"
    assert [item["stage"] for item in activity["obligations"]] == ["picked_up"]
    agent_state = state_json(claimed)
    agent_activity = agent_state["activity"]
    assert agent_activity["kind"] == activity["kind"]
    # The agent reading names each owed answer by its record's id beside the answer;
    # the move itself is listed once.
    [move] = owed(agent_state)
    assert [item["id"] for item in agent_activity["obligations"]] == [
        move["obligation"]
    ]
    assert move["subject"] == {"kind": "thread", "id": comment["id"]}
    assert "acknowledgments" not in page_state(claimed)["browser"]
    *_, pickup = (e for e in events_model.read_events(claimed) if e["kind"] == "pickup")
    claim = service_model.page_claim(claimed)
    assert claim is not None
    assert (pickup["phase"], pickup["session"], pickup["turn"]) == (
        "opened",
        claim["id"],
        claim["turn"],
    )

    end_work(claimed)
    session_model.cmd_waiting(claimed)
    assert activity_reading(claimed)["kind"] == "working"

    cleanup_model.close_session_turn(claim["id"])
    ended = activity_reading(claimed)
    assert ended["kind"] == "away"
    assert ended["obligations"][0]["condition"] == {
        "kind": "ended",
        "operation": "work",
    }

    lease_path = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path is not None
    lease = leases_model.take_wait_lease(lease_path)
    assert lease
    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "answered",
        },
    )
    settled = activity_reading(claimed)
    assert settled["kind"] == "listening"
    assert settled["obligations"] == []
    leases_model.release_lease(lease)


def _activity_at(page, minutes=0):
    """The page's activity as the server would read it `minutes` from now."""
    now = datetime.now().astimezone() + timedelta(minutes=minutes)
    return activity_reading(page, now.isoformat())


def test_claude_codes_own_record_adds_what_no_hook_sees(claimed, capsys, dead_pid):
    """Claude Code publishes each session's live status in its session registry,
    dated by its last change: `idle` (or `shell`, with a background command) once no
    turn runs, `waiting` while a turn holds a dialog open, `busy` otherwise. An
    interrupt runs no Stop hook, so an `idle` newer than everything that renewed the
    turn ends it at that moment, and a `waiting` newer than the turn's stamps is
    a dialog open now. `busy` never says a turn runs: the record keeps it across
    turn endings while background work runs. Without a word from the record the
    hook stamps answer, believed only while something renewed the turn within the
    working grace, so a delivered move no Stop closed cannot read working forever."""
    serving(claimed, 1)
    registry = harness_model.claude_code_sessions()
    registry.mkdir(parents=True, exist_ok=True)

    live = os.getpid()

    def harness_says(status, *, pid=live, ago=0):
        cleanup_model.write_json(
            registry / f"{pid}.json",
            {
                "pid": pid,
                "sessionId": "s1",
                "status": status,
                "statusUpdatedAt": int((time.time() - ago) * 1000),
            },
        )

    session_model.cmd_waiting(claimed)
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Tighten the lede."}
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert json.loads(context.split("\n")[1])["acknowledge"] is None

    # The stamps answer, and nothing renews this turn past the grace; `busy`, and
    # a record whose process is gone, change nothing.
    harness_says("busy")
    harness_says("waiting", pid=dead_pid)
    assert _activity_at(claimed)["kind"] == "working"
    unrenewed = _activity_at(claimed, 16)
    assert unrenewed["counts"]["handling"] == 0
    assert unrenewed["obligations"][0]["condition"] == {
        "kind": "stale",
        "operation": "work",
    }

    # A dialog in the terminal is observed work the page announces.
    harness_says("waiting")
    waiting = _activity_at(claimed)
    assert (waiting["kind"], waiting["observed_kind"]) == ("working", "awaiting_user")

    # Escape: the turn ended with no Stop hook, and the move it held reads Turn
    # ended at once.
    harness_says("idle")
    claim_record = service_model.page_claim(claimed)
    assert claim_record is not None
    assert claim_record["turn_closed"] is None
    assert _activity_at(claimed)["obligations"][0]["condition"] == {
        "kind": "ended",
        "operation": "work",
    }

    # The next prompt renews the turn the interrupt left open, and the move it
    # holds is handled in it again.
    harness_says("busy")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    assert _activity_at(claimed)["counts"]["handling"] == 1

    # A start the agent writes after that renews the turn, and the move it starts
    # stops being believed once the renewal grace has passed since the next
    # interrupt.
    harness_says("idle", ago=5)
    assert _start(claimed, comment["id"], "Cutting the lede").exit_code == 0
    assert _activity_at(claimed)["counts"]["active"] == 1
    harness_says("idle")
    assert _activity_at(claimed)["kind"] == "working"
    ended = _activity_at(claimed, 3)
    assert (ended["kind"], ended["dropped"]) == ("away", True)
    assert ended["obligations"][0]["condition"] == {
        "kind": "stale",
        "operation": "work",
    }

    # A status the harness has no word on is no reading at all.
    harness_says("compacting")
    assert harness_model.ClaudeCodeHarness("s1", "Claude").live_turn() is None


def test_a_coordinators_workers_keep_its_page_working(claimed, capsys):
    """Claude Code's record stays `busy` after a turn ends while the background
    subagents it left run. Until the record leaves `busy`, the page reads working,
    observed in the background. The record doesn't say which turn left the work,
    so the ended turn's start is dropped as usual. A background shell leaves the
    record `shell`, which is idle."""
    serving(claimed, 1)
    registry = harness_model.claude_code_sessions()
    registry.mkdir(parents=True, exist_ok=True)

    def harness_says(status):
        cleanup_model.write_json(
            registry / f"{os.getpid()}.json",
            {
                "pid": os.getpid(),
                "sessionId": "s1",
                "status": status,
                "statusUpdatedAt": int(time.time() * 1000),
            },
        )

    session_model.cmd_waiting(claimed)
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Compare the layouts."}
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    consume_pending_input("s1")
    harness_says("busy")
    assert (
        _start(claimed, comment["id"], "Workers are comparing layouts").exit_code == 0
    )
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": False},
    )
    capsys.readouterr()
    claim_record_2 = service_model.page_claim(claimed)
    assert claim_record_2 is not None
    assert claim_record_2["turn_closed"] is not None

    # Within the renewal grace the start's line stands, with the step beside it.
    ending = _activity_at(claimed)
    assert (ending["kind"], ending["detail"], ending["observed"]) == (
        "working",
        "Workers are comparing layouts",
        activity_model.BACKGROUND_DETAIL,
    )
    later = _activity_at(claimed, 10)
    assert (later["kind"], later["detail"], later["dropped"]) == (
        "working",
        activity_model.BACKGROUND_DETAIL,
        False,
    )
    assert later["obligations"][0]["condition"] == {
        "kind": "stale",
        "operation": "work",
    }

    for idle in ("idle", "shell"):
        harness_says(idle)
        ended = _activity_at(claimed, 10)
        assert (ended["kind"], ended["dropped"], ended["observed"]) == (
            "away",
            True,
            "",
        )


def test_away_asks_for_a_nudge_only_once_input_is_overdue(claimed, capsys):
    """With nothing taking input, a comment that has only just arrived is the
    session's next turn to take, and Leaf messages a Claude Code session as it
    arrives. The page asks the user to nudge the agent only once an owed move has
    stalled with the agent to act, which `counts.overdue` names: one still Sent
    past the pickup grace, or one a turn picked up and ended without answering."""
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)

    def turn_ends():
        # The first Stop refuses to end the turn over the page's debts; the
        # repeated one lets it end.
        for repeated in (False, True):
            hooks_model.cmd_hook(
                "claude-code",
                {
                    "hook_event_name": "Stop",
                    "session_id": "s1",
                    "stop_hook_active": repeated,
                },
            )
        capsys.readouterr()

    consume_pending_input("s1")

    turn_ends()
    assert _activity_at(claimed, 3)["kind"] == "away"
    assert _activity_at(claimed, 3)["counts"]["overdue"] == 0

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Still there?"}
    )
    fresh, late = _activity_at(claimed), _activity_at(claimed, 3)
    assert (fresh["kind"], fresh["counts"]["overdue"]) == ("away", 0)
    assert (late["kind"], late["counts"]["overdue"]) == ("away", 1)

    # Picked up by the next turn. A long, silent step past the working grace
    # leaves nothing to say the turn ended, so it asks for no nudge; the turn
    # ending without answering does.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    capsys.readouterr()
    consume_pending_input("s1")
    assert _activity_at(claimed)["counts"]["overdue"] == 0
    assert _activity_at(claimed, 16)["counts"]["overdue"] == 0
    turn_ends()
    stranded = _activity_at(claimed)
    assert (stranded["kind"], stranded["counts"]["overdue"]) == ("away", 1)


def test_a_harness_step_waiting_on_the_user_outlasts_the_working_grace():
    """An App Server observer renews its step on every event, and a wait on the
    user sends none until the user answers, so that step stands for as long as
    its observer holds the lease. A turn that completed with no final answer
    leaves the move it owed reading ended."""
    now = datetime.now().astimezone()
    old = (now - timedelta(minutes=30)).isoformat()
    present = {
        "status": {"state": "waiting", "ts": old},
        "listening": True,
        "session_alive": True,
        "live_turn": None,
        "claim_session": "session-1",
        "claim_turn": "turn-1",
        "cursor": 0,
        "turn_opened": old,
        "turn_closed": None,
        "turn_takes_input": False,
    }
    voice = {"author": "agent", "agent": "Agent", "session": "session-1"}
    events = [
        {
            "kind": "todo",
            "id": "t1",
            "owner": "agent",
            "seq": 1,
            "ts": old,
            "subject": {"kind": "page"},
            "title": "Revise the page",
            **voice,
        },
        {
            "kind": "start",
            "id": "s1",
            "seq": 2,
            "ts": old,
            "item": "t1",
            "text": "Revising",
            "turn": "turn-1",
            **voice,
        },
    ]
    stream = {"session": "session-1", "turn": "turn-1", "ts": old}
    nothing = obligations_model.collection([])
    waiting = activity_model.canonical_activity(
        present,
        [],
        events,
        now.isoformat(),
        {**stream, "kind": "awaiting_approval"},
        updates=nothing,
    )
    assert (waiting["kind"], waiting["observed_kind"]) == (
        "working",
        "awaiting_approval",
    )
    thinking = activity_model.canonical_activity(
        present,
        [],
        events,
        now.isoformat(),
        {**stream, "kind": "thinking"},
        updates=nothing,
    )
    assert (thinking["kind"], thinking["observed_kind"]) == ("stalled", None)

    workflow = {
        "id": "input-1",
        "input": "input-1",
        "seq": 1,
        "subject": {"kind": "thread", "id": "input-1"},
        "obligation": "update:input-1",
        "stage": "picked_up",
        "ts": now.isoformat(),
        "condition": None,
        "response": None,
    }
    reply = {
        "state": "partial",
        "session": "session-1",
        "responds": "input-1",
        "turn": "turn-1",
        "attempt": "reply-attempt",
        "settles": False,
        "updated_at": now.isoformat(),
    }
    owed = obligations_model.update_obligation(
        "input-1",
        {"kind": "thread", "id": "input-1"},
        "input-1",
        "input-1",
        next_actor="agent",
    )
    [ended] = activity_model.canonical_activity(
        present,
        [workflow],
        events,
        now.isoformat(),
        reply=reply,
        updates=obligations_model.collection([owed]),
    )["workflows"]
    assert ended["condition"] == {"kind": "ended", "operation": "response"}


def test_queued_input_does_not_hide_fresh_work(claimed):
    serving(claimed, 1)
    working(claimed, "Revising the heading")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    with service_model.PageTransaction(claimed) as transaction:
        delivery_model.record_pickup(transaction, [comment], phase="queued")

    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Revising the heading",
    )
    assert activity["counts"]["queued"] == 1
    assert activity["obligations"][0]["stage"] == "queued"


def test_newer_pending_input_does_not_reclassify_page_work(claimed):
    serving(claimed, 1)
    working(claimed, "Revising the heading")

    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )

    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Revising the heading",
    )
    assert activity["counts"]["pending"] == 1
    assert activity["obligations"][0]["stage"] == "sent"


def test_queued_input_does_not_hide_live_codex_activity(claimed):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_2 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_2 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_2)
    assert lease
    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the checks"}
        )

    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    with service_model.PageTransaction(claimed) as transaction:
        delivery_model.record_pickup(transaction, [comment], phase="queued")

    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Running the checks",
    )
    assert activity["observed_kind"] == "tool"
    assert activity["counts"]["queued"] == 1
    leases_model.release_lease(lease)


def test_live_codex_activity_overlays_the_declared_page_status(claimed):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_3 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_3 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_3)
    assert lease

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )

    assert declared(claimed)["state"] == "waiting"
    public_presence = presence_model.presence(
        claimed, events_model.read_events(claimed)
    )
    assert "stream" not in public_presence
    assert "stream" not in public_presence["status"]
    live = page_state(claimed)
    assert "stream" not in live
    assert "stream" not in live["status"]
    activity = live["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Running the tests",
    )
    assert activity["observed_kind"] == "tool"

    session_model.cmd_waiting(claimed)
    assert activity_reading(claimed)["detail"] == "Running the tests"

    with service_model.PageTransaction(claimed) as transaction:
        transaction.clear_stream_activity("s1", "turn-live")
    returned = activity_reading(claimed)
    assert (returned["kind"], returned["detail"]) == ("listening", "")
    leases_model.release_lease(lease)


def test_stream_activity_writes_only_new_readings(claimed, monkeypatch):
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )
    unchanged = (claimed / "stream.json").read_bytes()

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "tool", "detail": "Running the tests"}
        )
    assert (claimed / "stream.json").read_bytes() == unchanged

    with service_model.PageTransaction(claimed) as transaction:
        transaction.set_stream_activity(
            "s1", "turn-live", {"kind": "thinking", "detail": "Reviewing the result"}
        )
    changed = (claimed / "stream.json").read_bytes()
    assert changed != unchanged
    observed = read_record(claimed / "stream.json")["activity"]
    assert observed["detail"] == "Reviewing the result"

    renewed_at = (
        datetime.fromisoformat(observed["ts"]) + timedelta(minutes=6)
    ).isoformat()
    with monkeypatch.context() as patch:
        patch.setattr(service_model, "now_iso", lambda: renewed_at)
        with service_model.PageTransaction(claimed) as transaction:
            transaction.set_stream_activity(
                "s1",
                "turn-live",
                {"kind": "thinking", "detail": "Reviewing the result"},
            )
    assert read_record(claimed / "stream.json")["activity"]["ts"] == renewed_at


def test_a_current_declaration_keeps_the_sentence_a_live_stream_stands_beside(claimed):
    """One turn states two facts, and each answers its own question.

    The observed step proves the session is alive and moving, which is what makes a page
    working over a declaration that says otherwise. What the work *is* is the agent's to
    say, and a user waiting on an answer is owed that sentence rather than whichever
    command the transport saw most recently. So a current declaration keeps the sentence
    and its own date, and the step is reported beside it."""
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_4 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_4 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_4)
    assert lease

    start = working(claimed, "Checking the rollout against staging")
    with service_model.PageTransaction(claimed) as transaction:
        assert claim is not None
        transaction.set_stream_activity(
            claim["id"],
            "turn-live",
            {"kind": "tool", "detail": "Running the tests"},
        )

    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"], activity["observed"]) == (
        "working",
        "Checking the rollout against staging",
        "Running the tests",
    )
    # The date belongs to the line, so a stream renewing every few seconds cannot
    # make an old start read as current work.
    assert activity["ts"] == start["ts"]
    assert activity["detail_source"] == {
        "event_id": start["id"],
        "item": start["item"],
    }

    # With nothing in hand, the step is all there is, and it is the sentence.
    ended = CliRunner().invoke(
        cli_model.cli, ["task", "end", str(claimed), start["item"], "done"]
    )
    assert ended.exit_code == 0, ended.output
    session_model.cmd_waiting(claimed)
    waiting = activity_reading(claimed)
    assert (waiting["kind"], waiting["detail"], waiting["observed"]) == (
        "working",
        "Running the tests",
        "Running the tests",
    )
    assert waiting["detail_source"] is None

    session_model.cmd_waiting(claimed)

    # A newer user move has its own pending delivery; it does not reclassify current
    # page work or imply that the observed tool step belongs to that message.
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "One more note"}
    )
    quiet = activity_reading(claimed)
    assert (
        quiet["kind"],
        quiet["detail"],
        quiet["observed_kind"],
        quiet["observed"],
    ) == (
        "working",
        "Running the tests",
        "tool",
        "Running the tests",
    )
    assert quiet["counts"]["pending"] == 1
    leases_model.release_lease(lease)


def test_a_malformed_old_stream_record_is_ignored(claimed):
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_5 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_5 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_5)
    assert lease
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "user",
            "text": "new work",
        },
    )
    start = working(claimed, "Handling the new work")
    # Written past `write_record`, whose schema check would refuse the activity
    # without its `kind`.
    cleanup_model.write_json(
        claimed / "stream.json",
        service_model.STREAM.stored(
            {
                **service_model.no_stream(),
                "activity": {
                    "session": claim["id"],
                    "turn": "older-turn",
                    "detail": "Older streamed work",
                    "ts": start["ts"],
                    "after": 0,
                },
            }
        ),
    )

    activity = activity_reading(claimed)
    assert (activity["kind"], activity["detail"]) == (
        "working",
        "Handling the new work",
    )
    end_work(claimed)
    session_model.cmd_waiting(claimed)
    without_old_stream = activity_reading(claimed)
    assert (without_old_stream["kind"], without_old_stream["observed_kind"]) == (
        "listening",
        None,
    )
    leases_model.release_lease(lease)


def test_stream_work_is_scoped_to_the_live_session_and_freshness(claimed):
    serving(claimed, 1)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_6 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_6 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_6)
    assert lease
    session_model.cmd_waiting(claimed)
    with service_model.PageTransaction(claimed) as transaction:
        assert claim is not None
        transaction.set_stream_activity(
            claim["id"],
            "provider-turn",
            {"kind": "thinking", "detail": "Checking the result"},
        )
    assert activity_reading(claimed)["observed_kind"] == "thinking"

    activity = read_record(claimed / "stream.json")["activity"]
    write_record(
        claimed / "stream.json", {"activity": {**activity, "session": "other"}}
    )
    assert activity_reading(claimed)["observed_kind"] is None

    write_record(
        claimed / "stream.json",
        {"activity": {**activity, "ts": "2020-01-01T00:00:00+00:00"}},
    )
    stale = activity_reading(claimed)
    assert (stale["kind"], stale["observed_kind"]) == ("listening", None)
    leases_model.release_lease(lease)


def test_unheld_activity_drops_interaction_claims_from_the_same_reading(
    page_dir, monkeypatch
):
    """One held decision governs both the page and its interaction receipts."""
    serving(page_dir, 1)
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "new input"}
    )
    claimed = _start(page_dir, comment["id"], "reading it")
    assert claimed.exit_code == 0, claimed.output
    followup = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": comment["id"],
            "text": "one more detail",
        },
    )
    assert [
        (workflow["input"], workflow["stage"])
        for workflow in page_state(page_dir)["workflows"]
    ] == [(comment["id"], "working"), (followup["id"], "sent")]
    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (datetime.now().astimezone() + timedelta(minutes=20)).isoformat(),
    )

    state = page_state(page_dir)
    activity = state["activity"]
    assert (activity["kind"], activity["held"]) == ("unheld", False)
    assert {item["input"]: item["stage"] for item in state["workflows"]} == {
        comment["id"]: "sent",
        followup["id"]: "sent",
    }
    assert all(
        (workflow["agent"], workflow["detail"]) == (None, None)
        for workflow in state["workflows"]
    )
    assert all(workflow["activity"] == [] for workflow in state["workflows"])
    assert all(
        workflow["condition"] == {"kind": "stale", "operation": "delivery"}
        for workflow in state["workflows"]
    )


def test_idle_activity_refreshes_when_its_ownership_expires(page_dir, monkeypatch):
    """A Closed label still schedules the deadline at which nobody holds the page.

    The declaration puts down what was in hand, so the closed page holds no
    receipt; what lapses is whether the agent is believed there at all."""
    serving(page_dir, 1)
    started = datetime.now().astimezone()
    declare(page_dir, "idle", ts=started.isoformat())

    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (started + timedelta(minutes=14)).isoformat(),
    )
    before = page_state(page_dir)["activity"]
    assert (before["kind"], before["held"]) == ("closed", True)
    assert before["next_transition_at"] == (started + timedelta(minutes=15)).isoformat()

    monkeypatch.setattr(
        read_context,
        "now_iso",
        lambda: (started + timedelta(minutes=15)).isoformat(),
    )
    after = page_state(page_dir)["activity"]
    assert (after["kind"], after["held"]) == ("closed", False)
    assert after["next_transition_at"] is None


def test_the_state_payload_carries_the_clock_its_timestamps_were_written_by(page_dir):
    """Every ts a seat dates is written here, while the user's `Date.now()` is
    another machine's opinion. The payload states the writer's clock so the reading is
    made against that one; without it a skewed laptop misreads every age on the page,
    in one direction and with nothing to give it away."""
    state = served_page.full_state(page_dir, [])
    written = datetime.fromisoformat(state["now"])
    assert abs((datetime.now().astimezone() - written).total_seconds()) < 60


def test_the_state_payload_says_when_it_was_taken(page_dir):
    """Two answers can cross on the wire, and nothing the log orders tells them apart
    when neither carries a new event. Each says when the server took it, so a tab
    keeps the later one whichever lands last."""
    first = served_page.full_state(page_dir, [])
    second = served_page.full_state(page_dir, [])
    assert first["taken"] < second["taken"]
    assert abs(time.time() - second["taken"]) < 60


def test_waiting_written_over_an_unanswered_move_names_it(claimed, snapshot):
    """`leaf page open` reads its transition back so a silent success cannot pass for a
    no-op. Canonical activity keeps showing an unanswered user move over a `waiting`
    written ahead of it, so the status the agent believes it set is not the one the
    user sees. The readback names the move; once it has an answer the line stands
    alone."""
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "hi"}
    )
    comment = events_model.read_events(claimed)[0]["id"]
    waiting = ["page", "open", str(claimed)]

    early = CliRunner().invoke(cli_model.cli, waiting)
    assert early.exit_code == 0, early.output
    assert json.loads(early.stdout)["state"] == "waiting"
    [owed] = said(early.stderr)
    assert owed["code"] == "page-open-owes"
    assert owed["text"] == (
        "1 user update with no answer (`leaf thread reply <answer.ref>` with "
        f"the `answer.ref` that `leaf wait {claimed}` delivers for {comment}); "
        "opening the page does not answer them"
    )

    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(claimed, comment),
            "--text",
            "ok",
        ],
    )
    assert replied.exit_code == 0, replied.output
    settled = CliRunner().invoke(cli_model.cli, waiting)
    assert settled.stderr == ""
    assert json.loads(settled.stdout)["state"] == "waiting"
    snapshot.check(
        yaml_document(
            "Opening a page names unanswered work until the reply settles it.",
            _interaction_prompt_evidence(
                claimed,
                {
                    moment: {
                        "exit": result.exit_code,
                        # The status as written, less the instant it was written at.
                        "status": {
                            key: value
                            for key, value in json.loads(result.stdout).items()
                            if key != "ts"
                        },
                        "note": said(result.stderr),
                    }
                    for moment, result in (
                        ("before reply", early),
                        ("after reply", settled),
                    )
                },
            ),
        )
    )


def test_state_reports_whether_the_owning_session_still_exists(claimed, dead_pid):
    """The status's one hard fact: a claim outlives its session, the owning pid
    doesn't."""
    assert page_state(claimed)["session_alive"] is True
    record_claim(claimed, pid=dead_pid)
    assert page_state(claimed)["session_alive"] is False


def test_a_process_free_publication_keeps_input_without_claimant_facts(claimed):
    """Captured host delivery retains the log but cannot publish a sleeping process."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Keep this input"}
    )
    session_model.cmd_waiting(claimed)
    claim = service_model.page_claim(claimed)
    assert claim is not None
    lease_path_7 = leases_model.waiter_lease_path(claimed, claim["id"])
    assert lease_path_7 is not None
    assert claim is not None
    lease = leases_model.take_wait_lease(lease_path_7)
    assert lease
    try:
        live, _ = presence_model.presence_with_activity(claimed, [comment])
        assert live["listening"]
        assert claim is not None
        assert live["claim_session"] == claim["id"]
        captured, stream = presence_model.presence_with_activity(
            claimed, [comment], process=False
        )
        assert stream is None
        assert captured["cursor"] == live["cursor"]
        assert captured["pending"] == live["pending"] == 1
        assert captured["status"] == {"state": "waiting"}
        assert captured["agent"] == schema_model.UNNAMED_AGENT
        assert not captured["listening"]
        for field in (
            "session_alive",
            "live_turn",
            "claim_session",
            "session_name",
            "claim_turn",
            "turn_closed",
            "turn_opened",
            "session_cwd",
        ):
            assert captured[field] is None
        assert not captured["turn_takes_input"]
    finally:
        leases_model.release_lease(lease)


def test_the_activity_a_claim_its_turn_and_their_silence_come_to(page_dir, dead_pid):
    """The status may claim no more than the page directory can prove. A watch that
    has stopped must read differently from a watch with nothing to report, and a page
    nothing is behind differently from either, without reading as a fault: a
    persistent page spends the night that way. This walks one page through each
    declaration, claim and turn the status tells apart; what each reading says is
    `tests/runtime/activity-words.test.mjs`'s."""
    d = page_dir
    append_carried_log_record(
        d, {"kind": "comment", "author": "user", "revision": 1, "text": "Comment 0."}
    )

    def declare(
        state,
        detail="",
        *,
        agent="Claude",
        quiet_for=0,
        turn_ended=None,
        session_pid=None,
        claimed=True,
        stream=None,
    ):
        """`quiet_for` ages the declaration; `turn_ended` says how long ago the Stop
        hook watched the turn behind it end. Separate seconds, because the case the
        second exists for is a start that is not old at all. `working` is a start on
        the page's own task, in the claimant's voice, with a `waiting` status of the
        same age beside it; anything else ends that task and writes the status. The
        answer is the page's agent and activity once they are written."""
        ts = datetime.now().astimezone() - timedelta(seconds=quiet_for)
        end_work(d)
        # What a transport watched for itself, written the way an App Server
        # observer writes it: bound to this session and its live turn.
        write_record(
            d / "stream.json",
            {}
            if stream is None
            else {
                "activity": {
                    "session": "s",
                    "turn": "turn-live",
                    "ts": ts.isoformat(timespec="seconds"),
                    "after": events_model.read_events(d)[-1]["seq"],
                }
                | stream
            },
        )
        if claimed:
            record_claim(
                d,
                id="s",
                pid=session_pid or os.getpid(),
                agent=agent,
                turn_closed=None
                if turn_ended is None
                else (
                    datetime.now().astimezone() - timedelta(seconds=turn_ended)
                ).isoformat(timespec="seconds"),
            )
        else:
            service_model.claim_path(d).unlink(missing_ok=True)
        declare_status(
            d,
            "waiting" if state == "working" else state,
            ts=ts.isoformat(timespec="seconds"),
        )
        if state == "working":
            declare_work(
                d,
                detail,
                ts=ts.isoformat(timespec="seconds"),
                **({"session": "s"} if claimed else {}),
            )
        state = page_state(d)
        return state["agent"], state["activity"]

    def minutes_old(activity):
        return round(
            (datetime.now().astimezone() - datetime.fromisoformat(activity["ts"]))
            / timedelta(minutes=1)
        )

    agent, activity = declare("working", "revising the plan")
    assert (agent, activity["kind"], activity["detail"]) == (
        "Claude",
        "working",
        "revising the plan",
    )
    assert activity["counts"]["pending"] == 1
    # A claim still believed but minutes old is dated by its own word.
    _, activity = declare("working", "revising the plan", quiet_for=5 * 60)
    assert (activity["kind"], minutes_old(activity)) == ("working", 5)

    [first_comment] = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(transaction, [first_comment], phase="queued")
    _, activity = declare("working", "revising the plan")
    assert activity["kind"] == "working"
    assert (activity["counts"]["queued"], activity["counts"]["pending"]) == (1, 0)

    # Picked up into the claimant's open turn before the agent has said anything: the
    # page is working, on the comment the turn picked up.
    with service_model.PageTransaction(d) as transaction:
        delivery_model.record_pickup(
            transaction, [first_comment], phase="opened", session="s", turn="turn-1"
        )
    # Fresh page work keeps its own sentence beside the comment the turn picked up.
    _, activity = declare("working", "revising the plan")
    assert (activity["kind"], activity["detail"]) == ("working", "revising the plan")
    assert (
        activity["counts"]["handling"],
        activity["counts"]["handling_comments"],
    ) == (1, 1)
    _, activity = declare("waiting")
    assert (activity["kind"], activity["detail"]) == ("working", "")
    assert (
        activity["counts"]["handling"],
        activity["counts"]["handling_comments"],
    ) == (1, 1)

    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": first_comment["id"],
            "responds": first_comment["id"],
            "text": "Handled before the next turn.",
        },
    )
    lease_path_8 = leases_model.waiter_lease_path(d, "s")
    assert lease_path_8 is not None
    lease = leases_model.take_wait_lease(lease_path_8)
    assert lease
    try:
        declare("working", "revising the plan")
        append_carried_log_record(
            d, {"kind": "comment", "author": "user", "text": "A later update."}
        )
        # A newer user input keeps its own pending delivery while the page's fresh
        # work declaration continues to describe what the agent is doing overall.
        activity = activity_reading(d)
        assert (activity["kind"], activity["detail"]) == (
            "working",
            "revising the plan",
        )
        assert activity["counts"]["pending"] == 1

        # A transport that can watch the session's own steps reports one beside the
        # agent's own sentence.
        _, activity = declare(
            "working",
            "revising the plan",
            stream={"kind": "tool", "detail": "Running the tests"},
        )
        assert (
            activity["kind"],
            activity["detail"],
            activity["observed_kind"],
            activity["observed"],
        ) == ("working", "revising the plan", "tool", "Running the tests")

        # A claim of work that has gone quiet is still a claim of work, and a live
        # watcher does not turn it into an invitation: it is the silence with no
        # watcher, dated by the claim's last word.
        _, activity = declare("working", "revising the plan", quiet_for=20 * 60)
        assert (activity["kind"], activity["dropped"], minutes_old(activity)) == (
            "stalled",
            False,
            20,
        )
        assert activity["detail"] == "revising the plan"

        # The same silence reached by evidence rather than by the clock: the Stop hook
        # watched the turn that wrote the claim end, and the silence is dated by that
        # ending, not by the claim's own last word.
        for quiet_for in (6 * 60, 5 * 60):
            _, activity = declare(
                "working", "revising the plan", quiet_for=quiet_for, turn_ended=5 * 60
            )
            assert (activity["kind"], activity["dropped"], minutes_old(activity)) == (
                "stalled",
                True,
                5,
            )

        # A turn that has only just ended still holds it, since an agent that ends its
        # turn with work running can be back a minute later; and a status written after
        # the turn closed carries the claim past the ending on its own.
        for turn_ended in (30, 5 * 60):
            _, activity = declare(
                "working", "revising the plan", quiet_for=60, turn_ended=turn_ended
            )
            assert activity["kind"] == "working"

        # Waiting on the user, with input on its way.
        _, activity = declare("waiting")
        assert (activity["kind"], activity["detail"]) == ("listening", "")
        assert activity["counts"]["pending"] == 1
    finally:
        leases_model.release_lease(lease)

    # No watcher, but Claude checked in moments ago, so it is between turns; and with
    # nobody listening and the turn over, an update that has only just arrived still
    # reads away, since the session's next turn takes it.
    _, activity = declare("waiting")
    assert (activity["kind"], activity["counts"]["overdue"]) == ("away", 0)
    _, activity = declare(
        "working", "running the migration", quiet_for=6 * 60, turn_ended=5 * 60
    )
    assert (activity["kind"], activity["counts"]["overdue"]) == ("away", 0)

    # Once an update has waited past the pickup grace with nothing to carry it, the
    # remedy is the user's, dated since nobody has been there.
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "text": "Still there?",
            "ts": (datetime.now().astimezone() - timedelta(minutes=3)).isoformat(
                timespec="seconds"
            ),
        },
    )
    _, activity = declare(
        "working", "running the migration", quiet_for=6 * 60, turn_ended=5 * 60
    )
    assert (activity["kind"], activity["dropped"], minutes_old(activity)) == (
        "away",
        True,
        5,
    )
    assert activity["counts"]["overdue"] == 1

    # Claude's own status gets a far longer rope: with no turn closed, the same
    # silence is just a long turn.
    _, activity = declare("working", "running the migration", quiet_for=10 * 60)
    assert activity["kind"] == "working"

    # A dead session needs no timeout: the owning pid is gone, so the claim it left has
    # nothing behind it however lately it was written.
    _, activity = declare("working", "running the migration", session_pid=dead_pid)
    assert activity["kind"] == "unheld"

    # Nothing ever claimed the page, as a server started outside an agent harness: a
    # claim of work made moments ago is evidence and still stands, and an hour of its
    # silence leaves nothing holding the page.
    agent, activity = declare("working", "running the migration", claimed=False)
    assert (agent, activity["kind"]) == ("Agent", "working")
    agent, activity = declare(
        "working", "running the migration", quiet_for=60 * 60, claimed=False
    )
    assert (agent, activity["kind"]) == ("Agent", "unheld")

    agent, activity = declare("working", "revising the plan", agent="Codex")
    assert (agent, activity["kind"]) == ("Codex", "working")

    _, activity = declare("idle")
    assert activity["kind"] == "closed"


def test_an_ended_pickup_keeps_the_invitation_the_agent_declared(page_dir):
    """A comment a turn picked up and ended without answering is still owed, but it is
    on its way to nobody, so a `waiting` the agent writes after the turn reads as its
    request to the user rather than as input it is listening for."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Comment 0."},
    )
    claim = record_claim(page_dir, id="s", pid=os.getpid(), agent="Claude")
    lease_path_9 = leases_model.waiter_lease_path(page_dir, "s")
    assert lease_path_9 is not None
    lease = leases_model.take_wait_lease(lease_path_9)
    assert lease
    try:
        with service_model.PageTransaction(page_dir) as transaction:
            delivery_model.record_pickup(transaction, [comment])
            cleanup_model.close_session_turn(claim["id"])
        result = CliRunner().invoke(cli_model.cli, ["page", "open", str(page_dir)])
        assert result.exit_code == 0, result.output
        state = page_state(page_dir)
    finally:
        leases_model.release_lease(lease)
    activity = state["activity"]
    assert (activity["kind"], activity["detail"]) == (
        "listening",
        "",
    )
    assert (activity["counts"]["pending"], activity["counts"]["queued"]) == (0, 0)
    [view] = state["browser"]["views"].values()
    assert [item["kind"] for item in view["queues"]["on_agent"]] == ["update"]


def test_newer_page_work_takes_the_activity_from_an_older_thread_start(page_dir):
    """The page's activity says the agent's latest word about what it is doing: a
    start on the page's own task after a start on a thread's comment replaces the
    thread's line there, while the thread keeps its own on its workflow."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Why?"},
    )
    record_claim(page_dir, id="s", pid=os.getpid(), agent="Claude")
    with service_model.PageTransaction(page_dir) as transaction:
        delivery_model.record_pickup(transaction, [comment])
    started = CliRunner().invoke(
        cli_model.cli,
        ["task", "start", str(page_dir), comment["id"], "--text", "reading the traces"],
    )
    assert started.exit_code == 0, started.output
    activity = activity_reading(page_dir)
    assert (activity["kind"], activity["detail"]) == ("working", "reading the traces")
    assert activity["detail_source"]["item"] == comment["id"]

    task = working(page_dir, "drafting v2")
    state = page_state(page_dir)
    assert (state["activity"]["kind"], state["activity"]["detail"]) == (
        "working",
        "drafting v2",
    )
    assert state["activity"]["detail_source"] == {
        "event_id": task["id"],
        "item": task["item"],
    }
    [workflow] = [w for w in state["workflows"] if w["input"] == comment["id"]]
    assert workflow["at_work"]
