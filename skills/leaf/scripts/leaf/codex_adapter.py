"""The detached process that carries Leaf delivery into later turns of one Codex task.

`leaf codex start` claims a page and leaves this process running behind the turn that
started it, so a reader's later moves reach the same Codex task instead of waiting for
the agent to ask again. It owns the session watch: it captures each batch into the
task's delivery record, offers one delivery at a time, and reconciles the receipt its
page is owed however that delivery was taken.

One of two transports carries an offer. The `codex queue` command is the default,
and the only one open to a task whose App Server Leaf cannot reach, such as the Codex
desktop app's. It leaves a pointer for the task's next turn; the task reads that
immutable input through `leaf delivery read` and answers with explicit commands, the
reply included. Over App Server, `start_delivery_turn` opens a turn on a connection of
its own as soon as the task is idle and `DeliveryTurn` follows it there until it ends,
which is also how the reader sees activity and a streamed answer, and why the turn's
final message is its reply. The private App Server this transport needs is what
`leaf codex launch` runs.

`TaskObserver` holds the other connection, on the turns Leaf did not start: the
user's own work in the terminal, and a queued pointer the task picks up by itself.

`codex.py` owns the protocol, the turn every carrier follows to its reply, the
delivery records, and the page writers both transports share. What is here is the
process around them.
"""

import json
import os
import queue
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .codex import (
    START_TIMEOUT,
    AppServerEvents,
    AppServerReplyStream,
    AppServerRequestRejected,
    CarriedTurn,
    accept_codex_delivery,
    app_server_connect,
    app_server_delivery_id,
    app_server_handshake,
    app_server_request,
    app_server_turn_start_params,
    append_batch,
    archive_queue,
    check_app_server_endpoint,
    clear_stream_activity,
    close_stream_turn,
    delivery_lock_path,
    delivery_queue_state,
    delivery_stream_reply_target,
    offer_delivery,
    open_stream_turn,
    project_app_server_activity,
    queue_path,
    queue_records,
    retry_delay,
    session_state_path,
    set_stream_activity,
    stop_app_server,
    stream_reply_target,
    write_queue,
)
from .conversation import (
    delivery_reply_reserved,
    release_delivery_reply,
    reserve_delivery_reply,
)
from .delivery import ReceiptRefused, receive_batch, record_pickup
from .event_log import flocked, read_cursor
from .files import read_json
from .host import CodexHarness, session_harness
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .machine import state_home
from .schema import EVENTS_FILE
from .service import (
    PageTransaction,
    owned_pages,
    restore_page_claim,
    take_page_claim,
)
from .session import Watch, read_watch_pass

QUEUE_TIMEOUT = 20
APP_SERVER_ENV = "LEAF_CODEX_APP_SERVER"


class AppServerDeliveryUncertain(RuntimeError):
    """A delivery may have started, but its acknowledgement was lost."""


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
    # TODO(2026-09-12): Route active-turn delivery through `turn/steer` once
    # Codex exposes the desktop task's App Server endpoint or an equivalent CLI command.
    arguments = ["queue"]
    arguments.extend(["--thread", thread_id, "--message", prompt])
    _run_codex(codex_path, *arguments)


