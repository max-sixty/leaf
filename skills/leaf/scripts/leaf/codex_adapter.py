"""The detached process that carries Leaf delivery into later turns of one Codex task.

Serving a claimed page, or explicitly running `leaf codex start`, leaves this
process running behind the turn that started it, so a user's later moves reach
the same Codex task instead of waiting for the agent to ask again. It owns the session watch: it captures each batch into the
task's delivery record, offers one delivery at a time, and reconciles the receipt its
page is owed however that delivery was taken.

While a proven async tool hook has a running turn, it can offer the shared record
between steps (`codex.offer_hook_delivery`). The adapter reserves its own route
only when that turn is idle or no such hook has run, and an unread hook pointer
then falls back to the same durable delivery.

One of two transports carries the adapter's offer. The `codex queue` command is the
default for a task whose App Server Leaf cannot reach, such as the Codex desktop
app's. It leaves a pointer for the task's next turn; the task reads that
immutable input through `leaf delivery read` and answers with explicit commands, the
reply included. Over App Server, one `TaskConnection` owns the subscribed socket,
serializes starts, and routes every notification into one `TurnFold` per provider
turn. It observes the user's turns and Leaf delivery turns alike. Losing the
connection disconnects the folds; reconnecting reconciles them with the provider's
transcript, because a terminal task keeps running after this adapter disconnects.

`codex.py` owns the protocol, the per-turn fold every carrier runs, the delivery
records, and the page writers both transports share. What is here is the process
around them.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path

# The stream-activity writers are called as `codex.<name>`, so `leaf.codex` holds their
# one binding: whatever takes a turn's readings there takes every carrier's too.
from . import codex
from .codex import (
    START_TIMEOUT,
    AppServerDeliveryUncertain,
    TurnFold,
    accept_codex_delivery,
    app_server_connect,
    app_server_delivery_id,
    app_server_handshake,
    app_server_request,
    append_batch,
    archive_record,
    check_app_server_endpoint,
    delivery_record_state,
    delivery_records,
    delivery_stream_reply_target,
    finish_codex_batch,
    offer_delivery,
    retire_gone_task_records,
    retry_delay,
    start_app_server_delivery,
    stop_app_server,
    stream_reply_target,
    write_record,
)
from .codex_state import delivery_lock_path, hook_turn, step_delivery_turn
from .detached import Handshake, starting_detached
from .event_log import read_cursor
from .harness import CodexHarness, Harness, session_harness
from .leases import (
    adapter_is_live,
    adapter_lease_path,
    release_lease,
    session_state_path,
    take_lease,
)
from .machine import state_home
from .service import (
    PageTransaction,
    claim_page,
    owned_pages,
)
from .session import Watch, read_watch_pass
from .state import (
    EVENTS_FILE,
    ensure_session,
    flocked,
    session_record,
    start_session_turn,
)
from .thread import (
    answered_by_reply,
    delivery_reply_reserved,
)
from .thread_titles import app_server_title, name_untitled_threads

QUEUE_TIMEOUT = 20
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"


def _run_codex(codex_path: str, *arguments: str) -> None:
    try:
        completed = subprocess.run(
            [codex_path, *arguments],
            capture_output=True,
            text=True,
            timeout=QUEUE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Codex queue command timed out") from error
    if completed.returncode == 0:
        return
    detail = completed.stderr.strip() or completed.stdout.strip()
    if not detail:
        detail = f"Codex exited with status {completed.returncode}"
    raise RuntimeError(detail)


def check_queue_command(codex_path: str) -> None:
    """Prove that this Codex installation provides durable task queueing."""
    _run_codex(codex_path, "queue", "--help")


def queue_delivery(
    codex_path: str,
    thread_id: str,
    prompt: str,
) -> None:
    """Hand one pointer prompt to Codex's durable same-task queue."""
    arguments = ["queue"]
    arguments.extend(["--thread", thread_id, "--message", prompt])
    _run_codex(codex_path, *arguments)


