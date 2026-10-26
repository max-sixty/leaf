"""The `codex-app-server` and `codex-queue` journeys: a real Codex task reaching Leaf
through one transport, and the steps a user takes at its terminal.

    uv run leaf-dev journey codex-app-server|codex-queue [--preview] [--sandbox]

The suite drives the adapter with scripted App Server messages; this drives it with
Codex itself. It installs this working tree's plugin payload (`extract_payload`) into
a throwaway Codex home (`codex_home`), trusts the plugin's hooks there, and starts a
private App Server the way `leaf codex launch` does (`private_app_server`). On
`codex-app-server` Leaf's adapter observes that server; on `codex-queue` the task
sees no App Server environment variable, as in the desktop app or IDE extension, and
the real `codex queue` command is routed to the private server (`task_codex`). The
journey is then the terminal: it opens the task and types the user's turns, and
sends the user's comments at the journey's user end. It reads the page's log and
claim in process, and stops at the first check that fails.

The steps, in order:

- `setup`: the user asks for a page to review; serving it automatically connects
  delivery using this journey's transport. With `--sandbox`, the task's shell
  commands run in Codex's `workspace-write` sandbox, which may write the task's
  directory but not the state home, and nothing approves an escalation, so the task
  must serve through the plugin's MCP server (`leaf.codex_tool`);
- `release`: the journey's timed ask, sent while the task is idle, is answered in a
  turn Leaf starts (`journey.run_journey`); with `--case working` it is sent during
  the user's own turn's shell command, which answers it;
- `rich-choice` and `rich-question`: comments asking, in the author's own words, for
  clickable choices in the thread and for a question awaiting the user's answer, each
  moving its thread to the release rationale, are answered so;
- `mid-turn`: a comment sent during a shell command is answered once, and the claim
  names the user's turn while it runs; on `codex-queue` the comment must also enter
  that turn and be answered before its first final response, starting no turn of
  its own;
- `resume`: a turn interrupted during its shell command is resumed with empty input,
  as the desktop app resumes one, to report the interruption, so its first boundary is
  its Stop. On `codex-app-server` a comment sent as it starts doesn't enter it, since
  the Stop hook leaves input to the adapter's own turn, and is answered in a turn of
  its own. On `codex-queue` it enters the resumed turn, starting no turn of its own,
  since a queued turn would open on a message in the user's name;
- `unload`: the user's next turn holds its first shell command at a checkpoint.
  A comment sent there must enter that turn, starting no turn of its own. On
  `codex-queue` the user first leaves the task; the isolated server expires idle
  instances immediately, and the journey waits for native closure and Leaf's
  SessionEnd evidence before resuming it. Over App Server the adapter's own
  subscription keeps the task loaded;
- `restart`: with the adapter killed, the user's next turn ends with the agent having
  started it again, and a comment sent afterwards is answered.

After each step every comment sent so far, the rich ones aside, has exactly one reply
and a pickup, its thread was named by the page server's own title request
(`thread_titles`), and the page's claim names the task's last turn, closed. The
claim's turn is App Server's id for that turn, so the prompt hook and the adapter
agree on one identity, and a turn that ended stays closed.

With `--preview`, setup runs the canonical `leaf-dev preview --user` command instead.
Every step retains its keyed URL. A last step, `reconnect`, interrupts the page
server between turns; the preview restores it without an edit and the next comment
is answered through the existing adapter at the same URL.

The task's hook runs join the run's evidence. It spends a few model turns on the
host's Codex login, so CI does not run it.
"""

import json
import os
import shlex
import shutil
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import click
import psutil

from leaf.agent_state import cmd_page_state
from leaf.codex import private_app_server
from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.leases import adapter_is_live, hooks_ran, lock_is_held
from leaf.server import running_server
from leaf.service import page_claim
from leaf_dev import ROOT
from leaf_dev.arms import (
    PageClient,
    codex_home,
    environment,
    install_codex_plugin,
    now,
    run_leaf,
)
from leaf_dev.codex_task import Task, trust_plugin_hooks
from leaf_dev.commands.journey import (
    STEP_LIMIT,
    Isolation,
    Terminal,
    User,
    isolated,
    title,
    user_at,
)
from leaf_dev.commands.preview import preview_lease
from leaf_dev.eval_codex import records_for
from leaf_dev.review_scenario import (
    REQUEST,
    SLEEP,
    USER_TURN,
    answers,
    prepare,
    require,
    settled,
)

