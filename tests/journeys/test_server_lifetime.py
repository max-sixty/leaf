"""A page server's lifetime: `server start`, `stop` and `run`, persistent, session and
background-job lifetimes, the reaper that retires a server, and restarts across a
re-vendor."""

import json
import os
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND, hooks_run_this_tree
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    declared,
    fetch,
    fetch_hanging_up,
    install_payload,
    page_packages,
    publish,
    read_record,
    start_server_command,
    wait_for,
    woken,
)

from leaf.agents import presence as presence_model
from leaf.base import files as files_model
from leaf.base import leases as leases_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import cli as cli_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.pages import hosting as hosting_model
from leaf.records import transaction as transaction_model
from leaf.source.registry.storage import layer_record
from leaf_dev.page_fixtures import package_selection_args


def _another_selection(page_dir):
    """`page init` arguments selecting one more package than the page does, so the
    re-vendor changes what the page runs under."""
    extra = page_dir.parent / "extra"
    extra.mkdir()
    (extra / "overrides.css").write_text("/* another selection */\n")
    return package_selection_args((*page_packages(), "./extra"))


@pytest.mark.parametrize("changed", [False, True])
def test_page_init_restarts_a_served_page_under_the_sessions_wait(
    page_dir, tmp_path, spawn, changed
):
    """`page init` on a served page restarts its server itself, so the session's
    `leaf wait` carries on watching it. The comment after the re-vendor is the
    proof: only a wait still watching delivers it.
    """
    publish(page_dir)
    session = os.environ["CLAUDE_CODE_SESSION_ID"]
    started = start_server_command(page_dir, session_id=session)
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()

    def incarnation():
        with urllib.request.urlopen(state) as response:
            return response.headers["Leaf-Server"]

    # The record names the serving incarnation, which its responses carry as
    # `Leaf-Server`. Read the record rather than the server: a fetch the server
    # closes leaves the port in TIME_WAIT, and the restart would wait that out.
    original = server_model.running_server(page_dir)
    assert original is not None
    before = original["server_id"]
    claim = service_model.page_claim(page_dir)
    layer = layer_record(page_dir)
    assert layer is not None
    generation = layer["generation"]
    session_model.cmd_waiting(page_dir)
    waited = tmp_path / "wait.log"
    with waited.open("w", encoding="utf-8") as output:
        waiter = spawn(
            [*LEAF_COMMAND, "wait"],
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
    wait_for(
        lambda: waiter.poll() is None and leases_model.wait_is_live(page_dir, session),
        bool,
        failure="the wait did not start watching the page",
    )

    selection = _another_selection(page_dir) if changed else []
    # Reusing the recorded URL can wait through native TCP cooldown before
    # preparation finishes, independently of the session's continued watch.
    revendored = subprocess.run(
        [*LEAF_COMMAND, "page", "init", *selection, str(page_dir)],
        capture_output=True,
        text=True,
        timeout=hosting_model.PORT_WAIT_SECONDS + STATED_TIMEOUT,
        check=False,
    )
    assert revendored.returncode == 0, revendored.stderr
    layer_2 = layer_record(page_dir)
    assert layer_2 is not None
    assert (layer_2["generation"] != generation) == changed
    assert (incarnation() != before) == changed
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
    # The restart claims nothing, so the turn the claim records is left as it was.
    assert service_model.page_claim(page_dir) == claim
    assert waiter.poll() is None, waited.read_text()

    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "text": "still there?",
        },
    )
    assert waiter.wait(timeout=STATED_TIMEOUT) == 0, waited.read_text()
    _, batch, [event] = woken(waited.read_text())
    assert batch["page"] == str(page_dir)
    assert event["text"] == "still there?"


