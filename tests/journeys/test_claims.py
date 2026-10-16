"""Page claims: which session and harness hold a page, what a claim records, when it
is active, and the leases and page locks that keep a wait and a claim exclusive."""

import json
import os
import shlex
import subprocess
import urllib.parse
import urllib.request

from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    publish,
    start_server_command,
)
from leaf import cli as cli_model
from leaf import files as files_model
from leaf import hooks as hooks_model
from leaf import service as service_model
from leaf import state as cleanup_model


def test_revendor_and_serve_restore_input_after_an_unreadable_old_claim(
    claimed, capsys
):
    """A fresh serve restores delivery without interpreting an older claim.

    A plugin update may leave a claim and session record this version cannot
    read. Re-vendoring and serving again from the running session keeps the
    user's pending input and establishes current ownership for its prompt hook.
    """
    publish(claimed)
    started = start_server_command(claimed, session_id="s1")
    assert started.returncode == 0, started.stderr
    prior_claim = files_model.read_json(service_model.claim_path(claimed))
    prior_claim.pop("generation")
    prior_claim.pop("acquisition")
    prior_claim.update(pid=os.getpid(), turn="old-turn", turn_closed=None)
    cleanup_model.write_json(service_model.claim_path(claimed), prior_claim)
    cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX).unlink()
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Still here"}
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert capsys.readouterr().out == ""
    assert service_model.page_claim(claimed) is None
    assert cleanup_model.session_record("s1") is not None

    theme = claimed / "theme.css"
    theme.write_text(theme.read_text() + "\n/* repair installed edit */\n")
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(claimed)])
    assert result.exit_code == 0, result.output
    assert "has no live session owner" in result.output
    restarted = start_server_command(claimed, session_id="s1")
    assert restarted.returncode == 0, restarted.stderr
    state_url = (
        urllib.parse.urlsplit(json.loads(restarted.stdout)["url"])
        ._replace(path="/api/state")
        .geturl()
    )
    with urllib.request.urlopen(state_url) as response:
        assert response.status == 200
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
