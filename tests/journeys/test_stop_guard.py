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


from interact_support import (
    _interaction_prompt_evidence,
    adapter_lease,
    declare_idle,
    receive_through,
    yaml_document,
)

from leaf import harness as harness_model
from leaf import leases as leases_model
from leaf import session as session_model
from leaf import thread as thread_model


def test_agent_sees_codex_watcher_recovery(codex_claimed_page, capsys, snapshot):
    """What Codex's Stop hook tells a task, for each way its page can be watched: no
    watcher at all, a direct wait in unified exec, which keeps the turn active because
    only that session's output can enter this context, and an adapter, which lets the
    turn end because it can deliver into a later one."""
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    observations = {}

    def hook(**payload):
        hooks_model.cmd_hook(
            "codex",
            {"hook_event_name": "Stop", "session_id": "codex-thread", **payload},
        )
        output = capsys.readouterr().out
        return json.loads(output) if output else None

    observations["no adapter"] = hook()
    assert "leaf page claim" in observations["no adapter"]["reason"]
    assert str(page) in observations["no adapter"]["reason"]
    lease_path_3 = leases_model.waiter_lease_path(page, "codex-thread")
    assert lease_path_3 is not None
    lease = leases_model.take_wait_lease(lease_path_3)
    assert lease
    try:
        # The lease cannot say whether the session's command is the initial wait or
        # the one that acknowledged a delivery before waiting, so the remedy names both.
        observations["direct wait still running"] = hook()
        reason = observations["direct wait still running"]["reason"]
        assert "poll the existing" in reason and "write_stdin" in reason
        assert "running `leaf wait`, alone or after `leaf delivery ack`" in reason
        # The existing one-shot escape still prevents a hook recursion.
        assert hook(stop_hook_active=True) is None

        comment = append_carried_log_record(
            page, {"kind": "comment", "author": "user", "text": "Check this."}
        )
        # Pending output still has to cross context: the remedy is to poll the wait
        # already running, and nothing tells this task to start one in the background.
        # The delivery the poll yields says how this harness acknowledges it.
        observations["direct wait has input"] = hook()
        reason = observations["direct wait has input"]["reason"]
        assert "running `leaf wait`, alone or after `leaf delivery ack`" in reason
        assert "background" not in reason
        acknowledge = session_model.wait_acknowledgement(
            harness_model.CodexHarness("codex-thread", "Codex"), page
        )("0a1b2c3d")
        assert (
            "run `leaf delivery ack 0a1b2c3d && leaf wait` in unified exec"
            in acknowledge
        )
        assert "background" not in acknowledge
        # The adapter's second lease proves that the watcher can deliver into a
        # later turn. With that adapter alive, this turn may end normally.
        adapter = adapter_lease("codex-thread", None)
        try:
            observations["adapter carries input"] = hook()
        finally:
            adapter.close()
    finally:
        leases_model.release_lease(lease)
    snapshot.check(
        yaml_document(
            "Codex Stop output: no adapter, a direct shell wait, and a live adapter.",
            _interaction_prompt_evidence(page, observations),
        )
    )

    receive_through(page, comment["seq"])
    # Answered before the page closes: an acknowledged comment with nothing
    # under it holds the turn on its own account, which is the subject of
    # test_an_acknowledged_comment_nobody_answered_holds_the_turn.
    thread_model.post_reply(
        page,
        {"parent": comment["id"], "responds": comment["id"]},
        "so it does",
    )
    declare_idle(page)
    assert hook() is None
