"""Leaf's Claude Code hooks module (`hooks/claude-code.ts`) drawing the session's
pages above the prompt, forking the conversation for Leaf's clerk as a turn
ends, and running the line fork that writes a thread's working line.

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
from conftest import hooks_run_this_tree
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    read_record,
    serving,
    stamp,
    wait_for,
)

from leaf.agents import delivery as delivery_model
from leaf.agents import inference as inference_model
from leaf.agents import thread as thread_model
from leaf.agents import thread_titles as thread_titles_model
from leaf.base import leases as leases_model
from leaf.base import rows as rows_model
from leaf.base import server as server_model
from leaf.base.harness import NUDGE_WORDS
from leaf.commands import hooks as hooks_model
from leaf.commands import session as session_model
from leaf.log import event_log as events_model
from leaf.log.interaction_log import read_interactions
from leaf.records import transaction as transaction_model
from leaf.serving import event_endpoint as endpoint_model
from leaf.serving import server_rows as server_rows_model

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
        self.steps = queue.Queue()
        self.completions = queue.Queue()
        self.environ = queue.Queue()
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
                self.forks.put(record)
            elif "report" in record:
                self.steps.put(record["report"])
            elif "completed" in record:
                self.completions.put(record["completed"])
            elif "environ" in record:
                self.environ.put(record["environ"])
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


def holding_page(
    driven: ClaudeCode, page_dir: Path, monkeypatch, serve: bool = True
) -> None:
    """Have the session `driven` drives hold a page claimed and served from a Bash
    tool command as Claude Code runs one: its session id and its process. Claude
    Code's own environment names no session, so neither does the module's. The
    session then starts, as one does when the module loads while it holds a
    page. `serve=False` leaves the page served by an earlier session's call."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", driven.session)
    hooks_run_this_tree(driven.session)
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    hooks_run_this_tree(driven.session)
    transaction_model.claim_page(page_dir)
    if serve:
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


def admitted(page_dir, event: dict) -> dict:
    """The user's message, admitted to the page's log."""
    return append_carried_log_record(page_dir, event)


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
    nudge = f"leaf: /p {NUDGE_WORDS}"
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
    read_result_2 = rows_model.ROW.read(rows_model.row_path(page_dir))
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


def test_the_band_lists_a_page_served_for_no_session_from_the_sessions_shell(
    page_dir, spawn, sessionless
):
    """A session developing Leaf talks to the user on a page its checkout's
    `bin/leaf` serves for no session, which the session holds no claim on. The
    server's row names the session whose shell started it, so the band lists the
    page there as it lists one the session holds."""
    driven = ClaudeCode(spawn, "cc-dev", {})
    serving(page_dir, 1)
    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id, driven.session).refresh()
    read_row = rows_model.ROW.read(rows_model.row_path(page_dir))
    assert read_row is not None
    driven.emit("session.start", {"cwd": str(page_dir), "isInteractive": True})
    band = wait_for(
        lambda: driven.bands.get(timeout=STATED_TIMEOUT)["terminal"],
        lambda drawn: band_lines(drawn, "terminal"),
        failure="the module drew no band",
    )
    server = server_model.running_server(page_dir)
    assert server is not None
    [(text, href)] = band_lines(band, "terminal")
    assert text.startswith(f"Leaf {read_row['row']['title']}")
    assert href == server["url"]
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