class TaskConnection:
    """Own a task's subscription and serialized delivery starts on one socket.

    Only this owner's thread reads or writes the socket. The watcher submits a
    delivery through a Future, without holding page or delivery locks. Requests
    fold notifications while waiting; a start buffers them until its response
    binds the returned turn, then replays them in arrival order. Every provider
    turn has one fold, whether the user or Leaf started it.

    A dropped connection is unknown provider state, never a failed turn. Resuming
    reconciles running and completed turns from their exact delivery identities.
    A persisted starting offer is never blindly repeated after an uncertain send.
    Live provider observations adopt the subscription's lifecycle token before
    fold selection. A resume response uses its pre-request token, so intervening
    notifications or a newer prompt win; exact historical answers settle without
    adopting a current lifecycle. Matching completion refreshes the token for the
    next natural provider turn.
    """

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.turns: dict[str, TurnFold] = {}
        self.running: str | None = None
        self.lifecycle = session_record(thread_id)
        self.stop_event = threading.Event()
        self.socket = None
        self.started = False
        self.commands: queue.Queue[tuple[dict, Future]] = queue.Queue()
        self.submission_lock = threading.Lock()
        self.connected = threading.Event()
        self.ready: queue.Queue[BaseException | None] = queue.Queue(maxsize=1)
        self.thread = threading.Thread(
            target=self._run,
            name="leaf-codex-app-server",
            daemon=True,
        )

    def start(self) -> None:
        self.thread.start()
        try:
            outcome = self.ready.get(timeout=START_TIMEOUT)
        except queue.Empty as error:
            self.stop()
            raise RuntimeError("Codex App Server did not answer") from error
        if outcome is not None:
            self.stop()
            raise RuntimeError(f"Codex App Server connection failed: {outcome}")

    def stop(self) -> None:
        with self.submission_lock:
            self.stop_event.set()
        if self.socket is not None:
            self.socket.close()
        self.thread.join()

    def start_delivery(self, payload: dict) -> bool:
        """Request a fresh idle check and start; wait without owning shared locks."""
        with self.submission_lock:
            if self.stop_event.is_set():
                raise RuntimeError("Codex App Server client stopped")
            result = Future()
            self.commands.put((payload, result))
        return result.result()

    def working(self) -> bool:
        """Whether the last notification read left a turn of the task's running.

        This comes off the standing subscription, so the delivery loop can hold back
        without opening a connection every second to ask. It can lag, which is why
        it only ever holds a delivery back: the status that lets one start is read
        on this subscription, one request before the start. A disconnected owner
        also holds offers back until its resumed provider state is known.
        """
        return not self.connected.is_set() or self.running is not None

    def _send(self, socket, method: str, request_id: int, params: dict) -> dict:
        """Request on the owner's socket, folding notifications while waiting."""
        return app_server_request(
            socket,
            method,
            request_id,
            params,
            self._read,
            stopped=self.stop_event.is_set,
        )

    def _resume_task(self, socket, *, exclude_turns: bool) -> tuple[dict, dict | None]:
        """Capture the causal lifecycle token before authoritative provider metadata."""
        expected = session_record(self.thread_id)
        self.lifecycle = expected
        result = self._send(
            socket,
            "thread/resume",
            1,
            {
                "threadId": self.thread_id,
                "excludeTurns": exclude_turns,
            },
        )
        return result.get("thread") or {}, expected

    def _connect(self) -> None:
        with app_server_connect(self.endpoint) as socket:
            self.socket = socket
            if self.stop_event.is_set():
                return
            app_server_handshake(socket, 0, "leaf", "Leaf", self._read)
            thread, expected = self._resume_task(socket, exclude_turns=False)
            hydrated = self._resume(thread, expected)
            self._reconcile_history(socket, hydrated)
            self.connected.set()
            if not self.started:
                self.started = True
                self.ready.put(None)
            while not self.stop_event.is_set():
                try:
                    payload, result = self.commands.get_nowait()
                except queue.Empty:
                    pass
                else:
                    try:
                        outcome = self._start_delivery(socket, payload)
                    except Exception as error:
                        result.set_exception(error)
                        # A refused request leaves the subscription usable; an
                        # uncertain send or any other reader fault needs resume.
                        if not isinstance(error, codex.AppServerRequestRejected):
                            raise
                    else:
                        result.set_result(outcome)
                    continue
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _start_delivery(self, socket, payload: dict) -> bool:
        """Check provider status, then start once with a durable uncertain boundary."""
        with flocked(delivery_lock_path(self.thread_id)):
            path = codex.record_path(self.thread_id, payload["id"])
            record = codex.read_record(path)
            if record is None or record["state"] in {"accepted", "abandoned"}:
                return True
            uncertain = (record.get("transport") or {}).get("phase") == "starting"
        thread, expected = self._resume_task(socket, exclude_turns=not uncertain)
        if uncertain:
            hydrated = self._resume(thread, expected)
            self._reconcile_history(socket, hydrated)
            return delivery_record_state(self.thread_id, payload["id"]) in {
                "accepted",
                "abandoned",
            }
        status = thread.get("status") or {}
        if status.get("type") == "active" or self.running is not None:
            return False
        if status.get("type") != "idle":
            raise RuntimeError(
                f"the Codex task is not taking turns: {status.get('type', 'unknown')}"
            )
        # The status request folds callbacks, so its receipt may have accepted
        # and archived this offer. Re-read at the intent transition rather than
        # restoring the stale offering object captured before that request.
        with flocked(delivery_lock_path(self.thread_id)):
            record = codex.read_record(path)
            if record is None or record["state"] in {"accepted", "abandoned"}:
                return True
            record["transport"] = {"phase": "starting", "turn": None}
            write_record(path, record)
        buffered: list[dict] = []
        requested = False

        def send(method, params):
            nonlocal requested
            requested = True
            return app_server_request(
                socket,
                method,
                2,
                params,
                buffered.append,
                stopped=self.stop_event.is_set,
            )

        try:
            admitted = start_app_server_delivery(send, self.thread_id, payload)
        except BaseException as error:
            if not requested or isinstance(error, codex.AppServerRequestRejected):
                with flocked(delivery_lock_path(self.thread_id)):
                    refused = codex.read_record(path)
                    if refused is not None and refused["state"] == "offering":
                        refused["transport"] = {"phase": "app-server", "turn": None}
                        write_record(path, refused)
            for message in buffered:
                self._read(message)
            raise
        self.lifecycle = admitted
        turn_id = admitted["turn"]
        fold = self._fold(turn_id, payload["id"], follow=True)
        if fold is None:
            raise AppServerDeliveryUncertain(
                "a newer session epoch superseded the provider start"
            )
        self.running = turn_id
        fold.set_activity({"kind": "working"})
        for message in buffered:
            self._read(message)
        return True

    def _reconcile_history(self, socket, hydrated: set[str] | None = None) -> None:
        """Hydrate unresolved turns and deliveries from complete provider history.

        A resume may omit older turns. Exhaust its explicit pagination before
        abandoning an absent delivery; summaries or unloaded items cannot prove
        absence. Abandonment gives up this harness's attempt, never the provider turn.
        """
        codex.settle_answered_deliveries(self.thread_id)
        with flocked(delivery_lock_path(self.thread_id)):
            pending = {
                path.stem
                for path, record in delivery_records(self.thread_id)
                if record["state"] == "offering"
                and (record.get("transport") or {}).get("phase") == "starting"
            }
        # Receipts may already have archived an accepted delivery while its
        # provider turn was still running. A successful exact reply is the
        # completion evidence, independent of reservation or settlement lifetime.
        hydrated = hydrated or set()
        known = set(self.turns) - hydrated
        unresolved = set()
        directory = codex.delivery_dir(self.thread_id)
        for path in (
            *directory.glob("*.json"),
            *(directory / "history").glob("*.json"),
        ):
            record = codex.read_record(path)
            if record is None or record.get("state") not in {"accepted", "abandoned"}:
                continue
            if (record.get("transport") or {}).get("turn") in hydrated:
                continue
            target = delivery_stream_reply_target(self.thread_id, path.stem)
            if target is not None:
                try:
                    with PageTransaction(Path(target["page"])) as page:
                        answered = answered_by_reply(page.events, target["responds"])
                except FileNotFoundError:
                    continue
                if not answered:
                    unresolved.add(path.stem)
        if not (pending or known or unresolved):
            return
        cursor = None
        while True:
            expected = self.lifecycle
            page = self._send(
                socket,
                "thread/turns/list",
                3,
                {
                    "threadId": self.thread_id,
                    "itemsView": "full",
                    "cursor": cursor,
                },
            )
            for turn in page["data"]:
                if not _turn_items_complete(turn):
                    raise RuntimeError(
                        "Codex App Server did not return full turn items"
                    )
                delivery_id = _turn_delivery_id(turn)
                if delivery_id in pending | unresolved or turn["id"] in known:
                    self._reconcile(turn, expected)
                    pending.discard(delivery_id)
                    unresolved.discard(delivery_id)
                    known.discard(turn["id"])
            cursor = page["nextCursor"]
            if not (pending or known or unresolved) or cursor is None:
                break
        # The snapshot may precede notifications folded during pagination. Any
        # running turn holds back abandonment until a fresh idle reading.
        if pending and self.running is None:
            fresh, _ = self._resume_task(socket, exclude_turns=True)
            if (fresh.get("status") or {}).get(
                "type"
            ) != "idle" or self.running is not None:
                return
            for delivery_id in pending:
                codex.abandon_uncertain_delivery(
                    self.thread_id,
                    codex.read_json(codex.delivery_path(delivery_id)),
                )

    def _resume(self, thread: dict, expected: dict | None | object = ...) -> set[str]:
        """Reconcile task metadata; return turn IDs whose full items were read."""
        # A followed turn the snapshot does not list — a paginated thread's `turns`
        # can leave it out — stays disconnected until it says something.
        turns = thread.get("turns", [])
        # Only metadata naming a current turn establishes running identity;
        # every snapshot turn is read by the same reconciliation owner.
        if expected is ... or self.lifecycle == expected:
            self.running = None
        hydrated = {turn["id"] for turn in turns if self._reconcile(turn, expected)}
        status = thread.get("status", {})
        fold = self.turns.get(self.running) if self.running is not None else None
        if status.get("type") == "active" and any(
            turn["id"] == self.running and turn.get("status") == "inProgress"
            for turn in turns
        ):
            if fold is not None:
                fold.absorb(
                    {
                        "method": "thread/status/changed",
                        "params": {
                            "threadId": self.thread_id,
                            "turnId": self.running,
                            "status": status,
                        },
                    }
                )
        elif self.running is None:
            # A previous connection may have died without its disconnect cleanup.
            # This snapshot does not establish a current provider turn, so an
            # old thinking, tool, waiting, or replying observation cannot prove
            # one is still live.
            codex.clear_stream_activity(
                self.thread_id,
                expected=self.lifecycle if expected is ... else expected,
            )
        return hydrated

    def _reconcile(self, turn: dict, expected: dict | None | object = ...) -> bool:
        """Bring one snapshot turn's fold up to what the snapshot says of it.

        A running turn is followed, whether or not it was before the connection
        dropped. An ended one is committed if something here was following it, or
        if it carries a delivery: its item was written while this connection was
        down, or its carrier process died while the turn ran on, and its answer
        is still to write. Its turn is closed, never reopened. The snapshot's other
        turns are history. Return whether this snapshot supplied complete items.
        """
        # A completion with unloaded items says it ended, but cannot say what
        # it answered. Preserve its fold and reservation until full hydration.
        running = turn.get("status") == "inProgress"
        complete = _turn_items_complete(turn)
        if not running and not complete:
            return False
        if running and not self._observe_lifecycle(turn["id"], expected):
            return False
        fold = self._fold(
            turn["id"], _turn_delivery_id(turn), follow=running, ended=not running
        )
        if fold is None:
            return complete
        if running:
            self.running = turn["id"]
            if complete:
                fold.restore(turn)
        else:
            if self.running == turn["id"]:
                self.running = None
            self.turns.pop(turn["id"], None)
            fold.commit(turn)
            self._refresh_lifecycle(turn["id"])
        return complete

    def _read(self, message: dict) -> None:
        """Route one notification to the fold of the turn it names."""
        params = message.get("params") or {}
        if params.get("threadId") not in {None, self.thread_id}:
            return
        method = message.get("method")
        if method == "turn/started":
            turn_id = params["turn"]["id"]
        elif method == "turn/completed":
            turn_id = params["turn"]["id"]
            if self.running == turn_id:
                self.running = None
        else:
            turn_id = params.get("turnId") or self.running
        if turn_id is None:
            return
        # Live evidence must still own the subscription's epoch before it can
        # change running identity or reuse even an existing fold. Historical
        # completion instead settles the exact delivery without reopening it.
        if method != "turn/completed" and not self._observe_lifecycle(turn_id):
            return

        delivery_id = app_server_delivery_id(message)
        # An offered delivery can name a turn whose `turn/started` reached the task
        # before this subscription was open to see it.
        adopting = (
            delivery_id is not None
            and turn_id not in self.turns
            and delivery_record_state(self.thread_id, delivery_id)
            in {"offering", "abandoned"}
        )
        fold = self._fold(
            turn_id,
            delivery_id,
            follow=method == "turn/started" or adopting,
            ended=method == "turn/completed",
        )
        if fold is None:
            return
        if adopting or method == "turn/started":
            self.running = turn_id
        update = fold.absorb(message)
        if (terminal := fold.finished(message, update)) is not None:
            self.turns.pop(turn_id, None)
            fold.commit(terminal)
        self._refresh_lifecycle(turn_id)

    def _observe_lifecycle(
        self, turn_id: str, expected: dict | None | object = ...
    ) -> bool:
        """Adopt ordered live provider evidence only against this subscription's epoch."""
        observed = start_session_turn(
            self.thread_id, turn_id, self.lifecycle if expected is ... else expected
        )
        if observed is None:
            return False
        self.lifecycle = observed
        return True

    def _refresh_lifecycle(self, turn_id: str) -> None:
        """Follow our matching close, without adopting an unmatched newer prompt."""
        current = session_record(self.thread_id)
        if (
            current
            and self.lifecycle
            and current["turn"] == turn_id
            and current["generation"] == self.lifecycle["generation"]
        ):
            self.lifecycle = current

    def _fold(
        self,
        turn_id: str,
        delivery_id: str | None,
        *,
        follow: bool,
        ended: bool = False,
    ) -> TurnFold | None:
        """The fold of one turn, taking the turn up where `follow` says it runs.

        This is the one place the connection opens a turn and binds a delivery.
        An ended turn gets a fold to settle its immutable delivery or close the
        subscription's matching lifecycle identity. It is never reopened.
        """
        fold = self.turns.get(turn_id)
        if (
            fold is not None
            and follow
            and self.lifecycle is not None
            and fold.generation != self.lifecycle["generation"]
        ):
            # Freshly admitted metadata may follow the same provider task in a
            # new session lifetime. Retire the old live observer; its immutable
            # delivery can still recover through history without live authority.
            fold.disconnect()
            self.turns.pop(turn_id)
            fold = None
        if fold is None and follow:
            fold = TurnFold(self.thread_id, turn_id, lifecycle=self.lifecycle)
            if not fold.open():
                return None
            self.turns[turn_id] = fold
        elif (
            fold is None
            and ended
            and (
                delivery_id is not None
                or (self.lifecycle is not None and self.lifecycle["turn"] == turn_id)
            )
        ):
            fold = TurnFold(self.thread_id, turn_id, lifecycle=self.lifecycle)
        if fold is not None and delivery_id is not None and fold.delivery_id is None:
            accept_codex_delivery(self.thread_id, delivery_id, turn_id)
            fold.bind(
                delivery_id, delivery_stream_reply_target(self.thread_id, delivery_id)
            )
        return fold

    def _disconnect_turns(self) -> None:
        """Take every fold's reading down without breaking the recovery boundary."""
        self.connected.clear()
        failures = []
        for fold in list(self.turns.values()):
            try:
                fold.disconnect()
            except Exception as error:  # noqa: BLE001
                failures.append(error)
        if failures:
            print(
                f"Codex App Server stream cleanup failed: {failures[0]}",
                file=sys.stderr,
                flush=True,
            )

    def _run(self) -> None:
        failures = 0
        try:
            while not self.stop_event.is_set():
                try:
                    self._connect()
                    failures = 0
                # This is the connection thread's recovery boundary: nothing it reads may
                # take the process down, and a lost connection is retried.
                except Exception as error:  # noqa: BLE001
                    self._disconnect_turns()
                    if not self.started:
                        self.ready.put(error)
                        return
                    failures += 1
                    if failures == 1:
                        print(
                            f"Codex App Server stream retry: {error}",
                            file=sys.stderr,
                            flush=True,
                        )
                    self.stop_event.wait(retry_delay(failures))

        finally:
            if self.connected.is_set():
                self._disconnect_turns()
            # Submission and shutdown share a short lock; no command can enter
            # after stop and miss this receiver-owned drain.
            with self.submission_lock:
                while not self.commands.empty():
                    _, result = self.commands.get_nowait()
                    result.set_exception(
                        RuntimeError("Codex App Server client stopped")
                    )


