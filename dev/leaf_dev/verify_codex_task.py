"""Run real Codex tasks through Leaf's transports and check what they leave.

    uv run leaf-dev verify-codex-task [--preview]

The suite drives the adapter with scripted App Server messages; this drives it with
Codex itself. It installs this working tree's plugin payload (`extract_payload`) into
a throwaway Codex home (`codex_home`), trusts the plugin's hooks there, and starts a
private App Server the way `leaf codex launch` does (`private_app_server`). It runs
the journey through the observed App Server adapter and through the queue adapter.
The queue journey hides Leaf's App Server environment variable from the task and
routes the real `codex queue` command to the private server. The command is then
the terminal: it opens the task, types the user's turns, and posts the user's
comments to the served page as a tab would. It reads the page's log and claim in
process, and stops at the first check that fails.

The journey, in order:

- `setup`: the user asks for a page to review; serving it automatically connects
  delivery using this journey's transport;
- `idle`: a comment posted while the task is idle is answered in a turn Leaf starts;
- `mid-turn`: a comment posted during a shell command is answered once; the queue
  task must pick it up and answer it before that turn's first final response;
- `restart`: with the adapter killed, the user's next turn ends with the agent having
  started it again, and a comment posted afterwards is answered.

After each step every comment posted so far has exactly one reply and a pickup, and
the page's claim names the task's last turn, closed. The claim's turn is App Server's
id for that turn, so the prompt hook and the adapter agree on one identity, and a
turn that ended stays closed. During the user's own turn the claim names that turn.

With `--preview`, setup runs the canonical `leaf-dev preview --user` command instead.
Every step retains its keyed URL. Between turns, the page server is interrupted;
the preview restores it without an edit and the next comment is answered through
the existing adapter at the same URL.

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
from pathlib import Path

import click
import psutil
from leaf.codex_adapter import private_app_server
from leaf.event_log import read_events
from leaf.leases import adapter_is_live, lock_is_held
from leaf.server import running_server
from leaf.service import page_claim

from leaf_dev import ROOT
from leaf_dev.arms import (
    PageClient,
    codex_home,
    environment,
    extract_payload,
    run_leaf,
)
from leaf_dev.codex_task import STEP_LIMIT, Task, install_plugin
from leaf_dev.preview import preview_lease
from leaf_dev.review_scenario import (
    COMMENTS,
    REQUEST,
    answers,
    attempt,
    comment_id,
    post,
    prepare,
    require,
    settled,
)

USER_TURN = (
    "Run `sleep 20` in the shell. Then, in a separate tool call, run "
    "`printf 'verified\\n'`. Then reply with the single word done."
)
RESTART_TURN = "Reply with the single word OK."


def adapter_processes(codex: str) -> list[psutil.Process]:
    """The detached adapters using this journey's isolated Codex executable."""
    return [
        process
        for process in psutil.process_iter(["cmdline"])
        if codex in (cmdline := process.info["cmdline"] or [])
        and "--codex-path" in cmdline
    ]


def check(page: Path, task: Task, posted: list[str]) -> None:
    """What holds between steps (`settled`), and the claim's turn being the task's
    last."""
    claim = settled(page, task.thread, posted)
    require(
        claim["turn"] == task.started[-1],
        f"the claim names turn {claim['turn']}, not the task's last turn "
        f"{task.started[-1]}",
    )


