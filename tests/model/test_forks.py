"""Forked replies: each state a thread with waiting user messages moves through
(`forks.py`'s table), what Leaf holds from the session meanwhile, and what the
session hears once a fork has answered or handed the thread over."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    lock_contention,
    serving,
    stamp,
)

from leaf import clerk as clerk_model
from leaf import delivery as delivery_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import file_changes as file_changes_model
from leaf import forks as forks_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import presence as presence_model
from leaf import server_rows as server_rows_model
from leaf import session as session_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf.served_state.reading import outside_inputs
from leaf.service import PageTransaction
from leaf.state import session_file


def past_the_take() -> None:
    """Wait for the clock to leave the millisecond session s1's lane was taken in,
    since a message admitted within it stays with the session (`forks.held`)."""
    since = forks_model.lane_since("s1")
    assert since is not None
    while time.time() < since + 0.001:
        time.sleep(0.0005)


def take_lane():
    """Take session s1's forks lane, as its pages follower does, and wait past the
    take."""
    held = forks_model.take_lane("s1")
    past_the_take()
    return held


@pytest.fixture
def lane(claimed):
    """Session s1's forks lane, held as its pages follower holds it."""
    held = take_lane()
    yield held
    if not held.closed:
        leases_model.release_lease(held)


def said(page_dir, text: str, parent: str | None = None) -> dict:
    """The user's message, a comment opening a thread or a reply in one."""
    return append_carried_log_record(
        page_dir,
        {"kind": "reply", "parent": parent, "author": "user", "text": text}
        if parent
        else {"kind": "comment", "author": "user", "text": text},
    )


def held(page_dir) -> list:
    with PageTransaction(page_dir) as page:
        return [(thread.thread, thread.inputs) for thread in forks_model.held(page)]


def deliverable(page_dir) -> list[str]:
    with PageTransaction(page_dir) as page:
        return [event["id"] for event in delivery_model.deliverable(page)]


def basis(page_dir, thread: str, *inputs: str) -> dict:
    return {"page": str(page_dir), "thread": thread, "inputs": list(inputs)}


def context(capsys, event: str) -> str:
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": event, "session_id": "s1", "prompt_id": "p1"},
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def test_a_held_question_is_answered_by_its_fork_and_the_session_hears_it(
    claimed, lane, capsys
):
    """A message in a thread the session hasn't received is held: not deliverable,
    so neither a hook nor the watch hands it over, while a fork decides. Its reply
    goes in as the agent's and settles the thread, which then reaches the session at
    its next step with the reply in the thread's digest and a line saying a fork
    wrote it, and wakes no idle session."""
    asked = said(claimed, "Why a 2-second poll?")
    assert held(claimed) == [(asked["id"], (asked["id"],))]
    assert deliverable(claimed) == []

    question = forks_model.ask("s1", basis(claimed, asked["id"], asked["id"]), [])
    assert question is not None
    assert question["prompt"].startswith(forks_model.OPENING)
    assert "Why a 2-second poll?" in question["prompt"]
    assert "ends where the session last sent it to the model" in question["prompt"]

    outcome = forks_model.take(
        "s1",
        question["thread"],
        answer=json.dumps({"reply": "Presence rows go stale within 2 s."}),
        failed=None,
    )
    assert outcome["outcome"] == "reply"
    [reply] = [
        event
        for event in events_model.read_events(claimed)
        if event["id"] == outcome["reply"]
    ]
    assert (reply["author"], reply["session"], reply["responds"]) == (
        "agent",
        "s1",
        asked["id"],
    )
    assert held(claimed) == []
    assert deliverable(claimed) == [asked["id"]]
    with PageTransaction(claimed) as page:
        assert session_model.wake_inputs(page, delivery_model.deliverable(page)) == []

    told = context(capsys, "PostToolBatch")
    assert f"answered the user's message {asked['id']}" in told
    assert "Presence rows go stale within 2 s." in told
    assert clerk_model.queued("s1") == []


def test_a_hand_over_or_a_failed_fork_gives_the_thread_to_the_session_at_once(
    claimed, lane
):
    """The fork hands over what needs tools or work, and a fork that failed or gave
    an answer Leaf can't read hands over too. Each is recorded where the watch's
    reading stamps it, and the thread is deliverable at once."""
    work = said(claimed, "Make it 1 second")
    broken = said(claimed, "What does the follower print?")
    failed = said(claimed, "And the lane?")
    assert {thread for thread, _ in held(claimed)} == {
        work["id"],
        broken["id"],
        failed["id"],
    }

    assert forks_model.take(
        "s1",
        basis(claimed, work["id"], work["id"]),
        answer=json.dumps({"hand_over": "asks for a change"}),
        failed=None,
    ) == {"outcome": "hand_over", "why": "asks for a change"}
    assert forks_model.take(
        "s1",
        basis(claimed, broken["id"], broken["id"]),
        answer="I think the follower prints pages.",
        failed=None,
    )["outcome"] == ("hand_over")
    assert forks_model.take(
        "s1", basis(claimed, failed["id"], failed["id"]), answer=None, failed="aborted"
    ) == {"outcome": "hand_over", "why": "the fork failed: aborted"}

    assert held(claimed) == []
    assert deliverable(claimed) == [work["id"], broken["id"], failed["id"]]
    assert session_file("s1", forks_model.HANDED.kind).resolve() in outside_inputs(
        claimed
    )
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )


