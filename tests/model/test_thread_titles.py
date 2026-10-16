"""Thread titles: the title a page server asks a model for as a thread's opening
comment arrives, under Claude Code and Codex alike, and the App Server it holds
open for one."""

import contextlib
import json
import os
import shutil
import sys
import threading
from pathlib import Path

from interact_support import (
    STATED_TIMEOUT,
    Prose,
    append_carried_log_record,
    append_command,
    record_claim,
    stamp,
    wait_for,
    yaml_document,
)
from leaf import codex as codex_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import thread_titles


def titling_app_server(app_server, answer: str) -> tuple[str, list[dict]]:
    """An App Server that answers each titling thread with `answer`."""
    received = []

    def handle(socket):
        for raw in socket:
            message = json.loads(raw)
            received.append(message)
            method = message.get("method")
            if method == "initialize":
                socket.send(json.dumps({"id": message["id"], "result": {}}))
            elif method == "config/read":
                servers = {"docs": {"command": "docs-server", "enabled": True}}
                config = {"config": {"mcp_servers": servers}}
                socket.send(json.dumps({"id": message["id"], "result": config}))
            elif method == "thread/start":
                thread = {"thread": {"id": "title-thread"}}
                socket.send(json.dumps({"id": message["id"], "result": thread}))
            elif method == "turn/start":
                socket.send(
                    json.dumps({"id": message["id"], "result": {"turn": {"id": "t"}}})
                )
                for notification in (
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": "title-thread",
                            "item": {"type": "agentMessage", "text": answer},
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "title-thread",
                            "turn": {"id": "t", "status": "completed"},
                        },
                    },
                ):
                    socket.send(json.dumps(notification))

    return app_server(handle), received


