"""A page server's lifetime: `server start`, `stop` and `run`, persistent, session,
background-job and desktop-app lifetimes, the reaper that retires a server, and restarts across a
re-vendor."""

import contextlib
import itertools
import json
import os
import select
import signal
import socket
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
from conftest import LEAF_COMMAND, hooks_run_this_tree
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    available_loopback_port,
    fixture_service,
    read_record,
    serving,
    vendored_at_another_protocol,
    wait_for,
    write_record,
)

from leaf.agents import clerk as clerk_model
from leaf.agents import codex as codex_model
from leaf.agents import presence as presence_model
from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import schema as schema_model
from leaf.base import server as server_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.base.detached import StartRefused
from leaf.base.findings import Finding
from leaf.base.refusals import Refused
from leaf.commands import cli as cli_model
from leaf.pages import hosting as hosting_model
from leaf.pages import vendoring as vendoring_model
from leaf.records import transaction as transaction_model
from leaf.serving import server_lifetime as lifetime_model


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
            lifetime_model,
            "time",
            SimpleNamespace(monotonic=lambda: clock.now, sleep=next_check),
        )
        controlled.setattr(lifetime_model, "os", SimpleNamespace(_exit=retire))
        try:
            lifetime_model.stop_when_service_ends(page)
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
        return hosting_model.PageStart("http://127.0.0.1:1/", None, page, True)

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
                "deadline": None,
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
    transaction_model.claim_page(page_dir)
    fixture_service(page_dir, available_loopback_port(), lifetime="session")
    restarting_for = harness_model.session_harness()
    decided = hosting_model.claim_is_active

    def taken_after_the_decision(claim):
        comes_back = decided(claim)
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
        hooks_run_this_tree("s2")
        transaction_model.claim_page(page_dir)
        return comes_back

    monkeypatch.setattr(hosting_model, "claim_is_active", taken_after_the_decision)
    with (
        pytest.raises(Refused, match="another session took"),
        hosting_model.restarting_server(page_dir, restarting_for),
    ):
        pytest.fail("the re-vendor ran over another session's page")
    service = read_record(page_dir / "service.json")
    assert service["enabled"] and "restart" not in service


@pytest.mark.parametrize("lifetime", ["persistent", "session"])
def test_a_restart_for_another_session_refuses_a_held_page_before_it_stops(
    page_dir, lifetime
):
    """A restart for anyone but the session holding the page, such as a terminal's
    `server start` or the restart of a server that follows its copy while no
    session's Leaf acts for it, is refused while the page's server still runs,
    whatever the service's lifetime: only the holding session's Leaf serves it."""
    transaction_model.claim_page(page_dir)
    fixture_service(page_dir, available_loopback_port(), lifetime=lifetime)
    with (
        pytest.raises(Refused, match="is held by session"),
        hosting_model.restarting_server(page_dir, None),
    ):
        pytest.fail("the restart ran over a held page")
    service = read_record(page_dir / "service.json")
    assert service["enabled"] and "restart" not in service


CODEX_COPY = ("plugins", "cache", "leaf", "leaf", "local")
CLAUDE_CODE_COPY = ("plugins", "cache", "leaf", "leaf", "0a0a0a0a0a0a")
COPIES = {
    "codex": CODEX_COPY,
    "pi": (".pi", "agent", "git", "github.com", "max-sixty", "leaf"),
    "codex, once the session ended": CODEX_COPY,
    "claude-code": CLAUDE_CODE_COPY,
    "claude-code, once the session loads an update": CLAUDE_CODE_COPY,
    "claude-code, once the session moves on again": CLAUDE_CODE_COPY,
    "claude-code, once the session's hooks run a checkout": CLAUDE_CODE_COPY,
    "checkout": ("checkout",),
}
# The copy the session's hooks record from the server's first pass on, where it
# changes.
HOOKS_MOVE_TO = {
    "claude-code, once the session loads an update": (
        *CLAUDE_CODE_COPY[:-1],
        "1b1b1b1b1b1b",
    ),
    "claude-code, once the session moves on again": (
        *CLAUDE_CODE_COPY[:-1],
        "1b1b1b1b1b1b",
    ),
    "claude-code, once the session's hooks run a checkout": ("checkout",),
}
# The copy the session's hooks record from the server's second pass on, where the
# first copy it asked kept the server running.
HOOKS_MOVE_AGAIN = {
    "claude-code, once the session moves on again": (
        *CLAUDE_CODE_COPY[:-1],
        "2c2c2c2c2c2c",
    ),
}


