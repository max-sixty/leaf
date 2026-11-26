"""How the Codex delivery adapter offers a Codex task its deliveries, and what other
processes read of it: the record of the adapter that runs (`running_adapter`) and the
start a claim makes or joins (`preparing_adapter`). The adapter itself, the detached
process that carries delivery into the task's later turns, is `leaf codex run`
(`codex_run.py`).

While a turn runs, its tool hook can offer the shared record between steps
(`codex.offer_hook_delivery`), and on the queue route its Stop hook as it would end
(`later_turn_takes_input`).
The adapter reserves its own transport only once that turn ends, or at once where
nothing would show it the turn's end (`offer_queued_delivery`), and an unread hook
pointer then falls back to the same durable delivery.

One of three transports carries the adapter's offer. A desktop chat a window of the
Codex desktop app has opened takes it as a turn the app starts, with the complete
delivery as a tool output and no message in the user's name (`codex_desktop.py`). The
adapter sees nothing of that turn but its id, so the task answers with explicit
commands. Only a start the app refused before running it falls back to the queue; one
it may have run waits for the chat's transcript to settle it. The `codex queue` command
is the default for a task whose App Server Leaf cannot reach. It leaves a pointer for
the task's next turn; the task reads that
immutable input through `leaf delivery read` and answers with explicit commands, the
reply included. On the macOS desktop, the adapter then wakes the queued chat through
the app's background deep link: an external queue write alone waits for Codex's
ten-second check. Queue acceptance precedes the wake, so a failed wake cannot resend
accepted input. Over App Server, one `TaskConnection` owns the subscribed socket,
serializes starts, and routes every notification into one `TurnFold` per provider
turn. It observes the user's turns and Leaf delivery turns alike. Losing the
connection disconnects the folds; reconnecting reconciles them with the provider's
transcript, because a terminal task keeps running after this adapter disconnects.
Over App Server, a delivery start first resumes the task for fresh idle evidence;
cached activity only holds an offer back. `TaskConnection` owns what an uncertain
start and a dropped connection leave behind.

Recovery reads the full, paginated provider history, because a summary or an unloaded
item can neither settle an answer nor prove absence. Accepted or abandoned deliveries
without a successful exact reply hydrate from it too, even when the first resume omits
their turns or the user resolved the thread. When complete history and a fresh idle
reading show no matching delivery, Leaf abandons its own attempt, releases its reply
reservation, and reports that the delivery could not be confirmed and is not retried, without
claiming that a provider turn failed (`codex.abandon_uncertain_delivery`). A manual
reply retires an unknown offer through receipt recovery, even while disconnected. Only
a start or the task's exact offered delivery introduces live authority, and an ordinary
item notification updates only a fold matching the subscription's epoch. The
interactive client continues to handle approvals and user-input requests.

`codex.py` owns the protocol, the per-turn fold every App Server client runs, the
delivery records, and the page writers both transports share.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path
from types import EllipsisType
from typing import TYPE_CHECKING

# The stream-activity writers are called as `codex.<name>`, so `leaf.agents.codex` holds their
# one binding: whatever takes a turn's readings there takes every client's too.
from leaf.agents import codex
from leaf.agents.codex import (
    APP_SERVER_ENV,
    AppServerDeliveryUncertain,
    TurnFold,
    accept_codex_delivery,
    app_server_connect,
    app_server_delivery_id,
    app_server_handshake,
    app_server_request,
    app_server_socket_path,
    append_batch,
    delivery_records,
    delivery_stream_reply_target,
    offer_delivery,
    private_app_server,
    read_task_delivery,
    retry_delay,
    start_app_server_delivery,
)
from leaf.agents.codex_desktop import (
    DesktopUnavailable,
    settle_desktop_start,
    start_desktop_delivery,
)
from leaf.agents.codex_state import (
    delivery_lock_path,
    delivery_turn,
    hook_turn,
)
from leaf.agents.delivery import stream_reply_target
from leaf.agents.thread import delivery_reply_reserved
from leaf.base.codex_transcript import sync_transcript_turn
from leaf.base.detached import starting_detached
from leaf.base.harness import Harness
from leaf.base.leases import (
    adapter_is_live,
    adapter_lease_path,
    hooks_ran,
    wait_is_live,
)
from leaf.base.refusals import Refused
from leaf.base.state import (
    Record,
    described,
    ensure_session,
    flocked,
    object_schema,
    session_file,
    session_record,
    start_session_turn,
    state_home,
    turn_closed,
)
from leaf.records.transaction import PageTransaction, owned_pages

if TYPE_CHECKING:
    from leaf.agents.thread import MessageCheck
    from leaf.records.work_state import WorkState

QUEUE_TIMEOUT = 20
ADAPTER = Record(
    "codex-adapter",
    described(
        "A Codex task's running delivery adapter, beside the lease it holds at "
        "the state home's `sessions/<digest>.adapter` (`running_adapter`).",
        object_schema(
            {
                "app_server": described(
                    "The Codex App Server the adapter delivers through, or null for "
                    "the task's queue.",
                    {"type": ["string", "null"]},
                )
            },
        ),
    ),
    since=56,
)


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
        raise Refused("Codex queue command timed out") from error
    if completed.returncode == 0:
        return
    detail = completed.stderr.strip() or completed.stdout.strip()
    if not detail:
        detail = f"Codex exited with status {completed.returncode}"
    raise Refused(detail)


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


def _in_desktop_chat() -> bool:
    return os.environ.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") == "Codex Desktop"


def _start_in_desktop_chat(thread_id: str, payload: dict) -> bool:
    """Whether the desktop app took this delivery's start, confirmed or not. False
    leaves it to the queue, with the reason in the adapter's log."""
    if not _in_desktop_chat():
        return False
    try:
        start_desktop_delivery(thread_id, payload)
    except DesktopUnavailable as error:
        print(
            f"Codex desktop start not taken; queueing instead: {error}",
            file=sys.stderr,
            flush=True,
        )
        return False
    except AppServerDeliveryUncertain as error:
        print(
            f"Codex desktop start unconfirmed; settling it from the chat's transcript: {error}",
            file=sys.stderr,
            flush=True,
        )
    return True


