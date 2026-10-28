"""A session's lifecycle record: prompts, stops and provider observations opening
and closing its turn, session end releasing its pages, and the notice that tells a
resumed session to reconnect its leaf."""

import json
import shlex

from interact_support import start_server_command, wait_for

from leaf import hooks as hooks_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import state as cleanup_model


def test_normal_server_restart_leaves_later_recovery_advice_available(claimed, capsys):
    """A quick second outage still produces advice without an intervening healthy hook."""
    first = start_server_command(claimed, session_id="s1")
    assert first.returncode == 0, first.stderr
    cleanup_model.end_harness_instance("s1")
    wait_for(
        lambda: server_model.running_server(claimed),
        lambda running: not running,
        failure="the first ended session's server did not retire",
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    command = f"leaf server start {shlex.quote(str(claimed.resolve()))}"
    assert (
        command
        in json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
    )

    restarted = start_server_command(claimed, session_id="s1")
    assert restarted.returncode == 0, restarted.stderr
    assert service_model.claim_is_active(service_model.page_claim(claimed))
    cleanup_model.end_harness_instance("s1")
    wait_for(
        lambda: server_model.running_server(claimed),
        lambda running: not running,
        failure="the restarted server did not retire after its session ended",
    )
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s1"}
    )
    assert (
        command
        in json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
    )