@pytest.mark.parametrize("copy", COPIES)
def test_a_server_has_the_copy_its_session_runs_restart_it(
    claimed, tmp_path, monkeypatch, copy
):
    """A server follows the copy the session holding its page runs. Claude Code
    installs an update at a new path, which the session's hooks record once the
    session loads it. Codex replaces its installed copy by moving it aside and
    renaming another into its path, and Pi resets its clone in place and then
    removes the clone's environment. A server the old copy started has the new copy
    restart it once a pass finds it: it starts `server _follow` once, through the new
    copy's launcher, naming itself, tries again when that launch fails, and goes on
    serving until that restart stops it. Where that copy left it running, it asks
    again only once the session's hooks run yet another copy. The child's
    environment names no harness; it reads the session from the page's claim. A
    server whose session has ended retires after its grace instead, as
    does one from Claude Code's copy whose environment Claude Code deleted, one
    whose session's hooks run a checkout, and one a checkout started."""
    follows = copy in (
        "codex",
        "pi",
        "claude-code, once the session loads an update",
        "claude-code, once the session moves on again",
    )
    codex = COPIES[copy] == CODEX_COPY
    root = tmp_path.joinpath(*COPIES[copy])
    hooks = tmp_path.joinpath(*HOOKS_MOVE_TO.get(copy, COPIES[copy]))
    clone = COPIES[copy] != CLAUDE_CODE_COPY
    for directory in (".venv", ".git") if clone else (".venv",):
        (root / directory).mkdir(parents=True)
    serving(claimed, available_loopback_port(), "session")
    if copy == "codex, once the session ended":
        cleanup_model.end_harness_instance("s1")
    monkeypatch.setattr(cleanup_model, "PLUGIN_ROOT", root)
    attempts, replaced = [], []
    refusals = iter([StartRefused("the new copy could not build its environment")])
    passes = itertools.count()

    @contextlib.contextmanager
    def starting(arguments, *, harness, launcher, **_options):
        assert replaced, "the server followed before another copy stood at its path"
        assert server_model.running_server(claimed), "the server stopped first"
        attempts.append((arguments, harness, launcher))
        if refusal := next(refusals, None):
            raise refusal
        yield {}

    class Inline:
        """A thread that runs as it starts, so a pass that follows has followed by
        its end."""

        def __init__(self, *, target, args, daemon):
            self.start = lambda: target(*args)

    def next_pass(seconds):
        if not seconds:
            return  # the follow's pause before it tries again
        number = next(passes)
        if number == 0 and codex:
            root.rename(tmp_path / "replaced")
        elif number == 0 and copy in HOOKS_MOVE_TO:
            (hooks / "bin").mkdir(parents=True)
            (hooks / "bin" / "leaf").touch(mode=0o755)
            leases_model.mark_root("s1", hooks)
            replaced.append(copy)
        elif number == 0:
            (root / ".venv").rmdir()
            replaced.append(copy)
        elif number == 1 and codex:
            assert attempts == [], "the server followed while no copy stood there"
            (root / ".git").mkdir(parents=True)
            replaced.append(copy)
        elif number == 1 and copy in HOOKS_MOVE_AGAIN:
            again = tmp_path.joinpath(*HOOKS_MOVE_AGAIN[copy])
            (again / "bin").mkdir(parents=True)
            (again / "bin" / "leaf").touch(mode=0o755)
            leases_model.mark_root("s1", again)
        elif number == 3:
            service = server_model.read_service(claimed)
            assert service is not None
            server_model.write_service(claimed, {**service, "enabled": False})

    class Stopped(BaseException):
        pass

    def stopped(status):
        assert status == 0
        raise Stopped

    monkeypatch.setattr(lifetime_model, "starting_detached", starting)
    monkeypatch.setattr(codex_model, "retry_delay", lambda _failures: 0)
    monkeypatch.setattr(lifetime_model, "threading", SimpleNamespace(Thread=Inline))
    monkeypatch.setattr(
        lifetime_model, "time", SimpleNamespace(sleep=next_pass, monotonic=lambda: 0)
    )
    monkeypatch.setattr(lifetime_model, "exit_serving", stopped)
    with pytest.raises(Stopped):
        lifetime_model.stop_when_service_ends(claimed)
    if not follows:
        assert attempts == []
        return
    arguments = ["server", "_follow", str(claimed), "--server-id", "fixture-server"]
    launch = (arguments, None, (hooks / "bin" / "leaf").resolve())
    if copy in HOOKS_MOVE_AGAIN:
        again = tmp_path.joinpath(*HOOKS_MOVE_AGAIN[copy])
        assert attempts == [launch] * 2 + [
            (arguments, None, (again / "bin" / "leaf").resolve())
        ]
    else:
        assert attempts == [launch] * 2


