"""Watching a page between turns: `leaf wait` and a harness's hook watch,
what each watches and what wakes it, when a wait ends, bare-shell and Codex watcher
waits, the one wait a page answers to, reviving a server that died under a wait,
and messaging a Claude Code session nothing watches."""

import json
import os
import socket
import time
from datetime import datetime, timedelta

from interact_support import (
    STATED_TIMEOUT,
    _interaction_prompt_evidence,
    declare,
    fetch,
    publish,
    record_claim,
    yaml_document,
)

from leaf import files as files_model
from leaf import leases as leases_model
from leaf import state as cleanup_model


def test_a_user_move_no_watcher_will_pick_up_messages_its_claude_code_session(
    server, page_dir, tmp_path, monkeypatch, socket_dir, snapshot
):
    """A running turn's Stop hook carries a user move into that turn, and a live
    `leaf wait` wakes the session for one, so the move nobody picks up arrives at a Claude
    Code claim whose turn has closed with no wait lease held — a watcher that died
    after the turn ended. The server then messages that session's socket, found
    by session id in Claude Code's session registry, once per closed turn: a user
    ticking three boxes must not queue three turns or three approvals, and input
    left unacknowledged when the Stop hook failed open must not silence the next
    closed turn.

    The server sends inside the event request, and a Unix connection is queued in
    the listener's backlog before `connect` returns, so a listener with nothing to
    accept once the POST has answered was never messaged."""
    closed = "2026-09-17T09:00:00+00:00"
    publish(page_dir)
    config = tmp_path / "claude"
    (config / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    listeners = {}
    for pid, session_id in ((4101, "s1"), (4102, "s2")):
        address = str(socket_dir / f"{pid}.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(address)
        listener.listen()
        listener.setblocking(False)
        listeners[session_id] = listener
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.json",
            {"pid": pid, "sessionId": session_id, "messagingSocketPath": address},
        )
        cleanup_model.write_json(
            config / "sessions" / f"{pid}.k{pid}.key",
            {"peerToken": f"token-{session_id}"},
        )

    def react(text):
        status, body = fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": text}).encode(),
        )
        assert status == 200, body
        return json.loads(body)["state"]["events"][-1]["seq"]

    def messages(session_id):
        try:
            peer, _ = listeners[session_id].accept()
        except BlockingIOError:
            return None
        with peer:
            peer.settimeout(STATED_TIMEOUT)
            data = b"".join(iter(lambda: peer.recv(4096), b""))
        return [json.loads(line) for line in data.decode().splitlines()]

    try:
        # A turn still running: its Stop hook carries the move.
        record_claim(page_dir)
        react("while the turn runs")
        assert messages("s1") is None

        # A live watcher delivers it.
        claim = record_claim(page_dir, turn_closed=closed)
        lease_path = leases_model.waiter_lease_path(page_dir, claim["id"])
        assert lease_path is not None
        lease = leases_model.take_wait_lease(lease_path)
        assert lease
        react("while a wait holds the lease")
        leases_model.release_lease(lease)
        assert messages("s1") is None

        # Codex's detached adapter queues its own turns; the socket is Claude Code's.
        record_claim(page_dir, harness="codex", turn_closed=closed)
        react("to a Codex task")
        assert messages("s1") is None

        record_claim(page_dir, turn_closed=closed)
        react("after the watcher died")
        auth, user = messages("s1")
        assert auth == {"type": "auth", "token": "token-s1"}
        assert user["type"] == "user" and user["session_id"] == "s1"
        assert user["message"]["role"] == "user"
        assert str(page_dir.resolve()) in user["message"]["content"]
        snapshot.check(
            yaml_document(
                "A real user POST reaches the Claude Code socket after its watcher died.\n"
                "This is the complete user frame, without the separate authentication frame.",
                _interaction_prompt_evidence(page_dir, {"socket user frame": user}),
            )
        )
        assert messages("s2") is None
        react("in the same closed turn")
        assert messages("s1") is None

        # The next closed turn is messaged, whatever is still unacknowledged.
        record_claim(page_dir, turn="turn-2", turn_closed=closed)
        react("in the next closed turn")
        assert messages("s1") is not None

        # Another live session's socket is never a stand-in for the claimant's,
        # and input after a send nobody took tries again.
        record_path = config / "sessions" / "4101.json"
        record = files_model.read_json(record_path)
        record_path.unlink()
        record_claim(page_dir, turn="turn-3", turn_closed=closed)
        react("once the claimant's session has left the registry")
        assert messages("s1") is None and messages("s2") is None
        cleanup_model.write_json(record_path, record)
        react("once it is back")
        assert messages("s1") is not None

        # An interrupted turn runs no Stop hook, so only the session's own record
        # says it ended. A turn nothing has renewed for longer than the working
        # grace may still be running a long step, so it is not messaged; once the
        # record reads idle the input is, once for that ending and again for the
        # next interrupt under the same turn id.
        live = os.getpid()
        cleanup_model.write_json(
            config / "sessions" / f"{live}.k{live}.key", {"peerToken": "token-s1"}
        )
        opened = datetime.now().astimezone() - timedelta(minutes=20)
        record_claim(page_dir, turn="turn-4", turn_opened=opened.isoformat())
        declare(page_dir, ts=opened.isoformat())
        # `None` leaves the record as it stands: more input after the same ending.
        # A `shell` flip is the same ending seen again; a new prompt renews the
        # turn, and the interrupt after it is a new one.
        for status, prompt, messaged in (
            ("busy", False, False),
            ("idle", False, True),
            (None, False, False),
            ("shell", False, False),
            ("busy", True, False),
            ("idle", False, True),
        ):
            if prompt:
                time.sleep(1)
                cleanup_model.prompt_turn("s1")
            if status is not None:
                time.sleep(0.01)
                cleanup_model.write_json(
                    record_path,
                    {
                        **record,
                        "pid": live,
                        "status": status,
                        "statusUpdatedAt": int(time.time() * 1000),
                    },
                )
            react(f"while the session's record reads {status}")
            assert (messages("s1") is not None) is messaged, status
    finally:
        for listener in listeners.values():
            listener.close()


