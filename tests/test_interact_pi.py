"""Pi as a host: the harness its environment implies, and Leaf's extension
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
from leaf import host as host_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model

DRIVER = Path(__file__).with_name("pi_driver.mjs")


class Pi:
    """One driven Pi process and the session its extension serves."""

    def __init__(self, spawn, session: str):
        self.session = session
        self.ended = False
        self.process = spawn(
            ["node", str(DRIVER), session],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.lines = queue.Queue()
        threading.Thread(
            target=lambda: [self.lines.put(line) for line in self.process.stdout],
            daemon=True,
        ).start()
        self.pid = self.read()["pid"]

    def read(self, timeout: float = STATED_TIMEOUT) -> dict:
        """The driver's next line: a handler's result or a message sent."""
        return json.loads(self.lines.get(timeout=timeout))

    def emit(self, event: str, *, idle: bool = False) -> object:
        """Run one Pi event through the extension, and return what its handlers
        returned."""
        self.process.stdin.write(json.dumps({"emit": event, "idle": idle}) + "\n")
        self.process.stdin.flush()
        answer = self.read()
        assert answer["event"] == event, answer
        return answer["result"]

    def quit(self) -> None:
        """End the session as Pi does on quit, which stops the watch."""
        if not self.ended:
            self.emit("session_shutdown", idle=True)
            self.ended = True


@pytest.fixture
def pi(page_dir, monkeypatch, spawn):
    """A page claimed and served by a Pi session, from a shell-tool command run
    as Pi runs one: Pi's session id, and its process as the extension states it."""
    for name in host_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    driven = Pi(spawn, "pi-s1")
    driven.emit("session_start", idle=True)
    monkeypatch.setenv("PI_SESSION_ID", driven.session)
    monkeypatch.setenv("LEAF_PI_PID", str(driven.pid))
    service_model.claim_page(page_dir)
    serving(page_dir, 1)
    session_model.cmd_status(page_dir, "waiting", "")
    yield driven
    driven.quit()


def test_the_pi_extension_carries_a_comment_into_a_new_run(page_dir, pi):
    """The extension calls Leaf's hooks at the points of a Pi run Claude Code
    calls them at a turn, and starts the watch as each run settles. A comment
    arriving while Pi is idle wakes the watch, and the extension starts a run
    carrying the whole delivery, which is the same envelope the prompt hook hands
    a Claude Code turn. Ending the session ends the claim's lifetime."""
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
    sent = pi.read(timeout=3 * STATED_TIMEOUT)
    assert sent["options"] == {"triggerTurn": True}
    instruction, envelope = sent["sent"]["content"].split("\n")[:2]
    assert "acknowledge" in instruction
    delivery = json.loads(envelope)
    [batch] = delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert page_state(page_dir)["pending"] == 1

    pi.quit()
    assert cleanup_model.session_record("pi-s1")["ended"] is not None


def test_the_pi_extension_keeps_a_run_going_for_input_that_arrives_in_it(page_dir, pi):
    """Input that arrives during a run is handed over as the run is about to
    settle, and keeps it going; an Escape settles a run without that, and closes
    the turn."""
    pi.emit("before_agent_start")
    pi.emit("agent_start")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "one more"}
    )
    continued = pi.emit("agent_before_settle")
    assert continued["continue"] is True
    [entry] = continued["entries"]
    delivery = json.loads(entry["content"].split("\n")[1])
    [batch] = delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]

    pi.emit("agent_start")
    pi.emit("agent_settled", idle=True)
    assert cleanup_model.session_record("pi-s1")["turn_closed"] is not None


def test_pi_and_claude_code_nested_either_way_rank_by_process(monkeypatch):
    """Pi run from a Claude Code shell states both sessions, and so does Claude
    Code run from Pi's; the extension's LEAF_PI_PID is what ranks Pi's process
    against CLAUDE_PID."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "outer-claude")
    monkeypatch.setenv("PI_SESSION_ID", "inner-pi")
    monkeypatch.setenv("LEAF_PI_PID", str(os.getpid()))
    monkeypatch.setenv("CLAUDE_PID", str(os.getppid()))
    harness = host_model.session_harness()
    assert (type(harness), harness.session) == (host_model.PiHarness, "inner-pi")

    monkeypatch.setenv("LEAF_PI_PID", str(os.getppid()))
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    harness = host_model.session_harness()
    assert (type(harness), harness.session) == (
        host_model.ClaudeCodeHarness,
        "outer-claude",
    )


def test_a_pi_session_without_leafs_extension_is_refused(page_dir, monkeypatch):
    """Pi states its session to every shell-tool command but no process; only
    Leaf's extension states that, so without it there is no lifetime to claim
    a page for."""
    for name in host_model.IDENTITY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PI_SESSION_ID", "pi-bare")
    with pytest.raises(SystemExit, match="extension"):
        service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir) is None
