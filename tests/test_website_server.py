"""The website route adapter preserves Leaf's canonical served-page contract."""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest
import verify_site
from click.testing import CliRunner
from interact_support import (
    COMMAND_SUBJECTS,
    STATED_TIMEOUT,
    Prose,
    append_command,
    running_http_server,
    yaml_document,
)
from leaf import codex as leaf_codex
from leaf.cli import cli
from leaf.codex import accept_codex_delivery
from leaf.codex import queue_records as codex_queues
from leaf.event_log import append_event, read_events
from leaf.files import revision_path
from leaf.hosting import LeafHTTPServer
from leaf.http import supervised_document
from leaf.machine import pid_alive
from leaf.revision_artifact import Resource
from leaf.revisioning import activate_source
from leaf.schema import ASSETS, VENDORED_FILES
from render_harness import consume_browser_errors
from websockets.exceptions import ConnectionClosedError

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "website_server", ROOT / "worker" / "server.py"
)
website_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(website_server)
_previews_spec = importlib.util.spec_from_file_location(
    "example_previews", ROOT / "scripts" / "example-previews.py"
)
example_previews = importlib.util.module_from_spec(_previews_spec)
_previews_spec.loader.exec_module(example_previews)
_benchmark_spec = importlib.util.spec_from_file_location(
    "benchmark_site", ROOT / "scripts" / "benchmark-site.py"
)
benchmark_site = importlib.util.module_from_spec(_benchmark_spec)
_benchmark_spec.loader.exec_module(benchmark_site)


@pytest.fixture(autouse=True)
def _no_host_outlives_its_test(monkeypatch):
    """Close every website host a test made, as `_no_page_outlives_its_test` stops
    every page server.

    Closing stops the App Server a host started and releases the waiter lease it
    holds over a Codex thread. The host is the subject here, built in each test
    body with the paths that test needs, so the sweep takes every construction
    rather than routing them through a fixture. `close` is idempotent, so a test
    whose subject is closing still closes where its assertion reads the result.
    """
    made = []

    class Swept(website_server.WebsiteCodexHost):
        def __init__(self, *arguments, **named):
            super().__init__(*arguments, **named)
            made.append(self)

    monkeypatch.setattr(website_server, "WebsiteCodexHost", Swept)
    yield
    for host in made:
        host.close()


# The response headers as the message, not a plain dict: header names are
# case-insensitive and arrive lowercased, as they do in a browser.
def get(url: str) -> tuple[bytes, Message]:
    with urllib.request.urlopen(url) as response:
        return response.read(), response.headers


def post(url: str, body: dict, headers: dict | None = None) -> tuple[dict, Message]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read()), response.headers


def write_manifest(site: Path, pages: dict[str, tuple[str, str]]) -> None:
    """Give a focused server fixture the same generated routing authority as a build."""
    manifest = {
        "release": "0" * 64,
        "pages": {
            route: {
                "directory": directory,
                "kind": kind,
                "title": f"The {route} page",
                "description": f"What a reader does at {route}.",
                "image": "/media/card.png",
            }
            for route, (directory, kind) in pages.items()
        },
    }
    target = site / website_server.SITE_MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest), encoding="utf-8")


def take_stream_activity(monkeypatch, updates: list, clears: list) -> None:
    """Collect every activity reading a turn writes, instead of a page taking it.

    Two bindings of the same two functions write them: the host calls them for a
    turn it is starting or giving up on, and `leaf.codex` calls them for everything
    the projection reads off the stream. A test that wants the readings, or wants
    them to touch nothing, has to say so at both.
    """
    for module in (website_server, leaf_codex):
        monkeypatch.setattr(
            module, "set_stream_activity", lambda *args: updates.append(args)
        )
        monkeypatch.setattr(
            module, "clear_stream_activity", lambda *args: clears.append(args)
        )


def hosted_follower(
    host,
    page_dir,
    prepared,
    socket=None,
    *,
    turn_id: str = "app-server-turn",
    thread_id: str = "hosted-thread",
    reply_target=None,
):
    """Build the follower a dispatch builds, for a delivery a test prepared.

    A follower is made from one `turn/start` answer on one connection, so a test
    gives it the same three things the dispatch does: the delivery it sent, the
    turn App Server named for it, and the connection that named it. Opening the
    Leaf turn stays the follower's own first step.
    """
    return website_server.HostedTurn(
        host,
        page_dir,
        thread_id,
        prepared.payload["id"],
        tuple(
            event["id"]
            for batch in prepared.payload["batches"]
            for event in batch["events"]
        ),
        turn_id,
        socket,
        reply_target=(
            website_server.stream_reply_target(prepared.payload)
            if reply_target is None
            else reply_target
        ),
    )


def unfollowed_turn(host, page_dir, *, following=None, event_ids=("first-event",)):
    """A turn whose own following is stood in for, to reach what comes after it.

    What a turn's ending hands on is the subject below, not how it ended, so these
    turns read no connection: `following` is what happens in place of the reading,
    and the default is a turn that ended without incident.
    """
    turn = website_server.HostedTurn(
        host, page_dir, "hosted-thread", "delivery-1", event_ids, "provider-turn"
    )
    turn.follow = following if following is not None else lambda: None
    return turn


class FakeCodexHost:
    def __init__(self):
        self.attached = []

    def attach(self, page_dir: Path, event_id: str) -> str | None:
        if not website_server.agent_event_pending(page_dir, event_id):
            return None
        thread_id = website_server.agent_event_thread(page_dir, event_id)
        if thread_id is not None:
            return thread_id
        self.attached.append(page_dir)
        return "codex-thread"

    def failure_receipt(
        self, page_dir: Path, event_id: str, failure: str
    ) -> dict | None:
        return website_server.WebsiteCodexHost("codex").failure_receipt(
            page_dir, event_id, failure
        )


PAGE_SOURCE = """<!doctype html>
<html lang="en">
  <head>
    <title>Choose the next fix</title>
    <meta name="description" content="Pick one." />
  </head>
  <body>
    <main><h1>Choose</h1></main>
  </body>
</html>
"""


@pytest.mark.parametrize(
    ("page_root", "kind", "url"),
    (
        ("", "product", "https://leaf.page/"),
        ("/examples/decision", "example", "https://leaf.page/examples/decision/"),
    ),
)
def test_a_published_document_names_its_page_to_a_crawler(page_root, kind, url):
    """An unfurler reads absolute URLs, and reads them from inside the head.

    Leaf owns the canonical address; publication adds what needs the site's origin.
    """
    page = {
        "kind": kind,
        "title": 'Choose the "next" fix',
        "description": "Pick one.",
        "image": "/media/card.png",
    }
    addition = website_server.site_head(page_root, page)
    served = supervised_document(
        PAGE_SOURCE,
        1,
        1,
        executable="sha256:executable",
        widgets={},
        server_id="server",
        layer_id="layer",
        resources={
            path: Resource((ASSETS / path.lstrip("/")).read_bytes(), mime)
            for path, mime in (
                ("/runtime/bootstrap.js", "application/javascript"),
                ("/runtime/chrome.css", "text/css"),
                ("/runtime/marks.css", "text/css"),
            )
        },
        page_root=page_root,
        before_runtime=addition,
    ).decode()
    head = served[: served.index("</head>")]
    assert f'<link rel="canonical" href="{page_root}/" data-lf-runtime>' in head
    assert f'<meta property="og:url" content="{url}" data-lf-runtime>' in head
    assert (
        '<meta property="og:image" content="https://leaf.page/media/card.png"'
        " data-lf-runtime>" in head
    )
    assert (
        '<meta property="og:title" content="Choose the &quot;next&quot; fix"'
        " data-lf-runtime>" in head
    )
    assert (
        '<meta name="twitter:card" content="summary_large_image" data-lf-runtime>'
        in head
    )
    # The sitenote is website chrome for the examples, and rides the runtime
    # boundary rather than the head the metadata went into.
    assert ("sitenote.js" in served) is (kind == "example")
    runtime = f'src="{page_root}/leaf.js"' if page_root else 'src="/leaf.js"'
    assert head.index("theme.css") < head.index('property="og:type"')
    assert head.index('property="og:type"') < head.index(runtime)


def test_agent_logs_are_structured_and_content_free(capsys):
    website_server.log_agent(
        "container_start_completed",
        eventId="reader-event",
        durationMs=125,
    )

    assert json.loads(capsys.readouterr().out) == {
        "component": "leaf-agent",
        "event": "container_start_completed",
        "eventId": "reader-event",
        "durationMs": 125,
    }


def test_agent_logs_keep_every_event_in_a_batched_turn_searchable(capsys):
    website_server.log_agent(
        "turn_start_acknowledged",
        **website_server.agent_event_fields(("event-1", "event-2")),
        turnId="turn-1",
    )

    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {
            "component": "leaf-agent",
            "event": "turn_start_acknowledged",
            "turnId": "turn-1",
            "eventId": "event-1",
        },
        {
            "component": "leaf-agent",
            "event": "turn_start_acknowledged",
            "turnId": "turn-1",
            "eventId": "event-2",
        },
    ]


