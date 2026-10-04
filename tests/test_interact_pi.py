"""Pi as a harness: the one its environment implies, and Leaf's extension
(`hooks/pi.ts`) carrying a page's input into its runs.

`pi_driver.mjs` stands in for Pi around the extension, which calls the real
launcher, so these hold the extension and the hooks it calls together."""

import json
import os
import queue
import subprocess
import threading
from pathlib import Path

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    page_state,
    serving,
)
from leaf import harness as harness_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model

DRIVER = Path(__file__).with_name("pi_driver.mjs")


class Pi:
    """One driven Pi process and the session its extension serves."""

    def __init__(self, spawn, session: str, mode: str):
        self.session = session
        self.ended = False
        self.process = spawn(
            ["node", str(DRIVER), session, mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        # Handler results and sent messages interleave on the driver's stdout,
        # since a watch can wake while a handler runs.
        self.answers = queue.Queue()
        self.sent = queue.Queue()
        threading.Thread(target=self.route, daemon=True).start()
        self.pid = self.read()["pid"]

    def route(self) -> None:
        for line in self.process.stdout:
            record = json.loads(line)
            (self.sent if "sent" in record else self.answers).put(record)

    def read(self) -> dict:
        """The driver's next answer to a line sent to it."""
        return self.answers.get(timeout=STATED_TIMEOUT)

    def message(self) -> dict:
        """The next message the extension sends."""
        return self.sent.get(timeout=3 * STATED_TIMEOUT)

    def send(self, line: dict) -> dict:
        self.process.stdin.write(json.dumps(line) + "\n")
        self.process.stdin.flush()
        return self.read()

    def emit(self, event: str, *, idle: bool = False, reason: str = "") -> object:
        """Run one Pi event through the extension, and return what its handlers
        returned."""
        answer = self.send({"emit": event, "idle": idle, "reason": reason})
        assert answer["event"] == event, answer
        return answer["result"]

    def delivered(self, until: str) -> list[str]:
        """The ids of the events in the first message the extension sends that
        carries event `until`: the delivery the prompt hook returned."""
        while True:
            sent = self.message()
            delivery = json.loads(sent["sent"]["content"].split("\n")[1])
            [batch] = delivery["batches"]
            ids = [event["id"] for event in batch["events"]]
            if until in ids:
                return ids

    def reload(self) -> None:
        """Shut the extension down and load a fresh instance, as `/reload` does."""
        self.emit("session_shutdown", idle=True, reason="reload")
        assert self.send({"load": True}) == {"loaded": True}
        self.emit("session_start", idle=True, reason="reload")

    def quit(self) -> None:
        """End the session as Pi does on quit, which stops the watch."""
        if not self.ended:
            self.emit("session_shutdown", idle=True, reason="quit")
            self.ended = True


@pytest.fixture
def start_pi(page_dir, monkeypatch, spawn, sessionless):
    """Start a Pi session, in the TUI or as `pi --print`, holding a page claimed
    and served from a shell-tool command run as Pi runs one: Pi's session id, and
    its process as the extension states it. The session then starts, as a
    resumed one does with its pages."""
    started = []

    def start(mode: str) -> Pi:
        driven = Pi(spawn, "pi-s1", mode)
        started.append(driven)
        monkeypatch.setenv("PI_SESSION_ID", driven.session)
        monkeypatch.setenv("LEAF_PI_PID", str(driven.pid))
        service_model.claim_page(page_dir)
        serving(page_dir, 1)
        session_model.cmd_status(page_dir, "waiting", "")
        driven.emit("session_start", idle=True, reason="startup")
        return driven

    yield start
    for driven in started:
        driven.quit()


@pytest.fixture
def pi(start_pi):
    """A Pi session in the TUI, holding a waiting page."""
    return start_pi("tui")


def test_the_pi_extension_carries_a_comment_into_a_new_run(page_dir, pi):
    """The extension calls Leaf's hooks at the points of a Pi run Claude Code
    calls them at a turn, and keeps the watch running from the session's start. A
    comment arriving while Pi is idle wakes the watch, and the extension starts a
    run carrying the whole delivery, which is the same envelope the prompt hook
    hands a Claude Code turn. Ending the session ends the claim's lifetime."""
    claim = service_model.page_claim(page_dir)
    assert (claim["harness"], claim["id"], claim["agent"]) == ("pi", "pi-s1", "Pi")
    assert cleanup_model.session_record("pi-s1")["lifetime"] == {"pid": pi.pid}

    # A run with nothing pending: no context at its prompt, nothing that keeps it
    # going as it settles.
    assert pi.emit("before_agent_start") is None
    pi.emit("agent_start")
    assert pi.emit("agent_before_settle") is None
    pi.emit("agent_settled", idle=True)

    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    sent = pi.message()
    # Pi starts a run when none is going, and steers the running one.
    assert sent["options"] == {"triggerTurn": True, "deliverAs": "steer"}
    instruction, envelope = sent["sent"]["content"].split("\n")[:2]
    assert "acknowledge" in instruction
    [batch] = json.loads(envelope)["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert page_state(page_dir)["pending"] == 1

    pi.quit()
    assert cleanup_model.session_record("pi-s1")["ended"] is not None


def test_the_pi_extension_keeps_a_run_going_for_input_that_arrives_in_it(
    page_dir, start_pi
):
    """Input that arrives during a run with nothing watching, as under
    `pi --print`, is handed over as the run is about to settle, and keeps it
    going. An Escape settles a run without going on from there, and closes the
    turn."""
    pi = start_pi("print")
    pi.emit("before_agent_start")
    pi.emit("agent_start")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "one more"}
    )
    continued = pi.emit("agent_before_settle")
    assert continued["continue"] is True
    [entry] = continued["entries"]
    [batch] = json.loads(entry["content"].split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]

    pi.emit("agent_start")
    pi.emit("agent_settled", idle=True)
    assert cleanup_model.session_record("pi-s1")["turn_closed"] is not None


def test_an_escape_leaves_input_handed_to_the_run_for_the_next_prompt(page_dir, pi):
    """Input steered into a run the user then stops with Escape is not handed to
    a new run of its own (`session.watch_between_turns`); the user's next prompt
    carries it."""
    pi.emit("before_agent_start")
    pi.emit("agent_start")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "handed over"}
    )
    # The watch steers it into the run.
    assert pi.delivered(until=comment["id"]) == [comment["id"]]
    pi.emit("agent_settled", idle=True)
    assert cleanup_model.session_record("pi-s1")["turn_closed"] is not None

    prompt = pi.emit("before_agent_start", idle=True)
    [batch] = json.loads(prompt["message"]["content"].split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]


