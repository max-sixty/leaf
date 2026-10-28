"""The guard on a turn's end: the Stop hook holding a turn over a page nothing
watches or a move the agent still owes, `leaf page close` refusing over input
nobody answered, and the reminders both write."""

import json
import os

from click.testing import CliRunner
from interact_support import append_carried_log_record, check

from leaf import cli as cli_model
from leaf import hooks as hooks_model
from leaf import service as service_model


def test_only_serving_or_claiming_a_page_puts_the_session_under_the_guard(
    page_dir, interactive, monkeypatch, capsys
):
    """Verifying a change to the page layer means driving throwaway pages, and the
    guard must not read a handful of test fixtures as a handful of abandoned
    pages. A directory this session only built and linted was handed to nobody.
    Claiming one is what puts a user on the other end, and from there the
    guard holds the session to it."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s7")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    assert check(page_dir).exit_code == 0
    assert service_model.owned_pages("s7") == []
    # `page init` left the page "working", which is the state the guard blocks on —
    # but only for a page some session answers for, and none does.
    hooks_model.cmd_hook("claude-code", {"hook_event_name": "Stop", "session_id": "s7"})
    assert capsys.readouterr().out == ""

    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 2
    assert service_model.owned_pages("s7") == []
    claimed = CliRunner().invoke(cli_model.cli, ["page", "claim", str(page_dir)])
    assert claimed.exit_code == 0, claimed.output
    assert CliRunner().invoke(cli_model.cli, ["wait", str(page_dir)]).exit_code == 0
    assert service_model.owned_pages("s7") == [page_dir.resolve()]

    # The prompt hook of the turn the wake opens carries the input into it.
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": "s7"}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    [batch] = json.loads(context.split("\n")[1])["batches"]
    assert [event["text"] for event in batch["events"]] == ["hi"]
