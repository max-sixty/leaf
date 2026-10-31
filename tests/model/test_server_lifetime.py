"""A page server's lifetime: `server start`, `stop` and `run`, persistent, session,
background-job and desktop-app lifetimes, the reaper that retires a server, and restarts across a
re-vendor."""

import http.client
import http.cookiejar
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    available_loopback_port,
    command_findings,
    declared,
    fixture_service,
    publish,
    read_record,
    record_claim,
    serving,
    start_server_command,
    wait_for,
    write_record,
)

from leaf import cli as cli_model
from leaf import harness as harness_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import presence as presence_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf.refusals import Refused


def reaper_retires(page: Path, monkeypatch) -> bool:
    """Run the real lifetime decision for three cycles, advancing its grace clock.

    The HTTP process remains real and owns its own clock. Here the same reaper reads
    the real service and claim with controlled product time, so survival is observed
    after completed decisions rather than after a scheduling allowance.
    """
    clock = SimpleNamespace(now=0, cycles=0)

    class ChecksComplete(Exception):
        pass

    def next_check(_seconds):
        clock.cycles += 1
        clock.now += schema_model.ORPHAN_GRACE_SECS + 1
        if clock.cycles == 3:
            raise ChecksComplete

    def retire(code):
        assert code == 0
        raise SystemExit(code)

    with monkeypatch.context() as controlled:
        controlled.setattr(
            server_model,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now, sleep=next_check),
        )
        controlled.setattr(server_model, "os", SimpleNamespace(_exit=retire))
        try:
            server_model.stop_when_service_ends(page)
        except ChecksComplete:
            return False
        except SystemExit:
            return True
    raise AssertionError("the reaper neither completed its checks nor retired")