def _wake_desktop_queue(thread_id: str) -> None:
    """Resume an already queued desktop chat without opening or focusing it.

    The app handles `threads/wake` by reading the queue and resuming its thread;
    Codex still owns dispatch and starts only when idle. If the wake fails, the
    accepted message remains in the queue for Codex's external-write watcher.
    """
    if sys.platform != "darwin" or not _in_desktop_chat():
        return
    try:
        subprocess.run(
            ["open", "-g", f"codex://threads/wake/{thread_id}"],
            capture_output=True,
            text=True,
            timeout=QUEUE_TIMEOUT,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(
            f"Codex queue wake failed; input remains queued: {error}",
            file=sys.stderr,
            flush=True,
        )


class TaskConnection:
    """Own a task's subscription and serialized delivery starts on one socket.

    Only this owner's thread reads or writes the socket. The watcher submits a
    delivery through a Future, without holding page or delivery locks. Requests
    fold notifications while waiting; a start buffers them until its response
    binds the returned turn, then replays them in arrival order. Every provider
    turn has one fold, whether the user or Leaf started it.

    A delivery record is marked `starting` before its request goes out. A start
    whose response is lost is never sent blindly again, even after a restart or
    with no reply reservation; a rejected stale snapshot never marks the
    observer running. A dropped connection is unknown provider state, never a
    failed turn: it disconnects the turn's reply and clears live activity without
    inventing an ending or releasing a running turn's reservation. A later
    provider completion settles that turn, and a later session turn withdraws its
    reply reservation, so an explicit reply wins over a recovered final message.
    Resuming reconciles running and completed turns from their exact delivery
    identities.
    Live provider observations adopt the subscription's lifecycle token before
    fold selection. A resume response uses its pre-request token, so intervening
    notifications or a newer prompt win; exact historical answers settle without
    adopting a current lifecycle. Matching completion refreshes the token for the
    next natural provider turn. Terminal provider IDs remain terminal for this
    subscription, even after their heavy live folds are discarded; late output
    and stale running snapshots cannot give them a new lifecycle. The session
    record refuses to reopen only the turn it holds (`state.advance_turn`); an
    earlier id, such as the history a snapshot lists, only this subscription can
    name again, so it keeps those ids itself rather than writing each into the
    record, whose revision every hook offer compares against.
    """

    def __init__(
        self, endpoint: str, thread_id: str, check: "MessageCheck | None" = None
    ):
        self.endpoint = endpoint
        self.thread_id = thread_id
        # The check each turn's answer runs before it posts (`TurnFold`).
        self.check = check
        self.turns: dict[str, TurnFold] = {}
        self.running: str | None = None
        self.lifecycle = session_record(thread_id)
        self.terminal_turns: set[str] = (
            {self.lifecycle["turn"]} if turn_closed(self.lifecycle) else set()
        )
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
        outcome = self.ready.get()
        if outcome is not None:
            self.stop()
            raise Refused(f"Codex App Server connection failed: {outcome}")

    def stop(self) -> None:
        with self.submission_lock:
            self.stop_event.set()
        if self.socket is not None:
            self.socket.close()
        if self.thread.ident is not None:
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

        This comes off the persistent subscription, so the delivery loop can hold back
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
        record = read_task_delivery(self.thread_id, payload["id"])
        if record is None or isinstance(record, codex.ReceiptOutcome):
            return True
        uncertain = isinstance(record, codex.StartingOffer)
        thread, expected = self._resume_task(socket, exclude_turns=not uncertain)
        if uncertain:
            hydrated = self._resume(thread, expected)
            self._reconcile_history(socket, hydrated)
            return isinstance(
                read_task_delivery(self.thread_id, payload["id"]), codex.ReceiptOutcome
            )
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
        if not codex.begin_delivery_start(self.thread_id, payload["id"]):
            return True
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
                codex.release_delivery_start(self.thread_id, payload["id"])
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
                if isinstance(record, codex.StartingOffer)
            }
        # Receipts may already have archived an accepted delivery while its
        # provider turn was still running. A successful exact reply is the
        # completion evidence, independent of reservation or settlement lifetime.
        hydrated = hydrated or set()
        known = set(self.turns) - hydrated
        unresolved = set()
        directory = codex.delivery_dir(self.thread_id)
        for path in (
            *codex.RECORD.glob(directory),
            *codex.RECORD.glob(directory / "history"),
        ):
            record = codex.read_record(path)
            if not isinstance(record, codex.ReceiptOutcome):
                continue
            if isinstance(record, codex.Opened) and record.turn in hydrated:
                continue
            target = delivery_stream_reply_target(self.thread_id, path.stem)
            if target is not None and codex.reply_target_answered(target) is False:
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
            self._observe_terminals(page["data"])
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
                payload = codex.stored_delivery(delivery_id)
                assert payload is not None
                codex.abandon_uncertain_delivery(
                    self.thread_id,
                    payload,
                )

    def _resume(
        self, thread: dict, expected: dict | None | EllipsisType = ...
    ) -> set[str]:
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

    def _reconcile(
        self, turn: dict, expected: dict | None | EllipsisType = ...
    ) -> bool:
        """Bring one snapshot turn's fold up to what the snapshot says of it.

        A running turn is followed, whether or not it was before the connection
        dropped. An ended one is committed if something here was following it, or
        if it carries a delivery: its item was written while this connection was
        down, or its adapter process died while the turn ran on, and its answer
        is still to write. Its turn is closed, never reopened. The snapshot's other
        turns are history. Return whether this snapshot supplied complete items.
        """
        # A completion with unloaded items says it ended, but cannot say what
        # it answered. Preserve its fold and reservation until full hydration.
        running = turn.get("status") == "inProgress"
        self._observe_terminals([turn])
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
        if method == "turn/completed":
            self.terminal_turns.add(turn_id)
        delivery_id = app_server_delivery_id(message)
        # An offered delivery can name a turn whose `turn/started` reached the task
        # before this subscription was open to see it.
        adopting = (
            delivery_id is not None
            and turn_id not in self.turns
            and isinstance(
                read_task_delivery(self.thread_id, delivery_id),
                (codex.Offering, codex.Abandoned),
            )
        )
        if method != "turn/completed":
            # Background output can outlive its turn. A start or exact offered
            # delivery may introduce identity; ordinary items can only update
            # a fold that still owns this subscription's current epoch.
            if (
                method != "turn/started"
                and not adopting
                and (
                    turn_id not in self.turns
                    or self.lifecycle is None
                    or self.lifecycle["turn"] != turn_id
                )
            ):
                return
            if not self._observe_lifecycle(turn_id):
                return
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

    def _observe_terminals(self, turns: list[dict]) -> None:
        """Remember terminal identity even when items are unloaded or irrelevant.

        These provider observations survive removal of their live folds. They
        authorize no current state; they only prevent an ended ID from reopening.
        """
        self.terminal_turns.update(
            turn["id"] for turn in turns if turn.get("status") != "inProgress"
        )

    def _observe_lifecycle(
        self, turn_id: str, expected: dict | None | EllipsisType = ...
    ) -> bool:
        """Adopt ordered live provider evidence only against this subscription's epoch."""
        if turn_id in self.terminal_turns:
            return False
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
            fold = TurnFold(
                self.thread_id, turn_id, lifecycle=self.lifecycle, check=self.check
            )
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
            fold = TurnFold(
                self.thread_id, turn_id, lifecycle=self.lifecycle, check=self.check
            )
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
            except Exception as error:
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
                # This is the connection thread's recovery boundary: nothing it reads may
                # take the process down, and a lost connection is retried. A drop from a
                # connection that came up starts the retry ladder again.
                except Exception as error:
                    came_up = self.connected.is_set()
                    self._disconnect_turns()
                    if not self.started:
                        self.ready.put(error)
                        return
                    failures = 1 if came_up else failures + 1
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


