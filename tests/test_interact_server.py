"""HTTP event and service-address tests."""

import errno
import http.client
import http.cookiejar
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import INTERACT_SCRIPT
from interact_support import (
    PAGE,
    TOKEN,
    check,
    declare_data_input,
    fetch,
    neighbour_page,
    publish,
    record_claim,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import events as event_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import publishing as publishing_model
from leaf import registry as registry_model
from leaf import schema as schema_model
from leaf import service as service_model


def test_an_event_from_another_layer_is_not_interpreted_or_appended(server, page_dir):
    publish(page_dir)
    current = json.loads(fetch(f"{server}/api/state")[1])["layer"]
    before = event_model.read_events(page_dir)

    status, body = fetch(
        f"{server}/api/event",
        data=b"this is not even JSON in the current contract",
        layer="superseded-layer",
    )

    assert status == 200
    assert json.loads(body) == {"layer": current}
    assert event_model.read_events(page_dir) == before


def test_api_state_carries_the_validated_data_snapshot(server, page_dir):
    declare_data_input(
        page_dir,
        "builds",
        {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        contract="build-map",
    )
    data_model.cmd_data_set(page_dir, "builds", {"main": "green"})

    status, body = fetch(f"{server}/api/state")

    assert status == 200
    snapshot = json.loads(body)["data"]
    assert snapshot["revision"] == 1
    assert snapshot["sources"]["builds"]["contract"] == "build-map"
    assert snapshot["sources"]["builds"]["value"] == {"main": "green"}


def test_a_reader_who_closes_the_tab_is_not_a_server_error(page_dir):
    """Closing a tab mid-response is how nearly every page ends, and it used to put a
    BrokenPipeError traceback naming interact.py on the server's stderr —
    indistinguishable, in a log or in a suite's output, from the server having a
    fault.

    Both halves run the handler the way socketserver runs it, `RequestHandlerClass(
    request, client_address, server)` being the frame the traceback came out of. That
    is also what makes the failure deterministic: a socketpair whose far end is closed
    answers the first write with EPIPE, where a TCP client has to be raced into sending
    a reset between the server's read and its write. The answered half is here so the
    silent one cannot pass by refusing the request before it ever writes. The server
    object only supplies the argument; nothing is accepting on it.

    The poll, of everything a page asks for, because it is the request a closing tab
    is most likely to be holding — the runtime asks again forever — and because a
    socketpair's buffer is a few kilobytes: nothing drains this one until the handler
    has returned, so the answered half asks for a response that fits. The runtime is
    297kB and deadlocks the test rather than the server."""
    handler = http_model.handler_for(page_dir, TOKEN)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    request = f"GET /api/state?t={TOKEN} HTTP/1.0\r\nHost: x\r\n\r\n".encode()

    reader, edge = socket.socketpair()
    reader.sendall(request)
    handler(edge, ("127.0.0.1", 0), httpd)
    edge.close()  # so the drain below ends rather than waiting on a live connection
    answer = b""
    while chunk := reader.recv(65536):
        answer += chunk
    reader.close()
    assert answer.startswith(b"HTTP/1.0 200")
    head, body = answer.split(b"\r\n\r\n", 1)
    assert f"Content-Length: {len(body)}".encode() in head
    assert "versions" in json.loads(body)

    gone, edge = socket.socketpair()
    gone.sendall(request)
    gone.close()
    handler(edge, ("127.0.0.1", 0), httpd)  # the raise was here
    edge.close()
    httpd.server_close()


def test_server_round_trip(server, page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text()
        .replace("</section>", registry["lf-board"]["x-example"] + "\n</section>")
        .replace(
            '<script type="module" src="/leaf.js"></script>',
            '<style>.probe::before { content: "</head>"; }</style>\n'
            '<script type="module" src="/leaf.js"></script>',
        )
    )
    # Unnoted version: nothing published yet.
    status, _ = fetch(f"{server}/")
    assert status == 404
    status, _ = fetch(f"{server}/versions/v1.html")
    assert status == 404
    published = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )
    assert published.exit_code == 0, published.output
    # The handover address is the live page, not an alias for one immutable file.
    # It stays put while the browser adopts later versions, so the first response
    # must contain the version itself rather than redirecting the address away.
    peer = http.client.HTTPConnection(urllib.parse.urlsplit(server).netloc, timeout=10)
    peer.request("GET", f"/?t={TOKEN}")
    arrived = peer.getresponse()
    body = arrived.read()
    assert arrived.status == 200 and arrived.getheader("Location") is None
    peer.close()
    status = arrived.status
    assert status == 200 and b"lf-options" in body
    marker = b'<meta name="lf-version" data-lf-runtime content="1">'
    assert marker in body
    assert (
        body.index(b"</style>")
        < body.index(marker)
        < body.index(b'<script type="module" src="/leaf.js"></script>')
    )
    # Vendored files serve; the log and directory paths don't.
    for path in ["/leaf.js", "/theme.css", "/registry.json", "/widgets/lf-tabs.js"]:
        assert fetch(server + path)[0] == 200, path
    for path in [
        "/comments.jsonl",
        "/data.json",
        "/vendor/..",
        "/status.json",
        "/../secret",
    ]:
        assert fetch(server + path)[0] == 404, path
    outside = page_dir.parent / "outside.js"
    outside.write_text("not part of the page")
    (page_dir / "vendor" / "escape.js").symlink_to(outside)
    for path in ["/vendor/../../outside.js", "/vendor/escape.js"]:
        peer = http.client.HTTPConnection(
            urllib.parse.urlsplit(server).netloc, timeout=10
        )
        peer.request("GET", f"{path}?t={TOKEN}")
        refused = peer.getresponse()
        refused.read()
        assert refused.status == 404, path
        peer.close()
    # A browser-posted comment lands stamped author=user, with a server-minted id
    # (client ids are dropped — a reused one would re-root an existing thread).
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "id": "c9",
                "author": "claude",
                "agent": "Codex",
                "session": "s-forged",
                "ts": "1900-01-01T00:00:00Z",
                "seq": 99,
                "version": 1,
                "text": "hm",
            }
        ).encode(),
    )
    assert status == 200
    posted = event_model.read_events(page_dir)[-1]
    assert posted["author"] == "user" and posted["id"] != "c9"
    assert "agent" not in posted and "session" not in posted
    assert posted["ts"] != "1900-01-01T00:00:00Z"
    assert posted["seq"] != 99
    status, body = fetch(f"{server}/api/state")
    state = json.loads(body)
    assert state["versions"] == [1]
    assert state["cursor"] == 0  # no user event acknowledged yet
    assert state["events"][-1]["id"] == posted["id"]
    # A widget action rides the same channel; half-formed ones are refused at the edge.
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "version": 1,
                "widget": "feeder-board",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
            }
        ).encode(),
    )
    assert status == 200
    moved = event_model.read_events(page_dir)[-1]
    assert moved["author"] == "user" and moved["detail"]["to"] == "col-doing"
    # A design comment: about the layer, anchored on a runtime part the version never
    # holds, naming the control the press landed on. The door takes it as posted, and
    # the transcript says which kind of comment it was.
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "comment",
                "version": 1,
                "text": "the button reads dim",
                "about": "layer",
                "anchor": {"section": "lf-banner", "part": "Comments"},
            }
        ).encode(),
    )
    assert status == 200
    design = event_model.read_events(page_dir)[-1]
    assert design["about"] == "layer" and design["anchor"]["part"] == "Comments"
    transcript = CliRunner().invoke(cli_model.cli, ["transcript", str(page_dir)])
    assert "> § lf-banner · Comments  — about the layer" in transcript.output
    for bad in [
        {"kind": []},
        {"kind": "action", "action": "move"},  # no widget
        {"kind": "action", "widget": "", "action": "move", "detail": {}, "version": 1},
        {"kind": "action", "widget": "b", "action": "move", "version": 1},  # no detail
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": None,
            "version": 1,
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "version": "1",
        },
        {
            "kind": "action",
            "widget": "b",
            "action": "move",
            "detail": {},
            "version": True,
        },
        {"kind": "action", "widget": "b", "action": "move", "detail": {}, "version": 0},
        {"kind": "action", "widget": "b", "action": "move", "detail": {}, "version": 2},
        {"kind": "comment", "version": 1},  # no text: a blank thread nobody can read
        {"kind": "comment", "version": 1, "text": "x", "anchor": "intro"},
        {"kind": "comment", "version": 1, "text": "x", "anchor": {"quote": 7}},
        {"kind": "comment", "version": 1, "text": "x", "anchor": {}},
        {
            "kind": "comment",
            "version": 1,
            "text": "x",
            "anchor": {"datum": "row-1", "quote": "x"},
        },
        {
            "kind": "comment",
            "version": 1,
            "text": "x",
            "anchor": {"quote": "x", "extra": "y"},
        },
        {"kind": "comment", "version": 1, "text": "x", "suggestion": "yes"},
        {"kind": "comment", "version": 1, "text": "x", "attempt": "short"},
        # A design comment is about the layer, and that is the one word the field
        # takes: a browser inventing a second subject is refused at the door.
        {"kind": "comment", "version": 1, "text": "x", "about": "page"},
        {"kind": "comment", "version": 1, "text": "x", "about": True},
        {
            "kind": "reply",
            "parent": posted["id"],
            "version": 1,
            "text": "hi",
            "suggestion": True,
        },
        {"kind": "reply", "parent": "nope", "version": 1, "text": "hi"},
        {"kind": "resolve", "parent": "nope"},
        # A report is agent-authored: its one door is `leaf report`, so the
        # browser door refuses the kind outright rather than minting user
        # events that outrank nothing.
        {
            "kind": "report",
            "widget": "feeder-board",
            "action": "move",
            "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
            "version": 1,
        },
        # Message revisions are agent-authored too. The browser cannot turn the
        # reader into the recorded author of another speaker's words.
        {
            "kind": "edit",
            "message": posted["id"],
            "text": "rewritten in the browser",
        },
        ["not", "an", "object"],
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, bad
        answer = json.loads(body)
        assert answer["ok"] is False and answer["final"] is True, bad

    status, body = fetch(f"{server}/api/event", data=b"{")
    assert status == 400
    assert json.loads(body) == {
        "ok": False,
        "error": "invalid JSON",
        "final": True,
    }


