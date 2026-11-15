"""Tool-free, schema-constrained inference through the host's existing login.

Codex uses an ephemeral App Server thread, Claude Code a completion on the claimant
session's own model client, which Leaf's hooks module makes (`completions`), and Pi
a print run with nothing the user installed. None loads tools or the agent's
conversation. Claude Code puts its identity block before the system prompt, and the
session's other plugins can hook the completion. The host fixes the model; callers
supply input, instructions and a required JSON Schema. Results contain value, model,
usage and duration metadata. This layer neither retries requests nor collects or
persists page data; callers own those policies.

Codex constrains the answer to the schema. Claude Code's completion and Pi take no
answer schema, so the system prompt carries it (`answering`), and the answer is
parsed and validated here (`answered`); an answer that is not JSON matching the
schema fails the request as any other failure does.
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from . import completions
from .codex import (
    app_server_connect,
    app_server_handshake,
    app_server_request,
    private_app_server,
)
from .harness import IDENTITY_VARIABLES
from .registry.schema import json_validator

TIMEOUT = 60


class RateLimited(RuntimeError):
    """The provider refused the request for rate limits (HTTP 429)."""


# Disable tools, plugins, hooks and project instructions. With tools, a title
# request sometimes acted on the quoted message; hooks retitled the user’s
# terminal tab. Codex can still load
# its home AGENTS.md. Luna accepts `none` effort but not `minimal`
# (codex-cli 0.160); an unavailable host model fails the request.
CODEX_MODEL = "gpt-6-luna"
APP_SERVER_EFFORT = "none"
CODEX_CONFIG = {
    "features": {
        feature: False
        for feature in (
            "apps",
            "browser_use",
            "computer_use",
            "goals",
            "image_generation",
            "in_app_browser",
            "memories",
            "multi_agent",
            "plugins",
            "skill_mcp_dependency_install",
            "skill_search",
            "tool_suggest",
            "workspace_dependencies",
            "code_mode_host",
            "hooks",
            "shell_tool",
            "sleep_tool",
            "unified_exec",
            "view_image",
        )
    },
    "skills": {"include_instructions": False, "max_context_tokens": 1},
    "web_search": "disabled",
    "include_apply_patch_tool": False,
    "agents": {"enabled": False},
    "project_doc_max_bytes": 0,
    "model_reasoning_effort": APP_SERVER_EFFORT,
}
# Disable plugins at server startup too: a thread override comes after the server
# syncs the user's marketplaces, causing unrelated network and filesystem work.
CODEX_SERVER_ARGUMENTS = ("--disable", "plugins")
# What a model that takes no answer schema is told after the caller's instructions.
JSON_ANSWER = (
    "Answer with one JSON value and nothing else: no prose before or after it, and "
    "no Markdown code fence around it. The value must match this JSON Schema:\n"
)


def answering(instructions: str, schema: dict) -> str:
    """The system prompt of a model that takes no answer schema: the caller's
    instructions, then the schema its answer must match."""
    return "\n\n".join(filter(None, [instructions, JSON_ANSWER + json.dumps(schema)]))


def answered(text: str, schema: dict, host: str) -> object:
    """The JSON value `text` holds, checked against `schema`. Prose can echo the
    user's words, so it stays out of the error."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{host}'s answer is not JSON ({error.msg})") from None
    json_validator(schema).validate(value)
    return value


# The model Claude Code is asked on, whatever model the session runs. The request
# names no effort, and Haiku thought over none of the titles measured below (a median
# 20 tokens out); thinking had made its titles slower (3–7 s versus 1–2 s) without
# better results.
CLAUDE_CODE_MODEL = "haiku"
# The most one reply can hold, claude-haiku-5-5's limit and `$.model.complete`'s
# (Claude Code 2.1.322), so the time limit ends a long answer, such as a widget's
# code, rather than the default cap of 1024 tokens.
CLAUDE_CODE_MAX_TOKENS = 64_000


def claude_code_generator(session_id: str) -> Callable[..., dict]:
    """Ask for structured JSON through the Claude Code session `session_id`, on its
    own model client, credentials and provider: a completion Leaf's hooks module
    makes (`completions`), with no tools, history or system prompt beyond Claude
    Code's identity block and the one given.

    Told the schema in the system prompt (`answering`), Haiku answered 392 of 392
    thread titles asked of real pages' threads with JSON matching it, in a median
    1.5 s (p90 2.2 s); asked for the title as plain text, it prefaced 4 with its
    reasoning about the request (Claude Code 2.1.322)."""

    def generate(
        request: str,
        page_dir: Path,
        *,
        schema: dict,
        instructions: str,
    ) -> dict:
        started = time.monotonic()
        reply = completions.ask(
            session_id,
            {
                "model": CLAUDE_CODE_MODEL,
                "system": answering(instructions, schema),
                "prompt": request,
                "maxTokens": CLAUDE_CODE_MAX_TOKENS,
                "timeoutMs": round((TIMEOUT - completions.GRACE_S) * 1000),
            },
            timeout=TIMEOUT,
        )
        if "text" not in reply:
            status = reply.get("status")
            raise (RateLimited if status == 429 else RuntimeError)(
                f"the completion gave no answer: {reply.get('failed')}"
                + (f" (HTTP {status}: {reply.get('error')})" if status else "")
            )
        usage = reply["usage"]
        return {
            "value": answered(reply["text"], schema, "Claude Code"),
            "model": CLAUDE_CODE_MODEL,
            "durationMs": round((time.monotonic() - started) * 1000),
            # The model call's share of `durationMs`, as the module timed it; the
            # rest is the relay through the session's pages follower and the module.
            "apiDurationMs": reply["elapsed_ms"],
            "usage": {
                "inputTokens": usage["input_tokens"]
                + usage["cache_read_input_tokens"]
                + usage["cache_creation_input_tokens"],
                "outputTokens": usage["output_tokens"],
            },
        }

    return generate