import shlex
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

from conftest import LEAF_COMMAND
from interact_support import (
    acknowledged_through,
    append_carried_log_record,
    available_loopback_port,
    claim_and_wait_command,
    declare_idle,
    held_selection,
    page_state,
    printed,
    read_record,
    said,
    serving,
    wait_for,
    woken,
    write_record,
)

from leaf import hooks as hooks_model
from leaf import hosting as hosting_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model


def test_wait_restarts_a_server_that_died_under_it(
    page_dir, comment_once_served, capsys, snapshot
):
    """A page whose server died is offline in the user's browser and nowhere
    else — so `leaf wait`, the one thing positioned to notice, brings it back
    rather than exiting and leaving the discovery to the user."""

    write_record(
        page_dir / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "session",
        },
    )
    comment_once_served(page_dir)
    service_model.claim_page(page_dir)
    assert session_model.cmd_wait(page_dir) == 0
    info = server_model.running_server(page_dir)
    # The revived server has to answer on the URL it published, key included:
    # the user's browser has been polling that address since it died.
    assert info
    state = urllib.parse.urlsplit(info["url"])
    assert (
        urllib.request.urlopen(state._replace(path="/api/state").geturl()).status == 200
    )
    printed = capsys.readouterr()
    assert "server had died; restarted" in printed.err
    snapshot.check(
        yaml_document(
            "A wait revives its server, notes the recovery, and delivers input.\n"
            "The URL's dynamic port and access token are represented by <served-url>.",
            _interaction_prompt_evidence(
                page_dir,
                {
                    "exit": 0,
                    "stderr": said(printed.err.replace(info["url"], "<served-url>")),
                },
            ),
        )
    )
    # This session explicitly claimed the page, so what the wait revives is its
    # session's server and dies with that session. Here the session is the
    # worker (conftest), which is what keeps a killed run from stranding this.
    assert read_record(page_dir / "service.json")["lifetime"] == "session"