def test_the_live_root_places_its_marker_by_the_parsers_own_line_break(
    server, page_dir
):
    """A Unicode separator before an indented script must not shift its marker."""
    # Keep the separator escaped so normalization cannot silently weaken the fixture.
    script = '<script type="module" src="/leaf.js"></script>'
    source = PAGE.replace(
        "<title>t</title>", "<title>Backfill plan\u2028Q3</title>"
    ).replace(script, "  " + script)
    (page_dir / "versions" / "v1.html").write_text(source, encoding="utf-8")
    assert check(page_dir).exit_code == 0
    publish(page_dir)

    body = fetch(f"{server}/")[1].decode()

    marker = '<meta name="lf-version" data-lf-runtime content="1">'
    assert body == source.replace(script, marker + script)
    # The old splice corrupted this tag while leaving the page renderable.
    assert '<link rel="stylesheet" href="/theme.css">' in body


def test_server_takes_an_approval_only_where_the_version_asked_for_one(
    server, page_dir
):
    """The declaration is the ask, and the door holds anything posting past the banner
    to it: a version that never asked has no approval to record."""
    publish(page_dir, version=1)

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "done", "version": 1, "text": "Looks good"}).encode(),
    )
    assert status == 400
    assert json.loads(body)["error"] == (
        'version 1 does not declare <meta name="lf-review" content="sign-off">, '
        "so it has no approval to record"
    )

    signoff = PAGE.replace(
        "<title>t</title>",
        '<title>t</title>\n<meta name="lf-review" content="sign-off">',
    )
    (page_dir / "versions" / "v2.html").write_text(signoff)
    publish(page_dir, version=2)
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "done", "version": 2, "text": "Looks good"}).encode(),
    )
    assert status == 200, body
    assert event_model.read_events(page_dir)[-1]["kind"] == "done"


def test_server_makes_attempt_identity_atomic_without_deduplicating_content(
    server, page_dir
):
    """One attempt returns one durable event; equal words under a new attempt are new."""
    publish(page_dir)
    first = {
        "kind": "comment",
        "version": 1,
        "text": "The same words can be intentional later.",
        "attempt": "attempt-00000001",
    }
    results = []

    def post_first():
        results.append(fetch(f"{server}/api/event", data=json.dumps(first).encode()))

    threads = [threading.Thread(target=post_first) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 8 and {status for status, _ in results} == {200}
    accepted_events = [
        next(
            event
            for event in json.loads(body)["state"]["events"]
            if event.get("attempt") == first["attempt"]
        )
        for _, body in results
    ]
    assert len({event["id"] for event in accepted_events}) == 1
    accepted = accepted_events[0]

    status, body = fetch(f"{server}/api/event", data=json.dumps(first).encode())
    assert status == 200
    assert (
        next(
            event
            for event in json.loads(body)["state"]["events"]
            if event.get("attempt") == first["attempt"]
        )["id"]
        == accepted["id"]
    )
    comments = [
        event
        for event in event_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["id"] for event in comments] == [accepted["id"]]

    changed = {**first, "text": "Different payload under the same attempt."}
    status, body = fetch(f"{server}/api/event", data=json.dumps(changed).encode())
    assert status == 409
    assert "already belongs to another event" in json.loads(body)["error"]

    later = {**first, "attempt": "attempt-00000002"}
    status, body = fetch(f"{server}/api/event", data=json.dumps(later).encode())
    assert status == 200
    comments = [
        event
        for event in event_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first["text"], first["text"]]
    assert [event["attempt"] for event in comments] == [
        "attempt-00000001",
        "attempt-00000002",
    ]

    # Mutable validation may have changed before a replacement tab retries. The
    # accepted record is authoritative even after its version is no longer live.
    (page_dir / "versions" / "v1.html").unlink()
    status, body = fetch(f"{server}/api/event", data=json.dumps(first).encode())
    assert status == 200
    assert (
        next(
            event
            for event in json.loads(body)["state"]["events"]
            if event.get("attempt") == first["attempt"]
        )["id"]
        == accepted["id"]
    )


def test_a_refused_attempt_is_re_read_against_the_page_that_refused_it(
    server, page_dir
):
    """A draft's attempt is stored with its words and reminted only on a keystroke,
    so the same attempt is what a reader's second press sends. A refusal the server
    remembered therefore outlived the state that produced it: the draft was refused
    for naming a version the page had not published yet, and after the publish the
    identical payload read back the stale verdict while the payload the reload had
    moved on read `already belongs to another event`, naming an event that never
    existed. Either way the reader's words were unsendable until they typed.

    The door refuses a version in that direction only. `published_versions` grows and
    never shrinks, so no version a tab was served is later refused for liveness, and
    this gate is the mirror of the one a reader meets — cheapest to walk the door
    through, standing in for the refusals whose ground really does move under them
    (`unknown parent`, `undo_error`, `action_contract_error` behind a re-vendor)."""
    publish(page_dir, 1)
    draft = {
        "kind": "comment",
        "version": 2,
        "anchor": {"quote": "hello"},
        "text": "The words a reader typed before the version moved.",
        "attempt": "attempt-draft-0001",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(draft).encode())
    assert status == 400
    assert json.loads(body)["error"] == "comment version must be one of [1]"

    (page_dir / "versions" / "v2.html").write_text(PAGE)
    publish(page_dir, 2)

    # The same press, once v2 is live: the refusal was about the page, and the page
    # has moved.
    status, body = fetch(f"{server}/api/event", data=json.dumps(draft).encode())
    assert status == 200, body
    accepted = next(
        event
        for event in json.loads(body)["state"]["events"]
        if event.get("attempt") == draft["attempt"]
    )
    assert accepted["text"] == draft["text"]

    # And the version the reload would have rewritten still meets the durable
    # conflict, which is the log's answer rather than a receipt's.
    moved = {**draft, "version": 1}
    status, body = fetch(f"{server}/api/event", data=json.dumps(moved).encode())
    assert status == 409
    assert "already belongs to another event" in json.loads(body)["error"]
    comments = [
        event
        for event in event_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["id"] for event in comments] == [accepted["id"]]


def test_an_accepted_event_response_is_state_through_that_event(server, page_dir):
    """The POST answer is the sender's authoritative read, not half of a
    transaction completed by a second request. A response cannot acknowledge an
    event while handing the page history from before it."""
    publish(page_dir)
    sent = {
        "kind": "comment",
        "version": 1,
        "text": "The response carries the state that includes this message.",
        "attempt": "attempt-state-0001",
    }

    status, body = fetch(f"{server}/api/event", data=json.dumps(sent).encode())

    assert status == 200, body
    answer = json.loads(body)
    assert answer["state"]["events"][-1]["attempt"] == sent["attempt"]


def test_an_accepted_retry_releases_the_page_before_scanning_neighbours(
    server, page_dir, monkeypatch
):
    """A retry needs the accepted log snapshot, not a lease over other pages.

    Neighbour discovery is independent I/O. The normal state path releases this
    page before doing it, and an accepted retry must take the same route so a slow
    neighbour cannot hold this page's writers behind it.
    """
    publish(page_dir)
    sent = {
        "kind": "comment",
        "version": 1,
        "text": "The retry has already landed.",
        "attempt": "attempt-neighbours-1",
    }
    assert fetch(f"{server}/api/event", data=json.dumps(sent).encode())[0] == 200

    own_state_read = threading.Event()
    scanned = threading.Event()
    original = http_model.Handler._page_state

    def own_state(handler, events):
        assert service_model.lock_is_held(page_dir / "comments.jsonl")
        own_state_read.set()
        return original(handler, events)

    def neighbours(directory):
        assert directory == page_dir
        assert not service_model.lock_is_held(page_dir / "comments.jsonl")
        scanned.set()
        return []

    monkeypatch.setattr(http_model.Handler, "_page_state", own_state)
    monkeypatch.setattr(http_model, "other_leaves", neighbours)
    status, body = fetch(f"{server}/api/event", data=json.dumps(sent).encode())

    assert status == 200, body
    assert own_state_read.is_set()
    assert scanned.is_set()


def test_concurrent_retries_share_one_attempt_execution_then_release_it(
    server, page_dir, monkeypatch
):
    """A retry arriving while the original request is validating waits for that
    outcome. It cannot independently refuse while the original remains free to
    append later, which would make the refusal a lie to the browser. Once complete,
    the receipt leaves and a later retry evaluates afresh."""
    publish(page_dir)
    entered = threading.Event()
    release = threading.Event()
    waiter_entered = threading.Event()
    calls = 0
    original_attempt_init = event_model.AttemptExecution.__init__

    def observe_attempt(execution, payload):
        original_attempt_init(execution, payload)
        original_wait = execution.done.wait

        def observed_wait(*args, **kwargs):
            waiter_entered.set()
            return original_wait(*args, **kwargs)

        execution.done.wait = observed_wait

    def refuse_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(5), "the test never released the first attempt"
        return "the action was refused"

    monkeypatch.setattr(http_model, "action_contract_error", refuse_once)
    monkeypatch.setattr(event_model.AttemptExecution, "__init__", observe_attempt)
    sent = {
        "kind": "action",
        "version": 1,
        "widget": "feeder-board",
        "action": "move",
        "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
        "attempt": "attempt-flight-001",
    }
    results = []
    layer = registry_model.layer_generation(page_dir)

    def post():
        # A real retry already carries the layer of the attempt it is retrying. The
        # generic helper otherwise polls first to discover one; state reads now take
        # the page lease for an atomic log/status snapshot, which would serialize this
        # test before either request reached the attempt coordinator.
        results.append(
            fetch(
                f"{server}/api/event",
                data=json.dumps(sent).encode(),
                layer=layer,
            )
        )

    first = threading.Thread(target=post)
    second = threading.Thread(target=post)
    first.start()
    assert entered.wait(5), "the first attempt never entered validation"
    second.start()
    try:
        assert waiter_entered.wait(5), "the retry never joined the active attempt"
        assert not results, "the retry answered while the original attempt was active"
    finally:
        release.set()
        first.join()
        second.join()

    assert calls == 1
    assert len(results) == 2
    assert {status for status, _ in results} == {400}
    answers = [json.loads(body) for _, body in results]
    assert answers == [answers[0], answers[0]]
    assert answers[0] == {
        "ok": False,
        "attempt": sent["attempt"],
        "error": "the action was refused",
        "final": True,
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(sent).encode())
    assert status == 400 and json.loads(body) == answers[0]
    assert calls == 2, "a completed refusal left a receipt behind"
    assert [
        event
        for event in event_model.read_events(page_dir)
        if event["kind"] == "action"
    ] == []


def test_flocked_refuses_a_platform_without_cross_process_locking(
    page_dir, monkeypatch
):
    """A no-op lock cannot honestly promise one append for one attempt."""
    monkeypatch.setattr(event_model, "fcntl", None)
    with (
        pytest.raises(RuntimeError, match="cross-process file locking"),
        event_model.flocked(page_dir / ".lock"),
    ):
        pass


def test_server_startup_refuses_a_platform_without_cross_process_locking(
    page_dir, monkeypatch
):
    """Standing startup must fail before it opens a socket or records a URL."""
    monkeypatch.setattr(event_model, "fcntl", None)
    monkeypatch.setattr(service_model, "fcntl", None)
    with pytest.raises(RuntimeError, match="cross-process file locking"):
        hosting_model.cmd_serve(page_dir, standing=True)
    with pytest.raises(RuntimeError, match="cross-process file locking"):
        hosting_model.start_server(page_dir, standing=True)
    with pytest.raises(RuntimeError, match="cross-process file locking"):
        service_model.lock_is_held(page_dir / "server.lock")
    assert not (page_dir / "server.lock").exists()
    assert not (page_dir / "service.json").exists()


def test_server_validates_an_action_against_its_version_and_widget(server, page_dir):
    registry = json.loads((page_dir / "registry.json").read_text())
    board = registry["lf-board"]["x-example"]
    v1 = page_dir / "versions" / "v1.html"
    v1.write_text(v1.read_text().replace("</section>", board + "\n</section>"))
    publish(page_dir, version=1)
    (page_dir / "versions" / "v2.html").write_text(PAGE)
    publish(page_dir, version=2)

    invalid = [
        (
            {
                "kind": "action",
                "version": 2,
                "widget": "feeder-board",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
            },
            "unknown action widget",
        ),
        (
            {
                "kind": "action",
                "version": 1,
                "widget": "flow",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
            },
            "<lf-diagram> does not declare action verb",
        ),
        (
            {
                "kind": "action",
                "version": 1,
                "widget": "feeder-board",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "index": -1},
            },
            "detail is invalid",
        ),
    ]
    before = len(event_model.read_events(page_dir))
    for event, message in invalid:
        status, body = fetch(f"{server}/api/event", data=json.dumps(event).encode())
        assert status == 400, event
        assert message in json.loads(body)["error"]
    assert len(event_model.read_events(page_dir)) == before

    # The page may have advanced since the gesture, so resolve the sender from
    # the action's own published version rather than the newest document.
    valid = {
        "kind": "action",
        "version": 1,
        "widget": "feeder-board",
        "action": "move",
        "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
    }
    assert fetch(f"{server}/api/event", data=json.dumps(valid).encode())[0] == 200


