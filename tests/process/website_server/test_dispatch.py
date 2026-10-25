"""How the website harness attaches a user's move to a Codex thread and starts its turn,
and what a failed or unnamed start leaves the user."""

import json
import os
import shutil
import threading
from types import SimpleNamespace

import leaf_website as website_server
import pytest
from conftest import app_server_message_error
from interact_support import (
    STATED_TIMEOUT,
    activity_reading,
    refused_on,
    running_http_server,
    status_and_stream,
    wait_for,
)
from interact_support import append_carried_log_record as append_event
from websockets.exceptions import ConnectionClosedError

from leaf import codex as leaf_codex
from leaf.codex import AppServerRequestRejected, delivery_records
from leaf.event_log import read_events
from leaf.hosting import LeafHTTPServer
from leaf.refusals import Refused
from leaf.state import session_record
from leaf.thread import post_reply
from process.website_server import (
    FakeCodexHarness,
    accept_in_turn,
    post,
    write_manifest,
)


@pytest.mark.parametrize("status", ["active", "idle", "systemError", "notLoaded"])
def test_the_website_harness_delivers_into_the_existing_codex_thread(
    page_dir, tmp_path, monkeypatch, status
):
    harness = website_server.WebsiteCodexHarness(
        "codex",
        tmp_path / "app-server.log",
    )
    process = type("Process", (), {"pid": 41})()
    monkeypatch.setattr(harness, "_ensure_server", lambda: process)
    monkeypatch.setattr(
        website_server,
        "page_claim",
        lambda page: {"id": "hosted-thread", "harness": "embedded"},
    )
    reserved = []
    monkeypatch.setattr(
        "leaf.thread.reserve_delivery_reply",
        lambda *args: reserved.append(args),
    )
    requests = []
    follows = []

    def request(resources, method, params):
        requests.append((method, params))
        return (
            "socket",
            {"thread": {"id": "hosted-thread", "status": {"type": status}}},
            [],
        )

    monkeypatch.setattr(harness, "_request", request)
    monkeypatch.setattr(
        harness, "_follow", lambda turn, resources: follows.append(turn)
    )
    monkeypatch.setattr(harness, "_hold_waiter", lambda *_: None)
    started = []
    monkeypatch.setattr(
        harness,
        "_start_turn",
        lambda *args: started.append(args) or ("hosted-thread", "turn-2"),
    )
    closed = []
    monkeypatch.setattr(
        website_server,
        "close_session_turn",
        lambda *args: closed.append(args),
    )
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *_: SimpleNamespace(
            prompt="delivery-pointer",
            payload={
                "id": "delivery-1",
                "batches": [
                    {
                        "page": str(page_dir),
                        "events": [
                            {
                                "id": "user-event",
                                "answer": {
                                    "kind": "reply",
                                    "writer": "turn",
                                    "parent": "user-event",
                                    "responds": "user-event",
                                    "attempt": "leaf-delivery-1",
                                },
                            }
                        ],
                    }
                ],
            },
        ),
    )
    monkeypatch.setattr(
        website_server,
        "pending_agent_inputs",
        lambda *_: {"user-event": "hosted-thread" if follows or started else None},
    )
    interrupted = []
    monkeypatch.setattr(
        harness,
        "_end_unfollowed_turn",
        lambda socket, thread, pending, event: interrupted.append((thread, event)),
    )

    thread_id = harness.attach(page_dir, "user-event")

    assert thread_id == "hosted-thread"
    assert requests == [
        (
            "thread/resume",
            {
                "threadId": "hosted-thread",
                "cwd": str(page_dir),
                "excludeTurns": True,
            },
        )
    ]
    # However the thread was left, the user's message starts a turn of its own.
    # A thread still running one has it stopped first, since that turn is answering
    # into a container that stopped watching it.
    assert interrupted == (
        [("hosted-thread", "user-event")] if status == "active" else []
    )
    assert started == [("socket", page_dir, "hosted-thread", process, [])]
    assert reserved == []
    assert closed == [("hosted-thread",)]
    assert len(follows) == 1