def test_an_app_server_turn_names_the_untitled_thread_it_answers(page_dir, app_server):
    """The App Server client gives an unnamed thread its first title from the
    opening message and passage."""
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Why does the export take a minute?",
            "anchor": {"section": None, "quote": "Export runs nightly"},
        },
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    [batch] = prepared.payload["batches"]
    [delivered] = batch["events"]
    assert delivered["answer"]["writer"] == "turn"

    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    records = []
    thread_titles.name_thread(
        thread_titles.app_server_title(endpoint, "light-model"),
        page_dir,
        comment["id"],
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title was never generated")

    [(event, fields)] = records
    assert (event, fields["written"]) == ("thread_title_generated", True)
    [title] = [
        e for e in events_model.read_events(page_dir) if e["kind"] == "thread_title"
    ]
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Leaf guide", "hosted-thread")
    [start] = [m for m in received if m.get("method") == "thread/start"]
    assert start["params"]["ephemeral"] is True
    assert start["params"]["model"] == "light-model"
    # The user's MCP servers would start with the thread and list their tools to it.
    assert start["params"]["config"]["mcp_servers"] == {"docs": {"enabled": False}}
    # Both read the page's directory, so a project's own servers are among them.
    [read] = [m for m in received if m.get("method") == "config/read"]
    assert read["params"]["cwd"] == start["params"]["cwd"]
    assert Path(start["params"]["cwd"]).resolve() == page_dir.resolve()
    [turn] = [m for m in received if m.get("method") == "turn/start"]
    [text] = turn["params"]["input"]
    assert "Why does the export take a minute?" in text["text"]
    assert "Export runs nightly" in text["text"]


def test_a_title_is_drawn_from_the_opening_message_not_the_latest(page_dir, app_server):
    """The turn answers the thread's latest message, which may be an afterthought;
    the title comes from the message that opened it."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Why is the export slow?"},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": comment["id"],
            "text": "also, thanks",
        },
    )
    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    records = []
    thread_titles.name_thread(
        thread_titles.app_server_title(endpoint, None),
        page_dir,
        comment["id"],
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title was never generated")

    [turn] = [m for m in received if m.get("method") == "turn/start"]
    [text] = turn["params"]["input"]
    assert "Why is the export slow?" in text["text"]
    assert "thanks" not in text["text"]


def test_a_generated_title_yields_to_one_the_agent_wrote_first(page_dir):
    """A title that comes back after the agent named the thread is dropped, and a
    thread the agent named is not asked about."""
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )

    def generate(request: str, target: Path) -> dict:
        append_command(
            page_dir,
            {
                "kind": "thread_title",
                "author": "agent",
                "agent": "Leaf guide",
                "session": "hosted-thread",
                "thread": comment["id"],
                "title": "Intro",
            },
        )
        return {"title": "Shorter intro"}

    records = []
    for _ in range(2):
        thread_titles.name_thread(
            generate,
            page_dir,
            comment["id"],
            "hosted-thread",
            lambda event, **fields: records.append((event, fields)),
        )
        for worker in threading.enumerate():
            if worker.name == "leaf-thread-title":
                worker.join(timeout=STATED_TIMEOUT)

    [(event, fields)] = records
    assert (event, fields["written"]) == ("thread_title_generated", False)
    titles = [
        e["title"]
        for e in events_model.read_events(page_dir)
        if e["kind"] == "thread_title"
    ]
    assert titles == ["Intro"]


TITLING_CLAUDE = """\
#!{python}
import json, os, sys
with open(os.environ["TITLING_RECORD"], "a") as record:
    call = {{"argv": sys.argv[1:], "stdin": sys.stdin.read(), "env": dict(os.environ)}}
    record.write(json.dumps(call) + "\\n")
print(json.dumps({{
    "structured_output": {{"title": " Export speed "}},
    "duration_api_ms": 900,
    "usage": {{"input_tokens": 1100, "output_tokens": 60}},
}}))
"""


def test_a_comment_on_a_claude_code_page_is_named_as_it_arrives(
    claimed, tmp_path, monkeypatch
):
    """Claude Code's agent names a thread only when it replies, which can be minutes
    on; its page server asks Haiku for a title as the comment opening the thread
    arrives, in the claimant's voice, with none of the user's customizations, tools
    or session identity."""
    programs = tmp_path / "programs"
    programs.mkdir()
    claude = programs / "claude"
    claude.write_text(TITLING_CLAUDE.format(python=sys.executable))
    claude.chmod(0o755)
    record = tmp_path / "claude-calls.jsonl"
    monkeypatch.setenv("TITLING_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    assert stamp(claimed, "first").exit_code == 0

    status, body = endpoint_model.accept_event(
        claimed,
        {
            "kind": "comment",
            "revision": 1,
            "text": "Why does the export take a minute?",
        },
        dict,
    )
    assert status == 200, body
    titles = wait_for(
        lambda: [
            e for e in events_model.read_events(claimed) if e["kind"] == "thread_title"
        ],
        bool,
        failure="the thread was never named",
    )
    [comment] = [e for e in events_model.read_events(claimed) if e["kind"] == "comment"]
    [title] = titles
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Claude", "s1")

    [call] = [json.loads(line) for line in record.read_text().splitlines()]
    assert "Why does the export take a minute?" in call["stdin"]
    assert "CLAUDE_CODE_SESSION_ID" not in call["env"]
    assert call["env"]["MAX_THINKING_TOKENS"] == "0"
    assert call["env"]["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"

    # The page server's output goes nowhere, so the session's log says what the
    # request did, until the session ends.
    log = leases_model.titles_log("s1")
    [line] = wait_for(
        lambda: log.read_text().splitlines() if log.exists() else [],
        bool,
        failure="the request was never logged",
    )
    logged = json.loads(line)
    assert logged["event"] == "thread_title_generated"
    assert logged["apiDurationMs"] == 900
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "s1"}
    )
    assert not log.exists()


def test_a_comment_on_a_codex_page_is_named_as_it_arrives(
    page_dir, app_server, monkeypatch
):
    """A Codex task's turns may run through `codex queue`, which reaches no model, or
    through an App Server that starts the next turn only once the running one ends;
    either way its page server names the thread as the comment arrives, through an
    App Server of its own that runs none of the user's hooks or MCP servers and
    carries none of the session's identity."""
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    assert stamp(page_dir, "first").exit_code == 0
    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    servers = []

    @contextlib.contextmanager
    def title_server(executable, *, env, arguments):
        servers.append((executable, env, arguments))
        yield endpoint

    monkeypatch.setattr(thread_titles, "private_app_server", title_server)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")

    status, body = endpoint_model.accept_event(
        page_dir,
        {
            "kind": "comment",
            "revision": 1,
            "text": "Why does the export take a minute?",
        },
        dict,
    )
    assert status == 200, body
    [title] = wait_for(
        lambda: [
            e for e in events_model.read_events(page_dir) if e["kind"] == "thread_title"
        ],
        bool,
        failure="the thread was never named",
    )
    assert (title["title"], title["agent"], title["session"]) == (
        "Export speed",
        "Codex",
        "codex-thread",
    )
    [(executable, env, arguments)] = servers
    assert executable == shutil.which("codex")
    assert "CODEX_THREAD_ID" not in env
    # A server with plugins on syncs every marketplace the user configured.
    assert arguments == ("--disable", "plugins")
    [start] = [m for m in received if m.get("method") == "thread/start"]
    assert start["params"]["config"]["features"]["hooks"] is False
    assert start["params"]["config"]["mcp_servers"] == {"docs": {"enabled": False}}
    assert "model" not in start["params"]

    # A reaction opens a thread with no words; the reply that gives it some names it.
    reaction = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "token": "mark"}
    )
    status, body = endpoint_model.accept_event(
        page_dir,
        {
            "kind": "reply",
            "revision": 1,
            "parent": reaction["id"],
            "text": "Can the import run in parallel?",
        },
        dict,
    )
    assert status == 200, body
    wait_for(
        lambda: [
            e
            for e in events_model.read_events(page_dir)
            if e["kind"] == "thread_title" and e["thread"] == reaction["id"]
        ],
        bool,
        failure="the reaction's thread was never named",
    )
    turns = [m for m in received if m.get("method") == "turn/start"]
    assert "Can the import run in parallel?" in turns[-1]["params"]["input"][0]["text"]