def open_thread(socket, page_dir: Path, instructions: str) -> str:
    """Open the ephemeral thread one request is asked on, on Luna, over
    a new connection to an App Server, run in the page directory, and return its
    id."""
    app_server_handshake(socket, 0, "leaf-inference", "Leaf inference")
    # A thread starts every MCP server the user configured, its project's included,
    # and an override replacing the table leaves them configured, so each is turned
    # off by name, read from the directory the thread runs in.
    configured = app_server_request(socket, "config/read", 1, {"cwd": str(page_dir)})
    servers = configured["config"].get("mcp_servers") or {}
    thread = app_server_request(
        socket,
        "thread/start",
        2,
        {
            "model": CODEX_MODEL,
            "cwd": str(page_dir),
            "ephemeral": True,
            "approvalPolicy": "never",
            # A sandbox confines only the tools a turn runs, and this one has none,
            # so the request also works where Codex cannot start one, as in the
            # website's container.
            "sandbox": "read-only",
            "baseInstructions": instructions,
            "config": {
                **CODEX_CONFIG,
                "mcp_servers": {name: {"enabled": False} for name in servers},
            },
        },
    )
    return thread["thread"]["id"]


def ask(socket, thread_id: str, request: str, schema: dict, deadline: float) -> dict:
    """Ask for structured JSON in one turn on the thread `open_thread` opened, and read
    the answer by `deadline` (`time.monotonic`)."""
    # A thread that took longer to open than the request waits asks nothing.
    if time.monotonic() >= deadline:
        raise TimeoutError(f"no structured answer within {TIMEOUT} s")
    app_server_request(
        socket,
        "turn/start",
        3,
        {
            "threadId": thread_id,
            "input": [{"type": "text", "text": request}],
            "effort": APP_SERVER_EFFORT,
            "outputSchema": schema,
        },
    )
    answer = None
    usage = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no structured answer within {TIMEOUT} s")
        message = json.loads(socket.recv(timeout=remaining))
        params = message.get("params") or {}
        if params.get("threadId") != thread_id:
            continue
        method = message.get("method")
        if method == "item/completed" and params["item"]["type"] == "agentMessage":
            answer = params["item"]["text"]
        elif method == "thread/tokenUsage/updated":
            usage = params["tokenUsage"]["last"]
        elif method == "turn/completed":
            turn = params["turn"]
            if turn["status"] != "completed" or answer is None:
                # Each variant of a failure's `codexErrorInfo` that has an HTTP
                # status carries it as `httpStatusCode`.
                info = (turn.get("error") or {}).get("codexErrorInfo")
                limited = isinstance(info, dict) and any(
                    variant.get("httpStatusCode") == 429 for variant in info.values()
                )
                raise (RateLimited if limited else RuntimeError)(
                    f"the inference turn ended {turn['status']}: {turn.get('error')}"
                )
            value = json.loads(answer)
            json_validator(schema).validate(value)
            return {
                "value": value,
                "usage": {
                    "inputTokens": usage and usage["inputTokens"],
                    "outputTokens": usage and usage["outputTokens"],
                },
            }


def app_server_generate(endpoint: str) -> Callable[..., dict]:
    """A structured request as an ephemeral thread on the App Server at
    `endpoint`, run in the page directory."""

    def generate(
        request: str,
        page_dir: Path,
        *,
        schema: dict,
        instructions: str,
    ) -> dict:
        started = time.monotonic()
        socket = app_server_connect(endpoint)
        try:
            thread_id = open_thread(socket, page_dir, instructions)
            reading = ask(socket, thread_id, request, schema, started + TIMEOUT)
        finally:
            socket.close()
        return {
            **reading,
            "model": CODEX_MODEL,
            "durationMs": round((time.monotonic() - started) * 1000),
        }

    return generate