RESTART_TURN = "Reply with the single word OK."
# A resumed turn only reports its interruption, so the first boundary it reaches is
# its Stop, which decides where the comment sent while it runs goes.
RESUME_TURN = (
    f"Run `python3 -c 'import time; {SLEEP}'` in the shell, then in a separate tool "
    "call run `printf 'verified\\n'`, then say done. If interrupted and resumed, "
    "skip the remaining shell command and report the interruption."
)
# The driver releases this command only after admitting the comment. Model prose
# and host scheduling therefore cannot make the first command finish too early.
UNLOAD_READY = ".leaf-unload-ready"
UNLOAD_TURN = (
    f"Run `while [ ! -e {UNLOAD_READY} ]; do sleep 0.1; done; printf 'verified\\n'` "
    "in the shell in the foreground, with yield_time_ms 30000. "
    "Then reply with the single word done."
)


class Codex(Terminal):
    """The task's terminal (`Task`), heard as the journey's other terminals are, with
    every notification of the task's thread kept as tool and turn records."""

    def __init__(self, endpoint: str) -> None:
        super().__init__()
        self.task = Task(endpoint, self.record)
        self.running_commands = self.task.running_commands
        self.commands = self.task.commands
        # The task's cwd, approval policy and sandbox, which resuming it restores.
        self.settings: dict[str, str] = {}

    def record(self, message: dict) -> None:
        """Keep a notification of the task's thread as records, with where each turn
        starts and ends, each model response's end, which App Server reports with
        the response's token usage, and how long each hook ran, all of them Leaf's,
        since its plugin is the session's only one. App Server reports no request
        or stream start, only the items a response produces, the first of them after
        any hidden reasoning, so the model's time stays unsplit."""
        if self.task.thread and self.task.owns(message):
            normalized = records_for(message, self.task.thread, "")
            method, params = message.get("method"), message.get("params") or {}
            marker = {
                "turn/started": "turn_start",
                "turn/completed": "turn_end",
                "thread/closed": "thread_closed",
            }.get(method)
            if marker is not None:
                normalized.append({"type": marker})
            elif method == "thread/tokenUsage/updated":
                last = params["tokenUsage"]["last"]
                normalized.append(
                    {"type": "model_response", "outputTokens": last["outputTokens"]}
                )
            elif method == "hook/completed":
                normalized.append(
                    {"type": "leaf_hook", "ms": params["run"]["durationMs"]}
                )
            self.trace.extend({**record, "received_at": now()} for record in normalized)

    def hear(self, seconds: float) -> None:
        self.task.listen(seconds)

    def idle(self) -> bool:
        return not self.task.running

    def work(self) -> str:
        """Type the user's own turn, wait for its shell command, and return the
        turn's id."""
        turn = self.task.say(USER_TURN)
        self.await_command(SLEEP, "the user's turn did not start its command")
        return turn


def adapter_processes(codex: str) -> list[psutil.Process]:
    """The detached adapters using this journey's isolated Codex executable."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if codex in (cmdline := process.info["cmdline"] or [])
        and "--codex-path" in cmdline
    ]


def check(page: Path, codex: Codex, sent: dict[str, str]) -> str | None:
    """What holds between steps (`settled`), the last comment's thread titled by the
    page server, and the claim's turn being the task's last. `sent` names each
    comment so far by its step. Returns how the last comment's title was made."""
    claim = settled(page, codex.task.thread, sent)
    titled = None
    if sent:
        last = list(sent)[-1]
        record = codex.page_server_title(page, sent[last])
        require(record is not None, f"the page server did not title `{last}`'s thread")
        titled = (
            f"titled in {record['durationMs']} ms, {record['inputTokens']} input tokens"
        )
    require(
        claim["turn"] == codex.task.started[-1],
        f"the claim names turn {claim['turn']}, not the task's last turn "
        f"{codex.task.started[-1]}",
    )
    return titled


