"""Leaf's Claude Code hooks module (`hooks/claude-code.ts`) keeping a session's
watch in place of the background Stop registration.

`claude_code_driver.mjs` stands in for Claude Code around the module, which calls
the real launcher, so these hold the module and the hooks it calls together."""

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
    serving,
    wait_for,
)
from leaf import hook_carrier as hook_carrier_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model

DRIVER = Path(__file__).with_name("claude_code_driver.mjs")
PLUGIN_ROOT = DRIVER.parents[1]


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
        # Event results and what a wake sends interleave on the driver's stdout,
        # since a watch can wake while an event runs.
        self.answers = queue.Queue()
        self.sent = queue.Queue()
        self.watches = queue.Queue()
        self.exits = queue.Queue()
        threading.Thread(target=self.route, daemon=True).start()
        loaded = self.read()
        self.pid, self.events = loaded["pid"], loaded["events"]

    def route(self) -> None:
        for line in self.process.stdout:
            record = json.loads(line)
            if "watching" in record:
                self.watches.put(record["watching"])
            elif "watched" in record:
                self.exits.put(record["watched"])
            elif "submitted" in record or "appended" in record:
                self.sent.put(record)
            else:
                self.answers.put(record)

    def read(self) -> dict:
        return self.answers.get(timeout=STATED_TIMEOUT)

    def message(self) -> dict:
        """The next prompt the module submits or row it appends."""
        return self.sent.get(timeout=3 * STATED_TIMEOUT)

    def send(self, line: dict) -> None:
        self.process.stdin.write(json.dumps(line) + "\n")
        self.process.stdin.flush()

    def emit(
        self, event: str, e: dict | None = None, answer: dict | None = None
    ) -> dict:
        """Run one event through the module, and return what its hooks returned
        and the input they passed on to the hooks beneath, which answer with
        `answer` where it is given."""
        self.send({"emit": event, "e": e or {}, "answer": answer})
        answer = self.read()
        assert answer["event"] == event, answer
        return answer

    def stop(self) -> dict:
        """The Stop hooks of an ending turn, and the payload the registrations
        beneath the module receive."""
        payload = {"hook_event_name": "Stop", "session_id": self.session}
        return self.emit("classic.Stop", payload)["reached"]

    def start_turn(self) -> None:
        self.emit("turn.start", {"text": "", "turnId": "t"})

    def end_turn(self, *, interrupted: bool = False) -> None:
        """A main-loop turn's ending, by its Stop hooks or by Escape, which runs
        none."""
        if not interrupted:
            self.stop()
        self.emit(
            "turn.complete",
            {"answer": "", "durationMs": 1, "turnId": "t", "isAborted": interrupted},
        )

    def quit(self) -> None:
        if not self.ended:
            self.emit("session.end", {"reason": "other", "sessionId": self.session})
            self.ended = True


@pytest.fixture
def claude_code(page_dir, monkeypatch, spawn, sessionless):
    """A Claude Code session with the module turned on, holding a page claimed and
    served from a Bash tool command as Claude Code runs one: its session id and its
    process. Claude Code's own environment names no session, so neither does the
    module's. The session then starts, as one does when the module loads while it
    holds a page, and the module's watch holds the session's lease, so input posted afterwards
    arrived after the watch's first look rather than pending as it started."""
    driven = ClaudeCode(spawn, "cc-s1", {"hooks_module": True})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", driven.session)
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    service_model.claim_page(page_dir)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    # hooks.json's prompt hook has run for the session by the time it holds a page.
    leases_model.mark_hooks(driven.session)
    driven.emit("session.start", {"cwd": str(page_dir), "isInteractive": True})
    wait_for(
        lambda: leases_model.wait_is_live(None, driven.session),
        bool,
        failure="the module started no watch as the session started",
    )
    yield driven
    driven.quit()


def test_the_module_is_off_until_its_option_is_on(spawn, sessionless):
    """The module hooks nothing unless the user turns its option on, so a default
    install keeps the registrations in `hooks.json`."""
    assert ClaudeCode(spawn, "cc-off", {"hooks_module": False}).events == []


def test_the_module_wakes_an_idle_session_with_a_prompt(page_dir, claude_code):
    """The module keeps the watch from the session's start. A comment arriving
    while the session is idle wakes it, and the module submits the watch's line as
    a prompt, whose prompt hook hands the input over as for any prompt. The line
    starts with the page's path, and Claude Code refuses a plugin's prompt that
    starts with `/`, so the prompt names Leaf first."""
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    sent = claude_code.message()
    assert sent["submitted"].startswith(f"Leaf: {page_dir} has new input"), sent
    assert comment["id"] not in sent["submitted"]


