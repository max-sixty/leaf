"""The `codex-app-server` and `codex-queue` journeys: a real Codex task reaching Leaf
through one transport, and the steps a user takes at its terminal.

    uv run leaf-dev journey run codex-app-server|codex-queue [--preview] [--sandbox]

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

The steps, in order; `setup`, `release` and `mid-turn` are those more than one
harness takes, as `journey.Terminal` has them, with the task's adapter as what
listens for the task between turns:

- `setup`, serving the page connecting delivery through this journey's transport.
  With `--sandbox`, the task's shell commands run in Codex's `workspace-write`
  sandbox, which may write the task's directory but not the state home, and nothing
  approves an escalation, so the task must serve through the plugin's MCP server
  (`leaf.codex_tool`);
- `release`, which a turn Leaf starts answers while the task is idle;
- `rich-choice` and `rich-question`: comments asking, in the author's own words, for
  clickable choices in the thread and for a question awaiting the user's answer, each
  moving its thread to the release rationale, are answered so;
- `mid-turn`, whose comment, on `codex-queue`, is answered before the user's
  turn's first final response rather than at its Stop;
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

After each step the journey requires what every harness must hold between steps
(`journey.Terminal.between`), with the task's adapter as what listens for the task,
over every comment but the rich ones; and that the page's claim names the task's
last turn, by App Server's id for it, so the prompt hook and the adapter agree on
one identity, and that the page answers at the keyed URL it had after setup
(`Codex.between`).

With `--preview`, setup runs the canonical `leaf-dev preview --user` command instead.
Every step retains its acquisition and the preview's watcher. A last step,
`reconnect`, interrupts the page
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
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import click
import psutil

from leaf.agent_state import cmd_page_state
from leaf.codex import private_app_server
from leaf.event_log import read_events
from leaf.leases import adapter_is_live, hooks_ran, lock_is_held
from leaf.server import running_server
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
from leaf_dev.commands.journey.run import (
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
    claimed,
    picked_up,
    prepare,
    require,
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
    every notification of the task's thread kept as tool and turn records. With
    `preview`, the canonical preview serves the page."""

    def __init__(self, endpoint: str, *, preview: bool) -> None:
        super().__init__()
        self.task = Task(endpoint, self.record)
        self.running_commands = self.task.running_commands
        self.commands = self.task.commands
        self.preview = preview
        # The task's cwd, approval policy and sandbox, which resuming it restores.
        self.settings: dict[str, str] = {}
        # The page's keyed URL and the claim's acquisition when setup ended.
        self.served: tuple[str, str] | None = None

    def start(self, settings: dict[str, str]) -> None:
        """Trust the plugin's hooks and open the task with `settings`."""
        trust_plugin_hooks(self.task, Path(settings["cwd"]))
        self.settings = settings
        self.session = self.task.thread = self.task.request("thread/start", settings)[
            "thread"
        ]["id"]

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

    def say(self, text: str) -> None:
        self.task.say(text)

    def work(self, turn: str = USER_TURN) -> None:
        self.task.say(turn)
        self.await_command(SLEEP, "the user's turn did not start its command")

    def listening(self) -> bool:
        """Whether the task's adapter runs, which holds its wait lease between
        turns."""
        return adapter_is_live(self.session)

    def between(
        self, page: Path, name: str, comments: dict[str, str] | None = None
    ) -> list[str]:
        """What holds between steps (`Terminal.between`), with the claim's turn
        being the task's last, and the page answering at the keyed URL it had when
        setup ended. With `preview`, the claim keeps that acquisition and the
        preview's watcher runs, and the step's record prints the claim."""
        lines = super().between(page, name, comments)
        claim = claimed(page)
        require(
            claim["turn"] == self.task.started[-1],
            f"{name}: the claim names turn {claim['turn']}, not the task's last turn "
            f"{self.task.started[-1]}",
        )
        url = require(running_server(page), f"{name}: the page has no server")["url"]
        self.served = self.served or (url, claim["acquisition"])
        served, acquired = self.served
        require(url == served, f"{name}: the page's keyed URL changed")
        PageClient(url).state()
        if self.preview:
            require(
                claim["acquisition"] == acquired,
                f"{name}: the preview lost its acquisition",
            )
            require(
                lock_is_held(preview_lease(page)),
                f"{name}: the preview watcher ended",
            )
            lines.append(
                json.dumps(
                    {
                        "url": url,
                        "thread": self.session,
                        "turn": claim["turn"],
                        "generation": claim["generation"],
                        "acquisition": claim["acquisition"],
                        "turn_closed": claim["turn_closed"],
                        "answers": {
                            step: len(answers(page, comment))
                            for step, comment in self.counted.items()
                        },
                    }
                )
            )
        return lines