def setup(
    codex: Codex,
    page: Path,
    executable: str,
    transport: str,
    *,
    preview: bool,
    sandbox: bool,
):
    """Ask for the page and require it served, with delivery connected through
    `transport`, and in the sandbox by a `leaf` command run through the plugin's
    MCP server."""
    if preview:
        command = shlex.join(
            [
                "uv",
                "run",
                "--project",
                str(ROOT),
                "leaf-dev",
                "preview",
                "--source",
                "./source.html",
                "--slot",
                "page",
                "--user",
            ]
        )
        codex.task.say(
            "I wrote a Leaf source at ./source.html. "
            f"Run `{command}` so I can review it. "
            "Keep its preview available; feedback connects automatically. "
            "Handle the comments I leave on the page."
        )
    else:
        codex.task.say(REQUEST)
    codex.settle(
        lambda: adapter_is_live(codex.task.thread) and running_server(page) is not None,
        "the setup turn did not serve the page and start the adapter",
    )
    require(
        bool(adapter_processes(executable)),
        "the adapter did not use this journey's Codex",
    )
    require(
        all(
            ("--app-server" in process.cmdline()) == (transport == "app-server")
            for process in adapter_processes(executable)
        ),
        f"the adapter did not select the {transport} transport",
    )
    if sandbox:
        require(
            any(
                block.get("name") == "mcp__leaf__run"
                for record in codex.trace
                if record["type"] == "assistant"
                for block in record["message"]["content"]
            ),
            "the sandboxed task ran no `leaf` command through the plugin's MCP server",
        )