@pytest.mark.parametrize("status", ["active", "idle", "systemError", "notLoaded"])
def test_the_website_host_delivers_into_the_existing_codex_thread(
    page_dir, tmp_path, monkeypatch, status
):
    host = website_server.WebsiteCodexHost(
        "codex",
        tmp_path / "app-server.sock",
        tmp_path / "app-server.log",
    )
    process = type("Process", (), {"pid": 41})()
    monkeypatch.setattr(website_server, "agent_event_pending", lambda *_: True)
    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    monkeypatch.setattr(
        website_server,
        "page_claim",
        lambda page: {"id": "hosted-thread", "harness": "embedded"},
    )
    reserved = []
    monkeypatch.setattr(
        website_server,
        "reserve_delivery_reply",
        lambda *args: reserved.append(args),
    )
    requests = []
    follows = []

    def request(method, params, before_close=None):
        requests.append((method, params))
        if before_close is not None:
            follows.append(
                before_close(
                    "socket",
                    {
                        "thread": {
                            "id": "hosted-thread",
                            "status": {"type": status},
                        }
                    },
                    [],
                )
            )
        return {"thread": {"id": "hosted-thread", "status": {"type": status}}}

    monkeypatch.setattr(host, "_request", request)
    monkeypatch.setattr(host, "_hold_waiter", lambda *_: None)
    started = []
    monkeypatch.setattr(
        host,
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
                                "id": "reader-event",
                                "obligation": {
                                    "response": {
                                        "kind": "reply",
                                        "to": "reader-event",
                                        "for": "reader-event",
                                    }
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
        "agent_event_thread",
        lambda *_: "hosted-thread" if follows or started else None,
    )
    interrupted = []
    monkeypatch.setattr(
        host,
        "_end_unfollowed_turn",
        lambda socket, thread, pending, event: interrupted.append((thread, event)),
    )

    thread_id = host.attach(page_dir, "reader-event")

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
    # However the thread was left, the reader's message starts a turn of its own.
    # A thread still running one has it stopped first, since that turn is answering
    # into a container that stopped watching it.
    assert interrupted == (
        [("hosted-thread", "reader-event")] if status == "active" else []
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
    holds the thread against the reader waiting behind it. App Server takes the
    interrupt without a turn id and says the turn ended on the same subscription,
    which is what makes the thread the new delivery's.
    """
    harness = website_server.website_harness("hosted-thread", os.getpid())
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    website_server.prepare_codex_delivery(page_dir, harness)
    accept_codex_delivery("hosted-thread", turn="active-turn")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    host = website_server.WebsiteCodexHost("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    sent = []

    class Socket:
        def recv(self, timeout):
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {"id": "active-turn", "status": "interrupted"},
                    },
                }
            )

    def send(socket, method, params, pending=None):
        sent.append((method, params))
        if method == "turn/start":
            return {"turn": {"id": "second-turn"}}
        return {}

    def request(method, params, before_close=None):
        before_close(
            Socket(),
            {"thread": {"id": "hosted-thread", "status": {"type": "active"}}},
            [],
        )
        return {"thread": {"id": "hosted-thread"}}

    monkeypatch.setattr(host, "_request", request)
    monkeypatch.setattr(host, "_send", send)
    monkeypatch.setattr(host, "_hold_waiter", lambda *_: None)
    assert host._resume_and_start(
        page_dir,
        "hosted-thread",
        process,
        second["id"],
    )
    assert [method for method, _ in sent] == ["turn/interrupt", "turn/start"]
    assert sent[0][1] == {"threadId": "hosted-thread", "turnId": ""}
    assert sent[1][1]["clientUserMessageId"]
    [(_, queue)] = codex_queues("hosted-thread")
    assert queue["state"] == "offering"


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
    host = website_server.WebsiteCodexHost("codex")

    class Process:
        pid = os.getpid()

    process = Process()
    deliveries = []

    def accept(phase, turn):
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
        accept_codex_delivery("hosted-thread", phase=phase, turn=turn)

    def start_thread(*args):
        accept("opened", "first-turn")
        return "hosted-thread"

    def resume_and_start(*args):
        accept("queued", None)
        return True

    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    monkeypatch.setattr(host, "_start_thread", start_thread)
    monkeypatch.setattr(host, "_resume_and_start", resume_and_start)

    assert host.attach(page_dir, second["id"]) == "hosted-thread"
    assert deliveries == [[first["id"]], [second["id"]]]
    assert website_server.agent_event_thread(page_dir, second["id"]) == "hosted-thread"


def test_attach_leaves_an_uncertain_delivery_to_its_reconciliation_follower(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    host = website_server.WebsiteCodexHost("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    dispatches = []

    def uncertain_start(target, running, event_id):
        prepared = website_server.prepare_codex_delivery(
            target, website_server.website_harness("hosted-thread", running.pid)
        )
        dispatches.append((event_id, prepared.payload["id"]))
        host.following_threads.add("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(host, "_start_thread", uncertain_start)
    monkeypatch.setattr(
        host,
        "_resume_and_start",
        lambda *_: pytest.fail("the attach loop redispatched an uncertain delivery"),
    )

    assert host.attach(page_dir, comment["id"]) == "hosted-thread"
    assert host.attach(page_dir, comment["id"]) == "hosted-thread"
    assert len(dispatches) == 1


def test_a_turn_follower_releases_its_seat_before_continuing(page_dir, monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    host.following_threads.add("hosted-thread")
    rescans = []

    def next_event(target, *, excluding):
        assert "hosted-thread" not in host.following_threads
        rescans.append((target, excluding))
        return "next-event"

    monkeypatch.setattr(website_server, "next_unaccepted_agent_event", next_event)
    continued = []

    def attach(target, event_id):
        assert "hosted-thread" not in host.following_threads
        continued.append((target, event_id))
        return "hosted-thread"

    monkeypatch.setattr(host, "attach", attach)
    host._run_follow_turn(unfollowed_turn(host, page_dir))

    assert rescans == [(page_dir, ("first-event",))]
    assert continued == [(page_dir, "next-event")]


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Codex App Server did not start a turn: refused"),
        # The connection's own class, which descends from `Exception` alone: a start
        # can fail on the handshake or a dropped socket before it reaches the turn,
        # and the reader is owed the same receipt either way.
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
    leaves the reader on a turn that never began unless this writes the receipt.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    host.following_threads.add("hosted-thread")

    def attach(target, event_id):
        raise error

    monkeypatch.setattr(host, "attach", attach)
    host._run_follow_turn(unfollowed_turn(host, page_dir))

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
    `listening` until the reader sends a third.
    """
    comments = [
        append_event(page_dir, {"kind": "comment", "author": "user", "text": text})
        for text in ("edit the page", "and the title")
    ]
    host = website_server.WebsiteCodexHost("codex")
    host.following_threads.add("hosted-thread")
    attempted = []

    def attach(target, event_id):
        attempted.append(event_id)
        raise RuntimeError("Codex App Server did not start a turn: refused")

    monkeypatch.setattr(host, "attach", attach)
    host._run_follow_turn(unfollowed_turn(host, page_dir))

    assert attempted == [comment["id"] for comment in comments]
    receipts = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [receipt["responds"] for receipt in receipts] == attempted
    assert {receipt["failure"] for receipt in receipts} == {"startup_failed"}
    state = website_server.full_state(page_dir, read_events(page_dir))
    assert state["activity"]["obligations"] == []


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
    host = website_server.WebsiteCodexHost("codex")
    host.following_threads.add("hosted-thread")

    def fault():
        raise RuntimeError("closing the turn faulted")

    continued = []
    monkeypatch.setattr(
        host, "attach", lambda target, event_id: continued.append(event_id)
    )

    with pytest.raises(RuntimeError, match="closing the turn faulted"):
        host._run_follow_turn(unfollowed_turn(host, page_dir, following=fault))

    assert continued == [comment["id"]]
    assert "hosted-thread" not in host.following_threads


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
    host = website_server.WebsiteCodexHost("codex")
    host.following_threads.add("hosted-thread")
    ending = ValueError("closing the turn faulted on the page it left")

    def fault():
        raise ending

    with pytest.raises(ValueError) as raised:
        host._run_follow_turn(
            unfollowed_turn(host, page_dir, following=fault, event_ids=())
        )

    # The ending's own fault, not the hand-on's complaint about the same page.
    assert raised.value is ending
    receipts = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [receipt["responds"] for receipt in receipts] == [
        comment["id"] for comment in comments
    ]
    assert {receipt["failure"] for receipt in receipts} == {"startup_failed"}
    state = website_server.full_state(page_dir, read_events(page_dir))
    assert state["activity"]["obligations"] == []


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
    host = website_server.WebsiteCodexHost("codex")

    def refuse():
        raise ConnectionClosedError(None, None)

    monkeypatch.setattr(host, "_ensure_server", refuse)
    with pytest.raises(ConnectionClosedError):
        host.attach(page_dir, comment["id"])

    [record] = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if json.loads(line)["event"] == "container_start_failed"
    ]
    assert (record["eventId"], record["error"]) == (
        comment["id"],
        "ConnectionClosedError",
    )


@pytest.mark.parametrize("response_kind", ["reply", "version", "receipt"])
def test_hosted_agent_receives_the_response_instructions_and_delivery(
    page_dir, monkeypatch, snapshot, response_kind
):
    """Capture real instructions and deliveries at the App Server wire boundary.

    Only the external App Server connection is replaced. Event admission, delivery
    preparation, response addressing, and both request builders run normally.
    """
    command = {"kind": "comment", "author": "user", "text": "Use backfill first."}
    if response_kind == "version":
        registry_path = page_dir / "registry.json"
        registry = json.loads(registry_path.read_text())
        registry["lf-options"]["x-conversation"] = {
            "when": {"choose": [True]},
            "response": {"kind": "version", "verb": "choose"},
        }
        registry_path.write_text(json.dumps(registry))
        source = page_dir / "index.html"
        source.write_text(
            source.read_text().replace(
                "<lf-options>", '<lf-options id="choice" choose>'
            )
        )
        command.update(
            anchor={"section": "choice"},
            response={"kind": "version", "verb": "choose"},
        )
    if response_kind == "receipt":
        source = page_dir / "index.html"
        controls = (
            '<lf-command id="hub"><lf-task id="goal" status="active">'
            "<strong>Goal</strong>" + COMMAND_SUBJECTS + "</lf-task></lf-command>"
            '<lf-ask id="recovery"><h3>Restart the worker?</h3>'
            '<lf-operations id="commands" target="goal" worker="worker" '
            'worktree="tree">'
            '<lf-operation verb="restart"><strong>Restart</strong></lf-operation>'
            "</lf-operations></lf-ask>"
        )
        source.write_text(
            source.read_text().replace("</section>", controls + "</section>")
        )
        activated = activate_source(page_dir, [])
        assert activated.error is None
        command = {
            "kind": "request",
            "author": "user",
            "revision": activated.revision,
            "widget": "commands",
            "action": "restart",
            "detail": {"target": "goal", "worker": "worker", "worktree": "tree"},
        }
        event = append_command(page_dir, command)
    else:
        event = append_event(page_dir, command)
    host = website_server.WebsiteCodexHost("codex")
    outgoing = {}

    def request(method, params, before_close=None):
        outgoing[method] = params
        result = {"thread": {"id": "hosted-thread"}}
        before_close("socket", result, [])
        return result

    def send(socket, method, params, pending=None):
        outgoing[method] = params
        return {"turn": {"id": "initial-turn"}}

    monkeypatch.setattr(host, "_request", request)
    monkeypatch.setattr(host, "_send", send)
    assert (
        host._start_thread(page_dir, SimpleNamespace(pid=os.getpid()), event["id"])
        == "hosted-thread"
    )
    payload = json.loads(outgoing["turn/start"]["toolOutput"]["output"])
    [delivered] = payload["batches"][0]["events"]
    assert delivered["obligation"]["response"]["kind"] == response_kind
    replacements = {
        str(page_dir): "/page",
        event["id"]: "reader-event",
        event["ts"]: "2026-09-22T10:00:00-07:00",
        payload["id"]: "00000000-0000-4000-8000-000000000001",
        str(payload["created_at"]): "1790096400.0",
    }
    serialized = json.dumps(outgoing)
    for actual, stable in replacements.items():
        serialized = serialized.replace(actual, stable)
    recorded = json.loads(serialized)
    recorded["thread/start"]["developerInstructions"] = Prose(
        recorded["thread/start"]["developerInstructions"]
    )
    snapshot.check(
        yaml_document(
            "Actual outgoing App Server requests for an admitted reader event.\n"
            "Only the page path, event/delivery identities, and timestamps are pinned.\n"
            "toolOutput.output is the complete serialized delivery the agent receives.",
            recorded,
        )
    )
    if response_kind == "receipt":
        # The host's scope forbids restarting a worker outside this page. Its
        # command route must still let it report failure and reopen the request.
        result = CliRunner().invoke(
            cli,
            [
                "receipt",
                str(page_dir),
                event["id"],
                "failed",
                "--text",
                "The worker is outside this hosted page's scope.",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        receipt = json.loads(result.output)
        assert (receipt["request"], receipt["status"]) == (event["id"], "failed")
        assert (
            website_server.full_state(page_dir, read_events(page_dir))["activity"][
                "obligations"
            ]
            == []
        )


def test_the_website_task_is_a_scoped_leaf_codex_thread(page_dir, monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    requests = []
    sent = []
    prepared = []

    def request(method, params, before_close=None):
        requests.append((method, params))
        result = {"thread": {"id": "hosted-thread"}}
        if before_close is not None:
            before_close("socket", result, [])
        return result

    monkeypatch.setattr(host, "_request", request)

    def send(socket, method, params, pending=None):
        sent.append((socket, method, params, pending))
        return {"turn": {"id": "initial-turn"}}

    monkeypatch.setattr(host, "_send", send)
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *args: (
            prepared.append(args)
            or SimpleNamespace(
                payload={"id": "delivery-1", "batches": [{"events": []}]}
            )
        ),
    )
    assert host._start_thread(
        page_dir, type("Process", (), {"pid": 41})(), "reader-event"
    ) == ("hosted-thread")
    assert requests == [
        (
            "thread/start",
            {
                "model": "gpt-5.6-luna",
                "cwd": str(page_dir),
                "approvalPolicy": "never",
                "sandbox": "danger-full-access",
                "developerInstructions": website_server.CODEX_INSTRUCTIONS,
                "config": {"model_reasoning_effort": "low"},
            },
        )
    ]
    assert prepared == [(page_dir, website_server.website_harness("hosted-thread", 41))]
    assert sent == [
        (
            "socket",
            "turn/start",
            {
                "threadId": "hosted-thread",
                "clientUserMessageId": "delivery-1",
                "input": [],
                "toolOutput": {
                    "name": "leaf_delivery",
                    "output": '{"id":"delivery-1","batches":[{"events":[]}]}',
                },
                "turnTrigger": "leaf",
            },
            [],
        )
    ]
    assert sent[0][-1] == []


def test_the_local_adapter_owns_its_process_and_disposable_codex_home(
    tmp_path, monkeypatch
):
    """Exercise real build/process/file ownership with a stand-in for the hosted agent."""
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "worker").mkdir()
    host_home = tmp_path / "host-codex"
    host_home.mkdir()
    (host_home / "auth.json").write_text('{"test": "login"}')
    (root / "worker" / "codex-config.toml").write_text('model = "test"')
    (root / "scripts" / "site.py").write_text(
        "from pathlib import Path\n"
        "site = Path('.tmp/site/_leaf')\n"
        "site.mkdir(parents=True)\n"
        "(site / 'site.json').write_text('{\"release\": \"' + 'a' * 40 + '\"}')\n"
        "print('built the site')\n"
    )
    (root / "worker" / "server.py").write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
        "class Handler(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.end_headers()\n"
        "        self.wfile.write(json.dumps(dict(pid=os.getpid(), home=os.environ['CODEX_HOME'], site=os.environ['LEAF_SITE_ROOT'])).encode())\n"
        "server = HTTPServer(('127.0.0.1', 0), Handler)\n"
        "Path('port').write_text(str(server.server_port))\n"
        "print('startup diagnostic', flush=True)\n"
        "print(json.dumps(dict(component='leaf-agent', event='container_http_ready')), flush=True)\n"
        "server.serve_forever()\n"
    )
    monkeypatch.setattr(verify_site, "ROOT", root)
    monkeypatch.setenv("CODEX_HOME", str(host_home))
    urlopen = urllib.request.urlopen

    def local_health(url, **kwargs):
        assert url == "http://127.0.0.1:8080/health"
        port = (root / "port").read_text()
        return urlopen(f"http://127.0.0.1:{port}/health", **kwargs)

    monkeypatch.setattr(verify_site.urllib.request, "urlopen", local_health)
    with (
        pytest.raises(RuntimeError, match="journey failed"),
        verify_site.local_adapter() as (origin, release),
    ):
        assert release == "a" * 40
        body, _ = get(f"{origin}/health")
        running = json.loads(body)
        private_home = Path(running["home"])
        private_site = Path(running["site"])
        assert private_home != host_home
        assert (private_home / "auth.json").read_bytes() == (
            host_home / "auth.json"
        ).read_bytes()
        assert (private_home / "auth.json").stat().st_mode & 0o777 == 0o600
        assert (private_home / "config.toml").read_text() == 'model = "test"'
        assert private_site != root / ".tmp" / "site"
        assert (private_site / "_leaf" / "site.json").exists()
        raise RuntimeError("journey failed")
    assert not private_home.exists()
    assert not private_site.exists()
    assert (host_home / "auth.json").read_text() == '{"test": "login"}'
    with pytest.raises(ProcessLookupError):
        os.kill(running["pid"], 0)


def test_the_benchmark_passes_local_and_remote_targets_explicitly(monkeypatch):
    calls = []
    lifecycle = []

    @contextmanager
    def local():
        lifecycle.append("start")
        try:
            yield "http://127.0.0.1:8080", "a" * 40
        finally:
            lifecycle.append("stop")

    def measure(origin, release=None, *, direct_agent=False):
        calls.append((origin, release, direct_agent))
        return {"origin": origin, "release": release}

    monkeypatch.setattr(benchmark_site, "local_adapter", local)
    monkeypatch.setattr(benchmark_site, "measure", measure)
    runner = CliRunner()
    local_result = runner.invoke(benchmark_site.main, ["local"])
    assert local_result.exit_code == 0, local_result.output
    assert json.loads(local_result.output) == {
        "origin": "http://127.0.0.1:8080",
        "release": "a" * 40,
    }
    remote_result = runner.invoke(benchmark_site.main, ["https://leaf-dev.example/"])
    assert remote_result.exit_code == 0, remote_result.output
    assert json.loads(remote_result.output) == {
        "origin": "https://leaf-dev.example",
        "release": None,
    }
    assert lifecycle == ["start", "stop"]
    assert calls == [
        ("http://127.0.0.1:8080", "a" * 40, True),
        ("https://leaf-dev.example", None, False),
    ]
    invalid = runner.invoke(benchmark_site.main, ["https://leaf-dev.example/a-page"])
    assert invalid.exit_code == 2
    assert len(calls) == 2


def test_the_website_app_server_inherits_the_ready_leaf_cli(tmp_path, monkeypatch):
    """A hosted task must not discover or initialize another plugin environment."""
    site_root = tmp_path / "site"
    site_root.mkdir()
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site_root))
    host = website_server.WebsiteCodexHost(
        "codex",
        tmp_path / "app-server.sock",
        tmp_path / "app-server.log",
    )
    launched = {}

    class Process:
        """Running until it is told to stop, which is what the host does with it."""

        def __init__(self):
            self.stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout=None):
            return 0

    def popen(command, **options):
        launched.update(command=command, options=options)
        host.socket_path.touch()
        return Process()

    monkeypatch.setattr(website_server.subprocess, "Popen", popen)

    assert host._ensure_server() is not None
    assert launched["options"]["env"]["LEAF"] == website_server.LEAF_COMMAND
    assert "LEAF_REPLY" not in launched["options"]["env"]
    assert "LEAF_REPLY_TOKEN" not in launched["options"]["env"]
    assert launched["options"]["cwd"] == str(site_root)
    assert "LEAF_SKILL_DIR" not in launched["options"]["env"]
    assert launched["command"] == [
        "codex",
        "app-server",
        "--listen",
        host.endpoint,
    ]


