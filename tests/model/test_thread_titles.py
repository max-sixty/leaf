"""Thread titles: the title a page server asks a model for as a thread's opening
comment arrives, under Claude Code, Codex and Pi alike, and the App Server it
holds open for one."""

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
    claude_code_module,
    record_claim,
    stamp,
    wait_for,
    yaml_document,
)

from leaf import codex as codex_model
from leaf import completions, inference, thread_titles
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import interaction_log as interaction_model
from leaf import state as cleanup_model
from leaf.thread import fit_title

# What Codex's turn reports when the account cannot use the model it asks for.
UNAVAILABLE_MODEL = {
    "message": (
        "The 'gpt-6-luna' model is not supported when using Codex with a ChatGPT "
        "account."
    ),
    "codexErrorInfo": "other",
}
# What it reports when the model refuses the turn for rate limits (codex-cli 0.160).
RATE_LIMITED = {
    "message": "exceeded retry limit, last status: 429 Too Many Requests",
    "codexErrorInfo": {"responseTooManyFailedAttempts": {"httpStatusCode": 429}},
    "additionalDetails": None,
}


def title_records(page_dir: Path) -> list[dict]:
    """What the page server recorded of each title it asked for, in the page's
    diagnostics."""
    return [
        row
        for row in interaction_model.read_interactions(page_dir)
        if row["source"] == "server" and row["type"].startswith("thread_title")
    ]


def titling_app_server(
    app_server, answer: str | None, refusals: int = 0
) -> tuple[str, list[dict]]:
    """An App Server that answers each titling thread with `answer`, or fails its
    turn as an account without the title model does where `answer` is None. Its
    first `refusals` turns are refused for rate limits instead."""
    received = []
    refused = []

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
                completed = {"id": "t", "items": [], "status": "completed"}
                if len(refused) < refusals or answer is None:
                    error = UNAVAILABLE_MODEL
                    if len(refused) < refusals:
                        refused.append(message)
                        error = RATE_LIMITED
                    completed = {
                        "id": "t",
                        "items": [],
                        "status": "failed",
                        "error": error,
                    }
                else:
                    item = {"id": "title", "type": "agentMessage", "text": answer}
                    socket.send(
                        json.dumps(
                            {
                                "method": "item/completed",
                                "params": {
                                    "threadId": "title-thread",
                                    "turnId": "t",
                                    "item": item,
                                    "completedAtMs": 0,
                                },
                            }
                        )
                    )
                socket.send(
                    json.dumps(
                        {
                            "method": "turn/completed",
                            "params": {"threadId": "title-thread", "turn": completed},
                        }
                    )
                )

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
        thread_titles.app_server_title(endpoint),
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
    # The website's tasks run on a model of their own; its titles do not.
    assert start["params"]["model"] == inference.CODEX_MODEL
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
        thread_titles.app_server_title(endpoint),
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


def test_a_title_the_model_refuses_leaves_the_thread_to_the_agent(page_dir, app_server):
    """An account without the title model fails the title's turn: the thread stays
    untitled, so the agent's answer is asked to name it, and the record says why."""
    comment = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "text": "Why is the export slow?"},
    )
    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    endpoint, _ = titling_app_server(app_server, None)
    records = []
    thread_titles.name_thread(
        thread_titles.app_server_title(endpoint),
        page_dir,
        comment["id"],
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title request never reported")

    [(event, fields)] = records
    assert (event, fields["error"]) == ("thread_title_failed", "RuntimeError")
    assert UNAVAILABLE_MODEL["message"] in fields["detail"]
    kinds = [e["kind"] for e in events_model.read_events(page_dir)]
    assert "thread_title" not in kinds


def test_a_title_refused_for_rate_limits_is_asked_again_until_its_cap(
    page_dir, app_server, monkeypatch
):
    """A burst of comments meets the title model's rate limit, and an App Server
    turn's final message can't name the thread, so a refused title is asked again
    until it is answered. One refused past the cap fails, so a title never retries
    forever."""
    monkeypatch.setattr(thread_titles, "RETRY_INTERVAL", 0.01)

    def name(comment, endpoint):
        records = []
        thread_titles.name_thread(
            thread_titles.app_server_title(endpoint),
            page_dir,
            comment["id"],
            "hosted-thread",
            lambda event, **fields: records.append((event, fields)),
        )
        [(event, fields)] = wait_for(
            lambda: records, bool, failure="the title request never reported"
        )
        return event, fields

    answered = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Why is it slow?"}
    )
    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    endpoint, received = titling_app_server(
        app_server, '{"title": "Export speed"}', refusals=2
    )
    event, fields = name(answered, endpoint)
    assert (event, fields["written"], fields["refusals"]) == (
        "thread_title_generated",
        True,
        2,
    )
    # Each ask is a thread of its own, holding only the request.
    assert len([m for m in received if m.get("method") == "thread/start"]) == 3

    monkeypatch.setattr(thread_titles, "RETRY_FOR", 0.05)
    capped = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "And the import?"}
    )
    endpoint, _ = titling_app_server(app_server, '{"title": "Import"}', refusals=1000)
    event, fields = name(capped, endpoint)
    assert (event, fields["error"]) == ("thread_title_failed", "RateLimited")
    titled = {
        e["thread"]
        for e in events_model.read_events(page_dir)
        if e["kind"] == "thread_title"
    }
    assert titled == {answered["id"]}


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