def journey(
    task: Task, page: Path, codex: str, transport: str, *, preview: bool = False
) -> None:
    def step(name: str, started: float) -> None:
        click.echo(f"{transport}/{name}: passed in {time.monotonic() - started:.0f} s")
        if preview:
            claim = page_claim(page)
            click.echo(
                json.dumps(
                    {
                        "transport": transport,
                        "step": name,
                        "url": running_server(page)["url"],
                        "thread": task.thread,
                        "turn": claim["turn"],
                        "generation": claim["generation"],
                        "acquisition": claim["acquisition"],
                        "turn_closed": claim["turn_closed"],
                        "answers": {
                            name: len(answers(page, name))
                            for name in COMMENTS
                            if any(
                                event.get("attempt") == attempt(name)
                                for event in read_events(page)
                            )
                        },
                    }
                )
            )

    started = time.monotonic()
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
            f"Run `{command}` as a long-running shell command and leave it running "
            "so I can review it. The command connects feedback automatically. "
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
    check(page, task, [])
    url = running_server(page)["url"]
    acquired = page_claim(page)["acquisition"]

    def check_step(posted: list[str]) -> None:
        check(page, task, posted)
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

    step("setup", started)

    started = time.monotonic()
    post(page, "idle")
    task.settle(lambda: bool(answers(page, "idle")), "comment `idle` was not answered")
    check_step(["idle"])
    step("idle", started)

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
    post(page, "mid-turn")
    final_seen = False
    if transport == "queue":

        def before_final(turn: str) -> None:
            nonlocal final_seen
            if turn == user_turn:
                final_seen = True
                require(
                    bool(answers(page, "mid-turn")),
                    "the agent sent its final response before answering the active comment",
                )

        task.on_final = before_final
    named, deadline = False, time.monotonic() + STEP_LIMIT
    while (
        user_turn in task.running or user_turn not in task.started
    ) and time.monotonic() < deadline:
        task.listen(0.5)
        named = named or page_claim(page)["turn"] == user_turn
    require(named, f"the claim never named the user's turn {user_turn} while it ran")
    task.on_final = None
    if transport == "queue":
        require(final_seen, "the active turn emitted no final response to check")
        require(
            bool(answers(page, "mid-turn")), "the active turn ended without answering"
        )
        posted_id = comment_id(page, "mid-turn")
        require(
            any(
                event["kind"] == "pickup"
                and event["phase"] == "opened"
                and event["turn"] == user_turn
                and posted_id in event["events"]
                for event in read_events(page)
            ),
            f"the active hook did not deliver the comment into turn {user_turn}",
        )
    task.settle(
        lambda: bool(answers(page, "mid-turn")),
        "comment `mid-turn` was not answered",
    )
    check_step(["idle", "mid-turn"])
    if transport == "queue":
        require(
            task.started[previous_turns:] == [user_turn],
            "the mid-turn comment started another turn instead of entering the active one",
        )
    step("mid-turn", started)

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
    check_step(["idle", "mid-turn"])
    post(page, "restart")
    task.settle(
        lambda: bool(answers(page, "restart")),
        "comment `restart` was not answered",
    )
    check_step(["idle", "mid-turn", "restart"])
    step("restart", started)

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
        check_step(["idle", "mid-turn", "restart"])
        post(page, "reconnect")
        task.settle(
            lambda: bool(answers(page, "reconnect")),
            "the restored preview's comment was not answered",
        )
        check_step(["idle", "mid-turn", "restart", "reconnect"])
        step("reconnect", started)


def task_codex(root: Path, executable: str, transport: str) -> str:
    """Route the queue to the private server without exposing Leaf's observed
    App Server transport to the task. Both routes use the real Codex executable."""
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


def verify_transport(codex: str, transport: str, *, preview: bool = False) -> None:
    # Outside any repository, so the task loads no project instructions or skills.
    root = Path(tempfile.mkdtemp(prefix=f"leaf-verify-codex-{transport}-"))
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
    passed = False
    try:
        if preview:
            shutil.copy(ROOT / "examples" / "triage-board.html", work / "source.html")
        else:
            prepare(ROOT, state, page)
        with private_app_server(executable) as endpoint:
            task = Task(endpoint)
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
                journey(task, page, executable, transport, preview=preview)
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
            click.echo(f"Kept the task, its page and its state home in {root}")


@click.command()
@click.option("--preview", is_flag=True, help="Verify the canonical live user preview.")
def verify_codex_task(preview: bool = False) -> None:
    """Run Codex tasks through both Leaf transports and check same-turn delivery."""
    codex = shutil.which("codex")
    if codex is None:
        raise click.ClickException("cannot find the `codex` executable on PATH")
    for transport in ("app-server", "queue"):
        verify_transport(codex, transport, preview=preview)
    click.echo("Every check passed.")
