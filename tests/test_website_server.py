"""The website route adapter preserves Leaf's canonical served-page contract."""

import importlib.util
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from leaf.event_log import append_event, read_events
from leaf.hosting import server_at

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
_verify_spec = importlib.util.spec_from_file_location(
    "verify_site", ROOT / "scripts" / "verify-site.py"
)
verify_site = importlib.util.module_from_spec(_verify_spec)
_verify_spec.loader.exec_module(verify_site)


def get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(url) as response:
        return response.read(), dict(response.headers)


def post(url: str, body: dict, headers: dict | None = None) -> tuple[dict, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read()), dict(response.headers)


def write_manifest(site: Path, pages: dict[str, tuple[str, str]]) -> None:
    """Give a focused server fixture the same generated routing authority as a build."""
    manifest = {
        "release": "0" * 64,
        "pages": {
            route: {"directory": directory, "kind": kind}
            for route, (directory, kind) in pages.items()
        },
    }
    target = site / website_server.SITE_MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest), encoding="utf-8")


class FakeCodexHost:
    def __init__(self):
        self.attached = []
        self.abandoned = []

    def attach(self, page_dir: Path) -> str:
        self.attached.append(page_dir)
        return "codex-thread"

    def abandon(self, page_dir: Path, event_id: str) -> None:
        self.abandoned.append((page_dir, event_id))


def test_the_website_label_follows_the_script_contract_not_its_formatting():
    document = (
        b'<!doctype html><html><head><script\n type="module" '
        b'src="/leaf.js"></script></head><body></body></html>'
    )
    injected = website_server.with_sitenote(document, "/examples/decision")
    assert injected.index(b"/examples/decision/sitenote.js") < injected.index(
        b'src="/leaf.js"'
    )


@pytest.mark.parametrize(
    ("status", "closes_turn"),
    [
        ("active", False),
        ("idle", True),
        ("systemError", True),
        ("notLoaded", True),
    ],
)
def test_the_website_host_delivers_into_the_existing_codex_thread(
    page_dir, tmp_path, monkeypatch, status, closes_turn
):
    host = website_server.WebsiteCodexHost(
        "codex",
        tmp_path / "app-server.sock",
        tmp_path / "app-server.log",
    )
    process = type("Process", (), {"pid": 41})()
    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    monkeypatch.setattr(
        website_server,
        "page_claim",
        lambda page: {"id": "hosted-thread", "host": "codex"},
    )
    requests = []

    def request(method, params, before_close=None):
        requests.append((method, params))
        if before_close is not None:
            before_close(
                "socket",
                {"thread": {"id": "hosted-thread", "status": {"type": status}}},
            )
        return {"thread": {"id": "hosted-thread", "status": {"type": status}}}

    monkeypatch.setattr(host, "_request", request)
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

    thread_id = host.attach(page_dir)

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
    assert started == [("socket", page_dir, "hosted-thread", process)]
    assert closed == ([("hosted-thread",)] if closes_turn else [])


def test_the_website_task_is_a_scoped_leaf_codex_thread(page_dir, monkeypatch):
    host = website_server.WebsiteCodexHost("codex")
    requests = []
    sent = []
    prepared = []
    accepted = []

    def request(method, params, before_close=None):
        requests.append((method, params))
        result = {"thread": {"id": "hosted-thread"}}
        if before_close is not None:
            before_close("socket", result)
        return result

    monkeypatch.setattr(host, "_request", request)

    def send(socket, method, params):
        sent.append((socket, method, params))
        return {"turn": {"id": "initial-turn"}}

    monkeypatch.setattr(host, "_send", send)
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *args: prepared.append(args) or "<leaf-delivery />",
    )
    monkeypatch.setattr(
        website_server,
        "accept_codex_delivery",
        lambda *args: (
            accepted.append(args)
            or [
                {
                    "page": page_dir,
                    "events": ("reader-event",),
                    "turn": "leaf-turn",
                }
            ]
        ),
    )

    assert host._start_thread(page_dir, type("Process", (), {"pid": 41})()) == (
        "hosted-thread"
    )
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
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    assert prepared == [(page_dir, identity, {"pid": 41})]
    assert sent == [
        (
            "socket",
            "turn/start",
            {
                "threadId": "hosted-thread",
                "input": [{"type": "text", "text": "<leaf-delivery />"}],
            },
        )
    ]
    assert accepted == [("hosted-thread",)]


