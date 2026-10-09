"""The `codex-app-server` and `codex-queue` journeys: a real Codex task reaching Leaf
through one transport, and the steps a user takes at its terminal.

    uv run leaf-dev journey codex-app-server|codex-queue [--preview]

The suite drives the adapter with scripted App Server messages; this drives it with
Codex itself. It installs this working tree's plugin payload (`extract_payload`) into
a throwaway Codex home (`codex_home`), trusts the plugin's hooks there, and starts a
private App Server the way `leaf codex launch` does (`private_app_server`). On
`codex-app-server` Leaf's adapter observes that server; on `codex-queue` the task
sees no App Server environment variable, as in the desktop app or IDE extension, and
the real `codex queue` command is routed to the private server (`task_codex`). The
journey is then the terminal: it opens the task and types the user's turns, and
after the release ask posts the user's comments to the served page as a tab would. It
reads the page's log and claim in process, and stops at the first check that fails.

The steps, in order:

- `setup`: the user asks for a page to review; serving it automatically connects
  delivery using this journey's transport;
- `release`: the journey's timed ask, sent while the task is idle, is answered in a
  turn Leaf starts (`journey.run_journey`);
- `rich-choice` and `rich-question`: comments asking, in the author's own words, for
  clickable choices in the thread and for a question awaiting the user's answer, each
  moving its thread to the release rationale, are answered so;
- `mid-turn`: a comment sent during a shell command is answered once, and the claim
  names the user's turn while it runs; on `codex-queue` the comment must also enter
  that turn and be answered before its first final response, starting no turn of
  its own;
- `resume`, on `codex-queue`: a turn interrupted during its shell command is resumed
  with empty input, as the desktop app resumes one, to report the interruption, so its
  first boundary is its Stop; a comment sent as it starts enters it, starting no turn
  of its own;
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
from leaf.codex import private_app_server
from leaf.delivery import pickup_receipts
from leaf.event_log import read_events
from leaf.leases import adapter_is_live, lock_is_held, titles_log
from leaf.server import running_server
from leaf.service import page_claim
from leaf.thread_titles import TIMEOUT

from leaf_dev import ROOT
from leaf_dev.arms import PageClient, codex_home, environment, now, run_leaf
from leaf_dev.codex_task import Task, install_plugin
from leaf_dev.eval_codex import records_for
from leaf_dev.journey import (
    STEP_LIMIT,
    Isolation,
    Terminal,
    User,
    isolated,
    title,
    user_at,
)
from leaf_dev.preview import preview_lease
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
# its Stop, which must carry the comment sent while it runs.
RESUME_TURN = (
    f"Run `python3 -c 'import time; {SLEEP}'` in the shell, then in a separate tool "
    "call run `printf 'verified\\n'`, then say done. If interrupted and resumed, "
    "skip the remaining shell command and report the interruption."
)
# Where the queue wrapper finds the private App Server the task's `codex queue` reaches.
ENDPOINT = "LEAF_JOURNEY_CODEX_ENDPOINT"


class Codex(Terminal):
    """The task's terminal (`Task`), heard as the journey's other terminals are, with
    every notification of the task's thread kept as tool and turn records."""

    def __init__(self, endpoint: str) -> None:
        super().__init__()
        self.task = Task(endpoint, self.record)
        self.running_commands = self.task.running_commands
        self.commands = self.task.commands

    def record(self, message: dict) -> None:
        if self.task.thread and self.task.owns(message):
            self.trace.extend(
                {**normalized, "received_at": now()}
                for normalized in records_for(message, self.task.thread, "")
            )

    def hear(self, seconds: float) -> None:
        self.task.listen(seconds)

    def idle(self) -> bool:
        return not self.task.running


def adapter_processes(codex: str) -> list[psutil.Process]:
    """The detached adapters using this journey's isolated Codex executable."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if codex in (cmdline := process.info["cmdline"] or [])
        and "--codex-path" in cmdline
    ]


def page_server_title(codex: Codex, thread: str) -> dict | None:
    """The page server's record of the title it generated for `thread`, hearing the
    task as long as the request may take, or None where it made none. The log names
    a thread's title but not who made it; this is what says the page server did."""
    log = titles_log(codex.task.thread)
    deadline = time.monotonic() + TIMEOUT
    while True:
        records = log.read_text().splitlines() if log.exists() else []
        for line in records:
            record = json.loads(line)
            if (record["event"], record["thread"]) == (
                "thread_title_generated",
                thread,
            ):
                return record
        if time.monotonic() > deadline:
            return None
        codex.hear(0.5)


