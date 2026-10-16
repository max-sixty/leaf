"""Page claims: which session and harness hold a page, what a claim records, when it
is active, and the leases and page locks that keep a wait and a claim exclusive."""

import fcntl
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from click.testing import CliRunner
from conftest import HOOKED_SESSIONS, LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    claim_and_wait_command,
    lock_contention,
    page_state,
    record_claim,
    release_codex_command,
    serving,
    spawn_probe,
    wait_for,
    woken,
)
from leaf import cli as cli_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import machine as machine_model
from leaf import presence as presence_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import vendoring as vendoring_model


def test_a_codex_command_claims_the_page_for_its_thread(codex_claimed_page):
    session = service_model.page_claim(codex_claimed_page)
    assert session["id"] == "codex-thread"
    assert session["agent"] == "Codex"
    assert session["harness"] == "codex"
    assert set(session) == {
        "page",
        "id",
        "agent",
        "harness",
        "pid",
        "cwd",
        "ts",
        "turn",
        "turn_opened",
        "turn_closed",
        "generation",
        "acquisition",
    }
    assert page_state(codex_claimed_page)["agent"] == "Codex"


def test_a_codex_claim_records_the_session_not_the_shell_it_ran_through(
    tmp_path, under_codex, codex_env
):
    """The claim's pid is the one two reapers read as the session's life, and
    `$PPID` is not it: it is a fact about the shape of the command. Measured
    through `codex exec`, a bare command and an `&&` chain reported the codex
    process because the wrapping shell exec'd leaf in place, and a pipeline
        reported that shell — which exits with the command, so ownership would go
        inactive and its server would stop a second later. Here the
    shell is between the session and the command and has exited by the time this
    reads what was written, so a pid it could have recorded is one this cannot
    match."""
    page = tmp_path / "codex-page"
    env = codex_env | {"CODEX_THREAD_ID": "thread-shape"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    session = under_codex(claim_and_wait_command(page), env)
    assert session.wait(timeout=STATED_TIMEOUT) == 0
    assert service_model.page_claim(page)["pid"] == session.pid


def test_the_nearest_harness_runs_a_command_that_inherits_another(under_codex):
    """A command inherits the identity of every harness above it: Codex run from a
    Claude Code shell states both sessions, as this suite's Claude Code identity
    reaches the Codex it starts. The harness whose process is nearest above the
    command is the one running it, so a Codex task's command is Codex's; with no
    codex above it, the same environment is Claude Code's."""
    probe = (
        "from leaf.harness import session_harness; h = session_harness(); "
        "print(type(h).__name__, h.session)"
    )
    env = os.environ | {"CODEX_THREAD_ID": "inner-codex"}
    ran = under_codex(
        shlex.join([sys.executable, "-c", probe]),
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.split() == ["CodexHarness", "inner-codex"]

    # Claude Code run from that Codex task's shell: the shell is its harness.
    inner = shlex.join([sys.executable, "-c", probe])
    ran = under_codex(
        f"CLAUDE_CODE_SESSION_ID=inner-claude CLAUDE_PID=$$ {inner}",
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.split() == ["ClaudeCodeHarness", "inner-claude"]

    # With no codex above it, the same environment is Claude Code's, and a
    # process the Codex task detaches inherits only the identity chosen there.
    nearer = subprocess.run(
        [sys.executable, "-c", probe],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert nearer.returncode == 0, nearer.stderr
    assert nearer.stdout.split() == ["ClaudeCodeHarness", f"pytest-{os.getpid()}"]
    detached = (
        "from leaf.harness import detached_environment as d, session_harness; "
        "print(sorted(set(d(session_harness())) & "
        "{'CODEX_THREAD_ID', 'CLAUDE_CODE_SESSION_ID'}))"
    )
    ran = under_codex(
        shlex.join([sys.executable, "-c", detached]),
        env,
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = ran.communicate(timeout=STATED_TIMEOUT)
    assert ran.returncode == 0
    assert out.strip() == "['CODEX_THREAD_ID']"


def test_a_codex_session_id_with_no_codex_above_it_is_refused(page_dir, monkeypatch):
    """A hand-built environment: CODEX_THREAD_ID states a Codex session and
    nothing running Codex is above this process, so there is no process whose
    life is that session's. Nothing to fall back on either — a pid guessed here
    is a claim that expires by itself, and every state that follows from one is
    silent, so the refusal names what it walked."""
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-nobody")
    monkeypatch.setattr(machine_model, "process_info", lambda _pid: (1, "python"))
    refused = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert refused.exit_code == 1, refused.output
    assert "no codex process runs above this one" in refused.output
    assert service_model.page_claim(page_dir) is None


def test_a_claim_records_where_the_session_is_working(page_dir, tmp_path, monkeypatch):
    """What tells one leaf from another on the drawer is the work behind it, which
    neither the title somebody wrote nor the state directory nobody chose says — so
    the claim records the directory the claiming command ran in, the same reading
    `layer_dirs` already takes cwd to be. Every seat gets it through `presence`, and a
    page nothing ever claimed says so rather than borrowing a path from somewhere."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    work = tmp_path / "api"
    work.mkdir()
    monkeypatch.chdir(work)
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["cwd"] == str(work)
    assert presence_model.presence(page_dir, [])["session_cwd"] == str(work)
    # Diagnostic joins survive replacement/ending of the live claim and lifecycle.
    from leaf.event_log import read_events
    from leaf.interaction_log import read_interactions
    from leaf.todos import take_in_hand

    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "input", "author": "user", "text": "why?"}
    )
    with service_model.PageTransaction(page_dir) as page:
        started = take_in_hand(
            page, "input", "Reading it", {"session": "s1", "agent": "Claude"}
        )
    context = next(
        row
        for row in read_interactions(page_dir)
        if row.get("event", {}).get("id") == started["id"]
    )
    assert context["context"] == {
        "harness": "claude-code",
        "turn": started["turn"],
        "provider": False,
        "cwd": str(work),
        "transcript_path": None,
    }
    assert "context" not in started
    assert all("context" not in event for event in read_events(page_dir))
    cleanup_model.end_session("s1")
    assert presence_model.presence(page_dir, [])["session_cwd"] == str(work)
    assert presence_model.presence(page_dir, [])["session_alive"] is False
    assert context in read_interactions(page_dir, types=("event",))


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox")
def test_a_session_whose_shell_is_sandboxed_claims_its_page(page_dir, monkeypatch):
    """Claude Code's and Codex's macOS sandboxes refuse their commands any signal
    to a process outside the sandbox, the session's own included, so signal 0 to
    CLAUDE_PID meets EPERM there as it does for another user's process. The claim
    still takes, since the session is this user's; a pid of another user's still
    reads as gone."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sandboxed")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    signals_stay_inside = (
        "(version 1)(allow default)(deny signal)(allow signal (target same-sandbox))"
    )
    claimed = subprocess.run(
        ["sandbox-exec", "-p", signals_stay_inside, *LEAF_COMMAND]
        + ["page", "claim", str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert claimed.returncode == 0, claimed.stderr
    assert service_model.page_claim(page_dir)["id"] == "sandboxed"
    assert not machine_model.pid_alive(1)


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox")
@pytest.mark.parametrize(
    ("refused", "command"),
    [
        ('(deny file-write* (subpath "{state}"))', ["page", "claim"]),
        ("(deny network-bind)", ["server", "start"]),
    ],
)
def test_a_sandbox_refusal_says_to_run_outside_it(
    page_dir, monkeypatch, refused, command
):
    """Claude Code's sandbox lets a command write only its working directory and
    temporary files, not Leaf's state home, which a claim writes, and bind no port
    unless the user allows it. Each refusal says so in one line naming the sandbox
    and what to do, whether the command or the server it starts meets it, rather
    than a traceback or an OS error the agent would read as the host's."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "confined")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    state = os.path.realpath(os.environ["XDG_STATE_HOME"])
    profile = f"(version 1)(allow default){refused.format(state=state)}"
    done = subprocess.run(
        ["sandbox-exec", "-p", profile, *LEAF_COMMAND, *command, str(page_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert "[Errno 1] Operation not permitted" in done.stderr
    assert "(SANDBOX_RUNTIME=1), so rerun it outside the sandbox" in done.stderr
    assert "Traceback" not in done.stderr


def test_a_sandbox_that_hides_the_session_says_to_claim_outside_it(
    page_dir, monkeypatch
):
    """Claude Code's Linux sandbox runs each command in a process namespace of its
    own, so CLAUDE_PID names no process the command can see, and the claim cannot
    take there at all. The refusal says so where the harness declares its sandbox,
    since the agent's fix is to rerun the command outside it."""
    gone = subprocess.Popen(["true"])
    gone.wait()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "namespaced")
    monkeypatch.setenv("CLAUDE_PID", str(gone.pid))
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    refused = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert refused.exit_code == 1, refused.output
    assert "SANDBOX_RUNTIME=1" in refused.output
    assert "outside the sandbox" in refused.output
    assert service_model.page_claim(page_dir) is None


def test_a_page_calls_its_agent_by_its_claimant_or_last_voice(page_dir, monkeypatch):
    """The page's agent has one name, which every label naming the agent's side reads
    (`presence.page_agent`): its claimant's, else the voice that last wrote on it, else
    the unnamed agent's."""
    voiced = [
        {"seq": 1, "kind": "comment", "author": "agent", "agent": "Codex"},
        {"seq": 2, "kind": "reply", "author": "user"},
        {"seq": 3, "kind": "reply", "author": "agent", "agent": "Claude"},
        {"seq": 4, "kind": "reply", "author": "agent"},
    ]
    assert presence_model.presence(page_dir, [])["agent"] == "Agent"
    assert presence_model.presence(page_dir, voiced)["agent"] == "Claude"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    claimant = service_model.page_claim(page_dir)["agent"]
    assert presence_model.presence(page_dir, voiced[:1])["agent"] == claimant


def test_reinitializing_a_deleted_page_path_drops_its_old_claim(page_dir, monkeypatch):
    """A regenerated page is not the deleted page that occupied its path."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "old-session")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)

    shutil.rmtree(page_dir)
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert initialized.exit_code == 0, initialized.output

    assert service_model.page_claim(page_dir) is None
    assert service_model.owned_pages("old-session") == []


def test_a_fresh_init_does_not_delete_a_concurrently_created_pages_claim(
    tmp_path, monkeypatch, spawn
):
    """The first page creation is one serialized transition."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "concurrent-page"
    reached_layer = threading.Event()
    resume = threading.Event()
    original_composed_sheets = layer_model.composed_sheets

    def held_composed_sheets(sources):
        reached_layer.set()
        assert resume.wait(timeout=STATED_TIMEOUT), (
            "the concurrent init never released its peer"
        )
        return original_composed_sheets(sources)

    monkeypatch.setattr(layer_model, "composed_sheets", held_composed_sheets)
    executor = ThreadPoolExecutor(max_workers=1)
    first = executor.submit(vendoring_model.cmd_init, page)
    try:
        assert reached_layer.wait(timeout=STATED_TIMEOUT), (
            "the first init never reached its held read"
        )
        requested = tmp_path / "second-init-requested"
        second = spawn_probe(
            spawn,
            page,
            """\
import fcntl
native_flock = fcntl.flock
identity = Path(os.environ["PAGE"]).stat()
def observed_flock(fd, operation):
    descriptor = fd if isinstance(fd, int) else fd.fileno()
    if operation == fcntl.LOCK_EX and os.path.samestat(os.fstat(descriptor), identity):
        try:
            native_flock(fd, operation | fcntl.LOCK_NB)
        except BlockingIOError:
            Path(os.environ["REQUESTED"]).write_text("blocked")
        else:
            raise AssertionError("the overlapping init bypassed the page lease")
    return native_flock(fd, operation)
fcntl.flock = observed_flock
sys.argv = ["leaf", "page", "init", os.environ["PAGE"]]
cli_model.cli()
""",
            REQUESTED=requested,
        )
        wait_for(
            requested.exists,
            bool,
            failure="the overlapping init never attempted the held page lease",
        )
        resume.set()
        first.result(timeout=STATED_TIMEOUT)
        second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)
        assert second.returncode == 0, f"{second_out}{second_err}"
        idled = subprocess.run(
            [*LEAF_COMMAND, "status", page, "idle"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert idled.returncode == 0, idled.stderr
        picked_up = subprocess.run(
            claim_and_wait_command(page),
            shell=True,
            env=os.environ
            | {
                "CLAUDE_CODE_SESSION_ID": "new-owner",
                "CLAUDE_PID": str(os.getpid()),
            },
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert picked_up.returncode == 2, picked_up.stderr
        assert service_model.page_claim(page)["id"] == "new-owner"
    finally:
        resume.set()
        executor.shutdown(wait=True, cancel_futures=True)
    assert first.done()
    assert service_model.page_claim(page)["id"] == "new-owner"


def test_the_codex_environment_defaults_the_name_but_a_worker_keeps_its_own(
    tmp_path, under_codex, codex_env
):
    """A Codex worker launched with LEAF_AGENT set keeps that voice rather than
    the harness's default name."""
    page = tmp_path / "worker-page"
    env = codex_env | {"CODEX_THREAD_ID": "thread-9", "LEAF_AGENT": "Indexer"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    waited = under_codex(claim_and_wait_command(page), env)
    assert waited.wait(timeout=STATED_TIMEOUT) == 0
    session = service_model.page_claim(page)
    assert session["id"] == "thread-9"
    assert session["agent"] == "Indexer" and session["harness"] == "codex"


def test_hook_remedies_follow_the_harness_not_the_display_name(
    tmp_path, under_codex, codex_env, capsys
):
    """LEAF_AGENT names the voice the banner and threads show; which
    machinery the hook prescribes (unified exec vs background tasks) keys on the
    recorded harness, so a renamed Codex worker still gets Codex remedies."""
    page = tmp_path / "worker-page"
    env = codex_env | {"CODEX_THREAD_ID": "w1", "LEAF_AGENT": "Indexer"}
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    finished = tmp_path / "codex-wait-finished"
    waited = under_codex(claim_and_wait_command(page), env, finished=finished)
    release_codex_command(page, waited, finished)
    assert waited.wait(timeout=STATED_TIMEOUT) == 0
    session_model.cmd_waiting(page, "")

    hooks_model.cmd_hook("codex", {"hook_event_name": "Stop", "session_id": "w1"})
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "leaf codex start" in reason and str(page) in reason
    assert service_model.page_claim(page)["agent"] == "Indexer"


@pytest.mark.parametrize(
    "identity_names",
    [
        pytest.param(harness_model.IDENTITY_VARIABLES, id="bare-shell"),
        pytest.param((), id="harness-session"),
    ],
)
def test_wait_lease_is_exact_and_excludes_another_wait(
    page_dir, monkeypatch, spawn, identity_names
):
    """The held lease, not a timestamp or pid, is the wait's liveness."""
    # The suite's hook marks (`isolated_session`) are not records this test makes.
    for session in HOOKED_SESSIONS:
        leases_model.hooks_path(session).unlink()
    for name in identity_names:
        monkeypatch.delenv(name, raising=False)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "comment on the prototype")
    # Ownership is acquired explicitly before taking the session wait lease.
    if not identity_names:
        record_claim(page_dir, id="past-session")
        service_model.claim_page(page_dir)
    lease_path = (
        page_dir / "waiter.lock"
        if identity_names
        else leases_model.waiter_lease_path(
            page_dir, harness_model.session_harness().session
        )
    )
    first = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ,
    )
    wait_for(
        lambda: leases_model.lock_is_held(lease_path),
        bool,
        failure="the first wait never took its exact lease",
    )

    second = subprocess.run(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        env=os.environ,
        check=False,
    )
    assert second.returncode == 2
    assert "another `leaf wait` is already active" in second.stderr

    # SIGTERM unwinds the wait's application cleanup and releases its kernel lease.
    first.terminate()
    first.communicate(timeout=STATED_TIMEOUT)
    assert lease_path.exists()
    assert not leases_model.lock_is_held(lease_path)


def test_a_sigterm_its_handler_takes_inside_a_finalizer_still_ends_the_wait(
    page_dir, monkeypatch, spawn
):
    """Python discards an exception raised in a weakref callback, as it does one
    raised in `__del__` or a GC callback, so a SIGTERM whose handler runs inside
    one cannot end the wait by raising. A page memory's finalizer joins threads,
    which is where a stopped wait once kept running. The wait still ends with
    SIGTERM's status and releases its lease."""
    for name in harness_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "comment on the prototype")
    waiter = spawn_probe(
        spawn,
        page_dir,
        """\
import signal
import weakref
from leaf import session

def receive_termination():
    signal.raise_signal(signal.SIGTERM)
    # The handler runs at this loop's next bytecode check, inside the callback.
    for _ in range(1000):
        pass

class Collected:
    pass

read_watch_pass = session.read_watch_pass
def pass_after_a_finalizer(*args, **kwargs):
    session.read_watch_pass = read_watch_pass
    weakref.finalize(Collected(), receive_termination)
    return read_watch_pass(*args, **kwargs)
session.read_watch_pass = pass_after_a_finalizer
sys.argv = ["leaf", "wait", os.environ["PAGE"]]
cli_model.cli()
""",
    )
    _out, err = waiter.communicate(timeout=STATED_TIMEOUT)
    assert "Exception ignored" in err and "SystemExit" in err, err
    assert waiter.returncode == 128 + signal.SIGTERM, err
    assert not leases_model.lock_is_held(page_dir / "waiter.lock")


@pytest.mark.parametrize("prepared", [False, True])
def test_a_question_about_a_lease_does_not_turn_its_taker_away(tmp_path, prepared):
    """`lock_is_held` asks with a momentary shared lock, which refuses an exclusive
    one as a lease does. A lease taken while a question is open waits the question
    out; only a lease turns a taker away."""
    path = tmp_path / "lease"
    path.touch()
    with open(path, "rb") as question:
        fcntl.flock(question, fcntl.LOCK_SH)
        assert not leases_model.lock_is_held(path)
        threading.Timer(0.05, fcntl.flock, (question, fcntl.LOCK_UN)).start()
        lease = leases_model.take_lease(
            path, prepare=(lambda held: held.flush()) if prepared else None
        )
    assert lease is not None
    assert leases_model.take_lease(path) is None
    leases_model.release_lease(lease)


def test_a_stable_lock_serializes_waiting_takers_and_retains_its_file(
    tmp_path,
):
    """Every taker coordinates on one stable inode, including across release."""
    path = tmp_path / "purpose.lock"
    entered = threading.Event()
    release = threading.Event()
    attempting = threading.Event()

    def take():
        attempting.set()
        with cleanup_model.flocked(path):
            entered.set()
            assert release.wait(STATED_TIMEOUT)

    taker = threading.Thread(target=take)
    with cleanup_model.flocked(path):
        identity = path.stat()
        taker.start()
        assert attempting.wait(STATED_TIMEOUT), (
            "the taker never attempted the held lock"
        )
        assert not entered.is_set()
    assert entered.wait(STATED_TIMEOUT), (
        "the taker never entered the lock once it was free"
    )
    assert leases_model.lock_is_held(path)
    assert leases_model.take_lease(path) is None
    release.set()
    taker.join(STATED_TIMEOUT)
    assert not taker.is_alive()
    assert os.path.samestat(identity, path.stat())
    assert not leases_model.lock_is_held(path)
    with cleanup_model.flocked(path):
        assert leases_model.lock_is_held(path)


def test_prepared_lease_metadata_precedes_exclusive_liveness(tmp_path):
    """A preparation never pairs a successor's lease with retained old metadata."""
    path = tmp_path / "prepared.lock"
    path.write_bytes(b"old")

    def prepare(held):
        assert not leases_model.lock_is_held(path)
        held.truncate(0)
        held.write(b"new")
        held.flush()
        assert not leases_model.lock_is_held(path)

    lease = leases_model.take_lease(path, prepare=prepare)
    try:
        assert leases_model.lock_is_held(path)
        assert path.read_bytes() == b"new"
    finally:
        leases_model.release_lease(lease)
    assert not leases_model.lock_is_held(path)


def test_a_crashed_lease_holder_releases_the_stable_file_for_a_successor(
    tmp_path, spawn
):
    """Process death releases liveness without deleting the coordination inode."""
    path = tmp_path / "lease"
    holder = spawn(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import sys; "
                "from leaf.leases import take_lease; "
                "lease = take_lease(Path(sys.argv[1])); "
                "assert lease is not None; print('held', flush=True); sys.stdin.read()"
            ),
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout.readline() == "held\n"
    identity = path.stat()
    assert leases_model.lock_is_held(path)
    assert leases_model.take_lease(path) is None
    holder.terminate()
    holder.communicate(timeout=STATED_TIMEOUT)
    assert not leases_model.lock_is_held(path)
    assert os.path.samestat(identity, path.stat())
    lease = leases_model.take_lease(path)
    assert lease is not None
    assert leases_model.take_lease(path) is None
    leases_model.release_lease(lease)
    assert not leases_model.lock_is_held(path)
    assert os.path.samestat(identity, path.stat())


def test_a_page_lock_is_its_directory_and_follows_a_page_made_again(
    tmp_path, monkeypatch
):
    """The page lock is the page directory, so it leaves nothing in the state home
    and ends with the page. A taker that waited on a directory deleted and made
    again at the same path locks the new one, so it excludes the next taker; a
    page gone for good raises."""
    page = tmp_path / "page"
    assert CliRunner().invoke(cli_model.cli, ["page", "init", str(page)]).exit_code == 0
    assert not (machine_model.state_home() / "page-locks").exists()

    entered = threading.Event()
    release = threading.Event()
    requested = lock_contention(monkeypatch, page, by="page-taker")

    def take():
        with leases_model.page_locked(page):
            entered.set()
            assert release.wait(STATED_TIMEOUT), (
                "the replacement lock was never released"
            )

    taker = threading.Thread(target=take, name="page-taker")
    try:
        with leases_model.page_locked(page):
            taker.start()
            assert requested.wait(STATED_TIMEOUT), (
                "the taker never opened the old directory"
            )
            shutil.rmtree(page)
            page.mkdir()
        assert entered.wait(STATED_TIMEOUT), (
            "the taker never locked the replacement directory"
        )
        fd = os.open(page, os.O_RDONLY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        release.set()
        taker.join(STATED_TIMEOUT)
    assert not taker.is_alive(), "the taker retained the replacement directory lock"

    page.rmdir()
    with pytest.raises(FileNotFoundError), leases_model.page_locked(page):
        pass


def test_a_new_claim_cannot_borrow_the_previous_sessions_wait_lease(
    page_dir, monkeypatch
):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "first")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert service_model.claim_page(page_dir)
    first = harness_model.session_harness()
    first_turn = service_model.page_claim(page_dir)["turn"]
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, first.session)
    )
    assert lease and page_state(page_dir)["listening"]

    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["turn"] == first_turn
    assert page_state(page_dir)["listening"]

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    assert service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir)["turn"] != first_turn
    assert not page_state(page_dir)["listening"]
    leases_model.release_lease(lease)


def test_page_claim_takes_a_page_without_watching_it(page_dir, monkeypatch):
    """A Claude Code session picks up a page another session served by claiming
    it, and its own Stop hook watches the page from the end of the turn: a `leaf
    wait` there would hold the lease that hook needs."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    record_claim(page_dir, id="s2")
    result = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert service_model.owned_pages("s7") == [page_dir.resolve()]
    assert not leases_model.wait_is_live(page_dir, "s7")


def test_a_background_job_no_worker_hosts_is_resumed_with_its_input(
    tmp_path, monkeypatch, dead_pid
):
    """A background job's daemon retires its worker about an hour after the job
    goes idle, taking the socket and the Stop hook's watch with it, while the job
    still holds its pages. Input after that reaches it only by resuming the job:
    `claude --bg --resume` claims a fresh worker for the same session and runs the
    message there as its prompt. A job a live worker still hosts is not resumed,
    since the same command would start a copy of it."""
    config = tmp_path / "claude"
    (config / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    bin_dir, argv = tmp_path / "bin", tmp_path / "argv"
    bin_dir.mkdir()
    (bin_dir / "claude").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argv}\n')
    (bin_dir / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    page = tmp_path / "page"
    job = harness_model.ClaudeCodeHarness(
        session="s9", agent="Claude", job=str(tmp_path / "job")
    )

    # The retired worker's record outlives it; its pid does not.
    record = config / "sessions" / f"{dead_pid}.json"
    cleanup_model.write_json(
        record, {"pid": dead_pid, "sessionId": "s9", "messagingSocketPath": "/gone"}
    )
    assert job.nudge(page)
    wait_for(argv.exists, bool, failure="the job was never resumed")
    wait_for(
        lambda: len(argv.read_text().splitlines()),
        lambda n: n == 4,
        failure="the resume's arguments never arrived",
    )
    assert argv.read_text().splitlines() == [
        "--bg",
        "--resume",
        "s9",
        f"leaf: {page} has new input, which arrives with this message.",
    ]

    # A job whose worker still runs is not resumed, socket or none.
    argv.unlink()
    cleanup_model.write_json(
        record, {"pid": os.getpid(), "sessionId": "s9", "messagingSocketPath": "/gone"}
    )
    assert not job.nudge(page)
    record.unlink()
    assert not harness_model.ClaudeCodeHarness(session="s9", agent="Claude").nudge(page)
    assert not argv.exists()


def test_a_claim_an_older_leaf_wrote_is_dropped_rather_than_read_or_raised_on(
    tmp_path, page_dir, monkeypatch, capsys
):
    """The claims directory is one per machine, and the worktrees writing it are
    each on their own commit, so a session routinely reads records a different
    version wrote. Found in the wild: a session held six preview pages claimed
    before #811 named a harness, merged a main that had landed it, and every
    `leaf wait` after that died in `owned_by` on `claim["harness"]` — taking the
    watcher off the unrelated page the user was actually reading.

    Stage owes nothing to what an older version wrote, so the record is not
    migrated and its old shape is never read. It is dropped where it is read,
    which leaves its page unclaimed and every other page working."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s8")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    leases_model.mark_hooks("s8")  # its harness runs Leaf's hooks
    # The walk is in path order, so a name ahead of the user's page is what
    # puts the unreadable record in front of the batch the session came for.
    stale = tmp_path / "held-preview"
    assert (
        CliRunner().invoke(cli_model.cli, ["page", "init", str(stale)]).exit_code == 0
    )
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert service_model.claim_page(stale)
    assert service_model.claim_page(page_dir)
    assert service_model.owned_pages("s8") == [stale.resolve(), page_dir.resolve()]

    claim = service_model.page_claim(stale)
    written_before_811 = {**claim, "host": claim["harness"]}
    del written_before_811["harness"]
    cleanup_model.write_json(service_model.claim_path(stale), written_before_811)

    # The reported failure: the watcher walks every page the session holds, and
    # the record it cannot read belongs to a page the user is not on.
    waited = CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)])
    assert waited.exception is None, repr(waited.exception)
    assert waited.exit_code == 0, repr(waited.output)
    _, _, [event] = woken(waited.output)
    assert event["text"] == "hi"

    assert service_model.page_claim(stale) is None
    assert service_model.owned_pages("s8") == [page_dir.resolve()]

    # The same reading answers for the two records a later rename leaves behind,
    # and the Stop hook shows both: a harness name outside this version's table
    # raises in `harness.claim_harness`, which dispatches on that value rather than
    # reading it, and a record missing a field a user brackets is taken for a
    # live claim, putting its page back in front of the guard — and in front of
    # `event_endpoint`'s nudge, which brackets `turn_closed` under the append
    # lock.
    for unreadable in (
        {**claim, "harness": "some-harness-a-later-leaf-named"},
        {key: value for key, value in claim.items() if key != "generation"},
    ):
        cleanup_model.write_json(service_model.claim_path(stale), unreadable)
        hooks_model.cmd_hook(
            "claude-code", {"hook_event_name": "Stop", "session_id": "s8"}
        )
        assert str(stale) not in capsys.readouterr().out
        assert service_model.page_claim(stale) is None