def test_an_active_thread_has_its_unwatched_turn_stopped_before_the_next_starts(
    page_dir, monkeypatch
):
    """A running turn nothing follows is ended, not queued behind.

    Every follower stops its own turn before it stops, so a thread that resumes
    active is one whose container died mid-turn: that turn answers into nothing and
    holds the thread against the user waiting behind it. App Server takes the
    interrupt without a turn id and says the turn ended on the same subscription,
    which is what makes the thread the new delivery's.
    """
    declared = website_server.website_harness("hosted-thread", os.getpid())
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    website_server.prepare_codex_delivery(page_dir, declared)
    accept_in_turn("hosted-thread", "active-turn")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    sent = []

    class Socket:
        def recv(self, timeout):
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "active-turn",
                            "status": "interrupted",
                            "items": [],
                        },
                    },
                }
            )

    def send(socket, method, params, pending=None):
        sent.append((method, params))
        if method == "turn/start":
            return {"turn": {"id": "second-turn"}}
        return {}

    def request(resources, method, params):
        return (
            Socket(),
            {
                "thread": {
                    "id": "hosted-thread",
                    "status": {"type": "active", "activeFlags": []},
                }
            },
            [],
        )

    monkeypatch.setattr(harness, "_request", request)
    monkeypatch.setattr(harness, "_follow", lambda *_: None)
    monkeypatch.setattr(harness, "_send", send)
    monkeypatch.setattr(harness, "_hold_waiter", lambda *_: None)
    assert harness._resume_and_start(
        page_dir,
        "hosted-thread",
        process,
        second["id"],
    )
    assert [method for method, _ in sent] == ["turn/interrupt", "turn/start"]
    assert sent[0][1] == {"threadId": "hosted-thread", "turnId": ""}
    for method, params in sent:
        request = {"method": method, "id": 0, "params": params}
        assert app_server_message_error(request, "Client") is None
    assert app_server_message_error(json.loads(Socket().recv(1)), "Server") is None
    assert sent[1][1]["clientUserMessageId"]
    [(_, queue)] = delivery_records("hosted-thread")
    assert queue.state == "offering"


def test_attach_accepts_its_named_event_after_an_older_reply_slice(
    page_dir, monkeypatch
):
    first = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    harness = website_server.WebsiteCodexHarness("codex")

    class Process:
        pid = os.getpid()

    process = Process()
    deliveries = []

    def accept(turn):
        prepared = website_server.prepare_codex_delivery(
            page_dir, website_server.website_harness("hosted-thread", process.pid)
        )
        deliveries.append(
            [
                event["id"]
                for batch in prepared.payload["batches"]
                for event in batch["events"]
            ]
        )
        accept_in_turn("hosted-thread", turn)

    def start_thread(*args):
        accept("first-turn")
        return "hosted-thread"

    def resume_and_start(*args):
        accept("second-turn")
        return True

    monkeypatch.setattr(harness, "_ensure_server", lambda: process)
    monkeypatch.setattr(harness, "_start_thread", start_thread)
    monkeypatch.setattr(harness, "_resume_and_start", resume_and_start)

    assert harness.attach(page_dir, second["id"]) == "hosted-thread"
    assert deliveries == [[first["id"]], [second["id"]]]
    assert (
        website_server.pending_agent_inputs(page_dir)[second["id"]] == "hosted-thread"
    )


@pytest.mark.parametrize("existing_claim", [False, True], ids=["unclaimed", "claimed"])
def test_attach_rechecks_a_move_answered_while_the_provider_starts(
    page_dir, monkeypatch, existing_claim
):
    """Provider startup releases the page lock; an answer there needs no new turn."""
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    if existing_claim:
        with website_server.PageTransaction(page_dir) as page:
            page.take_claim(
                website_server.website_harness("previous-thread", os.getpid())
            )

    def ensure_server():
        website_server.write_failure_receipt(page_dir, comment["id"], "startup_failed")
        return SimpleNamespace(pid=os.getpid())

    monkeypatch.setattr(harness, "_ensure_server", ensure_server)
    monkeypatch.setattr(
        harness,
        "_start_thread",
        lambda *_: pytest.fail("the answered move started a turn"),
    )
    monkeypatch.setattr(
        harness,
        "_resume_and_start",
        lambda *_: pytest.fail("the answered move resumed a turn"),
    )
    assert harness.attach(page_dir, comment["id"]) is None
    assert website_server.pending_agent_inputs(page_dir) == {}