@pytest.mark.parametrize(
    ("corrupt", "message"),
    [
        (lambda registry: "{broken", "invalid JSON"),
        # The reachable one. A page's registry is vendored once and the layer around it
        # goes on moving, so a stamp that no longer names what this layer writes is
        # ordinary state — and the reader meets it by clicking, not by running anything.
        (
            lambda registry: json.dumps({**registry, "$events": {"kinds": {}}}),
            "$events.kinds omits or changes contracts the current layer writes",
        ),
    ],
)
def test_server_answers_a_broken_registry_instead_of_dropping_the_request(
    server, page_dir, corrupt, message
):
    """A registry that stopped being a vocabulary refuses like everything else on this
    path. It exited the process instead, which is the one refusal a reader cannot read:
    the handler died mid-request and the click came back a dead socket, saying nothing
    about the page, the action, or what to do next."""
    publish(page_dir)
    registry = json.loads((page_dir / "registry.json").read_text())
    (page_dir / "registry.json").write_text(corrupt(registry))

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "version": 1,
                "widget": "feeder-board",
                "action": "move",
                "detail": {"card": "card-baffle", "to": "col-doing", "index": 0},
            }
        ).encode(),
    )
    assert status == 400
    assert message in json.loads(body)["error"]
    assert not [e for e in event_model.read_events(page_dir) if e["kind"] == "action"]
    # The refusal cost the request and nothing else: the server is still serving, so a
    # page whose stamp fell behind still reads even where it can no longer be acted on.
    assert fetch(f"{server}/api/state")[0] == 200


def test_server_resolves_actions_from_claude_thread_widgets(server, page_dir):
    publish(page_dir)
    event_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "version": 1,
            "text": "pick one",
        },
    )
    reply = CliRunner().invoke(
        cli_model.cli,
        [
            "reply",
            str(page_dir),
            "--to",
            "c1",
            "--text",
            "Pick one:",
            "--markup",
            (
                '<lf-options id="thread-pick" choose>'
                '<lf-option id="thread-a"><strong>A</strong></lf-option>'
                "</lf-options>"
                '<lf-specimen id="sample">'
                '<lf-options id="exhibited-pick" choose>'
                '<lf-option id="exhibited-a"><strong>A</strong></lf-option>'
                "</lf-options></lf-specimen>"
            ),
        ],
    )
    assert reply.exit_code == 0, reply.output
    event_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": "c1",
            "version": 1,
            "text": '<lf-options id="text-pick" choose></lf-options>',
        },
    )

    choose = {
        "kind": "action",
        "version": 1,
        "action": "choose",
        "detail": {"options": ["thread-a"]},
    }
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps({**choose, "widget": "thread-pick"}).encode(),
    )
    assert status == 200
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                **choose,
                "widget": "exhibited-pick",
                "detail": {"options": ["exhibited-a"]},
            }
        ).encode(),
    )
    assert status == 400
    assert "stands inside an exhibit" in json.loads(body)["error"]
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({**choose, "widget": "text-pick"}).encode(),
    )
    assert status == 400
    assert "unknown action widget" in json.loads(body)["error"]