def test_a_generated_title_is_fitted_to_a_thread_title(page_dir):
    """A model can't count characters or keep to one line, so a generated title past
    the limit, or broken over lines, is fitted as the clerk's are rather than refused,
    which would leave the thread untitled."""
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("hosted-thread", "Leaf guide", os.getpid()),
    )
    words = "Tightening\nthe " + "long introduction " * 8
    records = []
    thread_titles.name_thread(
        lambda request, target: {"title": words},
        page_dir,
        comment["id"],
        "hosted-thread",
        lambda event, **fields: records.append((event, fields)),
    )
    wait_for(lambda: records, bool, failure="the title request never reported")

    [(event, fields)] = records
    assert (event, fields.get("written")) == ("thread_title_generated", True)
    [title] = [
        e["title"]
        for e in events_model.read_events(page_dir)
        if e["kind"] == "thread_title"
    ]
    assert title == fit_title(words)
    assert title.startswith("Tightening the long introduction") and title.endswith("…")


def test_a_comment_on_a_claude_code_page_is_named_as_it_arrives(claimed):
    """Claude Code's agent names a thread only when it replies, which can be minutes
    on; its page server asks Haiku for a title as the comment opening the thread
    arrives, through the claimant session's own model client, which Leaf's hooks
    module calls, and writes it in the claimant's voice."""
    assert stamp(claimed, "first").exit_code == 0

    with claude_code_module("s1", '{"title": " Export speed "}') as asked:
        status, body = endpoint_model.accept_event(
            claimed,
            {
                "kind": "comment",
                "revision": 1,
                "text": "Why does the export take a minute?",
            },
        )
        assert status == 200, body
        titles = wait_for(
            lambda: [
                e
                for e in events_model.read_events(claimed)
                if e["kind"] == "thread_title"
            ],
            bool,
            failure="the thread was never named",
        )
    [comment] = [e for e in events_model.read_events(claimed) if e["kind"] == "comment"]
    [title] = titles
    assert (title["thread"], title["title"]) == (comment["id"], "Export speed")
    assert (title["agent"], title["session"]) == ("Claude", "s1")

    [request] = asked
    assert request["request"]["model"] == "haiku"
    assert "Why does the export take a minute?" in request["request"]["prompt"]
    # The page server stops waiting a little after the model's own time limit.
    assert request["request"]["timeoutMs"] < inference.TIMEOUT * 1000
    assert completions.pending("s1") == []

    # The page server's output goes nowhere, so the page's diagnostics say what the
    # request did.
    [logged] = wait_for(
        lambda: title_records(claimed), bool, failure="the request was never logged"
    )
    assert logged["type"] == "thread_title_generated"
    assert (logged["model"], logged["apiDurationMs"]) == ("haiku", 900)
    assert (logged["inputTokens"], logged["outputTokens"]) == (300, 12)


