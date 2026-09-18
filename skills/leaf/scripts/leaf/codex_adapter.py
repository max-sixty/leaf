"""The detached process that carries Leaf delivery into later turns of one Codex task.

`leaf codex start` claims a page and leaves this process running behind the turn that
started it, so a reader's later moves reach the same Codex task instead of waiting for
the agent to ask again. It owns the session watch: it captures each batch into the
task's delivery record, offers one delivery at a time, and reconciles the receipt its
page is owed however that delivery was taken.

One of two transports carries an offer. `AppServerClient` observes the task's App
Server and opens a turn as soon as the task is idle, which is also how the reader sees
activity and a streamed answer; the `codex queue` command leaves a pointer for the
task's next turn, and the turn reports back through `leaf delivery claim`. The private
App Server the first transport needs is what `leaf codex launch` runs.

`codex.py` owns the protocol, the delivery records, and the page writers both
transports share. What is here is the process around them.
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
from .conversation import delivery_reply_reserved, reserve_delivery_reply
from .event_log import flocked, read_cursor
from .files import read_json
from .host import CodexHarness, session_harness, state_home
from .leases import adapter_is_live, adapter_lease_path, take_waiter_lease
from .schema import EVENTS_FILE
from .service import (
    PageTransaction,
    owned_pages,
    restore_page_claim,
    take_page_claim,
)
from .session import Watch, acknowledge, read_watch_pass, record_pickup

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


class AppServerClient:
    """Observe one Codex task and open idle turns with Leaf deliveries."""

    def __init__(self, endpoint: str, thread_id: str):
        check_app_server_endpoint(endpoint)
        self.endpoint = endpoint
        self.thread_id = thread_id
        self.events = AppServerEvents(thread_id)
        self.stop_event = threading.Event()
        self.available = threading.Event()
        self.socket = None
        self.last_activity_update = 0.0
        self.started = False
        self.request_id = 2
        self.requests: queue.Queue[dict] = queue.Queue()
        self.deferred: dict | None = None
        self.waiter_lock = threading.Lock()
        self.waiters: dict[str, queue.Queue] = {}
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
        self.available.clear()
        self._fail_pending(RuntimeError("Codex App Server client stopped"))
        if self.socket is not None:
            self.socket.close()
        self.thread.join(timeout=3)
        self._disconnect_streams()

    def start_delivery(self, payload: dict) -> dict | None:
        """Open a turn once this observed App Server task is idle."""
        answer: queue.Queue[tuple[dict | None, Exception | None]] = queue.Queue(
            maxsize=1
        )
        with self.waiter_lock:
            if self.stop_event.is_set() or not self.available.is_set():
                return None
            delivery_id = payload["id"]
            if delivery_id in self.waiters:
                raise RuntimeError(f"delivery {delivery_id} is already pending")
            self.waiters[delivery_id] = answer
            self.requests.put(payload)
        result = answer.get()
        result, error = result
        if error is not None:
            raise AppServerDeliveryUncertain(str(error)) from error
        return result

    def _send(
        self,
        socket,
        method: str,
        request_id: int,
        params: dict,
        pending: list[dict] | None = None,
    ) -> dict:
        """Request on this observer's connection, folding what it does not hold."""
        return app_server_request(
            socket,
            method,
            request_id,
            params,
            pending.append if pending is not None else self._read,
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
            if resumed.get("status", {}).get("type") == "active":
                active = next(
                    (
                        turn["id"]
                        for turn in reversed(resumed.get("turns", []))
                        if turn.get("status") == "inProgress"
                    ),
                    "active",
                )
                self.events.turn_id = active
                set_stream_activity(self.thread_id, active, "Working in Codex")
            with self.waiter_lock:
                if self.stop_event.is_set():
                    return
                self.available.set()
            if not self.started:
                self.started = True
                self.ready.put(None)
            while not self.stop_event.is_set():
                payload = self._next_delivery()
                if payload is not None:
                    try:
                        self._start_delivery(socket, payload)
                    except Exception as error:
                        self._answer_delivery(payload["id"], error=error)
                        raise
                    continue
                try:
                    raw = socket.recv(timeout=0.1)
                except TimeoutError:
                    continue
                self._read(json.loads(raw))

    def _next_delivery(self) -> dict | None:
        """Take the next scheduled delivery that still owns a live waiter."""
        while True:
            with self.waiter_lock:
                if self.deferred is not None:
                    if self.events.turn_id is not None:
                        return None
                    payload = self.deferred
                    self.deferred = None
                else:
                    try:
                        payload = self.requests.get_nowait()
                    except queue.Empty:
                        return None
                if payload["id"] in self.waiters:
                    return payload

    def _defer_delivery(self, payload: dict) -> bool:
        """Keep a live delivery scheduled until the provider becomes idle."""
        with self.waiter_lock:
            if payload["id"] not in self.waiters:
                return False
            self.deferred = payload
            return True

    def _start_delivery(self, socket, payload: dict) -> None:
        pending: list[dict] = []

        def request(method: str, params: dict) -> dict:
            request_id = self.request_id
            self.request_id += 1
            return self._send(socket, method, request_id, params, pending)

        if self.events.turn_id is not None:
            self._defer_delivery(payload)
            return
        try:
            result = request(
                "turn/start", app_server_turn_start_params(self.thread_id, payload)
            )
        except AppServerRequestRejected:
            self._read_pending(pending)
            if self.events.turn_id is None:
                raise
            self._defer_delivery(payload)
            return
        turn = result.get("turn") or {}
        if not turn.get("id"):
            raise RuntimeError("Codex App Server returned no turn id")
        self.events.restore_turn(turn)
        if not self._defer_delivery(payload):
            return
        for delivery_id, turn_id in self._read_pending(pending, defer_answer=True):
            self._answer_delivery(
                delivery_id,
                result={"phase": "opened", "turn": turn_id},
            )

    def _read_pending(
        self, pending: list[dict], *, defer_answer: bool = False
    ) -> list[tuple[str, str]]:
        """Read notifications held behind one request, in arrival order."""
        observed_deliveries = []
        for message in pending:
            if observed := self._read(message, defer_answer=defer_answer):
                observed_deliveries.append(observed)
        return observed_deliveries

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
                error = self._finish_binding(
                    turn_id,
                    turn.get("status", "failed"),
                    self.events.final_text(turn),
                )
                close_stream_turn(self.thread_id, turn_id)
                if self.events.turn_id == turn_id:
                    self.events.turn_id = None
                if error is not None:
                    print(
                        f"Codex final reply rejected: {error}",
                        file=sys.stderr,
                        flush=True,
                    )
        for turn in turns.values():
            if turn["id"] not in known_turns:
                self._restore_delivery_binding(turn)

    def _restore_delivery_binding(self, turn: dict) -> None:
        """Recover a provider turn from the immutable delivery it carries."""
        turn_id = turn["id"]
        if turn_id in self.bindings:
            return
        delivery_id = app_server_delivery_id(
            {"method": "turn/started", "params": {"turn": turn}}
        )
        if delivery_id is None:
            return
        path = queue_path(self.thread_id, delivery_id)
        with flocked(delivery_lock_path(self.thread_id)):
            queue_record = read_json(path)
        self._accept_observed_delivery(turn_id, delivery_id, queue_record)
        target = delivery_stream_reply_target(self.thread_id, delivery_id)
        if target is None:
            self._answer_delivery(
                delivery_id,
                result={"phase": "opened", "turn": turn_id},
            )
            return
        status = turn.get("status", "failed")
        if status == "inProgress":
            open_stream_turn(self.thread_id, turn_id)
            self._bind(turn_id, delivery_id, target)
            self.bindings[turn_id].restore(self.events.final_text(turn))
        else:
            self._bind(turn_id, delivery_id, target)
            error = self._finish_binding(
                turn_id,
                status,
                self.events.final_text(turn),
            )
            close_stream_turn(self.thread_id, turn_id)
            if error is not None:
                print(
                    f"Codex final reply rejected: {error}",
                    file=sys.stderr,
                    flush=True,
                )
        self._answer_delivery(
            delivery_id,
            result={"phase": "opened", "turn": turn_id},
        )

    def _accept_observed_delivery(
        self,
        turn_id: str,
        delivery_id: str,
        queue_record: dict | None = None,
    ) -> None:
        """Accept only provider evidence that carries the offered delivery id."""
        if queue_record is None:
            path = queue_path(self.thread_id, delivery_id)
            with flocked(delivery_lock_path(self.thread_id)):
                queue_record = read_json(path)
        if queue_record is not None and queue_record["state"] == "offering":
            accept_codex_delivery(self.thread_id, turn=turn_id)

    def _read(
        self, message: dict, *, defer_answer: bool = False
    ) -> tuple[str, str] | None:
        update = self.events.read(message)
        if update is None:
            return
        turn_id = update["turn"]
        observed_delivery = None
        if message.get("method") == "turn/started":
            open_stream_turn(self.thread_id, turn_id)
        delivery_id = app_server_delivery_id(message)
        if delivery_id is not None and turn_id not in self.bindings:
            self._accept_observed_delivery(turn_id, delivery_id)
            target = delivery_stream_reply_target(self.thread_id, delivery_id)
            if target is not None:
                self._bind(turn_id, delivery_id, target)
            observed_delivery = (delivery_id, turn_id)
        self.last_activity_update = project_app_server_activity(
            self.events,
            message,
            update,
            self.last_activity_update,
        )
        if stream := self.bindings.get(turn_id):
            stream.update(update)
        if completed := update.get("completed"):
            error = self._finish_binding(turn_id, completed, update.get("text", ""))
            close_stream_turn(self.thread_id, turn_id)
            if error is not None:
                print(
                    f"Codex final reply rejected: {error}",
                    file=sys.stderr,
                    flush=True,
                )
        if observed_delivery is not None and not defer_answer:
            self._answer_delivery(
                observed_delivery[0],
                result={"phase": "opened", "turn": observed_delivery[1]},
            )
            return None
        return observed_delivery

    def _finish_binding(
        self, turn_id: str, state: str, text: str
    ) -> BaseException | None:
        stream = self.bindings.pop(turn_id, None)
        if stream is None:
            return None
        return stream.finish(state, text)

    def _fail_pending(self, error: BaseException) -> None:
        """Return every delivery waiter owned by this client to its retry boundary."""
        with self.waiter_lock:
            answers = list(self.waiters.values())
            self.waiters.clear()
            self.deferred = None
            while True:
                try:
                    self.requests.get_nowait()
                except queue.Empty:
                    break
        for answer in answers:
            answer.put((None, error))

    def _answer_delivery(
        self,
        delivery_id: str,
        *,
        result: dict | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Resolve a delivery only after all fallible reply binding has succeeded."""
        with self.waiter_lock:
            answer = self.waiters.pop(delivery_id, None)
            if self.deferred is not None and self.deferred["id"] == delivery_id:
                self.deferred = None
        if answer is not None:
            answer.put((result, error))

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
            # This is the observer thread's recovery boundary: no connection or
            # notification failure may leave the adapter marked available.
            except Exception as error:  # noqa: BLE001
                self.available.clear()
                self._fail_pending(error)
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
    expected = {event["seq"]: event["id"] for event in batch["events"]}
    try:
        with PageTransaction(page_dir) as page:
            delivered = {
                event["seq"]: event
                for event in page.events
                if min(expected) <= event["seq"] <= max(expected)
            }
            if not all(
                delivered.get(seq, {}).get("id") == event_id
                for seq, event_id in expected.items()
            ):
                return
            record_pickup(
                page,
                [delivered[seq] for seq in expected],
                phase=(transport or {}).get("phase", "queued"),
                session=batch["session"],
                turn=(transport or {}).get("turn"),
            )
            acknowledge(page, max(expected))
    except FileNotFoundError:
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
    """Reconcile one accepted batch with its page, regardless of ownership."""
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
    app_client: AppServerClient | None = None,
) -> bool:
    """Offer one collecting delivery through the selected Codex transport."""
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
            queued = path, queue, offer_delivery(path, queue)
    if queued is not None:
        path, _offered, prepared = queued
        target = stream_reply_target(prepared.payload)
        if (
            target is not None
            and app_client is None
            and delivery_reply_reserved(session_id, prepared.payload["id"], target)
        ):
            raise AppServerDeliveryUncertain(
                "the observed App Server delivery is awaiting reconciliation"
            )
        if target is not None and app_client is not None:
            reserve_delivery_reply(session_id, prepared.payload["id"], target)
        if app_client is not None:
            transport = app_client.start_delivery(prepared.payload)
            if transport is None:
                raise AppServerDeliveryUncertain(
                    "the observed App Server disconnected before delivery"
                )
        else:
            queue_delivery(codex_path, session_id, prepared.prompt)
            transport = {"phase": "queued", "turn": None}
        with flocked(lock):
            queue = read_json(path)
            if queue is not None and queue["state"] == "offering":
                queue["state"] = "accepted"
                queue["transport"] = transport
                write_queue(path, queue)
        return True
    return False


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
    watch = Watch(harness)
    if not watch.acquire():
        lease.close()
        raise RuntimeError(
            "another `leaf wait` is already active; stop it before starting delivery"
        )
    leases_released = False
    app_client = None
    start_lock = adapter_start_lock_path(harness.session)
    start_lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        if app_server is not None:
            app_client = AppServerClient(app_server, harness.session)
            app_client.start()
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
                    if app_client is not None and not app_client.available.is_set():
                        raise AppServerDeliveryUncertain(
                            "the observed App Server is reconnecting"
                        )
                    recovered = _offer_queued_delivery(
                        codex_path,
                        harness.session,
                        app_client,
                    )
            except (OSError, RuntimeError) as error:
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

            def capture(reading) -> bool:
                """Persist the batch without claiming that a turn opened."""
                nonlocal captured
                captured = capture_batch(harness.session, reading)
                return False

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
        if app_client is not None:
            app_client.stop()
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
                return f"Codex delivery is already active for task {session_id}"
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
    connected = f" through App Server {app_server}" if app_server else ""
    return f"Codex delivery started for task {session_id}{connected}"


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
