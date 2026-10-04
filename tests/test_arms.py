"""Harness evidence admits successful commands and retains actual delivery inputs."""

import json

import pytest
from leaf_dev.arms import accepted_thread_claims, commands, completed, trace_result
from leaf_dev.eval_codex import records_for


def test_codex_command_and_turn_success_are_observed_harness_results():
    # App Server's observed commandExecution notifications, reduced to the fields
    # relevant to successful Leaf status admission. Unknown/nonzero exits must
    # never turn a printed status into an accepted claim.
    output = json.dumps(
        {"state": "working", "work": [{"subject": {"kind": "thread", "id": "comment"}}]}
    )
    for exit_code in (0, 1, None):
        item = {
            "id": "claim",
            "type": "commandExecution",
            "status": "completed",
            "command": "leaf status page working editing --on comment",
            "aggregatedOutput": output,
            "exitCode": exit_code,
        }
        trace = records_for(
            {"method": "item/started", "params": {"item": item}}, "session", ""
        ) + records_for(
            {"method": "item/completed", "params": {"item": item}}, "session", ""
        )
        assert commands(trace[0]) == [item["command"]]
        assert accepted_thread_claims(trace, "comment") == (
            {"claim": 1} if exit_code == 0 else {}
        )
        for status in ("completed", "failed", "interrupted"):
            end = records_for(
                {
                    "method": "turn/completed",
                    "params": {"turn": {"id": "turn", "status": status, "error": None}},
                },
                "session",
                "the actual final answer",
            )
            assert completed(trace + end) is (status == "completed")
            assert trace_result(end)["session_id"] == "session"
            assert trace_result(end)["turn_id"] == "turn"
            assert trace_result(end)["result"] == "the actual final answer"


def test_codex_delivery_evidence_preserves_actual_input_and_hook_output():
    content = [
        {
            "type": "text",
            "text": '<leaf-delivery-v1>{"elided":{"messages":12}}</leaf-delivery-v1>',
        }
    ]
    records = records_for(
        {
            "method": "item/completed",
            "params": {"item": {"type": "userMessage", "content": content}},
        },
        "session",
        "",
    )
    assert records == [{"type": "user", "message": {"content": content}}]
    delivery = json.dumps({"format": "leaf-delivery-v3", "elided": {"messages": 12}})
    output = records_for(
        {
            "method": "item/completed",
            "params": {
                "item": {
                    "type": "functionCallOutput",
                    "id": "fco",
                    "name": "leaf_delivery",
                    "output": delivery,
                }
            },
        },
        "session",
        "",
    )
    assert output == [
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "fco",
                        "tool_name": "leaf_delivery",
                        "content": delivery,
                    }
                ]
            },
        }
    ]
    observed = {
        "method": "hook/completed",
        "params": {
            "run": {
                "eventName": "stop",
                "status": "blocked",
                "entries": [{"kind": "context", "text": "the real hook's context"}],
            }
        },
    }
    assert records_for(observed, "session", "") == [
        {
            "type": "system",
            "subtype": "hook_response",
            "hook_event": "stop",
            "hook_status": "blocked",
            "output": "the real hook's context",
        }
    ]
    assert records_for({"method": "turn/started", "params": {}}, "session", "") == []


def test_codex_delegation_retains_the_actual_task_and_outcome():
    item = {
        "type": "collabAgentToolCall",
        "id": "reader",
        "tool": "spawnAgent",
        "prompt": "Review only the request and screenshots",
        "receiverThreadIds": ["child"],
        "agentsStates": {"child": {"status": "running"}},
        "status": "completed",
    }
    trace = []
    for method in ("item/started", "item/completed"):
        trace.extend(
            records_for({"method": method, "params": {"item": item}}, "author", "")
        )
    task = trace[0]["message"]["content"][0]
    assert task["name"] == "spawnAgent"
    assert task["input"]["prompt"] == item["prompt"]
    assert task["input"]["receivers"] == ["child"]
    assert trace[1]["message"]["content"][0]["is_error"] is False
    item["status"] = "failed"
    failed = records_for(
        {"method": "item/completed", "params": {"item": item}}, "author", ""
    )
    assert failed[0]["message"]["content"][0]["is_error"] is True