def test_a_claude_code_completion_that_gets_no_answer_says_why(page_dir, monkeypatch):
    """A provider's 429 to the session's model reads as a rate limit, which a title
    asks again; a session whose module answers nothing, as one whose Claude Code
    process isn't running, fails the request at its deadline, and a reply after
    that finds nothing to answer, so no request is left either way."""
    import pytest

    generate = inference.claude_code_generator("s1")
    limited = {"failed": "api-error", "status": 429, "error": "rate_limit"}
    with claude_code_module("s1", limited), pytest.raises(inference.RateLimited):
        generate("Pick", page_dir, schema=thread_titles.OUTPUT_SCHEMA, instructions="")

    requests = cleanup_model.session_file("s1", "completion.*")
    monkeypatch.setattr(inference, "TIMEOUT", 0.2)
    monkeypatch.setattr(completions, "GRACE_S", 0.1)
    with pytest.raises(TimeoutError):
        generate("Pick", page_dir, schema=thread_titles.OUTPUT_SCHEMA, instructions="")
    assert list(requests.parent.glob(requests.name)) == []
    completions.cmd_reply("s1", {"completion": "a" * 32, "text": "{}"})
    assert list(requests.parent.glob(requests.name)) == []


def test_a_comment_on_a_codex_page_is_named_as_it_arrives(
    page_dir, app_server, monkeypatch
):
    """A Codex task's turns may run through `codex queue`, which reaches no model, or
    through an App Server that starts the next turn only once the running one ends;
    either way its page server names the thread as the comment arrives, through an
    App Server of its own that runs none of the user's hooks or MCP servers and
    carries none of the session's identity. Each request starts and closes its own
    server, leaving none idle between comments."""
    record_claim(page_dir, id="codex-thread", harness="codex", agent="Codex")
    assert stamp(page_dir, "first").exit_code == 0
    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    servers = []
    stopped = []

    @contextlib.contextmanager
    def title_server(executable, *, env, arguments):
        servers.append((executable, env, arguments))
        try:
            yield endpoint, None
        finally:
            stopped.append(executable)

    monkeypatch.setattr(inference, "private_app_server", title_server)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    status, body = endpoint_model.accept_event(
        page_dir,
        {
            "kind": "comment",
            "revision": 1,
            "text": "Why does the export take a minute?",
        },
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
    assert start["params"]["model"] == inference.CODEX_MODEL

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
    wait_for(
        lambda: title_records(page_dir),
        lambda records: len(records) == 2,
        failure="the second title was never logged",
    )
    assert len(servers) == len(stopped) == 2, "Each title owns its server lifetime"


# Pi's records in `--mode json`: a run that failed and that Pi retries, then the
# retry's; then a Pi that lingers after answering, as the real one does for some 3 s.
TITLING_PI = """\
#!{python}
import json, os, sys, time
argv = sys.argv[1:]
with open(argv[argv.index("--system-prompt") + 1]) as prompt:
    system_prompt = prompt.read()
with open(os.environ["TITLING_RECORD"], "a") as record:
    call = {{
        "argv": argv,
        "system_prompt": system_prompt,
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
    "content": [{{"type": "text", "text": '{{"title": " Export speed "}}'}}],
    "provider": "openai-codex",
    "model": "gpt-6.1-sol",
    "usage": {{
        "input": 200,
        "output": 7,
        "cacheRead": 0,
        "cacheWrite": 0,
        "cost": {{"total": 0.00048}},
    }},
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
    monkeypatch.setattr(inference, "TIMEOUT", 3600)

    status, body = endpoint_model.accept_event(
        page_dir,
        {
            "kind": "comment",
            "revision": 1,
            "text": "Why does the export take a minute?",
        },
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
    # Pi has no answer schema, so the system prompt carries it.
    assert call["system_prompt"].startswith(thread_titles.INSTRUCTIONS + "\n\n")
    assert json.dumps(thread_titles.OUTPUT_SCHEMA) in call["system_prompt"]
    # Pi's hooks are extensions, Leaf's own among them.
    for switch in ("--print", "--no-session", "--no-tools", "--no-extensions"):
        assert switch in argv
    # Pi adds an APPEND_SYSTEM.md to the system prompt unless one is given.
    assert argv[argv.index("--append-system-prompt") + 1] == ""

    [logged] = wait_for(
        lambda: title_records(page_dir), bool, failure="the request was never logged"
    )
    assert logged["type"] == "thread_title_generated"
    assert (logged["model"], logged["costUsd"]) == ("openai-codex/gpt-6.1-sol", 0.00048)


def test_a_title_request_that_outlives_its_session_writes_no_title(claimed):
    """A request still waiting on the model when its session ends finishes after
    that, as a session no longer holding the page: it writes no title, and the
    page's diagnostics say so."""
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Tighten the intro"}
    )
    answered = threading.Event()

    def generate(request: str, page_dir: Path) -> dict:
        answered.wait(timeout=STATED_TIMEOUT)
        return {"title": "Intro"}

    thread_titles.name_admitted_thread(generate, claimed, comment["id"], "s1")
    cleanup_model.end_harness_instance("s1")
    answered.set()
    for worker in threading.enumerate():
        if worker.name == "leaf-thread-title":
            worker.join(timeout=STATED_TIMEOUT)

    [logged] = title_records(claimed)
    assert (logged["type"], logged["written"]) == ("thread_title_generated", False)
    kinds = [e["kind"] for e in events_model.read_events(claimed)]
    assert "thread_title" not in kinds


