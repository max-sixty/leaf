"""The website route adapter preserves Leaf's canonical served-page contract."""

import importlib.util
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import verify_site
from click.testing import CliRunner
from leaf.codex import _prompt as delivery_prompt
from leaf.codex import _queues as codex_queues
from leaf.event_log import append_event, read_events
from leaf.hosting import server_at
from leaf.http import supervised_document

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "website_server", ROOT / "worker" / "server.py"
)
website_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(website_server)
_reply_spec = importlib.util.spec_from_file_location(
    "website_reply", ROOT / "worker" / "reply.py"
)
website_reply = importlib.util.module_from_spec(_reply_spec)
_reply_spec.loader.exec_module(website_reply)
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


class FakeCodexHost:
    def __init__(self):
        self.attached = []
        self.responded = []

    def attach(self, page_dir: Path, event_id: str) -> str | None:
        if not website_server.agent_event_pending(page_dir, event_id):
            return None
        thread_id = website_server.agent_event_thread(page_dir, event_id)
        if thread_id is not None:
            return thread_id
        self.attached.append(page_dir)
        return "codex-thread"

    def response_authorized(self, authorization: str | None) -> bool:
        return authorization == "Bearer adapter-secret"

    def fallback_reply(
        self, page_dir: Path, event_id: str, text: str, failure: str
    ) -> dict | None:
        return website_server.WebsiteCodexHost("codex").fallback_reply(
            page_dir, event_id, text, failure
        )

    def respond(self, page_dir: Path, event_id: str, text: str, **target) -> dict:
        self.responded.append((page_dir, event_id, text, target))
        return {"id": "fast-reply"}


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
        server_id="server",
        layer_id="layer",
        bootstrap="",
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
        "turn_start_completed",
        **website_server.agent_event_fields(("event-1", "event-2")),
        turnId="turn-1",
    )

    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == [
        {
            "component": "leaf-agent",
            "event": "turn_start_completed",
            "turnId": "turn-1",
            "eventId": "event-1",
        },
        {
            "component": "leaf-agent",
            "event": "turn_start_completed",
            "turnId": "turn-1",
            "eventId": "event-2",
        },
    ]


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
    monkeypatch.setattr(website_server, "agent_event_pending", lambda *_: True)
    monkeypatch.setattr(host, "_ensure_server", lambda: process)
    monkeypatch.setattr(
        website_server,
        "page_claim",
        lambda page: {"id": "hosted-thread", "host": "codex"},
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
    queued = []
    accepted = []
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
        "queue_delivery",
        lambda *args: queued.append(args),
    )
    monkeypatch.setattr(
        website_server,
        "accept_codex_delivery",
        lambda *args, **kwargs: (
            accepted.append((args, kwargs))
            or [
                {
                    "page": page_dir,
                    "events": ("reader-event",),
                    "turn": None,
                }
            ]
        ),
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
    assert started == (
        []
        if status == "active"
        else [("socket", page_dir, "hosted-thread", process, [])]
    )
    assert closed == ([("hosted-thread",)] if closes_turn else [])
    if status == "active":
        assert queued == [("codex", "hosted-thread", "delivery-pointer", host.endpoint)]
        assert accepted == [(("hosted-thread",), {"phase": "queued"})]
        assert follows[0][-1] == "delivery-1"
        assert follows[0][-2] == {
            "page": str(page_dir),
            "reply_to": "reader-event",
            "responds": "reader-event",
        }
    else:
        assert queued == []


def test_a_queued_website_reply_binds_only_to_its_delivery_turn(page_dir):
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    website_server.accept_codex_delivery("hosted-thread")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second while active"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir, identity, {"pid": os.getpid()}
    )
    [queued] = website_server.accept_codex_delivery("hosted-thread", phase="queued")

    def queued_turn(turn_id, delivery_id):
        return {
            "method": "turn/started",
            "params": {
                "threadId": "hosted-thread",
                "turn": {
                    "id": turn_id,
                    "status": "inProgress",
                    "items": [
                        {
                            "id": f"message-{turn_id}",
                            "type": "userMessage",
                            "content": [
                                {
                                    "type": "text",
                                    "text": delivery_prompt(delivery_id),
                                }
                            ],
                        }
                    ],
                },
            },
        }

    class Socket:
        def __init__(self):
            self.messages = iter(
                [
                    queued_turn("other-turn", "another-delivery"),
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "other-turn",
                                "status": "completed",
                                "items": [],
                            },
                        },
                    },
                    queued_turn("queued-turn", prepared.payload["id"]),
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "queued-turn",
                                "status": "completed",
                                "items": [
                                    {
                                        "id": "answer",
                                        "type": "agentMessage",
                                        "phase": "final_answer",
                                        "text": "The queued answer",
                                    }
                                ],
                            },
                        },
                    },
                ]
            )
            self.closed = False

        def recv(self, timeout):
            return json.dumps(next(self.messages))

        def close(self):
            self.closed = True

    socket = Socket()
    website_server.WebsiteCodexHost("codex")._follow_turn(
        socket,
        page_dir,
        "hosted-thread",
        None,
        None,
        queued["events"],
        website_server.stream_reply_target(prepared.payload),
        prepared.payload["id"],
    )

    pickups = [
        event
        for event in read_events(page_dir)
        if event["kind"] == "pickup" and second["id"] in event["events"]
    ]
    assert [(event["phase"], event["turn"]) for event in pickups] == [
        ("queued", None),
        ("opened", "queued-turn"),
    ]
    replies = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [(reply["responds"], reply["text"]) for reply in replies] == [
        (second["id"], "The queued answer")
    ]
    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == "queued-turn"
    assert claim["turn_closed"] is not None
    assert socket.closed


