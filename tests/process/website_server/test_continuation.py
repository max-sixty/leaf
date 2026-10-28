"""What a hosted turn hands on when it ends: the next owed move it reaches, and the
receipts for moves a continuation could not start."""

import json
import os
from types import SimpleNamespace

import pytest
from interact_support import append_carried_log_record as append_event
from interact_support import owed_answers
from websockets.exceptions import ConnectionClosedError

import leaf_website as website_server
from leaf.event_log import read_events
from leaf.interaction_log import read_interactions
from leaf.refusals import Refused
from leaf.state import session_record
from leaf.thread import cmd_resolve


def unfollowed_turn(harness, page_dir, *, following=None, event_ids=("first-event",)):
    """A turn whose own following is stood in for, to reach what comes after it.

    What a turn's ending hands on is the subject below, not how it ended, so these
    turns read no connection: `following` is what happens in place of the reading,
    and the default is a turn that ended without incident.
    """
    lifecycle = session_record("hosted-thread")
    assert lifecycle is not None

    class FollowingTurn(website_server.HostedTurn):
        def follow(self):
            if following is not None:
                following()

    turn = FollowingTurn(
        harness,
        page_dir,
        "hosted-thread",
        "delivery-1",
        event_ids,
        "provider-turn",
        lifecycle=lifecycle,
    )
    return turn


def test_a_turn_follower_releases_its_seat_before_continuing(page_dir, monkeypatch):
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")
    rescans = []

    def next_event(target, *, excluding):
        assert "hosted-thread" not in harness.following_threads
        rescans.append((target, excluding))
        return "next-event"

    monkeypatch.setattr(website_server, "next_unaccepted_agent_event", next_event)
    continued = []

    def attach(target, event_id):
        assert "hosted-thread" not in harness.following_threads
        assert not any(
            row["type"] == "turn_following_ended" for row in read_interactions(page_dir)
        )
        continued.append((target, event_id))
        return "hosted-thread"

    monkeypatch.setattr(harness, "attach", attach)
    harness._run_follow_turn(unfollowed_turn(harness, page_dir))

    assert rescans == [(page_dir, ("first-event",))]
    assert continued == [(page_dir, "next-event")]
    [ended] = [
        row
        for row in read_interactions(page_dir)
        if row["type"] == "turn_following_ended"
    ]
    assert ended["completed"] is True


def test_continuation_reaches_the_next_move_when_the_named_one_settles(
    page_dir, monkeypatch
):
    """A scan names a candidate, not a handoff; settlement there owes the next scan."""
    first, second = [
        append_event(page_dir, {"kind": "comment", "author": "user", "text": text})
        for text in ("first", "second")
    ]
    harness = website_server.WebsiteCodexHarness("codex")
    scan = website_server.next_unaccepted_agent_event

    def settling_scan(target, *, excluding):
        named = scan(target, excluding=excluding)
        if named == first["id"]:
            cmd_resolve(target, first["id"])
        return named

    starts = []

    def start(target, process, event_id):
        starts.append(event_id)
        harness.following_threads.add("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(website_server, "next_unaccepted_agent_event", settling_scan)
    monkeypatch.setattr(
        harness, "_ensure_server", lambda: SimpleNamespace(pid=os.getpid())
    )
    monkeypatch.setattr(harness, "_start_thread", start)
    harness._continue_page(page_dir, ())

    assert first["id"] not in website_server.pending_agent_inputs(page_dir)
    assert second["id"] in website_server.pending_agent_inputs(page_dir)
    assert starts == [second["id"]]


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Codex App Server did not start a turn: refused"),
        # The connection's own class, which descends from `Exception` alone: a start
        # can fail on the handshake or a dropped socket before it reaches the turn,
        # and the user is owed the same receipt either way.
        ConnectionClosedError(None, None),
    ],
    ids=["refused", "disconnected"],
)
def test_a_continuation_that_cannot_start_receipts_the_move_it_was_for(
    page_dir, monkeypatch, capsys, error
):
    """A move that arrived while a turn was running is the container's to answer for.

    Its own request was answered `started` on the running turn's thread, so the
    Worker's dispatch is over and the `startup_failed` receipt it writes when a start
    throws cannot reach this one. Nothing scans for the move again either — the scan
    that would find it is the one that just produced it — so a start that throws here
    leaves the user on a turn that never began unless this writes the receipt.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")

    def attach(target, event_id):
        raise error

    monkeypatch.setattr(harness, "attach", attach)
    harness._run_follow_turn(unfollowed_turn(harness, page_dir))

    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert receipt["responds"] == comment["id"]
    assert receipt["failure"] == "startup_failed"
    assert "Send it again to retry" in receipt["text"]
    [record] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if json.loads(line)["event"] == "container_continuation_receipted"
    ]
    assert (record["eventId"], record["settled"]) == (comment["id"], True)


def test_a_move_queued_behind_one_that_could_not_start_is_reached_too(
    page_dir, monkeypatch
):
    """Receipting a move the container could not start is not the end of the chain.

    A delivery carries at most one reply-owing move, so two messages sent during a
    turn are two obligations, both answered `started` on that turn's thread. The
    ending is the only scan either gets: one that stopped at the first failure would
    leave the second with no delivery, no dispatch and nothing coming, which reads as
    `listening` until the user sends a third.
    """
    comments = [
        append_event(page_dir, {"kind": "comment", "author": "user", "text": text})
        for text in ("edit the page", "and the title")
    ]
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")
    attempted = []

    def attach(target, event_id):
        attempted.append(event_id)
        raise RuntimeError("Codex App Server did not start a turn: refused")

    monkeypatch.setattr(harness, "attach", attach)
    harness._run_follow_turn(unfollowed_turn(harness, page_dir))

    assert attempted == [comment["id"] for comment in comments]
    receipts = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [receipt["responds"] for receipt in receipts] == attempted
    assert {receipt["failure"] for receipt in receipts} == {"startup_failed"}
    assert owed_answers(page_dir) == []


def test_a_follower_that_faults_still_hands_the_page_on(page_dir, monkeypatch):
    """The chain runs on what the page still owes, not on how the turn ended.

    A turn whose accounting throws — closing it re-reads the page, which its own work
    may have left unopenable — leaves exactly the moves outstanding that a clean one
    would. Gating the scan on a clean ending stranded them for the container's life.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")

    def fault():
        raise RuntimeError("closing the turn faulted")

    continued = []
    monkeypatch.setattr(
        harness, "attach", lambda target, event_id: continued.append(event_id)
    )

    with pytest.raises(RuntimeError, match="closing the turn faulted"):
        harness._run_follow_turn(unfollowed_turn(harness, page_dir, following=fault))

    assert continued == [comment["id"]]
    assert "hosted-thread" not in harness.following_threads
    [ended] = [
        row
        for row in read_interactions(page_dir)
        if row["type"] == "turn_following_ended"
    ]
    assert ended["completed"] is False