def test_a_title_request_that_outlives_its_session_leaves_no_log(claimed):
    """SessionEnd removes the session's titles log, and a request still waiting on
    the model when it runs finishes after that; it writes neither the title nor a
    new log."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    answered = threading.Event()

    def generate(request: str, page_dir: Path) -> dict:
        answered.wait(timeout=STATED_TIMEOUT)
        return {"title": "Intro"}

    thread_titles.name_admitted_thread(generate, claimed, comment["id"], "s1")
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "SessionEnd", "session_id": "s1"}
    )
    answered.set()
    for worker in threading.enumerate():
        if worker.name == "leaf-thread-title":
            worker.join(timeout=STATED_TIMEOUT)

    assert not leases_model.titles_log("s1").exists()
    kinds = [e["kind"] for e in events_model.read_events(claimed)]
    assert "thread_title" not in kinds


def test_both_harnesses_are_asked_for_a_title_in_the_same_words(
    page_dir, app_server, tmp_path, monkeypatch, snapshot
):
    """Claude Code's `claude -p` and a Codex App Server are sent the same system
    prompt, request and answer schema; the snapshot is that request, verbatim."""
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Why does the export take a minute?",
            "anchor": {"section": None, "quote": "Export runs nightly"},
        },
    )
    _, request = thread_titles.title_request(page_dir, comment["id"])

    programs = tmp_path / "programs"
    programs.mkdir()
    claude = programs / "claude"
    claude.write_text(TITLING_CLAUDE.format(python=sys.executable))
    claude.chmod(0o755)
    record = tmp_path / "claude-calls.jsonl"
    monkeypatch.setenv("TITLING_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    thread_titles.claude_code_title(request, page_dir)
    [call] = [json.loads(line) for line in record.read_text().splitlines()]
    argv = call["argv"]
    system_prompt = argv[argv.index("--system-prompt") + 1]
    schema = json.loads(argv[argv.index("--json-schema") + 1])

    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    thread_titles.app_server_title(endpoint, None)(request, page_dir)
    [start] = [m for m in received if m.get("method") == "thread/start"]
    [turn] = [m for m in received if m.get("method") == "turn/start"]
    assert start["params"]["baseInstructions"] == system_prompt
    assert turn["params"]["input"] == [{"type": "text", "text": call["stdin"]}]
    assert turn["params"]["outputSchema"] == schema

    placeholders = {system_prompt: "<system_prompt>", json.dumps(schema): "<schema>"}
    snapshot.check(
        yaml_document(
            "What Claude Code's page server runs, what it and a Codex App Server "
            "both send, and\nthe App Server's titling thread, for a thread opened "
            "on a passage.",
            {
                "command": ["claude", *(placeholders.get(a, a) for a in argv)],
                "system_prompt": Prose(system_prompt),
                "request": Prose(call["stdin"]),
                "schema": schema,
                "app_server_thread": {
                    key: start["params"][key]
                    for key in ("ephemeral", "approvalPolicy", "sandbox", "config")
                },
                "app_server_effort": turn["params"]["effort"],
            },
        )
    )