def test_a_timed_out_app_server_is_stopped_before_startup_retries(
    tmp_path, monkeypatch
):
    host = website_server.WebsiteCodexHost(
        "codex",
        tmp_path / "app-server.sock",
        tmp_path / "app-server.log",
    )
    clock = [0.0]
    processes = []

    class Process:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout=None):
            return 0

    def popen(*args, **kwargs):
        process = Process()
        processes.append(process)
        if len(processes) == 2:
            host.socket_path.touch()
        return process

    monkeypatch.setattr(website_server.subprocess, "Popen", popen)
    monkeypatch.setattr(website_server.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        website_server.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + 21),
    )

    with pytest.raises(RuntimeError, match="did not become ready"):
        host._ensure_server()

    assert processes[0].stopped
    assert host.process is None
    assert host._ensure_server() is processes[1]


def test_an_attach_waiting_on_failed_prewarm_retries_startup(page_dir, monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    prewarm_started = threading.Event()
    fail_prewarm = threading.Event()
    calls = []
    process = type("Process", (), {"pid": 41})()
    monkeypatch.setattr(website_server, "agent_event_pending", lambda *_: True)

    def ensure_server():
        calls.append(None)
        if len(calls) == 1:
            prewarm_started.set()
            fail_prewarm.wait(timeout=STATED_TIMEOUT)
            raise RuntimeError("startup failed")
        return process

    monkeypatch.setattr(host, "_ensure_server", ensure_server)
    monkeypatch.setattr(host, "_warm_leaf_cli", lambda: None)
    monkeypatch.setattr(website_server, "page_claim", lambda page: None)
    delivered = []
    monkeypatch.setattr(
        host,
        "_start_thread",
        lambda *args: delivered.append(True) or "hosted-thread",
    )
    monkeypatch.setattr(
        website_server,
        "agent_event_thread",
        lambda *_: "hosted-thread" if delivered else None,
    )

    prewarm = host.prewarm()
    assert prewarm_started.wait(timeout=STATED_TIMEOUT)
    attached = []
    request = threading.Thread(
        target=lambda: attached.append(host.attach(page_dir, "reader-event"))
    )
    request.start()
    assert calls == [None]
    fail_prewarm.set()
    prewarm.join(timeout=STATED_TIMEOUT)
    request.join(timeout=STATED_TIMEOUT)

    assert attached == ["hosted-thread"]
    assert calls == [None, None]


def test_duplicate_attaches_share_one_delivery_start(page_dir, monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    process = type("Process", (), {"pid": 41})()
    started = threading.Event()
    release = threading.Event()
    second_called = threading.Event()
    accepted = []
    start_calls = []

    monkeypatch.setattr(website_server, "agent_event_pending", lambda *_: True)
    monkeypatch.setattr(
        website_server,
        "agent_event_thread",
        lambda *_: accepted[0] if accepted else None,
    )
    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    monkeypatch.setattr(website_server, "page_claim", lambda page: None)

    def start_thread(*args):
        start_calls.append(None)
        started.set()
        release.wait(timeout=STATED_TIMEOUT)
        accepted.append("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(host, "_start_thread", start_thread)
    attached = []
    first = threading.Thread(
        target=lambda: attached.append(host.attach(page_dir, "reader-event"))
    )

    def attach_second():
        second_called.set()
        attached.append(host.attach(page_dir, "reader-event"))

    second = threading.Thread(target=attach_second)
    first.start()
    assert started.wait(timeout=STATED_TIMEOUT)
    second.start()
    assert second_called.wait(timeout=STATED_TIMEOUT)
    release.set()
    first.join(timeout=STATED_TIMEOUT)
    second.join(timeout=STATED_TIMEOUT)

    assert attached == ["hosted-thread", "hosted-thread"]
    assert start_calls == [None]


def test_the_website_host_prewarms_app_server_and_leaf_cli_in_the_background(
    monkeypatch,
):
    host = website_server.WebsiteCodexHost("codex")
    app_started = threading.Event()
    leaf_started = threading.Event()
    leaf_finished = threading.Event()
    release_app = threading.Event()
    release_leaf = threading.Event()

    def ensure_server():
        app_started.set()
        release_app.wait(timeout=STATED_TIMEOUT)

    def warm_leaf_cli():
        leaf_started.set()
        release_leaf.wait(timeout=STATED_TIMEOUT)
        leaf_finished.set()

    monkeypatch.setattr(host, "_ensure_server", ensure_server)
    monkeypatch.setattr(host, "_warm_leaf_cli", warm_leaf_cli)

    thread = host.prewarm()

    assert app_started.wait(timeout=STATED_TIMEOUT)
    assert leaf_started.wait(timeout=STATED_TIMEOUT)
    assert thread.is_alive()
    release_app.set()
    thread.join(timeout=STATED_TIMEOUT)
    assert not thread.is_alive()
    release_leaf.set()
    assert leaf_finished.wait(timeout=STATED_TIMEOUT)


def test_the_leaf_cli_prewarm_runs_the_installed_command(monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    calls = []

    monkeypatch.setattr(
        website_server.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    host._warm_leaf_cli()

    assert calls == [
        (
            ([website_server.LEAF_COMMAND, "--version"],),
            {
                "stdin": website_server.subprocess.DEVNULL,
                "stdout": website_server.subprocess.DEVNULL,
                "stderr": website_server.subprocess.DEVNULL,
                "check": True,
                "timeout": 20,
            },
        )
    ]


def test_closing_the_website_host_stops_its_app_server(tmp_path):
    """The host adapter owns the process it starts, including during local runs."""
    host = website_server.WebsiteCodexHost(
        "codex", tmp_path / "app-server.sock", tmp_path / "app-server.log"
    )

    class Process:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout=None):
            return 0

    process = Process()
    host.process = process
    host.socket_path.touch()

    host.close()

    assert process.stopped
    assert host.process is None
    assert not host.socket_path.exists()


def test_the_adapter_takes_its_app_server_with_it_when_it_is_told_to_stop(
    tmp_path, socket_dir, spawn
):
    """The stop signal reaches the App Server, not only the adapter that started it.

    `close` covers the ordinary return, and inside a container nothing else is
    needed. On a host it is: `scripts/verify_site.py local` runs this adapter and
    stops it with SIGTERM, and uvicorn answers that signal by stopping its loop and
    re-raising it, so the process dies before any `finally`. The App Server is in a
    session of its own, which is what makes it the one child that survives that —
    three of them were alive on a developer's machine, fifteen hours after their runs.

    The whole adapter runs here, with a stand-in for the App Server itself: the fault
    was in how this process dies, so uvicorn's signal handling, the handler beneath
    it, and the real `_stop_server` are the parts that have to be real.
    """
    site = tmp_path / "site"
    site.mkdir()
    write_manifest(site, {})
    (site / "sitenote.js").write_bytes(b"")
    listening = tmp_path / "app-server.pid"
    codex = tmp_path / "codex"
    codex.write_text(
        f"""#!{sys.executable}
import os, socket, sys, time
from pathlib import Path

address = sys.argv[sys.argv.index("--listen") + 1].removeprefix("unix://")
listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
listener.bind(address)
listener.listen()
Path({str(listening)!r}).write_text(str(os.getpid()))
while True:
    time.sleep(3600)
"""
    )
    codex.chmod(0o755)
    adapter = spawn(
        [
            sys.executable,
            "-c",
            f"""
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "website_server", {str(ROOT / "worker" / "server.py")!r}
)
module = importlib.util.module_from_spec(spec)
sys.modules["website_server"] = module
spec.loader.exec_module(module)
module.PORT = 0
module._agent_host = module.WebsiteCodexHost(
    {str(codex)!r}, Path({str(socket_dir / "app-server.sock")!r}),
    Path({str(tmp_path / "app-server.log")!r}),
)
module.main()
""",
        ],
        env=os.environ | {"LEAF_SITE_ROOT": str(site)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + STATED_TIMEOUT
    while not listening.is_file():
        if adapter.poll() is not None or time.monotonic() >= deadline:
            adapter.kill()
            pytest.fail(
                "the adapter never started an App Server:\n"
                f"{adapter.communicate()[1]}\n"
                f"{(tmp_path / 'app-server.log').read_text(errors='replace')}"
            )
        time.sleep(0.05)
    app_server = int(listening.read_text())

    adapter.terminate()

    assert adapter.wait(timeout=STATED_TIMEOUT) == -signal.SIGTERM
    deadline = time.monotonic() + STATED_TIMEOUT
    while pid_alive(app_server):
        assert time.monotonic() < deadline, (
            "the App Server outlived the adapter that started it"
        )
        time.sleep(0.05)
    assert not (socket_dir / "app-server.sock").exists()


def test_closing_a_host_that_started_no_server_preserves_the_shared_socket(tmp_path):
    """A passive host does not own another host's process-global files."""
    socket_path = tmp_path / "app-server.sock"
    socket_path.touch()
    host = website_server.WebsiteCodexHost("codex", socket_path)

    host.close()

    assert socket_path.exists()


def test_the_direct_agent_handoff_runs_the_local_adapter_workflow():
    class Requests:
        def __init__(self):
            self.request = self
            self.posts = []

        def post(self, url, data, **options):
            self.posts.append((url, data))
            return _Read({"status": "started"})

    context = Requests()
    verify_site.start_direct_agent(
        context,
        "http://127.0.0.1:8080/examples/triage-board/",
        {"id": "comment-id"},
    )

    assert context.posts == [
        (
            "http://127.0.0.1:8080/examples/triage-board/_leaf/agent/start",
            {"event": "comment-id"},
        ),
    ]


@pytest.mark.parametrize(
    "refusal",
    [
        website_server.AppServerRequestRejected("rejected"),
        TimeoutError("lost ack"),
    ],
    ids=["refused", "lost"],
)
def test_a_start_that_names_no_turn_gives_the_reader_their_message_back(
    page_dir, monkeypatch, refusal
):
    """A dispatch that cannot name a turn withdraws, rather than going looking.

    There is nothing to follow and possibly something running: a lost
    acknowledgement is a request App Server may well have acted on. So the
    provider is told to stop whatever it started, and the delivery gives the
    moves back — both the offer and the reply seat it reserved, because either
    left standing blocks the `startup_failed` receipt this raise asks the Worker
    for, and that receipt is what invites the reader to send again.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    competing_writer_rejected = []

    def refuse(*args, **kwargs):
        with pytest.raises(SystemExit, match="bound to this delivery's final message"):
            website_server.cmd_reply(
                page_dir,
                comment["id"],
                "Competing tool reply",
                "",
                for_event=comment["id"],
                identity={"agent": "Codex", "session": "hosted-thread"},
            )
        competing_writer_rejected.append(True)
        raise refusal

    interrupts = []
    monkeypatch.setattr(host, "_send", refuse)
    monkeypatch.setattr(
        host,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    with pytest.raises(RuntimeError, match="did not start a turn"):
        host._start_turn(
            "socket",
            page_dir,
            "hosted-thread",
            type("Process", (), {"pid": os.getpid()})(),
        )

    assert interrupts == [("hosted-thread", "")]
    assert codex_queues("hosted-thread") == []
    assert competing_writer_rejected == [True]
    assert (
        website_server.full_state(page_dir, read_events(page_dir))["activity"]["kind"]
        != "working"
    )
    # The seat is free, so the Worker's own receipt reaches the reader.
    assert (
        website_server.write_failure_receipt(page_dir, comment["id"], "startup_failed")
        is not None
    )


def test_an_acknowledged_start_answers_a_reader_with_no_turn_started_notification(
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
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(
        host, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
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
    follow = host._start_turn(
        socket,
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    follow.follow()
    events = read_events(page_dir)
    activity = website_server.full_state(page_dir, events)["activity"]
    host.close()

    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["text"]) == (comment["id"], "Deployment verified.")
    assert "failure" not in reply
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert (activity["kind"], activity["obligations"]) == ("listening", [])
    assert socket.closed


def test_a_turn_that_completes_without_an_answer_is_still_receipted(
    page_dir, monkeypatch
):
    """A turn can end well and still leave the reader with nothing.

    App Server reports a turn completed whether or not it wrote a final answer, so
    the move it was given can outlive it settled by nobody. The follower that took
    it is the only writer the pickup leaves, and it reads the same question at
    every ending: is this move still owed a reply.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [],
                        },
                    },
                }
            )

        def close(self):
            self.closed = True

    host = website_server.WebsiteCodexHost("codex")
    interrupts = []
    monkeypatch.setattr(
        host,
        "_interrupt",
        lambda *args, **kwargs: interrupts.append(args),
    )
    hosted_follower(host, page_dir, prepared, Socket()).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    # The turn ended by itself, so there is nothing to stop.
    assert interrupts == []
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert website_server.full_state(page_dir, events)["activity"]["obligations"] == []


def test_a_turn_that_will_not_stop_leaves_the_thread_rather_than_the_reader(
    page_dir, monkeypatch
):
    """A dispatch holds the reader's request open, so it does not wait forever.

    The turn being stopped belongs to a container that is already gone. If App
    Server does not report it ended, this start raises, the Worker receipts the
    message as one the agent could not be started for, and the thread is left to
    whichever container start meets it next.
    """
    append_event(page_dir, {"kind": "comment", "author": "user", "text": "hello"})
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(website_server, "TURN_ABORT_WAIT", 0.0)
    sent = []

    class Socket:
        def recv(self, timeout):
            raise TimeoutError

    def send(socket, method, params, pending=None):
        sent.append(method)
        return {}

    monkeypatch.setattr(host, "_send", send)

    with pytest.raises(RuntimeError, match="did not stop"):
        host._end_unfollowed_turn(Socket(), "hosted-thread", [], "reader-event")

    assert sent == ["turn/interrupt"]


def test_an_interrupt_refused_by_an_idle_thread_is_recorded_not_raised(
    page_dir, monkeypatch, capsys
):
    """Losing the race to a turn's own ending is not a fault.

    The follower interrupts whatever its turn may still be doing, and App Server
    refuses when that turn has already finished. Raising there would replace the
    ending the follower is in the middle of accounting for with this one.
    """
    host = website_server.WebsiteCodexHost("codex")

    class Socket:
        closed = False

        def close(self):
            self.closed = True

    socket = Socket()
    monkeypatch.setattr(website_server, "app_server_connect", lambda _endpoint: socket)
    monkeypatch.setattr(
        website_server, "app_server_handshake", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        host,
        "_send",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            website_server.AppServerRequestRejected("no active turn to interrupt")
        ),
    )

    host._interrupt("hosted-thread", "app-server-turn", eventId="reader-event")

    [record] = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert record["event"] == "turn_interrupt_failed"
    assert record["detail"] == "no active turn to interrupt"
    assert record["turnId"] == "app-server-turn"
    assert socket.closed


def test_a_turn_whose_stream_drops_is_stopped_and_its_move_receipted(
    page_dir, monkeypatch
):
    """A follower that stops ends its turn and answers for it.

    The connection is the only thing Leaf loses; the provider turn goes on
    running, answering into nobody, and its pickup of this move stops every other
    writer from receipting it. So the follower that took the move is the one that
    has to close both: `turn/interrupt` for the turn, and the receipt that tells
    the reader to send again — which the move's own pickup would otherwise refuse,
    leaving the page showing a message picked up by a turn that is gone.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(
        host, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
    )

    class LostSocket:
        def recv(self, timeout):
            raise OSError("connection lost")

        def close(self):
            pass

    follow = host._start_turn(
        LostSocket(),
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    interrupts = []
    monkeypatch.setattr(
        host,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    host._hold_waiter(page_dir, "hosted-thread")
    follow.follow()
    events = read_events(page_dir)
    activity = website_server.full_state(page_dir, events)["activity"]

    assert interrupts == [("hosted-thread", "app-server-turn")]
    assert follow.leaf_turn is not None
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert reply["text"] == website_server.FAILURE_RECEIPTS["turn_failed"]
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert activity["kind"] != "working"
    assert activity["obligations"] == []


def test_a_host_failure_receipt_answers_a_gesture_on_its_conversation(page_dir):
    """The Worker's last-resort receipt reaches a widget gesture too, twice over.

    `/_leaf/agent/reply` is what the Worker calls when it is rate limited or its
    dispatch throws, with whatever event `/api/event` accepted — which can be a
    gesture on a widget frozen into thread markup. That is answered on the
    conversation holding it, so addressing the receipt at the gesture refuses the
    one write whose whole job is to leave the reader something.

    The Worker repeats that request, so the second call has to answer with the first
    receipt. Once the first has settled the gesture, nothing outside the log can say
    where its reply went: an address worked out ahead of the write reads the settled
    page, gets the gesture back, and refuses its own earlier receipt as another
    event's. The durable attempt is the answer, and the writer reads it first.
    """
    website_server.activate_source(page_dir, read_events(page_dir))
    asked = append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-options id="region" choose>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            "</lf-options>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "region",
            "action": "choose",
            "detail": {"options": ["east"]},
        },
    )

    reply = website_server.WebsiteCodexHost("codex").failure_receipt(
        page_dir, chose["id"], "startup_failed"
    )

    assert reply is not None
    assert (reply["parent"], reply["responds"]) == (asked["id"], chose["id"])
    assert reply["failure"] == "startup_failed"

    repeated = website_server.WebsiteCodexHost("codex").failure_receipt(
        page_dir, chose["id"], "startup_failed"
    )
    # The same event, which is what the door hands back (`accepted["id"]`); the log
    # read carries a `seq` the freshly appended record does not.
    assert repeated is not None and repeated["id"] == reply["id"]
    assert repeated["parent"] == asked["id"]
    assert [
        event["id"] for event in read_events(page_dir) if event["kind"] == "reply"
    ] == [reply["id"]]


def test_a_fault_record_keeps_the_end_of_an_oversized_message():
    """A boundary that raises with a whole file does not get to fill the log.

    `_wait_for_app_server` raises with App Server's entire log as the message when a
    spawn never becomes ready, and a record is not where a log file belongs. The
    reason a process exited is at the end of its log, so that is the part kept.
    """
    short = website_server.fault_fields(RuntimeError("no thread by that id"))
    assert short == {"error": "RuntimeError", "detail": "no thread by that id"}

    log = "noise\n" * 400 + "fatal: the reason it exited"
    assert len(log) > website_server.FAULT_DETAIL_LIMIT
    bounded = website_server.fault_fields(RuntimeError(log))
    assert bounded["error"] == "RuntimeError"
    assert bounded["detail"].endswith("fatal: the reason it exited")
    assert bounded["detail"].startswith("\u2026")
    assert len(bounded["detail"]) == website_server.FAULT_DETAIL_LIMIT + 1

    # The other boundary that writes a `detail` is App Server reporting its own turn
    # failed, and the record's size contract is the record's, not one writer's.
    reported = website_server.terminal_fault({"error": {"message": log}})
    assert reported == {"detail": bounded["detail"]}


def test_an_unanswered_widget_gesture_is_receipted_on_its_conversation(
    page_dir, monkeypatch
):
    """A receipt is addressed where the gesture is answered, not at the gesture.

    A widget frozen into thread markup is answered on the conversation holding it,
    so the address a reply is written to and the move it settles are two different
    events. Writing the receipt at the gesture refuses instead of settling it. The
    turn below starts, takes the gesture, and then loses its stream, which is the
    ending that owes this receipt.
    """
    website_server.activate_source(page_dir, read_events(page_dir))
    asked = append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which region?",
            "markup": '<lf-ask id="region-ask"><h3>Which region?</h3>'
            '<lf-options id="region" choose>'
            '<lf-option id="east"><strong>East</strong></lf-option>'
            '<lf-option id="west"><strong>West</strong></lf-option>'
            "</lf-options></lf-ask>",
        },
    )
    chose = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "region",
            "action": "choose",
            "detail": {"options": ["east"]},
        },
    )
    with website_server.PageTransaction(page_dir) as page:
        page.set_status("idle", "")
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(
        host, "_send", lambda *a, **k: {"turn": {"id": "app-server-turn"}}
    )

    class LostSocket:
        def recv(self, timeout):
            raise OSError("connection lost")

        def close(self):
            pass

    follow = host._start_turn(
        LostSocket(),
        page_dir,
        "hosted-thread",
        type("Process", (), {"pid": os.getpid()})(),
    )
    assert follow.reply_target is not None
    assert follow.reply_target["reply_to"] != follow.reply_target["responds"]

    monkeypatch.setattr(host, "_interrupt", lambda *args, **kwargs: None)
    follow.follow()
    host.close()

    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert (receipt["parent"], receipt["responds"]) == (asked["id"], chose["id"])
    assert receipt["failure"] == "turn_failed"


def test_notifications_before_start_response_reach_the_turn_follower(
    page_dir, monkeypatch
):
    # A real delivery, because the follower reads it back by id when it accounts for
    # the turn, and a made-up id is refused there rather than at the send.
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    payload = prepared.payload
    messages = iter(
        [
            json.dumps({"id": 0, "result": {}}),
            json.dumps({"id": 1, "result": {"thread": {"id": "hosted-thread"}}}),
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 900,
                        "item": {
                            "id": "delivery",
                            "type": "functionCallOutput",
                            "name": "leaf_delivery",
                            "output": json.dumps(payload),
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 1_000,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Deployment verified.",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {"id": "initial-turn", "status": "completed"},
                    },
                }
            ),
            json.dumps({"id": 2, "result": {"turn": {"id": "initial-turn"}}}),
        ]
    )

    class Socket:
        closed = False

        def send(self, message):
            pass

        def recv(self, timeout):
            return next(messages)

        def close(self):
            self.closed = True

    socket = Socket()
    monkeypatch.setattr(website_server, "app_server_connect", lambda endpoint: socket)
    take_stream_activity(monkeypatch, [], [])
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(host, "_hold_waiter", lambda *args: None)
    monkeypatch.setattr(
        website_server, "prepare_codex_delivery", lambda *args: prepared
    )
    monkeypatch.setattr(
        website_server,
        "open_app_server_delivery",
        lambda *args: "leaf-turn",
    )
    monkeypatch.setattr(
        website_server, "next_unaccepted_agent_event", lambda *args, **kwargs: None
    )
    finished = []
    completed = threading.Event()

    def finish(*args):
        finished.append(args)
        completed.set()

    monkeypatch.setattr(host, "_finish_turn", finish)

    assert (
        host._start_thread(
            page_dir,
            type("Process", (), {"pid": os.getpid()})(),
            comment["id"],
        )
        == "hosted-thread"
    )

    assert completed.wait(timeout=STATED_TIMEOUT)
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            "leaf-turn",
            {"id": "initial-turn", "status": "completed"},
        )
    ]
    assert socket.closed


def test_the_website_host_keeps_its_claim_listening_through_the_agent_turn(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(
        host,
        "_send",
        lambda *args: {"turn": {"id": "app-server-turn"}},
    )

    try:
        follow = host._start_turn(
            "socket",
            page_dir,
            "hosted-thread",
            type("Process", (), {"pid": os.getpid()})(),
        )
        # The reading is the turn's, so it starts when the follower opens the turn
        # rather than when the request that made it went out.
        follow.begin()
        state = website_server.full_state(page_dir, read_events(page_dir))

        assert state["listening"] is True
        assert state["activity"]["kind"] == "working"
        assert state["activity"]["detail"] == "Starting"
        assert state["activity"]["obligations"][0]["event"] == comment["id"]

        website_server.set_stream_activity(
            "hosted-thread", "app-server-turn", "Editing index.html"
        )
        working = website_server.full_state(page_dir, read_events(page_dir))
        assert working["activity"]["kind"] == "working"
        assert working["activity"]["detail"] == "Editing index.html"
    finally:
        host.close()

    assert (
        website_server.full_state(page_dir, read_events(page_dir))["listening"] is False
    )


def test_the_starting_connection_projects_codex_activity(page_dir, monkeypatch, capsys):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    messages = iter(
        [
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 1_000,
                        "item": {
                            "id": "command-1",
                            "type": "commandExecution",
                            "command": "leaf version check .",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 1_080,
                        "item": {
                            "id": "command-1",
                            "type": "commandExecution",
                            "command": "leaf version check .",
                            "status": "completed",
                            "exitCode": 0,
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "startedAtMs": 2_000,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
                        "completedAtMs": 2_500,
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Deployment verified.",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "initial-turn",
                            "status": "completed",
                            "items": [
                                {
                                    "id": "message-1",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Deployment verified.",
                                }
                            ],
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
    updates = []
    clears = []
    streamed = []
    committed = []

    class ReplyStream:
        def __init__(self, session, turn, delivery, target):
            streamed.append((session, turn, delivery, dict(target)))

        def update(self, update):
            message = update.get("message") if update is not None else None
            if message is not None and message["phase"] == "final_answer":
                streamed.append((message["text"], message["complete"]))
                return True
            return False

        def finish(self, state, text):
            committed.append((state, text))

    take_stream_activity(monkeypatch, updates, clears)
    monkeypatch.setattr(leaf_codex, "AppServerReplyStream", ReplyStream)

    host = website_server.WebsiteCodexHost("codex")
    finished = []
    monkeypatch.setattr(host, "_finish_turn", lambda *args: finished.append(args))
    hosted_follower(host, page_dir, prepared, socket, turn_id="initial-turn").follow()

    assert updates == [
        ("hosted-thread", "initial-turn", "Starting"),
        ("hosted-thread", "initial-turn", "Running leaf version check ."),
        ("hosted-thread", "initial-turn", "Deployment verified."),
    ]
    # The turn's own reading and no other. A completed turn's reading is released
    # both as its completion is folded and again when the follower accounts for the
    # turn, which is one reading gone rather than two calls worth pinning.
    assert set(clears) == {("hosted-thread", "initial-turn")}
    assert streamed == [
        (
            "hosted-thread",
            "initial-turn",
            prepared.payload["id"],
            {
                "page": str(page_dir),
                "reply_to": comment["id"],
                "responds": comment["id"],
            },
        ),
        ("Deployment verified.", True),
    ]
    assert committed == [("completed", "Deployment verified.")]
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["event"] for record in logs] == [
        "turn_following_started",
        "turn_delivery_bound",
        "turn_first_notification",
        "turn_first_activity",
        "turn_item_started",
        "turn_item_completed",
        "turn_item_started",
        "turn_item_completed",
        "turn_first_model_message",
        "turn_reply_first_text_published",
        "turn_stream_completed",
        # The reply above is this test's stand-in, which records the commit rather
        # than writing it, so the move it was answering is still owed one.
        "turn_failure_reported",
    ]
    assert logs[4] == {
        "component": "leaf-agent",
        "event": "turn_item_started",
        "eventId": comment["id"],
        "turnId": "initial-turn",
        "itemId": "command-1",
        "itemType": "commandExecution",
        "itemAtMs": 1_000,
    }
    assert logs[5]["durationMs"] == 80
    assert logs[5]["status"] == "completed"
    assert logs[5]["exitCode"] == 0
    assert logs[7]["durationMs"] == 500
    assert logs[8]["phase"] == "final_answer"
    assert logs[9]["recovered"] is False
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            website_server.page_claim(page_dir)["turn"],
            {
                "id": "initial-turn",
                "status": "completed",
                "items": [
                    {
                        "id": "message-1",
                        "type": "agentMessage",
                        "phase": "final_answer",
                        "text": "Deployment verified.",
                    }
                ],
            },
        )
    ]
    assert socket.closed


def test_a_stream_that_goes_silent_ends_its_turn_like_a_dropped_one(
    page_dir, monkeypatch
):
    """Silence past the bound ends the turn, because nothing else can end it.

    The subscription that has gone quiet is the one that would carry the turn's
    completion, so waiting longer only holds the reader on a page that says the
    agent is working. The turn is stopped, its reading comes off the page, and the
    reader is told no answer is coming.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    monkeypatch.setattr(website_server.HostedTurn, "silence", 0.0)

    class Socket:
        def __init__(self):
            self.closed = False

        def recv(self, timeout):
            raise TimeoutError

        def close(self):
            self.closed = True

    silent = Socket()
    host = website_server.WebsiteCodexHost("codex")
    interrupts = []
    monkeypatch.setattr(
        host,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    # Without the lease this page is not listening, and a page that is not
    # listening reads `away` whatever its stream reading holds — which would pass
    # the activity assertion below on a follower that left one standing.
    host._hold_waiter(page_dir, "hosted-thread")

    hosted_follower(host, page_dir, prepared, silent).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert interrupts == [("hosted-thread", "app-server-turn")]
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert website_server.full_state(page_dir, events)["activity"]["kind"] != "working"
    assert silent.closed


def test_a_follower_fault_of_any_shape_still_releases_its_website_turn(
    page_dir, monkeypatch, capsys
):
    """The follower owes its turn an outcome for every fault, not a listed few.

    A fault the stream handler does not name would otherwise leave the claim open with
    the activity its first line set, which is a page that reads working for as long as
    the container lives and never reaches a receipt. Catching it takes the traceback
    the excepthook used to print, so the turn's own record has to name the fault.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            raise KeyError("params")

        def close(self):
            self.closed = True

    socket = Socket()
    host = website_server.WebsiteCodexHost("codex")
    interrupts = []
    monkeypatch.setattr(
        host,
        "_interrupt",
        lambda thread_id, turn_id, **fields: interrupts.append((thread_id, turn_id)),
    )
    hosted_follower(host, page_dir, prepared, socket).follow()

    events = read_events(page_dir)
    [reply] = [event for event in events if event["kind"] == "reply"]
    assert (reply["responds"], reply["failure"]) == (comment["id"], "turn_failed")
    assert interrupts == [("hosted-thread", "app-server-turn")]
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    activity = website_server.full_state(page_dir, events)["activity"]
    assert activity["kind"] != "working"
    assert activity["obligations"] == []
    assert socket.closed
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    [completed] = [
        record for record in logs if record["event"] == "turn_stream_completed"
    ]
    assert (completed["status"], completed["error"]) == ("failed", "KeyError")


def test_an_empty_final_is_not_logged_as_visible_reply(page_dir, capsys):
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        def __init__(self):
            self.closed = False
            self.messages = iter(
                [
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turnId": "app-server-turn",
                            "startedAtMs": 1,
                            "completedAtMs": 2,
                            "item": {
                                "id": "empty-answer",
                                "type": "agentMessage",
                                "phase": "final_answer",
                                "text": "",
                            },
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "app-server-turn",
                                "status": "completed",
                                "items": [],
                            },
                        },
                    },
                ]
            )

        def recv(self, timeout):
            return json.dumps(next(self.messages))

        def close(self):
            self.closed = True

    socket = Socket()
    host = website_server.WebsiteCodexHost("codex")
    hosted_follower(host, page_dir, prepared, socket).follow()

    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert "turn_reply_first_text_published" not in {record["event"] for record in logs}
    assert socket.closed


def test_a_native_final_message_never_becomes_a_leaf_reply(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    [delivery] = accept_codex_delivery("hosted-thread")
    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        {"id": "app-server-turn", "status": "completed", "error": None},
    )

    events = read_events(page_dir)
    assert not any(event["kind"] == "reply" for event in events)
    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == delivery["turn"]
    assert claim["turn_closed"] is not None
    assert [
        obligation["event"]
        for obligation in website_server.full_state(page_dir, events)["activity"][
            "obligations"
        ]
    ] == [comment["id"]]


def test_an_invalid_source_still_releases_a_finished_website_turn(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    [delivery] = accept_codex_delivery("hosted-thread")
    (page_dir / "index.html").write_text("<main>unfinished")

    with pytest.raises(ValueError):
        website_server.WebsiteCodexHost("codex")._finish_turn(
            page_dir,
            "hosted-thread",
            delivery["turn"],
            {"id": "app-server-turn", "status": "completed", "error": None},
        )

    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == delivery["turn"]
    assert claim["turn_closed"] is not None
    assert website_server.PageTransaction(page_dir).status["state"] == "waiting"
    assert [
        obligation["event"]
        for obligation in website_server.full_state(page_dir, read_events(page_dir))[
            "activity"
        ]["obligations"]
    ] == [comment["id"]]


def test_a_rejected_streamed_reply_still_releases_its_website_turn(page_dir):
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )

    class Socket:
        closed = False

        def recv(self, timeout):
            # The turn's own work left the page unopenable, which is what the
            # commit below meets when it tries to close the turn on it.
            (page_dir / "index.html").write_text("<main>unfinished")
            return json.dumps(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {
                            "id": "app-server-turn",
                            "status": "completed",
                            "items": [
                                {
                                    "id": "answer",
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "Done.",
                                }
                            ],
                        },
                    },
                }
            )

        def close(self):
            self.closed = True

    socket = Socket()
    with pytest.raises(ValueError, match="unclosed tags"):
        host = website_server.WebsiteCodexHost("codex")
        hosted_follower(host, page_dir, prepared, socket).follow()

    claim = website_server.page_claim(page_dir)
    assert claim["turn_closed"] is not None
    reply = website_server.PageTransaction(page_dir).status["stream"]["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "failed",
        "Done.",
        False,
    )
    # The page the turn left cannot take the answer, and closing the turn on it is
    # what raised — so the receipt is the only thing the reader can still be given,
    # and it is owed exactly where the rest of the account failed.
    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert receipt["failure"] == "turn_failed"
    assert socket.closed


def test_a_reply_that_cannot_be_written_still_closes_its_website_turn(
    page_dir, monkeypatch
):
    """The page stops saying the agent is working, however the reply went.

    `DeliveryReply` guards only the commit of a completed answer: setting the state
    and releasing the binding open page transactions of their own, and the turn's own
    work may have left that page unopenable. The turn has ended either way, and until
    its Leaf turn closes the page tells its reader the agent is working, with nothing
    but the claim's grace to correct it — and the move it was carrying goes without
    the receipt that says no answer is coming.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    host = website_server.WebsiteCodexHost("codex")
    turn = hosted_follower(host, page_dir, prepared)
    turn.begin()

    def unopenable(*_args):
        raise OSError("the page could not be opened")

    monkeypatch.setattr(leaf_codex.DeliveryReply, "_set_state", unopenable)
    with pytest.raises(OSError, match="could not be opened"):
        turn.commit({"id": "app-server-turn", "status": "completed", "items": []})

    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    [receipt] = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert (receipt["responds"], receipt["failure"]) == (comment["id"], "turn_failed")


def test_a_finished_website_turn_does_not_overwrite_an_agent_reply(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    [delivery] = accept_codex_delivery("hosted-thread")
    website_server.cmd_reply(
        page_dir,
        comment["id"],
        "Done.",
        "",
        for_event=comment["id"],
        identity={"agent": "Leaf guide", "session": "leaf-website-agent"},
    )
    with website_server.PageTransaction(page_dir) as page:
        page.set_status("working", "Finishing")
    before = read_events(page_dir)

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        {"id": "app-server-turn", "status": "completed", "error": None},
    )

    assert read_events(page_dir) == before
    assert website_server.PageTransaction(page_dir).status["state"] == "waiting"


def test_a_host_receipt_does_not_answer_input_an_agent_turn_already_claimed(
    page_dir,
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    harness = website_server.website_harness("hosted-thread", os.getpid())
    website_server.prepare_codex_delivery(page_dir, harness)
    accept_codex_delivery("hosted-thread")

    reply = website_server.cmd_reply(
        page_dir,
        comment["id"],
        "The host could not start this task.",
        "",
        for_event=comment["id"],
        attempt=website_server.agent_attempt(comment["id"]),
        skip_if_settled=True,
        only_if_unclaimed=True,
        identity={"agent": "Leaf guide", "session": "leaf-website-agent"},
    )

    assert reply is None


def test_a_host_receipt_survives_an_invalid_candidate_source(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    (page_dir / "index.html").write_text("<main>unfinished")

    reply = website_server.WebsiteCodexHost("codex").failure_receipt(
        page_dir, comment["id"], "startup_failed"
    )

    assert reply is not None
    assert reply["responds"] == comment["id"]


def test_a_receipt_waits_for_external_turn_acceptance_to_be_recorded(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    process = type("Process", (), {"pid": os.getpid()})()
    turn_started = threading.Event()
    record_acceptance = threading.Event()
    receipt_waiting = threading.Event()

    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            if self.lock.locked():
                receipt_waiting.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    host.lock = ObservedLock()
    monkeypatch.setattr(host, "_ensure_server", lambda: process)

    def start_thread(page, process, event_id):
        website_server.prepare_codex_delivery(
            page, website_server.website_harness("hosted-thread", process.pid)
        )
        turn_started.set()
        record_acceptance.wait(timeout=STATED_TIMEOUT)
        accept_codex_delivery("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(host, "_start_thread", start_thread)

    with ThreadPoolExecutor(max_workers=2) as pool:
        attached = pool.submit(host.attach, page_dir, comment["id"])
        assert turn_started.wait(timeout=STATED_TIMEOUT)
        settled = pool.submit(
            host.failure_receipt,
            page_dir,
            comment["id"],
            "startup_failed",
        )

        assert receipt_waiting.wait(timeout=STATED_TIMEOUT)
        record_acceptance.set()
        assert attached.result(timeout=STATED_TIMEOUT) == "hosted-thread"
        assert settled.result(timeout=STATED_TIMEOUT) is None
    assert not any(
        event["kind"] == "reply" and event.get("parent") == comment["id"]
        for event in read_events(page_dir)
    )


def test_an_old_website_completion_does_not_close_the_new_leaf_turn(page_dir):
    first = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    harness = website_server.website_harness("hosted-thread", os.getpid())
    website_server.prepare_codex_delivery(page_dir, harness)
    [old_delivery] = accept_codex_delivery("hosted-thread")
    website_server.close_session_turn("hosted-thread")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    website_server.prepare_codex_delivery(page_dir, harness)
    [new_delivery] = accept_codex_delivery("hosted-thread")

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        old_delivery["turn"],
        {"id": "old-app-turn", "status": "failed", "error": None},
    )

    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == new_delivery["turn"]
    assert claim["turn_closed"] is None
    replies = {
        event["parent"]: event["text"]
        for event in read_events(page_dir)
        if event["kind"] == "reply"
    }
    assert replies == {}
    state = website_server.full_state(page_dir, read_events(page_dir))
    assert [item["event"] for item in state["activity"]["obligations"]] == [
        first["id"],
        second["id"],
    ]


def test_a_website_example_uses_the_real_page_server(page_dir, tmp_path, monkeypatch):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("document.body.dataset.site = 'example';\n")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    agent_host = FakeCodexHost()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_host)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        assert get(f"{root}/health")[0] == b"ok\n"

        document, headers = get(f"{root}/examples/decision/")
        assert b'src="/examples/decision/sitenote.js"' in document
        artifact = revision_path(published, 1).stem
        assert (
            f'data-lf-entry="/examples/decision/revisions/{artifact}/leaf.js"'.encode()
            in document
        )
        assert headers["Content-Security-Policy"] == "frame-ancestors 'none'"
        assert headers["Leaf-Session"] == "active"

        # A released document sends the public startup beacon, which the deployed site
        # answers at the edge. Nothing stands in front of this adapter, so it owes the
        # browser the same empty acknowledgement — a 404 here is a console error on
        # every page the site serves.
        assert b'data-lf-release="' in document
        beacon = urllib.request.Request(
            f"{root}/examples/decision/api/performance",
            data=json.dumps({"version": 1, "outcome": "presented"}).encode(),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )
        with urllib.request.urlopen(beacon) as recorded:
            assert recorded.status == 204
            assert recorded.read() == b""

        raw_state, headers = get(f"{root}/examples/decision/api/state")
        state = json.loads(raw_state)
        assert state["publication"] == {
            "kind": "example",
            "agent": "Leaf guide",
            "install_url": "/#install",
        }
        assert headers["Leaf-Layer"] == state["layer"]["generation"]
        assert headers["Leaf-Session"] == "active"

        raw_view, _ = get(
            verify_site.activation_url(f"{root}/examples/decision/", state)
        )
        view = json.loads(raw_view)
        revision = state["active"]["revision"]
        assert view["browser"]["views"][str(revision)]["basis"] == {
            "revision": revision,
            "through_seq": state["events"][-1]["seq"] if state["events"] else 0,
        }
        # The comparison base carries its own Ask reading, because the browser reads
        # which Asks a revision holds rather than folding the declarations again.
        assert set(view["browser"]["views"][str(revision)]["document"]["asks"]) == {
            "all",
            "reader",
            "unanswered",
            "awaiting",
            "unanswered_awaiting",
        }

        posted = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "text": "This came through the public example.",
            "anchor": {"section": "plan"},
            "attempt": "website-example-01",
        }
        answer, _ = post(
            f"{root}/examples/decision/api/event",
            posted,
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        assert answer["ok"] is True
        comment = read_events(published)[-1]
        assert comment["text"] == posted["text"]
        assert (
            next(
                event
                for event in answer["state"]["events"]
                if event.get("attempt") == posted["attempt"]
            )["id"]
            == comment["id"]
        )
        assert comment["id"] in {
            obligation["event"]
            for obligation in answer["state"]["activity"]["obligations"]
        }

        started, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_host.attached == [published]

        for refused in (
            {},
            {"failure": "unknown"},
            {"failure": None},
            # The words are the adapter's, declared beside the code, so a Worker that
            # sends its own is one copy of them too many rather than an override.
            {"failure": "startup_failed", "text": "Failure"},
            # And `turn_failed` says a turn was followed to nothing, which only the
            # code that followed it can say.
            {"failure": "turn_failed"},
        ):
            with pytest.raises(urllib.error.HTTPError) as invalid:
                post(
                    f"{root}/examples/decision/_leaf/agent/reply",
                    {"event": comment["id"], **refused},
                )
            assert invalid.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as forged:
            post(
                f"{root}/examples/decision/api/event",
                {
                    "kind": "reply",
                    "parent": comment["id"],
                    "revision": revision,
                    "text": "Forged host failure",
                    "failure": "startup_failed",
                    "attempt": "forged-host-failure",
                },
                {"Leaf-Layer": state["layer"]["generation"]},
            )
        assert forged.value.code == 400
        monkeypatch.setenv("LEAF_AGENT", "Leaf guide")
        monkeypatch.setenv("LEAF_SESSION_ID", "leaf-website-agent")
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        appended, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "failure": "startup_failed"},
        )
        reply = read_events(published)[-1]
        assert appended == {"status": "appended", "event": reply["id"]}
        assert reply == {
            "kind": "reply",
            "author": "agent",
            "agent": "Leaf guide",
            "session": "leaf-website-agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": website_server.FAILURE_RECEIPTS["startup_failed"],
            "failure": "startup_failed",
            "attempt": f"website-agent-{comment['id']}",
            "id": reply["id"],
            "ts": reply["ts"],
            "seq": reply["seq"],
        }
        served, _ = get(f"{root}/examples/decision/api/state")
        failures = [
            event for event in json.loads(served)["events"] if "failure" in event
        ]
        assert [event["id"] for event in failures] == [reply["id"]]
        assert verify_site.startup_failed(failures)
        assert verify_site.deployment_answer(failures) is None
        repeated, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "failure": "startup_failed"},
        )
        assert repeated == appended
        assert (
            len(
                [
                    event
                    for event in read_events(published)
                    if event.get("attempt") == f"website-agent-{comment['id']}"
                ]
            )
            == 1
        )

        assert get(f"{root}/examples/decision/sitenote.js")[0].startswith(
            b"document.body"
        )
        with pytest.raises(urllib.error.HTTPError) as stopped:
            urllib.request.urlopen(f"{root}/examples/missing/")
        assert stopped.value.code == 404