def check(page: Path, codex: Codex, sent: dict[str, str]) -> str | None:
    """What holds between steps (`settled`), the last comment's thread titled by the
    page server, and the claim's turn being the task's last. `sent` names each
    comment so far by its step. Returns how the last comment's title was made."""
    claim = settled(page, codex.task.thread, sent)
    titled = None
    if sent:
        last = list(sent)[-1]
        record = page_server_title(codex, sent[last])
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


def setup(codex: Codex, page: Path, executable: str, transport: str, preview: bool):
    """Ask for the page and require it served, with delivery connected through
    `transport`."""
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
                reply.get("awaits") is True,
                "the prose question does not await the user's answer",
            )
        require(
            title(read_events(page), posted) is not None,
            "the rich thread was not titled",
        )
        step(rich, started, check_step())

    started = time.monotonic()
    previous_turns = len(task.started)
    user_turn = task.say(USER_TURN)
    codex.await_command(SLEEP, "the user turn did not start its command")
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

    if transport == "queue":
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
        previous_turns = len(task.started)
        resumed = task.request(
            "turn/start",
            {
                "threadId": task.thread,
                "input": [],
                "turnTrigger": "resume_interrupted_task",
            },
        )["turn"]["id"]
        codex.until(
            lambda: resumed in task.started, "the empty-input resume did not start"
        )
        require(resumed in task.running, "the empty-input resume already ended")
        # Post while that native turn is open, before its first delivery hook.
        during = user.comment("resume")
        codex.settle(
            lambda: user.answered("resume"),
            "the comment sent during resume was not answered",
        )
        sent.append("resume")
        details = check_step()
        require(
            task.started[previous_turns:] == [resumed],
            "the resumed-turn comment started another turn",
        )
        require(
            any(
                event["turn"] == resumed
                for event in pickup_receipts(
                    read_events(page), phase="opened", input_id=during
                )
            ),
            "the comment did not enter the empty-input resumed turn",
        )
        step("resume", started, details)

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
    App Server transport to the task. Both transports use the real Codex executable."""
    directory = root / "bin"
    directory.mkdir()
    wrapper = directory / "codex"
    wrapper.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "arguments = sys.argv[1:]\n"
        f"if {transport!r} == 'queue':\n"
        "    if arguments[0] == 'app-server':\n"
        f"        os.environ[{ENDPOINT!r}] = "
        "arguments[arguments.index('--listen') + 1]\n"
        "        os.environ.pop('LEAF_CODEX_APP_SERVER', None)\n"
        "    elif arguments[0] == 'queue':\n"
        f"        arguments += ['--remote', os.environ[{ENDPOINT!r}]]\n"
        f"os.execv({executable!r}, [{executable!r}, *arguments])\n"
    )
    wrapper.chmod(0o700)
    return str(wrapper)


@contextmanager
def answering(
    browser, transport: str, *, preview: bool
) -> Iterator[tuple[User, Callable]]:
    """The user at the page a Codex task serves through `transport`, once it has,
    and the steps that follow."""
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise click.ClickException("cannot find the `codex` executable on PATH")
    executable = ""

    def isolated_environment(place: Isolation) -> dict[str, str]:
        nonlocal executable
        # Keep the journey's isolated executable on PATH; a login shell would
        # replace it with the user's Codex and bypass the queue wrapper.
        home = codex_home(place.root / "codex-home", "allow_login_shell = false\n")
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
        with private_app_server(executable) as endpoint:
            codex = Codex(endpoint)
            try:
                install_plugin(codex.task, payload=place.payload, cwd=place.work)
                codex.task.thread = codex.task.request(
                    "thread/start",
                    {
                        "cwd": str(place.work),
                        "approvalPolicy": "never",
                        "sandbox": "danger-full-access",
                    },
                )["thread"]["id"]
                started = time.monotonic()
                setup(codex, place.page, executable, transport, preview)
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