class TaskObserver:
    """Watch one Codex task: the turns Leaf did not start, and what they are doing.

    This connection resumes the task and keeps the subscription that resume opens,
    so it sees the user's own turns in the terminal and a queued pointer the task
    picks up by itself. It projects their activity onto every page the task claims,
    and binds a pointer turn's reply, because no follower of Leaf's ever will.

    Two connections may resume one thread and both then receive everything it says,
    so every notification about a turn a `DeliveryTurn` is carrying arrives here too.
    Adopting one would give that turn two owners and its answer two writers, so a
    delivery this process is carrying is held in `carried` from before its
    `turn/start` is sent, and passed over here until its follower is done.
    """

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.events = AppServerEvents(thread_id)
        self.stop_event = threading.Event()
        self.socket = None
        self.last_activity_update = 0.0
        self.started = False
        self.lock = threading.Lock()
        self.carried: set[str] = set()
        self.bindings: dict[str, AppServerReplyStream] = {}
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
        self._disconnect_streams()

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
        without opening a connection every second to ask. It is a fold and it can
        lag, which is why it only ever holds a delivery back: the status that lets
        one start is read on the starting connection itself, one request before the
        start.
        """
        return self.events.turn_id is not None

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
            resumed = result.get("thread", {})
            self._restore_bindings(resumed)
            active = next(
                (
                    turn["id"]
                    for turn in reversed(resumed.get("turns", []))
                    if turn.get("status") == "inProgress"
                ),
                None,
            )
            if resumed.get("status", {}).get("type") == "active" and active is not None:
                # Only a turn this can name. A resume that reports the task active
                # without naming its turn — a paginated thread whose `turns` the
                # response left out — used to record the word "active" as the turn
                # id, which no `turn/completed` matches, so both the reading below
                # and the fold `working` reads stood until the next reconnect.
                self.events.turn_id = active
                restored = self.events.read(
                    {
                        "method": "thread/status/changed",
                        "params": {
                            "threadId": self.thread_id,
                            "turnId": active,
                            "status": resumed["status"],
                        },
                    }
                )
                set_stream_activity(self.thread_id, active, restored["activity"])
            else:
                # A previous observer may have died without its disconnect cleanup.
                # This snapshot does not establish a current provider turn, so an
                # old thinking, tool, waiting, or replying observation cannot prove
                # one is still live.
                clear_stream_activity(self.thread_id)
            if not self.started:
                self.started = True
                self.ready.put(None)
            while not self.stop_event.is_set():
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _bind(self, turn_id: str, delivery_id: str, target: dict) -> None:
        self.bindings[turn_id] = AppServerReplyStream(
            self.thread_id,
            turn_id,
            delivery_id,
            target,
        )

    def _restore_bindings(self, thread: dict) -> None:
        turns = {turn["id"]: turn for turn in thread.get("turns", [])}
        active_turn = next(
            (
                turn
                for turn in reversed(list(turns.values()))
                if turn.get("status") == "inProgress"
            ),
            None,
        )
        self.events = AppServerEvents(self.thread_id)
        if active_turn is not None:
            self.events.restore_turn(active_turn)
        known_turns = set(self.bindings)
        for turn_id, stream in list(self.bindings.items()):
            turn = turns.get(turn_id)
            if turn is None:
                stream.disconnect()
                continue
            if turn.get("status") == "inProgress":
                stream.restore(self.events.final_text(turn))
            else:
                if self.events.turn_id == turn_id:
                    self.events.turn_id = None
                self._end_turn(
                    turn_id,
                    turn.get("status", "failed"),
                    self.events.final_text(turn),
                )
        for turn in turns.values():
            if turn["id"] not in known_turns:
                self._restore_delivery_binding(turn)

    def _restore_delivery_binding(self, turn: dict) -> None:
        """Recover a provider turn from the immutable delivery it carries.

        A turn reached this way is one nobody is following: a pointer the task
        picked up by itself, or a delivery whose carrier process died while its turn
        ran on. A live follower's turn is excluded by `carried`, which is held from
        before the turn exists.
        """
        turn_id = turn["id"]
        if turn_id in self.bindings:
            return
        delivery_id = app_server_delivery_id(
            {"method": "turn/started", "params": {"turn": turn}}
        )
        if delivery_id is None or self._is_carried(delivery_id):
            return
        path = queue_path(self.thread_id, delivery_id)
        with flocked(delivery_lock_path(self.thread_id)):
            queue_record = read_json(path)
        accept_offered_delivery(self.thread_id, delivery_id, turn_id, queue_record)
        target = delivery_stream_reply_target(self.thread_id, delivery_id)
        if target is None:
            return
        status = turn.get("status", "failed")
        if status == "inProgress":
            open_stream_turn(self.thread_id, turn_id)
            self._bind(turn_id, delivery_id, target)
            self.bindings[turn_id].restore(self.events.final_text(turn))
            return
        self._bind(turn_id, delivery_id, target)
        self._end_turn(turn_id, status, self.events.final_text(turn))

    def _is_carried(self, delivery_id: str) -> bool:
        with self.lock:
            return delivery_id in self.carried

    def _read(self, message: dict) -> None:
        """Fold one notification about a turn this task is running."""
        delivery_id = app_server_delivery_id(message)
        if (
            self.events.turn_id is None
            and delivery_id is not None
            and delivery_queue_state(self.thread_id, delivery_id) == "offering"
        ):
            # The immutable offered delivery explicitly binds this provider turn.
            # An ordinary late item cannot reopen an ended turn, but the observer
            # must be able to adopt a delivery whose `turn/started` notification
            # another connection consumed before this subscription saw it.
            self.events.turn_id = (message.get("params") or {}).get("turnId")
        update = self.events.read(message)
        if update is None:
            return
        turn_id = update["turn"]
        if message.get("method") == "turn/started":
            open_stream_turn(self.thread_id, turn_id)
        if (
            delivery_id is not None
            and turn_id not in self.bindings
            and not self._is_carried(delivery_id)
        ):
            accept_offered_delivery(self.thread_id, delivery_id, turn_id)
            target = delivery_stream_reply_target(self.thread_id, delivery_id)
            if target is not None:
                self._bind(turn_id, delivery_id, target)
        self.last_activity_update = project_app_server_activity(
            self.events,
            message,
            update,
            self.last_activity_update,
        )
        if stream := self.bindings.get(turn_id):
            stream.update(update)
        if completed := update.get("completed"):
            self._end_turn(turn_id, completed, update.get("text", ""))

    def _end_turn(self, turn_id: str, state: str, text: str) -> None:
        """Commit an ended turn's bound answer, then close the turn on every page.

        The close runs whatever the answer did, for the reason `CarriedTurn` gives:
        until it does, every page the task claims tells its reader the agent is
        still working.
        """
        stream = self.bindings.pop(turn_id, None)
        error = None
        try:
            if stream is not None:
                error = stream.finish(state, text)
        finally:
            close_stream_turn(self.thread_id, turn_id)
        if error is not None:
            print(f"Codex final reply rejected: {error}", file=sys.stderr, flush=True)

    def _disconnect_streams(self) -> None:
        """Disconnect projections without breaking the observer recovery boundary."""
        failures = []
        try:
            clear_stream_activity(self.thread_id)
        except Exception as error:  # noqa: BLE001
            failures.append(error)
        for stream in list(self.bindings.values()):
            try:
                stream.disconnect()
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
                self._disconnect_streams()
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


def accept_offered_delivery(
    session_id: str,
    delivery_id: str,
    turn_id: str,
    queue_record: dict | None = None,
) -> None:
    """Accept the offered delivery against the provider turn known to carry it."""
    if queue_record is None:
        path = queue_path(session_id, delivery_id)
        with flocked(delivery_lock_path(session_id)):
            queue_record = read_json(path)
    if queue_record is not None and queue_record["state"] == "offering":
        accept_codex_delivery(session_id, turn=turn_id)


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
    steers an already-active turn" — and a reader's comment does not belong in a turn
    the user started, whose one final answer is an answer to something else. The
    status read here is this connection's own, one request before the start, rather
    than a fold left over from notifications another connection happened to see.
    """
    socket = app_server_connect(observer.endpoint)
    reply_target = None
    seat_is_free = True
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
            # the reader's move held and nothing saying why. Raising puts it in the
            # adapter's log and on the delivery loop's retry ladder.
            raise RuntimeError(
                f"the Codex task is not taking turns: {status.get('type', 'unknown')}"
            )
        reply_target = stream_reply_target(payload)
        if reply_target is not None:
            reserve_delivery_reply(session_id, payload["id"], reply_target)
        try:
            started = app_server_request(
                socket,
                "turn/start",
                2,
                app_server_turn_start_params(session_id, payload),
                buffered.append,
            )
        except AppServerRequestRejected:
            # A definitive refusal before the provider executed anything, so no turn
            # exists and the seat goes back with the rest.
            raise
        except BaseException as error:
            # The request went out and no answer came back, so a turn carrying this
            # delivery may be running. The seat stays reserved: until something sees
            # that turn, no other writer may answer for the delivery, and the
            # observer adopts the turn the moment it says anything.
            seat_is_free = False
            raise AppServerDeliveryUncertain(
                f"the Codex App Server turn was not acknowledged: {error}"
            ) from error
        turn_id = (started.get("turn") or {}).get("id")
        if not turn_id:
            raise RuntimeError("Codex App Server returned no turn id")
    except BaseException:
        # Nothing is running that could answer, so the seat reserved for an answer is
        # given up. Left standing it would block every other writer from telling the
        # reader that nothing is coming.
        if seat_is_free and reply_target is not None:
            release_delivery_reply(session_id, payload["id"], reply_target)
        socket.close()
        raise
    return DeliveryTurn(
        observer, session_id, socket, turn_id, payload["id"], reply_target, buffered
    )