@pytest.mark.parametrize("service", ["stopped", "orphaned", "foreign"])
def test_page_init_leaves_a_service_it_cannot_restart_for_this_session(
    page_dir, service
):
    """Only an enabled service this command may restart comes back.

    A page another live session holds is refused before anything stops, served or
    stopped, since only that session's Leaf changes it (`service.refuse_held`). A
    session service whose session has ended has nobody to come back for, so the
    re-vendor stops it and leaves it for the next `server start`.
    """
    publish(page_dir)
    started = start_server_command(page_dir, session_id="other")
    assert started.returncode == 0, started.stderr
    layer_3 = layer_record(page_dir)
    assert layer_3 is not None
    generation = layer_3["generation"]
    if service == "stopped":
        assert hosting_model.cmd_stop(page_dir) is True
    elif service == "orphaned":
        cleanup_model.end_session("other")

    result = CliRunner().invoke(
        cli_model.cli, ["page", "init", *_another_selection(page_dir), str(page_dir)]
    )

    layer_4 = layer_record(page_dir)
    assert layer_4 is not None
    revendored = layer_4["generation"] != generation
    if service != "orphaned":
        assert result.exit_code == 1
        assert "is held by session other" in result.output
        assert bool(server_model.running_server(page_dir)) == (service == "foreign")
        assert not revendored
        return
    assert result.exit_code == 0, result.output
    assert revendored
    assert server_model.running_server(page_dir) is None
    assert not read_record(page_dir / "service.json")["enabled"]
    assert "has no live session owner" in result.output


@pytest.mark.parametrize("lifetime", ["persistent", "session"])
def test_init_restarts_a_served_page_onto_the_replacement_contract(
    page_dir, spawn, monkeypatch, lifetime
):
    """Re-vendoring a served page restarts its server under the recorded lifetime
    and URL, onto the new layer, and preserves the active revision contract."""
    publish(page_dir)
    old_plugin = install_payload(
        page_dir.parent / "plugins" / "cache" / "leaf" / "leaf" / "0a0a0a0a0a0a"
    )

    if lifetime == "persistent":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
        monkeypatch.delenv("CLAUDE_PID")
    old_server = spawn(
        [
            # The old plugin's own launcher, so `PLUGIN_ROOT` resolves into it and
            # this server answers out of the registry there rather than the
            # checkout's.
            old_plugin / "bin" / "leaf",
            "server",
            "run",
            str(page_dir),
            *(["--lifetime", "persistent"] if lifetime == "persistent" else []),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reading = json.loads(old_server.stdout.readline())
    url = reading["url"]
    assert url.startswith("http://127.0.0.1:")
    assert reading["lifetime"] == lifetime
    prior_status = declared(page_dir)
    prior_owner = service_model.page_claim(page_dir)

    endpoint = urllib.parse.urlsplit(url)._replace(path="/api/event").geturl()
    comment = {
        "kind": "comment",
        "revision": 1,
        "text": "Can the replacement route this?",
        "attempt": "replacement_route_1",
    }
    status, body = fetch_hanging_up(endpoint, json.dumps(comment).encode())
    assert status == 200, body

    project_layer = page_dir.parent / ".leaf"
    project_layer.mkdir()
    (project_layer / "overrides.css").write_text(":root { --lf-accent: red; }\n")
    revendored = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert revendored.exit_code == 0, revendored.output
    layer_5 = layer_record(page_dir)
    assert layer_5 is not None
    assert layer_5["packages"][-1] == "./packages/.leaf"
    # The old server went down with the restart, and this checkout's came up in its
    # place at the same URL, under the lifetime and claim it had.
    old_server.wait(timeout=STATED_TIMEOUT)
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
    assert read_record(page_dir / "service.json")["lifetime"] == lifetime
    assert service_model.page_claim(page_dir) == prior_owner
    restored = declared(page_dir)
    assert restored == prior_status

    status, body = fetch(endpoint, data=json.dumps(comment).encode(), token=None)
    assert status == 200, body
    # The replacement's first read activated the re-vendored revision, which
    # names its place in the log; the retried comment was the one already taken.
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["note", "comment", "activation"]
    assert events[1]["attempt"] == comment["attempt"]
    assert events[2]["revision"] == 2


import http.client
import shutil

from interact_support import (
    PLUGIN_ROOT,
    command_findings,
    record_claim,
)
from model.test_server_lifetime import (
    PROCESS_LISTING_REFUSED,
    reaper_retires,
)

from leaf.base import harness as harness_model
from leaf.base import schema as schema_model


def test_a_refused_revendor_leaves_the_running_server_alone(page_dir):
    """A malformed incoming registry is refused before the server goes down.

    A restart after the refusal would put this Leaf's server over the layer the
    page keeps, so a page vendored by another Leaf would be served by code its
    runtime does not speak. The same process answers at the same URL before and
    after, which is what `Leaf-Server`, the server's incarnation, says."""
    # Original decision evidence can outlive its declaration. The malformed
    # incoming registry, rather than that history, causes this refusal.
    version = page_dir / "index.html"
    version.write_text(
        version.read_text().replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-draft id="d1"><pre>A decision.</pre></lf-draft>',
        )
    )
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "d1",
            "action": "decide",
            "detail": {"decision": "approved"},
            "meaning": {
                "scope": "page",
                "unit": "d1",
                "depends": ["d1"],
                "answer": None,
            },
        },
    )
    started = start_server_command(
        page_dir, session_id=os.environ["CLAUDE_CODE_SESSION_ID"]
    )
    assert started.returncode == 0, started.stderr
    url = json.loads(started.stdout)["url"]
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()

    def incarnation():
        with urllib.request.urlopen(state) as response:
            return response.headers["Leaf-Server"], response.headers["Leaf-Layer"]

    before = incarnation()

    overlay = page_dir.parent / ".leaf"
    overlay.mkdir()
    (overlay / "registry.json").write_text("{broken")
    [refused] = command_findings("page", "init", "--package", "./.leaf", str(page_dir))

    assert refused.code == "registry-json"
    assert (current := server_model.running_server(page_dir)) is not None
    assert current["url"] == url
    assert incarnation() == before