def steps(
    codex: Codex, user: User, page: Path, executable: str, transport: str, preview: bool
) -> None:
    """The steps after setup, as the module docstring lists them."""
    task = codex.task
    url = running_server(page)["url"]
    acquired = page_claim(page)["acquisition"]
    sent: list[str] = []

    def check_step() -> list[str]:
        titled = check(page, codex, {name: user.ids[name] for name in sent})
        require(
            running_server(page)["url"] == url,
            "the page's keyed URL changed between Codex turns",
        )
        PageClient(url).state()
        if preview:
            require(
                page_claim(page)["acquisition"] == acquired,
                "the preview lost its acquisition between Codex turns",
            )
            require(
                lock_is_held(preview_lease(page)),
                "the preview watcher ended between Codex turns",
            )
        return [titled] if titled else []

    def step(name: str, started: float, details: list[str]) -> None:
        if preview:
            claim = page_claim(page)
            details.append(
                json.dumps(
                    {
                        "url": running_server(page)["url"],
                        "thread": task.thread,
                        "turn": claim["turn"],
                        "generation": claim["generation"],
                        "acquisition": claim["acquisition"],
                        "turn_closed": claim["turn_closed"],
                        "answers": {
                            sent_name: len(answers(page, user.ids[sent_name]))
                            for sent_name in sent
                        },
                    }
                )
            )
        user.passed(name, started, *details)

    started = time.monotonic()
    user.release()
    codex.settle(lambda: True, "the turn that answered `release` did not end")
    sent.append("release")
    step("release", started, check_step())

    for rich in ("rich-choice", "rich-question"):
        started = time.monotonic()
        posted = user.comment(rich)

        def rich_answers(responds=posted):
            return [
                event
                for event in read_events(page)
                if event["kind"] == "reply"
                and event.get("responds") == responds
                and "failure" not in event
            ]

        codex.settle(
            lambda name=rich: user.answered(name), f"`{rich}` was not answered"
        )
        [reply] = rich_answers()
        require(bool(reply.get("text")), "the rich reply has no prose")
        require(
            reply.get("anchor", {}).get("section") == "triage-why",
            "rich reply did not relocate to the rationale",
        )
        if rich == "rich-choice":
            require(
                bool(reply.get("markup")),
                "the real author did not send clickable thread markup",
            )
        else:
            require(
                any(
                    item["thread"] == posted and item["next_actor"] == "user"
                    for item in cmd_page_state(page)["obligations"]
                ),
                "the question has no On me obligation in its thread",
            )
        require(
            title(read_events(page), posted) is not None,
            "the rich thread was not titled",
        )
        step(rich, started, check_step())

    started = time.monotonic()
    previous_turns = len(task.started)
    user_turn = codex.work()
    mid_turn = user.comment("mid-turn")
    if transport == "queue":

        def before_final(turn: str) -> None:
            if turn == user_turn:
                require(
                    bool(answers(page, mid_turn)),
                    "the agent sent its final response before answering the active comment",
                )

        task.on_final = before_final
    named, deadline = False, time.monotonic() + STEP_LIMIT
    while (
        user_turn in task.running or user_turn not in task.started
    ) and time.monotonic() < deadline:
        codex.hear(0.5)
        named = named or page_claim(page)["turn"] == user_turn
    require(named, f"the claim never named the user's turn {user_turn} while it ran")
    task.on_final = None
    if transport == "queue":
        require(
            user_turn in task.final_answers,
            "the active turn emitted no final response to check",
        )
        require(
            bool(answers(page, mid_turn)), "the active turn ended without answering"
        )
        require(
            any(
                event["turn"] == user_turn
                for event in pickup_receipts(
                    read_events(page), phase="opened", input_id=mid_turn
                )
            ),
            f"the active hook did not deliver the comment into turn {user_turn}",
        )
    codex.settle(lambda: user.answered("mid-turn"), "`mid-turn` was not answered")
    sent.append("mid-turn")
    details = check_step()
    if transport == "queue":
        require(
            task.started[previous_turns:] == [user_turn],
            "the mid-turn comment started another turn instead of entering the active one",
        )
    step("mid-turn", started, details)

    started = time.monotonic()
    interrupted = task.say(RESUME_TURN)
    codex.await_command(SLEEP, "the turn to interrupt did not start its command")
    task.request("turn/interrupt", {"threadId": task.thread, "turnId": interrupted})
    codex.until(
        lambda: interrupted not in task.running, "the interrupted turn did not end"
    )
    # Aborted command items need not emit item/completed. They cannot stand
    # in for execution of the resumed turn's first command.
    task.running_commands.clear()
    # The user writes the comment now and sends it the moment the resumed turn
    # starts; in a browser its admission then does not wait on typing in a turn
    # this short.
    send = user.write("resume")
    previous_turns = len(task.started)
    resumed = task.request(
        "turn/start",
        {
            "threadId": task.thread,
            "input": [],
            "turnTrigger": "resume_interrupted_task",
        },
    )["turn"]["id"]
    codex.until(lambda: resumed in task.started, "the empty-input resume did not start")
    require(resumed in task.running, "the empty-input resume already ended")
    during = send()
    codex.settle(
        lambda: user.answered("resume"),
        "the comment sent during resume was not answered",
    )
    sent.append("resume")
    details = check_step()
    entered = any(
        event["turn"] == resumed
        for event in pickup_receipts(read_events(page), phase="opened", input_id=during)
    )
    if transport == "queue":
        require(entered, "the comment did not enter the empty-input resumed turn")
        require(
            task.started[previous_turns:] == [resumed],
            "the resumed-turn comment started another turn",
        )
    else:
        require(
            not entered,
            "the Stop hook handed the comment into the empty-input resumed turn",
        )
        require(
            len(task.started[previous_turns:]) == 2,
            "the resumed-turn comment was not answered in one turn of its own",
        )
    step("resume", started, details)

    started = time.monotonic()
    if transport == "queue":
        previous_records = len(codex.trace)
        task.request("thread/unsubscribe", {"threadId": task.thread})
        # SessionEnd runs before shutdown completes; only thread/closed makes
        # the unloaded thread ready to resume.
        codex.until(
            lambda: any(
                record["type"] == "thread_closed"
                for record in codex.trace[previous_records:]
            ),
            "the task left by its last client did not close",
        )
        # The instance's SessionEnd retires the evidence that Leaf's hooks run in
        # it (`state.end_harness_instance`).
        require(
            not hooks_ran(task.thread),
            "the task left by its last client did not end its instance",
        )
        task.request("thread/resume", {"threadId": task.thread, **codex.settings})
    previous_turns = len(task.started)
    early = task.say(UNLOAD_TURN)
    codex.await_command(UNLOAD_READY, "the resumed turn did not reach its checkpoint")
    codex.until(
        lambda: page_claim(page)["turn"] == early,
        f"the claim never named the user's turn {early}",
    )
    during = user.comment("unload")
    (Path(codex.settings["cwd"]) / UNLOAD_READY).touch()
    codex.settle(
        lambda: user.answered("unload"),
        "the comment sent at the resumed turn's checkpoint was not answered",
    )
    sent.append("unload")
    details = check_step()
    require(
        any(
            event["turn"] == early
            for event in pickup_receipts(
                read_events(page), phase="opened", input_id=during
            )
        ),
        f"the comment sent at the checkpoint did not enter turn {early}",
    )
    require(
        task.started[previous_turns:] == [early],
        "the comment sent at the checkpoint started a turn of its own",
    )
    step("unload", started, details)

    started = time.monotonic()
    for process in adapter_processes(executable):
        process.kill()
    # The preview may retain its killed child as a zombie until its next spawn.
    # The kernel-backed lease proves execution ended before that parent reaps it.
    codex.settle(
        lambda: not adapter_is_live(task.thread),
        "the killed adapter still holds its lease",
    )
    if preview:
        reconnect = shlex.join(
            [
                "uv",
                "run",
                "--project",
                str(ROOT),
                "python",
                "-c",
                "from leaf.harness import session_harness; session_harness().ensure_delivery()",
            ]
        )
        task.say(
            "The isolated delivery adapter stopped. Reconnect the current preview "
            f"without acquiring its page again: run `{reconnect}`, then {RESTART_TURN}"
        )
    else:
        task.say(
            "Serve the existing ./page again with `leaf server start ./page`, "
            f"then {RESTART_TURN}"
        )
    codex.settle(
        lambda: adapter_is_live(task.thread),
        "the agent did not start the adapter again",
    )
    check_step()
    user.comment("restart")
    codex.settle(lambda: user.answered("restart"), "`restart` was not answered")
    sent.append("restart")
    step("restart", started, check_step())

    if preview:
        started = time.monotonic()
        servers = [
            process
            for process in psutil.process_iter(["cmdline"])
            if (cmdline := process.info["cmdline"] or [])
            and "_serve" in cmdline
            and str(page.resolve()) in cmdline
        ]
        require(len(servers) == 1, "the isolated preview has no unique page server")
        servers[0].kill()
        codex.settle(
            lambda: running_server(page) is not None,
            "the idle preview did not restore its server without an edit",
        )
        check_step()
        user.comment("reconnect")
        codex.settle(
            lambda: user.answered("reconnect"),
            "the restored preview's comment was not answered",
        )
        sent.append("reconnect")
        step("reconnect", started, check_step())