def _turn_items_complete(turn: dict) -> bool:
    """The provider schema defaults an omitted itemsView to full."""
    return turn.get("itemsView", "full") == "full"


def _turn_delivery_id(turn: dict) -> str | None:
    """The Leaf delivery a snapshot turn carries, read off its items."""
    return app_server_delivery_id({"method": "turn/started", "params": {"turn": turn}})


def _log_record(event: str, **fields) -> None:
    """One structured line in the adapter's log."""
    print(json.dumps({"event": event, **fields}), file=sys.stderr, flush=True)


def adapter_log_path(session_id: str) -> Path:
    return session_state_path(session_id, "codex.log")


def adapter_start_lock_path(session_id: str) -> Path:
    return session_state_path(session_id, "start")


def capture_batch(session_id: str, reading) -> bool:
    """Persist one watcher batch in the session's collecting record."""
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        captured = append_batch(
            session_id,
            reading.page_dir,
            reading.transaction,
            reading.batch,
        )
    return captured is not None


def _page_acknowledged(batch: dict) -> bool:
    page_dir = Path(batch["page"])
    if not (page_dir / EVENTS_FILE).is_file():
        return True
    return read_cursor(page_dir) >= max(event["seq"] for event in batch["events"])


def _sync_receipts(path: Path, record: dict) -> None:
    """Persist page receipts before archiving completed delivery records."""
    if record["state"] == "abandoned":
        archive_record(path, record)
        return
    changed = False
    for batch in record["batches"]:
        if not batch["receipted"] and _page_acknowledged(batch):
            batch["receipted"] = True
            changed = True
    if changed:
        write_record(path, record)
    else:
        archive_record(path, record)