@pytest.mark.parametrize("in_thread", [False, True])
def test_server_refuses_a_stale_action_after_a_selection_facet_is_answered(
    server, page_dir, in_thread
):
    """A child attribute record closes the sender's standing request."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["defer"] = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "deferral",
        "unit": "widget",
        "requires": {"target": "self", "awaiting": True},
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "</section>",
            '<lf-options id="eligibility-options" choose>'
            '<lf-option id="eligibility-a">A</lf-option>'
            '<lf-option id="eligibility-b">B</lf-option>'
            "</lf-options></section>",
        )
    )

    publish(page_dir)
    widget = "eligibility-options"
    option = "eligibility-a"
    if in_thread:
        event_model.append_event(
            page_dir,
            {
                "kind": "comment",
                "id": "c-eligibility",
                "author": "user",
                "version": 1,
                "text": "change this task",
            },
        )
        reply = CliRunner().invoke(
            cli_model.cli,
            [
                "reply",
                str(page_dir),
                "--to",
                "c-eligibility",
                "--text",
                "Here it is:",
                "--markup",
                (
                    '<lf-options id="thread-options" choose>'
                    '<lf-option id="thread-a">A</lf-option>'
                    '<lf-option id="thread-b">B</lf-option>'
                    "</lf-options>"
                ),
            ],
        )
        assert reply.exit_code == 0, reply.output
        widget = "thread-options"
        option = "thread-a"

    choose = {
        "kind": "action",
        "version": 1,
        "widget": widget,
        "action": "choose",
        "detail": {"options": [option]},
    }
    nonanswer = {**choose, "action": "defer", "detail": {}}
    assert fetch(f"{server}/api/event", data=json.dumps(nonanswer).encode())[0] == 200
    assert fetch(f"{server}/api/event", data=json.dumps(nonanswer).encode())[0] == 200
    assert fetch(f"{server}/api/event", data=json.dumps(choose).encode())[0] == 200
    before = len(event_model.read_events(page_dir))

    status_code, body = fetch(
        f"{server}/api/event", data=json.dumps(nonanswer).encode()
    )

    assert status_code == 400
    assert "action 'defer' is unavailable" in json.loads(body)["error"]
    assert "no longer awaiting the reader" in json.loads(body)["error"]
    assert len(event_model.read_events(page_dir)) == before


def test_a_seat_conversation_does_not_lock_out_the_answer_it_is_about(server, page_dir):
    """A remark in the widget's own seat leaves the pick that would answer it open.

    Two readings of one reducer, and this door takes the one that asks whether the
    request is *answered*. A conversation standing in the seat takes the request off
    the reader's list — the banner stops counting it, and
    `test_page_state_takes_a_seated_question_off_the_readers_list` holds that — but
    it records nothing: the group still holds no pick and its controls still offer
    one. A gate reading the reader's list instead would refuse the pick for the
    reader's having written in the box the page put under the question, which is
    refusing them the answer they were asked for. It would also refuse it silently:
    `lf-options` paints a pick before this door sees it, so the option would flip,
    nothing would be logged, no toast would fire, and the next poll would put it
    back."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-options"]["x-state"]["choose"]["requires"] = {
        "target": "self",
        "awaiting": True,
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "</section>",
            '<lf-options id="seated-options" choose>'
            '<lf-option id="seated-a">A</lf-option>'
            '<lf-option id="seated-b">B</lf-option>'
            "</lf-options></section>",
        )
    )
    publish(page_dir)
    event_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "anchor": {"section": "seated-options"},
            "text": "neither — cap the retries instead",
        },
    )
    choose = {
        "kind": "action",
        "version": 1,
        "widget": "seated-options",
        "action": "choose",
        "detail": {"options": ["seated-a"]},
    }
    status_code, body = fetch(f"{server}/api/event", data=json.dumps(choose).encode())
    assert status_code == 200, body
    # And the answer does close it, so the gate is reading the request rather than
    # ignoring the declaration outright.
    again = {**choose, "detail": {"options": ["seated-b"]}}
    status_code, body = fetch(f"{server}/api/event", data=json.dumps(again).encode())
    assert status_code == 400
    assert "no longer awaiting the reader" in json.loads(body)["error"]


def test_server_checks_recursive_parent_prerequisite_under_append_lock(
    server, page_dir
):
    """A custom scalar reads the declared roll-up, not ask containment."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-awaits"]["rollup"] = True
    scalar = {"type": "string", "pattern": "^[0-9]+$"}
    detail = {
        "type": "object",
        "properties": {"slots": scalar},
        "required": ["slots"],
        "additionalProperties": False,
    }
    record = {"kind": "value", "attr": "slots", "value": "slots"}
    registry["lf-quota"] = {
        "description": "A project-defined absolute scalar control.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "slots": scalar,
            "restated": {"type": "boolean"},
        },
        "required": ["id", "slots"],
        "additionalProperties": False,
        "x-parent": ["lf-task"],
        "x-content": "none",
        "x-upgrade": True,
        "x-state": {
            "move": {
                "detail": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "index": {"type": "integer", "minimum": 0},
                    },
                    "required": ["to", "index"],
                    "additionalProperties": False,
                },
                "facet": "placement",
                "unit": "widget",
                "record": {
                    "kind": "position",
                    "within": "lf-task",
                    "value": "to",
                    "order": "index",
                },
            },
            "increase": {
                "detail": detail,
                "facet": "capacity",
                "unit": "widget",
                "record": record,
                "requires": {
                    "target": "parent",
                    "awaiting": False,
                },
            },
            "decrease": {
                "detail": detail,
                "facet": "capacity",
                "unit": "widget",
                "record": record,
            },
        },
    }
    (page_dir / "registry.json").write_text(json.dumps(registry))
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "</section>",
            '<lf-tasks id="quota-tasks"><lf-task id="quota-task" status="active">'
            "<strong>Task</strong>"
            '<lf-quota id="quota" slots="1"></lf-quota>'
            '<lf-options id="quota-intervention" choose label="Proceed?">'
            '<lf-option id="quota-ready" chosen>Ready</lf-option></lf-options>'
            '<lf-task id="quota-child" status="active"><strong>Child</strong></lf-task>'
            "</lf-task>"
            '<lf-task id="quota-destination" status="active">'
            "<strong>Destination</strong></lf-task>"
            "</lf-tasks></section>",
        )
    )
    publish(page_dir)

    event = {
        "kind": "action",
        "version": 1,
        "widget": "quota",
        "action": "increase",
        "detail": {"slots": "2"},
    }
    event_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "version": 1,
            "widget": "quota-task",
            "action": "status",
            "detail": {"status": "blocked"},
        },
    )
    # The answered direct intervention takes precedence over the nested task, so the
    # stopped parent is available while that answer stands.
    assert fetch(f"{server}/api/event", data=json.dumps(event).encode())[0] == 200

    event_model.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "agent",
            "version": 1,
            "widget": "quota-child",
            "action": "status",
            "detail": {"status": "blocked"},
        },
    )
    increase = {**event, "detail": {"slots": "3"}}
    assert fetch(f"{server}/api/event", data=json.dumps(increase).encode())[0] == 200

    # Clearing the direct answer reopens that intervention. It now overrides the
    # blocked child in the other direction and closes capacity under the same lock.
    choose = {
        "kind": "action",
        "version": 1,
        "widget": "quota-intervention",
        "action": "choose",
        "detail": {"options": []},
    }
    assert fetch(f"{server}/api/event", data=json.dumps(choose).encode())[0] == 200
    increase = {**event, "detail": {"slots": "4"}}
    status, body = fetch(f"{server}/api/event", data=json.dumps(increase).encode())
    assert status == 400
    assert "still awaiting the reader" in json.loads(body)["error"]

    decrease = {**event, "action": "decrease", "detail": {"slots": "0"}}
    assert fetch(f"{server}/api/event", data=json.dumps(decrease).encode())[0] == 200

    # Placement is projected too. After the absolute move, admission reads the
    # active destination rather than the blocked parent in authored markup.
    move = {
        "kind": "action",
        "version": 1,
        "widget": "quota",
        "action": "move",
        "detail": {"to": "quota-destination", "index": 0},
    }
    assert fetch(f"{server}/api/event", data=json.dumps(move).encode())[0] == 200
    increase_after_move = {**event, "detail": {"slots": "1"}}
    assert (
        fetch(f"{server}/api/event", data=json.dumps(increase_after_move).encode())[0]
        == 200
    )
    assert [
        logged["action"]
        for logged in event_model.read_events(page_dir)
        if logged["kind"] == "action"
    ] == ["increase", "increase", "choose", "decrease", "move", "increase"]


def test_server_rejects_an_action_from_a_widget_removed_by_revendoring(
    server, page_dir
):
    """An open old tab may outlive the custom layer that upgraded its widget."""
    shipped = json.loads((page_dir / "registry.json").read_text())
    overlay = page_dir.parent / ".leaf"
    (overlay / "widgets").mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"lf-local-draft": shipped["lf-draft"]})
    )
    (overlay / "widgets" / "lf-local-draft.js").write_text(
        "customElements.define('lf-local-draft', class extends HTMLElement {});"
    )
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)]).exit_code
        == 0
    )
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-local-draft id="local-draft"><pre>Words.</pre>'
            "</lf-local-draft>",
        )
    )
    noted = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            "1",
            "--text",
            "custom widget",
        ],
    )
    assert noted.exit_code == 0, noted.output

    # The explicit re-vendor is allowed because no recorded action rests on this
    # tag yet. A browser that loaded it before the re-vendor can still send one.
    (overlay / "registry.json").unlink()
    (overlay / "widgets" / "lf-local-draft.js").unlink()
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)]).exit_code
        == 0
    )

    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "version": 1,
                "widget": "local-draft",
                "action": "edit",
                "detail": {"text": "New words."},
            }
        ).encode(),
    )

    assert status == 400
    assert "no longer declares" in json.loads(body)["error"]


def test_concurrent_posts_never_tear_the_log(server, page_dir):
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )

    def post(i):
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "version": 1, "text": f"c{i} " + "x" * 500}
            ).encode(),
        )

    threads = [threading.Thread(target=post, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events = [e for e in event_model.read_events(page_dir) if e["kind"] == "comment"]
    assert {e["text"].split()[0] for e in events} == {f"c{i}" for i in range(20)}
    assert len({e["id"] for e in events}) == 20  # server-minted, all distinct


def test_a_stated_host_restates_the_address_and_nothing_else(page_dir):
    """--host is the recovery for an unroutable name, and the record's other
    facts restate nothing: dropping them re-derived the exact port an open tab
    polls and demoted the standing lifetime to the recovering session's."""
    files_model.write_json(
        page_dir / "service.json",
        {
            "host": "10.0.0.5",
            "bind": "10.0.0.5",
            "port": 41234,
            "enabled": False,
            "lifetime": "standing",
        },
    )
    access = service_model.page_access(page_dir, "box.tailnet.example")
    assert access["host"] == "box.tailnet.example" and access["bind"] == "::"
    assert access["port"] == 41234
    assert access["lifetime"] == "standing"


