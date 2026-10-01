"""The detached process that carries Leaf delivery into later turns of one Codex task.

`leaf codex start` claims a page and leaves this process running behind the turn that
started it, so a user's later moves reach the same Codex task instead of waiting for
the agent to ask again. It owns the session watch: it captures each batch into the
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
reply included. Over App Server, `start_delivery_turn` opens a turn on a connection of
its own as soon as the task is idle and `DeliveryTurn` follows it there until it ends,
which is also how the user sees activity and a streamed answer, and why the turn's
opening and final messages are its reply. The private App Server this transport needs is what
`leaf codex launch` runs.

`TaskObserver` holds the other connection, on the turns Leaf did not start: the
user's own work in the terminal, and a queued pointer the task picks up by itself.
It folds each of those turns the way `DeliveryTurn` folds its own; the two differ
only in the connection they read.

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
from contextlib import contextmanager
from pathlib import Path

# The stream-activity writers are called as `codex.<name>`, so `leaf.codex` holds their
# one binding: whatever takes a turn's readings there takes every carrier's too.
from . import codex
from .codex import (
    START_TIMEOUT,
    AppServerDeliveryUncertain,
    CarriedTurn,
    TurnFold,
    accept_codex_delivery,
    app_server_connect,
    app_server_delivery_id,
    app_server_handshake,
    app_server_request,
    append_batch,
    archive_record,
    check_app_server_endpoint,
    delivery_lock_path,
    delivery_record_state,
    delivery_records,
    delivery_stream_reply_target,
    finish_codex_batch,
    hook_turn,
    offer_delivery,
    retire_gone_task_records,
    retry_delay,
    start_app_server_delivery,
    step_delivery_turn,
    stop_app_server,
    stream_reply_target,
    write_record,
)
from .detached import Handshake, start_detached
from .event_log import flocked, read_cursor
from .host import CodexHarness, session_harness
from .leases import (
    adapter_is_live,
    adapter_lease_path,
    release_lease,
    session_state_path,
    take_lease,
)
from .machine import state_home
from .schema import EVENTS_FILE
from .service import (
    owned_pages,
    starting_claim,
)
from .session import Watch, read_watch_pass
from .thread import (
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


class TaskObserver:
    """Watch one Codex task: the turns Leaf did not start, and what they are doing.

    This connection resumes the task and keeps the subscription that resume opens,
    so it sees the user's own turns in the terminal and a queued pointer the task
    picks up by itself. Each such turn gets a `TurnFold`, the same fold a carried
    turn is, and each notification goes to the fold of the turn it names. A fold
    binds a reply only for an App Server delivery whose follower is gone, because
    no follower of Leaf's ever will write it. A queued pointer's reply is not the
    turn's to write: that delivery names a plain reply for `leaf thread reply`, so its
    turn is watched and opened on its pages but binds nothing.

    What is this carrier's own is the subscription. One connection outlives the
    turns it reports, so losing it does not end them: every fold is disconnected,
    and the next resume reconciles each against the task's snapshot — taken up
    again if still running, committed if it ended meanwhile.

    Two connections may resume one thread and both then receive everything it says,
    so every notification about a turn a `DeliveryTurn` is carrying arrives here too.
    Folding it here as well would give that turn two owners and its answer two
    writers, so a delivery this process is carrying is held in `carried` from
    before its `turn/start` is sent, and its turn gets no fold here.
    """

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.turns: dict[str, TurnFold] = {}
        self.running: str | None = None
        self.stop_event = threading.Event()
        self.socket = None
        self.started = False
        self.lock = threading.Lock()
        self.carried: set[str] = set()
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
        self.stop_event.set()
        if self.socket is not None:
            self.socket.close()
        self.thread.join(timeout=3)
        self._disconnect_turns()

    def carry(self, delivery_id: str) -> None:
        """Take one delivery as this process's own, before its turn exists.

        Held from before `turn/start` is sent, because the turn's own `turn/started`
        can reach this connection before the response naming it reaches the starter.
        """
        with self.lock:
            self.carried.add(delivery_id)

    def release(self, delivery_id: str) -> None:
        """Give one delivery back, once no follower of this process holds it."""
        with self.lock:
            self.carried.discard(delivery_id)

    def busy(self) -> bool:
        """Whether this process is carrying a delivery right now."""
        with self.lock:
            return bool(self.carried)

    def stopped(self) -> bool:
        """Whether the adapter is going, which is not its turns ending."""
        return self.stop_event.is_set()

    def working(self) -> bool:
        """Whether the last notification read left a turn of the task's running.

        This comes off the standing subscription, so the delivery loop can hold back
        without opening a connection every second to ask. It can lag, which is why
        it only ever holds a delivery back: the status that lets one start is read
        on the starting connection itself, one request before the start.
        """
        return self.running is not None

    def _is_carried(self, delivery_id: str | None) -> bool:
        with self.lock:
            return delivery_id in self.carried

    def _send(self, socket, method: str, request_id: int, params: dict) -> dict:
        """Request on this observer's connection, folding what it does not hold."""
        return app_server_request(
            socket,
            method,
            request_id,
            params,
            self._read,
            stopped=self.stop_event.is_set,
        )

    def _connect(self) -> None:
        with app_server_connect(self.endpoint) as socket:
            self.socket = socket
            app_server_handshake(socket, 0, "leaf", "Leaf", self._read)
            result = self._send(
                socket,
                "thread/resume",
                1,
                {"threadId": self.thread_id, "excludeTurns": False},
            )
            self._resume(result.get("thread", {}))
            if not self.started:
                self.started = True
                self.ready.put(None)
            while not self.stop_event.is_set():
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _resume(self, thread: dict) -> None:
        """Reconcile every turn against a resumed snapshot of the task."""
        # A followed turn the snapshot does not list — a paginated thread's `turns`
        # can leave it out — stays disconnected until it says something.
        turns = thread.get("turns", [])
        for turn in turns:
            self._reconcile(turn)

        # Only a turn this can name. A resume that reports the task active without
        # naming its turn leaves nothing a `turn/completed` could ever clear.
        self.running = next(
            (
                turn["id"]
                for turn in reversed(turns)
                if turn.get("status") == "inProgress"
            ),
            None,
        )
        status = thread.get("status", {})
        fold = self.turns.get(self.running) if self.running is not None else None
        if status.get("type") == "active" and self.running is not None:
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
        else:
            # A previous observer may have died without its disconnect cleanup.
            # This snapshot does not establish a current provider turn, so an
            # old thinking, tool, waiting, or replying observation cannot prove
            # one is still live.
            codex.clear_stream_activity(self.thread_id)

    def _reconcile(self, turn: dict) -> None:
        """Bring one snapshot turn's fold up to what the snapshot says of it.

        A running turn is followed, whether or not it was before the connection
        dropped. An ended one is committed if something here was following it, or
        if it carries a delivery: its item was written while this connection was
        down, or its carrier process died while the turn ran on, and its answer
        is still to write. Its turn is closed, never reopened. The snapshot's other
        turns are history.
        """
        running = turn.get("status") == "inProgress"
        fold = self._fold(
            turn["id"], _turn_delivery_id(turn), follow=running, ended=not running
        )
        if fold is None:
            return
        if running:
            fold.restore(turn)
        else:
            self.turns.pop(turn["id"], None)
            fold.commit(turn)

    def _read(self, message: dict) -> None:
        """Route one notification to the fold of the turn it names."""
        params = message.get("params") or {}
        if params.get("threadId") not in {None, self.thread_id}:
            return
        method = message.get("method")
        if method == "turn/started":
            turn_id = params["turn"]["id"]
            self.running = turn_id
        elif method == "turn/completed":
            turn_id = params["turn"]["id"]
            if self.running == turn_id:
                self.running = None
        else:
            turn_id = params.get("turnId") or self.running
        if turn_id is None:
            return

        delivery_id = app_server_delivery_id(message)
        # An offered delivery can name a turn whose `turn/started` reached the task
        # before this subscription was open to see it.
        adopting = (
            delivery_id is not None
            and turn_id not in self.turns
            and delivery_record_state(self.thread_id, delivery_id) == "offering"
        )
        fold = self._fold(
            turn_id, delivery_id, follow=method == "turn/started" or adopting
        )
        if fold is None:
            return
        if adopting:
            self.running = turn_id
        update = fold.absorb(message)
        if (terminal := fold.finished(message, update)) is not None:
            del self.turns[turn_id]
            fold.commit(terminal)

    def _fold(
        self,
        turn_id: str,
        delivery_id: str | None,
        *,
        follow: bool,
        ended: bool = False,
    ) -> TurnFold | None:
        """The fold of one turn, taking the turn up where `follow` says it runs.

        This is the one place the observer opens a turn and binds a delivery to
        it. A turn carrying a delivery this process's own follower carries is
        that follower's, so it gets no fold here and any fold it had is dropped.
        An `ended` turn nothing here followed gets a fold only to commit a
        delivery it carries, and is never opened for it.
        """
        if delivery_id is not None and self._is_carried(delivery_id):
            # Its follower answers for this turn, so nothing here writes it twice.
            self.turns.pop(turn_id, None)
            return None
        fold = self.turns.get(turn_id)
        if fold is None and follow:
            fold = self.turns[turn_id] = TurnFold(self.thread_id, turn_id)
            fold.open()
        elif fold is None and ended and delivery_id is not None:
            fold = TurnFold(self.thread_id, turn_id)
        if fold is not None and delivery_id is not None and fold.delivery_id is None:
            accept_codex_delivery(self.thread_id, delivery_id, turn_id)
            fold.bind(
                delivery_id, delivery_stream_reply_target(self.thread_id, delivery_id)
            )
        return fold

    def _disconnect_turns(self) -> None:
        """Take every fold's reading down without breaking the recovery boundary."""
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
        while not self.stop_event.is_set():
            try:
                self._connect()
                failures = 0
            # This is the observer thread's recovery boundary: nothing it reads may
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