def codex_generate(
    request: str,
    page_dir: Path,
    *,
    schema: dict,
    instructions: str,
) -> dict:
    """Ask Codex on demand; no server remains idle between requests."""
    started = time.monotonic()
    executable = shutil.which("codex")
    if executable is None:
        raise FileNotFoundError("no `codex` on PATH")
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in IDENTITY_VARIABLES
    }
    with private_app_server(executable, env=env, arguments=CODEX_SERVER_ARGUMENTS) as (
        endpoint,
        _process,
    ):
        reading = app_server_generate(endpoint)(
            request, page_dir, schema=schema, instructions=instructions
        )
    return {**reading, "durationMs": round((time.monotonic() - started) * 1000)}


# Pi: a print-mode run of the model the user configured, with no tools, and none of
# the extensions (Leaf's own among them, and every hook, since Pi's hooks are
# extensions), MCP servers, skills, prompt templates or context files the user
# installed. An empty appended prompt stands in for the APPEND_SYSTEM.md Pi would
# otherwise add. Offline skips the version check and catalog refresh a start makes.
# Thinking off is the least a model accepts: `minimal` on gpt-6.1-sol, which
# reasoned on no title.
PI_COMMAND = (
    "--print",
    "--mode",
    "json",
    "--no-session",
    "--no-tools",
    "--no-extensions",
    "--no-mcp",
    "--no-skills",
    "--no-prompt-templates",
    "--no-context-files",
    "--append-system-prompt",
    "",
    "--no-themes",
    "--offline",
    "--thinking",
    "off",
)


def pi_generate(
    request: str,
    page_dir: Path,
    *,
    schema: dict,
    instructions: str,
) -> dict:
    """Ask Pi's configured model for structured JSON through the `pi` on PATH, on
    the user's own login and Pi home, run in the page directory.

    The page server's environment is that of whichever Pi session started it, so the
    child is given none of that session's identity. The request goes on stdin and the
    system prompt in a file, out of the process table. The file also keeps the
    caller's instructions from naming one: Pi reads a `--system-prompt` that names an
    existing path as that file, and an empty one as its own coding-agent prompt.

    Told the schema that way, gpt-6.1-sol on Pi's `openai-codex` provider answered 56
    of 56 requests with JSON matching it, across eight widget-style requests (a thread
    title, a classification, nullable fields in a list, no instructions, and a request
    for Markdown paragraphs among them). Answers took 1.8–3.6 s, and the Markdown one
    up to 15 s, at a load average near 30 (Pi 1.0.4). Asked for thread titles, whose
    instructions say to reply with the title alone, it answered 24 of 24 in the
    schema, to messages asking for a fix, a shell command, a poem, a sum, a bare
    "YES" or a plain-text answer.

    Pi exits some 3 s after it answers (Pi 1.0.4 on its `openai-codex` provider,
    where the model took 1–2 s), so the answer is read as Pi prints it, and the
    process is killed once it has, with no session to save."""
    executable = shutil.which("pi")
    if executable is None:
        raise FileNotFoundError("no `pi` on PATH")
    started = time.monotonic()
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in IDENTITY_VARIABLES
    }
    with (
        tempfile.NamedTemporaryFile("w", encoding="utf-8") as system_prompt,
        tempfile.TemporaryFile("w+") as errors,
    ):
        system_prompt.write(answering(instructions, schema))
        system_prompt.flush()
        with subprocess.Popen(
            [executable, *PI_COMMAND, "--system-prompt", system_prompt.name],
            cwd=page_dir,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
        ) as process:
            assert process.stdin is not None and process.stdout is not None
            deadline = threading.Timer(TIMEOUT, process.kill)
            deadline.start()
            try:
                process.stdin.write(request)
                process.stdin.close()
                settled = next(
                    (
                        record
                        for record in map(json.loads, process.stdout)
                        # A run that failed and that Pi will retry ends first.
                        if record["type"] == "agent_end" and not record["willRetry"]
                    ),
                    None,
                )
            finally:
                deadline.cancel()
                process.kill()
                process.wait()
        if settled is None:
            if time.monotonic() - started >= TIMEOUT:
                raise TimeoutError(f"no structured answer within {TIMEOUT} s")
            errors.seek(0)
            raise RuntimeError(
                f"pi exited {process.returncode} without an answer: "
                f"{errors.read().strip()[-300:]}"
            )
    answer = settled["messages"][-1]
    if answer["role"] != "assistant" or answer["stopReason"] != "stop":
        raise RuntimeError(
            f"the inference run ended {answer.get('stopReason')}: "
            f"{answer.get('errorMessage')}"
        )
    text = "".join(part["text"] for part in answer["content"] if part["type"] == "text")
    usage = answer["usage"]
    return {
        "value": answered(text, schema, "Pi"),
        "model": f"{answer['provider']}/{answer['model']}",
        "durationMs": round((time.monotonic() - started) * 1000),
        "usage": {
            # Pi counts cached input apart; the other harnesses count it in.
            "inputTokens": usage["input"] + usage["cacheRead"] + usage["cacheWrite"],
            "outputTokens": usage["output"],
        },
        # Pi prices each answer from its model catalog.
        "costUsd": usage["cost"]["total"],
    }