def test_wait_revival_cannot_take_a_page_back_after_claim_transfer(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """A stale wait cannot revive a server for a page it no longer owns.

    The waiter holds after it selected the page but before it checks the dead
    server. Another session then claims the page. The old wait must leave without
    spawning a server under its stale ownership decision.
    """
    page = codex_claimed_page
    hosting_model.cmd_stop(page)
    session_model.cmd_waiting(page)
    selected = page.parent / "selected"
    first = under_codex(
        shlex.join([*LEAF_COMMAND, "page", "claim", str(page), "--manual-delivery"])
        + " >/dev/null && "
        + shlex.join(held_selection(selected, page, "wait", str(page))),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(selected.exists, bool, failure="the waiter never selected its page")

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    declare_idle(page)

    first_out, first_err = first.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert "no longer owns it" in first_err
    assert "the page closed" not in first_err
    session = service_model.page_claim(page)
    assert session is not None
    assert session["id"] == "replacement"
    assert server_model.running_server(page) is None


def test_the_newest_watch_takes_the_session_over(claimed, monkeypatch, capsys):
    """Claude Code starts a watch at every turn's end and leaves the earlier one
    running, so the newest takes the session's lease, and the watch it displaces
    ends without waking anyone. That is how a Leaf update reaches the watch: the
    earlier one may run a Leaf that cannot read a page the session now holds,
    while the new one runs the Leaf the harness runs now. A `leaf wait` the
    model left running gives way to it too."""
    leases_model.mark_hooks("s1")
    serving(claimed, 1)
    session_model.cmd_waiting(claimed)
    stop = {"hook_event_name": "Stop", "session_id": "s1"}
    passed = {name: threading.Event() for name in ("wait", "older", "newer")}
    await_news = session_model.Watch.await_news

    def after_a_pass(watch, mark, *args, **kwargs):
        passed[threading.current_thread().name].set()
        return await_news(watch, mark, *args, **kwargs)

    monkeypatch.setattr(session_model.Watch, "await_news", after_a_pass)

    def started(name: str, run) -> tuple[threading.Thread, list]:
        outcome = []
        thread = threading.Thread(name=name, target=lambda: outcome.append(run()))
        thread.start()
        assert passed[name].wait(STATED_TIMEOUT), f"{name} never completed a pass"
        assert leases_model.wait_is_live(claimed, "s1")
        return thread, outcome

    def ended(thread: threading.Thread, outcome: list):
        thread.join(timeout=STATED_TIMEOUT)
        assert not thread.is_alive(), f"{thread.name} went on watching"
        [result] = outcome
        return result

    wait, waited = started("wait", session_model.cmd_wait)
    older, olders = started("older", lambda: hooks_model.cmd_watch("claude-code", stop))
    assert ended(wait, waited) == 2
    assert "took over" in capsys.readouterr().err
    newer, newers = started("newer", lambda: hooks_model.cmd_watch("claude-code", stop))
    assert ended(older, olders) is None
    append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "after"}
    )
    assert ended(newer, newers).startswith(f"{claimed} has new input")
    assert not leases_model.wait_is_live(claimed, "s1")


def test_a_revived_server_keeps_the_lifetime_it_was_serving_under(
    claimed, comment_once_served
):
    """A persistent page comes back persistent. The lifetime is the page's record
    rather than the reviving process's, so the restarts a page doesn't choose —
    a crash, the revival a `leaf wait` makes under it — leave it as the serve
    that started it declared, and `leaf server stop` is still the one thing that
    ends one. Read off the launch instead, a session that happened to notice the
    server was down would inherit a dashboard somebody left up for weeks, and
    take it down when it ended."""
    write_record(
        claimed / "service.json",
        {
            "host": "127.0.0.1",
            "bind": "127.0.0.1",
            "port": available_loopback_port(),
            "enabled": True,
            "lifetime": "persistent",
        },
    )
    comment_once_served(claimed)
    assert session_model.cmd_wait(claimed) == 0
    # The reviving session did claim the page, so a lifetime read off this
    # launch would have said "session" — the claim is what the persistent
    # record has to outrank.
    claim_record_2 = service_model.page_claim(claimed)
    assert claim_record_2 is not None
    assert claim_record_2["id"] == "s1"
    assert read_record(claimed / "service.json")["lifetime"] == "persistent"


def test_a_harness_claim_supersedes_a_bare_shell_wait(page_dir, sessionless, spawn):
    """A page has one wait owner even when the first has no harness identity."""
    session_model.cmd_waiting(page_dir)
    serving(page_dir, 1)
    bare = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: leases_model.lock_is_held(page_dir / "waiter.lock"),
        bool,
        failure="the bare wait never took its lease",
    )

    harness_env = os.environ | {
        "CLAUDE_CODE_SESSION_ID": "harness-owner",
        "CLAUDE_PID": str(os.getpid()),
    }
    leases_model.mark_hooks("harness-owner")  # its harness runs Leaf's hooks
    subprocess.run(
        [*LEAF_COMMAND, "page", "claim", str(page_dir)], env=harness_env, check=True
    )
    harness = spawn(
        [*LEAF_COMMAND, "wait", str(page_dir)],
        env=harness_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: service_model.page_claim(page_dir),
        lambda claim: bool(
            claim
            and claim["id"] == "harness-owner"
            and (lease_path := leases_model.waiter_lease_path(page_dir, claim["id"]))
            is not None
            and leases_model.lock_is_held(lease_path)
        ),
        failure="the harness wait never claimed the page and took its lease",
    )

    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "once", "author": "user", "text": "hi"},
    )
    bare_out, bare_err = bare.communicate(timeout=STATED_TIMEOUT)
    harness_out, harness_err = harness.communicate(timeout=STATED_TIMEOUT)

    assert (bare.returncode, bare_out) == (2, ""), bare_err
    assert "no longer owns it" in bare_err
    assert harness.returncode == 0, harness_err
    _, _, shown = woken(harness_out, "harness-owner")
    assert [event["id"] for event in shown] == ["once"]