def test_a_new_copy_restarts_only_the_server_that_asked(claimed, monkeypatch):
    """`server _follow` from the copy that replaced a server's own answers as soon
    as it runs, then restarts that server under itself, at its address and for the
    session holding the page (`vendoring.follow_copy`). A server another start put in
    its place, such as one a checkout started, keeps running, and so does one whose
    session has ended, which retires after its grace; neither is a failure of the
    follow."""
    serving(claimed, available_loopback_port(), "session")
    claim = service_model.page_claim(claimed)
    assert claim is not None
    holder = harness_model.claim_harness(claim)
    restarted, asking = [], {}

    @contextlib.contextmanager
    def restarting(page_dir, harness):
        heard, _, _ = select.select([asking["server"]], [], [], 0)
        assert heard, "the restart began before the server had its answer"
        restarted.append((page_dir, harness))
        yield

    monkeypatch.setattr(vendoring_model, "restarting_server", restarting)
    assert follow(claimed, "a-checkout-s-server", asking).exit_code == 0
    assert restarted == []
    assert follow(claimed, "fixture-server", asking).exit_code == 0
    assert restarted == [(claimed, holder)]
    cleanup_model.end_harness_instance("s1")
    assert follow(claimed, "fixture-server", asking).exit_code == 0
    assert restarted == [(claimed, holder)]


def follow(page_dir: Path, server_id: str, asking: dict):
    """Run `server _follow` for the server `server_id` names, as a server that
    accepts the answer as it hears it, which it keeps at `asking["server"]` while the
    command runs."""
    asking["server"], child = socket.socketpair()
    with asking["server"]:
        asking["server"].sendall(b"\n")
        return CliRunner().invoke(
            cli_model.cli,
            [
                *("server", "_follow", str(page_dir), "--server-id", server_id),
                *("--handshake", str(child.detach())),
            ],
        )


@pytest.mark.parametrize("hooks_run", ["this Leaf", "another Leaf"])
def test_a_new_copy_renews_a_page_left_at_an_older_protocol_first(
    claimed, monkeypatch, hooks_run
):
    """An update that moves the page protocol leaves the page at the old one, which
    the new copy can't serve. `server _follow` renews it first, for the session
    holding the page, as that session's next hook would, and queues what holds the
    renewal back for the session. The renewal restarts the server, so the follow
    finds another server in place of the one that asked and restarts nothing more.
    Where the session's hooks run another Leaf, the page stays at the protocol they
    read."""
    leases_model.mark_root(
        "s1",
        Path("/another/leaf")
        if hooks_run == "another Leaf"
        else cleanup_model.PLUGIN_ROOT,
    )
    serving(claimed, available_loopback_port(), "session")
    claim = service_model.page_claim(claimed)
    assert claim is not None
    held_back = Finding(
        "unready-reinit", values={"page": str(claimed), "errors": ["not activated"]}
    )
    renewals = []

    def renew(page_dir, harness, still):
        assert still(), "the server that asked is the one serving the page"
        renewals.append((page_dir, harness))
        service = server_model.read_service(page_dir)
        assert service is not None
        server_model.write_service(page_dir, {**service, "server_id": "renewed"})
        return held_back

    restarted = []

    @contextlib.contextmanager
    def restarting(page_dir, harness):
        restarted.append(page_dir)
        yield

    monkeypatch.setattr(vendoring_model, "renew_layer", renew)
    monkeypatch.setattr(vendoring_model, "restarting_server", restarting)
    assert follow(claimed, "fixture-server", {}).exit_code == 0
    if hooks_run == "another Leaf":
        assert renewals == []
        assert clerk_model.waking("s1") == []
        return
    assert renewals == [(claimed, harness_model.claim_harness(claim))]
    assert restarted == [], "the follow restarted the renewed server again"
    assert clerk_model.waking("s1") == [str(held_back)]