def _recover_receipt(session_id: str) -> bool:
    """Reconcile one accepted batch while its session still owns the page."""
    settled = codex.settle_answered_deliveries(session_id)
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        records = delivery_records(session_id)
        for path, record in records:
            _sync_receipts(path, record)
        pending = min(
            (
                (path, index, dict(batch), record.get("transport"), record["state"])
                for path, record in delivery_records(session_id)
                if record["state"] in {"accepted", "abandoned"}
                for index, batch in enumerate(record["batches"])
                if not batch["receipted"]
            ),
            key=lambda pending: (
                pending[2]["page"],
                min(event["seq"] for event in pending[2]["events"]),
            ),
            default=None,
        )
    if pending is None:
        return settled
    path, batch_index, batch, transport, state = pending
    if state == "abandoned":
        codex.finish_abandoned_batch(path, batch_index, batch)
    else:
        finish_codex_batch(path, batch_index, batch, transport)
    return True


def _offer_queued_delivery(
    codex_path: str,
    session_id: str,
    connection: "TaskConnection | None",
) -> bool:
    """Offer one collecting delivery through the selected Codex transport.

    The App Server connection owns the idle check, start, acceptance and fold.
    The watcher waits for the start command without holding shared locks, then
    continues watching pages while the connection reads the running turn.
    """
    if connection is not None and connection.working():
        # The task takes one turn at a time, and one is already running — this
        # process's delivery, or the user's own work in the terminal. Cached
        # activity may hold back, but only fresh provider status permits a start.
        # Saying so is not work done: the loop goes on watching pages meanwhile.
        return False
    observed_hook_turn = hook_turn(session_id)
    if connection is None and step_delivery_turn(session_id) is not None:
        # A trusted tool hook can offer this input before the running turn ends.
        # Stop/Interrupt closes that turn; unread pointers then take this queue.
        return False
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        if hook_turn(session_id) != observed_hook_turn:
            # A prompt, ending, or tool step changed while activity was read.
            # Retry before reserving a route against that newer observation.
            return False
        records = delivery_records(session_id)
        unoffered = next(
            (
                (path, record)
                for path, record in records
                if record["state"] in {"collecting", "offering"}
            ),
            None,
        )
        prepared = None
        if unoffered is not None:
            path, record = unoffered
            prepared = offer_delivery(
                path, record, "queue" if connection is None else "app-server"
            )
            if (record.get("transport") or {}).get("phase") != "starting":
                record["transport"] = {
                    "phase": "queue" if connection is None else "app-server",
                    "turn": None,
                }
            write_record(prepared.record_path, record)
    if prepared is None:
        return False
    target = stream_reply_target(prepared.payload)
    if (
        connection is None
        and (record.get("transport") or {}).get("phase") == "starting"
    ):
        raise AppServerDeliveryUncertain(
            "the observed App Server delivery is awaiting reconciliation"
        )
    if connection is not None:
        started = connection.start_delivery(prepared.payload)
        if started:
            name_untitled_threads(
                app_server_title(connection.endpoint, None),
                prepared.payload,
                session_id,
                _log_record,
            )
        return started
    if target is not None and delivery_reply_reserved(
        session_id, prepared.payload["id"], target
    ):
        raise AppServerDeliveryUncertain(
            "the observed App Server delivery is awaiting reconciliation"
        )
    queue_delivery(codex_path, session_id, prepared.prompt)
    accept_codex_delivery(session_id, prepared.payload["id"], None)
    return True