@pytest.fixture
def observed_codex():
    from collections import deque
    from io import StringIO

    from leaf_dev.codex_task import Task
    from leaf_dev.eval_codex import CodexChild

    child = CodexChild.__new__(CodexChild)
    child.raw = StringIO()
    child.queue = deque()
    child.final, child.usage = "", None
    child.now = lambda: "2026-10-02T22:36:55-07:00"
    task = Task.__new__(Task)
    task.thread, task.started, task.running = "parent", [], set()
    task.commands, task.running_commands, task.hooks = [], {}, []
    task.on_final = None
    task.on_message = child._hear
    child.task = task
    child.closing = False
    return child, task


def test_codex_parent_evidence_isolated_from_delegated_threads_and_usage_snapshots(
    observed_codex,
):
    """Replay App Server's observed multiplexing through both shared owners.

    Delegating authors receive the child's notifications on their connection.
    The child completed before the parent in the recorded failing run; that must
    not end the parent's eval, replace its answer or count the child's usage.
    """
    child, task = observed_codex
    observed = []

    def hear(method, thread="parent", **params):
        message = {"method": method, "params": {"threadId": thread, **params}}
        observed.append(message)
        task._hear(message)

    def usage(total, last, thread="parent"):
        hear(
            "thread/tokenUsage/updated",
            thread,
            turnId=task.started[-1] if thread == "parent" else "child-turn",
            tokenUsage={
                "total": {"inputTokens": total, "outputTokens": total // 10},
                "last": {"inputTokens": last, "outputTokens": last // 10},
            },
        )

    hear("hook/started", run={"eventName": "UserPromptSubmit"})
    hear("turn/started", turn={"id": "parent-turn"})
    usage(50, 50)
    hear(
        "item/completed",
        item={"type": "agentMessage", "phase": "final_answer", "text": "Parent answer"},
        turnId="parent-turn",
    )
    hear("turn/started", "child", turn={"id": "child-turn"})
    usage(900, 900, "child")
    hear(
        "item/completed",
        "child",
        item={"type": "agentMessage", "phase": "final_answer", "text": "Child answer"},
        turnId="child-turn",
    )
    hear(
        "hook/completed",
        "child",
        run={
            "eventName": "stop",
            "status": "blocked",
            "entries": [{"kind": "context", "text": "Child hook context"}],
        },
    )
    foreign_command = {
        "type": "commandExecution",
        "id": "child-command",
        "command": "touch child-output",
        "status": "completed",
        "exitCode": 0,
        "aggregatedOutput": "Child command output",
    }
    hear("item/started", "child", item=foreign_command)
    hear("item/completed", "child", item=foreign_command)
    hear(
        "turn/completed",
        "child",
        turn={"id": "child-turn", "status": "completed", "error": None},
    )
    assert task.running == {"parent-turn"}
    assert [message["method"] for message in task.hooks] == ["hook/started"]
    assert task.started == ["parent-turn"]
    assert task.commands == [] and task.running_commands == {}
    assert child.final == "Parent answer"
    assert child.usage == {"inputTokens": 50, "outputTokens": 5}
    assert not any(r.get("type") == "result" for r in child.queue)
    assert all("Child" not in json.dumps(record) for record in child.queue)

    # A repeated cumulative usage snapshot is the same evidence, not another
    # model call. The later total advances by the new call's `last` usage.
    usage(50, 50)
    usage(80, 30)
    parent_hook = {
        "eventName": "stop",
        "status": "completed",
        "entries": [{"kind": "context", "text": "Parent hook context"}],
    }
    hear("hook/completed", run=parent_hook)
    assert [message["method"] for message in task.hooks] == [
        "hook/started",
        "hook/completed",
    ]
    assert task.hooks[-1]["params"]["run"] == parent_hook
    hear(
        "turn/completed",
        turn={"id": "parent-turn", "status": "completed", "error": None},
    )
    assert task.running == set()
    result = trace_result(list(child.queue))
    assert result["session_id"] == "parent"
    assert result["turn_id"] == "parent-turn"
    assert result["result"] == "Parent answer"
    assert result["usage"] == {"input_tokens": 80, "output_tokens": 8}
    assert result["duration_ms"] >= 0
    assert completed(list(child.queue))
    assert sum(r.get("type") == "result" for r in child.queue) == 1
    assert [
        r["output"] for r in child.queue if r.get("subtype") == "hook_response"
    ] == ["Parent hook context"]
    assert [json.loads(line) for line in child.raw.getvalue().splitlines()] == observed

    # Resuming another turn on this same parent keeps thread-wide cumulative
    # accounting from becoming the resumed turn's usage.
    hear("turn/started", turn={"id": "parent-resumed"})
    usage(100, 20)
    hear(
        "turn/completed",
        turn={"id": "parent-resumed", "status": "completed", "error": None},
    )
    assert trace_result(list(child.queue))["usage"] == {
        "input_tokens": 20,
        "output_tokens": 2,
    }


def test_codex_live_driver_observes_stdout_before_the_next_harness_notification(
    observed_codex,
):
    """The real transport emits URL stdout before parent completion.

    An external model socket is replaced by the recorded two-notification order;
    the actual Task receiver, normalization and generator must give the driver a
    chance to post its move while the parent is still running.
    """
    from leaf_dev.arms import URL, blocks

    child, task = observed_codex
    task._hear(
        {
            "method": "turn/started",
            "params": {
                "threadId": "parent",
                "turn": {"id": "active"},
            },
        }
    )
    url = "http://127.0.0.1:41458/?t=3sJv7fdFvl_kSLic5OynkA"
    messages = iter(
        [
            {
                "method": "item/commandExecution/outputDelta",
                "params": {
                    "threadId": "parent",
                    "turnId": "active",
                    "itemId": "server-command",
                    "delta": json.dumps({"url": url}) + "\n",
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "parent",
                    "turn": {"id": "active", "status": "completed", "error": None},
                },
            },
        ]
    )

    class RecordedSocket:
        def recv(self, *, timeout):
            return json.dumps(next(messages))

    task.socket = RecordedSocket()
    records = child.records()
    stdout = next(records)
    assert stdout["type"] == "tool_output"
    assert stdout["tool_use_id"] == "server-command"
    assert stdout["turn_id"] == "active"
    assert URL.search(json.dumps(stdout))[0] == url
    assert list(blocks([stdout])) == []  # A delta is never a successful tool result.
    assert task.running == {"active"}
    assert not completed([stdout])
    child.close()
    result = next(records)
    assert completed([stdout, result])
    assert task.running == set()
    with pytest.raises(StopIteration):
        next(records)


def test_token_counts_distinguish_unknown_partial_and_observed_zero():
    from leaf_dev.arms import token_counts

    known = {"input_tokens": 7, "output_tokens": 2}
    cached = {**known, "cache_creation_input_tokens": 3, "cache_read_input_tokens": 11}
    for usage, expected in [
        ([], {"input_tokens": None, "output_tokens": None}),
        ([None], {"input_tokens": None, "output_tokens": None}),
        ([{}], {"input_tokens": None, "output_tokens": None}),
        (
            [{"input_tokens": 0, "output_tokens": 0}],
            {"input_tokens": 0, "output_tokens": 0},
        ),
        ([{"input_tokens": 7}], {"input_tokens": 7, "output_tokens": None}),
        ([known, cached], {"input_tokens": 28, "output_tokens": 4}),
        ([known, None], {"input_tokens": None, "output_tokens": None}),
    ]:
        trace = [{"type": "result", "usage": counts} for counts in usage]
        assert token_counts(trace) == expected


def test_single_turn_timeout_retains_native_trace_without_fabricating_completion(
    tmp_path, monkeypatch
):
    import subprocess

    from leaf_dev import arms

    partial = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Still working"}]},
    }
    seen = []

    def stalled_cli(**kwargs):
        # Replace the external CC process with its observed timeout boundary;
        # preserve its native stdout/stderr exactly, with no model dependency.
        seen.append(kwargs["timeout"])
        kwargs["stdout"].write(json.dumps(partial) + "\n")
        kwargs["stderr"].write("a native diagnostic\n")
        raise subprocess.TimeoutExpired(kwargs["args"], kwargs["timeout"])

    monkeypatch.setattr(arms, "claude_child", lambda *a, **k: {"args": ["external-cc"]})
    monkeypatch.setattr(arms.subprocess, "run", stalled_cli)
    out, err = tmp_path / "stream.jsonl", tmp_path / "stderr.txt"
    assert arms.run_agent(tmp_path, "work", out=out, err=err) == [partial]
    assert seen == [arms.TURN_LIMIT]
    assert out.read_text() == json.dumps(partial) + "\n"
    assert err.read_text() == "a native diagnostic\n"
    assert out.with_suffix(".timed-out").is_file()
    assert not completed(arms.read_trace(out))
