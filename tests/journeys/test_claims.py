"""Page claims: which session and harness hold a page, what a claim records, when it
is active, and the leases and page locks that keep a wait and a claim exclusive."""

import json
import shlex
import subprocess

from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    page_packages,
    publish,
    start_server_command,
)

from leaf import cli as cli_model
from leaf import hooks as hooks_model
from leaf import service as service_model
from leaf.registry.storage import layer_record
from leaf_dev.page_fixtures import package_selection_args


def test_revendor_preserves_pending_input_for_the_current_claim(claimed, capsys):
    """A served page's pending comment reaches its session after a re-selection
    restarts its server."""
    publish(claimed)
    started = start_server_command(claimed, session_id="s1")
    assert started.returncode == 0, started.stderr
    prior_claim = service_model.page_claim(claimed)
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Still here"}
    )
    layer = layer_record(claimed)
    assert layer is not None
    generation = layer["generation"]
    extra = claimed.parent / "extra"
    extra.mkdir()
    (extra / "overrides.css").write_text("/* another selection */\n")
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./extra")),
            str(claimed),
        ],
    )
    assert result.exit_code == 0, result.output
    layer_2 = layer_record(claimed)
    assert layer_2 is not None
    assert layer_2["generation"] != generation
    assert service_model.page_claim(claimed) == prior_claim
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    [batch] = json.loads(context["additionalContext"].split("\n")[1])["batches"]
    assert batch["page"] == str(claimed)
    assert [event["id"] for event in batch["events"]] == [asked["id"]]


def test_the_app_s_shared_codex_is_not_taken_for_one_session_s_lifetime(
    tmp_path, under_codex, codex_env, codex_queue, native_codex_chat
):
    """The one word that separates the two Codex shapes, and the claim each writes.

    `CodexHarness.lifetime` finds a session by walking for the nearest `codex`
    ancestor. Under the CLI that process is the session and its pid is exact.
    The ChatGPT app runs one `codex ... app-server` for the whole app and every
    thread hangs off it, so the same walk handed every session one pid
    that outlives them all: a session-managed server checks `pid_alive` and
    never sees it die, and the page stays served until the app quits. Found in
    the wild as 133 unreleased claims naming a single app-server pid, 49 of
    their servers still up, the oldest 28 hours past its thread.

    Both runs go through the real claim door under a real process of that name,
    so what is asserted is the claim leaf writes rather than a reading of the
    walk. Nothing varies between them but the word.
    """

    def claimed(name, *, app_server):
        if app_server:
            native_codex_chat(name)
        page = tmp_path / name
        subprocess.run([*LEAF_COMMAND, "page", "init", page], env=codex_env, check=True)
        started = under_codex(
            shlex.join([*LEAF_COMMAND, "server", "start", str(page)]),
            codex_env | codex_queue | {"CODEX_THREAD_ID": name},
            app_server=app_server,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, err = started.communicate(timeout=STATED_TIMEOUT)
        assert started.returncode == 0, f"{out}{err}"
        claim = service_model.page_claim(page)
        subprocess.run(
            [*LEAF_COMMAND, "server", "stop", page], env=codex_env, check=True
        )
        return claim

    session = claimed("cli-thread", app_server=False)
    assert session["pid"] > 0
    assert "chat" not in session

    app = claimed("app-thread", app_server=True)
    assert "pid" not in app
    assert app["chat"] is True


import os
import threading
from concurrent.futures import ThreadPoolExecutor

from interact_support import (
    claim_and_wait_command,
    page_state,
    spawn_probe,
    wait_for,
)

from leaf import vendoring as vendoring_model


def test_a_codex_command_claims_the_page_for_its_thread(codex_claimed_page):
    session = service_model.page_claim(codex_claimed_page)
    assert session is not None
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


def test_a_fresh_init_does_not_delete_a_concurrently_created_pages_claim(
    tmp_path, monkeypatch, spawn
):
    """The first page creation is one serialized transition."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "concurrent-page"
    reached_layer = threading.Event()
    resume = threading.Event()
    original_compose_layer = vendoring_model.compose_layer

    # Held where init composes the selection under the page lock, which runs on
    # every init.
    def held_compose_layer(*roots):
        reached_layer.set()
        assert resume.wait(timeout=STATED_TIMEOUT), (
            "the concurrent init never released its peer"
        )
        return original_compose_layer(*roots)

    monkeypatch.setattr(vendoring_model, "compose_layer", held_compose_layer)
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
            [*LEAF_COMMAND, "page", "close", page],
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
        claim_record_5 = service_model.page_claim(page)
        assert claim_record_5 is not None
        assert claim_record_5["id"] == "new-owner"
    finally:
        resume.set()
        executor.shutdown(wait=True, cancel_futures=True)
    assert first.done()
    claim_record_6 = service_model.page_claim(page)
    assert claim_record_6 is not None
    assert claim_record_6["id"] == "new-owner"