def test_a_turn_that_never_answered_is_reported_before_the_threads_panel():
    """The deployment gate names the turn it read, not the panel it looked at.

    A hosted turn that publishes nothing and replies nothing leaves Threads with no
    reply to draw, so the panel reading is a symptom. The complaint has to carry the
    revision the page reached, the activity it stood under, and the receipts it
    collected, because that reading is the only account of why the turn stopped.
    """
    stalled = verify_site.TurnReading(
        {"active": {"revision": 1}, "activity": {"kind": "answering"}}, None, [], None
    )
    with pytest.raises(RuntimeError) as stopped:
        verify_site.check_turn_answered(
            "https://leaf.page/examples/triage-board/",
            "Deployment 446b8fe9 verified",
            stalled,
            1,
            1,
        )
    assert str(stopped.value) == (
        "https://leaf.page/examples/triage-board/ agent did not publish "
        "‘Deployment 446b8fe9 verified’; it reached revision 1 from 1 "
        "with the page reading answering and did not reply"
    )

    answered = verify_site.TurnReading(
        {"active": {"revision": 2}, "activity": {"kind": "listening"}},
        {"revision": 2},
        [{"text": "deployment verified"}],
        {"text": "deployment verified"},
    )
    verify_site.check_turn_answered(
        "https://leaf.page/examples/triage-board/",
        "Deployment 446b8fe9 verified",
        answered,
        1,
        1,
    )