def test_a_follower_that_ends_to_be_renewed_starts_again(spawn, sessionless, tmp_path):
    """A follower ends with EX_TEMPFAIL once the session's delivery runs another Leaf
    (`hooks.cmd_pages`), and the module starts it again, under that Leaf, without a
    word in the conversation."""
    launcher = tmp_path / "bin" / "leaf"
    launcher.parent.mkdir()
    starts = tmp_path / "starts"
    page = {
        "page_key": "k",
        "url": "http://127.0.0.1:1/?t=k",
        "title": "Release",
        "on_user": 0,
        "threads": {"open": 0, "unread": 0},
        "activity": {
            "presence": "here",
            "state": "waiting",
            "reason": None,
            "detail": "",
        },
    }
    # The first follower lists the page and ends to be renewed; the next stays.
    launcher.write_text(
        "#!/bin/sh\n"
        f"echo started >> {starts}\n"
        f"echo '{json.dumps({'pages': [page], 'do': []})}'\n"
        f'[ "$(wc -l < {starts})" -gt 1 ] && exec sleep 60\n'
        "exit 75\n"
    )
    launcher.chmod(0o755)
    driven = ClaudeCode(spawn, "cc-renewed", {"pluginRoot": str(tmp_path)})
    driven.emit("session.start", {"cwd": str(tmp_path), "isInteractive": True})
    wait_for(
        lambda: starts.read_text() if starts.exists() else "",
        lambda read: read.count("started") == 2,
        failure="the module did not start the follower again",
    )
    driven.settle()
    assert driven.diagnostics.empty()
    driven.quit()


def test_an_instruction_the_module_does_not_run_comes_back_failed_at_once(
    spawn, sessionless, tmp_path
):
    """An instruction whose `do` the module doesn't know, as a Leaf newer than the
    session's module can list one, is reported failed at once, without a word in the
    conversation, so whatever waits on it moves on (`carrier.py`)."""
    launcher = tmp_path / "bin" / "leaf"
    launcher.parent.mkdir()
    unknown = {"id": "x1", "do": "frobnicate", "basis": {"kind": "line"}}
    launcher.write_text(
        "#!/bin/sh\n"
        'case "$*" in *--pages*)\n'
        f"  echo '{json.dumps({'pages': [], 'do': [unknown]})}'\n"
        "  exec sleep 60;;\n"
        "esac\n"
    )
    launcher.chmod(0o755)
    driven = ClaudeCode(spawn, "cc-unknown", {"pluginRoot": str(tmp_path)})
    driven.emit("session.start", {"cwd": str(tmp_path), "isInteractive": True})
    reported = driven.steps.get(timeout=STATED_TIMEOUT)
    assert {name: reported[name] for name in ("done", "do", "basis", "failed")} == {
        "done": "x1",
        "do": "frobnicate",
        "basis": {"kind": "line"},
        "failed": 'the hooks module runs no "frobnicate"',
    }, reported
    driven.settle()
    assert driven.steps.empty() and driven.diagnostics.empty()
    driven.quit()


# The main thread's last request as a fork's diagnostics name it: the newest row
# stored as it went out, and the newest by the time of the fork, such as its reply.
RESENT = {
    "model": "claude-opus-5-5",
    "effort": "xhigh",
    "messages": 12,
    "sent": "r1",
    "row": "r2",
}
# The usage the driver's fork reports (`tests/claude_code_driver.mjs`).
FORK_USAGE = {
    "input_tokens": 10,
    "output_tokens": 20,
    "cache_read_input_tokens": 1000,
    "cache_creation_input_tokens": 0,
}


def main_thread_request(driven) -> None:
    """The main thread's request and the conversation's rows by the time of a fork,
    which resends them: the request went out after a tool's result, `r1`, and the
    model's reply, `r2`, came after it. A subagent's request leaves the main thread's
    as it was."""
    driven.send({"conversation": ["r0", "r1"]})
    step = {"turnId": "t1", "index": 0, "model": "claude-opus-5-5", "effort": "xhigh"}
    driven.emit("turn.step", {**step, "messageCount": 12})
    driven.send({"conversation": ["r0", "r1", "r2"]})
    driven.emit(
        "turn.step",
        {**step, "model": "claude-haiku-5-5", "messageCount": 3, "agentId": "a1"},
    )


