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
    HELD_LEASES,
    STATED_TIMEOUT,
    append_carried_log_record,
    available_loopback_port,
    serving,
    wait_for,
)
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf.refusals import Refused

DRIVER = Path(__file__).parents[1].joinpath("pi_driver.mjs")


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
        self.closed_watches = 0
        threading.Thread(target=self.route, daemon=True).start()
        self.pid = self.read()["pid"]

    def route(self) -> None:
        for line in self.process.stdout:
            record = json.loads(line)
            if record.get("type") == "leaf_watch_closed":
                self.closed_watches += record["code"] == 0
                continue
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

    def emit(
        self,
        event: str,
        *,
        idle: bool = False,
        reason: str = "",
        aborted: bool = False,
        message: dict | None = None,
    ) -> object:
        """Run one Pi event through the extension, and return what its handlers
        returned."""
        answer = self.send(
            {
                "emit": event,
                "idle": idle,
                "reason": reason,
                "aborted": aborted,
                "message": message,
            }
        )
        assert answer["event"] == event, answer
        return answer["result"]

    def delivered(self, until: str) -> list[str]:
        """The ids of the events in the first message the extension sends that
        carries event `until`: the delivery the prompt hook returned."""
        while True:
            self.message()
            self.emit("agent_start")
            continued = self.emit("turn_end")
            [entry] = continued["entries"]
            delivery = json.loads(entry["content"].split("\n")[1])
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


@pytest.fixture(name="start_pi")
def start_pi_fixture(page_dir, monkeypatch, spawn, sessionless):
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
        session_model.cmd_waiting(page_dir, "")
        driven.emit("session_start", idle=True, reason="startup")
        return driven

    yield start
    for driven in started:
        driven.quit()


@pytest.fixture(name="pi")
def pi_fixture(start_pi):
    """A Pi session in the TUI, holding a waiting page."""
    return start_pi("tui")


def test_the_pi_extension_keeps_a_run_going_for_input_that_arrives_in_it(
    page_dir, start_pi
):
    """Input that arrives during a run with nothing watching, as under
    `pi --print`, is handed over as the run is about to settle, and keeps it
    going."""
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


def test_an_escape_leaves_input_handed_to_the_run_for_the_next_prompt(page_dir, pi):
    """Input handed to a run the user then stops with Escape is not handed to a
    new run of its own (`session.watch_between_turns`). The Escape settles the
    run without going on from there, and the watch the extension starts then
    closes the turn. The hook confirmed the input as it handed it over, so the
    user's next prompt carries it as a move still owed its answer, picked up
    again in that run."""
    pi.emit("before_agent_start")
    pi.emit("agent_start")
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "handed over"}
    )
    # The watch wakes, and the run's next turn end adds the delivery to the
    # session and keeps the run going to read it.
    handed = wait_for(
        lambda: pi.emit("turn_end"), bool, failure="no turn end took the input"
    )
    assert handed["continue"] is True
    [entry] = handed["entries"]
    [batch] = json.loads(entry["content"].split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    ref = batch["events"][0]["answer"]["ref"]
    pi.emit("agent_settled", idle=True)
    wait_for(
        lambda: cleanup_model.session_record("pi-s1")["turn_closed"],
        bool,
        failure="the Escape left the turn open",
    )

    assert pi.emit("before_agent_start", idle=True) is None
    pi.emit("agent_start")
    continued = pi.emit("turn_end")
    [entry] = continued["entries"]
    assert f"`leaf response reply {ref}`" in entry["content"]
    pickup = events_model.read_events(page_dir)[-1]
    assert (pickup["kind"], pickup["events"], pickup["turn"]) == (
        "pickup",
        [comment["id"]],
        cleanup_model.session_record("pi-s1")["turn"],
    )


def test_the_pi_watch_restarts_a_session_server_that_died(page_dir, pi):
    """The watch the extension runs revives the session's server as `leaf wait`
    would. The server it starts must serve as the Pi session the hook names,
    though nothing in the hook's environment names that session."""
    leases_model.release_lease(HELD_LEASES.pop())
    cleanup_model.write_json(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    wait_for(
        lambda: server_model.running_server(page_dir),
        bool,
        failure="the Pi watch never restarted the dead session server",
    )
    claim = service_model.page_claim(page_dir)
    assert (claim["harness"], claim["id"]) == ("pi", "pi-s1")


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
    with pytest.raises(Refused, match="extension"):
        service_model.claim_page(page_dir)
    assert service_model.page_claim(page_dir) is None
