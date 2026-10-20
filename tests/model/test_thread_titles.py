"""Thread titles: the title a page server asks a model for as a thread's opening
comment arrives, under Claude Code, Codex and Pi alike, and the App Server it
holds open for one."""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import psutil
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
from leaf import state as state_model
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
    carries none of the session's identity. That server and its thread start before
    the comment arrives, while the Codex session holds the page and again once each
    title is answered, since starting them is most of a title's time."""
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    assert stamp(page_dir, "first").exit_code == 0
    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    servers = []

    @contextlib.contextmanager
    def title_server(executable, *, env, arguments):
        servers.append((executable, env, arguments))
        yield endpoint

    monkeypatch.setattr(thread_titles, "private_app_server", title_server)
    monkeypatch.setattr(thread_titles, "_next_codex_titles", {})
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    thread_titles.prepare_for_claimant(page_dir)
    wait_for(
        lambda: [m for m in received if m.get("method") == "thread/start"],
        bool,
        failure="the title thread was never started",
    )

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
    (executable, env, arguments), *_ = servers
    assert executable == shutil.which("codex")
    assert "CODEX_THREAD_ID" not in env
    # A server with plugins on syncs every marketplace the user configured.
    assert arguments == ("--disable", "plugins")
    start, *_ = [m for m in received if m.get("method") == "thread/start"]
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
    log = leases_model.titles_log("codex-thread")
    records = wait_for(
        lambda: [json.loads(line) for line in log.read_text().splitlines()],
        lambda records: len(records) == 2,
        failure="the second title was never logged",
    )
    assert [record["prepared"] for record in records] == [True, True]
    wait_for(
        lambda: len(servers),
        lambda count: count == 3,
        failure="the next title's server was never started",
    )


def test_a_codex_title_server_that_fails_to_start_leaves_the_title_to_a_new_one(
    page_dir, app_server, monkeypatch
):
    """A title server started ahead of the comment that then fails to start,
    whether before the comment or while the comment waits on it, asked nothing, so
    the title is asked on a server started then."""
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    assert stamp(page_dir, "first").exit_code == 0
    endpoint, _ = titling_app_server(app_server, '{"title": "Export speed"}')
    starts = []
    released = threading.Event()

    @contextlib.contextmanager
    def title_server(executable, *, env, arguments):
        starts.append(executable)
        if len(starts) == 1:
            released.wait()
            raise codex_model.Refused("Codex App Server exited before it was ready")
        yield endpoint

    monkeypatch.setattr(thread_titles, "private_app_server", title_server)
    monkeypatch.setattr(thread_titles, "_next_codex_titles", {})
    thread_titles.prepare_for_claimant(page_dir)

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
    # The comment's request has taken the server still starting.
    wait_for(
        lambda: thread_titles._next_codex_titles,
        lambda prepared: not prepared,
        failure="the comment never took the prepared server",
    )
    # The comment's write wakes the page server's follower, which starts the next
    # title's server only once this title is answered.
    thread_titles.prepare_for_claimant(page_dir)
    assert not thread_titles._next_codex_titles
    released.set()
    wait_for(
        lambda: [
            e for e in events_model.read_events(page_dir) if e["kind"] == "thread_title"
        ],
        bool,
        failure="the thread was never named",
    )
    log = leases_model.titles_log("codex-thread")
    [record] = wait_for(
        lambda: [json.loads(line) for line in log.read_text().splitlines()],
        bool,
        failure="the title was never logged",
    )
    assert record["prepared"] is False


# An App Server that opens a title thread and records its pid, so a test can see
# whether it runs.
OPENING_CODEX = """\
#!{python}
import json, os, sys
from websockets.sync.server import unix_serve

RESULTS = {{
    "initialize": {{}},
    "config/read": {{"config": {{}}}},
    "thread/start": {{"thread": {{"id": "title-thread"}}}},
}}

def handle(connection):
    for raw in connection:
        message = json.loads(raw)
        if (result := RESULTS.get(message.get("method"))) is not None:
            connection.send(json.dumps({{"id": message["id"], "result": result}}))

with open(os.environ["TITLE_SERVERS"], "a") as record:
    record.write(f"{{os.getpid()}}\\n")
with unix_serve(handle, sys.argv[3].removeprefix("unix://")) as server:
    server.serve_forever()
"""