def test_the_page_reports_its_own_errors_to_the_watcher(server, page_dir):
    """kind "error" through the browser door: the page's runtime reporting a
    live-session fault. Stamped author "page" (the machine speaking, not the
    reader), heard by the watcher beside comments and reports, acknowledged
    through the same cursor — and never counted in the reader's pending, since
    a broken page is the agent's debt."""
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {"kind": "error", "version": 1, "text": "widget lf-x failed to load"}
        ).encode(),
    )
    assert status == 200
    events = event_model.read_events(page_dir)
    error = events[-1]
    assert error["kind"] == "error" and error["author"] == "page"
    assert error in service_model.unacknowledged(events, 0)
    assert http_model.presence(page_dir, events)["pending"] == 0
    result = CliRunner().invoke(
        cli_model.cli, ["ack", str(page_dir), str(error["seq"])]
    )
    assert result.exit_code == 0, result.output


def test_a_poll_records_that_the_page_is_open(server, page_dir):
    """A page nobody ever opened and one the user studied and left used to be
    indistinguishable from the agent's side; the poll is the proof a browser
    holds the page, so the server writes it down."""
    events = event_model.read_events(page_dir)
    assert http_model.presence(page_dir, events)["viewed"] is None
    fetch(f"{server}/api/state")
    assert http_model.presence(page_dir, events)["viewed"] is not None


def test_a_comment_carrying_line_separators_survives_the_log(server, page_dir):
    """U+2028, U+2029 and U+0085 are legal raw in JSON strings and line breaks to
    splitlines(): unescaped, one pasted separator split an event across "lines",
    every later read of the log raised, and the page read as offline forever."""
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )
    text = "one\u2028two\u2029three\u0085four"
    status, _ = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "comment", "version": 1, "text": text}).encode(),
    )
    assert status == 200
    events = [e for e in event_model.read_events(page_dir) if e["kind"] == "comment"]
    assert [e["text"] for e in events] == [text]
    # One physical line per event under any line-splitting reader, so what
    # `wait` and `events` print stays one event per line for every consumer.
    raw = (page_dir / "comments.jsonl").read_text()
    assert raw.splitlines() == raw.rstrip("\n").split("\n")


def test_a_torn_tail_is_isolated_and_the_log_keeps_reading(page_dir):
    """A crash tears an append mid-line. The next append restores the line
    discipline rather than gluing onto the fragment, the fragment's event is
    gone (its sender saw the failure), and the seqs around it hold."""
    event_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "version": 1, "text": "before"}
    )
    with open(page_dir / "comments.jsonl", "a", encoding="utf-8") as f:
        f.write('{"kind": "comm')  # the tear: no trailing newline
    event_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "version": 1, "text": "after"}
    )
    events = event_model.read_events(page_dir)
    assert [e["text"] for e in events] == ["before", "after"]
    assert [e["seq"] for e in events] == [1, 3]  # the torn line keeps its number
    # A tear lands mid-character as easily as mid-line — ensure_ascii=False
    # writes multi-byte UTF-8 — and a strict whole-file decode would raise
    # before any line-level tolerance could reach it.
    with open(page_dir / "comments.jsonl", "ab") as f:
        f.write('{"kind": "comment", "text": "café'.encode()[:-1])
    event_model.append_event(
        page_dir, {"kind": "comment", "author": "user", "version": 1, "text": "again"}
    )
    assert [e["text"] for e in event_model.read_events(page_dir)] == [
        "before",
        "after",
        "again",
    ]


def test_a_reader_without_the_key_reads_and_writes_nothing(server, page_dir):
    """The page is served wherever the SSH session reached this machine, so the
    port is open to whatever else is on that network. Reading is half of it: the
    log outranks the document and takes appends from anyone who can POST."""
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )

    assert fetch(f"{server}/versions/v1.html", token=None)[0] == 403
    assert fetch(f"{server}/api/state", token=None)[0] == 403
    assert fetch(f"{server}/", token=None)[0] == 403
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "comment", "version": 1, "text": "not mine"}).encode(),
        token=None,
    )
    assert status == 403
    assert json.loads(body) == {
        "ok": False,
        "error": schema_model.NO_KEY,
        "final": True,
    }

    # The key gate precedes the body read. A peer that cannot open the page must not
    # get to choose how much a handler allocates or park it waiting for bytes that never
    # arrive merely by declaring a large body before authentication.
    http11 = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        http_model.handler_for(page_dir, TOKEN, protocol_version="HTTP/1.1"),
    )
    thread = threading.Thread(target=http11.serve_forever, daemon=True)
    thread.start()
    peer = http.client.HTTPConnection(
        f"127.0.0.1:{http11.server_address[1]}", timeout=2
    )
    try:
        peer.putrequest("POST", "/api/event")
        peer.putheader("Content-Length", str(1 << 30))
        peer.putheader("Content-Type", "application/json")
        peer.endheaders()
        refused = peer.getresponse()
        refusal = json.loads(refused.read())
    finally:
        peer.close()
        http11.shutdown()
    assert (refused.status, refusal) == (
        403,
        {"ok": False, "error": schema_model.NO_KEY, "final": True},
    )
    assert refused.version == 11
    assert refused.getheader("Connection") == "close"
    assert refused.will_close
    assert fetch(f"{server}/versions/v1.html", token="not-the-key")[0] == 403

    assert [
        e for e in event_model.read_events(page_dir) if e["kind"] == "comment"
    ] == []


