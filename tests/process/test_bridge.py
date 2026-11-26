"""Claude Code's sandboxed commands, run outside its sandbox by Leaf's bridge."""

import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest
from conftest import hooks_run_this_tree
from interact_support import ROOT, STATED_TIMEOUT

from leaf.base import bridge as bridge_model
from leaf.base import service as service_model
from leaf.base import state as state_model
from leaf.commands import hooks as hooks_model

LAUNCHER = str(ROOT / "bin" / "leaf")


def before_leaf_command(monkeypatch, session: str) -> None:
    """Run Claude Code's hook before a `leaf` command in `session`."""
    payload = {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "tool_name": "Bash",
        "tool_input": {"command": "leaf page claim page"},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    hooks_model.main("claude-code")


@pytest.fixture
def bridged(monkeypatch):
    """A Claude Code session whose hook before a `leaf` command ran and whose
    shell is sandboxed."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bridged")
    hooks_run_this_tree("bridged")
    before_leaf_command(monkeypatch, "bridged")
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    # The bridge is reached directly here, not through a proxy the host may name.
    for name in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox")
@pytest.mark.usefixtures("bridged")
def test_a_sandboxed_command_runs_outside_the_sandbox(page_dir):
    """Claude Code's sandbox refuses a command the state home, where a claim is
    written. The launcher hands the command to the bridge the hook left
    running outside it, so the claim takes. This sandbox lets a command reach
    127.0.0.1 directly, as Claude Code's does through its proxy."""
    state = os.path.realpath(os.environ["XDG_STATE_HOME"])
    profile = f'(version 1)(allow default)(deny file-write* (subpath "{state}"))'
    claimed = subprocess.run(
        ["sandbox-exec", "-p", profile, LAUNCHER, "page", "claim", str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    claim_record = service_model.page_claim(page_dir)
    assert claim_record is not None
    assert claim_record["id"] == "bridged"


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_keeps_its_stdin_streams_and_status(page_dir):
    """The command reads the stdin it was given, and its stdout, stderr and exit
    status come back apart. A hook leaves stdout to its harness's answer, so it
    refuses on stderr."""
    refused = subprocess.run(
        [LAUNCHER, "hook", "--harness", "claude-code"],
        input="{",
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode == 1
    assert refused.stdout == ""
    assert "Expecting property name" in json.loads(refused.stderr)["error"]


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_ends_though_its_stdin_never_does(spawn):
    """A harness may hand a command a stdin that never ends, and a command that
    never reads it still finishes."""
    held = spawn(
        [LAUNCHER, "--version"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert held.wait(timeout=STATED_TIMEOUT) == 0
    assert held.stdout.read().startswith("leaf ")


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_refuses_a_socket_stdin_at_once(page_dir):
    """Claude Code hands a command spanning lines a socket as its stdin that never
    closes. A bridged command given no JSON gets an empty pipe in its place, and
    refuses at once rather than waiting for the socket to end."""
    held, caller = socket.socketpair()
    with held, caller:
        refused = subprocess.run(
            [LAUNCHER, "data", "set", str(page_dir), "source"],
            stdin=held.fileno(),
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
    assert refused.returncode == 1
    assert "no JSON given" in refused.stdout


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_reads_a_socket_stdin_it_names(page_dir):
    """A command that names stdin itself (`--file -`) reads it through the bridge
    even from a socket, as a Node caller's piped stdin is."""
    held, caller = socket.socketpair()
    with held, caller:
        caller.sendall(b"{")
        caller.shutdown(socket.SHUT_WR)
        read = subprocess.run(
            [LAUNCHER, "data", "set", str(page_dir), "source", "--file", "-"],
            stdin=held.fileno(),
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
    assert read.returncode == 1
    assert "invalid JSON (Expecting property name" in read.stdout


def test_a_background_job_keeps_the_bridge_while_the_job_stands(
    tmp_path, monkeypatch, dead_pid
):
    """A background job's next sitting runs on a fresh worker and may run `leaf`
    from a script, before which no hook runs, so the bridge serves the job for its
    lifetime rather than the worker's, and lets it go once the job is deleted."""
    job = tmp_path / "job"
    job.mkdir()
    (job / "state.json").write_text('{"sessionId": "bg-job"}')
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "bg-job")
    hooks_run_this_tree("bg-job")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    before_leaf_command(monkeypatch, "bg-job")
    assert bridge_model.live_sessions()
    (job / "state.json").unlink()
    assert not bridge_model.live_sessions()


@pytest.mark.parametrize(
    "ending", ["live", "a later kind", "record ends", "session ends"]
)
def test_the_bridge_lets_a_session_go_once_it_ends(ending):
    """A registered session keeps the bridge until it ends: until its record says
    so, or until its end retires its files, record and registration among them. So
    the bridge can retire and free its port. A registration's lifetime of a kind this
    Leaf can't check, as a later Leaf sharing this bridge may register, keeps it
    too, since the registration's shape doesn't name its lifetime's keys."""
    lifetime = {"window": "w-1"} if ending == "a later kind" else {"pid": os.getpid()}
    registration = state_model.session_file("later", f"{bridge_model.KEY}-1.bridge")
    bridge_model.REGISTRATION.write(registration, {"id": "later", **lifetime})
    if ending != "a later kind":
        started = state_model.new_session("later", lifetime)
        if ending == "record ends":
            started["ended"] = state_model.now_iso()
        state_model.SESSION.write(
            state_model.session_file("later", state_model.SESSION_SUFFIX),
            {**started, "revision": 1},
        )
    if ending == "session ends":
        state_model.end_session("later")
    live = ending in {"live", "a later kind"}
    assert bridge_model.live_sessions() is live
    assert bridge_model.REGISTRATION.file(registration).exists() is live


def test_every_copy_that_ships_this_bridge_reaches_the_same_one(tmp_path):
    """Claude Code installs each plugin update as a new copy, and a running session
    keeps the copy it loaded, so a bridge keyed by its copy would start again with
    every update and serve each session for its whole lifetime. A copy elsewhere
    with this `bridge.py` addresses this checkout's bridge."""
    copy = tmp_path / "copy" / "leaf" / "base"
    copy.mkdir(parents=True)
    shutil.copy(bridge_model.__file__, copy / "bridge.py")
    # The copy's own `bridge.py`, beside this checkout's other modules.
    for package in (copy.parent, copy):
        checkout = ROOT / "src" / package.relative_to(copy.parent.parent)
        (package / "__init__.py").write_text(f"__path__.append({str(checkout)!r})\n")
    addressed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import leaf.base.bridge as b; print(b.__file__, b.KEY)",
        ],
        cwd=copy.parent.parent,
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert addressed.returncode == 0, addressed.stderr
    assert addressed.stdout == f"{copy / 'bridge.py'} {bridge_model.KEY}\n"


@pytest.mark.usefixtures("bridged")
def test_a_bridged_command_runs_on_the_interpreter_of_the_copy_that_sent_it(
    tmp_path, monkeypatch, capfd
):
    """Every copy that ships the same bridge reaches one bridge, the newer copy a
    plugin update installs and a checkout run by path alike, and each command
    runs as the Leaf of the copy whose client sent it."""
    interpreter = tmp_path / "python"
    interpreter.write_text('#!/bin/sh\necho "$0 $*"\nexit 3\n')
    interpreter.chmod(0o755)
    monkeypatch.setattr("sys.executable", str(interpreter))
    assert bridge_model.run(["--version"]) == 3
    assert capfd.readouterr().out == f"{interpreter} -I -m leaf --version\n"


def test_a_bridged_command_waits_for_a_slow_bridge_while_it_holds_the_lease(
    tmp_path, monkeypatch, capfd
):
    """The hook returns once it has started the bridge, which on a loaded machine
    may take longer to publish its address than any count of polls allows. The
    client waits while the bridge holds its lease, so the command runs.

    The bridge starts only once the client has polled past the old budget of
    `REFUSALS` polls, so the order holds however the processes are scheduled."""
    for name in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    python = sys.executable
    release = tmp_path / "release"
    # A bridge never released gives up after the suite's deadline, which drops
    # its lease, so the client fails rather than waiting forever.
    held_python = tmp_path / "python"
    held_python.write_text(
        "#!/bin/sh\n"
        f"deadline=$(( $(date +%s) + {STATED_TIMEOUT} ))\n"
        f'while [ ! -e "{release}" ]; do\n'
        '  [ "$(date +%s)" -lt "$deadline" ] || { echo never released >&2; exit 1; }\n'
        "  sleep 0.01\n"
        "done\n"
        f'exec "{python}" "$@"\n'
    )
    held_python.chmod(0o755)
    monkeypatch.setattr("sys.executable", str(held_python))
    bridge_model.ensure("slow", {"pid": os.getpid()})
    monkeypatch.setattr("sys.executable", python)
    monkeypatch.setattr(bridge_model, "POLL_SECONDS", 0.001)
    polls = 0
    released_at = None
    held = bridge_model.lock_is_held

    def counting(path):
        nonlocal polls, released_at
        polls += 1
        if released_at is None and polls > bridge_model.REFUSALS:
            release.touch()
            released_at = time.monotonic()
        if released_at is not None and time.monotonic() - released_at > STATED_TIMEOUT:
            message = "the released bridge never published its address"
            raise AssertionError(message)
        return held(path)

    monkeypatch.setattr(bridge_model, "lock_is_held", counting)
    assert bridge_model.run(["--version"]) == 0, capfd.readouterr().err
    assert released_at is not None
    assert capfd.readouterr().out


@pytest.mark.parametrize("published", ["absent", "closed", "occupied"])
def test_a_bridged_command_fails_at_once_where_no_bridge_runs(
    monkeypatch, capfd, published
):
    """With no bridge holding the lease, an address absent or left by a bridge
    since gone gets no answer however long the client waits, so it says at once
    that no bridge runs rather than blaming the sandbox's network rule. It never
    contacts a gone bridge's address, whose port another listener may now hold
    without answering."""
    for name in ("HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    bridge_model.bridge_path("json").parent.mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        listener = stack.enter_context(socket.socket())
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        contacted = threading.Event()
        if published == "occupied":
            listener.listen()

            def answer_nothing() -> None:
                # A client that sent its request gets the connection closed
                # unanswered, so a regression fails here rather than hanging.
                with contextlib.suppress(OSError):
                    connection, _ = listener.accept()
                    contacted.set()
                    connection.close()

            threading.Thread(target=answer_nothing, daemon=True).start()
        else:
            listener.close()
        if published != "absent":
            bridge_model.ADDRESS.write(
                bridge_model.bridge_path("json"),
                {"port": port, "token": "t", "pid": 1},
            )
        monkeypatch.setattr(bridge_model, "POLL_SECONDS", STATED_TIMEOUT)
        assert bridge_model.run(["--version"]) == 1
        assert not contacted.is_set()
    error = capfd.readouterr().err
    assert "no Leaf bridge is running" in error
    assert "127.0.0.1" not in error


def test_a_session_registered_as_the_bridge_retires_keeps_its_lease_held(
    monkeypatch,
):
    """A hook that finds the bridge's lease held returns, and its session's client
    then asks whether a bridge runs. Where the hook registered just after the
    bridge's sweep found no session left, the bridge goes on serving with its lease
    held, so that client is never told no bridge runs while this one serves it.
    Once the session ends, the bridge releases its lease."""
    from leaf.base.leases import take_lease

    bridge_model.bridge_path("lock").parent.mkdir(parents=True)
    lock = bridge_model.bridge_path("lock")
    lease = take_lease(lock)
    assert lease is not None
    monkeypatch.setattr(bridge_model, "SWEEP_SECONDS", 0)
    sweep = bridge_model.live_sessions
    release = bridge_model.release_lease
    sweeps = 0
    released = False

    def sweep_then_register() -> bool:
        nonlocal sweeps
        sweeps += 1
        if sweeps == 1:
            # The sweep finds no session; a hook registers before the bridge acts.
            assert not sweep()
            bridge_model.ensure("late", {"pid": os.getpid()})
            assert bridge_model.lock_is_held(lock)
            return False
        if sweeps == 3:
            # The late session ends, so the bridge may retire.
            state_model.end_session("late")
        return sweep()

    def release_unserved(held) -> None:
        nonlocal released
        assert not sweep(), "the lease was released while a session it serves lives"
        released = True
        release(held)

    monkeypatch.setattr(bridge_model, "live_sessions", sweep_then_register)
    monkeypatch.setattr(bridge_model, "release_lease", release_unserved)
    bridge_model.retire(lease, set())
    assert released
    assert not bridge_model.lock_is_held(lock)


@pytest.mark.parametrize("cause", ["state home removed", "sweep raises"])
def test_a_bridge_ends_once_its_sweep_cannot_retire_it(tmp_path, monkeypatch, cause):
    """An eval removes a sample's scratch state home, with the bridge's lease and
    registrations in it, once the sample's session ends, so no hook or client can
    find that bridge again. A sweep that raises, as a bug can make it, can no
    longer retire the bridge. Either way the bridge ends rather than serving for
    good, though a session registered with it still lives, and a removed state
    home stays removed."""
    from leaf.base.leases import take_lease

    bridge_model.bridge_path("lock").parent.mkdir(parents=True)
    lease = take_lease(bridge_model.bridge_path("lock"))
    assert lease is not None
    bridge_model.ensure("evaluated", {"pid": os.getpid()})
    monkeypatch.setattr(bridge_model, "SWEEP_SECONDS", 0)
    home = state_model.state_home()
    sweep = bridge_model.live_sessions

    def sweeping() -> bool:
        if cause == "sweep raises":
            raise RuntimeError("the sweep broke")
        alive = sweep()
        # The eval removes the state home between two sweeps.
        if home.exists():
            home.rename(tmp_path / "removed")
        return alive

    monkeypatch.setattr(bridge_model, "live_sessions", sweeping)
    ended = threading.Event()

    def serve() -> None:
        with contextlib.suppress(RuntimeError):
            bridge_model.serve(os.dup(lease.fileno()))
        ended.set()

    threading.Thread(target=serve, daemon=True).start()
    # The bridge's address names this process, which the test's teardown would
    # end for a bridge that still holds its lease.
    try:
        assert ended.wait(STATED_TIMEOUT), (
            "the bridge serves on with no sweep to end it"
        )
    finally:
        bridge_model.release_lease(lease)
    if cause == "state home removed":
        assert not home.exists(), "the bridge made its removed state home again"


def test_a_bridge_whose_lease_file_was_replaced_as_it_started_leaves_the_next(
    tmp_path,
):
    """The state home can be removed while a bridge starts, and a hook in the home
    made again then starts the next bridge on a new lease file. Once the first
    bridge has loaded, it leaves the next one's address standing and ends."""
    from leaf.base.leases import take_lease

    lock = bridge_model.bridge_path("lock")
    lock.parent.mkdir(parents=True)
    first = take_lease(lock)
    assert first is not None
    lock.rename(tmp_path / "removed.lock")
    second = take_lease(lock)
    assert second is not None
    address = {"port": 1, "token": "t", "pid": 1}
    bridge_model.ADDRESS.write(bridge_model.bridge_path("json"), address)
    # An address the first bridge wrote would name this process, which the
    # test's teardown ends for a bridge that still holds its lease.
    try:
        bridge_model.serve(os.dup(first.fileno()))
        assert bridge_model.ADDRESS.read(bridge_model.bridge_path("json")) == address
    finally:
        first.close()
        bridge_model.release_lease(second)


def test_a_hook_that_finds_a_new_bridge_starting_gets_no_gone_bridges_address(
    monkeypatch,
):
    """A gone bridge left its address, and a hook takes the lease to start the
    next bridge. A second hook that registers as soon as the first lets the
    registrations' lock go finds the lease held and returns, so its client may
    read the address at once; it finds none, rather than the gone bridge's, whose
    port another listener may now hold."""
    bridge_model.bridge_path("json").parent.mkdir(parents=True, exist_ok=True)
    bridge_model.ADDRESS.write(
        bridge_model.bridge_path("json"), {"port": 1, "token": "t", "pid": 1}
    )
    sessions_lock = bridge_model.bridge_path("sessions.lock")
    locked = bridge_model.flocked
    seen = []

    @contextlib.contextmanager
    def then_second_hook(path, **kwargs):
        with locked(path, **kwargs):
            yield
        if path == sessions_lock and not seen:
            seen.append(None)
            bridge_model.ensure("second", {"pid": os.getpid()})
            # The second hook's client asks whether a bridge runs, then reads
            # its address.
            assert bridge_model.lock_is_held(bridge_model.bridge_path("lock"))
            seen[0] = bridge_model.ADDRESS.read(bridge_model.bridge_path("json"))

    monkeypatch.setattr(bridge_model, "flocked", then_second_hook)
    monkeypatch.setattr(bridge_model.subprocess, "Popen", lambda *a, **k: None)
    bridge_model.ensure("first", {"pid": os.getpid()})
    assert seen == [None]


def test_each_process_of_a_session_keeps_the_bridge(dead_pid):
    """Two processes can carry one session's id, as a session resumed while it
    still runs elsewhere does, and each lives as its own pid. The one that ends
    leaves the bridge to the one still running."""
    bridge_model.ensure("resumed", {"pid": os.getpid()})
    bridge_model.ensure("resumed", {"pid": dead_pid})
    assert bridge_model.live_sessions()


def test_a_session_that_runs_no_leaf_command_starts_no_bridge():
    """Claude Code runs Leaf's start and prompt hooks in every session, and only
    the hook before a `leaf` command starts the bridge, so a session that never
    uses Leaf keeps no process of Leaf's running."""
    for payload in (
        {"hook_event_name": "SessionStart", "source": "resume"},
        {"hook_event_name": "UserPromptSubmit", "turn_id": "t1", "prompt": "hi"},
    ):
        hooks_model.cmd_hook("claude-code", {"session_id": "unbridged", **payload})
    assert not bridge_model.bridge_path("lock").exists()


@pytest.mark.parametrize(
    "argv",
    [["--help"], ["--version"], ["--root", "--", "x"]],
)
def test_the_bridge_client_forwards_leaf_arguments_verbatim(monkeypatch, argv):
    """`bin/leaf` hands a sandboxed command's whole argv to the bridge client,
    which passes every argument after its mode to Leaf unparsed, `--` included."""
    received = []
    monkeypatch.setattr(bridge_model, "run", lambda args: received.append(args) or 7)
    monkeypatch.setattr("sys.argv", ["bridge.py", "run", *argv])
    with pytest.raises(SystemExit) as exited:
        bridge_model.main()
    assert exited.value.code == 7
    assert received == [argv]