def test_a_refused_correction_receipt_still_hands_the_page_on(
    page_dir, monkeypatch, capsys
):
    """A correction turn that cannot restart receipts what it owed, and the page can
    refuse that receipt while a reply is still held. The refusal is recorded and
    the page's next move is still started."""
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")
    turn = unfollowed_turn(harness, page_dir)
    turn.correction = {"source": "index.html"}

    def no_server():
        raise RuntimeError("no App Server")

    def refused_receipt():
        raise Refused("failure receipts wait for this turn to release the answer")

    continued = []
    monkeypatch.setattr(harness, "_ensure_server", no_server)
    monkeypatch.setattr(turn, "_receipt_unanswered", refused_receipt)
    monkeypatch.setattr(
        harness, "attach", lambda target, event_id: continued.append(event_id)
    )
    harness._run_follow_turn(turn)

    assert continued == [comment["id"]]
    [record] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if json.loads(line)["event"] == "turn_receipt_refused"
    ]
    assert (
        record["detail"] == "failure receipts wait for this turn to release the answer"
    )


def test_an_ending_on_an_unopenable_page_still_answers_every_move(
    page_dir, monkeypatch
):
    """The page a turn left unopenable is the one whose ending has the most to say.

    Closing the turn re-reads the source, so a turn whose own work broke `index.html`
    faults there — the named fault class that reaches the hand-on. The hand-on has to
    answer for every move on that page, and it can: what it needs is the log, which
    reads fine. Refusing the scan on activation instead put a start-door condition in
    front of it, and it fired before any move was named, so none was receipted and
    the scan's complaint replaced the ending's own fault on the way out.
    """
    comments = [
        append_event(page_dir, {"kind": "comment", "author": "user", "text": text})
        for text in ("edit the page", "and the title")
    ]
    (page_dir / "index.html").write_text(
        "<!doctype html><html><body><main><section id='a'>hi</section></main>"
        "</body></html>"
    )
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")
    ending = ValueError("closing the turn faulted on the page it left")

    def fault():
        raise ending

    with pytest.raises(ValueError) as raised:
        harness._run_follow_turn(
            unfollowed_turn(harness, page_dir, following=fault, event_ids=())
        )

    # The ending's own fault, not the hand-on's complaint about the same page.
    assert raised.value is ending
    receipts = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [receipt["responds"] for receipt in receipts] == [
        comment["id"] for comment in comments
    ]
    assert {receipt["failure"] for receipt in receipts} == {"startup_failed"}
    assert owed_answers(page_dir) == []