def test_every_event_door_refusal_is_final_and_read_refusals_name_the_attempt(
    server, page_dir
):
    """`final` is the only word that ends a retry, so a refusal that leaves it out is
    not a refusal the browser can act on: the outbox reads it as an incomplete answer
    and re-posts the same attempt every poll for the life of the tab, with one toast as
    the reader's whole explanation. Every one of these is deterministic, so the loop
    never ends.

    The state-dependent refusals were written through `event_rejection` from the start
    and the gates in front of them were not, which is the split this asserts away: the
    key, the read-only preview server, and each shape gate answer in the door's own
    shape rather than in the shape of whichever branch decided them. The key gate runs
    before the body read, so its refusal is safely attempt-less; every authenticated
    refusal can and must name the attempt it read. A page's runtime is vendored at
    `page init` and the layer around it moves, so the shape gates are reachable by an
    older page's honest event, not only by a hand-written POST."""
    publish(page_dir)
    attempt = "attempt-for-the-door-x"
    comment = {"kind": "comment", "version": 1, "text": "hello", "attempt": attempt}
    preview = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0), http_model.handler_for(page_dir, TOKEN, preview_upto=1)
    )
    thread = threading.Thread(target=preview.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = fetch(
            f"{server}/api/event", data=json.dumps(comment).encode(), token=None
        )
        answer = json.loads(body)
        assert (status, answer.get("ok"), answer.get("final")) == (
            403,
            False,
            True,
        )
        assert "attempt" not in answer
        assert answer.get("error") == schema_model.NO_KEY

        refusals = [
            (
                "the preview server",
                403,
                comment,
                TOKEN,
                f"http://127.0.0.1:{preview.server_address[1]}",
            ),
            ("an unknown kind", 400, {**comment, "kind": "nope"}, TOKEN, server),
            ("an unexpected field", 400, {**comment, "widget": "x"}, TOKEN, server),
            ("a field of the wrong type", 400, {**comment, "text": 7}, TOKEN, server),
            (
                "a bad anchor",
                400,
                {**comment, "anchor": {"nothing": "here"}},
                TOKEN,
                server,
            ),
            (
                "a malformed attempt",
                400,
                {**comment, "attempt": "too-short"},
                TOKEN,
                server,
            ),
            # The one refusal that was always in this shape, here so the loop below is
            # read against a case that could never have failed it.
            ("an unlive version", 400, {**comment, "version": 9}, TOKEN, server),
        ]
        for name, wanted, event, token, url in refusals:
            status, body = fetch(
                f"{url}/api/event", data=json.dumps(event).encode(), token=token
            )
            answer = json.loads(body)
            assert (status, answer.get("ok"), answer.get("final")) == (
                wanted,
                False,
                True,
            ), (name, status, answer)
            assert answer.get("attempt") == event["attempt"], (name, answer)
            assert answer.get("error"), (name, answer)
    finally:
        preview.shutdown()

    # The refusals decided before the body is a dict at all, which the parsed rows above
    # cannot reach. These name no attempt because the door has nothing to read one out
    # of, but each is safely final: parsing failed before an append could begin, so the
    # browser may put the gesture back. What it must still receive is an answer: a body
    # defeats the parse in more ways than the parse was written for — bytes that are not
    # UTF-8 raise UnicodeDecodeError, since `json.loads` decodes before it parses, and
    # nesting past the parser's own stack raises RecursionError, which is not even a
    # ValueError. Uncaught, each left the request unanswered — which the outbox reads as
    # a lost connection and re-posts every poll for the life of the tab.
    #
    # Each row names the refusal it must earn rather than asking for any refusal at all.
    # The depth the parser gives up at is the interpreter's to choose, so a platform
    # that got through this nesting would fall to the next gate, be refused as not an
    # object, and pass a row that had proved nothing about the stack it was written for.
    unreadable = [
        (
            "a body that is not UTF-8",
            b'{"kind": "comment", "text": "\xff"}',
            "invalid JSON",
        ),
        ("a body that is not JSON", b"{not json", "invalid JSON"),
        ("a body that is not an object", b"[1, 2]", "event must be a JSON object"),
        (
            "a body nested past the parser's stack",
            b"[" * 100000 + b"]" * 100000,
            "invalid JSON",
        ),
    ]
    for name, body, refusal in unreadable:
        status, answered = fetch(f"{server}/api/event", data=body)
        answer = json.loads(answered)
        assert (status, answer.get("ok"), answer.get("final"), answer.get("error")) == (
            400,
            False,
            True,
            refusal,
        ), (name, status, answer)

    # The fifth is the header rather than the body, and no opener will send it: a
    # Content-Length the machine will not hand over. `BufferedReader.read(n)` allocates
    # n bytes before it reads any, so this raises MemoryError out of the read itself —
    # neither a ValueError nor anything the parse could have raised, and the third
    # exception type found this way. A length that cannot be allocated is a length that
    # cannot be used, so it earns the same word an unparsable length does. The length is
    # past what any machine can address rather than merely large: a host that overcommits
    # can hand over ~91 TiB inside the 128 TiB four-level paging reaches, and the read
    # would then block until this connection's own timeout, failing the row on the wait
    # rather than on the refusal it is about.
    # It arrives under this page's layer, as every runtime's POST does: a request from
    # another generation is answered with the one to reload into, ahead of any verdict
    # on a body written in a vocabulary this server no longer speaks.
    _, served = fetch(f"{server}/api/state")
    door = http.client.HTTPConnection(urllib.parse.urlsplit(server).netloc, timeout=10)
    try:
        door.putrequest("POST", f"/api/event?t={TOKEN}")
        door.putheader("Leaf-Layer", json.loads(served)["layer"])
        door.putheader("Content-Length", "999999999999999999")
        door.putheader("Content-Type", "application/json")
        door.endheaders()
        door.send(b"")
        answered = door.getresponse()
        answer = json.loads(answered.read())
    finally:
        door.close()
    assert (
        answered.status,
        answer.get("ok"),
        answer.get("final"),
        answer.get("error"),
    ) == (400, False, True, "invalid Content-Length"), answer

    assert [
        e for e in event_model.read_events(page_dir) if e["kind"] == "comment"
    ] == []


def test_the_key_arrives_in_the_query_and_stays_in_the_cookie(server, page_dir):
    """What makes the key invisible: it is in the link once, and the cookie carries
    it from there. The runtime's own fetches are relative and hold no query, and a
    user who reloads the bare address is the same user — so nothing has to
    thread it through the page, and `leaf.js` never learns there is one."""
    CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(page_dir), "--version", "1", "--text", "cut"],
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    with opener.open(f"{server}/versions/v1.html?t={TOKEN}") as arrival:
        assert arrival.status == 200
    assert [c.value for c in jar] == [TOKEN]

    # No query this time: the runtime's own fetches never carry one.
    with opener.open(f"{server}/api/state") as polled:
        assert polled.status == 200


def test_a_page_is_reached_where_the_ssh_session_reached_this_machine(
    page_dir, monkeypatch
):
    """SSH_CONNECTION is "client_ip client_port server_ip server_port" — the third
    field is the address that carried the session, so it is a route the user has
    already used rather than a hostname guessed from this end. The server binds that
    address alone: the open port faces only the network the session crossed."""
    monkeypatch.setenv("SSH_CONNECTION", "10.1.1.9 51234 10.20.30.40 22")
    access = service_model.page_access(page_dir)
    assert (access["host"], access["bind"]) == ("10.20.30.40", "10.20.30.40")


def test_a_local_session_is_served_on_loopback(page_dir, monkeypatch):
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    access = service_model.page_access(page_dir)
    assert (access["host"], access["bind"]) == ("127.0.0.1", "127.0.0.1")


def test_a_stated_host_binds_every_interface_without_recording_before_serve(
    page_dir, monkeypatch
):
    """The name a user routes to need not resolve to an address this machine
    could bind — a jump host or NAT is the case `--host` exists for — nor say
    which family they reach it by, so a stated name binds the wildcard of both
    families and goes in the URL as given. Derivation stays in memory until the
    server-lease winner records it."""
    monkeypatch.setenv("SSH_CONNECTION", "10.1.1.9 51234 10.20.30.40 22")
    stated = service_model.page_access(page_dir, host="devbox.corp.example")
    assert (stated["host"], stated["bind"]) == ("devbox.corp.example", "::")
    service = {
        **stated,
        "port": 41234,
        "enabled": False,
        "lifetime": "standing",
    }
    files_model.write_json(page_dir / "service.json", service)
    assert service_model.page_access(page_dir) == service


def test_a_stated_host_is_a_hostname_or_ip_and_nothing_else(page_dir):
    """A scheme, a port, or a path pasted into --host would mint a URL no browser
    resolves, recorded permanently and handed to the one reader who can't report
    it — so the record's one door refuses what was never a hostname. An IPv6
    literal is a name a user can route to, and it must not be mistaken for a
    host:port."""
    for junk in ("devbox:8443", "http://devbox", "devbox/page", "devbox one"):
        with pytest.raises(SystemExit):
            service_model.page_access(page_dir, host=junk)
    assert not (page_dir / "service.json").exists()

    assert service_model.page_access(page_dir, host="fd7a:115c:a1e0::1")["bind"] == "::"


def test_the_stated_host_wildcard_serves_both_families(wildcard_server):
    """The URL promises whatever the stated name resolves to, so the socket must
    answer both: "::" with V6ONLY off reaches IPv4 as ::ffff:... — an AF_INET
    0.0.0.0 would leave an IPv6-only user a URL nothing listens on."""
    port = urllib.parse.urlsplit(wildcard_server).port
    for loopback in ("127.0.0.1", "[::1]"):
        assert fetch(f"http://{loopback}:{port}/api/state")[0] == 200, loopback


def test_the_stated_host_wildcard_binds_what_a_kernel_without_ipv6_has(
    page_dir, monkeypatch
):
    """A kernel with IPv6 switched off refuses AF_INET6 at the constructor, and
    the reader who most needs `--host` is on exactly such a box — headless, where
    the derived address is loopback and no browser is local. So the wildcard is
    restated as 0.0.0.0, which says the same thing in the family that is left,
    and the page serves. A literal v6 address keeps its refusal: every interface
    is not what that record chose."""
    real_socket = socket.socket

    def kernel_without_ipv6(family=socket.AF_INET, *args, **kwargs):
        if family == socket.AF_INET6:
            raise OSError(
                errno.EAFNOSUPPORT, "Address family not supported by protocol"
            )
        return real_socket(family, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", kernel_without_ipv6)
    with pytest.raises(OSError) as refused:
        hosting_model.server_at(
            "fd7a:115c:a1e0::1", 0, http_model.handler_for(page_dir, TOKEN)
        )
    # Name the errno, or the assertion is satisfied on a v6-capable machine by
    # EADDRNOTAVAIL from an address that is local nowhere — a bare OSError says
    # nothing about whether the family refusal under test was ever reached.
    assert refused.value.errno == errno.EAFNOSUPPORT

    httpd = hosting_model.server_at("::", 0, http_model.handler_for(page_dir, TOKEN))
    assert httpd.socket.family == socket.AF_INET
    assert httpd.server_address[0] == "0.0.0.0"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        assert fetch(f"http://127.0.0.1:{port}/api/state")[0] == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_address_and_key_outlive_the_session_that_first_served(
    page_dir, monkeypatch
):
    """`start_server` restarts a dead server through the detached service. The
    user's browser has been polling one URL since it died, so a fresh address or
    key there would leave the page it reopens talking to nothing."""
    monkeypatch.setenv("SSH_CONNECTION", "10.1.1.9 51234 10.20.30.40 22")
    recorded = service_model.page_access(page_dir)
    minted = service_model.host_key()
    service = {
        **recorded,
        "port": 41234,
        "enabled": False,
        "lifetime": "session",
    }
    files_model.write_json(page_dir / "service.json", service)

    monkeypatch.setenv("SSH_CONNECTION", "10.1.1.9 51235 172.16.0.1 22")
    assert service_model.page_access(page_dir) == service
    assert service_model.host_key() == minted


def test_start_server_spawns_the_public_entrypoint(page_dir, monkeypatch):
    calls = []

    class Pipe:
        def readline(self):
            return "http://127.0.0.1:41234/?t=test\n"

        def read(self):
            return ""

    class Child:
        stdout = Pipe()
        stderr = Pipe()

    def popen(command, **options):
        calls.append((command, options))
        return Child()

    monkeypatch.setattr(hosting_model.subprocess, "Popen", popen)

    started = hosting_model.start_server(
        page_dir,
        host="page.example",
        standing=True,
        revive=True,
    )

    assert started[0] == "http://127.0.0.1:41234/?t=test"
    assert calls == [
        (
            [
                sys.executable,
                str(INTERACT_SCRIPT.resolve()),
                "server",
                "_serve",
                str(page_dir),
                "--host",
                "page.example",
                "--standing",
                "--revive",
            ],
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "start_new_session": True,
            },
        )
    ]