def test_the_module_stands_the_background_registration_down(page_dir, claude_code):
    """Each Stop payload the module passes on is marked, and `hooks.json`'s
    background registration, given that payload with input pending and no other
    watch running, ends silently where the unmarked payload wakes the session.
    Driven the way Claude Code drives it, through a shell with the payload on
    stdin."""
    stamped = claude_code.stop()
    assert stamped["leaf_watch"] == "module"
    claude_code.quit()
    [hook] = [
        hook
        for entry in json.loads((PLUGIN_ROOT / "hooks/hooks.json").read_text())[
            "hooks"
        ]["Stop"]
        for hook in entry["hooks"]
        if hook.get("asyncRewake")
    ]
    cleanup_model.close_session_turn(claude_code.session)
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "pending"}
    )

    def background(payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", "-c", hook["command"]],
            input=json.dumps(payload),
            env=os.environ | {"CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT)},
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )

    marked = background(stamped)
    assert (marked.returncode, marked.stderr) == (0, "")
    unmarked = background({key: stamped[key] for key in stamped if key != "leaf_watch"})
    assert unmarked.returncode == 2
    assert unmarked.stderr.startswith(f"{page_dir} has new input")


def test_the_module_hands_input_to_a_running_turn_and_closes_an_interrupted_one(
    page_dir, claude_code
):
    """Input arriving during a turn is handed to that turn: the module calls the
    prompt hook and appends its delivery, which the turn reads at its next step.
    An Escape then ends the turn with no Stop hook; the module starts the watch
    with the Interrupt payload, which closes the turn the delivery opened and
    wakes the session only for input arriving after it
    (`session.watch_between_turns`)."""
    assert claude_code.watches.get(timeout=STATED_TIMEOUT)["hook_event_name"] == "Stop"
    claude_code.start_turn()
    handed = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "during"}
    )
    appended = claude_code.message()["appended"]
    [batch] = json.loads(appended.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [handed["id"]]

    claude_code.end_turn(interrupted=True)
    interrupt = claude_code.watches.get(timeout=STATED_TIMEOUT)
    # The watch closes the turn after the ending, so it states when that was.
    assert (interrupt["hook_event_name"], "ended_at" in interrupt) == (
        "Interrupt",
        True,
    )
    wait_for(
        lambda: cleanup_model.session_record(claude_code.session)["turn_closed"],
        bool,
        failure="the Escape left the turn open",
    )
    # Input admitted before the new watch's first look waits for the next prompt
    # (`session.watch_between_turns`).
    wait_for(
        lambda: leases_model.wait_is_live(None, claude_code.session),
        bool,
        failure="the module started no watch after the interrupted turn",
    )
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "after"}
    )
    assert claude_code.message()["submitted"].startswith(
        f"Leaf: {page_dir} has new input"
    )


def test_the_module_keeps_a_stop_hooks_delivery_out_of_the_terminal(
    page_dir, claude_code, capsys
):
    """Claude Code prints what a Stop hook continues a turn with in the user's
    terminal, and none of a row a module appends. Input pending as a turn ends,
    with no watch running, is handed over by Leaf's Stop hook inline; the module
    appends that delivery to the session and the turn goes on with one line, so
    the delivery is in the turn's context, as its Picked up says, but not on the
    user's screen."""
    claude_code.start_turn()
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "wakes the watch"}
    )
    claude_code.message()
    pending = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "as it ends"}
    )
    payload = {"hook_event_name": "Stop", "session_id": claude_code.session}
    hooks_model.cmd_hook("claude-code", payload)
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert context.startswith(hook_carrier_model.INLINE_DELIVERY)

    answer = {"additionalContext": [context]}
    result = claude_code.emit("classic.Stop", payload, answer)["result"]
    appended = claude_code.message()["appended"]
    assert appended == context
    [batch] = json.loads(appended.split("\n")[1])["batches"]
    assert [event["id"] for event in batch["events"]] == [pending["id"]]
    [shown] = result["additionalContext"]
    assert hook_carrier_model.INLINE_DELIVERY not in shown


def test_a_wake_during_the_stop_hooks_waits_for_them(page_dir, claude_code):
    """Leaf's Stop hook hands over the input pending as it runs, and decides
    whether the turn goes on. A watch that wakes while a turn's Stop hooks run
    waits for them, so the input has one carrier: here they let the turn end, and
    only then does the module submit its prompt."""
    claude_code.start_turn()
    payload = {"hook_event_name": "Stop", "session_id": claude_code.session}
    claude_code.send({"emit": "classic.Stop", "e": payload, "hold": True})
    assert claude_code.read() == {"holding": "classic.Stop"}
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "during Stop"}
    )
    claude_code.exits.get(timeout=STATED_TIMEOUT)
    assert claude_code.sent.empty()
    claude_code.send({"release": True})
    assert claude_code.read()["event"] == "classic.Stop"
    assert claude_code.message()["submitted"].startswith(
        f"Leaf: {page_dir} has new input"
    )