class DeliveryTurn(CarriedTurn):
    """One delivery's turn in the task this adapter watches.

    Leaf's names for the turn are the turn opened on every page the task claims and
    the seat its final answer commits into. The observer holds the delivery as
    carried for as long as this runs, so the connection watching the task passes
    over everything this turn says rather than writing it a second time.
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
        open_stream_turn(self.session_id, self.turn_id)
        accept_offered_delivery(self.session_id, self.delivery_id, self.turn_id)
        self.open_reply()
        set_stream_activity(self.session_id, self.turn_id, {"kind": "working"})

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

    def close(self, terminal: dict, reply_error: BaseException | None) -> None:
        """Close the turn on every page the task claims, and take its reading off."""
        if reply_error is not None:
            print(
                f"Codex final reply rejected: {reply_error}",
                file=sys.stderr,
                flush=True,
            )
        close_stream_turn(self.session_id, self.turn_id)
        clear_stream_activity(self.session_id, self.turn_id)

    def disconnect(self) -> None:
        """Leave a still-running turn to a later carrier, with its text on the page."""
        if self.reply_stream is not None:
            self.reply_stream.disconnect()
        clear_stream_activity(self.session_id, self.turn_id)


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
    """Persist one watcher batch in the session's collecting queue."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        captured = append_batch(
            session_id,
            reading.page_dir,
            reading.transaction,
            reading.batch,
        )
    return captured is not None


