"""The `codex-app-server` and `codex-queue` journeys: a real Codex task reaching Leaf
through one transport, and the steps a user takes at its terminal.

    uv run leaf-dev journey codex-app-server|codex-queue [--preview]

The suite drives the adapter with scripted App Server messages; this drives it with
Codex itself. It installs this working tree's plugin payload (`extract_payload`) into
a throwaway Codex home (`codex_home`), trusts the plugin's hooks there, and starts a
private App Server the way `leaf codex launch` does (`private_app_server`). On
`codex-app-server` Leaf's adapter observes that server; on `codex-queue` the task
sees no App Server environment variable, as in the desktop app or IDE extension, and
the real `codex queue` command is routed to the private server. The journey is then
the terminal: it opens the task and types the user's turns, and the user sends
comments through the page's Threads in Chrome. It reads the page's log and claim in
process, and stops at the first check that fails.

The steps, in order:

- `setup`: the user asks for a page to review; serving it automatically connects
  delivery using this journey's transport;
- `release`: the journey's timed ask, sent while the task is idle, is answered in a
  turn Leaf starts (`journey.run_journey`);
- `rich-choice` and `rich-question`: comments asking, in the author's own words, for
  clickable choices in the thread and for a question awaiting the user's answer, each
  moving its thread to the release rationale, are answered so;
- `mid-turn`: a comment sent during a shell command is answered once; the queue
  task must pick it up and answer it before that turn's first final response;
- `restart`: with the adapter killed, the user's next turn ends with the agent having
  started it again, and a comment sent afterwards is answered.

After each step every comment sent so far has exactly one reply and a pickup, its
thread was named by the page server's own title request (`thread_titles`), and the
page's claim names the task's last turn, closed. The claim's turn is App Server's id
for that turn, so the prompt hook and the adapter agree on one identity, and a turn
that ended stays closed. During the user's own turn the claim names that turn.

With `--preview`, setup runs the canonical `leaf-dev preview --user` command instead.
Every step retains its keyed URL. A last step, `reconnect`, interrupts the page
server between turns; the preview restores it without an edit and the next comment
is answered through the existing adapter at the same URL.

It spends a few model turns on the host's Codex login, so CI does not run it. The
task, its page and its state home live in a temporary directory, removed when every
check passes and kept, with its path printed, when one fails.
"""

import json
import os
import shlex
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import click
import psutil
from leaf.codex import private_app_server
from leaf.event_log import read_events
from leaf.events import build_threads
from leaf.leases import adapter_is_live, lock_is_held, titles_log
from leaf.revision_artifact import active_enclosing
from leaf.server import running_server
from leaf.service import page_claim
from leaf.thread_titles import TIMEOUT

from leaf_dev import ROOT
from leaf_dev.arms import (
    PageClient,
    codex_home,
    environment,
    extract_payload,
    now,
    run_leaf,
)
from leaf_dev.codex_task import STEP_LIMIT, Task, install_plugin
from leaf_dev.eval_codex import records_for
from leaf_dev.journey import User, checkout_version, local_session
from leaf_dev.preview import preview_lease
from leaf_dev.review_scenario import REQUEST, answers, prepare, require, settled

USER_TURN = (
    "Run `sleep 20` in the shell. Then, in a separate tool call, run "
    "`printf 'verified\\n'`. Then reply with the single word done."
)
RESTART_TURN = "Reply with the single word OK."
# Real author intent exercises the rich interface without naming its commands.
RICH = {
    "rich-choice": (
        "I need to decide whether to ship or wait. Give me two clickable choices "
        "inside this thread, not on the page. Explain the decision in a short "
        "question, and move this thread to the release rationale section."
    ),
    "rich-question": (
        "Ask me whether I can own the release check, as a prose question in this "
        "thread. Keep it waiting for my answer and move the thread to the release "
        "rationale section."
    ),
}