def test_a_claim_is_active_while_the_lifetime_it_names_holds(
    tmp_path, monkeypatch, dead_pid, native_codex_chat
):
    """One reading of what makes a claim active, and every hook comes through it.

    The claims this writes have to go to a relocated home. A record left in a shared
    directory outlives the run that made it, and a constant id in one is a name every
    run answers to: an earlier version of this test wrote into the developer's own
    `~/.local/state/leaf/claims`, one unreleased claim per run under this same id and
    nothing ever sweeping them. Seventy-six had collected when one of their pids came
    round again on a live process, and the rule below read as true for a claim no run
    of this test had made. `isolated_session` supplies the home.
    """
    page = tmp_path / "page"
    page.mkdir()
    record_claim(page, id="guarded")
    assert service_model.claim_is_active(service_model.page_claim(page))
    cleanup_model.end_session("guarded")
    assert not service_model.claim_is_active(service_model.page_claim(page))
    record_claim(page, id="guarded", pid=dead_pid)
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # A background job's claim names the job's record and no process at all, so the
    # pid the environment states — dead here — is nothing to this user. Claimed
    # through the real door, which asks for an initialized page.
    (page / "events.jsonl").write_bytes(b"")
    job = tmp_path / "job"
    job.mkdir()
    cleanup_model.write_json(job / "state.json", {"sessionId": "guarded"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "guarded")
    monkeypatch.setenv("CLAUDE_PID", str(dead_pid))
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(job))
    assert service_model.claim_page(page)
    assert "pid" not in service_model.page_claim(page)
    assert service_model.claim_is_active(service_model.page_claim(page))
    # Deleting the job takes its record; the directory can stay behind empty.
    (job / "state.json").unlink()
    assert not service_model.claim_is_active(service_model.page_claim(page))

    # Desktop ownership follows the persisted native chat, independently of page
    # freshness. Missing or archived/deleted native sources own no page.
    chat = tmp_path / "chat"
    chat.mkdir()
    source = native_codex_chat("multiplexed")
    record_claim(chat, id="multiplexed", harness="codex", chat=True)
    claim = service_model.page_claim(chat)
    assert "pid" not in claim
    assert service_model.claim_is_active(claim)
    source.rename(source.with_suffix(".archived"))
    assert not service_model.claim_is_active(service_model.page_claim(chat))
    (chat / "events.jsonl").write_bytes(b"")
    assert not service_model.claim_is_active(service_model.page_claim(chat))

    # A dead claim answers for its own page and no more: the session's other
    # records are still walked, and the live one is still the session's page.
    other = tmp_path / "other"
    other.mkdir()
    (other / "events.jsonl").write_bytes(b"")
    record_claim(other, id="other-guarded")
    assert service_model.owned_pages("guarded") == []
    assert service_model.owned_pages("other-guarded") == [other.resolve()]