def test_a_stale_layer_is_answered_with_the_generation_the_container_holds(
    page_dir, tmp_path
):
    """What a reader posting into a draining rollout gets back.

    A container carries the layer of the image it runs, so a session allocated on a
    previous image answers a newer generation with its own rather than with state.
    The website deploy gate reads that answer, so it has to be the shape it names.
    """
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, FakeCodexHost())
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        state = json.loads(get(f"{root}/examples/decision/api/state")[0])
        before = read_events(published)
        answer, headers = post(
            f"{root}/examples/decision/api/event",
            {
                "kind": "comment",
                "revision": state["active"]["revision"],
                "text": "Posted under a layer this container does not speak.",
                "attempt": "stale-layer-01",
            },
            {"Leaf-Layer": "a-layer-from-another-release"},
        )
        generation = state["layer"]["generation"]
        assert answer == {"layer": generation}
        assert headers["Leaf-Layer"] == generation
        assert read_events(published) == before


@pytest.mark.parametrize(
    ("page_root", "name"), [("", "index"), ("/examples", "examples")]
)
def test_a_product_route_uses_the_same_real_page_server(
    page_dir, tmp_path, page_root, name
):
    site = tmp_path / "site"
    published = site / "_leaf" / "pages" / name
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {page_root or "/": (f"_leaf/pages/{name}", "product")})

    agent_host = FakeCodexHost()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_host)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        document, _ = get(f"{root}{page_root}/")
        assert b"data-lf-site" not in document
        artifact = revision_path(published, 1).stem
        assert (
            f'data-lf-entry="{page_root}/revisions/{artifact}/leaf.js"'.encode()
            in document
        )
        assert get(f"{root}{page_root}/sitenote.js")[0] == b"export {};"
        state = json.loads(get(f"{root}{page_root}/api/state")[0])
        assert state["publication"] == {
            "kind": "product",
            "agent": "Leaf guide",
            "install_url": "/#install",
        }
        posted = {
            "kind": "comment",
            "revision": state["active"]["revision"],
            "text": "Can the product-page agent read this?",
            "anchor": {"section": "plan"},
            "attempt": f"website-product-{name}",
        }
        answer, _ = post(
            f"{root}{page_root}/api/event",
            posted,
            {"Leaf-Layer": state["layer"]["generation"]},
        )
        comment = next(
            event
            for event in answer["state"]["events"]
            if event.get("attempt") == posted["attempt"]
        )
        started, _ = post(
            f"{root}{page_root}/_leaf/agent/start", {"event": comment["id"]}
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_host.attached == [published]


def test_a_retried_agent_start_returns_the_accepted_task(page_dir, tmp_path):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    comment = append_event(
        published,
        {"kind": "comment", "author": "user", "text": "edit this"},
    )
    website_server.prepare_codex_delivery(
        published,
        website_server.website_harness("already-started-thread", os.getpid()),
    )
    accept_codex_delivery("already-started-thread")
    agent_host = FakeCodexHost()
    httpd = LeafHTTPServer(
        ("127.0.0.1", 0), website_server.site_endpoint(site, agent_host)
    )
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    with running_http_server(httpd):
        answer, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )

        assert answer == {"status": "started", "thread": "already-started-thread"}
        assert agent_host.attached == []


