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