# A lease held the way a server holds one: until the service is disabled, which
# is the exit `stop_when_service_ends` takes. A holder that slept instead would
# leave a sweep that reached it blocked on the lease, and the run with it. The
# deadline is for the sweep that never comes — the case
# `test_a_run_ends_only_the_servers_it_started` exists to catch — so a missing
# sweep fails a test instead of leaving a process behind.
HOLDER = """
import fcntl, json, sys, time
from pathlib import Path
page = Path(sys.argv[1])
lease = open(page / "server.lock", "a+b")
fcntl.flock(lease, fcntl.LOCK_EX)
print("held", flush=True)
deadline = time.monotonic() + 60
while json.loads((page / "service.json").read_text())["enabled"]:
    if time.monotonic() > deadline:
        sys.exit("no sweep came")
    time.sleep(0.05)
"""


def hold_standing(page: Path, start) -> subprocess.Popen:
    """A standing page with its lease held, as `server run --standing` leaves one."""
    page.mkdir(parents=True)
    files_model.write_json(
        page / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 1,
            "enabled": True,
            "lifetime": "standing",
        },
    )
    holder = start(
        [sys.executable, "-c", HOLDER, str(page)], stdout=subprocess.PIPE, text=True
    )
    assert holder.stdout.readline() == "held\n"
    return holder


def test_a_page_left_standing_is_the_sweeps_to_stop():
    """The forgotten server, on purpose: a standing page under the run's state
    home, its lease held, and nothing here to stop it. `_no_page_outlives_its_test`
    ends it, and `test_a_run_ends_only_the_servers_it_started` runs this test to
    watch that happen. Not `spawn`, whose teardown would end the holder before
    the sweep reached it."""
    hold_standing(service_model.state_home() / "pages" / "left", subprocess.Popen)


def test_a_run_ends_only_the_servers_it_started(tmp_path, spawn):
    """The sweep reads the run's own state home, and does read it.

    A standing server under the machine's `~/.local/state/leaf/pages` looks to
    the sweep exactly like a page a test forgot: a held lease under an enabled
    service. The sweep once took its root from the environment before
    `isolated_session` had moved it, and stopped every such server on the
    machine after every test (tests/CLAUDE.md, "A process the suite starts ends
    with the run").

    So a run is made against a home planted the way the developer's is, of the
    one test that leaves a page for the sweep. The planted page must come out as
    it went in, with nothing written beside it, and the page the run left under
    its own home must have been stopped — or the sweep proves nothing."""
    home = tmp_path / "state"
    review = home / "leaf" / "pages" / "review"
    holder = hold_standing(review, spawn)
    planted = sorted(path.relative_to(home) for path in home.rglob("*"))
    nested = tmp_path / "nested"

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-n0",
            "-q",
            f"--basetemp={nested}",
            "-o",
            f"cache_dir={tmp_path / 'cache'}",
            f"{__file__}::test_a_page_left_standing_is_the_sweeps_to_stop",
        ],
        env=os.environ | {"XDG_STATE_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert files_model.read_json(review / "service.json")["enabled"]
    assert holder.poll() is None
    assert sorted(path.relative_to(home) for path in home.rglob("*")) == planted
    (left,) = nested.rglob("left/service.json")
    assert not files_model.read_json(left)["enabled"]
    assert not service_model.lock_is_held(left.parent / "server.lock")


def test_one_key_reads_every_page_this_machine_serves(page_dir, tmp_path):
    """The key is the machine's, so a reader admitted at one page is admitted at
    the next with no second link — cookies are scoped by host and blind to the
    port, so the jar the first arrival filled is the jar the second is read
    from."""
    second = tmp_path / "second-page"
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(second)]).exit_code == 0
    )
    key = service_model.host_key()

    servers = [
        hosting_model.LeafHTTPServer(
            ("127.0.0.1", 0), http_model.handler_for(directory, key)
        )
        for directory in (page_dir, second)
    ]
    for httpd in servers:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        first, other = (f"http://127.0.0.1:{h.server_address[1]}" for h in servers)
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        with opener.open(f"{first}/api/state?t={key}") as arrival:
            assert arrival.status == 200
        # No query: the cookie the first page set is the whole of the second's
        # authorization, and a 403 here raises rather than returns.
        with opener.open(f"{other}/api/state") as onward:
            assert onward.status == 200
    finally:
        for httpd in servers:
            httpd.shutdown()


def test_state_ships_the_machines_other_live_leaves(page_dir, server, tmp_path):
    """`others` on /api/state is every page a live server holds up, found through
    both places pages are written down — the conventional pages/ home and the
    canonical claims — titled by its newest published version, and nothing
    else: not a dead server's page, not one with nothing published to link, and
    not the page doing the asking. Each entry carries the same presence facts the
    page ships about itself (`presence`), so the panel's row and that page's own
    banner judge from one shape — where the claiming session is working included,
    which is the one thing on a row's hover that no title could ever say."""
    pages = service_model.state_home() / "pages"
    live_url = neighbour_page(pages / "live", title="The other page")
    files_model.write_json(
        pages / "live" / "status.json",
        {"state": "working", "detail": "measuring", "ts": "2026-01-01T00:00:00-08:00"},
    )
    record_claim(
        pages / "live",
        id="s9",
        agent="Codex",
        cwd="/work/api",
    )
    # A server that died leaves its record behind and its lock with the kernel:
    # the file says served and nothing holds it, which is what reads as stale.
    neighbour_page(pages / "dead", title="A dead server's page", dead=True)
    neighbour_page(pages / "unpublished", title="Nothing to link", published=False)
    # A neighbour something corrupted: its log no longer parses, and the fault
    # stays its own — skipped, rather than 500ing every other page's poll.
    neighbour_page(pages / "corrupt", title="A corrupted page")
    (pages / "corrupt" / "comments.jsonl").write_text('{"kind": "note", "author"')
    # Presence belongs to the same isolation boundary as the log and version. A
    # malformed private claim on another page must not make this page's poll fail.
    malformed = pages / "malformed-status"
    neighbour_page(malformed, title="Malformed status")
    files_model.write_json(
        malformed / "status.json",
        {
            "state": "working",
            "detail": "unknown",
            "ts": event_model.now_iso(),
            "work": [{}],
        },
    )
    # A page served from a session's scratch directory, plus the asking page
    # itself: the claim index finds the first, and the second stays out of its own
    # list. Untitled, so the title falls back to the directory's name.
    scratch = tmp_path / "scratch"
    claimed_url = neighbour_page(scratch)
    record_claim(scratch, released="2026-01-01T00:00:00-08:00")

    state = json.loads(fetch(f"{server}/api/state")[1])
    # A directory holding no claims at all is still a complete answer: every
    # presence field arrives, as its absent-file default.
    unclaimed = {
        "status": {"state": "idle", "detail": "", "ts": None},
        "claims": [],
        "listening": False,
        "cursor": 0,
        "pending": 0,
        "agent": "Claude",
        "host": None,
        "session_alive": None,
        "claim_session": None,
        "turn_closed": None,
        "viewed": None,
        "session_cwd": None,
    }
    assert state["others"] == [
        {
            "title": "scratch",
            "url": claimed_url,
            **unclaimed,
            "agent": "Claude",
            "host": "claude-code",
            "session_alive": False,
            "claim_session": "s1",
            "session_cwd": str(Path.cwd()),
        },
        {
            "title": "The other page",
            "url": live_url,
            **unclaimed,
            "status": {
                "state": "working",
                "detail": "measuring",
                "ts": "2026-01-01T00:00:00-08:00",
            },
            "agent": "Codex",
            "host": "claude-code",
            "session_alive": True,
            "claim_session": "s9",
            "session_cwd": "/work/api",
        },
    ]