def _turn_delivery_id(turn: dict) -> str | None:
    """The Leaf delivery a snapshot turn carries, read off its items."""
    return app_server_delivery_id({"method": "turn/started", "params": {"turn": turn}})


def _log_record(event: str, **fields) -> None:
    """One structured line in the adapter's log."""
    print(json.dumps({"event": event, **fields}), file=sys.stderr, flush=True)


def start_delivery_turn(
    observer: "TaskObserver",
    session_id: str,
    payload: dict,
) -> "DeliveryTurn | None":
    """Open one Leaf turn on a connection of its own, or report the task busy.

    The connection belongs to the turn for the turn's whole life. `thread/resume`
    subscribes it and `turn/start` neither subscribes nor unsubscribes, so
    everything the turn says arrives here, and losing the connection is that turn
    ending rather than a gap to read across.

    The task has to be idle. `turn/start` against a running turn steers the delivery
    into it instead — App Server says so of `turnTrigger`, "Ignored when this request
    steers an already-active turn" — and a user's comment does not belong in a turn
    the user started, whose one final answer is an answer to something else. The
    status read here is this connection's own, one request before the start, rather
    than a fold left over from notifications another connection happened to see.
    """
    socket = app_server_connect(observer.endpoint)
    try:
        buffered: list[dict] = []
        app_server_handshake(socket, 0, "leaf", "Leaf", buffered.append)
        resumed = app_server_request(
            socket,
            "thread/resume",
            1,
            {"threadId": session_id, "excludeTurns": True},
            buffered.append,
        )
        status = (resumed.get("thread") or {}).get("status") or {}
        if status.get("type") == "active":
            socket.close()
            return None
        if status.get("type") != "idle":
            # `notLoaded` and `systemError` are not states a task comes out of by
            # being left alone, so waiting for one to pass is waiting forever with
            # the user's move held and nothing saying why. Raising puts it in the
            # adapter's log and on the delivery loop's retry ladder.
            raise RuntimeError(
                f"the Codex task is not taking turns: {status.get('type', 'unknown')}"
            )
        turn_id = start_app_server_delivery(
            lambda method, params: app_server_request(
                socket, method, 2, params, buffered.append
            ),
            session_id,
            payload,
        )
    except BaseException:
        # An uncertain start keeps its seat reserved, and the observer adopts the
        # turn the moment it says anything; every other failure has given it back.
        socket.close()
        raise
    # On the task's configured model: a user's App Server offers no model this
    # process could name for every account.
    name_untitled_threads(
        app_server_title(observer.endpoint, None), payload, session_id, _log_record
    )
    return DeliveryTurn(
        observer,
        session_id,
        socket,
        turn_id,
        payload["id"],
        stream_reply_target(payload),
        buffered,
    )