def test_attach_leaves_an_uncertain_delivery_to_its_reconciliation_follower(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    monkeypatch.setattr(harness, "_ensure_server", lambda: process)
    dispatches = []

    def uncertain_start(target, running, event_id):
        prepared = website_server.prepare_codex_delivery(
            target, website_server.website_harness("hosted-thread", running.pid)
        )
        dispatches.append((event_id, prepared.payload["id"]))
        harness.following_threads.add("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(harness, "_start_thread", uncertain_start)
    monkeypatch.setattr(
        harness,
        "_resume_and_start",
        lambda *_: pytest.fail("the attach loop redispatched an uncertain delivery"),
    )

    assert harness.attach(page_dir, comment["id"]) == "hosted-thread"
    assert harness.attach(page_dir, comment["id"]) == "hosted-thread"
    assert len(dispatches) == 1


def test_a_thread_opened_during_a_hosted_turn_is_named_as_it_is_dispatched(
    page_dir, monkeypatch
):
    """A move dispatched while a turn runs waits for that turn to end before a turn
    answers it, but its thread is named as it arrives, and asked about once: the
    turn that later answers it finds it named."""
    with website_server.PageTransaction(page_dir) as page:
        page.take_claim(website_server.website_harness("hosted-thread", os.getpid()))
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Why is the export slow?"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    harness.following_threads.add("hosted-thread")
    monkeypatch.setattr(
        harness, "_ensure_server", lambda: SimpleNamespace(pid=os.getpid())
    )
    requests = []

    def app_server_title(endpoint):
        def generate(request, target):
            requests.append((endpoint, request))
            return {"title": "Export speed"}

        return generate

    monkeypatch.setattr(website_server, "app_server_title", app_server_title)
    try:
        assert harness.attach(page_dir, comment["id"]) == "hosted-thread"
        [title] = wait_for(
            lambda: [e for e in read_events(page_dir) if e["kind"] == "thread_title"],
            bool,
            failure="the thread was never named",
        )
        assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
        [(endpoint, request)] = requests
        assert endpoint == harness.endpoint
        assert "Why is the export slow?" in request

        def resume_and_start(target, thread_id, process, event_id):
            harness.following_threads.add(thread_id)
            return True

        harness.following_threads.clear()
        monkeypatch.setattr(harness, "_resume_and_start", resume_and_start)
        assert harness.attach(page_dir, comment["id"]) == "hosted-thread"
        for worker in threading.enumerate():
            if worker.name == "leaf-thread-title":
                worker.join(timeout=STATED_TIMEOUT)
        assert len(requests) == 1
    finally:
        harness.close()


def test_a_start_that_fails_on_its_connection_is_recorded_like_any_other(
    page_dir, monkeypatch, capsys
):
    """`attach` records whatever the start raised, whichever class it belongs to.

    A connection that refuses its handshake or drops mid-request raises the
    `websockets` class, which descends from `Exception` alone rather than from any
    of the three a named list held, so a start that failed on the one thing every
    start needs was the one that went unrecorded.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")

    def refuse():
        raise ConnectionClosedError(None, None)

    monkeypatch.setattr(harness, "_ensure_server", refuse)
    with pytest.raises(ConnectionClosedError):
        harness.attach(page_dir, comment["id"])

    [record] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if json.loads(line)["event"] == "container_start_failed"
    ]
    assert (record["eventId"], record["error"]) == (
        comment["id"],
        "ConnectionClosedError",
    )


def test_a_follower_that_cannot_start_releases_its_delivery(page_dir, monkeypatch):
    """A refused background thread must leave the Worker's failure receipt writable."""
    event = append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "edit the page"}
    )
    harness = website_server.WebsiteCodexHarness("codex")
    closed = []
    interrupted = []
    socket = SimpleNamespace(close=lambda: closed.append(True))

    def request(resources, method, params):
        resources.callback(socket.close)
        return socket, {"thread": {"id": "hosted-thread"}}, []

    def refuse_start(_thread):
        raise OSError("no thread resources")

    monkeypatch.setattr(harness, "_request", request)
    monkeypatch.setattr(
        harness, "_send", lambda *_: {"turn": {"id": "unfollowed-turn"}}
    )
    monkeypatch.setattr(
        harness, "_interrupt", lambda *args, **_: interrupted.append(args)
    )
    monkeypatch.setattr(threading.Thread, "start", refuse_start)
    try:
        with pytest.raises(OSError, match="no thread resources"):
            harness._start_thread(
                page_dir, SimpleNamespace(pid=os.getpid()), event["id"]
            )
        assert harness.following_threads == set()
        assert closed == [True]
        assert interrupted == [("hosted-thread", "")]
        assert session_record("hosted-thread")["turn_closed"] is not None
        assert website_server.write_failure_receipt(
            page_dir, event["id"], "startup_failed"
        )
    finally:
        harness.close()