def test_an_agent_reply_is_dropped_when_a_newer_reader_turn_overtakes_it(
    page_dir, tmp_path
):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = LeafHTTPServer(("127.0.0.1", 0), website_server.site_endpoint(site))
    root = f"http://127.0.0.1:{httpd.server_address[1]}/examples/decision"
    with running_http_server(httpd):
        state = json.loads(get(f"{root}/api/state")[0])
        headers = {"Leaf-Layer": state["layer"]["generation"]}
        post(
            f"{root}/api/event",
            {
                "kind": "comment",
                "revision": state["active"]["revision"],
                "text": "First question",
                "attempt": "first-question-01",
            },
            headers,
        )
        first = read_events(published)[-1]
        post(
            f"{root}/api/event",
            {
                "kind": "reply",
                "parent": first["id"],
                "revision": state["active"]["revision"],
                "text": "A more specific follow-up",
                "attempt": "second-question-1",
            },
            headers,
        )

        answer, _ = post(
            f"{root}/_leaf/agent/reply",
            {"event": first["id"], "failure": "rate_limited"},
        )

        assert answer == {"status": "settled"}
        stale = website_server.FAILURE_RECEIPTS["rate_limited"]
        assert all(event.get("text") != stale for event in read_events(published))


def test_the_preview_generator_uses_the_live_website_route(page_dir, tmp_path):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("document.body.dataset.site = 'example';\n")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    with example_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/decision/api/state")[0])

    assert state["publication"] == {
        "kind": "example",
        "agent": "Leaf guide",
        "install_url": "/#install",
    }