def test_a_codex_watcher_task_takes_the_parent_watch_obligation(
    codex_claimed_page, under_codex, codex_env, capsys
):
    """The task that blocks in wait is the claimant, not the task it wakes.

    That transfer is the bridge: the parent may finish its turn because it no
    longer owns an unattended page, while the helper's own Stop hook keeps the
    wait inside a live turn. Leaf does not need to know where that task sends the
    batch.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    watcher = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher" and reading[1],
        failure="the watcher task never claimed the page and entered leaf wait",
    )
    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "codex-thread"}
    )
    assert capsys.readouterr().out == ""

    hooks_model.cmd_hook(
        "codex", {"hook_event_name": "Stop", "session_id": "leaf-watcher"}
    )
    reason = json.loads(capsys.readouterr().out)["reason"]
    assert "Keep this turn active" in reason and "poll the existing" in reason

    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    out, err = watcher.communicate(timeout=STATED_TIMEOUT)
    assert watcher.returncode == 0, f"{out}{err}"
    _, header, [event] = printed(out)
    assert header["page"] == str(page)
    assert event["text"] == "hi"
    assert acknowledged_through(page) == 0


def test_a_superseded_waiter_cannot_deliver_the_new_owners_batch(
    codex_claimed_page, under_codex, codex_env
):
    """One page has one cursor owner even if two watcher tasks are started.

    Transfer the claim after the old wait selects its subscription roots, before
    it opens them. The earlier wait must leave cleanly when its claim directory
    disappears, without printing input that belongs to the replacement.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    selected = page.parent / "waiter-selected-roots"
    held_subscription = """
import sys
from pathlib import Path
from leaf import session
from leaf.__main__ import main
from leaf.service import claim_page

constructor = session.FileChanges
marker, page = map(Path, sys.argv[1:])
def subscribing(*args, **kwargs):
    session.FileChanges = constructor
    marker.write_text("selected")
    sys.stdin.readline()
    return constructor(*args, **kwargs)

session.FileChanges = subscribing
assert claim_page(page)
sys.argv = ["leaf", "wait", str(page)]
main()
"""

    first = under_codex(
        shlex.join([sys.executable, "-c", held_subscription, str(selected), str(page)]),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        selected.exists,
        bool,
        failure="the first watcher never selected its subscription roots",
    )

    second = under_codex(
        claim_and_wait_command(page),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-2"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for(
        lambda: (service_model.page_claim(page) or {}, page_state(page)["listening"]),
        lambda reading: reading[0].get("id") == "leaf-watcher-2" and reading[1],
        failure="the replacement watcher never claimed the page and entered leaf wait",
    )

    first_out, first_err = first.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    assert second.poll() is None
    assert page_state(page)["listening"]

    comment = append_carried_log_record(
        page, {"kind": "comment", "author": "user", "text": "hi"}
    )
    second_out, second_err = second.communicate(timeout=STATED_TIMEOUT)

    assert second.returncode == 0, f"{second_out}{second_err}"
    _, header, [event] = printed(second_out)
    assert header["page"] == str(page)
    assert event["seq"] == comment["seq"]


def test_a_claim_transfer_stops_a_waiter_already_inside_a_poll(
    codex_claimed_page, under_codex, codex_env, monkeypatch
):
    """Ownership is checked at delivery, not only at the start of a poll.

    The first watcher holds after it has selected its page. A second session then
    takes the claim and an event arrives. The old watcher must re-read ownership
    before it prints that event; otherwise two sessions can act as cursor owner
    despite the supersession check passing on every ordinary run.
    """
    page = codex_claimed_page
    session_model.cmd_waiting(page)
    selected = page.parent / "waiter-selected-page"
    first = under_codex(
        shlex.join([*LEAF_COMMAND, "page", "claim", str(page), "--manual-delivery"])
        + " >/dev/null && "
        + shlex.join(held_selection(selected, page, "wait", str(page))),
        codex_env | {"CODEX_THREAD_ID": "leaf-watcher-1"},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wait_for(
        selected.exists,
        bool,
        failure="the first watcher never selected its page before the transaction",
    )
    claim_record = service_model.page_claim(page)
    assert claim_record is not None
    assert claim_record["id"] == "leaf-watcher-1"

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "replacement")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page)
    append_carried_log_record(page, {"kind": "comment", "author": "user", "text": "hi"})
    first_out, first_err = first.communicate(input="continue\n", timeout=STATED_TIMEOUT)
    assert (first.returncode, first_out) == (2, ""), first_err
    session = service_model.page_claim(page)
    assert session is not None
    assert session["id"] == "replacement"