def test_state_reads_claims_and_their_log_floor_in_one_transaction(
    page_dir, server, monkeypatch
):
    """A poll cannot combine an old event window with a claim written after it.

    Status writes hold the log lease because a claim records the exact log floor it
    followed. The state reader takes the same lease across both reads, so every claim
    in a response names a floor that response's events actually contain."""
    event_model.append_event(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "why?"},
    )
    entered = threading.Event()
    release = threading.Event()
    original = http_model.full_state

    def held_state(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(http_model, "full_state", held_state)
    response = []

    def read_state():
        response.append(json.loads(fetch(f"{server}/api/state")[1]))

    reader = threading.Thread(target=read_state)
    reader.start()
    assert entered.wait(5)

    def resolve_then_claim():
        writer_entered.set()
        with service_model.PageTransaction(page_dir) as page:
            page.append_event({"kind": "resolve", "author": "claude", "parent": "c1"})
            page.set_status(
                "working",
                "checking",
                work={
                    "subject": {"kind": "thread", "id": "c1"},
                    "after": page.events[-1]["seq"],
                },
            )

    writer_entered = threading.Event()
    writer = threading.Thread(target=resolve_then_claim)
    writer.start()
    assert writer_entered.wait(5)
    assert service_model.lock_is_held(page_dir / "comments.jsonl")
    release.set()
    reader.join(5)
    writer.join(5)
    assert not reader.is_alive() and not writer.is_alive()

    events = response[0]["events"]
    assert [(event["kind"], event["seq"]) for event in events] == [("comment", 1)]
    assert response[0]["claims"] == []

    after = json.loads(fetch(f"{server}/api/state")[1])
    assert [(event["kind"], event["seq"]) for event in after["events"]] == [
        ("comment", 1),
        ("resolve", 2),
    ]
    assert len(after["claims"]) == 1
    assert after["claims"][0]["log_floor"] == 2


def test_others_ships_on_a_network_facing_bind_too(wildcard_server):
    """The list is not gated on the bind. Every URL in it carries the key its
    reader already arrived on, because there is one key for the machine — so a
    `--host` reader sees the neighbours, and sees no key they were not already
    holding. Gating it again is what to do if the key is ever scoped per page."""
    neighbour_page(
        service_model.state_home() / "pages" / "live", title="The other page"
    )
    state = json.loads(fetch(f"{wildcard_server}/api/state")[1])
    assert [entry["title"] for entry in state["others"]] == ["The other page"]


def test_a_bare_ipv6_address_is_bracketed_in_the_url():
    """A v6 address is colons all the way down, and the authority separates its port
    with one too."""
    assert (
        service_model.page_url("fd00::1", 41999, "k") == "http://[fd00::1]:41999/?t=k"
    )
    assert (
        service_model.page_url("10.20.30.40", 41999, "k")
        == "http://10.20.30.40:41999/?t=k"
    )


def test_a_conversation_predicate_cannot_follow_replayed_value_state(page_dir):
    """Conversation seats are installed from authored predicates once. Refuse a
    declaration that would make replay and the POST hold gate disagree about one."""
    registry = json.loads((page_dir / "registry.json").read_text())
    registry["lf-task"]["x-conversation"]["when"] = {"status": ["blocked"]}
    (page_dir / "registry.json").write_text(json.dumps(registry))

    result = check(page_dir)

    assert result.exit_code == 1
    assert (
        "x-conversation predicate attributes are authored and static" in result.output
    )


def test_a_hold_comment_can_only_hold_its_declared_exact_section(server, page_dir):
    """The stronger send is one comment, not a comment followed by a pause action.
    Its target is therefore checked at the comment door against the same declaration
    that rendered the control, or a forged field could pause any id on the page."""
    version = page_dir / "versions" / "v1.html"
    version.write_text(
        PAGE.replace(
            "</section>",
            '<lf-tasks id="work"><lf-task id="goal" status="active" talk>'
            "<strong>Goal</strong></lf-task>"
            '<lf-task id="plain-goal" status="active"><strong>Plain</strong>'
            "</lf-task></lf-tasks></section>",
        )
    )
    publish(page_dir)
    event = {
        "kind": "comment",
        "version": 1,
        "text": "Finish the current pass, then pause here.",
        "anchor": {"section": "goal"},
        "holds": "goal",
        "attempt": "hold_comment_good_1",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(event).encode())
    assert status == 200, body
    assert event_model.read_events(page_dir)[-1]["holds"] == "goal"

    ambiguous = {
        **event,
        "anchor": {"section": "goal", "quote": "Goal"},
        "attempt": "hold_comment_bad_quote",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(ambiguous).encode())
    assert status == 400
    assert "exact-section anchor" in json.loads(body)["error"]

    for target in ("plain-goal", "plan"):
        bad = {
            **event,
            "holds": target,
            "attempt": f"hold_comment_bad_{target.replace('-', '_')}",
        }
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400
        assert "matching x-conversation hold target" in json.loads(body)["error"]


def test_a_version_response_comment_requires_its_declared_exact_section(
    server, page_dir
):
    version = page_dir / "versions" / "v1.html"
    version.write_text(PAGE.replace("<lf-options>", '<lf-options id="choice" choose>'))
    publish(page_dir)
    event = {
        "kind": "comment",
        "version": 1,
        "text": "Add the camera first.",
        "anchor": {"section": "choice"},
        "response": "version",
        "attempt": "version_response_good_1",
    }

    status, body = fetch(f"{server}/api/event", data=json.dumps(event).encode())

    assert status == 200, body
    assert event_model.read_events(page_dir)[-1]["response"] == "version"

    forged = {
        **event,
        "anchor": {"section": "plan"},
        "attempt": "version_response_forged_1",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(forged).encode())
    assert status == 400
    assert "exact-section x-conversation response target" in json.loads(body)["error"]


def test_publish_keeps_its_checked_log_snapshot_until_the_note(monkeypatch, page_dir):
    """A browser action arriving during the check waits behind the publication
    note. Otherwise the successor can go live without ever being checked against
    the decision that replays onto it."""
    html = PAGE.replace("<lf-options>", '<lf-options id="choice" choose>')
    (page_dir / "versions" / "v1.html").write_text(html)
    publish(page_dir)
    (page_dir / "versions" / "v2.html").write_text(html)
    entered = threading.Event()
    release = threading.Event()
    original = publishing_model.cmd_check

    def paused_check(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(publishing_model, "cmd_check", paused_check)
    failures = []

    def run_publish():
        try:
            publishing_model.cmd_publish(page_dir, 2, "next")
        except (AssertionError, SystemExit) as error:  # surface thread failures here
            failures.append(error)

    action = {
        "kind": "action",
        "author": "user",
        "version": 1,
        "widget": "choice",
        "action": "choose",
        "detail": {"options": ["flag-first"]},
    }
    publisher = threading.Thread(target=run_publish)
    publisher.start()
    assert entered.wait(5)
    writer = threading.Thread(target=lambda: event_model.append_event(page_dir, action))
    writer.start()
    time.sleep(0.05)
    assert writer.is_alive(), "the browser writer crossed the checked snapshot"
    release.set()
    publisher.join(5)
    writer.join(5)

    assert not failures
    assert not publisher.is_alive() and not writer.is_alive()
    ordered = [
        (event["kind"], event.get("version"))
        for event in event_model.read_events(page_dir)
        if event["kind"] in {"note", "action"}
    ]
    assert ordered == [("note", 1), ("note", 2), ("action", 1)]


def test_a_thread_whose_opening_message_was_torn_away_still_reads(page_dir):
    """The tolerance above has to reach the readings built on it, or it buys nothing.

    `read_events` skips a torn line and keeps reading, so a reply can outlive the
    message it answers — the one way the log tears from inside the product's own
    grammar rather than from someone editing the file. Two readings walk that
    relation: `thread_roots`, which resolves a reply to the conversation it is in,
    and `build_threads`, which builds the conversation itself. The first was made to
    degrade and the second went on raising, so a page that had lost one line answered
    `page state` with a KeyError and handed the session picking it up nothing at all —
    the reply included, which was still perfectly readable.

    Both now put the surviving reply under the id the lost message was known by, so an
    action naming that id in `resolves` still finds its thread and the two readings
    cannot disagree about which conversation a message is in."""
    publish(page_dir)
    event_model.append_event(
        page_dir,
        {
            "kind": "comment",
            "id": "c-lost",
            "author": "user",
            "version": 1,
            "text": "the question nobody can read any more",
        },
    )
    event_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "id": "r-kept",
            "author": "claude",
            "parent": "c-lost",
            "version": 1,
            "text": "the answer that survived it",
        },
    )
    log = page_dir / "comments.jsonl"
    lines = log.read_text(encoding="utf-8").split("\n")
    torn = next(i for i, line in enumerate(lines) if '"id": "c-lost"' in line)
    lines[torn] = lines[torn][: len(lines[torn]) // 2]  # the tear a crash leaves
    log.write_text("\n".join(lines), encoding="utf-8")

    events = event_model.read_events(page_dir)
    assert [e["id"] for e in events if e["kind"] == "reply"] == ["r-kept"], (
        "the tear took the reply with it, so nothing below is being read"
    )
    assert event_model.thread_roots(events)["r-kept"] == "c-lost"
    threads = event_model.build_threads(events, {})
    assert list(threads) == ["c-lost"], (
        f"the two readings put the reply in different conversations: {list(threads)}"
    )
    assert [m["id"] for m in threads["c-lost"]["msgs"]] == ["r-kept"]

    # And the command a session picks the page up with, which carries the
    # surviving words as the thread's own message rather than anywhere in its
    # output — the reading that lets that session answer the reply it can see.
    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state.exit_code == 0, state.output
    [thread] = json.loads(state.output)["threads"]
    assert [(m["id"], m["text"]) for m in thread["messages"]] == [
        ("r-kept", "the answer that survived it")
    ]
