"""The website route adapter preserves Leaf's canonical served-page contract."""

import importlib.util
import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from leaf.event_log import read_events
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


def test_the_website_host_delivers_into_the_existing_codex_thread(
    page_dir, tmp_path, monkeypatch
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
            before_close("socket", {"thread": {"id": "hosted-thread"}})
        return {"thread": {"id": "hosted-thread"}}

    monkeypatch.setattr(host, "_request", request)
    started = []
    monkeypatch.setattr(
        host,
        "_start_turn",
        lambda *args: started.append(args) or ("hosted-thread", "turn-2"),
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
        lambda *args: accepted.append(args),
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
    assert accepted == [("hosted-thread", "initial-turn")]


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


def test_the_starting_connection_projects_codex_activity(monkeypatch):
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
                    "method": "turn/completed",
                    "params": {
                        "threadId": "hosted-thread",
                        "turn": {"id": "initial-turn"},
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

    website_server.WebsiteCodexHost._follow_turn(
        socket, "hosted-thread", "initial-turn"
    )

    assert updates == [
        ("hosted-thread", "initial-turn", "Starting"),
        ("hosted-thread", "initial-turn", "Running leaf version check ."),
    ]
    assert clears == [("hosted-thread", "initial-turn")]
    assert socket.closed


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


def test_a_retried_agent_start_returns_the_accepted_task(
    page_dir, tmp_path, monkeypatch
):
    site = tmp_path / "site"
    published = site / "examples" / "decision"
    published.parent.mkdir(parents=True)
    shutil.copytree(page_dir, published)
    (site / "sitenote.js").write_text("export {};")
    write_manifest(site, {"/examples/decision": ("examples/decision", "example")})
    monkeypatch.setattr(website_server, "agent_event_pending", lambda *args: True)
    monkeypatch.setattr(
        website_server,
        "agent_event_thread",
        lambda *args: "already-started-thread",
    )
    agent_host = FakeCodexHost()
    httpd = server_at("127.0.0.1", 0, website_server.handler_for(site, agent_host))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        answer, _ = post(
            f"{root}/examples/decision/_leaf/agent/start",
            {"event": "reader-event"},
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