def adapter_processes(codex: str) -> list[psutil.Process]:
    """The detached adapters using this journey's isolated Codex executable."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if codex in (cmdline := process.info["cmdline"] or [])
        and "--codex-path" in cmdline
    ]


def page_server_title(session: str, thread: str) -> dict | None:
    """The page server's record of the title it generated for `thread`, waiting as
    long as the request may take, or None where it made none."""
    log = titles_log(session)
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
        time.sleep(0.5)


def check(page: Path, task: Task, user: User, sent: list[str]) -> str | None:
    """What holds between steps (`settled`), each comment's thread titled by the page
    server, and the claim's turn being the task's last. Returns how the last
    comment's title was made."""
    claim = settled(page, task.thread, {name: user.ids[name] for name in sent})
    titled = None
    if sent:
        record = page_server_title(task.thread, user.ids[sent[-1]])
        require(
            record is not None,
            f"the page server did not title comment `{sent[-1]}`'s thread",
        )
        titled = (
            f"titled in {record['durationMs']} ms, {record['inputTokens']} input tokens"
        )
    require(
        claim["turn"] == task.started[-1],
        f"the claim names turn {claim['turn']}, not the task's last turn "
        f"{task.started[-1]}",
    )
    return titled


def setup(task: Task, page: Path, codex: str, transport: str, preview: bool) -> None:
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
        task.say(
            "I wrote a Leaf source at ./source.html. "
            f"Run `{command}` so I can review it. "
            "Keep its preview available; feedback connects automatically. "
            "Handle the comments I leave on the page."
        )
    else:
        task.say(REQUEST)
    task.settle(
        lambda: adapter_is_live(task.thread) and running_server(page) is not None,
        "the setup turn did not serve the page and start the adapter",
    )
    require(
        bool(adapter_processes(codex)), "the adapter did not use this journey's Codex"
    )
    require(
        all(
            ("--app-server" in process.cmdline()) == (transport == "app-server")
            for process in adapter_processes(codex)
        ),
        f"the adapter did not select the {transport} transport",
    )