def test_a_desktop_app_sessions_server_lives_as_long_as_the_app_session(
    page_dir, tmp_path, monkeypatch, dead_pid
):
    """The Claude desktop app stops a session's process to update, and resumes it
    only when the user opens the session, so a claim naming the process takes the
    page down while the user reads it in another window. The app's record of the
    session is the lifetime instead: the page stays served through the SessionEnd
    of the process's stop, comes back to the same generation when the session
    resumes, and retires once the record names another session or the user
    archives it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    record = (
        tmp_path
        / "Library/Application Support/Claude/claude-code-sessions/acct/org"
        / "local_one.json"
    )
    record.parent.mkdir(parents=True)
    app = {"cliSessionId": "app-session", "isArchived": False}
    cleanup_model.write_json(record, app)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "app-session")
    hooks_run_this_tree("app-session")
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_one")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    assert transaction_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir, harness=harness_model.session_harness())
    claim_record_2 = service_model.page_claim(page_dir)
    assert claim_record_2 is not None
    generation = claim_record_2["generation"]
    cleanup_model.end_harness_instance("app-session")
    assert not reaper_retires(page_dir, monkeypatch)
    assert server_model.running_server(page_dir)
    harness_2 = harness_model.session_harness()
    assert harness_2 is not None
    assert (
        cleanup_model.ensure_session("app-session", harness_2.lifetime())["generation"]
        == generation
    )
    assert service_model.claim_is_active(service_model.page_claim(page_dir))

    cleanup_model.write_json(record, {**app, "cliSessionId": "after-clear"})
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    cleanup_model.write_json(record, {**app, "isArchived": True})
    assert reaper_retires(page_dir, monkeypatch)
    wait_for(
        lambda: server_model.running_server(page_dir),
        lambda running: not running,
        failure="the app session's server stayed up after it was archived",
    )


def test_a_live_session_can_take_over_an_existing_server(
    page_dir, session_process, managed_server
):
    first, second = session_process(), session_process()
    server = managed_server(page_dir, "first", first.pid)
    record_claim(page_dir, id="second", pid=second.pid, agent="Codex")
    first.terminate()
    first.wait(timeout=STATED_TIMEOUT)
    assert server.poll() is None

    second.terminate()
    second.wait(timeout=STATED_TIMEOUT)
    server.wait(timeout=STATED_TIMEOUT)
    assert server.returncode == 0, server.stderr.read()
    assert read_record(page_dir / "service.json")["enabled"] is True


def test_server_start_hands_the_page_to_a_process_of_its_own(page_dir):
    """The command returns and the page stays up. Two long-running commands per
    leaf was one accident: `leaf wait` has to exit, its exit being how a comment
    reaches the agent, and the server has to not exit at all — so no one process
    does both, but only the watcher is the session's to hold open. The serve gets
    a session of its own, which is also what leaves a killed background task
    costing the watcher alone."""
    started = start_server_command(page_dir)
    assert started.returncode == 0, started.stderr
    reading = json.loads(started.stdout)
    url = reading["url"]
    assert url.startswith("http://127.0.0.1:")
    assert reading["lifetime"] == "session"
    info = server_model.running_server(page_dir)
    assert info and info["url"] == url
    # The child claims only after its refusal and bind checks, which is what lets
    # the loop's hooks find the session's pages without a failed start taking one.
    claim_record_3 = service_model.page_claim(page_dir)
    assert claim_record_3 is not None
    assert claim_record_3["id"] == "starter"
    service = server_model.read_service(page_dir)
    assert service is not None
    assert service["lifetime"] == "session"
    assert set(service) == {
        "host",
        "bind",
        "port",
        "enabled",
        "lifetime",
        "runtime",
        "server_id",
    }
    assert service["runtime"]["path"] == str(schema_model.PLUGIN_ROOT)
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    response = urllib.request.urlopen(state)
    assert response.status == 200
    assert response.headers["Leaf-Server"] == service["server_id"]


def test_server_start_forwards_flags_and_returns_service_output(page_dir):
    """`server start` states nothing about a serve itself. The flags go verbatim
    to the service it spawns and the account comes back from there, so the
    lifetime a flag declared and the refusal a running server earns are both that
    process's own words, carried out with its exit status."""
    persistent = start_server_command(page_dir, "--lifetime", "persistent")
    assert persistent.returncode == 0, persistent.stderr
    assert json.loads(persistent.stdout)["lifetime"] == "persistent"
    assert read_record(page_dir / "service.json")["lifetime"] == "persistent"
    assert service_model.page_claim(page_dir) is None

    refused = start_server_command(page_dir, "--host", "devbox.corp.example")
    assert refused.returncode != 0
    said = json.loads(refused.stdout)
    assert "already serving at" in said["error"]
    assert "server stop" in said["error"]
    # A refusal, so a caller reading the URL there reads no URL.
    assert "url" not in said
    assert service_model.page_claim(page_dir) is None