def test_a_turn_end_forks_the_conversation_for_the_clerk(
    page_dir, monkeypatch, spawn, sessionless
):
    """As a main-loop turn the model answered ends in a session holding a live page,
    the module forks the conversation with the clerk's question and hands the answer
    back, and Leaf asks what it names On Me, in a thread of its own. A subagent's turn, or an interrupted
    one, forks nothing."""
    page = page_dir.resolve()
    reply = json.dumps(
        {
            "asks": [
                {
                    "page": str(page),
                    "title": "The retry limit",
                    "text": "Should the retry limit be 3 or 5?",
                    "passage": "",
                    "again": "",
                    "quote": "Should the retry limit be 3 or 5?",
                }
            ],
            "findings": [],
        }
    )
    driven = ClaudeCode(spawn, "cc-fork", {"forkAnswer": reply})
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
    main_thread_request(driven)
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t1"}
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "a1"})
    driven.emit("turn.complete", {**ended, "reason": "aborted", "isAborted": True})
    driven.emit("turn.complete", {**ended, "reason": "answer"})
    forked = driven.forks.get(timeout=STATED_TIMEOUT)
    assert "<leaf-fork-check>" in forked["forked"]
    # The fork names no effort, so it thinks at the session's and reads its cache.
    assert "effort" not in forked, forked
    told = wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the clerk"),
        failure=lambda: f"the clerk never reported: {list(driven.diagnostics.queue)}",
    )
    assert "wrote 1 record, changed 0 passages and told the agent 1 line" in told, told
    assert driven.forks.empty()
    [asked] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    assert (asked["author"], asked["title"], asked["obligation"]) == (
        "agent",
        "The retry limit",
        True,
    )
    [note] = read_interactions(page_dir, types=("turn_end_check",))
    assert note["request"] == RESENT, note
    assert note["usage"] == FORK_USAGE and note["elapsedMs"] >= 0, note
    driven.quit()


def test_a_failed_fork_stays_out_of_the_conversation_and_the_next_turn_forks(
    page_dir, monkeypatch, spawn, sessionless
):
    """A fork the model refuses writes nothing and reaches only the debug log and the
    page's diagnostics, since the user never meets the clerk, and a turn that ended
    while it was out still forks after it. Neither waits on the band: Leaf says
    whether the session holds a page."""
    driven = ClaudeCode(spawn, "cc-fork-refused", {"forkRejects": True})
    holding_page(driven, page_dir, monkeypatch)
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "reason": "answer"}
    # The second ends while the first fork's question is still being asked.
    driven.emit("turn.complete", {**ended, "turnId": "t1"})
    driven.emit("turn.complete", {**ended, "turnId": "t2"})
    for _ in range(2):
        assert "<leaf-fork-check>" in driven.forks.get(timeout=STATED_TIMEOUT)["forked"]
        told = wait_for(
            lambda: driven.debug.get(timeout=STATED_TIMEOUT),
            lambda line: line.startswith("Leaf: the clerk"),
            failure=lambda: (
                f"the clerk never reported: {list(driven.diagnostics.queue)}"
            ),
        )
        assert "gave no answer (Error: the model refused the request)" in told, told
    driven.settle()
    assert driven.forks.empty()
    assert driven.diagnostics.empty()
    notes = read_interactions(page_dir, types=("turn_end_check",))
    assert [note["failed"] for note in notes] == [
        "Error: the model refused the request"
    ] * 2, notes
    assert not [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment"
    ]
    driven.quit()


def test_a_thread_message_gets_the_agents_working_line_from_a_fork(
    page_dir, monkeypatch, spawn, sessionless
):
    """The pages follower lists the user's message in a new thread as it arrives,
    and the module forks the conversation with Leaf's prompt for it and hands the
    line back: it goes in as the agent's working line."""
    said = "Checking why the poll is 2 s"
    driven = ClaudeCode(
        spawn,
        "cc-reply",
        {"forkAnswer": json.dumps({"line": said})},
    )
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
    main_thread_request(driven)
    asked = admitted(
        page_dir, {"kind": "comment", "author": "user", "text": "Why 2 s?"}
    )
    forked = driven.forks.get(timeout=STATED_TIMEOUT)
    prompt = forked["forked"]
    assert prompt.startswith("<leaf-line-fork>"), prompt
    assert "Why 2 s?" in prompt
    # The fork names no effort, so it thinks at the session's and reads its cache.
    assert "effort" not in forked, forked
    told = wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the line fork for thread"),
        failure=lambda: f"the fork never reported: {list(driven.diagnostics.queue)}",
    )
    assert told == f"Leaf: the line fork for thread {asked['id']}: posted", told
    [line] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply" and event["author"] == "agent"
    ]
    assert (line["parent"], line["text"], line["session"], line["ephemeral"]) == (
        asked["id"],
        said,
        "cc-reply",
        True,
    )
    [note] = read_interactions(page_dir, types=("fork_outcome",))
    assert note["request"] == RESENT, note
    assert note["usage"] == FORK_USAGE and note["elapsedMs"] >= 0, note
    assert driven.diagnostics.empty()
    driven.quit()