def steps(
    task: Task, user: User, page: Path, codex: str, transport: str, preview: bool
) -> None:
    """The steps after setup, as the module docstring lists them."""
    url = running_server(page)["url"]
    acquired = page_claim(page)["acquisition"]
    sent: list[str] = []

    def check_step() -> list[str]:
        titled = check(page, task, user, sent)
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
    task.settle(lambda: True, "the turn that answered `release` did not end")
    sent.append("release")
    step("release", started, check_step())

    for rich, request in RICH.items():
        started = time.monotonic()
        posted = user.comment(rich, request)

        def rich_answers(responds=posted):
            return [
                event
                for event in read_events(page)
                if event["kind"] == "reply"
                and event.get("responds") == responds
                and "failure" not in event
            ]

        task.settle(
            lambda name=rich: user.answered(name),
            f"rich {rich} comment was not answered",
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
        thread = build_threads(read_events(page), active_enclosing(page))[posted]
        require(bool(thread["title"]), "the rich thread was not titled")
        step(rich, started, check_step())

    started = time.monotonic()
    previous_turns = len(task.started)
    user_turn = task.say(USER_TURN)
    deadline = time.monotonic() + STEP_LIMIT
    while not any("sleep 20" in command for command in task.running_commands.values()):
        task.listen(0.5)
        require(
            time.monotonic() < deadline and user_turn in task.running,
            "the user turn did not start its sleep command",
        )
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
        task.listen(0.5)
        user.answered("mid-turn")
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
                event["kind"] == "pickup"
                and event["phase"] == "opened"
                and event["turn"] == user_turn
                and mid_turn in event["events"]
                for event in read_events(page)
            ),
            f"the active hook did not deliver the comment into turn {user_turn}",
        )
    task.settle(
        lambda: user.answered("mid-turn"),
        "comment `mid-turn` was not answered",
    )
    sent.append("mid-turn")
    details = check_step()
    if transport == "queue":
        require(
            task.started[previous_turns:] == [user_turn],
            "the mid-turn comment started another turn instead of entering the active one",
        )
    step("mid-turn", started, details)

    started = time.monotonic()
    for process in adapter_processes(codex):
        process.kill()
    # The preview may retain its killed child as a zombie until its next spawn.
    # The kernel-backed lease proves execution ended before that parent reaps it.
    task.settle(
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
    task.settle(
        lambda: adapter_is_live(task.thread),
        "the agent did not start the adapter again",
    )
    check_step()
    user.comment("restart")
    task.settle(
        lambda: user.answered("restart"),
        "comment `restart` was not answered",
    )
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
        task.settle(
            lambda: running_server(page) is not None,
            "the idle preview did not restore its server without an edit",
        )
        check_step()
        user.comment("reconnect")
        task.settle(
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
        "        os.environ['LEAF_VERIFY_CODEX_ENDPOINT'] = "
        "arguments[arguments.index('--listen') + 1]\n"
        "        os.environ.pop('LEAF_CODEX_APP_SERVER', None)\n"
        "    elif arguments[0] == 'queue':\n"
        "        arguments += ['--remote', os.environ['LEAF_VERIFY_CODEX_ENDPOINT']]\n"
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
    codex = shutil.which("codex")
    if codex is None:
        raise click.ClickException("cannot find the `codex` executable on PATH")
    version = checkout_version()
    # Outside any repository, so the task loads no project instructions or skills.
    root = Path(tempfile.mkdtemp(prefix=f"leaf-journey-codex-{transport}-"))
    state, work = root / "state", root / "work"
    work.mkdir()
    page = work / "page"
    payload = root / "plugin"
    extract_payload(payload)
    # Keep the journey's isolated executable on PATH; a login shell would
    # replace it with the user's Codex and bypass the queue wrapper.
    home = codex_home(root / "codex-home", "allow_login_shell = false\n")
    executable = task_codex(root, codex, transport)
    # This process reads the page and claim in the state home the task writes, and
    # every child inherits the throwaway Codex home, never the session running this.
    inherited = dict(os.environ)
    isolated = environment(
        XDG_STATE_HOME=str(state),
        CODEX_HOME=str(home),
        LEAF_PREVIEWS_ROOT=str(work),
        PATH=f"{Path(executable).parent}{os.pathsep}{os.environ['PATH']}",
    )
    os.environ.clear()
    os.environ.update(isolated)
    # The task's tool and turn record, for the turn phases each comment's timing
    # carries.
    records: list[dict] = []
    passed = False
    try:
        if preview:
            shutil.copy(ROOT / "examples" / "triage-board.html", work / "source.html")
        else:
            prepare(ROOT, state, page)
        with private_app_server(executable) as endpoint:
            task = Task(endpoint)

            def record(message: dict) -> None:
                if task.thread and task.owns(message):
                    records.extend(
                        {**normalized, "received_at": now()}
                        for normalized in records_for(message, task.thread, "")
                    )

            task.on_message = record
            try:
                install_plugin(task, payload, work)
                task.thread = task.request(
                    "thread/start",
                    {
                        "cwd": str(work),
                        "approvalPolicy": "never",
                        "sandbox": "danger-full-access",
                    },
                )["thread"]["id"]
                started = time.monotonic()
                setup(task, page, executable, transport, preview)
                session = local_session(browser, running_server(page)["url"])
                user = User(
                    session._replace(records=lambda: records, pause=task.listen),
                    version,
                    lambda: read_events(page),
                )
                check(page, task, user, [])
                user.passed("setup", started)
                yield (
                    user,
                    lambda: steps(task, user, page, executable, transport, preview),
                )
            finally:
                (root / "hooks.json").write_text(json.dumps(task.hooks, indent=2))
                task.socket.close()
                for process in adapter_processes(executable):
                    process.kill()
                run_leaf(ROOT, state, "server", "stop", str(page))
                if preview:
                    deadline = time.monotonic() + 30
                    while lock_is_held(preview_lease(page)):
                        require(
                            time.monotonic() < deadline,
                            "the isolated preview outlived its stopped service",
                        )
                        time.sleep(0.05)
            passed = True
    finally:
        os.environ.clear()
        os.environ.update(inherited)
        if passed:
            shutil.rmtree(root)
        else:
            click.echo(
                f"Kept the task, its page and its state home in {root}", err=True
            )