def task_codex(root: Path, executable: str, transport: str) -> str:
    """Route the queue to the private server without exposing Leaf's observed
    App Server transport to the task. Both transports use the real Codex executable.

    The server's endpoint is kept in a file beside the wrapper rather than in the
    environment, since Codex starts a plugin's MCP server, through which a sandboxed
    task runs `leaf`, with only the variables the plugin names."""
    directory = root / "bin"
    directory.mkdir()
    wrapper = directory / "codex"
    endpoint = directory / "endpoint"
    wrapper.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "arguments = sys.argv[1:]\n"
        f"endpoint = Path({str(endpoint)!r})\n"
        f"if {transport!r} == 'queue':\n"
        "    if arguments[0] == 'app-server':\n"
        "        endpoint.write_text(arguments[arguments.index('--listen') + 1])\n"
        "        os.environ.pop('LEAF_CODEX_APP_SERVER', None)\n"
        "    elif arguments[0] == 'queue':\n"
        "        arguments += ['--remote', endpoint.read_text()]\n"
        f"os.execv({executable!r}, [{executable!r}, *arguments])\n"
    )
    wrapper.chmod(0o700)
    return str(wrapper)


@contextmanager
def answering(
    browser, transport: str, *, preview: bool, sandbox: bool
) -> Iterator[tuple[User, Callable]]:
    """The user at the page a Codex task serves through `transport`, once it has,
    and the steps that follow. With `sandbox`, the task's shell commands run in
    Codex's sandbox and nothing approves an escalation, so a `leaf` command the
    sandbox refuses reaches Leaf only through the plugin's MCP server."""
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise click.ClickException("cannot find the `codex` executable on PATH")
    executable = ""

    def isolated_environment(place: Isolation) -> dict[str, str]:
        nonlocal executable
        # Keep the journey's isolated executable on PATH; a login shell would
        # replace it with the user's Codex and bypass the queue wrapper.
        # Expire idle, unsubscribed instances immediately so the unload step
        # observes native SessionEnd without the host's inactivity wait.
        config = "allow_login_shell = false\nthread_unload_delay_secs = 0\n"
        if sandbox:
            # The journey's state home is under TMPDIR, which the sandbox otherwise
            # lets a command write, where a user's is not. And the journey cannot
            # answer Codex's question whether to allow Leaf's MCP tool, so it
            # allows it as a user who answered "always" has. The state home's pages
            # directory is writable, as the README asks a user to make it.
            config += (
                "[sandbox_workspace_write]\n"
                "exclude_tmpdir_env_var = true\n"
                f'writable_roots = ["{place.state / "leaf" / "pages"}"]\n'
                '[plugins."leaf@leaf".mcp_servers.leaf]\n'
                'default_tools_approval_mode = "approve"\n'
            )
        home = codex_home(place.root / "codex-home", config)
        executable = task_codex(place.root, codex_path, transport)
        return environment(
            XDG_STATE_HOME=str(place.state),
            CODEX_HOME=str(home),
            LEAF_PREVIEWS_ROOT=str(place.work),
            PATH=f"{Path(executable).parent}{os.pathsep}{os.environ['PATH']}",
        )

    with isolated(f"codex-{transport}", isolated_environment) as place:
        if preview:
            shutil.copy(
                ROOT / "examples" / "triage-board.html", place.work / "source.html"
            )
        else:
            prepare(ROOT, place.state, place.page)
        with (place.evidence / "stderr.txt").open("w") as output:
            install_codex_plugin(
                Path(executable),
                place.payload,
                cwd=place.work,
                env=dict(os.environ),
                output=output,
            )
        with private_app_server(executable) as (endpoint, _process):
            codex = Codex(endpoint)
            try:
                trust_plugin_hooks(codex.task, place.work)
                codex.settings = {
                    "cwd": str(place.work),
                    "approvalPolicy": "never",
                    "sandbox": "workspace-write" if sandbox else "danger-full-access",
                }
                codex.task.thread = codex.task.request("thread/start", codex.settings)[
                    "thread"
                ]["id"]
                started = time.monotonic()
                setup(
                    codex,
                    place.page,
                    executable,
                    transport,
                    preview=preview,
                    sandbox=sandbox,
                )
                check(place.page, codex, {})
                with user_at(browser, place, codex, started) as user:
                    yield (
                        user,
                        lambda: steps(
                            codex, user, place.page, executable, transport, preview
                        ),
                    )
            finally:
                (place.evidence / "hooks.json").write_text(
                    json.dumps(codex.task.hooks, indent=2)
                )
                codex.task.socket.close()
                for process in adapter_processes(executable):
                    process.kill()
                if preview:
                    run_leaf(ROOT, place.state, "server", "stop", str(place.page))
                    deadline = time.monotonic() + 30
                    while lock_is_held(preview_lease(place.page)):
                        require(
                            time.monotonic() < deadline,
                            "the isolated preview outlived its stopped service",
                        )
                        time.sleep(0.05)