def test_duplicate_attaches_share_one_delivery_start(page_dir, monkeypatch):
    harness = website_server.WebsiteCodexHarness("codex")
    process = type("Process", (), {"pid": 41})()
    started = threading.Event()
    release = threading.Event()
    second_called = threading.Event()
    accepted = []
    start_calls = []

    monkeypatch.setattr(
        website_server,
        "pending_agent_inputs",
        lambda *_: {"user-event": accepted[0] if accepted else None},
    )
    monkeypatch.setattr(harness, "_ensure_server", lambda: process)
    monkeypatch.setattr(website_server, "page_claim", lambda page: None)

    def start_thread(*args):
        start_calls.append(None)
        started.set()
        release.wait(timeout=STATED_TIMEOUT)
        accepted.append("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(harness, "_start_thread", start_thread)
    attached = []
    first = threading.Thread(
        target=lambda: attached.append(harness.attach(page_dir, "user-event"))
    )

    def attach_second():
        second_called.set()
        attached.append(harness.attach(page_dir, "user-event"))

    second = threading.Thread(target=attach_second)
    first.start()
    assert started.wait(timeout=STATED_TIMEOUT), (
        "the first attach never started its turn"
    )
    second.start()
    assert second_called.wait(timeout=STATED_TIMEOUT), (
        "the second attach was never called"
    )
    release.set()
    first.join(timeout=STATED_TIMEOUT)
    assert not first.is_alive(), "the first attach never returned"
    second.join(timeout=STATED_TIMEOUT)
    assert not second.is_alive(), "the second attach never returned"

    assert attached == ["hosted-thread", "hosted-thread"]
    assert start_calls == [None]


@pytest.mark.parametrize(
    "refusal",
    [
        AppServerRequestRejected("rejected"),
        TimeoutError("lost ack"),
        None,
    ],
    ids=["refused", "lost", "unnamed"],
)
def test_a_start_that_names_no_turn_gives_the_user_their_message_back(
    page_dir, monkeypatch, refusal
):
    """A dispatch that cannot name a turn withdraws, rather than going looking.

    There is nothing to follow and possibly something running: a lost
    acknowledgement is a request App Server may well have acted on. So the
    provider is told to stop whatever it started, and the delivery gives the
    moves back — both the offer and its reply reservation, because either
    left held blocks the `startup_failed` receipt this raise asks the Worker
    for, and that receipt is what invites the user to send again.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    competing_writer_rejected = []

    def refuse(*args, **kwargs):
        with pytest.raises(Refused) as refused:
            post_reply(
                page_dir,
                {"parent": comment["id"], "responds": comment["id"]},
                "Competing tool reply",
                identity={"agent": "Codex", "session": "hosted-thread"},
            )
        assert refused_on(refused.value).code == "reserved-answer"
        competing_writer_rejected.append(True)
        if refusal is None:
            return {"turn": {}}
        raise refusal

    interrupts = []
    monkeypatch.setattr(harness, "_send", refuse)
    monkeypatch.setattr(
        harness,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    with pytest.raises(RuntimeError, match="did not start a turn"):
        harness._start_turn(
            "socket",
            page_dir,
            "hosted-thread",
            type("Process", (), {"pid": os.getpid()})(),
        )

    assert interrupts == [("hosted-thread", "")]
    assert delivery_records("hosted-thread") == []
    assert competing_writer_rejected == [True]
    assert website_server.page_claim(page_dir) is None
    activity = activity_reading(page_dir)
    assert activity["observed_kind"] is None
    assert [item["stage"] for item in activity["obligations"]] == ["sent"]
    # The reply reservation is released, so the Worker's own receipt reaches the user.
    assert (
        website_server.write_failure_receipt(page_dir, comment["id"], "startup_failed")
        is not None
    )


def test_an_acknowledged_start_answers_a_user_with_no_turn_started_notification(
    page_dir, monkeypatch
):
    """App Server's answer to `turn/start` is the binding, not a timing record.

    The request carries the delivery both as its `clientUserMessageId` and as its
    `leaf_delivery` tool output, so the turn the response names is the turn that
    took this delivery. Waiting for a notification to repeat that leaves the
    follower unbound, and an unbound follower has no turn whose terminal status it
    can read: nothing it receives finishes it, and nothing it loses recovers it.
    The stream below carries the whole turn except the one notification that names
    the delivery, which is the shape behind a page that read `working: Starting`
    for ten minutes while its agent published.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(
        harness, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
    )
    answer = {
        "id": "answer",
        "type": "agentMessage",
        "phase": "final_answer",
        "text": "Deployment verified.",
    }
    messages = iter(
        [
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "app-server-turn",
                        "completedAtMs": 1_000,
                        "item": answer,
                    },
                }
            ),
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [answer],
                        },
                    },
                }
            ),
        ]
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            return next(messages)

        def close(self):
            self.closed = True

    socket = Socket()
    follow = harness._start_turn(
        socket,
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    follow.follow()
    events = read_events(page_dir)
    activity = activity_reading(page_dir)
    harness.close()

    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["text"]) == (comment["id"], "Deployment verified.")
    assert "failure" not in reply
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert (activity["kind"], activity["obligations"]) == ("listening", [])
    assert socket.closed


