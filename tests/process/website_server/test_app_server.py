"""The Codex App Server behind the website harness: the thread and instructions a task
gets, prewarming, startup retries, and stopping the processes it owns."""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import leaf_website as website_server
import pytest
from interact_support import STATED_TIMEOUT, Prose, yaml_document
from interact_support import append_carried_log_record as append_event

from leaf.codex import APP_SERVER_ENV
from leaf.machine import pid_alive
from leaf.service import delivery_reply_attempt
from process.website_server import (
    write_manifest,
)


def test_hosted_agent_receives_the_response_instructions_and_delivery(
    page_dir, monkeypatch, snapshot
):
    """Capture real instructions and deliveries at the App Server wire boundary.

    Only the external App Server connection is replaced. Event admission, delivery
    preparation, response addressing, and both request builders run normally.
    """
    event = append_event(
        page_dir, {"kind": "comment", "author": "user", "text": "Use backfill first."}
    )
    harness = website_server.WebsiteCodexHarness("codex")
    outgoing = {}

    def request(resources, method, params):
        outgoing[method] = params
        result = {"thread": {"id": "hosted-thread"}}
        return "socket", result, []

    def send(socket, method, params, pending=None):
        outgoing[method] = params
        return {"turn": {"id": "initial-turn"}}

    monkeypatch.setattr(harness, "_request", request)
    monkeypatch.setattr(harness, "_follow", lambda *_: None)
    monkeypatch.setattr(harness, "_send", send)
    assert (
        harness._start_thread(page_dir, SimpleNamespace(pid=os.getpid()), event["id"])
        == "hosted-thread"
    )
    payload = json.loads(outgoing["turn/start"]["toolOutput"]["output"])
    [delivered] = payload["batches"][0]["events"]
    # Frozen for App Server, a reply is the turn's to write with its messages.
    assert delivered["answer"]["writer"] == "turn"
    replacements = {
        str(page_dir): "/page",
        event["id"]: "user-event",
        event["ts"]: "2026-09-22T10:00:00-07:00",
        payload["id"]: "00000001",
        # The turn's reply attempt is derived from the delivery id.
        delivery_reply_attempt(payload["id"]): delivery_reply_attempt("00000001"),
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
            "Actual outgoing App Server requests for an admitted user event.\n"
            "Only the page path, event/delivery identities, and timestamps are pinned.\n"
            "toolOutput.output is the complete serialized delivery the agent receives.",
            recorded,
        )
    )


def test_the_website_task_is_a_scoped_leaf_codex_thread(page_dir, monkeypatch):
    harness = website_server.WebsiteCodexHarness("codex")
    requests = []
    sent = []
    prepared = []

    def request(resources, method, params):
        requests.append((method, params))
        result = {"thread": {"id": "hosted-thread"}}
        return "socket", result, []

    monkeypatch.setattr(harness, "_request", request)
    monkeypatch.setattr(harness, "_follow", lambda *_: None)

    def send(socket, method, params, pending=None):
        sent.append((socket, method, params, pending))
        return {"turn": {"id": "initial-turn"}}

    monkeypatch.setattr(harness, "_send", send)
    monkeypatch.setattr(
        website_server,
        "prepare_codex_delivery",
        lambda *args: (
            prepared.append(args)
            or SimpleNamespace(
                payload={"id": "delivery-1", "batches": [{"events": [], "threads": []}]}
            )
        ),
    )
    assert harness._start_thread(
        page_dir, type("Process", (), {"pid": 41})(), "user-event"
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
                    "output": '{"id":"delivery-1","batches":[{"events":[],"threads":[]}]}',
                },
                "turnTrigger": "leaf",
            },
            [],
        )
    ]
    assert sent[0][-1] == []


def test_the_website_app_server_inherits_the_ready_leaf_cli(tmp_path, monkeypatch):
    """A hosted task inherits the installed Leaf CLI and selects its App Server contract."""
    site_root = tmp_path / "site"
    site_root.mkdir()
    monkeypatch.setenv("LEAF_SITE_ROOT", str(site_root))
    harness = website_server.WebsiteCodexHarness(
        "codex",
        tmp_path / "app-server.log",
    )
    launched = {}

    class Process:
        """Running until it is told to stop, which is what the harness does with it."""

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
        Path(command[3].removeprefix("unix://")).touch()
        return Process()

    monkeypatch.setattr(website_server.subprocess, "Popen", popen)

    assert harness._ensure_server() is not None
    harness.close()
    path = launched["options"]["env"]["PATH"].split(os.pathsep)
    assert shutil.which("leaf", path=path[0]) == website_server.LEAF_COMMAND
    assert "LEAF_REPLY" not in launched["options"]["env"]
    assert "LEAF_REPLY_TOKEN" not in launched["options"]["env"]
    assert launched["options"]["cwd"] == str(site_root)
    assert launched["options"]["env"][APP_SERVER_ENV] == harness.endpoint
    assert (
        launched["options"]["env"]["LEAF_HOST_LAUNCHER"] == website_server.LEAF_COMMAND
    )
    assert launched["command"] == [
        "codex",
        "app-server",
        "--listen",
        harness.endpoint,
    ]
    # Measured 2026-09-17: adding a "declare each step" instruction here made the turn
    # run a closing `resolve` and never reply, which `leaf-dev journey website-adapter`
    # caught. The hosted page's sentence comes from the steps App Server watches
    # instead, which the activity fold prefers over Leaf's own claim wording for
    # exactly this reason. The shared contract describes `leaf page open`, so what the
    # agent receives has to hand the status to the harness.
    instructions = " ".join(website_server.CODEX_INSTRUCTIONS.split())
    assert "Leave status to the harness" in instructions