def test_a_fork_after_a_compaction_names_no_row_of_the_request_before_it(
    page_dir, monkeypatch, spawn, sessionless
):
    """A thread message that comes after Claude Code compacted the conversation, with
    no main-thread request since, gets a fork that resends the compacted
    conversation. Its diagnostics name the last request's model and effort and that
    the conversation was rewritten, and none of that request's rows or its count, at
    which a replay would cut the conversation as it stood before the compaction."""
    driven = ClaudeCode(
        spawn,
        "cc-compacted",
        {"forkAnswer": json.dumps({"line": "Checking"})},
    )
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
    main_thread_request(driven)
    # The compaction's summary, and the reply it kept.
    driven.send({"conversation": ["s1", "r2"]})
    driven.settle()
    admitted(page_dir, {"kind": "comment", "author": "user", "text": "Why 2 s?"})
    wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the line fork for thread"),
        failure=lambda: f"the fork never reported: {list(driven.diagnostics.queue)}",
    )
    [note] = read_interactions(page_dir, types=("fork_outcome",))
    assert note["request"] == {
        "model": "claude-opus-5-5",
        "effort": "xhigh",
        "rewritten": True,
    }, note
    driven.quit()


def test_a_long_threads_message_gets_a_summary_fork_beside_its_line_fork(
    page_dir, monkeypatch, spawn, sessionless
):
    """A message in a thread long enough that Leaf suggests a range to summarize gets
    a second fork, which the module makes beside the line fork and hands back on its
    own: Leaf writes its answer as the agent's summary of that range."""
    driven = ClaudeCode(
        spawn,
        "cc-reply",
        {
            "forkAnswer": {
                "<leaf-line-fork>": json.dumps({"line": "Checking"}),
                "<leaf-summary-fork>": json.dumps(
                    {"from": "q0", "through": "q5", "text": "The earlier discussion."}
                ),
            }
        },
    )
    # The thread's history, written before the follower first reads the page, gets
    # no line fork.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", driven.session)
    hooks_run_this_tree(driven.session)
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    hooks_run_this_tree(driven.session)
    transaction_model.claim_page(page_dir)
    # Ids the fork's answer names as the range it chose.
    opened = admitted(
        page_dir, {"kind": "comment", "author": "user", "id": "q0", "text": "Q0?"}
    )
    thread_model.post_reply(page_dir, {"responds": opened["id"]}, "A0.")
    for n in range(1, 6):
        asked = admitted(
            page_dir,
            {
                "kind": "reply",
                "author": "user",
                "parent": opened["id"],
                "id": f"q{n}",
                "text": f"Q{n}?",
            },
        )
        thread_model.post_reply(page_dir, {"responds": asked["id"]}, f"A{n}.")
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
    main_thread_request(driven)
    admitted(
        page_dir,
        {"kind": "reply", "author": "user", "parent": opened["id"], "text": "Q6?"},
    )
    prompts = {
        driven.forks.get(timeout=STATED_TIMEOUT)["forked"].split("\n")[0]
        for _ in range(2)
    }
    assert prompts == {"<leaf-line-fork>", "<leaf-summary-fork>"}, prompts
    told = wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the summary fork for thread"),
        failure=lambda: f"the fork never reported: {list(driven.diagnostics.queue)}",
    )
    assert told == f"Leaf: the summary fork for thread {opened['id']}: summarized"
    [summary] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "summary"
    ]
    assert (summary["from"], summary["through"], summary["text"]) == (
        "q0",
        "q5",
        "The earlier discussion.",
    )
    [note] = read_interactions(page_dir, types=("summary_fork",))
    assert note["usage"] == FORK_USAGE and note["request"] == RESENT, note
    assert driven.diagnostics.empty()
    driven.quit()