def test_both_harnesses_are_asked_for_a_title_in_the_same_words(
    page_dir, app_server, snapshot
):
    """A Claude Code session's completion and a Codex App Server are sent the same
    instructions, request and answer schema, which the completion, taking no answer
    schema, reads at the end of its system prompt; the snapshot is that request,
    verbatim."""
    comment = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Why does the export take a minute?",
            "anchor": {"section": None, "quote": "Export runs nightly"},
        },
    )
    title_request_result = thread_titles.title_request(page_dir, comment["id"])
    assert title_request_result is not None
    _, request = title_request_result

    with claude_code_module("s1", '{"title": "Export speed"}') as asked:
        thread_titles.title_generator(inference.claude_code_generator("s1"))(
            request, page_dir
        )
    [completion] = [each["request"] for each in asked]

    endpoint, received = titling_app_server(app_server, '{"title": "Export speed"}')
    thread_titles.app_server_title(endpoint)(request, page_dir)
    [start] = [m for m in received if m.get("method") == "thread/start"]
    [turn] = [m for m in received if m.get("method") == "turn/start"]
    instructions = start["params"]["baseInstructions"]
    schema = turn["params"]["outputSchema"]
    assert completion["system"].startswith(instructions)
    assert turn["params"]["input"] == [{"type": "text", "text": completion["prompt"]}]

    snapshot.check(
        yaml_document(
            "What a Claude Code session's module and a Codex App Server are asked "
            "for a thread opened on\na passage, and the App Server's titling thread.",
            {
                "instructions": Prose(instructions),
                "request": Prose(completion["prompt"]),
                "schema": schema,
                "claude_code_completion": {
                    **{
                        key: completion[key]
                        for key in ("model", "maxTokens", "timeoutMs")
                    },
                    "system": Prose(completion["system"]),
                },
                "app_server_thread": {
                    key: start["params"][key]
                    for key in (
                        "model",
                        "ephemeral",
                        "approvalPolicy",
                        "sandbox",
                        "config",
                    )
                },
                "app_server_effort": turn["params"]["effort"],
            },
        )
    )


def test_shared_inference_checks_structured_results(page_dir, app_server):
    """Widgets and titles use the same tool-free transports, with the host's model
    and caller's schema; an answer outside that schema must not reach the caller."""
    import pytest
    from jsonschema import ValidationError

    schema = {
        "type": "object",
        "properties": {"choice": {"type": "integer"}},
        "required": ["choice"],
        "additionalProperties": False,
    }
    endpoint, received = titling_app_server(app_server, '{"choice": 7}')
    with claude_code_module("s1", '{"choice": 7}'):
        for generate in (
            inference.claude_code_generator("s1"),
            inference.app_server_generate(endpoint),
        ):
            result = generate(
                "Pick an item",
                page_dir,
                schema=schema,
                instructions="Choose one item",
            )
            assert result["value"] == {"choice": 7}
            assert result["model"] in {"haiku", inference.CODEX_MODEL}
            assert set(result["usage"]) == {"inputTokens", "outputTokens"}
            with pytest.raises(ValidationError):
                generate(
                    "Pick an item",
                    page_dir,
                    schema=thread_titles.OUTPUT_SCHEMA,
                    instructions="Choose one item",
                )
    start = next(m for m in received if m.get("method") == "thread/start")
    assert start["params"]["model"] == inference.CODEX_MODEL
    assert start["params"]["baseInstructions"] == "Choose one item"
    assert start["params"]["config"]["features"]["shell_tool"] is False
    assert start["params"]["config"]["mcp_servers"] == {"docs": {"enabled": False}}