def test_a_codex_title_server_runs_while_a_codex_session_holds_the_page(
    page_dir, tmp_path, monkeypatch, spawn
):
    """A page server holds the next title's App Server only for a Codex claimant:
    it starts one when a Codex session claims a page it already serves, and stops
    it when a Claude Code session takes the page, which titles with Haiku, or the
    Codex session ends, rather than leave an idle server of some 100 MB behind."""
    programs = tmp_path / "programs"
    programs.mkdir()
    codex = programs / "codex"
    codex.write_text(OPENING_CODEX.format(python=sys.executable))
    codex.chmod(0o755)
    started = tmp_path / "title-servers"
    monkeypatch.setenv("TITLE_SERVERS", str(started))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")

    def servers() -> list[int]:
        return (
            [int(pid) for pid in started.read_text().split()]
            if started.exists()
            else []
        )

    record_claim(page_dir, id="s1", harness="claude-code", agent="Claude")
    # The page server's follower, run in a process of its own as it is there, until
    # its stdin closes. Its exit then stops the title server it holds, as a page
    # server's does.
    follow = """
import sys, threading
from pathlib import Path
from leaf.thread_titles import follow_claimant
page = Path(sys.argv[1])
threading.Thread(target=follow_claimant, args=(page,), daemon=True).start()
sys.stdin.read()
"""
    follower = spawn(
        [sys.executable, "-c", follow, str(page_dir)], stdin=subprocess.PIPE
    )
    try:
        endings = {
            "Claude Code took the page": lambda: record_claim(
                page_dir, id="s1", harness="claude-code", agent="Claude"
            ),
            "the Codex session ended": lambda: state_model.end_session("codex-thread"),
        }
        for claims, (ending, end) in enumerate(endings.items(), start=1):
            record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
            *_, pid = wait_for(
                servers,
                lambda pids, claims=claims: len(pids) == claims,
                failure="no title server started for the Codex claim",
            )
            assert psutil.pid_exists(pid)
            end()
            wait_for(
                lambda pid=pid: psutil.pid_exists(pid),
                lambda running: not running,
                failure=f"the title server ran on after {ending}",
            )
    finally:
        follower.stdin.close()
        follower.wait(timeout=STATED_TIMEOUT)


# Pi's records in `--mode json`: a run that failed and that Pi retries, then the
# retry's; then a Pi that lingers after answering, as the real one does for some 3 s.
TITLING_PI = """\
#!{python}
import json, os, sys, time
with open(os.environ["TITLING_RECORD"], "a") as record:
    call = {{
        "argv": sys.argv[1:],
        "stdin": sys.stdin.read(),
        "env": dict(os.environ),
        "cwd": os.getcwd(),
    }}
    record.write(json.dumps(call) + "\\n")
failed = {{
    "role": "assistant",
    "content": [],
    "stopReason": "error",
    "errorMessage": "overloaded",
}}
answer = {{
    "role": "assistant",
    "content": [{{"type": "text", "text": " Export speed "}}],
    "provider": "openai-codex",
    "model": "gpt-6.1-sol",
    "usage": {{"input": 200, "output": 7, "cost": {{"total": 0.00048}}}},
    "stopReason": "stop",
}}
for record in (
    {{"type": "session", "id": "title-session"}},
    {{"type": "agent_end", "messages": [failed], "willRetry": True}},
    {{"type": "message_end", "message": answer}},
    {{"type": "agent_end", "messages": [answer], "willRetry": False}},
):
    print(json.dumps(record), flush=True)
time.sleep(3600)
"""


def test_a_comment_on_a_pi_page_is_named_as_it_arrives(page_dir, tmp_path, monkeypatch):
    """Pi's agent names a thread only when it replies; its page server asks Pi's
    configured model for a title as the comment opening the thread arrives, in a
    print-mode run with none of the user's tools, extensions, hooks or session
    identity, and takes the answer as soon as Pi prints it, after any retry and
    without waiting for Pi to exit."""
    record_claim(page_dir, id="pi-session", harness="pi", agent="Pi")
    assert stamp(page_dir, "first").exit_code == 0
    programs = tmp_path / "programs"
    programs.mkdir()
    pi = programs / "pi"
    pi.write_text(TITLING_PI.format(python=sys.executable))
    pi.chmod(0o755)
    record = tmp_path / "pi-calls.jsonl"
    monkeypatch.setenv("TITLING_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PI_SESSION_ID", "pi-session")
    monkeypatch.setenv("LEAF_PI_PID", str(os.getpid()))
    # Only the answer, never Pi's exit, can end the request within the wait below.
    monkeypatch.setattr(thread_titles, "TIMEOUT", 3600)

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
    [comment] = [
        e for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    ]
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Pi", "pi-session")

    [call] = [json.loads(line) for line in record.read_text().splitlines()]
    assert "Why does the export take a minute?" in call["stdin"]
    assert "PI_SESSION_ID" not in call["env"]
    assert "LEAF_PI_PID" not in call["env"]
    assert Path(call["cwd"]).resolve() == page_dir.resolve()
    argv = call["argv"]
    assert argv[argv.index("--system-prompt") + 1] == thread_titles.INSTRUCTIONS
    # Pi's hooks are extensions, Leaf's own among them.
    for switch in ("--print", "--no-session", "--no-tools", "--no-extensions"):
        assert switch in argv
    # Pi adds an APPEND_SYSTEM.md to the system prompt unless one is given.
    assert argv[argv.index("--append-system-prompt") + 1] == ""

    log = leases_model.titles_log("pi-session")
    [line] = wait_for(
        lambda: log.read_text().splitlines() if log.exists() else [],
        bool,
        failure="the request was never logged",
    )
    logged = json.loads(line)
    assert logged["event"] == "thread_title_generated"
    assert (logged["model"], logged["costUsd"]) == ("openai-codex/gpt-6.1-sol", 0.00048)


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