def test_a_line_fork_whose_step_leaf_could_not_take_posts_nothing(
    page_dir, monkeypatch, spawn, sessionless
):
    """Where Leaf's step for the line fork's answer fails, as when Leaf's process
    does, the module reports the instruction once more as failed, and Leaf records
    that the line fork failed and posts nothing, while the message stays the
    session's input."""
    driven = ClaudeCode(
        spawn,
        "cc-unrouted",
        {
            "forkAnswer": json.dumps({"line": "Checking the version"}),
            # The report of the fork's answer, not the one saying that step failed.
            "stepFails": {"do": "fork", "failed": None},
        },
    )
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
    main_thread_request(driven)
    asked = admitted(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    [routed] = wait_for(
        lambda: read_interactions(page_dir, types=("fork_outcome",)),
        bool,
        failure=lambda: f"Leaf never routed the thread: {list(driven.debug.queue)}",
    )
    assert routed["outcome"] == "failed", routed
    assert routed["why"].startswith("the fork failed: Leaf's step failed"), routed
    assert not [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    with transaction_model.PageTransaction(page_dir) as page:
        assert [event["id"] for event in delivery_model.deliverable(page)] == [
            asked["id"]
        ]
    driven.quit()


LIMIT = "CLAUDE_CODE_AUTO_BACKGROUND_TIMEOUT_MS"


def test_a_session_holding_a_page_has_its_long_commands_moved_to_the_background(
    page_dir, monkeypatch, spawn, sessionless
):
    """While the session holds a page, the module sets Claude Code's own limit on how
    long a main-agent foreground command holds the turn to 90 s, after which Claude
    Code moves it to the background and the page's input reaches the session. A
    `leaf` command may take a page on, however its launcher is spelled, so the limit
    is set before that command's result returns, ahead of the session's next call,
    and taken back once the follower finds the session holds no page. A limit the
    user set stays as it was, Leaf's own value included."""
    quoted = '"/opt/leaf/bin/leaf" server start p'

    pageless = ClaudeCode(spawn, "cc-pageless", {})
    pageless.emit("tool.call", {"tool": "Bash", "command": quoted, "tool_use_id": "u1"})
    assert pageless.environ.get_nowait() == {LIMIT: "90000"}
    assert pageless.environ.get(timeout=STATED_TIMEOUT) == {LIMIT: None}
    pageless.quit()

    driven = ClaudeCode(spawn, "cc-limited", {})
    holding_page(driven, page_dir, monkeypatch)
    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    # The follower's listing of the live page sets it, as in a session resumed
    # holding one.
    assert driven.environ.get(timeout=STATED_TIMEOUT) == {LIMIT: "90000"}
    driven.quit()

    own = ClaudeCode(spawn, "cc-own-limit", {"env": {LIMIT: "90000"}})
    own.emit(
        "tool.call",
        {"tool": "Bash", "command": "leaf page state p", "tool_use_id": "u2"},
    )
    # The follower finds no page and ends, and the band is drawn empty.
    own.bands.get(timeout=STATED_TIMEOUT)
    own.settle()
    assert own.environ.empty()
    own.quit()


def test_leaf_hears_nothing_from_a_subagent_and_hands_it_nothing(
    page_dir, monkeypatch, spawn, sessionless, capsys
):
    """A subagent the session spawns runs the module's hooks and `hooks.json`'s
    tool-boundary hook under its parent's session, naming itself, and Leaf neither
    hears from it nor hands it input, since the main session passes it what it
    needs. The module reports none of its calls or turns, so the first report Leaf
    hears is that of the main thread's turn ending after them; and `leaf hook` skips
    its PostToolBatch (`state.worker_tool_batch`), which hands over nothing and
    records no pickup, while the main thread's next boundary hands over the user's
    message."""
    driven = ClaudeCode(spawn, "cc-subagent", {})
    holding_page(driven, page_dir, monkeypatch)
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    subagent = {"agentId": "a1"}
    driven.emit(
        "tool.call",
        {"tool": "Bash", "command": "leaf page state", "tool_use_id": "u1", **subagent},
    )
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t1"}
    driven.emit("turn.complete", {**ended, "reason": "answer", **subagent})
    driven.emit("turn.complete", {**ended, "reason": "answer"})
    first = driven.steps.get(timeout=STATED_TIMEOUT)
    assert first.get("turn_end") is True, first
    wait_for(
        lambda: driven.debug.get(timeout=STATED_TIMEOUT),
        lambda line: line.startswith("Leaf: the clerk"),
        failure=lambda: f"the clerk never reported: {list(driven.diagnostics.queue)}",
    )
    driven.settle()
    later = list(driven.steps.queue)
    assert not any(step.get("turn_end") for step in later), later

    def boundary(**payload) -> str:
        capsys.readouterr()
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": "PostToolBatch", "session_id": "cc-subagent"} | payload,
        )
        return capsys.readouterr().out

    assert boundary(agent_id="a1") == ""
    assert not [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    ]
    assert asked["text"] in boundary()
    driven.quit()


def test_a_comment_is_titled_by_a_completion_on_the_sessions_own_model(
    page_dir, monkeypatch, spawn, sessionless
):
    """As a comment opens an untitled thread, its page server asks the claimant's
    model for a title through the session's pages follower; the module makes the
    completion on the session's own client and hands the reply back through the
    launcher, and the title goes in in the claimant's voice. The provider's first
    answer is a 429, which the module reports with its status, so the page server
    asks again (`thread_titles.RETRY_INTERVAL`). The comment's line fork hands it
    to the session meanwhile."""
    monkeypatch.setattr(thread_titles_model, "RETRY_INTERVAL", 0.1)
    driven = ClaudeCode(
        spawn,
        "cc-title",
        {
            "completeReply": '{"title": "Poll interval"}',
            "completeRefusals": 1,
            "forkAnswer": json.dumps({"line": "Checking"}),
        },
    )
    holding_page(driven, page_dir, monkeypatch)
    assert stamp(page_dir, "first").exit_code == 0
    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    wait_for(
        lambda: band_lines(
            driven.bands.get(timeout=STATED_TIMEOUT)["terminal"], "terminal"
        ),
        bool,
        failure="the band never showed the page",
    )
    status, body = endpoint_model.accept_event(
        page_dir, {"kind": "comment", "revision": 1, "text": "Why does it poll 2 s?"}
    )
    assert status == 200, body
    refused = driven.completions.get(timeout=STATED_TIMEOUT)
    assert refused["model"] == inference_model.CLAUDE_CODE_MODEL
    assert "Why does it poll 2 s?" in refused["prompt"]
    assert driven.completions.get(timeout=STATED_TIMEOUT) == refused
    [title] = wait_for(
        lambda: [
            event
            for event in events_model.read_events(page_dir)
            if event["kind"] == "thread_title"
        ],
        bool,
        failure=lambda: f"no title: {read_interactions(page_dir)}",
    )
    assert (title["thread"], title["title"], title["session"]) == (
        body["event"]["id"],
        "Poll interval",
        "cc-title",
    )
    [logged] = wait_for(
        lambda: read_interactions(page_dir, types=("thread_title_generated",)),
        bool,
        failure="the title was never recorded",
    )
    assert (logged["refusals"], logged["inputTokens"]) == (1, 300)
    assert logged["apiDurationMs"] >= 0
    assert driven.diagnostics.empty()
    driven.quit()