class DeliveryTurn(CarriedTurn):
    """One delivery's turn in the task this adapter watches.

    Leaf's names for the turn are the turn opened on every page the task claims and
    the seat its final answer commits into, and its ending is the fold's. The
    observer holds the delivery as carried for as long as this runs, so the
    connection watching the task gives this turn no fold of its own and writes
    nothing it says a second time.
    """

    def __init__(
        self,
        observer: "TaskObserver",
        session_id: str,
        socket,
        turn_id: str,
        delivery_id: str,
        reply_target: dict | None,
        buffered=(),
    ):
        super().__init__(
            session_id, socket, turn_id, delivery_id, reply_target, buffered
        )
        self.observer = observer

    def begin(self) -> None:
        """Record the delivery against this turn, and bind the answer it will give."""
        self.open()
        accept_codex_delivery(self.session_id, self.delivery_id, self.turn_id)
        self.open_reply()
        codex.set_stream_activity(self.session_id, self.turn_id, {"kind": "working"})

    def ended(self, error: BaseException) -> dict | None:
        """Account for the turn the stream stopped carrying, unless it is not over.

        A fault here is not the turn stopping. The provider turn goes on running in
        a terminal the user is sitting at, where it is theirs to watch and interrupt,
        so unlike the website's carrier this one never interrupts what it can no
        longer read — it only stops claiming to speak for it. An adapter shutting
        down is the case where that is all there is to do: the turn outlives this
        process, and a later carrier reads its answer back off the transcript.
        """
        if self.observer.stopped():
            self.disconnect()
            return None
        print(f"Codex delivery turn ended: {error}", file=sys.stderr, flush=True)
        return super().ended(error)


