"""Leaf's Claude Code hooks module (`hooks/claude-code.ts`) keeping a session's
watch between turns, and drawing the session's pages above the prompt.

`claude_code_driver.mjs` stands in for Claude Code around the module, which calls
the real launcher, so these hold the module and the hooks it calls together."""

import json
import queue
import socket
import subprocess
import threading
from pathlib import Path

import pytest
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    declare,
    read_record,
    serving,
    wait_for,
)
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import leases as leases_model
from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import thread as thread_model

DRIVER = Path(__file__).parents[1].joinpath("claude_code_driver.mjs")
PLUGIN_ROOT = DRIVER.parents[1]


def test_the_shared_watch_owner_serializes_host_endings(spawn):
    """Both host adapters share the lifecycle exercised with held termination."""
    run = spawn(
        ["node", "--test", str(DRIVER.with_name("watch_owner.test.mjs"))],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output, _ = run.communicate(timeout=STATED_TIMEOUT)
    assert run.returncode == 0, output


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
        self.diagnostics = queue.Queue()
        self.bands = queue.Queue()
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
            elif {"submitted", "dropped", "appended"} & record.keys():
                self.sent.put(record)
            elif "diagnostic" in record:
                self.diagnostics.put(record["diagnostic"])
            elif "band" in record:
                self.bands.put(record["band"])
            else:
                self.answers.put(record)

    def read(self) -> dict:
        return self.answers.get(timeout=STATED_TIMEOUT)

    def message(self) -> dict:
        """The next prompt the module submits, or Claude Code drops, or row it
        appends."""
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
def claude_code(page_dir, monkeypatch, spawn, sessionless, request):
    """A Claude Code session with the module loaded, holding a page claimed and
    served from a Bash tool command as Claude Code runs one: its session id and its
    process. Claude Code's own environment names no session, so neither does the
    module's. The session then starts, as one does when the module loads while it
    holds a page, and the module's watch holds the session's lease, so input posted afterwards
    arrived after the watch's first look rather than pending as it started."""
    driven = ClaudeCode(spawn, "cc-s1", getattr(request, "param", {}))
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


def band_lines(band) -> list[tuple[str, str]]:
    """Each page's line in the band, as its text and the address its link opens;
    none where the module draws nothing."""
    if band is None:
        return []

    def text(node) -> str:
        if isinstance(node, str):
            return node
        return "".join(text(child) for child in node["children"])

    return [
        (text(line), link["props"]["href"])
        for line in band["children"]
        # What the plugins beneath drew, which the driver's bottom leaves empty.
        if line is not None
        for link in line["children"]
        if isinstance(link, dict) and link["tag"] == "Link"
    ]


def test_the_band_follows_the_pages_the_session_holds(
    page_dir, claude_code, monkeypatch
):
    """Above the prompt, each page the session holds is a link with the counts its
    Leaf panel marks that aren't zero: On me, open threads, and those holding words
    the user hasn't read; then what the agent last said it waits for. The band
    redraws as the page's row changes, and empties once the session holds no
    page."""

    def band(expected):
        server_rows_model.RowPublisher(page_dir, server_id).refresh()
        return wait_for(
            lambda: band_lines(claude_code.bands.get(timeout=STATED_TIMEOUT)),
            lambda lines: lines == expected,
            failure=f"the band never showed {expected}",
        )

    server_id = read_record(page_dir / "service.json")["server_id"]
    server_rows_model.RowPublisher(page_dir, server_id).refresh()
    published = server_rows_model.ROW.read(server_rows_model.row_path(page_dir))["row"]
    url, title = server_model.running_server(page_dir)["url"], published["title"]
    band([(f"Leaf {title}", url)])
    # A /clear ends the session and starts none; the next turn follows again.
    claude_code.emit(
        "session.end", {"reason": "clear", "sessionId": claude_code.session}
    )
    band([])
    claude_code.start_turn()
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
    declare(page_dir, detail="Pick a layout")
    band([(f"Leaf {title} · On me 1 · Threads 1, 1 new · Pick a layout", url)])
    # Another session takes the page, so this one holds none.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cc-s2")
    service_model.claim_page(page_dir)
    band([])


@pytest.mark.parametrize("failure", ["watch", "startup", "spawn"])
def test_failed_module_processes_report_their_diagnostics(
    spawn, sessionless, tmp_path, failure
):
    """The native host runs an unavailable or failing external launcher. Neither
    watch startup nor a hook's stderr may disappear behind the adapter."""
    launcher = tmp_path / "bin" / "leaf"
    if failure not in {"startup", "spawn"}:
        launcher.parent.mkdir()
        launcher.write_text('#!/bin/sh\necho "watch launcher failed" >&2\nexit 23\n')
        launcher.chmod(0o755)
    driven = ClaudeCode(
        spawn,
        "cc-failure",
        {
            "pluginRoot": str(tmp_path),
            "throwWatchSpawn": failure == "spawn",
        },
    )
    driven.start_turn()
    driven.emit("session.start", {"cwd": str(tmp_path), "isInteractive": True})
    # The pages follower starts beside the watch, as the turn and the session start,
    # and reports its own failures.
    followers, watches = [], []
    while not (followers and watches):
        line = driven.diagnostics.get(timeout=STATED_TIMEOUT)
        (watches if line.startswith("Leaf: watch") else followers).append(line)
    [diagnostic] = watches
    if failure == "spawn":
        assert (
            diagnostic == "Leaf: watch could not start: Error: host cannot spawn watch"
        )
        expected = (
            "Leaf: the pages follower could not start: Error: host cannot spawn watch"
        )
        assert followers and set(followers) == {expected}, followers
    elif failure == "startup":
        assert "watch failed" in diagnostic and "ENOENT" in diagnostic, diagnostic
        assert followers and all(
            "pages follower failed" in line and "ENOENT" in line for line in followers
        ), followers
    else:
        assert diagnostic == "Leaf: watch failed (exit code 23): watch launcher failed"
        expected = "Leaf: the pages follower exited with code 23: watch launcher failed"
        assert followers and set(followers) == {expected}, followers
    driven.quit()


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


def test_the_module_hands_input_to_a_running_turn_and_closes_an_interrupted_one(
    page_dir, claude_code, capsys, socket_dir
):
    """The module leaves mid-turn input to the native tool-batch boundary.
    An Escape then ends the turn with no Stop hook; the module starts the watch
    with the Interrupt payload, which closes the turn the delivery opened and
    wakes for input the stopped turn never received
    (`session.watch_between_turns`). Claude Code drops the prompt that wake
    submits, as it drops every plugin's prompt from an Escape until the user next
    types, so Leaf messages the session's socket with the input instead, as
    admission does for a session nothing watches."""
    assert claude_code.watches.get(timeout=STATED_TIMEOUT)["hook_event_name"] == "Stop"
    claude_code.start_turn()
    handed = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "during"}
    )
    claude_code.exits.get(timeout=STATED_TIMEOUT)
    claude_code.send({"flush": True})
    assert claude_code.read() == {"submissions": 0}
    for number in range(2):
        comment = (
            handed
            if number == 0
            else append_carried_log_record(
                page_dir, {"kind": "comment", "author": "user", "text": "another"}
            )
        )
        hooks_model.cmd_hook(
            "claude-code",
            {"hook_event_name": "PostToolBatch", "session_id": claude_code.session},
        )
        context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
            "additionalContext"
        ]
        [batch] = json.loads(context.split("\n")[1])["batches"]
        assert comment["id"] in [event["id"] for event in batch["events"]]

    # This one arrives during the turn's last tool, whose batch never ends.
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "unread"}
    )
    listener = messaging_socket(claude_code, socket_dir)
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
    # The watch after Escape wakes for the unread comment at once. The opened
    # receipt removed handed input from the pending batch, so the stopped turn's
    # debt waits for the next prompt (`session.watch_between_turns`).
    assert claude_code.message()["dropped"].startswith(
        f"Leaf: {page_dir} has new input"
    )
    listener.settimeout(STATED_TIMEOUT)
    peer, _ = listener.accept()
    with peer:
        frames = b"".join(iter(lambda: peer.recv(4096), b"")).decode().splitlines()
    _, user = map(json.loads, frames)
    assert user["session_id"] == claude_code.session
    assert str(page_dir.resolve()) in user["message"]["content"]