def run_adapter(
    codex_path: str,
    handshake: Handshake | None = None,
    app_server: str | None = None,
) -> int:
    """Own the session watch until every claimed page ends or transfers.

    A detached adapter announces its readiness through `handshake` once it holds
    its leases and its transport answers, and exits if `leaf codex start` left
    without committing that start."""
    harness = session_harness()
    if harness is None or harness.name != CodexHarness.name:
        raise RuntimeError("the Codex adapter needs a Codex task identity")
    lease = take_lease(adapter_lease_path(harness.session))
    if lease is None:
        raise RuntimeError("a Codex delivery adapter is already active")
    # The lease record names this adapter's transport, so a later `leaf codex start`
    # in the task reports the one it joins.
    lease.truncate(0)
    lease.write(json.dumps({"app_server": app_server}).encode())
    lease.flush()
    watch = Watch(harness)
    if not watch.acquire():
        release_lease(lease)
        raise RuntimeError(
            "another `leaf wait` is already active; stop it before starting delivery"
        )
    leases_released = False
    connection = None
    start_lock = adapter_start_lock_path(harness.session)

    def retire() -> None:
        """Let this adapter's leases go, and with them, once the task owns no page,
        the log this run wrote. Taken under the start lock, so no successor starts
        until it is done; a task that still owns a page keeps the log for the next
        adapter it starts. On the way out it retires every task's delivery records
        whose pages are gone (`retire_gone_task_records`)."""
        nonlocal leases_released
        if connection is not None:
            connection.stop()
        if not owned_pages(harness.session):
            adapter_log_path(harness.session).unlink(missing_ok=True)
        retire_gone_task_records()
        watch.release()
        release_lease(lease)
        leases_released = True

    try:
        if app_server is not None:
            connection = TaskConnection(app_server, harness.session)
            connection.start()
        else:
            check_queue_command(codex_path)
        if handshake is not None and not handshake.announce():
            return 1
        failures = 0
        while True:
            try:
                # Receipt recovery judges page ownership as retirement does, so
                # both wait out a starter's claim handoff under the start lock
                # (`session-lifetime.md`, "Carriers").
                with flocked(start_lock):
                    recovered = _recover_receipt(harness.session)
                    if not recovered and not owned_pages(harness.session):
                        retire()
                        return 0
                if not recovered:
                    recovered = _offer_queued_delivery(
                        codex_path,
                        harness.session,
                        connection,
                    )
            # Transport and page errors belong to this retry boundary; neither
            # may end the adapter and strand the pages it claims.
            except Exception as error:  # noqa: BLE001 - retried, never raised
                failures += 1
                if failures == 1:
                    print(
                        f"Codex delivery retry: {error}",
                        file=sys.stderr,
                        flush=True,
                    )
                time.sleep(retry_delay(failures))
                continue
            if recovered:
                failures = 0
                continue

            captured = False

            def capture(reading) -> None:
                """Persist the batch without claiming that a turn opened."""
                nonlocal captured
                captured = capture_batch(harness.session, reading)

            mark = watch.mark()
            reading = read_watch_pass(watch, None, deliver=capture)
            if captured:
                continue
            if reading.outcome is not None or not reading.live:
                with flocked(start_lock):
                    captured = False
                    reading = read_watch_pass(watch, None, deliver=capture)
                    if captured or (reading.outcome is None and reading.live):
                        continue
                    if not owned_pages(harness.session):
                        retire()
                        return reading.outcome or 0
                # The route belongs to the session's ownership, not its current
                # authored status. Idle pages deliver nothing; a later status
                # resumes this same route. Wait outside the startup lock.
                watch.await_news(mark, timeout=1)
                continue
            # A second a pass, as well as each time a page moves: the queued offer
            # and receipt recovery above answer to Codex, not to the page's files.
            watch.await_news(mark, timeout=1)
    finally:
        # Provider turns outlive the adapter. Disconnect every fold, preserving
        # its reserved reply and transcript recovery for the next owner.
        if connection is not None:
            connection.stop()
        if not leases_released:
            watch.release()
            release_lease(lease)