def _carry_delivery_turn(turn: DeliveryTurn) -> None:
    """Follow one delivery turn, and hand the observer its turn back at the end.

    This is the top of a follower thread. Anything not caught here is a traceback in
    the adapter's log and a delivery the observer goes on holding as carried, which
    is a task that never offers another.
    """
    try:
        turn.follow()
    except Exception as error:  # noqa: BLE001 - reported, never raised
        print(f"Codex delivery turn failed: {error}", file=sys.stderr, flush=True)
    finally:
        turn.observer.release(turn.delivery_id)


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
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        records = delivery_records(session_id)
        for path, record in records:
            _sync_receipts(path, record)
        pending = min(
            (
                (path, index, dict(batch), record.get("transport"))
                for path, record in delivery_records(session_id)
                if record["state"] == "accepted"
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
        return False
    path, batch_index, batch, transport = pending
    finish_codex_batch(path, batch_index, batch, transport)
    return True


def _offer_queued_delivery(
    codex_path: str,
    session_id: str,
    observer: "TaskObserver | None",
    follow,
) -> bool:
    """Offer one collecting delivery through the selected Codex transport.

    Over App Server the offer is a turn this process starts and then follows, so
    what this returns says only that the delivery left its record. Its acceptance,
    its reply and its receipt are the follower's, and they are written where every
    other carrier writes them.
    """
    if observer is not None and (observer.busy() or observer.working()):
        # The task takes one turn at a time, and one is already running — this
        # process's delivery, or the user's own work in the terminal. Both readings
        # come off what the observer already holds, so holding back costs nothing;
        # opening a connection a second to ask the task instead is what this avoids.
        # Saying so is not work done: the loop goes on watching pages meanwhile.
        return False
    observed_hook_turn = hook_turn(session_id)
    if observer is None and step_delivery_turn(session_id) is not None:
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
                path, record, "queue" if observer is None else "app-server"
            )
            record["transport"] = {
                "phase": "queue" if observer is None else "app-server",
                "turn": None,
            }
            write_record(prepared.record_path, record)
    if prepared is None:
        return False
    target = stream_reply_target(prepared.payload)
    if observer is not None:
        delivery_id = prepared.payload["id"]
        observer.carry(delivery_id)
        try:
            turn = start_delivery_turn(observer, session_id, prepared.payload)
        except BaseException:
            observer.release(delivery_id)
            raise
        if turn is None:
            # The task is busy with a turn of its own. The record stays offering and
            # the same frozen delivery is offered again once the task is idle.
            observer.release(delivery_id)
            return False
        follow(turn)
        return True
    if target is not None and delivery_reply_reserved(
        session_id, prepared.payload["id"], target
    ):
        raise AppServerDeliveryUncertain(
            "the observed App Server delivery is awaiting reconciliation"
        )
    queue_delivery(codex_path, session_id, prepared.prompt)
    accept_codex_delivery(session_id, prepared.payload["id"], None)
    return True


def _has_delivery_work(session_id: str) -> bool:
    with flocked(delivery_lock_path(session_id)):
        return any(
            record["state"] != "accepted"
            or any(not batch["receipted"] for batch in record["batches"])
            for _, record in delivery_records(session_id)
        )


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
    observer = None
    followers: list[tuple[threading.Thread, DeliveryTurn]] = []
    start_lock = adapter_start_lock_path(harness.session)

    def follow(turn: DeliveryTurn) -> None:
        """Follow one started turn on its own thread, off the delivery loop.

        The loop has to keep watching pages while the turn runs, which can be
        minutes, so the turn is followed beside it rather than in it. Only one
        follower runs at a time: the task takes one turn at a time, and until this
        one ends the observer reports the delivery as carried and no second offer
        is made.
        """
        followers[:] = [running for running in followers if running[0].is_alive()]
        follower = threading.Thread(
            target=_carry_delivery_turn,
            args=(turn,),
            name="leaf-codex-delivery-turn",
            daemon=True,
        )
        followers.append((follower, turn))
        follower.start()

    def retire() -> None:
        """Let this adapter's leases go, and with them, once the task owns no page,
        the log this run wrote. Taken under the start lock, so no successor starts
        until it is done; a task that still owns a page keeps the log for the next
        adapter it starts. On the way out it retires every task's delivery records
        whose pages are gone (`retire_gone_task_records`)."""
        nonlocal leases_released
        if not owned_pages(harness.session):
            adapter_log_path(harness.session).unlink(missing_ok=True)
        retire_gone_task_records()
        watch.release()
        release_lease(lease)
        leases_released = True

    try:
        if app_server is not None:
            observer = TaskObserver(app_server, harness.session)
            observer.start()
        else:
            check_queue_command(codex_path)
        if handshake is not None and not handshake.announce():
            return 1
        failures = 0
        while True:
            try:
                recovered = _recover_receipt(harness.session)
                if not recovered:
                    with flocked(start_lock):
                        if not owned_pages(harness.session):
                            retire()
                            return 0
                    recovered = _offer_queued_delivery(
                        codex_path,
                        harness.session,
                        observer,
                        follow,
                    )
            # Every class. A delivery opens a connection of its own in here now, and
            # `websockets` raises `WebSocketException`, which descends from
            # `Exception` alone; naming the classes to retry would let a refused
            # handshake end the adapter and strand every page it claims.
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
                    if owned_pages(harness.session) and _has_delivery_work(
                        harness.session
                    ):
                        time.sleep(1)
                        continue
                    retire()
                    return reading.outcome or 0
            # A second a pass, as well as each time a page moves: the queued offer
            # and receipt recovery above answer to Codex, not to the page's files.
            watch.await_news(mark, timeout=1)
    finally:
        # A turn goes on running in the task whatever happens here, so the follower
        # is told the adapter is going and its connection is closed under it. It
        # then leaves what the turn has said on the page instead of committing an
        # ending it did not see. Stopping the observer is what tells it: every
        # follower reads the adapter's going off the observer whose delivery it
        # carries, and there are no followers without one.
        if observer is not None:
            observer.stop()
        for follower, turn in followers:
            turn.socket.close()
            follower.join(timeout=3)
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
    harness = session_harness()
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
    with starting_claim(page_dir), flocked(launch_lock):
        record = _running_adapter(session_id)
        if record is not None:
            running = record["app_server"]
            if app_server is not None and app_server != running:
                raise RuntimeError(
                    f"Codex delivery is already active for task {session_id}"
                    + (f" through App Server {running}" if running else "")
                    + f", not through App Server {app_server}"
                )
            return {"task": session_id, "app_server": running, "started": False}
        start_detached(
            [
                "codex",
                "run",
                "--codex-path",
                executable,
                *(["--app-server", app_server] if app_server is not None else []),
            ],
            what="Codex delivery",
            log=adapter_log_path(session_id),
            cwd=state_home(),
            timeout=START_TIMEOUT,
        )
    return {"task": session_id, "app_server": app_server, "started": True}


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
def private_app_server(executable: str) -> Iterator[str]:
    """Run one App Server on a Unix socket only this user can reach, and yield its
    endpoint until the block ends and the server stops.

    The server's environment names that endpoint as `LEAF_CODEX_APP_SERVER`, so a
    task it runs hands its pages to this server when it runs `leaf codex start`."""
    with tempfile.TemporaryDirectory(prefix="leaf-codex-", dir="/tmp") as directory:
        path = Path(directory) / "app-server.sock"
        endpoint = f"unix://{path}"
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [executable, "app-server", "--listen", endpoint],
                env=os.environ | {APP_SERVER_ENV: endpoint},
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
