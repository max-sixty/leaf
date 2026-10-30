"""Leaf's Claude Code hooks module (`hooks/claude-code.ts`) drawing the session's
pages above the prompt, and forking the conversation for Leaf's clerk as a turn
ends.

`claude_code_driver.mjs` stands in for Claude Code around the module, which calls
the real launcher, so these hold the module and the follower it runs together."""

import json
import os
import queue
import re
import subprocess
import threading
from pathlib import Path

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    read_record,
    serving,
    wait_for,
)

from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import thread as thread_model

DRIVER = Path(__file__).parents[1].joinpath("claude_code_driver.mjs")


class ClaudeCode:
    """One driven Claude Code process and the session its module serves."""

    def __init__(self, spawn, session: str, options: dict):
        self.session = session
        self.ended = False
        self.process = spawn(
            ["node", str(DRIVER), session, json.dumps(options)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        # Event results and redraws interleave on the driver's stdout, since the
        # follower prints while an event runs.
        self.answers = queue.Queue()
        self.diagnostics = queue.Queue()
        self.debug = queue.Queue()
        self.bands = queue.Queue()
        self.pressed = queue.Queue()
        self.forks = queue.Queue()
        threading.Thread(target=self.route, daemon=True).start()
        self.pid = self.read()["pid"]

    def route(self) -> None:
        for line in self.process.stdout:
            record = json.loads(line)
            if "diagnostic" in record:
                self.diagnostics.put(record["diagnostic"])
            elif "debug" in record:
                self.debug.put(record["debug"])
            elif "band" in record:
                self.bands.put(record["band"])
            elif "forked" in record:
                self.forks.put(record["forked"])
            elif {"copied", "toast"} & record.keys():
                self.pressed.put(record)
            else:
                self.answers.put(record)

    def read(self) -> dict:
        return self.answers.get(timeout=STATED_TIMEOUT)

    def send(self, line: dict) -> None:
        self.process.stdin.write(json.dumps(line) + "\n")
        self.process.stdin.flush()

    def emit(self, event: str, e: dict | None = None) -> dict:
        """Run one event through the module, and return what its hooks returned."""
        self.send({"emit": event, "e": e or {}})
        answer = self.read()
        assert answer["event"] == event, answer
        return answer

    def settle(self) -> None:
        """Wait until the module has done what it does without waiting on anything
        outside."""
        self.send({"flush": True})
        assert self.read() == {"flushed": True}

    def quit(self) -> None:
        if not self.ended:
            self.emit("session.end", {"reason": "other", "sessionId": self.session})
            self.ended = True


def holding_page(driven: ClaudeCode, page_dir: Path, monkeypatch) -> None:
    """Have the session `driven` drives hold a page claimed and served from a Bash
    tool command as Claude Code runs one: its session id and its process. Claude
    Code's own environment names no session, so neither does the module's. The
    session then starts, as one does when the module loads while it holds a
    page."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", driven.session)
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    service_model.claim_page(page_dir)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir)
    # hooks.json's prompt hook has run for the session by the time it holds a page.
    leases_model.mark_hooks(driven.session)
    driven.emit("session.start", {"cwd": str(page_dir), "isInteractive": True})


@pytest.fixture
def claude_code(page_dir, monkeypatch, spawn, sessionless):
    """A Claude Code session with the module loaded, holding a page."""
    driven = ClaudeCode(spawn, "cc-s1", {})
    holding_page(driven, page_dir, monkeypatch)
    yield driven
    driven.quit()


def elements(node, tag: str):
    """The elements of `tag` in a drawn tree, in the order drawn."""
    if isinstance(node, dict):
        if node["tag"] == tag:
            yield node
        for child in node["children"]:
            yield from elements(child, tag)


def band_lines(band, surface) -> list[tuple[str, ...]]:
    """Each page's line in the band, as its text and the addresses its links open,
    or none where the module draws nothing. The desktop app draws a `Link` to
    anything but https or localhost as plain text, and links any http URL in
    `Markdown` (measured at Claude Code 2.1.304)."""
    if band is None:
        return []

    def text(node) -> str:
        if isinstance(node, str):
            return node
        if node["tag"] == "Markdown":
            fullmatch_result = re.fullmatch(r"\[(.*)\]\(.*\)", node["props"]["text"])
            assert fullmatch_result is not None
            label = fullmatch_result[1]
            return re.sub(r"\\(.)", r"\1", label)
        return "".join(text(child) for child in node["children"])

    def href(node) -> list[str]:
        if isinstance(node, str):
            return []
        if node["tag"] == "Link":
            target = node["props"]["href"]
            linked = surface == "terminal" or re.match(
                r"https:|http://localhost[:/]", target
            )
            return [target] if linked else []
        if node["tag"] == "Markdown":
            fullmatch_result_2 = re.fullmatch(r"\[.*\]\((.*)\)", node["props"]["text"])
            assert fullmatch_result_2 is not None
            return [fullmatch_result_2[1]]
        return [found for child in node["children"] for found in href(child)]

    return [
        (text(line), *href(line))
        for line in band["children"]
        # What the plugins beneath drew, which the driver's bottom leaves empty.
        if line is not None
    ]


def test_leaves_own_rows_in_the_conversation_stay_quiet(spawn, sessionless):
    """The watch's wake, a task notification under the summary `hooks.json` names,
    draws as nothing, and Leaf's nudge, another session's message, as one dim line.
    Other rows, and Leaf's own once ctrl+o expands them, draw as Claude Code
    draws them."""
    [summary] = [
        hook["rewakeSummary"]
        for entry in json.loads((DRIVER.parents[1] / "hooks/hooks.json").read_text())[
            "hooks"
        ]["Stop"]
        for hook in entry["hooks"]
        if hook.get("asyncRewake")
    ]
    driven = ClaudeCode(spawn, "cc-rows", {})

    def drawn(origin: dict, text: str, expanded: bool = False):
        row = {
            "component": "UserMessage",
            "props": {"text": text, "origin": origin, "isExpanded": expanded},
        }
        result = driven.emit("ui.render:UserMessage", row)["result"]
        # The driver's bottom answers with the row it reached: Claude Code's drawing.
        return "engine" if result == row else result

    wake = {"kind": "task-notification"}
    nudge = "leaf: /p has new input, which arrives with this message."
    assert drawn(wake, summary) == {"tag": "Box", "props": {}, "children": []}
    assert drawn({"kind": "peer"}, nudge) == {
        "tag": "Text",
        "props": {"dimColor": True},
        "children": ["Leaf: new input"],
    }
    assert drawn(wake, summary, expanded=True) == "engine"
    assert drawn(wake, "Stop hook feedback") == "engine"
    assert drawn({"kind": "composer"}, "hello") == "engine"
    driven.quit()


def test_the_band_follows_the_pages_the_session_holds(
    page_dir, claude_code, monkeypatch
):
    """Above the prompt, in the terminal and the desktop app alike, each page the
    session holds is a link with the counts its Leaf panel marks that aren't zero:
    On me, open threads, and those holding words the user hasn't read; then what
    the agent last said it waits for. The band redraws as the page's row changes,
    and empties once the session holds no page."""

    def band(expected):
        server_rows_model.RowPublisher(page_dir, server_id).refresh()
        return wait_for(
            lambda: {
                surface: band_lines(drawn, surface)
                for surface, drawn in claude_code.bands.get(
                    timeout=STATED_TIMEOUT
                ).items()
            },
            lambda lines: lines == {"terminal": expected, "desktop": expected},
            failure=f"the band never showed {expected}",
        )

    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    read_result = server_rows_model.ROW.read(server_rows_model.row_path(page_dir))
    assert read_result is not None
    published = read_result["row"]
    server = server_model.running_server(page_dir)
    assert server is not None
    url, title = server["url"], published["title"]
    band([(f"Leaf {title}", url)])
    # A /clear ends the session and starts none; the next turn follows again.
    claude_code.emit(
        "session.end", {"reason": "clear", "sessionId": claude_code.session}
    )
    band([])
    claude_code.emit("turn.start", {"text": "", "turnId": "t"})
    band([(f"Leaf {title}", url)])
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "why?"}
    )
    band([(f"Leaf {title} · Threads 1", url)])
    thread_model.post_reply(
        page_dir, {"parent": comment["id"], "responds": comment["id"]}, "Because."
    )
    band([(f"Leaf {title} · Threads 1, 1 new", url)])
    append_carried_log_record(
        page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "owner": "user",
            "subject": {"kind": "page"},
            "title": "Try it",
        },
    )
    band([(f"Leaf {title} · On me 1 · Threads 1, 1 new", url)])
    # Another session takes the page, so this one holds none.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cc-s2")
    service_model.claim_page(page_dir)
    band([])


@pytest.mark.parametrize("ssh", [False, True], ids=["local", "ssh"])
def test_the_band_opens_a_page_from_the_keyboard(
    page_dir, monkeypatch, spawn, sessionless, tmp_path, ssh
):
    """In the terminal each line of the band ends with a button, the first focused
    as the band takes the keyboard. On the user's own machine it opens the page in
    the browser. Over SSH a browser started here would open on the wrong machine,
    so it copies the link to the user's clipboard instead, and says so."""
    opened = tmp_path / "opened"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Whichever opener the platform runs records the address it was given.
    for opener in ["open", "xdg-open"]:
        stub = bin_dir / opener
        stub.write_text(f'#!/bin/sh\nprintf %s "$1" > {opened}\n')
        stub.chmod(0o755)
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    if ssh:
        env["SSH_CONNECTION"] = "192.0.2.1 50000 192.0.2.2 22"
    driven = ClaudeCode(spawn, "cc-open", {"env": env})
    holding_page(driven, page_dir, monkeypatch)
    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    band = wait_for(
        lambda: driven.bands.get(timeout=STATED_TIMEOUT)["terminal"],
        lambda drawn: band_lines(drawn, "terminal"),
        failure="the module drew no band",
    )
    server = server_model.running_server(page_dir)
    assert server is not None
    url = server["url"]
    read_result_2 = server_rows_model.ROW.read(server_rows_model.row_path(page_dir))
    assert read_result_2 is not None
    title = read_result_2["row"]["title"]
    [button] = elements(band, "Button")
    assert button["props"]["label"] == ("copy link" if ssh else "open")
    assert button["props"]["autoFocus"] is True
    driven.send({"press": button["props"]["key"]})
    if ssh:
        assert driven.pressed.get(timeout=STATED_TIMEOUT) == {"copied": url}
        assert driven.pressed.get(timeout=STATED_TIMEOUT) == {
            "toast": f"Copied the link to {title}"
        }
        assert not opened.exists()
    else:
        wait_for(
            lambda: opened.exists() and opened.read_text(),
            lambda address: address == url,
            failure="the button opened nothing",
        )
        assert driven.pressed.empty()
    driven.quit()


@pytest.mark.parametrize("failure", ["exit", "startup", "spawn"])
def test_a_failed_pages_follower_reports_its_diagnostics(
    spawn, sessionless, tmp_path, failure
):
    """The native host runs an unavailable or failing external launcher. A follower
    that cannot spawn, cannot start, or exits with an error says so in the
    conversation, with its stderr."""
    launcher = tmp_path / "bin" / "leaf"
    if failure == "exit":
        launcher.parent.mkdir()
        launcher.write_text('#!/bin/sh\necho "launcher failed" >&2\nexit 23\n')
        launcher.chmod(0o755)
    driven = ClaudeCode(
        spawn,
        "cc-failure",
        {"pluginRoot": str(tmp_path), "throwSpawn": failure == "spawn"},
    )
    driven.emit("session.start", {"cwd": str(tmp_path), "isInteractive": True})
    diagnostic = driven.diagnostics.get(timeout=STATED_TIMEOUT)
    if failure == "spawn":
        assert diagnostic == (
            "Leaf: the pages follower could not start: Error: host cannot spawn"
        )
    elif failure == "startup":
        assert "pages follower failed" in diagnostic, diagnostic
        assert "ENOENT" in diagnostic, diagnostic
    else:
        assert diagnostic == (
            "Leaf: the pages follower exited with code 23: launcher failed"
        )
    driven.quit()


def test_a_follower_terminated_from_outside_stays_out_of_the_conversation(
    spawn, sessionless, tmp_path
):
    """A follower that something outside the module terminates, as happens while a
    session sits idle, did not fail: its line goes to Claude Code's debug log
    rather than the conversation the user reads."""
    launcher = tmp_path / "bin" / "leaf"
    launcher.parent.mkdir()
    # As `bin/leaf` does when its uv is terminated.
    launcher.write_text("#!/bin/sh\nsh -c 'kill -TERM $$'\nexit $?\n")
    launcher.chmod(0o755)
    driven = ClaudeCode(spawn, "cc-terminated", {"pluginRoot": str(tmp_path)})
    driven.emit("session.start", {"cwd": str(tmp_path), "isInteractive": True})
    assert driven.debug.get(timeout=STATED_TIMEOUT).startswith(
        "Leaf: the pages follower exited with code 143"
    )
    driven.settle()
    assert driven.diagnostics.empty()
    driven.quit()


def test_a_turn_end_forks_the_conversation_for_the_clerk(
    page_dir, monkeypatch, spawn, sessionless
):
    """As a main-loop turn the model answered ends in a session holding a live page,
    the module forks the conversation with the clerk's question and hands the answer
    back, and Leaf writes the ask it names On me. A subagent's turn, or an interrupted
    one, forks nothing."""
    page = page_dir.resolve()
    reply = json.dumps(
        {
            "status": {str(page): "Waiting on your pick of the retry limit"},
            "on_me": [
                {
                    "page": str(page),
                    "title": "Choose the retry limit: 3 or 5?",
                    "kind": "ask",
                    "quote": "Should the retry limit be 3 or 5?",
                }
            ],
            "missed": [],
        }
    )
    driven = ClaudeCode(spawn, "cc-fork", {"forkReply": reply})
    holding_page(driven, page_dir, monkeypatch)
    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    wait_for(
        lambda: band_lines(
            driven.bands.get(timeout=STATED_TIMEOUT)["terminal"], "terminal"
        ),
        bool,
        failure="the band never showed the page",
    )
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t1"}
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "a1"})
    driven.emit("turn.complete", {**ended, "reason": "aborted", "isAborted": True})
    driven.emit("turn.complete", {**ended, "reason": "answer"})
    assert "<leaf-fork-check>" in driven.forks.get(timeout=STATED_TIMEOUT)
    told = wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the clerk"),
        failure=lambda: f"the clerk never reported: {list(driven.diagnostics.queue)}",
    )
    assert "wrote 2 records" in told, told
    assert driven.forks.empty()
    [todo] = [
        event for event in events_model.read_events(page_dir) if event["kind"] == "todo"
    ]
    assert (todo["owner"], todo["title"], todo["by"]) == (
        "user",
        "Choose the retry limit: 3 or 5?",
        "leaf",
    )
    driven.quit()