def test_a_timed_out_app_server_is_stopped_before_startup_retries(
    tmp_path, monkeypatch
):
    harness = website_server.WebsiteCodexHarness(
        "codex",
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

    def popen(command, **kwargs):
        process = Process()
        processes.append(process)
        if len(processes) == 2:
            Path(command[3].removeprefix("unix://")).touch()
        return process

    monkeypatch.setattr(website_server.subprocess, "Popen", popen)
    monkeypatch.setattr(website_server.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        website_server.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + 21),
    )

    with pytest.raises(website_server.Refused, match="did not become ready"):
        harness._ensure_server()

    assert processes[0].stopped
    assert harness.process is None
    assert harness._ensure_server() is processes[1]
    harness.close()


def test_an_attach_waiting_on_failed_prewarm_retries_startup(page_dir, monkeypatch):
    harness = website_server.WebsiteCodexHarness("codex")
    prewarm_started = threading.Event()
    fail_prewarm = threading.Event()
    calls = []
    process = type("Process", (), {"pid": 41})()

    def ensure_server():
        calls.append(None)
        if len(calls) == 1:
            prewarm_started.set()
            fail_prewarm.wait(timeout=STATED_TIMEOUT)
            raise RuntimeError("startup failed")
        return process

    monkeypatch.setattr(harness, "_ensure_server", ensure_server)
    monkeypatch.setattr(harness, "_warm_leaf_cli", lambda: None)
    monkeypatch.setattr(website_server, "page_claim", lambda page: None)
    delivered = []
    monkeypatch.setattr(
        harness,
        "_start_thread",
        lambda *args: delivered.append(True) or "hosted-thread",
    )
    monkeypatch.setattr(
        website_server,
        "pending_agent_inputs",
        lambda *_: {"user-event": "hosted-thread" if delivered else None},
    )

    prewarm = harness.prewarm()
    assert prewarm_started.wait(timeout=STATED_TIMEOUT), "the prewarm never started"
    attached = []
    request = threading.Thread(
        target=lambda: attached.append(harness.attach(page_dir, "user-event"))
    )
    request.start()
    assert calls == [None]
    fail_prewarm.set()
    prewarm.join(timeout=STATED_TIMEOUT)
    assert not prewarm.is_alive(), "the failed prewarm never ended"
    request.join(timeout=STATED_TIMEOUT)
    assert not request.is_alive(), "the attach never returned after the prewarm failed"

    assert attached == ["hosted-thread"]
    assert calls == [None, None]


def test_the_website_harness_prewarms_app_server_and_leaf_cli_in_the_background(
    monkeypatch,
):
    harness = website_server.WebsiteCodexHarness("codex")
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

    monkeypatch.setattr(harness, "_ensure_server", ensure_server)
    monkeypatch.setattr(harness, "_warm_leaf_cli", warm_leaf_cli)

    thread = harness.prewarm()

    assert app_started.wait(timeout=STATED_TIMEOUT), (
        "the prewarm never began starting the app server"
    )
    assert leaf_started.wait(timeout=STATED_TIMEOUT), (
        "the prewarm never began warming the leaf CLI"
    )
    assert thread.is_alive()
    release_app.set()
    thread.join(timeout=STATED_TIMEOUT)
    assert not thread.is_alive()
    release_leaf.set()
    assert leaf_finished.wait(timeout=STATED_TIMEOUT), (
        "the leaf CLI warm-up never finished"
    )


def test_the_leaf_cli_prewarm_runs_the_installed_command(monkeypatch):
    harness = website_server.WebsiteCodexHarness("codex")
    calls = []

    monkeypatch.setattr(
        website_server.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    harness._warm_leaf_cli()

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


def test_closing_the_website_harness_stops_its_app_server(tmp_path):
    """The harness adapter owns the process it starts, including during local runs."""
    harness = website_server.WebsiteCodexHarness("codex", tmp_path / "app-server.log")

    class Process:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout=None):
            return 0

    process = Process()

    def popen(command, **options):
        Path(command[3].removeprefix("unix://")).touch()
        return process

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("LEAF_SITE_ROOT", str(tmp_path))
        patch.setattr(website_server.subprocess, "Popen", popen)
        assert harness._ensure_server() is process
        socket_path = Path(harness.endpoint.removeprefix("unix://"))
        harness.close()

    assert process.stopped
    assert harness.process is None
    assert not socket_path.exists()


def test_the_adapter_takes_its_app_server_with_it_when_it_is_told_to_stop(
    tmp_path, spawn
):
    """The stop signal reaches the App Server, not only the adapter that started it.

    `close` covers the ordinary return, and inside a container nothing else is
    needed. On a host it is: `leaf-dev journey website-adapter` runs this adapter and
    stops it with SIGTERM, and uvicorn answers that signal by stopping its loop and
    re-raising it, so the process dies before any `finally`. The App Server is in a
    session of its own, which is what makes it the one child that survives that —
    three of them were alive on a developer's machine, fifteen hours after their runs.

    The whole adapter runs here, with a stand-in for the App Server itself: the fault
    was in how this process dies, so uvicorn's signal handling, the handler beneath
    it, and the shared process owner are the parts that have to be real.
    """
    site = tmp_path / "site"
    site.mkdir()
    write_manifest(site, {})
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
from pathlib import Path

import leaf_website as module

original_harness = module.WebsiteCodexHarness
module.WebsiteCodexHarness = lambda: original_harness(
    {str(codex)!r},
    Path({str(tmp_path / "app-server.log")!r}),
)
module.main(["--port", "0"])
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
            adapter.terminate()
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