def messaging_socket(claude_code: ClaudeCode, socket_dir: Path) -> socket.socket:
    """A listening socket registered as the driven session's own, as Claude Code
    registers each session's (`harness.message_claude_code_session`)."""
    address = str(socket_dir / f"{claude_code.pid}.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(address)
    listener.listen()
    sessions = harness_model.claude_code_sessions()
    sessions.mkdir(parents=True, exist_ok=True)
    cleanup_model.write_json(
        sessions / f"{claude_code.pid}.json",
        {
            "pid": claude_code.pid,
            "sessionId": claude_code.session,
            "messagingSocketPath": address,
        },
    )
    cleanup_model.write_json(
        sessions / f"{claude_code.pid}.k.key", {"peerToken": "token"}
    )
    return listener


@pytest.mark.parametrize("claude_code", [{"abortLagMs": 250}], indirect=True)
def test_concurrent_interrupt_endings_keep_one_watch(claude_code):
    """Two endings during cancellation cannot start before the old lease exits."""
    assert (
        claude_code.watches.get(timeout=STATED_TIMEOUT)["previous_active_watches"] == 0
    )
    claude_code.start_turn()
    claude_code.end_turn(interrupted=True)
    claude_code.end_turn(interrupted=True)
    replacement = claude_code.watches.get(timeout=STATED_TIMEOUT)
    assert replacement["hook_event_name"] == "Interrupt"
    assert replacement["previous_active_watches"] == 0


@pytest.mark.parametrize("claude_code", [{"abortLagMs": 250}], indirect=True)
def test_shutdown_during_watch_replacement_waits_for_exit(claude_code):
    """SessionEnd waits for cancellation already in flight and starts no successor."""
    claude_code.watches.get(timeout=STATED_TIMEOUT)
    claude_code.start_turn()
    claude_code.end_turn(interrupted=True)
    claude_code.quit()
    assert not leases_model.wait_is_live(None, claude_code.session)
    assert claude_code.watches.empty()
    assert claude_code.diagnostics.empty()


def test_clear_keeps_the_module_able_to_watch_the_next_session(claude_code):
    """Claude emits session.start once per process; /clear emits only session.end."""
    claude_code.watches.get(timeout=STATED_TIMEOUT)
    claude_code.emit(
        "session.end", {"reason": "clear", "sessionId": claude_code.session}
    )
    claude_code.start_turn()
    claude_code.end_turn()
    assert (
        claude_code.watches.get(timeout=STATED_TIMEOUT)["previous_active_watches"] == 0
    )


def test_a_module_loaded_mid_session_watches_after_its_first_turn(
    page_dir, monkeypatch, spawn, sessionless
):
    """A module loaded or reloaded mid-session sees no session.start, so the first
    turn it sees reads Claude Code's process and the watch it starts holds the
    session's lease."""
    driven = ClaudeCode(spawn, "cc-late", {})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", driven.session)
    monkeypatch.setenv("CLAUDE_PID", str(driven.pid))
    service_model.claim_page(page_dir)
    serving(page_dir, 1)
    session_model.cmd_waiting(page_dir, "")
    leases_model.mark_hooks(driven.session)
    driven.start_turn()
    driven.end_turn()
    wait_for(
        lambda: leases_model.wait_is_live(None, driven.session),
        bool,
        failure="the module started no watch after its first turn",
    )
    driven.quit()


@pytest.mark.parametrize("claude_code", [{"abortLagMs": 250}], indirect=True)
def test_interrupt_watch_replacement_waits_for_aborted_process_exit(
    page_dir, claude_code
):
    """Aborting the output reader is not proof that the child's lease ended.
    Replacement waits for process completion even when output iteration throws."""
    assert claude_code.watches.get(timeout=STATED_TIMEOUT)["hook_event_name"] == "Stop"
    claude_code.start_turn()
    claude_code.end_turn(interrupted=True)
    assert claude_code.exits.get(timeout=STATED_TIMEOUT)["hook_event_name"] == "Stop"
    assert (
        claude_code.watches.get(timeout=STATED_TIMEOUT)["hook_event_name"]
        == "Interrupt"
    )
    wait_for(
        lambda: leases_model.wait_is_live(None, claude_code.session),
        bool,
        failure="the replacement lost its lease to the canceled watch",
    )
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "after Escape"}
    )
    assert claude_code.message()["dropped"].startswith(
        f"Leaf: {page_dir} has new input"
    )