def test_the_website_task_preserves_a_delivery_the_app_server_rejects(
    page_dir, monkeypatch
):
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *args: "<leaf-delivery />",
    )
    monkeypatch.setattr(
        host,
        "_send",
        lambda *args: (_ for _ in ()).throw(RuntimeError("rejected")),
    )
    with pytest.raises(RuntimeError, match="rejected"):
        host._start_turn(
            "socket", page_dir, "hosted-thread", type("Process", (), {"pid": 41})()
        )


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
        host._start_turn(
            "socket",
            page_dir,
            "hosted-thread",
            type("Process", (), {"pid": os.getpid()})(),
        )
        state = website_server.full_state(page_dir, read_events(page_dir))

        assert state["listening"] is True
        assert state["activity"]["kind"] == "handling"
        assert state["activity"]["obligations"][0]["event"] == comment["id"]

        website_server._set_stream_activity(
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


def test_the_starting_connection_projects_codex_activity(page_dir, monkeypatch):
    messages = iter(
        [
            json.dumps(
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "hosted-thread",
                        "turnId": "initial-turn",
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
                        "item": {
                            "id": "message-1",
                            "type": "agentMessage",
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
    monkeypatch.setattr(
        website_server,
        "_set_stream_activity",
        lambda *args: updates.append(args),
    )
    monkeypatch.setattr(
        website_server,
        "_clear_stream_activity",
        lambda *args: clears.append(args),
    )

    host = website_server.WebsiteCodexHost("codex")
    finished = []
    monkeypatch.setattr(host, "_finish_turn", lambda *args: finished.append(args))
    host._follow_turn(
        socket,
        page_dir,
        "hosted-thread",
        "initial-turn",
        "leaf-turn",
        ("reader-event",),
    )

    assert updates == [
        ("hosted-thread", "initial-turn", "Starting"),
        ("hosted-thread", "initial-turn", "Running leaf version check ."),
        ("hosted-thread", "initial-turn", "Deployment verified."),
    ]
    assert clears == [("hosted-thread", "initial-turn")]
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            "leaf-turn",
            ("reader-event",),
            {"id": "initial-turn", "status": "completed"},
            "Deployment verified.",
        )
    ]
    assert socket.closed


def test_a_lost_starting_connection_settles_its_unanswered_delivery(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery("hosted-thread")

    class Socket:
        closed = False

        def recv(self, timeout):
            raise OSError("connection lost")

        def close(self):
            self.closed = True

    socket = Socket()
    website_server.WebsiteCodexHost("codex")._follow_turn(
        socket,
        page_dir,
        "hosted-thread",
        "app-server-turn",
        delivery["turn"],
        delivery["events"],
    )

    events = read_events(page_dir)
    assert events[-1]["kind"] == "reply"
    assert events[-1]["parent"] == comment["id"]
    assert events[-1]["text"] == website_server.GENERATION_FAILURE_REPLY
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert website_server.full_state(page_dir, events)["activity"]["obligations"] == []
    assert socket.closed


@pytest.mark.parametrize(
    ("turn", "final_message", "reply"),
    [
        (
            {
                "id": "app-server-turn",
                "status": "failed",
                "error": {"message": "model request failed"},
            },
            None,
            website_server.GENERATION_FAILURE_REPLY,
        ),
        (
            {"id": "app-server-turn", "status": "completed", "error": None},
            None,
            website_server.MISSING_REPLY,
        ),
        (
            {"id": "app-server-turn", "status": "completed", "error": None},
            "  Deployment verified.  ",
            "Deployment verified.",
        ),
        (
            {"id": "app-server-turn", "status": "completed", "error": None},
            "![missing](/media/missing.png)",
            website_server.MISSING_REPLY,
        ),
    ],
)
def test_a_finished_website_turn_settles_its_unanswered_delivery(
    page_dir, turn, final_message, reply
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery("hosted-thread")
    host = website_server.WebsiteCodexHost("codex")

    host._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        delivery["events"],
        turn,
        final_message,
    )

    events = read_events(page_dir)
    assert events[-1] == {
        "kind": "reply",
        "author": "claude",
        "agent": "Leaf guide",
        "session": "leaf-website-agent",
        "parent": comment["id"],
        "text": reply,
        "attempt": f"website-agent-{comment['id']}",
        "id": events[-1]["id"],
        "ts": events[-1]["ts"],
        "seq": events[-1]["seq"],
    }
    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == delivery["turn"]
    assert claim["turn_closed"] is not None
    assert website_server.full_state(page_dir, events)["activity"]["obligations"] == []


def test_a_finished_website_turn_does_not_overwrite_an_agent_reply(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery("hosted-thread")
    website_server.cmd_reply(
        page_dir,
        comment["id"],
        "Done.",
        "",
        identity={"agent": "Leaf guide", "session": "leaf-website-agent"},
    )
    before = read_events(page_dir)

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        delivery["events"],
        {"id": "app-server-turn", "status": "completed", "error": None},
    )

    assert read_events(page_dir) == before


def test_an_old_website_completion_does_not_close_the_new_leaf_turn(page_dir):
    first = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [old_delivery] = website_server.accept_codex_delivery("hosted-thread")
    website_server.close_session_turn("hosted-thread")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second"},
    )
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [new_delivery] = website_server.accept_codex_delivery("hosted-thread")

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        old_delivery["turn"],
        old_delivery["events"],
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
    assert replies == {first["id"]: website_server.GENERATION_FAILURE_REPLY}
    state = website_server.full_state(page_dir, read_events(page_dir))
    assert [item["event"] for item in state["activity"]["obligations"]] == [
        second["id"]
    ]


def test_a_website_example_uses_the_real_page_server(page_dir, tmp_path, monkeypatch):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("document.body.dataset.site = 'example';\n")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})

    agent_host = FakeCodexHost()
    httpd = server_at(
        "127.0.0.1",
        0,
        website_server.handler_for(site, agent_host),
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert get(f"{root}/health")[0] == b"ok\n"

        document, headers = get(f"{root}/examples/decision/")
        assert b'src="/examples/decision/sitenote.js"' in document
        assert b'data-lf-entry="/examples/decision/leaf.js"' in document
        assert headers["Content-Security-Policy"] == "frame-ancestors 'none'"

        raw_state, headers = get(f"{root}/examples/decision/api/state")
        state = json.loads(raw_state)
        assert state["publication"] == {
            "kind": "example",
            "agent": "Leaf guide",
            "install_url": "/#install",
        }
        assert headers["Leaf-Layer"] == state["layer"]["generation"]

        raw_view, _ = get(
            verify_site.activation_url(f"{root}/examples/decision/", state)
        )
        view = json.loads(raw_view)
        revision = state["active"]["revision"]
        assert view["browser"]["views"][str(revision)]["basis"] == {
            "revision": revision,
            "through_seq": state["events"][-1]["seq"] if state["events"] else 0,
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

        ready, _ = post(
            f"{root}/examples/decision/_leaf/agent/turn",
            {"event": comment["id"]},
        )
        assert ready == {"status": "ready"}
        started, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_host.attached == [published]

        monkeypatch.setenv("LEAF_AGENT", "Leaf guide")
        monkeypatch.setenv("LEAF_SESSION_ID", "leaf-website-agent")
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
        appended, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "text": "This is the agent's answer."},
        )
        reply = read_events(published)[-1]
        assert appended == {"status": "appended", "event": reply["id"]}
        assert reply == {
            "kind": "reply",
            "author": "claude",
            "agent": "Leaf guide",
            "session": "leaf-website-agent",
            "parent": comment["id"],
            "text": "This is the agent's answer.",
            "attempt": f"website-agent-{comment['id']}",
            "id": reply["id"],
            "ts": reply["ts"],
            "seq": reply["seq"],
        }
        repeated, _ = post(
            f"{root}/examples/decision/_leaf/agent/reply",
            {"event": comment["id"], "text": "This is the agent's answer."},
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
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


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

    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site, FakeCodexHost()))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
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
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


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
    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site, agent_host))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        document, _ = get(f"{root}{page_root}/")
        assert b"data-lf-site" not in document
        assert f'data-lf-entry="{page_root}/leaf.js"'.encode() in document
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
        ready, _ = post(f"{root}{page_root}/_leaf/agent/turn", {"event": comment["id"]})
        assert ready == {"status": "ready"}
        started, _ = post(
            f"{root}{page_root}/_leaf/agent/start", {"event": comment["id"]}
        )
        assert started == {"status": "started", "thread": "codex-thread"}
        assert agent_host.attached == [published]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


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
        {
            "id": "already-started-thread",
            "host": "codex",
            "agent": "Leaf guide",
        },
        {"pid": os.getpid()},
    )
    website_server.accept_codex_delivery("already-started-thread")
    agent_host = FakeCodexHost()
    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site, agent_host))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        answer, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": comment["id"]},
        )

        assert answer == {"status": "started", "thread": "already-started-thread"}
        assert agent_host.attached == []
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_an_agent_reply_is_dropped_when_a_newer_reader_turn_overtakes_it(
    page_dir, tmp_path
):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}/examples/decision"
    try:
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
            {"event": first["id"], "text": "Now stale"},
        )

        assert answer == {"status": "settled"}
        assert all(event.get("text") != "Now stale" for event in read_events(published))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


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