def _finish_batch(batch: dict, transport: dict | None = None) -> None:
    """Take receipt for one persisted batch, preserving a successor's claim."""
    page_dir = Path(batch["page"])
    try:
        with (
            PageTransaction(page_dir) as page,
            receive_batch(page, batch, session_id=batch["session"]) as delivered,
        ):
            record_pickup(
                page,
                delivered,
                phase=(transport or {}).get("phase", "queued"),
                session=batch["session"],
                turn=(transport or {}).get("turn"),
            )
    except (FileNotFoundError, ReceiptRefused):
        # The accepted transport record survives, but a removed or transferred
        # page has no cursor this carrier may advance.
        pass


def _page_acknowledged(batch: dict) -> bool:
    page_dir = Path(batch["page"])
    if not (page_dir / EVENTS_FILE).is_file():
        return True
    return read_cursor(page_dir) >= max(event["seq"] for event in batch["events"])


def _sync_receipts(path: Path, queue: dict) -> None:
    """Persist page receipts before archiving completed queue state."""
    changed = False
    for batch in queue["batches"]:
        if not batch["receipted"] and _page_acknowledged(batch):
            batch["receipted"] = True
            changed = True
    if changed:
        write_queue(path, queue)
    else:
        archive_queue(path, queue)


def _record_receipt(path: Path, batch_index: int) -> None:
    queue = read_json(path)
    if queue is not None and not queue["batches"][batch_index]["receipted"]:
        queue["batches"][batch_index]["receipted"] = True
        write_queue(path, queue)