def test_a_hold_ends_with_its_bound_or_its_lane(claimed, lane, monkeypatch):
    """However the fork fares, the lane hands the messages to the session once
    `BOUND_S` has passed since the newest of them, nudging a session no watch
    follows as admission would have; and they are deliverable once the follower
    holding the lane exits."""
    nudged = []
    monkeypatch.setattr(
        presence_model, "nudge_unwatched", lambda page: nudged.append(page.page_dir)
    )
    asked = said(claimed, "Is the bound from the newest message?")
    admitted = datetime.fromisoformat(asked["ts"]).timestamp()
    [still] = forks_model.look("s1", claimed, now=admitted + forks_model.BOUND_S - 1)
    assert still.thread == asked["id"]
    assert deliverable(claimed) == []
    assert forks_model.look("s1", claimed, now=admitted + forks_model.BOUND_S) == []
    assert deliverable(claimed) == [asked["id"]]
    assert nudged == [claimed.resolve()]

    other = said(claimed, "And without a lane?")
    assert held(claimed) == [(other["id"], (other["id"],))]
    leases_model.release_lease(lane)
    assert held(claimed) == []
    assert deliverable(claimed) == [asked["id"], other["id"]]


def test_without_a_lane_nothing_is_held(claimed):
    """A session without Leaf's hooks module, or any other harness, delivers as
    before."""
    asked = said(claimed, "Anyone there?")
    assert held(claimed) == []
    assert deliverable(claimed) == [asked["id"]]


def test_a_message_while_held_starts_a_fork_for_both_and_drops_the_first_answer(
    claimed, lane
):
    """A second message in a held thread keeps it held, now with both, and the fork
    asked about the first alone writes nothing: the thread's newest message carries
    its one answer."""
    first = said(claimed, "Why 30 s?")
    second = said(claimed, "Or rather, why not 20?", parent=first["id"])
    assert held(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert forks_model.ask("s1", basis(claimed, first["id"], first["id"]), []) is None

    assert forks_model.take(
        "s1",
        basis(claimed, first["id"], first["id"]),
        answer=json.dumps({"reply": "Thirty covers a cold cache."}),
        failed=None,
    ) == {"outcome": "dropped", "text": "Thirty covers a cold cache."}
    assert held(claimed) == [(first["id"], (first["id"], second["id"]))]
    assert not any(
        event["kind"] == "reply" and event["author"] == "agent"
        for event in events_model.read_events(claimed)
    )


def test_a_thread_the_session_owes_stays_with_it_and_a_follow_up_is_forked(
    claimed, lane, capsys
):
    """Once the session has received a thread's message, a message after it in that
    thread goes to the session too; once the agent has answered, the user's
    follow-up is held again, and its fork sees the earlier exchange."""
    asked = said(claimed, "Where does the hold live?")
    leases_model.release_lease(lane)
    assert "Where does the hold live?" in context(capsys, "UserPromptSubmit")
    lane = take_lane()
    more = said(claimed, "And who reads it?", parent=asked["id"])
    assert held(claimed) == []
    assert more["id"] in deliverable(claimed)
    leases_model.release_lease(lane)

    context(capsys, "PostToolBatch")
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s1"})
    capsys.readouterr()
    thread_model.post_reply(
        claimed, {"responds": more["id"]}, "In `delivery.deliverable`."
    )
    lane = take_lane()
    follow_up = said(claimed, "Thanks. Does the watch read it too?", parent=asked["id"])
    assert held(claimed) == [(asked["id"], (follow_up["id"],))]
    question = forks_model.ask("s1", basis(claimed, asked["id"], follow_up["id"]), [])
    assert question is not None
    assert "In `delivery.deliverable`." in question["prompt"]
    leases_model.release_lease(lane)


def test_the_session_taking_the_message_first_leaves_the_fork_nothing_to_write(
    claimed, lane, capsys
):
    """A held message the session picks up anyway, as once the bound has passed, is
    the session's: the fork's later answer writes nothing."""
    asked = said(claimed, "Which wins?")
    with PageTransaction(claimed) as page:
        [event] = [e for e in page.events if e["id"] == asked["id"]]
        delivery_model.record_pickup(page, [event], session="s1", turn="t1")
    assert held(claimed) == []
    assert forks_model.take(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=json.dumps({"reply": "The fork."}),
        failed=None,
    ) == {"outcome": "dropped", "text": "The fork."}


def test_a_hold_ending_while_the_reply_goes_in_leaves_the_thread_to_the_session(
    claimed, lane, monkeypatch
):
    """The reply is fenced to the hold under the lock its append takes, so the lane
    handing the thread over while the reply is on its way in leaves it wholly to the
    session, which a delivery prepared then would otherwise tell to answer it
    again."""
    asked = said(claimed, "Is the fence inside the append?")
    checked = thread_model.checked_text

    def bound_passes(page_dir, text):
        forks_model.look("s1", claimed, now=float("inf"))
        return checked(page_dir, text)

    monkeypatch.setattr(thread_model, "checked_text", bound_passes)
    assert forks_model.take(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        answer=json.dumps({"reply": "Yes."}),
        failed=None,
    ) == {"outcome": "dropped", "text": "Yes."}
    assert deliverable(claimed) == [asked["id"]]
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(claimed)
    )