def test_a_reload_keeps_the_pi_session_and_its_watch(page_dir, pi):
    """`/reload` shuts the extension down and loads it again in the same session,
    so the session's claims stand and the reloaded extension watches them."""
    pi.reload()
    assert cleanup_model.session_record("pi-s1")["ended"] is None
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "after reload"}
    )
    assert pi.delivered(until=comment["id"]) == [comment["id"]]


def test_pi_and_claude_code_nested_either_way_rank_by_process(monkeypatch):
    """Pi run from a Claude Code shell states both sessions, and so does Claude
    Code run from Pi's; the extension's LEAF_PI_PID is what ranks Pi's process
    against CLAUDE_PID."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "outer-claude")
    monkeypatch.setenv("PI_SESSION_ID", "inner-pi")
    monkeypatch.setenv("LEAF_PI_PID", str(os.getpid()))
    monkeypatch.setenv("CLAUDE_PID", str(os.getppid()))
    harness = harness_model.session_harness()
    assert (type(harness), harness.session) == (harness_model.PiHarness, "inner-pi")

    monkeypatch.setenv("LEAF_PI_PID", str(os.getppid()))
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    harness = harness_model.session_harness()
    assert (type(harness), harness.session) == (
        harness_model.ClaudeCodeHarness,
        "outer-claude",
    )


def test_a_pi_session_without_the_leaf_extension_is_refused(
    page_dir, monkeypatch, sessionless
):
    """Pi states its session to every shell-tool command but no process; only
    Leaf's extension states that, so without it there is no lifetime to claim
    a page for."""
    monkeypatch.setenv("PI_SESSION_ID", "pi-bare")
    with pytest.raises(SystemExit, match="extension"):
        service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir) is None