def adapter_log_path(session_id: str) -> Path:
    return session_file(session_id, "codex.log")


def adapter_start_lock_path(session_id: str) -> Path:
    return session_file(session_id, "start")


def capture_batch(
    session_id: str,
    page: PageTransaction,
    batch: list[dict],
    *,
    work: "WorkState | None" = None,
) -> bool:
    """Persist `batch`, read under the page's transaction `page`, in the session's
    collecting record, by the page's work, `work` where the caller has already
    read it (`codex.append_batch`)."""
    with flocked(delivery_lock_path(session_id)):
        captured = append_batch(session_id, page.page_dir, page, batch, work=work)
    return captured is not None


def offer_queued_delivery(
    codex_path: str,
    session_id: str,
    connection: TaskConnection | None,
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
    if connection is None:
        # Resume may start with no input and therefore no prompt hook. Read the
        # provider's lifecycle before reserving the idle queue, including while
        # the resumed turn is still executing its first tool.
        sync_transcript_turn(session_id)
        # A start the desktop app may have run holds later input back until the
        # chat's transcript settles it, even in an adapter the chat started outside
        # the app, as a terminal resume does.
        if settle_desktop_start(session_id):
            return False
    observed_hook_turn = hook_turn(session_id)
    if (
        connection is None
        and observed_hook_turn is not None
        and (hooks_ran(session_id) or observed_hook_turn.get("transcript_path"))
        and delivery_turn(session_id) is not None
    ):
        # Codex runs a queued pointer only once the running turn ends, as a turn
        # of its own on a message in the user's name. So the input waits for the
        # turn's tool hook, or its Stop, to hand it in quietly, from the turn's
        # start, wherever Leaf will see that turn end: through the hooks, where
        # one has run in this instance, or through Codex's transcript, read
        # above, which shows a turn before the instance's first hook has run.
        # Once the turn ends, the queue takes the input, or a pointer the turn
        # left unread. With neither, nothing shows the end before the claim's
        # turn ages out, so the input goes to the queue at once.
        return False
    lock = delivery_lock_path(session_id)
    with flocked(lock):
        if hook_turn(session_id) != observed_hook_turn:
            # A prompt, ending, or tool step changed while activity was read.
            # Retry before reserving a transport against that newer observation.
            return False
        records = delivery_records(session_id)
        unoffered = next(
            (
                (path, record)
                for path, record in records
                if isinstance(record, (codex.Collecting, codex.Offering))
            ),
            None,
        )
        prepared = None
        if unoffered is not None:
            path, record = unoffered
            prepared = offer_delivery(
                path,
                record,
                transport="app-server" if connection is not None else "queue",
            )
    if prepared is None:
        return False
    if connection is not None:
        return connection.start_delivery(prepared.payload)
    # The embedded client makes its own reply reservation, whatever the adapter intends.
    # Read it outside the delivery lock: capture takes a page transaction first.
    target = stream_reply_target(prepared.payload)
    if target is not None and delivery_reply_reserved(
        session_id, prepared.payload["id"], target
    ):
        raise AppServerDeliveryUncertain(
            "the observed App Server delivery is awaiting reconciliation"
        )
    if _start_in_desktop_chat(session_id, prepared.payload):
        return True
    queue_delivery(codex_path, session_id, prepared.prompt)
    # `codex queue` takes no message id and lists nothing queued, so a failure
    # before this acceptance is recorded leaves the offer to be queued again rather
    # than risk losing it. A turn that acknowledges the first pointer before then
    # accepts it (`codex.confirm_codex_pointer`); otherwise Codex runs a turn
    # for each, and the second one's `delivery ack` says it repeats the first
    # (`delivery.earlier_pickup`).
    accept_codex_delivery(session_id, prepared.payload["id"], None)
    _wake_desktop_queue(session_id)
    return True


@contextmanager
def preparing_adapter(harness: Harness):
    """Retain a ready adapter for `harness`'s task until the caller commits page
    ownership (`hosting.preparing_delivery`), unless a model wait this task
    already selected remains its watcher.

    The same task start lock serializes adapter startup and no-page retirement.
    Holding it across the caller's publication lets delivery prepare before any
    claim exists, without an adapter retiring in that gap, and a failed
    preparation precedes any page ownership transition. A new adapter captures
    the launching harness's canonical session generation before subscribing to turns.
    """
    if wait_is_live(None, harness.session) and not adapter_is_live(harness.session):
        yield
        return
    executable = shutil.which("codex")
    if executable is None:
        raise Refused("cannot find the `codex` executable on PATH")
    executable = str(Path(executable).absolute())
    session_id = harness.session
    app_server = os.environ.get(APP_SERVER_ENV)
    if app_server is not None:
        app_server_socket_path(app_server)
    with flocked(adapter_start_lock_path(session_id)):
        record = running_adapter(session_id)
        if record is not None and "other" in record:
            if app_server is not None:
                raise Refused(
                    f"a Codex delivery adapter another Leaf version started is "
                    f"active for task {session_id}, through a transport this Leaf "
                    "can't read; it hands the task to this Leaf's adapter once the "
                    "task's hooks run this Leaf, so claim the page again after the "
                    "task's next prompt"
                )
            yield
            return
        if record is not None:
            running = record["app_server"]
            if app_server is not None and app_server != running:
                raise Refused(
                    f"Codex delivery is already active for task {session_id}"
                    + (f" through App Server {running}" if running else "")
                    + f", not through App Server {app_server}"
                )
            yield
            return
        # Existing active ownership already proves the canonical lifetime and
        # generation. A new acquisition establishes that evidence in its own harness.
        # owned_pages checks generation and liveness, so retained claims cannot
        # lend an ended session their former authority.
        if not owned_pages(session_id):
            ensure_session(session_id, harness.lifetime())
        start_adapter(harness, executable, app_server, None)
        yield


def start_adapter(
    harness: Harness,
    codex_path: str,
    app_server: str | None,
    launcher: Path | None,
) -> None:
    """Start an adapter for `harness`'s task through `launcher`, or else under this
    process's interpreter, and return once it holds its leases and its transport
    answers. The caller holds the task's start lock."""
    with starting_detached(
        [
            "codex",
            "run",
            "--codex-path",
            codex_path,
            *(["--app-server", app_server] if app_server is not None else []),
        ],
        harness=harness,
        what="Codex delivery",
        log=adapter_log_path(harness.session),
        cwd=state_home(),
        launcher=launcher,
    ):
        pass


def running_adapter(session_id: str) -> dict | None:
    """The live adapter's lease record, naming its transport, or None when no
    adapter holds the lease. An adapter can let go between the question and the
    read, since only its retirement takes the start lock, and its record goes with
    it; that reads as no adapter. One a Leaf of another `ADAPTER` shape started
    keeps its record where this Leaf reads none, so it reads as running with its
    transport unknown, `{"other": <its record>}`, and delivers the task's input
    until it hands the task to this Leaf's adapter (`state.Record`)."""
    if not adapter_is_live(session_id):
        return None
    path = adapter_lease_path(session_id)
    if (record := ADAPTER.read(path)) is not None:
        return record
    if others := ADAPTER.others(path):
        return {"other": others[0]}
    return None


def later_turn_takes_input(session_id: str) -> bool:
    """Whether input that arrives as this task's turn ends goes to a turn of its own
    rather than into the ending one, where the Stop hook would hand it
    (`hooks.offer_at_step`): only where the task's adapter delivers over App Server.

    That turn opens on a `leaf_delivery` tool output, which adds no message to the
    user's conversation. Through `codex queue` the turn opens on a `leaf-delivery`
    pointer that Codex shows as a message from the user, which is noisier than the
    one more message the ending turn writes, so there Stop hands the input into the
    ending turn.

    An adapter takes its lease before it writes its transport there, and holds the
    start lock across that, so the record is read under the start lock."""
    if not adapter_is_live(session_id):
        return False
    with flocked(adapter_start_lock_path(session_id)):
        adapter = running_adapter(session_id)
    # One another Leaf version started reads its own delivery records, not this
    # Leaf's, so input it will deliver is left to it, as to an App Server's.
    return adapter is not None and (
        "other" in adapter or adapter["app_server"] is not None
    )


def cmd_codex_launch(codex_path: str | None = None) -> int:
    """Run one private App Server and its Codex terminal client."""
    executable = codex_path or shutil.which("codex")
    if executable is None:
        raise Refused("cannot find the `codex` executable on PATH")
    with private_app_server(executable) as (endpoint, _process):
        return subprocess.call(
            [executable, "--remote", endpoint],
            env=os.environ | {APP_SERVER_ENV: endpoint},
        )