def test_a_thread_the_lane_going_down_gave_over_stays_with_the_session(claimed, lane):
    """A lane holds only what arrived while it ran: once it goes down, the next lane
    leaves its threads to the session, and the old fork's reply writes nothing,
    since a delivery may already be telling the session to answer them."""
    asked = said(claimed, "Still held after a restart?")
    leases_model.release_lease(lane)
    assert deliverable(claimed) == [asked["id"]]
    again = take_lane()
    try:
        assert held(claimed) == []
        assert forks_model.take(
            "s1",
            basis(claimed, asked["id"], asked["id"]),
            answer=json.dumps({"reply": "Yes."}),
            failed=None,
        ) == {"outcome": "dropped", "text": "Yes."}
    finally:
        leases_model.release_lease(again)


def test_a_fork_the_page_has_since_left_writes_nothing_on_it(claimed, lane):
    """The hold is the claimant's: a fork of another session's conversation, as one
    returning after the page passed to a new session, neither hands the thread over
    nor answers it."""
    asked = said(claimed, "Who holds this?")
    for answer in ({"hand_over": "needs a look"}, {"reply": "The other session."}):
        assert (
            forks_model.take(
                "s2",
                basis(claimed, asked["id"], asked["id"]),
                answer=json.dumps(answer),
                failed=None,
            )["outcome"]
            == "dropped"
        )
    assert held(claimed) == [(asked["id"], (asked["id"],))]
    assert not session_file("s2", forks_model.HANDED.kind).exists()


def test_the_running_tool_reaches_the_prompt(claimed, lane):
    """Mid-turn, the session's last request predates the call it is running, so the
    fork's prompt names that call."""
    asked = said(claimed, "What are you running?")
    question = forks_model.ask(
        "s1",
        basis(claimed, asked["id"], asked["id"]),
        [{"tool": "Bash", "input": {"command": "pytest -x", "description": "tests"}}],
    )
    assert question is not None
    assert 'Bash command: "pytest -x" description: "tests"' in question["prompt"]


def test_the_pages_follower_holds_the_lane_and_lists_held_threads(
    claimed, monkeypatch, capsys
):
    """Asked for forks, the follower is the session's lane while it runs and lists
    each page's held threads for the module, without a native subscription; stopping
    with a thread held, it nudges what the hold leaves, as a watch giving up its
    lease does."""
    serving(claimed, 1)
    server_rows_model.RowPublisher(claimed, "fixture-server").refresh()
    nudged = []
    monkeypatch.setattr(session_model, "nudge_pending", nudged.append)
    asked = []

    class Stopped(Exception):
        pass

    def forbidden(*_args, **_kwargs):
        pytest.fail("the page list allocated a native subscription")

    def wait(_seconds):
        if asked:
            raise Stopped
        past_the_take()
        asked.append(said(claimed, "Is anyone forking?"))

    monkeypatch.setattr(file_changes_model, "FileChanges", forbidden)
    monkeypatch.setattr(
        hooks_model, "time", SimpleNamespace(sleep=wait, time=time.time)
    )
    with pytest.raises(Stopped):
        hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert forks_model.lane_since("s1") is None
    listed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert listed[0][0]["forks"] == []
    assert listed[1][0]["forks"] == [
        {
            "page": str(claimed.resolve()),
            "thread": asked[0]["id"],
            "inputs": [asked[0]["id"]],
        }
    ]
    assert nudged == ["s1"]