def test_input_pending_as_a_turn_ends_wakes_a_turn_of_its_own(
    page_dir, claude_code, interactive, capsys
):
    """Input pending as a turn ends, with no watch running, stays out of that turn:
    Leaf's Stop registration beneath the module hands it nothing and lets the turn
    end on the answer it wrote, and the watch the module starts as the turn
    completes wakes the session with a prompt for it."""
    claude_code.start_turn()
    first = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "wakes the watch"}
    )
    claude_code.exits.get(timeout=STATED_TIMEOUT)
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": "PostToolBatch", "session_id": claude_code.session},
    )
    capsys.readouterr()
    thread_model.post_reply(
        page_dir, {"parent": first["id"], "responds": first["id"]}, "Yes."
    )
    pending = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "as it ends"}
    )
    reached = claude_code.stop()
    hooks_model.cmd_hook("claude-code", reached)
    assert capsys.readouterr().out == ""
    assert cleanup_model.session_record(claude_code.session)["turn_closed"]

    claude_code.emit(
        "turn.complete",
        {"answer": "", "durationMs": 1, "turnId": "t", "isAborted": False},
    )
    sent = claude_code.message()
    assert sent["submitted"].startswith(f"Leaf: {page_dir} has new input"), sent
    assert pending["id"] not in sent["submitted"]


def test_subagent_turn_after_main_turn_does_not_block_wake(page_dir, claude_code):
    """A subagent can start after the main loop ends; its turn does not make the
    idle main loop busy when the page's next input wakes the watch."""
    assert "classic.Stop" not in claude_code.events
    claude_code.start_turn()
    claude_code.end_turn()
    wait_for(
        lambda: leases_model.wait_is_live(None, claude_code.session),
        bool,
        failure="the module started no watch after the main turn",
    )
    claude_code.emit("turn.start", {"text": "", "turnId": "sub", "agentId": "sub-1"})
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "after main turn"}
    )
    claude_code.exits.get(timeout=STATED_TIMEOUT)
    claude_code.send({"flush": True})
    assert claude_code.read() == {"submissions": 1}