def test_a_sessionless_server_ignores_a_stale_claim_and_requires_explicit_stop(
    page_dir, dead_pid, persistent_server, monkeypatch
):
    record_claim(page_dir, id="old-session", pid=dead_pid, agent="Codex")
    server = persistent_server(page_dir)
    assert not reaper_retires(page_dir, monkeypatch)
    assert server.poll() is None, "a manual server inherited the stale session claim"
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_a_persistent_server_outlives_a_session_that_picks_the_page_up(
    page_dir, persistent_server, monkeypatch, capsys
):
    """The persistent serve, the whole way round: a page kept up across sessions, and a
    session that works on it for an afternoon and goes. Picking a page up earns the
    watch obligation and nothing else, so the session's end must take down neither the
    process it didn't start nor a leaf that outlives it."""
    server = persistent_server(page_dir)
    launched = server_model.running_server(page_dir)
    assert launched is not None
    assert read_record(page_dir / "service.json")["lifetime"] == "persistent"

    # A session picks the page up, the way `leaf wait` does.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "later")
    hooks_run_this_tree("later")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert transaction_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir)
    # Without this the hook would skip the page for the wrong reason and the test
    # would pass with the bug in: the persistent check has to be what spares it.
    assert page_dir in transaction_model.owned_pages("later")

    # A `server run` of its own finds this one up and reports the lifetime the
    # running server has, not the one this claiming launch would have given it.
    hosting_model.cmd_serve(page_dir, harness=harness_model.session_harness())
    served = json.loads(capsys.readouterr().out)
    assert (served["url"], served["lifetime"]) == (launched["url"], "persistent")

    cleanup_model.end_harness_instance("later")

    # The synchronous hook left the persistent service enabled and live.
    assert server_model.running_server(page_dir) == launched
    assert declared(page_dir)["state"] == "waiting"
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))
    assert page_dir not in transaction_model.owned_pages("later")
    # Explicit stop crosses that server's release barrier before returning.
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_a_background_jobs_server_lives_as_long_as_the_job(
    page_dir, tmp_path, monkeypatch, dead_pid
):
    """A background job runs each sitting on a worker its daemon retires between
    them, so a claim naming that worker's pid takes the page down an hour after
    every turn. The job's record is the lifetime instead: the page stays held
    and served whatever became of the process that claimed it, including the
    SessionEnd Claude Code runs as the worker retires, and retires when the job
    is deleted — which takes the record and may leave the directory."""
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "bg-job"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bg-job")
    hooks_run_this_tree("bg-job")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert transaction_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir, harness=harness_model.session_harness())
    assert read_record(page_dir / "service.json")["lifetime"] == "session"
    cleanup_model.end_harness_instance("bg-job")
    turn_record = cleanup_model.session_record("bg-job")
    assert turn_record is not None
    assert turn_record["turn_closed"] is not None
    assert not reaper_retires(page_dir, monkeypatch)
    assert server_model.running_server(page_dir)
    assert transaction_model.owned_pages("bg-job") == [page_dir.resolve()]
    assert presence_model.presence(page_dir, [])["session_alive"] is True

    (job / "state.json").unlink()
    assert reaper_retires(page_dir, monkeypatch)
    wait_for(
        lambda: server_model.running_server(page_dir),
        lambda running: not running,
        failure="the background-job server stayed up after its job was deleted",
    )
    assert transaction_model.owned_pages("bg-job") == []
    assert presence_model.presence(page_dir, [])["session_alive"] is False