def test_an_unbound_queued_website_turn_leaves_the_direct_turn_running(page_dir):
    first = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "first"},
    )
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [opened] = website_server.accept_codex_delivery("hosted-thread")
    second = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "second while active"},
    )
    prepared = website_server.prepare_codex_delivery(
        page_dir, identity, {"pid": os.getpid()}
    )
    [queued] = website_server.accept_codex_delivery("hosted-thread", phase="queued")
    website_server._set_stream_activity(
        "hosted-thread", opened["turn"], "Still working"
    )

    class Socket:
        closed = False

        def __init__(self):
            self.messages = iter(
                [
                    {
                        "method": "turn/started",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "unidentified-turn",
                                "status": "inProgress",
                                "items": [],
                            },
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "hosted-thread",
                            "turn": {
                                "id": "unidentified-turn",
                                "status": "completed",
                                "items": [],
                            },
                        },
                    },
                ]
            )

        def recv(self, timeout):
            try:
                return json.dumps(next(self.messages))
            except StopIteration as error:
                raise OSError("connection closed") from error

        def close(self):
            self.closed = True

    socket = Socket()
    website_server.WebsiteCodexHost("codex")._follow_turn(
        socket,
        page_dir,
        "hosted-thread",
        None,
        None,
        queued["events"],
        website_server.stream_reply_target(prepared.payload),
        prepared.payload["id"],
    )

    claim = website_server.page_claim(page_dir)
    assert claim["turn"] == opened["turn"]
    assert claim["turn_closed"] is None
    stream = website_server.PageTransaction(page_dir).status["stream"]["activity"]
    assert (stream["turn"], stream["detail"]) == (opened["turn"], "Still working")
    activity = website_server.full_state(page_dir, read_events(page_dir))["activity"]
    assert activity["kind"] == "working"
    assert activity["counts"]["handling"] == 1
    assert activity["counts"]["queued"] == 1
    assert [obligation["event"] for obligation in activity["obligations"]] == [
        first["id"],
        second["id"],
    ]
    assert socket.closed


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
    monkeypatch.setattr(
        website_server,
        "accept_codex_delivery",
        lambda *args, **kwargs: (
            accepted.append((args, kwargs))
            or [
                {
                    "page": page_dir,
                    "events": ("reader-event",),
                    "turn": "leaf-turn",
                }
            ]
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
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    assert prepared == [(page_dir, identity, {"pid": 41})]
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
    assert accepted == [(("hosted-thread",), {"turn": "initial-turn"})]


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


def test_the_private_reply_client_resolves_manifest_routes(tmp_path):
    site = tmp_path / "site"
    pages = {
        "/": ("_leaf/pages/index", "product"),
        "/examples": ("_leaf/pages/examples", "product"),
        "/examples/triage-board": ("examples/triage-board", "example"),
    }
    write_manifest(site, pages)
    for route, (directory, _kind) in pages.items():
        page_dir = site / directory
        page_dir.mkdir(parents=True, exist_ok=True)
        expected = "" if route == "/" else route
        assert website_reply.published_route(page_dir) == expected


def test_the_private_reply_client_carries_a_new_thread_target():
    assert website_reply.response_payload(
        [
            "reader-event",
            "Moved the thread.",
            "--section",
            "result",
            "--part",
            "chart",
        ]
    ) == {
        "event": "reader-event",
        "text": "Moved the thread.",
        "section": "result",
        "part": "chart",
    }


def test_the_private_reply_client_timing_is_numeric():
    assert website_server._agent_response_timing(
        {
            "Leaf-Agent-Helper-Entered-At-Ms": "1789180475000",
            "Leaf-Agent-Helper-Request-At-Ms": "1789180475125",
        }
    ) == {
        "helperEnteredAtMs": 1789180475000,
        "helperRequestAtMs": 1789180475125,
    }
    with pytest.raises(ValueError, match="Unix millisecond"):
        website_server._agent_response_timing(
            {
                "Leaf-Agent-Helper-Entered-At-Ms": "1789180475000",
                "Leaf-Agent-Helper-Request-At-Ms": "unknown",
            }
        )


def test_the_private_reply_client_sends_its_timing(tmp_path, monkeypatch, capsys):
    token = tmp_path / "reply-token"
    token.write_text("adapter-secret", encoding="utf-8")
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"status":"appended"}'

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(
        website_reply.sys,
        "argv",
        ["reply.py", "reader-event", "The reply."],
    )
    monkeypatch.setattr(website_reply, "published_route", lambda page: "/example")
    monkeypatch.setattr(
        website_reply.time,
        "time_ns",
        iter([1_000_000_000, 1_125_000_000]).__next__,
    )
    monkeypatch.setattr(website_reply.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("LEAF_REPLY_TOKEN", str(token))

    website_reply.main()

    request, timeout = requests[0]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert request.full_url == "http://127.0.0.1:8080/example/_leaf/agent/respond"
    assert headers["leaf-agent-helper-entered-at-ms"] == "1000"
    assert headers["leaf-agent-helper-request-at-ms"] == "1125"
    assert timeout == 20
    assert capsys.readouterr().out == '{"status":"appended"}\n'


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
        def poll(self):
            return None

    def popen(command, **options):
        launched.update(command=command, options=options)
        host.socket_path.touch()
        return Process()

    monkeypatch.setattr(website_server.subprocess, "Popen", popen)

    assert host._ensure_server() is not None
    assert launched["options"]["env"]["LEAF"] == website_server.LEAF_COMMAND
    assert (
        launched["options"]["env"]["LEAF_REPLY"] == website_server.AGENT_REPLY_COMMAND
    )
    assert launched["options"]["env"]["LEAF_REPLY_TOKEN"] == str(host.reply_token_path)
    assert host.reply_token_path.read_text(encoding="utf-8") == host.reply_token
    assert host.reply_token_path.stat().st_mode & 0o777 == 0o600
    assert launched["options"]["cwd"] == str(site_root)
    assert "LEAF_SKILL_DIR" not in launched["options"]["env"]
    assert launched["command"] == [
        "codex",
        "app-server",
        "--listen",
        host.endpoint,
    ]
    assert "$LEAF" in website_server.CODEX_INSTRUCTIONS
    assert "structured `leaf_delivery` tool output" in website_server.CODEX_INSTRUCTIONS
    assert "$LEAF delivery claim ID" in website_server.CODEX_INSTRUCTIONS
    assert "$LEAF delivery read ID" in website_server.CODEX_INSTRUCTIONS
    assert '$LEAF_REPLY EVENT_ID "..."' in website_server.CODEX_INSTRUCTIONS
    assert "your normal final message is the\n  only reply operation" in (
        website_server.CODEX_INSTRUCTIONS
    )
    assert "Do not run\n  `$LEAF_REPLY`" in website_server.CODEX_INSTRUCTIONS
    assert "no separate `leaf publish` command" in website_server.CODEX_INSTRUCTIONS
    assert "$LEAF version check" not in website_server.CODEX_INSTRUCTIONS
    assert "$LEAF status" not in website_server.CODEX_INSTRUCTIONS
    assert (
        "$LEAF resolve . --to RESPONSE_CONVERSATION"
        in website_server.CODEX_INSTRUCTIONS
    )
    assert "normal final" in website_server.CODEX_INSTRUCTIONS
    assert "Use exactly one response path" in website_server.CODEX_INSTRUCTIONS
    assert (
        "The host binds, streams, and commits it" in website_server.CODEX_INSTRUCTIONS
    )


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
            fail_prewarm.wait(timeout=2)
            raise RuntimeError("startup failed")
        return process

    monkeypatch.setattr(host, "_ensure_server", ensure_server)
    monkeypatch.setattr(host, "_warm_leaf_cli", lambda: None)
    monkeypatch.setattr(website_server, "page_claim", lambda page: None)
    monkeypatch.setattr(host, "_start_thread", lambda *args: "hosted-thread")

    prewarm = host.prewarm()
    assert prewarm_started.wait(timeout=2)
    attached = []
    request = threading.Thread(
        target=lambda: attached.append(host.attach(page_dir, "reader-event"))
    )
    request.start()
    assert calls == [None]
    fail_prewarm.set()
    prewarm.join(timeout=2)
    request.join(timeout=2)

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
        release.wait(timeout=2)
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
    assert started.wait(timeout=2)
    second.start()
    assert second_called.wait(timeout=2)
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

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
        release_app.wait(timeout=2)

    def warm_leaf_cli():
        leaf_started.set()
        release_leaf.wait(timeout=2)
        leaf_finished.set()

    monkeypatch.setattr(host, "_ensure_server", ensure_server)
    monkeypatch.setattr(host, "_warm_leaf_cli", warm_leaf_cli)

    thread = host.prewarm()

    assert app_started.wait(timeout=2)
    assert leaf_started.wait(timeout=2)
    assert thread.is_alive()
    release_app.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    release_leaf.set()
    assert leaf_finished.wait(timeout=2)


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
    host.reply_token_path.write_text(host.reply_token, encoding="utf-8")
    host.reply_token_owned = True

    host.close()

    assert process.stopped
    assert host.process is None
    assert not host.socket_path.exists()
    assert not host.reply_token_path.exists()


def test_closing_a_host_that_started_no_server_preserves_the_shared_socket(tmp_path):
    """A passive host does not own another host's process-global files."""
    socket_path = tmp_path / "app-server.sock"
    socket_path.touch()
    host = website_server.WebsiteCodexHost("codex", socket_path)
    host.reply_token_path.write_text("another host's token", encoding="utf-8")

    host.close()

    assert socket_path.exists()
    assert host.reply_token_path.read_text(encoding="utf-8") == "another host's token"


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


def test_the_website_task_preserves_a_delivery_the_app_server_rejects(
    page_dir, monkeypatch
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    host = website_server.WebsiteCodexHost("codex")
    during_start = []

    def reject(*args):
        during_start.append(
            website_server.full_state(page_dir, read_events(page_dir))["activity"]
        )
        raise RuntimeError("rejected")

    monkeypatch.setattr(host, "_send", reject)
    try:
        with pytest.raises(RuntimeError, match="rejected"):
            host._start_turn(
                "socket",
                page_dir,
                "hosted-thread",
                type("Process", (), {"pid": os.getpid()})(),
            )
    finally:
        host.close()

    [(_, queue)] = codex_queues("hosted-thread")
    assert queue["state"] == "offering"
    assert queue["batches"][0]["events"] == [{"seq": 1, "id": comment["id"]}]
    assert during_start[0]["kind"] == "working"
    assert during_start[0]["detail"] == "Starting"
    assert (
        website_server.full_state(page_dir, read_events(page_dir))["activity"]["kind"]
        != "working"
    )


def test_notifications_before_start_response_reach_the_turn_follower(
    page_dir, monkeypatch
):
    messages = iter(
        [
            json.dumps({"id": 0, "result": {}}),
            json.dumps({"id": 1, "result": {"thread": {"id": "hosted-thread"}}}),
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
    monkeypatch.setattr(website_server, "_app_server_connect", lambda endpoint: socket)
    monkeypatch.setattr(website_server, "_set_stream_activity", lambda *args: None)
    monkeypatch.setattr(website_server, "_clear_stream_activity", lambda *args: None)
    host = website_server.WebsiteCodexHost("codex")
    monkeypatch.setattr(host, "_hold_waiter", lambda *args: None)
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *args: SimpleNamespace(
            payload={
                "id": "delivery-1",
                "batches": [{"events": [{"id": "reader-event"}]}],
            }
        ),
    )
    monkeypatch.setattr(
        website_server,
        "accept_codex_delivery",
        lambda *args, **kwargs: [
            {
                "page": page_dir,
                "events": ("reader-event",),
                "turn": "leaf-turn",
            }
        ],
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
            type("Process", (), {"pid": 41})(),
            "reader-event",
        )
        == "hosted-thread"
    )

    assert completed.wait(timeout=2)
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


def test_the_starting_connection_projects_codex_activity(page_dir, monkeypatch, capsys):
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
        def __init__(self, session, turn, target):
            streamed.append((session, turn, dict(target)))

        def update(self, update):
            message = update.get("message") if update is not None else None
            if message is not None and message["phase"] == "final_answer":
                streamed.append((message["text"], message["complete"]))

        def finish(self, state, text):
            committed.append((state, text))

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
    monkeypatch.setattr(website_server, "AppServerReplyStream", ReplyStream)

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
        {
            "page": str(page_dir),
            "reply_to": "reader-event",
            "responds": "reader-event",
        },
    )

    assert updates == [
        ("hosted-thread", "initial-turn", "Starting"),
        ("hosted-thread", "initial-turn", "Running leaf version check ."),
        ("hosted-thread", "initial-turn", "Deployment verified."),
    ]
    assert clears == [("hosted-thread", "initial-turn")]
    assert streamed == [
        (
            "hosted-thread",
            "initial-turn",
            {
                "page": str(page_dir),
                "reply_to": "reader-event",
                "responds": "reader-event",
            },
        ),
        ("Deployment verified.", True),
    ]
    assert committed == [("completed", "Deployment verified.")]
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["event"] for record in logs] == [
        "turn_following_started",
        "turn_first_notification",
        "turn_first_activity",
        "turn_item_started",
        "turn_item_completed",
        "turn_item_started",
        "turn_item_completed",
        "turn_first_model_message",
        "turn_stream_completed",
    ]
    assert logs[3] == {
        "component": "leaf-agent",
        "event": "turn_item_started",
        "eventId": "reader-event",
        "turnId": "initial-turn",
        "itemId": "command-1",
        "itemType": "commandExecution",
        "itemAtMs": 1_000,
    }
    assert logs[4]["durationMs"] == 80
    assert logs[4]["status"] == "completed"
    assert logs[4]["exitCode"] == 0
    assert logs[6]["durationMs"] == 500
    assert logs[7]["phase"] == "final_answer"
    assert finished == [
        (
            page_dir,
            "hosted-thread",
            "leaf-turn",
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


def test_a_lost_starting_connection_leaves_its_response_obligation(page_dir):
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
    assert not any(event["kind"] == "reply" for event in events)
    assert website_server.page_claim(page_dir)["turn_closed"] is not None
    assert [
        obligation["event"]
        for obligation in website_server.full_state(page_dir, events)["activity"][
            "obligations"
        ]
    ] == [comment["id"]]
    assert socket.closed


def test_a_native_final_message_never_becomes_a_leaf_reply(page_dir):
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
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery("hosted-thread")
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
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    website_server.prepare_codex_delivery(
        page_dir,
        {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
        {"pid": os.getpid()},
    )
    [delivery] = website_server.accept_codex_delivery(
        "hosted-thread", turn="app-server-turn"
    )
    (page_dir / "index.html").write_text("<main>unfinished")

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
        website_server.WebsiteCodexHost("codex")._follow_turn(
            socket,
            page_dir,
            "hosted-thread",
            "app-server-turn",
            delivery["turn"],
            delivery["events"],
            {
                "page": str(page_dir),
                "reply_to": comment["id"],
                "responds": comment["id"],
            },
        )

    claim = website_server.page_claim(page_dir)
    assert claim["turn_closed"] is not None
    reply = website_server.PageTransaction(page_dir).status["stream"]["reply"]
    assert (reply["state"], reply["text"], reply["settles"]) == (
        "failed",
        "Done.",
        False,
    )
    assert socket.closed


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


def test_a_host_fallback_does_not_answer_input_an_agent_turn_already_claimed(
    page_dir,
):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    website_server.accept_codex_delivery("hosted-thread")

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


def test_an_explicit_website_reply_wins_over_the_streamed_final(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    identity = {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"}
    website_server.prepare_codex_delivery(page_dir, identity, {"pid": os.getpid()})
    [delivery] = website_server.accept_codex_delivery("hosted-thread")
    target = {
        "page": str(page_dir),
        "reply_to": comment["id"],
        "responds": comment["id"],
    }
    stream = website_server.AppServerReplyStream(
        "hosted-thread", delivery["turn"], target
    )
    host = website_server.WebsiteCodexHost("codex")

    reply = host.respond(
        page_dir,
        comment["id"],
        "Done.",
        quote="The cutoff lives in",
        section="plan",
    )

    assert reply["parent"] == comment["id"]
    assert reply["responds"] == comment["id"]
    assert reply["text"] == "Done."
    assert reply["session"] == "hosted-thread"
    assert reply["attempt"] == website_server.agent_attempt(comment["id"])
    assert reply["revision"] == 1
    assert reply["anchor"]["section"] == "plan"
    assert reply["anchor"]["quote"] == "The cutoff lives in"
    assert stream.finish("completed", "Answered on the page.") is None
    replies = [event for event in read_events(page_dir) if event["kind"] == "reply"]
    assert [(event["text"], event["responds"]) for event in replies] == [
        ("Done.", comment["id"])
    ]
    assert "stream" not in website_server.PageTransaction(page_dir).status


def test_a_host_fallback_survives_an_invalid_candidate_source(page_dir):
    comment = append_event(
        page_dir,
        {"kind": "comment", "author": "user", "text": "edit the page"},
    )
    (page_dir / "index.html").write_text("<main>unfinished")

    reply = website_server.WebsiteCodexHost("codex").fallback_reply(
        page_dir,
        comment["id"],
        "The host could not start this task.",
        "startup_failed",
    )

    assert reply is not None
    assert reply["responds"] == comment["id"]


def test_a_fallback_waits_for_external_turn_acceptance_to_be_recorded(
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
    fallback_waiting = threading.Event()

    class ObservedLock:
        def __init__(self):
            self.lock = threading.Lock()

        def __enter__(self):
            if self.lock.locked():
                fallback_waiting.set()
            self.lock.acquire()

        def __exit__(self, *args):
            self.lock.release()

    host.lock = ObservedLock()
    monkeypatch.setattr(host, "_ensure_server", lambda: process)

    def start_thread(page, process, event_id):
        website_server.prepare_codex_delivery(
            page,
            {"id": "hosted-thread", "host": "codex", "agent": "Leaf guide"},
            {"pid": process.pid},
        )
        turn_started.set()
        record_acceptance.wait(timeout=2)
        website_server.accept_codex_delivery("hosted-thread")
        return "hosted-thread"

    monkeypatch.setattr(host, "_start_thread", start_thread)

    with ThreadPoolExecutor(max_workers=2) as pool:
        attached = pool.submit(host.attach, page_dir, comment["id"])
        assert turn_started.wait(timeout=2)
        settled = pool.submit(
            host.fallback_reply,
            page_dir,
            comment["id"],
            "The host could not start this task.",
            "startup_failed",
        )

        assert fallback_waiting.wait(timeout=2)
        record_acceptance.set()
        assert attached.result(timeout=2) == "hosted-thread"
        assert settled.result(timeout=2) is None
    assert not any(
        event["kind"] == "reply" and event.get("parent") == comment["id"]
        for event in read_events(page_dir)
    )


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
        assert headers["Leaf-Session"] == "active"

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

        with pytest.raises(urllib.error.HTTPError) as unauthorized:
            post(
                f"{root}/examples/decision/_leaf/agent/respond",
                {"event": comment["id"], "text": "Forged."},
            )
        assert unauthorized.value.code == 403

        responded, _ = post(
            f"{root}/examples/decision/_leaf/agent/respond",
            {
                "event": comment["id"],
                "text": "This uses the private adapter.",
                "quote": "The cutoff lives in",
                "section": "plan",
            },
            {
                "Authorization": "Bearer adapter-secret",
                "Leaf-Agent-Helper-Entered-At-Ms": "1789180475000",
                "Leaf-Agent-Helper-Request-At-Ms": "1789180475125",
            },
        )
        assert responded == {"status": "appended", "event": "fast-reply"}
        assert agent_host.responded == [
            (
                published,
                comment["id"],
                "This uses the private adapter.",
                {"quote": "The cutoff lives in", "section": "plan", "part": ""},
            )
        ]

        for failure_fields in ({}, {"failure": "unknown"}, {"failure": None}):
            with pytest.raises(urllib.error.HTTPError) as invalid:
                post(
                    f"{root}/examples/decision/_leaf/agent/reply",
                    {"event": comment["id"], "text": "Failure", **failure_fields},
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
            {
                "event": comment["id"],
                "text": "This is a host failure.",
                "failure": "startup_failed",
            },
        )
        reply = read_events(published)[-1]
        assert appended == {"status": "appended", "event": reply["id"]}
        assert reply == {
            "kind": "reply",
            "author": "claude",
            "agent": "Leaf guide",
            "session": "leaf-website-agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "This is a host failure.",
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
            {
                "event": comment["id"],
                "text": "This is a host failure.",
                "failure": "startup_failed",
            },
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
            {"event": first["id"], "text": "Now stale", "failure": "rate_limited"},
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


def test_a_failed_verifier_page_reports_its_browser_errors(browser):
    page = browser.new_page()
    try:
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
    finally:
        page.close()


def test_the_agent_response_clock_waits_until_the_reply_is_on_screen(browser):
    page = browser.new_page()
    try:
        verify_site.observe_startup(page)
        url = "https://site-verifier.test/visible-response"
        page.route(
            url,
            lambda route: route.fulfill(
                content_type="text/html",
                body="""<div class="lf-threads" style="height: 100px; overflow: auto">
                  <div style="height: 500px"></div>
                  <div class="lf-msg claude"><span class="lf-msg-text">Visible reply</span></div>
                </div>""",
            ),
        )
        page.goto(url)
        page.evaluate("window.__leafVerifier.startVisibleReplyClock")
        page.wait_for_timeout(100)
        assert page.evaluate("window.__leafVerifier.visibleReplyAt") is None

        page.locator(".lf-msg.claude").scroll_into_view_if_needed()
        page.wait_for_function("window.__leafVerifier.visibleReplyRecorded")
        assert page.evaluate("window.__leafVerifier.visibleReplyAt") is not None
    finally:
        page.close()


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
    reply = host.fallback_reply(
        page_dir, comment["id"], "New failure wording.", failure
    )
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
    for text in (
        "deployment verified",
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
