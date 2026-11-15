"""Leaf's Claude Code hooks module (`hooks/claude-code.ts`) drawing the session's
pages above the prompt, forking the conversation for Leaf's clerk as a turn
ends, and running the forks that write a thread's working line or do its work.

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
    stamp,
    wait_for,
)

from leaf import clerk as clerk_model
from leaf import event_endpoint as endpoint_model
from leaf import event_log as events_model
from leaf import inference as inference_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as state_model
from leaf import thread as thread_model
from leaf import thread_titles as thread_titles_model
from leaf.harness import NUDGE_WORDS
from leaf.interaction_log import read_interactions

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
        self.spawned = queue.Queue()
        self.sent = queue.Queue()
        self.steps = queue.Queue()
        self.completions = queue.Queue()
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
            elif "spawned" in record:
                self.spawned.put(record["spawned"])
            elif "sent" in record:
                self.sent.put(record["sent"])
            elif "forkStep" in record:
                self.steps.put(record["forkStep"])
            elif "completed" in record:
                self.completions.put(record["completed"])
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
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    service_model.claim_page(page_dir)
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
        "activity": {"kind": "waiting"},
    }
    # The first follower lists the page and ends to be renewed; the next stays.
    launcher.write_text(
        "#!/bin/sh\n"
        f"echo started >> {starts}\n"
        f"echo '{json.dumps({'pages': [page], 'completions': []})}'\n"
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


def main_thread_request(driven, messages: int = 12) -> None:
    """The main thread's request and the rows it stored, which a fork resends: the
    model's reply and a tool's result, by Claude Code's doors for them. A subagent's
    row after them, and hook context and a queue record, which are no rows the model
    reads in the transcript, don't move the cut."""
    row = {
        "message": {"type": "assistant", "role": "assistant", "content": []},
        "door": "response",
        "origin": {"kind": "model", "model": "claude-opus-5-5"},
    }
    driven.emit("session.append", {**row, "uuid": "r0"})
    driven.emit("session.append", {**row, "uuid": "r1", "door": "tool-result"})
    step = {"turnId": "t1", "index": 0, "model": "claude-opus-5-5", "effort": "xhigh"}
    driven.emit("turn.step", {**step, "messageCount": 12})
    driven.emit("session.append", {**row, "uuid": "r2"})
    driven.emit(
        "turn.step",
        {**step, "model": "claude-haiku-5-5", "messageCount": 3, "agentId": "a1"},
    )
    driven.emit("session.append", {**row, "uuid": "r3", "agentId": "a1"})
    driven.emit("session.append", {**row, "uuid": "r4", "door": "hook-context"})
    driven.emit("session.append", {**row, "uuid": "r5", "door": "queue"})


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