def test_a_server_exits_when_its_session_is_hard_killed(
    page_dir, session_process, managed_server
):
    owner = session_process()
    server = managed_server(page_dir, "abandoned", owner.pid)
    owner.terminate()
    owner.wait(timeout=STATED_TIMEOUT)

    server.wait(timeout=STATED_TIMEOUT)
    assert server.returncode == 0, server.stderr.read()
    assert read_record(page_dir / "service.json")["enabled"] is True
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_an_abandoned_handoff_does_not_disable_the_server_it_reuses(
    codex_claimed_page, spawn, codex_env
):
    """Dropping a reused server's real handshake withdraws no existing service."""
    page = codex_claimed_page
    before = server_model.running_server(page)
    assert before is not None
    caller, child = socket.socketpair()
    task = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "_serve",
            str(page),
            "--harness",
            json.dumps({"name": "codex", "session": "codex-thread", "agent": "Codex"}),
            "--handshake",
            str(child.fileno()),
        ],
        env=codex_env | {"CODEX_THREAD_ID": "codex-thread"},
        pass_fds=(child.fileno(),),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child.close()
    caller.settimeout(STATED_TIMEOUT)
    try:
        with caller.makefile("rb") as announced:
            assert json.loads(announced.readline())["url"] == before["url"]
    finally:
        caller.close()
    output, errors = task.communicate(timeout=STATED_TIMEOUT)
    assert task.returncode == 0, f"{output}{errors}"
    assert server_model.running_server(page) == before


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(LEAF_COMMAND, id="module"),
        pytest.param([str(PLUGIN_ROOT / "bin" / "leaf")], id="launcher"),
        pytest.param(
            [
                "sandbox-exec",
                "-p",
                PROCESS_LISTING_REFUSED,
                str(PLUGIN_ROOT / "bin" / "leaf"),
            ],
            id="sandboxed launcher",
            marks=pytest.mark.skipif(
                not shutil.which("sandbox-exec"), reason="macOS's sandbox"
            ),
        ),
    ],
)
def test_a_temporary_server_ends_when_the_process_that_ran_it_exits(
    page_dir, spawn, command
):
    """A temporary server leaves nothing `server stop` could reach, so a caller
    that dies without stopping it, as a killed test does, must not leave it serving.
    The caller here is a shell that starts it in the background and exits. Through
    the launcher, the server's own parent is the `uv run` that `bin/leaf` execs,
    which waits on it and so outlives the caller. Codex's macOS sandbox refuses a
    listing of every process, so finding that caller must not take one."""
    # The caller hands its stdout and stderr to the server and closes its own, so
    # they reach their end when the server exits, whether it served or failed.
    caller = spawn(
        [
            "sh",
            "-c",
            '"$@" & exec >&- 2>&-; read _',
            "sh",
            *command,
            "server",
            "run",
            "--lifetime",
            "temporary",
            str(page_dir),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = caller.stdout.readline()
    assert started, caller.communicate(timeout=STATED_TIMEOUT)[1]
    state = urllib.parse.urlsplit(json.loads(started)["url"])
    state = state._replace(path="/api/state").geturl()
    assert urllib.request.urlopen(state).status == 200

    # Closing its stdin ends the caller, and reading the server's stdout and stderr
    # to their end waits for the server to exit.
    _, error = caller.communicate(timeout=STATED_TIMEOUT)
    assert error == ""
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(state)


def test_server_stop_closes_accepted_keep_alive_connections(
    page_dir, persistent_server
):
    server = persistent_server(page_dir)
    service = read_record(page_dir / "service.json")
    connection = http.client.HTTPConnection(service["host"], service["port"])
    connection.request("GET", f"/api/state?t={server_model.host_key()}")
    response = connection.getresponse()
    assert response.status == 200
    response.read()
    accepted = connection.sock
    accepted.sendall(
        (
            f"GET /api/state?t={server_model.host_key()} HTTP/1.1\r\n"
            f"Host: {service['host']}\r\n"
        ).encode()
    )

    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)

    # A closed connection reads as end of stream or a reset. A socket still open,
    # as one a surviving child process inherited would be, times out instead, and
    # `TimeoutError` is an `OSError` this must not take for a close.
    accepted.settimeout(STATED_TIMEOUT)
    try:
        accepted.sendall(b"\r\n")
        remainder = accepted.recv(1)
    except (ConnectionResetError, BrokenPipeError):
        remainder = b""
    assert remainder == b""


def test_server_stop_reports_a_server_that_exits_as_soon_as_it_is_disabled(
    page_dir, persistent_server, monkeypatch
):
    server = persistent_server(page_dir)
    write_service = hosting_model.write_service

    def write_and_wait_for_exit(directory, value):
        write_service(directory, value)
        if not value["enabled"]:
            wait_for(
                lambda: leases_model.lock_is_held(page_dir / "server.lock"),
                lambda held: not held,
                failure="server did not release its lease after stop",
            )

    monkeypatch.setattr(hosting_model, "write_service", write_and_wait_for_exit)
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)