def _recover_receipt(session_id: str) -> bool:
    """Reconcile one accepted batch while its session still owns the page."""
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        queues = queue_records(session_id)
        for path, queue in queues:
            _sync_receipts(path, queue)
        pending = min(
            (
                (path, index, dict(batch), queue.get("transport"))
                for path, queue in queue_records(session_id)
                if queue["state"] == "accepted"
                for index, batch in enumerate(queue["batches"])
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
    _finish_batch(batch, transport)
    with flocked(lock):
        _record_receipt(path, batch_index)
    return True


def _offer_queued_delivery(
    codex_path: str,
    session_id: str,
    observer: "TaskObserver | None",
    follow,
) -> bool:
    """Offer one collecting delivery through the selected Codex transport.

    Over App Server the offer is a turn this process starts and then follows, so
    what this returns says only that the delivery left the queue. Its acceptance,
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
    lock = delivery_lock_path(session_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with flocked(lock):
        queues = queue_records(session_id)
        unoffered = next(
            (
                (path, queue)
                for path, queue in queues
                if queue["state"] in {"collecting", "offering"}
            ),
            None,
        )
        queued = None
        if unoffered is not None:
            path, queue = unoffered
            prepared = offer_delivery(path, queue)
            queued = prepared.queue_path, queue, prepared
    if queued is None:
        return False
    path, _offered, prepared = queued
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
    with flocked(lock):
        queue = read_json(path)
        if queue is not None and queue["state"] == "offering":
            queue["state"] = "accepted"
            queue["transport"] = {"phase": "queued", "turn": None}
            write_queue(path, queue)
    return True


def _has_delivery_work(session_id: str) -> bool:
    with flocked(delivery_lock_path(session_id)):
        return any(
            queue["state"] != "accepted"
            or any(not batch["receipted"] for batch in queue["batches"])
            for _, queue in queue_records(session_id)
        )


def run_adapter(
    codex_path: str,
    ready_fd: int | None = None,
    app_server: str | None = None,
) -> int:
    """Own the session watch until every claimed page ends or transfers."""
    harness = session_harness()
    if harness is None or harness.name != CodexHarness.name:
        raise RuntimeError("the Codex adapter needs a Codex task identity")
    lease = take_waiter_lease(adapter_lease_path(harness.session))
    if lease is None:
        raise RuntimeError("a Codex delivery adapter is already active")
    # The lease record names this adapter's transport, so a later `leaf codex start`
    # in the task reports the one it joins.
    lease.truncate(0)
    lease.write(json.dumps({"app_server": app_server}).encode())
    lease.flush()
    watch = Watch(harness)
    if not watch.acquire():
        lease.close()
        raise RuntimeError(
            "another `leaf wait` is already active; stop it before starting delivery"
        )
    leases_released = False
    observer = None
    followers: list[tuple[threading.Thread, DeliveryTurn]] = []
    start_lock = adapter_start_lock_path(harness.session)
    start_lock.parent.mkdir(parents=True, exist_ok=True)

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

    try:
        if app_server is not None:
            observer = TaskObserver(app_server, harness.session)
            observer.start()
        else:
            check_queue_command(codex_path)
        if ready_fd is not None:
            os.write(ready_fd, b'{"ready":true}\n')
            os.close(ready_fd)
            ready_fd = None
        failures = 0
        while True:
            try:
                recovered = _recover_receipt(harness.session)
                if not recovered:
                    with flocked(start_lock):
                        if not owned_pages(harness.session):
                            watch.release()
                            lease.close()
                            leases_released = True
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
                    watch.release()
                    lease.close()
                    leases_released = True
                    return reading.outcome or 0
            time.sleep(1)
    except BaseException as error:
        if ready_fd is not None:
            os.write(
                ready_fd,
                (json.dumps({"ready": False, "error": str(error)}) + "\n").encode(),
            )
            os.close(ready_fd)
        raise
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
            lease.close()


def cmd_codex_start(
    page_dir: Path,
    codex_path: str | None = None,
    app_server: str | None = None,
) -> str:
    """Claim PAGE and start one detached delivery carrier for this task."""
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
    transition = take_page_claim(page_dir)
    launch_lock = adapter_start_lock_path(session_id)
    launch_lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with flocked(launch_lock):
            if adapter_is_live(session_id):
                record = adapter_lease_path(session_id).read_text()
                try:
                    running = json.loads(record)["app_server"]
                except (ValueError, KeyError, TypeError):
                    # An adapter built before the record named its transport.
                    return f"Codex delivery is already active for task {session_id}"
                if app_server is not None and app_server != running:
                    raise RuntimeError(
                        f"Codex delivery is already active for task {session_id}"
                        f"{_transport(running)}, not through App Server {app_server}"
                    )
                return (
                    f"Codex delivery is already active for task {session_id}"
                    f"{_transport(running)}"
                )
            read_fd, write_fd = os.pipe()
            log_path = adapter_log_path(session_id)
            with open(log_path, "ab", buffering=0) as log:
                arguments = [
                    sys.executable,
                    "-m",
                    "leaf",
                    "codex",
                    "run",
                    "--codex-path",
                    executable,
                    "--ready-fd",
                    str(write_fd),
                ]
                if app_server is not None:
                    arguments.extend(["--app-server", app_server])
                process = subprocess.Popen(
                    arguments,
                    cwd=state_home(),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                    pass_fds=(write_fd,),
                )
            os.close(write_fd)
            try:
                ready, _, _ = select.select([read_fd], [], [], START_TIMEOUT)
                if not ready:
                    process.terminate()
                    process.wait(timeout=5)
                    raise RuntimeError("Codex delivery did not become ready")
                answer = json.loads(os.read(read_fd, 65536))
            finally:
                os.close(read_fd)
            if not answer.get("ready"):
                process.wait(timeout=5)
                raise RuntimeError(
                    answer.get("error") or "Codex delivery failed to start"
                )
    except BaseException:
        restore_page_claim(page_dir, transition)
        raise
    return f"Codex delivery started for task {session_id}{_transport(app_server)}"


def _transport(app_server: str | None) -> str:
    """How `leaf codex start` names a transport: the App Server's endpoint, or
    nothing for the queue, which is how the host contracts tell the two apart."""
    return f" through App Server {app_server}" if app_server else ""


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


def cmd_codex_launch(codex_path: str | None = None) -> int:
    """Run one private App Server and its Codex terminal client."""
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find the `codex` executable on PATH")
    with tempfile.TemporaryDirectory(prefix="leaf-codex-", dir="/tmp") as directory:
        path = Path(directory) / "app-server.sock"
        endpoint = f"unix://{path}"
        environment = os.environ | {APP_SERVER_ENV: endpoint}
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [executable, "app-server", "--listen", endpoint],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                _wait_for_app_server(path, server, log)
                return subprocess.call(
                    [executable, "--remote", endpoint],
                    env=environment,
                )
            finally:
                stop_app_server(server)
