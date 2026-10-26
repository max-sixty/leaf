"""Tool-free, schema-constrained inference through the host's existing login.

Codex uses an ephemeral App Server thread, Claude Code a safe-mode print run and Pi
a print run with nothing the user installed. None loads page tools, plugins or
session identity. The host fixes the model; callers supply input, instructions and
a required JSON Schema. Results contain value, model, usage and duration metadata.
This layer neither retries requests nor collects or persists page data; callers own
those policies.

Codex and Claude Code constrain the answer to the schema. Pi has no answer schema,
so its system prompt carries the schema, and its answer is parsed and validated
here; an answer that is not JSON matching the schema fails the request as any other
failure does (`pi_generate`).
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
# Safe mode omits user instructions, plugins, hooks, MCP servers and skills while
# keeping auth. User-only settings prevent project settings from overriding auth.
# Thinking made Haiku titles slower (3–7 s versus 1–2 s) without better results.
# Disabling nonessential traffic cut median startup/exit overhead in an interleaved
# four-pair comparison on a busy host (8.4 s versus 15.8 s total).
CLAUDE_CODE_ENVIRONMENT = {
    "MAX_THINKING_TOKENS": "0",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}


def claude_code_generate(
    request: str,
    page_dir: Path,
    *,
    schema: dict,
    instructions: str,
) -> dict:
    """Ask for structured JSON through the `claude` on PATH, on the user's own login
    and provider.

    The page server's environment is that of whichever session started it, so the
    child is given none of that session's identity and starts as a session of its
    own. The request goes on stdin, out of the process table."""
    executable = shutil.which("claude")
    if executable is None:
        raise FileNotFoundError("no `claude` on PATH")
    started = time.monotonic()
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in IDENTITY_VARIABLES
    }
    finished = subprocess.run(
        [
            executable,
            "-p",
            "--no-session-persistence",
            "--model=haiku",
            "--tools=",
            "--safe-mode",
            "--setting-sources=user",
            "--system-prompt",
            instructions,
            "--json-schema",
            json.dumps(schema),
            "--output-format",
            "json",
        ],
        env=env | CLAUDE_CODE_ENVIRONMENT,
        input=request,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    if finished.returncode != 0:
        raise RuntimeError(
            f"claude exited {finished.returncode}: {finished.stderr.strip()[-300:]}"
        )
    answer = json.loads(finished.stdout)
    # Haiku sometimes answers in prose rather than calling for the structured one;
    # the prose echoes the user's words, so it stays out of the record.
    if "structured_output" not in answer:
        raise RuntimeError(
            f"no structured output in the answer ({answer.get('stop_reason')})"
        )
    json_validator(schema).validate(answer["structured_output"])
    usage = answer["usage"]
    return {
        "value": answer["structured_output"],
        "model": "haiku",
        "durationMs": round((time.monotonic() - started) * 1000),
        # The model's share of `durationMs`; the rest is `claude` starting and
        # exiting, which a busy machine stretches and the model does not.
        "apiDurationMs": answer["duration_api_ms"],
        "usage": {
            "inputTokens": usage["input_tokens"]
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0),
            "outputTokens": usage["output_tokens"],
        },
    }


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
PI_ANSWER = (
    "Answer with one JSON value and nothing else: no prose before or after it, and "
    "no Markdown code fence around it. The value must match this JSON Schema:\n"
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
        system_prompt.write(
            "\n\n".join(filter(None, [instructions, PI_ANSWER + json.dumps(schema)]))
        )
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
    try:
        value = json.loads(text)
    # The prose can echo the user's words, so it stays out of the error.
    except json.JSONDecodeError as error:
        raise ValueError(f"Pi's answer is not JSON ({error.msg})") from None
    json_validator(schema).validate(value)
    usage = answer["usage"]
    return {
        "value": value,
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