def test_the_follower_keeps_the_bound_of_a_page_it_does_not_list(
    claimed, monkeypatch, capsys
):
    """A page whose server isn't running goes unlisted, yet the follower still hands
    its held threads to the session at their bound. That hand-over nudges for itself,
    so a follower that then exits holding nothing sends no nudge of its own, which
    could wake a session its Stop hook's watch is about to wake."""
    monkeypatch.setattr(forks_model, "BOUND_S", 0.0)
    nudged = []
    monkeypatch.setattr(session_model, "nudge_pending", nudged.append)
    asked = []

    def wait(_seconds):
        if not asked:
            past_the_take()
            asked.append(said(claimed, "Is anyone serving this?"))
        else:
            state_model.end_session("s1")

    monkeypatch.setattr(
        hooks_model, "time", SimpleNamespace(sleep=wait, time=time.time)
    )
    hooks_model.cmd_pages({"session_id": "s1", "forks": True})
    assert capsys.readouterr().out.splitlines() == ["[]"]
    assert forks_model.handed_inputs("s1", claimed) == {asked[0]["id"]}
    assert nudged == []


def test_a_lane_counts_from_when_it_took_the_name(claimed, lane, monkeypatch):
    """A follower writes its lease before renaming it into place, and a message can
    arrive, and the earlier lane go down, in between: the new lane counts from the
    rename, so it leaves that message to the session and the earlier fork's reply
    writes nothing, even when the filesystem clock trails the admission clock."""
    replace = os.replace
    stat = Path.stat
    lane_path = forks_model.lane_path("s1")
    asked = []

    def coarse_clock(path, *args, **kwargs):
        result = stat(path, *args, **kwargs)
        if path == lane_path:
            return os.stat_result((*result[:9], 0))
        return result

    def publish(staged, path):
        monkeypatch.setattr(os, "replace", replace)
        asked.append(said(claimed, "Arrived while the next follower started?"))
        leases_model.release_lease(lane)
        replace(staged, path)

    monkeypatch.setattr(os, "replace", publish)
    monkeypatch.setattr(Path, "stat", coarse_clock)
    again = forks_model.take_lane("s1")
    try:
        assert held(claimed) == []
        assert deliverable(claimed) == [asked[0]["id"]]
        assert (
            forks_model.take(
                "s1",
                basis(claimed, asked[0]["id"], asked[0]["id"]),
                answer=json.dumps({"reply": "Yes."}),
                failed=None,
            )["outcome"]
            == "dropped"
        )
    finally:
        leases_model.release_lease(again)


def test_admission_waits_for_the_lane_cutoff_to_be_published(claimed, monkeypatch):
    """An event admitted after the cutoff waits for publication before deciding
    whether to nudge the session. It cannot be deliverable now and held later."""
    assert stamp(claimed).exit_code == 0
    before = said(claimed, "Before the lane started")
    write = forks_model.LANE_START.write
    publishing, release = Event(), Event()
    sampled = []
    nudged = []

    def publish(path, value):
        sampled.append(value["since"])
        publishing.set()
        assert release.wait(STATED_TIMEOUT)
        return write(path, value)

    monkeypatch.setattr(forks_model.LANE_START, "write", publish)
    monkeypatch.setattr(
        endpoint_model, "nudge_unwatched", lambda page: nudged.append(page.page_dir)
    )
    monkeypatch.setattr(
        endpoint_model,
        "claim_harness",
        lambda _claim: SimpleNamespace(title_generator=lambda: None),
    )
    blocked = lock_contention(monkeypatch, forks_model.lane_lock_path("s1"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        taking = executor.submit(forks_model.take_lane, "s1")
        try:
            assert publishing.wait(STATED_TIMEOUT)
            after_cutoff = (
                datetime.fromtimestamp(sampled[0] + 0.002)
                .astimezone()
                .isoformat(timespec="milliseconds")
            )
            monkeypatch.setattr(events_model, "now_iso", lambda: after_cutoff)
            admitting = executor.submit(
                endpoint_model.accept_event,
                claimed,
                {"kind": "comment", "revision": 1, "text": "During publication"},
                dict,
            )
            assert blocked.wait(STATED_TIMEOUT), (
                "admission did not wait for publication"
            )
        finally:
            release.set()
        lane = taking.result(timeout=STATED_TIMEOUT)
        try:
            status, answer = admitting.result(timeout=STATED_TIMEOUT)
            assert status == 200, answer
            [asked] = [
                event
                for event in events_model.read_events(claimed)
                if event.get("text") == "During publication"
            ]
            assert nudged == []
            assert held(claimed) == [(asked["id"], (asked["id"],))]
            assert deliverable(claimed) == [before["id"]]
        finally:
            leases_model.release_lease(lane)