def test_a_held_thread_message_gets_the_agents_working_line_from_a_fork(
    page_dir, monkeypatch, spawn, sessionless
):
    """The pages follower holds the session's forks lane, so the user's message in a
    new thread is kept back from the session, and the module forks the conversation with
    Leaf's prompt for it as it arrives and hands the line back: it goes in as the
    agent's working line, and the thread goes to the session."""
    said = "Checking why the poll is 2 s"
    driven = ClaudeCode(
        spawn, "cc-reply", {"forkAnswer": json.dumps({"line": said, "work": "take"})}
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
    asked = append_carried_log_record(
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
    assert told == f"Leaf: the line fork for thread {asked['id']}: hand_over", told
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


def test_a_fork_given_a_threads_work_runs_in_a_turn_leaf_keeps_for_it(
    page_dir, monkeypatch, spawn, sessionless
):
    """With forks that do the work, a thread the line fork judges `take` goes to a
    fork the module spawns with Leaf's task, and Leaf hears which agent runs the turn
    it opened for it. As that agent's run ends its turn closes, and the main thread
    hears what came of the thread."""
    driven = ClaudeCode(
        spawn,
        "cc-work",
        {
            "forkAnswer": json.dumps({"line": "Checking the version", "work": "take"}),
            "agentId": "agent-1",
            "env": {"LEAF_FORK_WORK": "on"},
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
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    spawned = driven.spawned.get(timeout=STATED_TIMEOUT)
    assert (spawned["subagentType"], spawned["name"]) == ("fork", f"leaf-{asked['id']}")
    assert spawned["prompt"].startswith("<leaf-fork-work>"), spawned["prompt"]
    wait_for(
        lambda: state_model.agent_turn_of("cc-work", "agent-1"),
        bool,
        failure="Leaf never heard which agent runs the fork's turn",
    )

    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t9"}
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "agent-1"})
    wait_for(
        lambda: state_model.open_agent_turns("cc-work"),
        lambda turns: turns == {},
        failure="the fork's turn never closed",
    )
    wait_for(
        lambda: clerk_model.queued("cc-work"),
        lambda lines: any(f"gave thread {asked['id']}" in line for line in lines),
        failure=lambda: f"the main thread never heard: {clerk_model.queued('cc-work')}",
    )
    driven.quit()


def test_a_fork_whose_run_ends_before_its_spawn_returns_still_ends_its_turn(
    page_dir, monkeypatch, spawn, sessionless
):
    """A fork can end its run before Claude Code answers the module's spawn with its
    agent id, as one that fails at once does. The module keeps that run's end until
    it learns the id, then tells Leaf, so the fork's turn closes and the main thread
    is given the thread back, rather than the turn holding the thread until it
    lapses."""
    driven = ClaudeCode(
        spawn,
        "cc-early",
        {
            "forkAnswer": json.dumps({"line": "Checking the version", "work": "take"}),
            "agentId": "agent-1",
            "env": {"LEAF_FORK_WORK": "on"},
            "spawnWaits": True,
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
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    driven.spawned.get(timeout=STATED_TIMEOUT)
    ended = {"durationMs": 1, "isAborted": True, "turnId": "t9"}
    driven.emit("turn.complete", {**ended, "reason": "error", "agentId": "agent-1"})
    driven.send({"spawnReturns": True})
    wait_for(
        lambda: state_model.open_agent_turns("cc-early"),
        lambda turns: turns == {},
        failure="the fork's turn never closed",
    )
    wait_for(
        lambda: clerk_model.queued("cc-early"),
        lambda lines: any(f"gave thread {asked['id']}" in line for line in lines),
        failure=lambda: (
            f"the main thread never heard: {clerk_model.queued('cc-early')}"
        ),
    )
    driven.quit()


def test_a_fork_whose_start_leaf_could_not_record_still_ends_its_turn(
    page_dir, monkeypatch, spawn, sessionless
):
    """A fork the module spawned whose agent Leaf couldn't record, as when Leaf's
    process fails, ends the turn Leaf opened for it, so the main thread gets the
    thread back at once rather than once the turn lapses; the end names the agent,
    which runs on, so its later `leaf` commands are refused as an ended fork's."""
    driven = ClaudeCode(
        spawn,
        "cc-unrecorded",
        {
            "forkAnswer": json.dumps({"line": "Checking the version", "work": "take"}),
            "agentId": "agent-1",
            "env": {"LEAF_FORK_WORK": "on"},
            "forkStepFails": "started",
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
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    driven.spawned.get(timeout=STATED_TIMEOUT)
    wait_for(
        lambda: clerk_model.queued("cc-unrecorded"),
        lambda lines: any(f"gave thread {asked['id']}" in line for line in lines),
        failure=lambda: (
            f"the main thread never heard: {clerk_model.queued('cc-unrecorded')}"
        ),
    )
    assert state_model.open_agent_turns("cc-unrecorded") == {}
    assert state_model.agent_known("cc-unrecorded", "agent-1")
    [gave] = [
        note
        for note in read_interactions(page_dir, types=("fork_outcome",))
        if note.get("step") == "end"
    ]
    assert gave["outcome"] == "hand_back" and "Leaf's step failed" in gave["why"]
    driven.quit()


@pytest.mark.parametrize("resumes", [True, False])
def test_a_later_message_in_a_forks_thread_resumes_that_fork(
    page_dir, monkeypatch, spawn, sessionless, resumes
):
    """The user's later message in a thread a fork answered, once that fork's run has
    ended, goes to the same fork: the module resumes it with Leaf's message, and Leaf
    hears that it runs the new turn, which its next end closes. Where Claude Code
    can't resume the fork, the module ends the turn Leaf opened and spawns nothing,
    which gives the thread to the main thread."""
    driven = ClaudeCode(
        spawn,
        "cc-resume",
        {
            "forkAnswer": json.dumps({"line": "Checking the version", "work": "take"}),
            "agentId": ["agent-1", "agent-2"],
            "env": {"LEAF_FORK_WORK": "on"},
            **({} if resumes else {"sendRefuses": "No transcript found"}),
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
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which Python?"}
    )
    assert driven.spawned.get(timeout=STATED_TIMEOUT)["name"] == f"leaf-{asked['id']}"
    first = wait_for(
        lambda: state_model.agent_turn_of("cc-resume", "agent-1"),
        bool,
        failure="Leaf never heard which agent runs the fork's turn",
    )
    ref = next(
        event["refs"][asked["id"]]["ref"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "pickup"
    )
    monkeypatch.setenv(state_model.AGENT_ID_VARIABLE, "agent-1")
    assert thread_model.post_response(ref, "Python 3.12 or later.", asks_back=False)
    monkeypatch.delenv(state_model.AGENT_ID_VARIABLE)
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t9"}
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "agent-1"})
    wait_for(
        lambda: state_model.open_agent_turns("cc-resume"),
        lambda turns: turns == {},
        failure="the fork's turn never closed",
    )

    more = append_carried_log_record(
        page_dir,
        {"kind": "reply", "parent": asked["id"], "author": "user", "text": "And uv?"},
    )
    sent = driven.sent.get(timeout=STATED_TIMEOUT)
    assert sent["to"] == {"agentId": "agent-1"}
    assert sent["text"].startswith("<leaf-fork-work>") and "And uv?" in sent["text"]
    if resumes:
        second = wait_for(
            lambda: state_model.agent_turn_of("cc-resume", "agent-1"),
            lambda turn: turn not in (None, first),
            failure="Leaf never heard which agent runs the follow-up's turn",
        )
        pickup = [
            e for e in events_model.read_events(page_dir) if e["kind"] == "pickup"
        ][-1]
        assert (pickup["events"], pickup["turn"]) == ([more["id"]], second)
        driven.emit(
            "turn.complete", {**ended, "reason": "answer", "agentId": "agent-1"}
        )
    wait_for(
        lambda: state_model.open_agent_turns("cc-resume"),
        lambda turns: turns == {},
        failure="the follow-up's turn never closed",
    )
    if not resumes:
        # Leaf closes the turn before it notes the end, so wait for the note.
        [gave] = wait_for(
            lambda: [
                note
                for note in read_interactions(page_dir, types=("fork_outcome",))
                if note.get("step") == "end" and more["id"] in note["inputs"]
            ],
            bool,
            failure="Leaf never noted the follow-up's end",
        )
        assert gave["outcome"] == "hand_back", gave
        assert "could not be resumed" in gave["why"], gave
    driven.settle()
    assert driven.spawned.empty() and driven.sent.empty()
    driven.quit()


def test_leaf_hears_of_the_end_of_a_fork_the_module_spawned_and_no_other(
    spawn, sessionless
):
    """The module keeps the forks it spawned in `$.state`, with the turn Leaf opened
    for each run, which a reload of its code leaves standing, so it tells Leaf as such
    a fork's run ends, naming that turn, even one spawned before the module loaded,
    and runs nothing for any other agent's end."""
    driven = ClaudeCode(
        spawn,
        "cc-ends",
        {"state": {"forks": {"agent-7": {"started": 1, "turn": "t7"}}}},
    )
    ended = {"answer": "Done.", "durationMs": 1, "isAborted": False, "turnId": "t9"}
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "agent-9"})
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "agent-7"})
    step = driven.steps.get(timeout=STATED_TIMEOUT)
    assert step["ended"] == {"agent": "agent-7", "turn": "t7", "answer": "Done."}, step
    driven.emit("turn.complete", {**ended, "reason": "answer", "agentId": "agent-7"})
    driven.settle()
    assert driven.steps.empty()
    driven.quit()


def test_a_comment_is_titled_by_a_completion_on_the_sessions_own_model(
    page_dir, monkeypatch, spawn, sessionless
):
    """As a comment opens an untitled thread, its page server asks the claimant's
    model for a title through the session's pages follower; the module makes the
    completion on the session's own client and hands the reply back through the
    launcher, and the title goes in in the claimant's voice. The provider's first
    answer is a 429, which the module reports with its status, so the page server
    asks again (`thread_titles.RETRY_INTERVAL`). Forks are off, so the follower
    waits on the session's requests alone."""
    monkeypatch.setattr(thread_titles_model, "RETRY_INTERVAL", 0.1)
    driven = ClaudeCode(
        spawn,
        "cc-title",
        {
            "completeReply": '{"title": "Poll interval"}',
            "completeRefusals": 1,
            "env": {"LEAF_FORK_REPLIES": "off"},
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
    assert driven.forks.empty() and driven.diagnostics.empty()
    driven.quit()
