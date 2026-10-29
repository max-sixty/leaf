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
    (extra / "theme.css").write_text("/* another selection */\n")
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