def cmd_codex_start(
    page_dir: Path,
    codex_path: str | None = None,
    app_server: str | None = None,
) -> dict:
    """Claim PAGE and start one detached delivery carrier for this task, or find
    the one already running; return which, with its task and transport."""
    with preparing_adapter(session_harness(), codex_path, app_server) as prepared:
        claim_page(page_dir)
        return prepared


@contextmanager
def preparing_adapter(
    harness: Harness | None,
    codex_path: str | None = None,
    app_server: str | None = None,
):
    """Retain a ready carrier for `harness`'s task until the caller commits page
    ownership.

    The same task start lock serializes carrier startup and no-page retirement.
    Holding it across the caller's publication lets delivery prepare before any
    claim exists, without a carrier retiring in that gap. A new carrier captures
    the launching harness's canonical session generation before subscribing to turns.
    """
    if harness is None or harness.name != CodexHarness.name:
        raise RuntimeError("`leaf codex start` must run inside a Codex task")
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    executable = str(Path(executable).absolute())
    session_id = harness.session
    app_server = app_server or os.environ.get(APP_SERVER_ENV)
    if app_server is not None:
        check_app_server_endpoint(app_server)
    launch_lock = adapter_start_lock_path(session_id)
    with flocked(launch_lock):
        record = _running_adapter(session_id)
        if record is not None:
            running = record["app_server"]
            if app_server is not None and app_server != running:
                raise RuntimeError(
                    f"Codex delivery is already active for task {session_id}"
                    + (f" through App Server {running}" if running else "")
                    + f", not through App Server {app_server}"
                )
            yield {"task": session_id, "app_server": running, "started": False}
            return
        # The connection captures its causal lifecycle before observing turns.
        # Establish it in the launching harness, independently of page ownership.
        ensure_session(session_id, harness.lifetime())
        with starting_detached(
            [
                "codex",
                "run",
                "--codex-path",
                executable,
                *(["--app-server", app_server] if app_server is not None else []),
            ],
            harness=harness,
            what="Codex delivery",
            log=adapter_log_path(session_id),
            cwd=state_home(),
            timeout=START_TIMEOUT,
        ):
            pass
        yield {"task": session_id, "app_server": app_server, "started": True}