def test_a_page_that_never_presents_names_itself_and_how_far_it_got():
    """The site gate's own timeout says nothing; the message it raises has to.

    A red `Measure the bundled release in Chrome` step carried only Playwright's
    wait, so a reader could not tell which of the three pages stalled, nor whether
    widget upgrade or the first state read was the one that never answered.
    """
    stalled = verify_site.unpresented(
        "https://leaf.page/examples/design-decision/", ["upgraded"], []
    )
    assert "examples/design-decision" in stalled
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
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery("hosted-thread")

    handling = website_server.full_state(page_dir, read_events(page_dir))
    assert handling["activity"]["kind"] == "handling"
    assert verify_site.still_answering(handling, comment["id"])
    # Another page's comment is not this gate's turn, whatever this page is doing.
    assert not verify_site.still_answering(handling, "another-event")

    website_server.WebsiteCodexHost("codex")._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        delivery["events"],
        {"id": "app-server-turn", "status": "completed", "error": None},
        "deployment verified",
    )

    settled = website_server.full_state(page_dir, read_events(page_dir))
    assert settled["activity"]["obligations"] == []
    assert not verify_site.still_answering(settled, comment["id"])


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


def test_the_deploy_gate_reads_the_container_s_own_generation_failure(page_dir):
    """The gate's retry rests on one settlement, so both sides own the same text.

    `publish-site` went red with `agent returned an unexpected reply; it replied: I
    couldn't generate a reply just now.` — the container catching a turn that never
    completed and answering the reader's standing ask, which is the deployment
    working rather than failing. The gate takes that reply as the one outcome worth
    asking again for, and a completed turn that simply posted nothing is not it.
    """
    host = website_server.WebsiteCodexHost("codex")
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [delivery] = website_server.accept_codex_delivery("hosted-thread")
    host._finish_turn(
        page_dir,
        "hosted-thread",
        delivery["turn"],
        delivery["events"],
        {"id": "app-server-turn", "status": "failed", "error": {"message": "stream"}},
    )

    def replies_to(event: dict) -> list[dict]:
        state = website_server.full_state(page_dir, read_events(page_dir))
        return [
            logged
            for logged in state["events"]
            if logged.get("kind") == "reply" and logged.get("parent") == event["id"]
        ]

    assert verify_site.generation_failed(replies_to(comment))

    # A turn that completed and posted nothing settles differently, and stays a
    # first-ask failure: the deployed agent broke its own instructions.
    again = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page again"},
    )
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [second] = website_server.accept_codex_delivery("hosted-thread")
    host._finish_turn(
        page_dir,
        "hosted-thread",
        second["turn"],
        second["events"],
        {"id": "app-server-turn", "status": "completed", "error": None},
    )
    assert replies_to(again) != []
    assert not verify_site.generation_failed(replies_to(again))