def adapter_processes(codex: str) -> list[psutil.Process]:
    """The detached adapters using this journey's isolated Codex executable."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if codex in (cmdline := process.info["cmdline"] or [])
        and "--codex-path" in cmdline
    ]


def setup(
    codex: Codex,
    page: Path,
    executable: str,
    transport: str,
    *,
    preview: bool,
    sandbox: bool,
):
    """`setup` (`Terminal.setup`), asking for the page by the canonical preview
    command with `preview`, and requiring delivery connected through `transport`
    by this journey's Codex, and in the sandbox by a `leaf` command run through the
    plugin's MCP server."""
    request = REQUEST
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
        request = (
            "I wrote a Leaf source at ./source.html. "
            f"Run `{command}` so I can review it. "
            "Keep its preview available; feedback connects automatically. "
            "Handle the comments I leave on the page."
        )
    codex.setup(page, request)
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
    codex: Codex, user: User, page: Path, executable: str, transport: str
) -> None:
    """The steps after setup, as the module docstring lists them."""
    task = codex.task

    def step(name: str, started: float, *comments: str) -> None:
        codex.passed(user, page, name, started, *comments)

    started = time.monotonic()
    codex.release(user)
    step("release", started, "release")

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
                "the question has no On Me obligation in its thread",
            )
        require(
            title(read_events(page), posted) is not None,
            "the rich thread was not titled",
        )
        step(rich, started)

    started = time.monotonic()
    if transport == "queue":
        # The comment enters the user's turn at a tool boundary, so its answer comes
        # before the turn's final response, not after it at the turn's Stop. Only the
        # queue's Stop hands input into the ending turn; over App Server it leaves
        # input to the adapter, so the pickup in the user's turn proves the boundary.
        def answered_first(turn: str) -> None:
            comment = user.ids.get("mid-turn")
            require(
                comment is not None and answers(page, comment),
                "mid-turn: the agent sent its final response before answering the "
                "comment",
            )

        task.on_final = answered_first
    codex.mid_turn(user, page)
    task.on_final = None
    require(
        transport != "queue" or task.started[-1] in task.final_answers,
        "mid-turn: the user's turn emitted no final response to check",
    )
    step("mid-turn", started, "mid-turn")

    started = time.monotonic()
    interrupted = task.say(RESUME_TURN)
    codex.await_command(SLEEP, "the turn to interrupt did not start its command")
    task.request("turn/interrupt", {"threadId": codex.session, "turnId": interrupted})
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
            "threadId": codex.session,
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
    entered = resumed in picked_up(page, during)
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
    step("resume", started, "resume")

    started = time.monotonic()
    if transport == "queue":
        previous_records = len(codex.trace)
        task.request("thread/unsubscribe", {"threadId": codex.session})
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
            not hooks_ran(codex.session),
            "the task left by its last client did not end its instance",
        )
        task.request("thread/resume", {"threadId": codex.session, **codex.settings})
    previous_turns = len(task.started)
    early = task.say(UNLOAD_TURN)
    codex.await_command(UNLOAD_READY, "the resumed turn did not reach its checkpoint")
    codex.until(
        lambda: claimed(page)["turn"] == early,
        f"the claim never named the user's turn {early}",
    )
    during = user.comment("unload")
    (Path(codex.settings["cwd"]) / UNLOAD_READY).touch()
    codex.settle(
        lambda: user.answered("unload"),
        "the comment sent at the resumed turn's checkpoint was not answered",
    )
    require(
        early in picked_up(page, during),
        f"the comment sent at the checkpoint did not enter turn {early}",
    )
    require(
        task.started[previous_turns:] == [early],
        "the comment sent at the checkpoint started a turn of its own",
    )
    step("unload", started, "unload")

    started = time.monotonic()
    for process in adapter_processes(executable):
        process.kill()
    # The preview may retain its killed child as a zombie until its next spawn.
    # The kernel-backed lease proves execution ended before that parent reaps it.
    codex.settle(
        lambda: not codex.listening(), "the killed adapter still holds its lease"
    )
    if codex.preview:
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
    codex.settle(codex.listening, "the agent did not start the adapter again")
    codex.between(page, "restart")
    user.comment("restart")
    codex.settle(lambda: user.answered("restart"), "`restart` was not answered")
    step("restart", started, "restart")

    if codex.preview:
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
        codex.between(page, "reconnect")
        user.comment("reconnect")
        codex.settle(
            lambda: user.answered("reconnect"),
            "the restored preview's comment was not answered",
        )
        step("reconnect", started, "reconnect")


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
) -> Generator[tuple[User, Callable]]:
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
            codex = Codex(endpoint, preview=preview)
            try:
                codex.start(
                    {
                        "cwd": str(place.work),
                        "approvalPolicy": "never",
                        "sandbox": "workspace-write"
                        if sandbox
                        else "danger-full-access",
                    }
                )
                started = time.monotonic()
                setup(
                    codex,
                    place.page,
                    executable,
                    transport,
                    preview=preview,
                    sandbox=sandbox,
                )
                with user_at(browser, place, codex, started) as user:
                    yield (
                        user,
                        lambda: steps(codex, user, place.page, executable, transport),
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