@pytest.mark.parametrize(
    "stopped", ["during the block", "during the lease wait", "never"]
)
def test_a_stop_during_a_restart_keeps_the_service_stopped(
    page_dir, monkeypatch, stopped
):
    """`leaf server stop` while `page init` holds a service down to re-vendor it
    finds the service already disabled, and the restart must not enable it
    again after the block: the stop is the later word. Without one, the restart
    enables the service and starts it as a revival. A stop can also land while the
    restart's own stop is still waiting out the old server's lease, between two of
    its passes, and a later pass must not write the restart's mark back over it."""
    write_record(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    starts = []

    def recorded_start(page, **kwargs):
        starts.append(kwargs)
        return hosting_model.PageStart("http://127.0.0.1:1/", None, page)

    monkeypatch.setattr(hosting_model, "start_server", recorded_start)
    if stopped == "during the lease wait":
        # The old server holds its lease through the restart's first pass, and the
        # plain stop runs in the pause before the next one.
        take_lease, sleep = hosting_model.take_lease, hosting_model.time.sleep
        held = iter([True])
        monkeypatch.setattr(
            hosting_model,
            "take_lease",
            lambda path: None if next(held, False) else take_lease(path),
        )
        paused = iter([True])

        def stop_in_the_pause(seconds):
            if next(paused, False):
                hosting_model.cmd_stop(page_dir)
            sleep(seconds)

        monkeypatch.setattr(hosting_model.time, "sleep", stop_in_the_pause)
    with hosting_model.restarting_server(page_dir, harness_model.session_harness()):
        assert not read_record(page_dir / "service.json")["enabled"]
        if stopped == "during the block":
            hosting_model.cmd_stop(page_dir)

    service = read_record(page_dir / "service.json")
    assert "restart" not in service
    if stopped == "never":
        assert service["enabled"]
        assert starts == [
            {
                "persistent": True,
                "revive": True,
                "harness": harness_model.session_harness(),
            }
        ]
    else:
        assert not service["enabled"]
        assert starts == []


def test_a_restart_leaves_the_service_of_a_session_that_took_the_page_meanwhile(
    page_dir, monkeypatch
):
    """A re-vendor decides from the page's claim that its session may bring the
    service back, and another session can take the page before the service goes
    down. The stop then belongs to that session's service, not this one's, so it
    keeps running and the re-vendor is refused rather than run under the new owner."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    fixture_service(page_dir, available_loopback_port(), lifetime="session")
    restarting_for = harness_model.session_harness()
    decided = hosting_model._restarts_for_session

    def taken_after_the_decision(page, harness):
        comes_back = decided(page, harness)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
        service_model.claim_page(page)
        return comes_back

    monkeypatch.setattr(
        hosting_model, "_restarts_for_session", taken_after_the_decision
    )
    with (
        pytest.raises(Refused, match="another session took"),
        hosting_model.restarting_server(page_dir, restarting_for),
    ):
        pytest.fail("the re-vendor ran over another session's page")
    service = read_record(page_dir / "service.json")
    assert service["enabled"] and "restart" not in service


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


def test_server_maintenance_needs_no_native_subscription(page_dir, monkeypatch):
    """Retained servers publish rows and retire without spending native watchers.

    Advance maintenance after a log append and then a service withdrawal. Both
    loops must still read the files and act on the next look.
    """
    from leaf import file_changes, server_rows

    fixture_service(page_dir, available_loopback_port(), lifetime="persistent")

    def forbidden(*_args, **_kwargs):
        pytest.fail("server maintenance allocated a native subscription")

    monkeypatch.setattr(file_changes, "FileChanges", forbidden)
    publisher = server_rows.RowPublisher(page_dir, "maintenance-test")
    monkeypatch.setattr(
        server_rows,
        "exit_serving",
        lambda status: pytest.fail(f"row publisher exited with status {status}"),
    )

    class Finished(BaseException):
        pass

    seen = []

    def after_row(seconds):
        assert seconds == presence_model.PRESENCE_CACHE_S
        row = server_rows.ROW.read(publisher.path)["row"]
        seen.append(row["threads"]["open"])
        if len(seen) == 1:
            assert seen == [0]
            append_carried_log_record(
                page_dir, {"kind": "comment", "author": "user", "text": "why?"}
            )
            return
        assert seen == [0, 1]
        raise Finished

    with monkeypatch.context() as timer:
        timer.setattr(
            server_rows,
            "time",
            SimpleNamespace(
                monotonic=time.monotonic,
                time=time.time,
                sleep=after_row,
            ),
        )
        with pytest.raises(Finished):
            publisher.run()

    def stop_after_check(_seconds):
        service = server_model.read_service(page_dir)
        server_model.write_service(page_dir, {**service, "enabled": False})

    def exited(status):
        assert status == 0
        raise Finished

    monkeypatch.setattr(server_model, "time", SimpleNamespace(sleep=stop_after_check))
    monkeypatch.setattr(server_model, "exit_serving", exited)
    with pytest.raises(Finished):
        server_model.stop_when_service_ends(page_dir)


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
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page_dir)
    assert hosting_model.start_server(page_dir, harness=harness_model.session_harness())
    assert read_record(page_dir / "service.json")["lifetime"] == "session"
    cleanup_model.end_harness_instance("bg-job")
    turn_record = cleanup_model.session_record("bg-job")
    assert turn_record is not None
    assert turn_record["turn_closed"] is not None
    assert not reaper_retires(page_dir, monkeypatch)
    assert server_model.running_server(page_dir)
    assert service_model.owned_pages("bg-job") == [page_dir.resolve()]
    assert presence_model.presence(page_dir, [])["session_alive"] is True

    (job / "state.json").unlink()
    assert reaper_retires(page_dir, monkeypatch)
    wait_for(
        lambda: server_model.running_server(page_dir),
        lambda running: not running,
        failure="the background-job server stayed up after its job was deleted",
    )
    assert service_model.owned_pages("bg-job") == []
    assert presence_model.presence(page_dir, [])["session_alive"] is False


def test_a_claim_takes_the_job_lifetime_only_for_the_jobs_own_session(
    page_dir, tmp_path, monkeypatch
):
    """CLAUDE_JOB_DIR is inherited, so a session started under a background job's
    shell tool carries the job's directory while being a process of its own: its
    claim names its pid. A job record that is not there is refused, since a claim
    written on it would be over before the server it licensed came up."""
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "the-job"})
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    claim_record = service_model.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["pid"] == os.getpid()
    value_2 = service_model.page_claim(page_dir)
    assert value_2 is not None
    assert "job" not in value_2

    (job / "state.json").unlink()
    with pytest.raises(Refused, match="names no job record"):
        service_model.claim_page(page_dir)


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
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local_one")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    assert service_model.claim_page(page_dir)
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


def test_a_claim_takes_the_app_lifetime_only_for_the_apps_own_session(
    page_dir, tmp_path, monkeypatch
):
    """CLAUDE_CODE_HOST_SESSION_ID is inherited, so a session started under an app
    session's shell tool names the app's record while being a process of its own;
    so does a session whose app keeps no record."""
    monkeypatch.setenv("HOME", str(tmp_path))
    record = (
        tmp_path
        / "Library/Application Support/Claude/claude-code-sessions/acct/org"
        / "local_one.json"
    )
    record.parent.mkdir(parents=True)
    cleanup_model.write_json(record, {"cliSessionId": "the-app", "isArchived": False})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    for host in ("local_one", "local_unrecorded"):
        monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", host)
        harness_3 = harness_model.session_harness()
        assert harness_3 is not None
        assert harness_3.lifetime() == {"pid": os.getpid()}


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
    assert "already serving at" in refused.stderr
    assert "server stop" in refused.stderr
    # Nothing on stdout, so a caller reading the URL there reads no URL.
    assert not refused.stdout.strip()
    assert service_model.page_claim(page_dir) is None


def test_server_stop_disables_desired_state_without_signalling_a_pid(
    page_dir, monkeypatch
):
    write_record(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 41000,
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    (page_dir / "server.lock").write_bytes(b"")

    def unexpected_signal(*_args):
        pytest.fail("an unlocked record's pid was signalled")

    monkeypatch.setattr(os, "kill", unexpected_signal)

    assert hosting_model.cmd_stop(page_dir) is False
    assert read_record(page_dir / "service.json")["enabled"] is False


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


def test_server_stop_waits_for_the_live_server_to_release_its_lease(
    page_dir, persistent_server
):
    server = persistent_server(page_dir)
    # The ready lines are printed inside the server's startup page lock. Let that
    # transaction finish before pausing the process, so this checks the live lease
    # barrier rather than freezing startup while it still owns the page lock.
    with leases_model.page_locked(page_dir):
        pass
    os.kill(server.pid, signal.SIGSTOP)
    outcomes, errors = [], []

    def stop():
        try:
            outcomes.append(hosting_model.cmd_stop(page_dir))
        except BaseException as error:
            errors.append(error)

    stopping = threading.Thread(target=stop)
    stopping.start()
    try:
        wait_for(
            lambda: read_record(page_dir / "service.json")["enabled"],
            lambda enabled: not enabled,
            failure="server stop never disabled the service",
        )
        returned_while_paused = not stopping.is_alive()
    finally:
        os.kill(server.pid, signal.SIGCONT)
    stopping.join(timeout=STATED_TIMEOUT)
    assert not stopping.is_alive(), "server stop never returned once the server resumed"
    server.wait(timeout=STATED_TIMEOUT)

    assert not returned_while_paused, "server stop returned before lock release"
    assert not stopping.is_alive(), "server stop did not cross the release barrier"
    assert errors == []
    assert outcomes == [True]
    assert not leases_model.lock_is_held(page_dir / "server.lock")


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

    accepted.settimeout(STATED_TIMEOUT)
    try:
        accepted.sendall(b"\r\n")
        remainder = accepted.recv(1)
    except OSError:
        remainder = b""
    assert remainder == b""


def test_a_sessionless_server_ignores_a_stale_claim_and_requires_explicit_stop(
    page_dir, dead_pid, persistent_server, monkeypatch
):
    record_claim(page_dir, id="old-session", pid=dead_pid, agent="Codex")
    server = persistent_server(page_dir)
    assert not reaper_retires(page_dir, monkeypatch)
    assert server.poll() is None, "a manual server inherited the stale session claim"
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)


def test_server_run_persistent_declines_the_claim_a_harness_session_offers(
    page_dir, spawn
):
    """`--lifetime persistent` from inside a harness is the bare-shell statement made
    explicit: the launch declines the claim it could have made, so the server
    records the persistent lifetime and the page stays nobody's — no watcher
    thread to stop it when the harness pid goes, no SessionEnd reaper. The harness is
    the suite's own session, which every command here already runs under. Its user
    stops it with Ctrl-C, which ends it at once, as `server stop` does
    (`exit_serving`), with SIGINT's status."""
    process = spawn(
        [
            *LEAF_COMMAND,
            "server",
            "run",
            "--lifetime",
            "persistent",
            str(page_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reading = json.loads(process.stdout.readline())
    assert reading["url"].startswith("http://127.0.0.1:")
    assert reading["lifetime"] == "persistent"
    assert read_record(page_dir / "service.json")["lifetime"] == "persistent"
    assert service_model.page_claim(page_dir) is None

    process.send_signal(signal.SIGINT)
    _, error = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 128 + signal.SIGINT, error


def test_server_run_temporary_uses_the_browser_harness_boundary(page_dir, spawn):
    """A temporary serve is real HTTP with process-owned lifetime and access.

    It writes neither half of durable delivery: no service for a later wait to revive,
    and no claim for this test's harness session to watch.
    """
    process = spawn(
        [*LEAF_COMMAND, "server", "run", "--lifetime", "temporary", str(page_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    reading = json.loads(process.stdout.readline())
    url = reading["url"]
    assert url.startswith("http://127.0.0.1:")
    assert reading["lifetime"] == "temporary"
    state = urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
    assert urllib.request.urlopen(state).status == 200
    assert not (page_dir / "service.json").exists()
    assert service_model.page_claim(page_dir) is None

    process.send_signal(signal.SIGINT)
    _, error = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 1, error
    assert json.loads(error)["error"] == "interrupted"


def test_server_run_persistent_refuses_to_adopt_a_session_server(page_dir):
    """A stated lifetime contradicted by the running server is refused with the
    way out named, exactly as a stated `--host` is — not silently ignored."""
    serving(page_dir, 1, "session")
    result = CliRunner().invoke(
        cli_model.cli, ["server", "run", "--lifetime", "persistent", str(page_dir)]
    )
    assert result.exit_code != 0
    assert "server stop" in result.output


# A server an older Leaf started: it holds the serving lease and exits once its
# record is gone, as `server.stop_when_service_ends` does.
OLDER_SERVER = """
import sys, time
from pathlib import Path
from leaf.leases import take_lease
page = Path(sys.argv[1])
lease = take_lease(page / "server.lock")
print("held" if lease else "refused", flush=True)
while (page / "service.json").exists():
    time.sleep(0.02)
"""


def older_server(page_dir, spawn):
    """An older Leaf's persistent serve: its `"lifetime": "standing"` record, and a
    process holding the lease over it."""
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 1,
            "enabled": True,
            "lifetime": "standing",
        },
    )
    process = spawn(
        [sys.executable, "-c", OLDER_SERVER, str(page_dir)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout.readline().strip() == "held"
    return process


def test_a_service_record_this_version_cannot_read_is_no_service(page_dir, spawn):
    """An older Leaf recorded a persistent serve as `"lifetime": "standing"`. This
    version reads that record as absent rather than as a session server, so a
    persistent start is not refused as one. An explicit stop discards the record,
    which is what ends a server an older Leaf runs over it, and reports it stopped:
    whether a server ran is the lease's to say, not the record's."""
    process = older_server(page_dir, spawn)
    assert server_model.read_service(page_dir) is None
    assert server_model.running_server(page_dir) is None
    assert hosting_model._reuse_server(page_dir, None, persistent=True) is None

    assert hosting_model.cmd_stop(page_dir) is True
    assert not (page_dir / "service.json").exists()
    assert process.wait(timeout=STATED_TIMEOUT) == 0
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_a_re_vendor_stops_a_server_whose_record_it_cannot_read(
    page_dir, spawn, capsys
):
    """`page init` re-vendors with no server running, since the layer a server serves
    is what the re-vendor replaces. A server an older Leaf runs over a record this
    version cannot read is still running, so the re-vendor stops it first, and it
    stays stopped: there is no lifetime this version could bring it back under."""
    process = older_server(page_dir, spawn)
    with hosting_model.restarting_server(page_dir, harness_model.session_harness()):
        assert not leases_model.lock_is_held(page_dir / "server.lock")
    assert process.wait(timeout=STATED_TIMEOUT) == 0
    assert not (page_dir / "service.json").exists()
    assert "stays stopped" in capsys.readouterr().err


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
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir)
    # Without this the hook would skip the page for the wrong reason and the test
    # would pass with the bug in: the persistent check has to be what spares it.
    assert page_dir in service_model.owned_pages("later")

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
    assert page_dir not in service_model.owned_pages("later")
    # Explicit stop crosses that server's release barrier before returning.
    assert hosting_model.cmd_stop(page_dir) is True
    server.wait(timeout=STATED_TIMEOUT)