class _Read:
    ok = True
    status = 200

    def __init__(self, payload: dict, body: str = "", headers: dict | None = None):
        self.payload = payload
        self.body = body
        self.headers = headers or {}

    def json(self) -> dict:
        return self.payload

    def text(self) -> str:
        return self.body


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
    """A deployed page whose first turn stops without generating a reply.

    The container settles that turn's standing ask itself, and the second turn does
    the work: this is the shape `publish-site` hit, answered the way the settlement
    text asks for.
    """

    def __init__(self, heading: str):
        self.heading = heading
        self.request = self
        self.comments: list[dict] = []

    def post(self, url: str, data: dict, **kwargs) -> _Read:
        comment = {
            "id": f"comment-{len(self.comments) + 1}",
            "attempt": data["attempt"],
            "revision": data["revision"],
        }
        self.comments.append(comment)
        return _Read({"state": {"events": [comment]}})

    def get(self, url: str, **kwargs) -> _Read:
        if url.endswith("/api/state"):
            return _Read(self.state())
        return _Read({}, f"<h1>{self.heading}</h1>")

    def state(self) -> dict:
        events = [
            {
                "kind": "reply",
                "parent": "comment-1",
                "text": website_server.GENERATION_FAILURE_REPLY,
            }
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


def test_the_deploy_gate_sends_the_new_message_the_container_asks_for():
    """A turn that never generated a reply is asked again, not reported.

    `publish-site` went red on a deployment whose own container had caught the failed
    turn and said what to do about it. The pass now does that, and the second ask has
    to be its own event: an ask that reused the first attempt would be answered with
    the first comment, and the gate would wait out a turn nobody started.
    """
    heading = "Deployment abcd1234 verified"
    context = _FailedFirstTurn(heading)
    asked = verify_site.ask_until_answered(
        context,
        "https://leaf.page/examples/design-decision/",
        "https://leaf.page/examples/design-decision/api/state",
        "layer",
        "release",
        heading,
        "deployment-abcd1234",
        {"active": {"revision": 1, "url": "revisions/1.html"}},
    )
    assert asked.asks == 2
    assert asked.turn.answer["text"] == "deployment verified"
    assert asked.turn.published["revision"] == 2
    first, second = context.comments
    assert first["attempt"] != second["attempt"]
    # The second ask continues the page the first turn left rather than an older one.
    assert second["revision"] == 1


def test_the_deploy_gate_stops_reading_a_turn_the_container_has_closed():
    """A settled generation failure is terminal, so the wait ends where it lands.

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
                "text": website_server.GENERATION_FAILURE_REPLY,
            }
        ],
    }
    context = _StateReads([working])
    turn = verify_site.await_turn(
        context,
        "https://leaf.page/examples/design-decision/",
        "https://leaf.page/examples/design-decision/api/state",
        "layer",
        "release",
        comment,
        1,
        "Deployment abcd1234 verified",
        None,
        # Seconds rather than `TURN_LIMIT`: a wait that stopped reading this reply
        # would come back on the next assertion instead of running the real budget.
        time.monotonic() + 5,
    )
    # One read, though the page still names a turn on the comment: the wait ended on
    # the reply rather than on `still_answering` or a clock.
    assert context.reads == 1
    assert verify_site.still_answering(working, "comment-id")
    assert turn.answer is None
    assert verify_site.generation_failed(turn.replies)


class _PresentationWait:
    def __init__(self, waits: list[int]):
        self.waits = waits

    def wait_for(self, timeout: int) -> None:
        self.waits.append(timeout)


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
    ):
        self.heading = heading
        self.revision = revision
        self.presented_at = presented_at
        self.reload_ok = reload_ok
        self.banner = banner
        self.follows_revision = follows_revision
        self.init_scripts: list[str] = []
        self.presentation_waits: list[int] = []
        self.revision_waits: list[tuple[int, int]] = []

    def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    def on(self, event: str, handler) -> None:
        pass

    def goto(self, url: str, **kwargs) -> _Read:
        return _Read({})

    def reload(self, **kwargs) -> _Read:
        answered = _Read({})
        answered.ok = self.reload_ok
        return answered

    def wait_for_function(self, expression: str, *, arg: int, timeout: int) -> None:
        assert "lf-revision" in expression
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
        assert selector == "body[data-lf-presented]"
        return _PresentationWait(self.presentation_waits)

    def evaluate(self, script: str):
        if "presented?.at" in script:
            return self.presented_at
        if "lf-revision" in script:
            return str(self.revision)
        if "lf-status-text" in script:
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
    )
    container = _DeployedContainer(release, page)
    published = {"revision": 2, "url": "revisions/2.html"}
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
        verify_site.verify_agent_turn(_DeployedSite(container), release)

    # The ordinary first load uses the edge-page presentation bound. The post-turn
    # reload gets its own bound for both presentation and the later revision follow.
    assert page.presentation_waits == [30_000, verify_site.TURN_PRESENTATION]
    assert page.revision_waits == [(2, verify_site.TURN_PRESENTATION)]
    assert verify_site.TURN_PRESENTATION > 30_000
    # The stamps the message needs to say which stall it was. Without them a page that
    # upgraded and stalled on its first state read reports the same "no startup
    # milestone" as one whose modules never arrived.
    assert page.init_scripts == [verify_site.PROFILE_SCRIPT]
    # A green run reports startup and the post-presentation revision follow separately.
    reported = capsys.readouterr().out
    assert "presented in 28444 ms" in reported
    assert "followed revision 2 2500 ms after presentation" in reported
    assert container.closed

    # A reload the container never answered is its own reading, taken before the wait.
    # Left unchecked it arrives as a presentation timeout, which is the message this
    # branch is here to stop conflating with a slow read.
    refused = _DeployedPage(heading, revision=2, presented_at=28444.0, reload_ok=False)
    with pytest.raises(RuntimeError, match="did not reload after its agent turn"):
        verify_site.verify_agent_turn(
            _DeployedSite(_DeployedContainer(release, refused)), release
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
            _DeployedSite(_DeployedContainer(release, offline)), release
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
            _DeployedSite(_DeployedContainer(release, told)), release
        )
    assert "stands on revision 1" in str(named.value)
    assert "Claude is handling 1 update" in str(named.value)
    assert "Server offline" not in str(named.value)
    assert told.revision_waits == [(2, verify_site.TURN_PRESENTATION)]