def test_a_retried_agent_start_returns_the_accepted_task(page_dir, tmp_path):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    comment = append_event(
        published,
        {"kind": "comment", "author": "user", "text": "edit this"},
    )
    website_server.prepare_codex_delivery(
        published,
        website_server.website_harness("already-started-thread", os.getpid()),
    )
    accept_in_turn("already-started-thread")
    agent_harness = FakeCodexHarness()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_harness)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        answer, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )

        assert answer == {"status": "started", "thread": "already-started-thread"}
        assert agent_harness.attached == []


@pytest.mark.parametrize("replacement", ["generation", "prompt"])
def test_hosted_start_retains_its_admitted_epoch_until_it_begins(
    page_dir, monkeypatch, replacement
):
    from leaf.state import end_session, prompt_turn

    append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "An old request"}
    )
    harness = website_server.WebsiteCodexHarness("codex")
    monkeypatch.setattr(
        harness, "_send", lambda *args: {"turn": {"id": "started-turn"}}
    )
    winner = {}

    def competing_work(event, **fields):
        if event != "turn_start_acknowledged":
            return
        if replacement == "generation":
            end_session("hosted-thread")
            prompt_turn("hosted-thread", "started-turn")
        else:
            prompt_turn("hosted-thread", "new-turn")
        with website_server.PageTransaction(page_dir) as page:
            page.take_claim(
                website_server.website_harness("hosted-thread", os.getpid())
            )
            page.set_status("waiting")
        current = session_record("hosted-thread")
        leaf_codex.set_stream_activity(
            "hosted-thread",
            current["turn"],
            {"kind": "tool", "detail": "New activity"},
            expected=current,
        )
        winner["epoch"] = current
        winner["status"] = status_and_stream(page_dir)

    monkeypatch.setattr(website_server, "log_agent", competing_work)
    try:
        old = harness._start_turn(
            "socket", page_dir, "hosted-thread", SimpleNamespace(pid=os.getpid())
        )
        with pytest.raises(RuntimeError, match="no longer owns"):
            old.begin()
        old.close({"id": "started-turn", "status": "completed", "items": []}, None)
        assert session_record("hosted-thread") == winner["epoch"]
        assert status_and_stream(page_dir) == winner["status"]
    finally:
        harness.close()