def test_the_preview_generator_bootstraps_a_new_catalog_entry(tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    existing = current / "example-existing.jpg"
    source_preview = next(example_previews.locked_previews().glob("example-*.jpg"))
    shutil.copy2(source_preview, existing)
    source = ROOT / "examples" / "ideas-to-implement.html"
    sources = [source]
    monkeypatch.setattr(example_previews, "locked_previews", lambda: current)
    monkeypatch.setattr(example_previews, "catalog_sources", lambda: sources)
    monkeypatch.setattr(example_previews.site_build, "catalog_sources", lambda: sources)
    monkeypatch.setattr(
        example_previews.site_build, "published_page_sources", lambda: sources
    )

    previews = example_previews.bootstrap_previews(tmp_path / "previews")
    site = tmp_path / "site"
    example_previews.site_build.build_examples(site, catalog_previews=previews)

    assert (
        previews / "example-ideas-to-implement.jpg"
    ).read_bytes() == existing.read_bytes()
    with example_previews.serve_examples(site) as root:
        state = json.loads(get(f"{root}/examples/ideas-to-implement/api/state")[0])
    assert state["publication"]["kind"] == "example"


def test_the_preview_generator_updates_every_linked_example_image(
    tmp_path, monkeypatch
):
    docs = tmp_path / "docs"
    docs.mkdir()
    preview = tmp_path / "example-decision.jpg"
    preview.write_bytes(b"new decision preview")
    old = "/media/0123456789abcdef.jpg"
    expected = hashlib.sha256(preview.read_bytes()).hexdigest()[:16]
    (docs / "examples.html").write_text(
        f'<a class="example-link" href="/examples/decision/">\n'
        f'  <span><img src="{old}"></span>\n'
        "</a>\n",
        encoding="utf-8",
    )
    (docs / "index.html").write_text(
        f'<a href="/examples/decision/"><img src="{old}" loading="lazy"></a>\n'
        f'<img src="{old}" alt="unlinked">\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(example_previews, "DOCS", docs)

    example_previews.update_catalog({preview})

    replacement = f"/media/{expected}.jpg"
    assert replacement in (docs / "examples.html").read_text()
    home = (docs / "index.html").read_text()
    assert replacement in home
    assert f'<img src="{old}" alt="unlinked">' in home


def test_a_failed_verifier_page_reports_its_browser_errors(browser):
    page = browser.new_page()
    failures = verify_site.observe_startup(page)
    url = "https://site-verifier.test/broken"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<!doctype html><body><script>
                  console.error('widget resource unavailable');
                  throw new Error('runtime initialization failed');
                </script></body>""",
        ),
    )
    page.goto(url)
    with pytest.raises(RuntimeError) as caught:
        verify_site.await_presentation(page, url, failures, timeout=100)
    assert "widget resource unavailable" in str(caught.value)
    assert "runtime initialization failed" in str(caught.value)
    assert "no startup milestone" in str(caught.value)
    # The same two faults the verifier reported are what this page said.
    consume_browser_errors(
        page, "widget resource unavailable", "runtime initialization failed"
    )


def test_the_agent_response_clock_waits_until_the_reply_is_on_screen(browser):
    page = browser.new_page()
    verify_site.observe_startup(page)
    url = "https://site-verifier.test/visible-response"
    page.route(
        url,
        lambda route: route.fulfill(
            content_type="text/html",
            body="""<div class="lf-threads" style="height: 100px; overflow: auto">
                  <div style="height: 500px"></div>
                  <div class="lf-msg agent"><span class="lf-msg-text">Visible reply</span></div>
                </div>""",
        ),
    )
    page.goto(url)
    page.evaluate("window.__leafVerifier.startVisibleReplyClock")
    page.wait_for_timeout(100)
    assert page.evaluate("window.__leafVerifier.visibleReplyAt") is None

    page.locator(".lf-msg.agent").scroll_into_view_if_needed()
    page.wait_for_function("window.__leafVerifier.visibleReplyRecorded")
    assert page.evaluate("window.__leafVerifier.visibleReplyAt") is not None


def test_a_page_that_never_presents_names_itself_and_how_far_it_got():
    """The site gate's own timeout says nothing; the message it raises has to.

    A red `Measure the bundled release in Chrome` step carried only Playwright's
    wait, so a reader could not tell which of the three pages stalled, nor whether
    widget upgrade or the first state read was the one that never answered.
    """
    stalled = verify_site.unpresented(
        "https://leaf.page/examples/triage-board/", ["upgraded"], []
    )
    assert "examples/triage-board" in stalled
    assert "upgraded" in stalled

    early = verify_site.unpresented("https://leaf.page/", [], ["widget module 404"])
    assert "no startup milestone" in early
    assert "widget module 404" in early


def test_the_deploy_gate_waits_on_the_page_rather_than_its_own_clock(page_dir):
    """A hosted turn's pace is the model's, so the wait reads the page's own account.

    `publish-site` failed three deployments in one morning with `agent published but
    did not reply` — a turn that had edited the page and was still working when the
    gate's fixed five minutes ran out. The gate now extends its wait only while the
    page still names an outstanding obligation and a turn on it, so a slow turn is
    given the time and a settled one ends the wait whatever the clock says.
    """
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        website_server.website_harness("hosted-thread", os.getpid()),
    )
    [delivery] = accept_codex_delivery("hosted-thread")

    handling = website_server.full_state(page_dir, read_events(page_dir))
    assert handling["activity"]["kind"] == "handling"
    assert verify_site.still_answering(handling, comment["id"])
    # Another page's comment is not this gate's turn, whatever this page is doing.
    assert not verify_site.still_answering(handling, "another-event")

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        {"id": "app-server-turn", "status": "completed", "error": None},
    )

    stopped = website_server.full_state(page_dir, read_events(page_dir))
    assert [
        obligation["event"] for obligation in stopped["activity"]["obligations"]
    ] == [comment["id"]]
    assert not verify_site.still_answering(stopped, comment["id"])


def test_the_deploy_gate_stops_waiting_on_a_page_with_no_agent_on_the_comment():
    """The other half of the same reading: nothing is coming, so do not wait it out.

    A container that dropped its session leaves the obligation standing with no turn
    behind it. Extending the wait there would spend the step's whole budget to raise
    the failure it could already raise.
    """
    obligation = {"event": "comment-id", "dropped": False}
    for kind in ("away", "unheld", "stalled", "closed", "listening"):
        state = {"activity": {"kind": kind, "obligations": [obligation]}}
        assert not verify_site.still_answering(state, "comment-id")
    dropped = {
        "activity": {
            "kind": "working",
            "obligations": [{"event": "comment-id", "dropped": True}],
        }
    }
    assert not verify_site.still_answering(dropped, "comment-id")
    assert not verify_site.still_answering({}, "comment-id")


@pytest.mark.parametrize("failure", ["startup_failed", "rate_limited"])
def test_the_deploy_gate_reads_a_durable_host_failure(page_dir, failure):
    from leaf.event_contracts import event_record_error
    from leaf.registry.storage import load_registry

    host = website_server.WebsiteCodexHost("codex")
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    reply = host.failure_receipt(page_dir, comment["id"], failure)
    state = website_server.full_state(page_dir, read_events(page_dir))
    replies = [event for event in state["events"] if event["kind"] == "reply"]
    assert [event["id"] for event in replies] == [reply["id"]]
    contract = load_registry(page_dir)["$events"]["kinds"]["reply"]
    assert event_record_error(contract, replies[0]) is None
    assert verify_site.turn_failed(replies)
    assert verify_site.startup_failed(replies) == (failure == "startup_failed")
    assert verify_site.deployment_answer(replies) is None
    assert not state["activity"]["obligations"]


class _Read:
    ok = True
    status = 200

    def __init__(
        self,
        payload: dict,
        body: str = "",
        headers: dict | None = None,
        *,
        url: str = "",
        request=None,
    ):
        self.payload = payload
        self.body = body
        self.headers = headers or {}
        self.url = url
        self.request = request

    def json(self) -> dict:
        return self.payload

    def text(self) -> str:
        return self.body


class _PostedHeaders(_Read):
    """An intercepted browser POST whose body must remain the browser's to consume."""

    def json(self) -> dict:
        raise AssertionError("the verifier re-read the browser's POST response body")


class _StateReads:
    """One Playwright request context standing in for a page that is being read."""

    def __init__(self, states: list[dict]):
        self.states = states
        self.reads = 0
        self.request = self

    def get(self, url: str, **kwargs):
        state = self.states[min(self.reads, len(self.states) - 1)]
        self.reads += 1
        return _Read(state)


class _FailedFirstTurn:
    """A deployed page whose first startup fails and whose second ask succeeds."""

    def __init__(self, heading: str, failure: str = "startup_failed"):
        self.failure = failure
        self.heading = heading
        self.request = self
        self.comments: list[dict] = []
        self.draft = ""
        self.last_response = None

    def locator(self, selector: str):
        assert selector == ".lf-general textarea"
        return self

    def fill(self, text: str) -> None:
        self.draft = text

    def evaluate(self, script: str) -> float:
        assert script == "window.__leafVerifier.startVisibleReplyClock"
        return 100.0

    def press(self, key: str) -> None:
        assert key == "ControlOrMeta+Enter"
        attempt = f"attempt-{len(self.comments) + 1}"
        self.last_response = self.post(
            "https://leaf.page/examples/triage-board/api/event",
            {
                "kind": "comment",
                "revision": 1,
                "text": self.draft,
                "attempt": attempt,
            },
        )

    def expect_response(self, predicate):
        owner = self

        class ResponseInfo:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                assert predicate(owner.last_response)

            @property
            def value(self):
                return owner.last_response

        return ResponseInfo()

    def post(self, url: str, data: dict, **kwargs) -> _Read:
        comment = {
            "id": f"comment-{len(self.comments) + 1}",
            "attempt": data["attempt"],
            "revision": data["revision"],
        }
        self.comments.append(comment)
        request = SimpleNamespace(method="POST", post_data_json=data)
        return _PostedHeaders(
            {"state": {"events": [comment]}},
            url=url,
            request=request,
        )

    def get(self, url: str, **kwargs) -> _Read:
        if url.endswith("/api/state"):
            return _Read(self.state())
        return _Read({}, f"<h1>{self.heading}</h1>")

    def state(self) -> dict:
        events = [
            *self.comments,
            {
                "kind": "reply",
                "parent": "comment-1",
                "text": "The host could not start this task.",
                "failure": self.failure,
            },
        ]
        if len(self.comments) < 2:
            return {
                "active": {"revision": 1, "url": "revisions/1.html"},
                "activity": {"kind": "away", "obligations": []},
                "events": events,
            }
        events.append(
            {"kind": "reply", "parent": "comment-2", "text": "deployment verified"}
        )
        return {
            "active": {"revision": 2, "url": "revisions/2.html"},
            "activity": {"kind": "away", "obligations": []},
            "events": events,
        }


@pytest.mark.parametrize("failure", ["startup_failed", "rate_limited"])
def test_the_deploy_gate_retries_only_startup_failures(failure):
    """A startup retry gets a fresh attempt; a rate limit ends the pass immediately."""
    heading = "Deployment abcd1234 verified"
    context = _FailedFirstTurn(heading, failure)
    asked = verify_site.ask_until_answered(
        context,
        context,
        "https://leaf.page/examples/triage-board/",
        "https://leaf.page/examples/triage-board/api/state",
        "layer",
        "release",
        heading,
        {"active": {"revision": 1, "url": "revisions/1.html"}},
    )
    if failure == "rate_limited":
        assert asked.asks == 1
        assert asked.turn.answer is None
        assert len(context.comments) == 1
        return
    assert asked.asks == 2
    assert asked.turn.answer["text"] == "deployment verified"
    assert asked.turn.published["revision"] == 2
    first, second = context.comments
    assert first["attempt"] != second["attempt"]
    # The second ask continues the page the first turn left rather than an older one.
    assert second["revision"] == 1


def test_the_deploy_gate_reads_outcomes_independently_of_reply_wording():
    """`failure` decides, so the wording may change and old pages still read right."""
    for text in (
        "deployment verified",
        *website_server.FAILURE_RECEIPTS.values(),
        # Wordings this adapter has already written into pages that outlive it.
        "I couldn’t generate a reply just now. Please send a new message to try again.",
        "I finished without posting a reply. Please send a new message to try again.",
        "This public demo is busy right now. Please wait a minute, then send a new message.",
    ):
        answer = {"text": text}
        assert verify_site.deployment_answer([answer]) is answer
        assert not verify_site.turn_failed([answer])
        for failure in ("startup_failed", "rate_limited"):
            receipt = {"text": text, "failure": failure}
            assert verify_site.deployment_answer([receipt]) is None
            assert verify_site.turn_failed([receipt])


def test_startup_line_distinguishes_an_unobserved_state_request():
    startup = {
        "first_byte": 20,
        "document": 30,
        "paint": {"first-contentful-paint": 40},
        "upgraded": {"at": 50},
        "presented": {
            "at": 60,
            "js_loaded": 45,
            "state_loaded": None,
            "requests": 3,
            "bytes": 3072,
            "code_requests": 2,
            "code_bytes": 2048,
            "js_requests": 1,
            "js_bytes": 1024,
        },
    }

    line = verify_site.startup_line("page", startup)

    assert "JS fetched 45 ms" in line
    assert "state answered not observed" in line
    assert "state answered 0 ms" not in line


def test_startup_line_distinguishes_an_unobserved_first_paint():
    startup = {
        "first_byte": 20,
        "document": 30,
        "paint": {},
        "upgraded": {"at": 50},
        "presented": {
            "at": 60,
            "js_loaded": 45,
            "state_loaded": 55,
            "requests": 3,
            "bytes": 3072,
            "code_requests": 2,
            "code_bytes": 2048,
            "js_requests": 1,
            "js_bytes": 1024,
        },
    }

    line = verify_site.startup_line("page", startup)

    assert "first contentful paint not observed" in line
    assert "first contentful paint 0 ms" not in line


@pytest.mark.parametrize(
    "failure",
    ["startup_failed", "rate_limited"],
)
def test_the_deploy_gate_stops_reading_a_turn_the_container_has_closed(
    failure,
):
    """A host failure receipt is terminal, so the wait ends where it lands.

    Every other reading the wait takes is one a live turn can still be passing
    through, which is why they run to `TURN_PATIENCE`. This one is posted from where
    the container closes the turn, and waiting the budget out on it would spend five
    minutes before the second ask that follows it could even start.
    """
    comment = {"id": "comment-id"}
    working = {
        "active": {"revision": 1, "url": "revisions/1.html"},
        "activity": {
            "kind": "working",
            "obligations": [{"event": "comment-id", "dropped": False}],
        },
        "events": [
            {
                "kind": "reply",
                "parent": "comment-id",
                "text": "A newly worded host failure.",
                "failure": failure,
            }
        ],
    }
    context = _StateReads([working])
    profile = verify_site.AgentProfile()
    turn = verify_site.await_turn(
        context,
        "https://leaf.page/examples/triage-board/",
        "https://leaf.page/examples/triage-board/api/state",
        "layer",
        "release",
        comment,
        1,
        "Deployment abcd1234 verified",
        None,
        # Seconds rather than `TURN_LIMIT`: a wait that stopped reading this reply
        # would come back on the next assertion instead of running the real budget.
        time.monotonic() + 5,
        profile,
    )
    # One read, though the page still names a turn on the comment: the wait ended on
    # the reply rather than on `still_answering` or a clock.
    assert context.reads == 1
    assert verify_site.still_answering(working, "comment-id")
    assert turn.answer is None
    assert verify_site.turn_failed(turn.replies)


class _PresentationWait:
    def __init__(self, waits: list[int]):
        self.waits = waits

    def wait_for(self, timeout: int) -> None:
        self.waits.append(timeout)


class _Click:
    def __init__(self, clicks: list[str]):
        self.clicks = clicks

    def click(self) -> None:
        self.clicks.append("threads")


class _Heading:
    def __init__(self, text: str):
        self.text = text

    def inner_text(self) -> str:
        return self.text


class _DeployedPage:
    """The page the agent pass opens, reloads after its turn, and reads back."""

    def __init__(
        self,
        heading: str,
        revision: int,
        presented_at: float,
        reload_ok: bool = True,
        banner: str | None = None,
        follows_revision: bool = False,
        initial_presented_at: float | None = None,
    ):
        self.heading = heading
        self.revision = revision
        self.presented_at = presented_at
        self.reload_ok = reload_ok
        self.banner = banner
        self.follows_revision = follows_revision
        self.initial_presented_at = (
            presented_at if initial_presented_at is None else initial_presented_at
        )
        self.init_scripts: list[Path] = []
        self.presentation_waits: list[int] = []
        self.visible_reply_waits: list[int] = []
        self.revision_waits: list[tuple[int, int]] = []
        self.clicks: list[str] = []

    def add_init_script(self, *, path: Path) -> None:
        self.init_scripts.append(path)

    def on(self, event: str, handler) -> None:
        pass

    def goto(self, url: str, **kwargs) -> _Read:
        return _Read({})

    def reload(self, **kwargs) -> _Read:
        answered = _Read({})
        answered.ok = self.reload_ok
        return answered

    def wait_for_function(
        self, expression: str, *, arg: int | None = None, timeout: int
    ) -> None:
        if expression == "window.__leafVerifier.visibleReplyRecorded":
            self.visible_reply_waits.append(timeout)
            return
        assert expression == "window.__leafVerifier.revisionAtLeast" and arg is not None
        self.revision_waits.append((arg, timeout))
        if self.revision >= arg:
            return
        if self.follows_revision:
            self.revision = arg
            return
        raise verify_site.PlaywrightTimeout("revision did not arrive")

    def locator(self, selector: str):
        if selector == "h1":
            return _Heading(self.heading)
        if selector == ".lf-threads-toggle":
            return _Click(self.clicks)
        assert selector == "body[data-lf-presented]"
        return _PresentationWait(self.presentation_waits)

    def evaluate(self, script: str):
        if script == "window.__leafVerifier.startVisibleReplyClock":
            return 100.0
        if script == "window.__leafVerifier.visibleReplyAt":
            return 12_600.0
        if script == "window.__leafVerifier.startupReading":
            presented_at = (
                self.presented_at
                if len(self.presentation_waits) > 1
                else self.initial_presented_at
            )
            return {
                "first_byte": 100.0,
                "document": 200.0,
                "paint": {"first-contentful-paint": 250.0},
                "upgraded": {"at": 300.0},
                "presented": {
                    "at": presented_at,
                    "js_loaded": 275.0,
                    "state_loaded": presented_at - 100.0,
                    "js_requests": 16,
                    "js_bytes": 150 * 1024,
                    "code_requests": 20,
                    "code_bytes": 330 * 1024,
                    "requests": 24,
                    "bytes": 335 * 1024,
                },
            }
        if "presented?.at" in script:
            return self.presented_at
        if script == "window.__leafVerifier.revision":
            return str(self.revision)
        if script == "window.__leafVerifier.status":
            return self.banner
        return []


class _DeployedContainer:
    """The private container one activated reader session reaches, serving `release`."""

    def __init__(self, release: str, page: _DeployedPage):
        self.release = release
        self.page = page
        self.request = self
        self.closed = False

    def new_page(self) -> _DeployedPage:
        return self.page

    def get(self, url: str, headers: dict | None = None, **kwargs) -> _Read:
        answered = {"leaf-session": "active", "leaf-release": self.release}
        return _Read(
            {
                "active": {"revision": 1, "url": "revisions/1.html"},
                "layer": {"generation": "generation-1"},
                "release": self.release,
                "events": [],
            },
            headers=answered,
        )

    def close(self) -> None:
        self.closed = True


class _DeployedSite:
    def __init__(self, context: _DeployedContainer):
        self.context = context

    def new_context(self) -> _DeployedContainer:
        return self.context


class _RollingOutContainer:
    """An allocation the image rollout has not reached, so the edge answers for it."""

    def __init__(self, release: str, page: _DeployedPage):
        self.release = release
        self.page = page
        self.request = self
        self.closed = False

    def new_page(self) -> _DeployedPage:
        return self.page

    def get(self, url: str, headers: dict | None = None, **kwargs) -> _Read:
        if "api/view" not in url:
            return _Read(
                {
                    "active": {"revision": 1, "url": "revisions/1.html"},
                    "layer": {"generation": "generation-1"},
                    "release": self.release,
                    "events": [],
                },
                headers={"leaf-release": self.release, "leaf-session": "passive"},
            )
        # What `rollingOut` in `worker/src/index.ts` sends: the deployed release
        # rather than this container's, no session at all, and `Retry-After` naming
        # the rollout as the reason there is nothing to compare.
        starting = _Read(
            {},
            "this release is still starting",
            headers={"retry-after": "5", "leaf-release": self.release},
        )
        starting.ok = False
        starting.status = 503
        return starting

    def close(self) -> None:
        self.closed = True


class _RollingSite:
    """Successive allocations, so the gate's retry gets a fresh one each time."""

    def __init__(self, contexts: list):
        self.contexts = list(contexts)
        self.opened: list = []

    def new_context(self):
        context = self.contexts.pop(0) if len(self.contexts) > 1 else self.contexts[0]
        self.opened.append(context)
        return context


def _rolling_clock(monkeypatch, samples: list[float], slept: list[float]) -> None:
    readings = iter(samples)
    monkeypatch.setattr(
        verify_site,
        "time",
        SimpleNamespace(monotonic=readings.__next__, sleep=slept.append),
    )


def test_the_agent_pass_waits_out_an_allocation_the_rollout_has_not_reached(
    monkeypatch,
):
    """A rollout answered by the edge is the same wait as one read off a container.

    `publish-site` deployed release `a471af1a…` and its release pass verified
    leaf.page in Chrome; six seconds later the agent pass failed outright on
    `https://leaf.page/examples/triage-board/api/view?revision=1&through_seq=1
    returned 503` (run 35320758891). `api/view` activates a session, and until the
    container image rollout reaches the allocation it gets, the Worker unseats the
    session and answers `503` rather than handing a foreign release on. That is the
    condition this loop already waits out when the container answers for itself, so
    it has to end in the same retry rather than in a red deploy.
    """
    release = "a471af1a" + "0" * 56
    starting = _RollingOutContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    ready = _DeployedContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    slept: list[float] = []
    _rolling_clock(monkeypatch, [0.0, 12.0], slept)

    site = _RollingSite([starting, ready])
    session = verify_site.agent_session(site, release, origin="https://leaf.page")

    assert session.context is ready
    # The unseated allocation is dropped rather than carried into the turn.
    assert starting.closed and not ready.closed
    assert site.opened == [starting, ready]
    assert slept == [10]


def test_a_rollout_that_never_lands_ends_the_agent_pass_naming_it(monkeypatch):
    """The bound still holds, and the message says which reading ran it out."""
    release = "a471af1a" + "0" * 56
    starting = _RollingOutContainer(
        release, _DeployedPage("", revision=1, presented_at=900.0)
    )
    slept: list[float] = []
    _rolling_clock(monkeypatch, [0.0, 400.0], slept)

    with pytest.raises(RuntimeError) as failure:
        verify_site.agent_session(
            _RollingSite([starting]), release, origin="https://leaf.page"
        )

    assert "reached no container able to admit its agent's turn" in str(failure.value)
    assert verify_site.STILL_STARTING in str(failure.value)
    assert slept == []


class _Allocation:
    """One activating read, answering as the edge or as the container it reached."""

    def __init__(self, answer: _Read):
        self.answer = answer
        self.request = self
        self.asked: list[str] = []

    def get(self, url: str, **kwargs) -> _Read:
        self.asked.append(url)
        return self.answer


def _answered(status: int, headers: dict) -> _Read:
    answer = _Read({}, "this release is still starting", headers=headers)
    answer.ok = status < 400
    answer.status = status
    return answer


ACTIVATION = "https://leaf.page/examples/triage-board/api/view?revision=1&through_seq=1"


def test_the_rollout_answer_is_the_one_503_the_activating_read_waits_on():
    """Both passes make this request, so one function reads what comes back.

    Run 35320758891 printed `...api/view?revision=1&through_seq=1 returned 503` seven
    times: six inside the release pass's `until` loop, then the seventh in the agent
    pass, which ended the deploy. Every one was the Worker's own `rollingOut` answer,
    which says the deployment is still landing. A bare status cannot say that, and
    two investigations went to Cloudflare's control plane instead.
    """
    rolling = _Allocation(
        _answered(503, {"retry-after": "5", "leaf-release": "a" * 64})
    )

    assert verify_site.activation_read(rolling, ACTIVATION) is None
    assert rolling.asked == [ACTIVATION]


def test_a_503_the_worker_did_not_write_is_this_release_failing():
    """`Retry-After` separates the Worker's rollout answer from a container's own 503.

    A container answering `503` for itself comes back through the pass-through path
    without the header, and waiting that out would sit on a broken release until the
    workflow's deadline instead of reporting it.
    """
    broken = _Allocation(_answered(503, {"leaf-session": "active"}))

    with pytest.raises(RuntimeError) as failure:
        verify_site.activation_read(broken, ACTIVATION)

    assert str(failure.value) == f"{ACTIVATION} returned 503"


def test_the_page_a_turn_has_just_written_waits_for_its_revision_after_presentation(
    monkeypatch, capsys
):
    """One bound cannot serve both pages this gate reads, so the reload states its own.

    `publish-site` deployed release `4ef93dd9…` and then failed on the reload after a
    healthy turn: `never presented, reaching no startup milestone`. The pages the
    release pass walks come from the edge and present in about a second, which is what
    the default bound is for. The reloaded one is answered by a container that has just
    run a hosted model turn, whose first `/api/state` read costs seconds rather than
    milliseconds — measured against the live deployment, 123 ms before a turn and
    2252-3918 ms after one, on the same session and page.

    The gate gives the reload that bound both to present and, after presentation, to
    follow the revision its first read brings back. The second wait is required now that
    presentation no longer implies the read has answered.
    """
    release = "4ef93dd9" + "0" * 56
    heading = f"Deployment {release[:8]} verified"
    page = _DeployedPage(
        heading,
        revision=1,
        presented_at=28444.0,
        follows_revision=True,
        initial_presented_at=1400.0,
    )
    container = _DeployedContainer(release, page)
    published = {"revision": 2, "url": "revisions/2.html"}
    profile = verify_site.AgentProfile()
    profile.visible_reply_started_ms = 100.0
    profile.ask_count = 1
    profile.milestones = {
        "acknowledged 1": 0.250,
        "published": 12.0,
        "replied": 12.5,
        "answered": 12.5,
    }
    profile.activities = [
        (0.250, "queued", ""),
        (1.0, "working", "Editing the page"),
        (12.5, "away", ""),
    ]
    monkeypatch.setattr(
        verify_site,
        "ask_until_answered",
        lambda *args, **kwargs: verify_site.AgentAsks(
            verify_site.TurnReading(
                {"active": {"revision": 2}, "activity": {"kind": "away"}},
                published,
                [{"kind": "reply", "text": "deployment verified"}],
                {"kind": "reply", "text": "deployment verified"},
            ),
            1,
            1,
            profile,
        ),
    )
    # The first sample sets `agent_session`'s rollout deadline; the next two surround
    # the revision wait this case measures.
    following_clock = iter([0.0, 40.0, 42.5])
    with monkeypatch.context() as timing:
        timing.setattr(
            verify_site,
            "time",
            SimpleNamespace(monotonic=following_clock.__next__),
        )
        benchmark = verify_site.verify_agent_turn(
            _DeployedSite(container), None, origin="https://leaf.page"
        )

    # The ordinary first load uses the edge-page presentation bound. The post-turn
    # reload gets its own bound for both presentation and the later revision follow.
    assert page.presentation_waits == [30_000, verify_site.TURN_PRESENTATION]
    assert page.visible_reply_waits == [30_000]
    assert page.revision_waits == [(2, verify_site.TURN_PRESENTATION)]
    assert verify_site.TURN_PRESENTATION > 30_000
    # The stamps the message needs to say which stall it was. Without them a page that
    # upgraded and stalled on its first state read reports the same "no startup
    # milestone" as one whose modules never arrived.
    assert page.init_scripts == [verify_site.VERIFIER_SCRIPT]
    # A green run reports startup and the post-presentation revision follow separately.
    reported = capsys.readouterr().out
    assert "presented in 28444 ms" in reported
    assert "followed revision 2 2500 ms after presentation" in reported
    assert "request acknowledged 250 ms" in reported
    assert "activity working: Editing the page at 1.0 s" in reported
    assert "published at 12.0 s" in reported
    assert "response visible at 12.5 s" in reported
    assert "changed page — HTML first byte 100 ms" in reported
    assert benchmark == {
        "origin": "https://leaf.page",
        "release": release,
        "page": {
            "htmlFirstByteMs": 100.0,
            "htmlCompleteMs": 200.0,
            "firstContentfulPaintMs": 250.0,
            "javascriptFetchedMs": 275.0,
            "upgradedMs": 300.0,
            "stateAnsweredMs": 1300.0,
            "presentedMs": 1400.0,
            "requestsAtPresentation": 24,
            "bytesAtPresentation": 335 * 1024,
            "javascriptRequestsAtPresentation": 16,
            "javascriptBytesAtPresentation": 150 * 1024,
            "codeRequestsAtPresentation": 20,
            "codeBytesAtPresentation": 330 * 1024,
        },
        "comment": {
            "sessionReference": None,
            "eventIds": [],
            "asks": 1,
            "acknowledgedMs": [250.0],
            "activity": [
                {"atMs": 250.0, "kind": "queued", "detail": ""},
                {
                    "atMs": 1000.0,
                    "kind": "working",
                    "detail": "Editing the page",
                },
                {"atMs": 12500.0, "kind": "away", "detail": ""},
            ],
            "publishedMs": 12000.0,
            "responseVisibleMs": 12500.0,
            "repliedMs": 12500.0,
            "answeredMs": 12500.0,
        },
        "change": {
            "heading": heading,
            "revision": 2,
            "reply": "deployment verified",
        },
        "changedPage": {
            "htmlFirstByteMs": 100.0,
            "htmlCompleteMs": 200.0,
            "firstContentfulPaintMs": 250.0,
            "javascriptFetchedMs": 275.0,
            "upgradedMs": 300.0,
            "stateAnsweredMs": 28344.0,
            "presentedMs": 28444.0,
            "requestsAtPresentation": 24,
            "bytesAtPresentation": 335 * 1024,
            "javascriptRequestsAtPresentation": 16,
            "javascriptBytesAtPresentation": 150 * 1024,
            "codeRequestsAtPresentation": 20,
            "codeBytesAtPresentation": 330 * 1024,
            "followedRevisionMs": 2500.0,
        },
    }
    assert page.clicks == ["threads"]
    assert container.closed

    # A reload the container never answered is its own reading, taken before the wait.
    # Left unchecked it arrives as a presentation timeout, which is the message this
    # branch is here to stop conflating with a slow read.
    refused = _DeployedPage(heading, revision=2, presented_at=28444.0, reload_ok=False)
    with pytest.raises(RuntimeError, match="did not reload after its agent turn"):
        verify_site.verify_agent_turn(
            _DeployedSite(_DeployedContainer(release, refused)),
            release,
            origin="https://leaf.page",
        )
    assert refused.presentation_waits == [30_000]
    assert refused.revision_waits == []


def test_a_reload_that_presented_offline_reports_the_banner_it_presented_under(
    monkeypatch,
):
    """A stale revision has two causes, and the message has to separate them.

    `publish-site` failed on release `5b6be522…` with `stands on revision 1 rather than
    following the published 2` and nothing else, which reads the same whether the
    container answered the reload's first state read with revision 1 or never answered
    it at all. The gate cannot watch that read, but the page says which it was: an
    answer it never got leaves the offline banner standing over the authored document.
    """
    release = "5b6be522" + "0" * 56
    heading = f"Deployment {release[:8]} verified"
    published = {"revision": 2, "url": "revisions/2.html"}
    profile = verify_site.AgentProfile()
    profile.visible_reply_started_ms = 100.0
    monkeypatch.setattr(
        verify_site,
        "ask_until_answered",
        lambda *args, **kwargs: verify_site.AgentAsks(
            verify_site.TurnReading(
                {"active": {"revision": 2}, "activity": {"kind": "away"}},
                published,
                [{"kind": "reply", "text": "deployment verified"}],
                {"kind": "reply", "text": "deployment verified"},
            ),
            1,
            1,
            profile,
        ),
    )

    offline = _DeployedPage(
        heading,
        revision=1,
        presented_at=11_000.0,
        banner="Server offline — reconnecting",
    )
    with pytest.raises(RuntimeError) as reported:
        verify_site.verify_agent_turn(
            _DeployedSite(_DeployedContainer(release, offline)),
            release,
            origin="https://leaf.page",
        )
    assert "stands on revision 1" in str(reported.value)
    assert "Server offline — reconnecting" in str(reported.value)
    # Reported after the gate's own patience ran out, not at presentation: the banner is
    # quoted for a read that never answered rather than for one a second slower than the
    # runtime's wait.
    assert offline.revision_waits == [(2, verify_site.TURN_PRESENTATION)]

    # A page whose read answered is standing under an ordinary activity line rather
    # than an empty banner — a presented page always has one — so the two causes are
    # separated by what the message quotes rather than by whether it quotes anything.
    told = _DeployedPage(
        heading,
        revision=1,
        presented_at=1_400.0,
        banner="Claude is handling 1 update",
    )
    with pytest.raises(RuntimeError) as named:
        verify_site.verify_agent_turn(
            _DeployedSite(_DeployedContainer(release, told)),
            release,
            origin="https://leaf.page",
        )
    assert "stands on revision 1" in str(named.value)
    assert "Claude is handling 1 update" in str(named.value)
    assert "Server offline" not in str(named.value)
    assert told.revision_waits == [(2, verify_site.TURN_PRESENTATION)]


def test_the_worker_routes_every_file_a_page_vendors():
    """A page asks for its layer files at the page's own path, and the Worker answers
    only the paths its route list names. The Python adapter builds its list from
    schema.VENDORED_FILES; the Worker's copy in routing.ts cannot import that, so it is
    held to the same contract here. A file missing from it is a 404 on every published
    page that asks for it."""
    source = (ROOT / "worker" / "src" / "routing.ts").read_text()
    literal = re.search(r"const PAGE_RESOURCE =\s*/(.+)/;", source)
    assert literal, "routing.ts no longer states PAGE_RESOURCE as a regex literal"
    routed = re.compile(literal[1].replace("\\/", "/"))
    missing = [name for name in VENDORED_FILES if not routed.match(name)]
    assert not missing, f"routing.ts does not route {missing}"