def test_a_stale_follow_leaves_the_server_that_took_its_place(page_dir, monkeypatch):
    """A server can ask the new copy to follow it, and another start can put its own
    server in place on the page before the follow runs. Where the page is at an
    older page protocol, the follow's renewal restarts the page's server, so it
    asks, under the renewal's locks, whether the server in place is still the one
    that asked, and renews and restarts nothing where another took its place: that
    server keeps running, as it does on a page that needs no renewal."""
    serving(page_dir, available_loopback_port(), "session")
    vendored_at_another_protocol(page_dir)
    restarted = []

    @contextlib.contextmanager
    def restarting(directory, harness):
        restarted.append(directory)
        yield

    monkeypatch.setattr(vendoring_model, "restarting_server", restarting)
    follow(page_dir, "the-server-that-asked", {})
    assert restarted == [], "the stale follow restarted the server in its place"
    service = server_model.read_service(page_dir)
    assert service is not None
    assert service["enabled"] and service["server_id"] == "fixture-server"


def test_server_maintenance_needs_no_native_subscription(page_dir, monkeypatch):
    """Retained servers publish rows and retire without spending native watchers.

    Advance maintenance after a log append and then a service withdrawal. Both
    loops must still read the files and act on the next look.
    """
    from leaf.base import rows
    from leaf.log import file_changes
    from leaf.serving import server_rows

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
        record = rows.ROW.read(publisher.path)
        assert record is not None
        row = record["row"]
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
        assert service is not None
        server_model.write_service(page_dir, {**service, "enabled": False})

    def exited(status):
        assert status == 0
        raise Finished

    monkeypatch.setattr(lifetime_model, "time", SimpleNamespace(sleep=stop_after_check))
    monkeypatch.setattr(lifetime_model, "exit_serving", exited)
    with pytest.raises(Finished):
        lifetime_model.stop_when_service_ends(page_dir)


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
    hooks_run_this_tree("nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert transaction_model.claim_page(page_dir)
    claim_record = service_model.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["pid"] == os.getpid()
    value_2 = service_model.page_claim(page_dir)
    assert value_2 is not None
    assert "job" not in value_2

    (job / "state.json").unlink()
    with pytest.raises(Refused, match="names no job record"):
        transaction_model.claim_page(page_dir)


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
    hooks_run_this_tree("nested")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    for host in ("local_one", "local_unrecorded"):
        monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", host)
        harness_3 = harness_model.session_harness()
        assert harness_3 is not None
        assert harness_3.lifetime() == {"pid": os.getpid()}


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
    assert not server_model.SERVICE.file(page_dir / "service.json").exists()
    assert service_model.page_claim(page_dir) is None

    process.send_signal(signal.SIGINT)
    output, error = process.communicate(timeout=STATED_TIMEOUT)
    assert process.returncode == 1, error
    assert json.loads(output)["error"] == "interrupted"


# The refusal Codex's macOS sandbox makes of a listing of every process, with the
# same error psutil raises there.
PROCESS_LISTING_REFUSED = (
    '(version 1)(allow default)(deny sysctl-read (sysctl-name "kern.proc.all"))'
)


def test_server_run_persistent_refuses_to_adopt_a_session_server(page_dir):
    """A stated lifetime contradicted by the running server is refused with the
    way out named, exactly as a stated `--host` is — not silently ignored."""
    serving(page_dir, 1, "session")
    result = CliRunner().invoke(
        cli_model.cli, ["server", "run", "--lifetime", "persistent", str(page_dir)]
    )
    assert result.exit_code != 0
    assert "server stop" in result.output


# A server a Leaf of another `SERVICE` shape started: it holds the serving lease
# and exits once its record, in that shape's file, is gone, as
# `server_lifetime.stop_when_service_ends` does.
OLDER_SERVER = """
import sys, time
from pathlib import Path
from leaf.base.leases import take_lease
page, record = Path(sys.argv[1]), Path(sys.argv[2])
lease = take_lease(page / "server.lock")
print("held" if lease else "refused", flush=True)
while record.exists():
    time.sleep(0.02)
"""


def older_service(page_dir):
    """Where a Leaf of another `SERVICE` shape keeps the page's service record."""
    return page_dir / "service@0.json"


def older_server(page_dir, spawn):
    """A persistent serve a Leaf of another `SERVICE` shape started: its record in
    that shape's file, and a process holding the lease over it."""
    cleanup_model.write_json(
        older_service(page_dir),
        {
            "format": "leaf-service/0",
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": 1,
            "enabled": True,
            "lifetime": "standing",
        },
    )
    process = spawn(
        [
            sys.executable,
            "-c",
            OLDER_SERVER,
            str(page_dir),
            str(older_service(page_dir)),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout.readline().strip() == "held"
    return process


def test_a_service_record_this_version_cannot_read_is_no_service(page_dir, spawn):
    """A Leaf of another `SERVICE` shape keeps its serve's record in that shape's
    file, which this version reads as no service, so a persistent start is not
    refused as a session server. An explicit stop removes that record, which is what
    ends a server the other Leaf runs over it, and reports it stopped: whether a
    server ran is the lease's to say, not the record's."""
    process = older_server(page_dir, spawn)
    assert server_model.read_service(page_dir) is None
    assert server_model.running_server(page_dir) is None
    assert hosting_model._reuse_server(page_dir, None, persistent=True) is None
    # A start can reach that server neither to reuse it nor to stop it, so it names
    # the stop that can.
    with pytest.raises(Refused) as refused:
        hosting_model._take_server_lease(page_dir)
    assert f"run `leaf server stop {page_dir}`, then `leaf server start" in str(
        refused.value
    )

    assert hosting_model.cmd_stop(page_dir) is True
    assert not older_service(page_dir).exists()
    assert process.wait(timeout=STATED_TIMEOUT) == 0
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_a_stop_ends_another_shapes_server_beside_this_shapes_record(page_dir, spawn):
    """A page this Leaf served before a Leaf of another `SERVICE` shape served it
    keeps both records, and the server running is that Leaf's. A stop removes that
    record too, which ends its server, and returns once the lease is free, rather
    than disabling only its own record and waiting on a server that never exits."""
    fixture_service(page_dir, available_loopback_port(), "persistent")
    process = older_server(page_dir, spawn)
    own = server_model.read_service(page_dir)
    assert own is not None and own["enabled"]

    assert hosting_model.cmd_stop(page_dir) is True
    assert not older_service(page_dir).exists()
    assert process.wait(timeout=STATED_TIMEOUT) == 0
    assert not leases_model.lock_is_held(page_dir / "server.lock")


def test_a_re_vendor_stops_a_server_whose_record_it_cannot_read(
    page_dir, spawn, capsys
):
    """`page init` re-vendors with no server running, since the layer a server serves
    is what the re-vendor replaces. A server a Leaf of another `SERVICE` shape
    runs over its own record is still running, so the re-vendor stops it first, and
    it stays stopped: there is no lifetime this version could bring it back
    under."""
    process = older_server(page_dir, spawn)
    with hosting_model.restarting_server(page_dir, harness_model.session_harness()):
        assert not leases_model.lock_is_held(page_dir / "server.lock")
    assert process.wait(timeout=STATED_TIMEOUT) == 0
    assert not older_service(page_dir).exists()
    assert "stays stopped" in capsys.readouterr().err