def _running_adapter(session_id: str) -> dict | None:
    """The live adapter's lease record, naming its transport, or None when no
    adapter holds the lease. An adapter can let go between the question and the
    read, since only its retirement takes the start lock, and its record goes with
    it; that reads as no adapter."""
    if not adapter_is_live(session_id):
        return None
    try:
        return json.loads(adapter_lease_path(session_id).read_text())
    except FileNotFoundError:
        return None


def _wait_for_app_server(path: Path, process: subprocess.Popen, log) -> None:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            log.seek(0)
            detail = log.read().decode(errors="replace").strip()
            raise RuntimeError(detail or "Codex App Server exited before it was ready")
        time.sleep(0.05)
    raise RuntimeError("Codex App Server did not become ready")


@contextmanager
def private_app_server(
    executable: str, *, env: dict[str, str] | None = None
) -> Iterator[str]:
    """Run one App Server on a Unix socket only this user can reach, and yield its
    endpoint until the block ends and the server stops.

    The server's environment names that endpoint as `LEAF_CODEX_APP_SERVER`, so a
    task it runs hands its pages to this server when it serves them.
    An eval may supply an isolated child environment without mutating this process.
    """
    with tempfile.TemporaryDirectory(prefix="leaf-codex-", dir="/tmp") as directory:
        path = Path(directory) / "app-server.sock"
        endpoint = f"unix://{path}"
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [executable, "app-server", "--listen", endpoint],
                env=(os.environ if env is None else env) | {APP_SERVER_ENV: endpoint},
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                _wait_for_app_server(path, server, log)
                yield endpoint
            finally:
                stop_app_server(server)


def cmd_codex_launch(codex_path: str | None = None) -> int:
    """Run one private App Server and its Codex terminal client."""
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    with private_app_server(executable) as endpoint:
        return subprocess.call(
            [executable, "--remote", endpoint],
            env=os.environ | {APP_SERVER_ENV: endpoint},
        )
