"""Disposable neighbor-row delivery, computed by each serving page alone.

The document and log remain the authority. A server publishes their canonical
activity fold to state-home rows/<page-key>.json, together with its title, its
working directory and the user's counts its Leaf panel marks (On me, open threads,
threads with unread words), which neighbors and Leaf's Claude Code band show. The record is bound to service.server_id, so another server
incarnation cannot inherit it; the server lease decides whether any row exists.
Deleting every row only hides neighbors until their next maintenance look. No
server removes its own row, since a server can die without a last word; the reader
that finds a readable row's server lease unheld deletes it
(`presence.other_leaves`).

A per-page producer subscribes to this page's application writes and checks live harness,
process and waiter facts every presence-cache interval. Changed inputs or the fold's next
transition trigger a local transaction and fold; quiet looks never reread the
log or document. Only changed row content is replaced. Neighbor consumers read
this small output and server liveness, without folding any neighboring page.
A change in those facts is also how the server learns that the claimant's turn was
interrupted, which runs no hook, so the producer then messages a claimant whose
interrupted turn left input nothing will carry (`presence.nudge_interrupted`).
The lifetime supervisor runs independently: a page writer holding the transaction
must never prevent a stop. A failed producer ends the serving process, so its
lease withdraws the row. The enabled service remains eligible for the existing
server revival path.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from .file_changes import page_changes
from .page_memory import memory_of
from .presence import PRESENCE_CACHE_S, live_facts, nudge_interrupted
from .served_state.reading import page_reading
from .served_state.service import PageStateService
from .server import exit_serving
from .service import page_claim
from .state import STRING, Record, described, object_schema, page_key, state_home

ACTIVITY_FIELDS = frozenset(
    {
        "kind",
        "held",
        "dropped",
        "detail",
        "observed",
        "observed_kind",
        "awaiting",
        "counts",
        "ts",
        "next_transition_at",
    }
)
COUNT_FIELDS = frozenset(
    {"active", "handling", "queued", "picked_up", "pending", "overdue", "total"}
)


def compact_activity(activity: dict) -> dict:
    """The bounded presentation contract; owed updates and reply bodies stay local."""
    return {key: activity[key] for key in ACTIVITY_FIELDS}


def row_path(page_dir: Path) -> Path:
    return state_home() / "rows" / f"{page_key(page_dir)}.json"


COUNT = {"type": "integer", "minimum": 0}

ROW = Record(
    "row",
    described(
        "A serving page's row, which other pages show it by, in the state home's "
        "`rows/<page key>.json`.",
        object_schema(
            {
                "page": described("The page directory.", STRING),
                "page_key": described("The page's key (`state.page_key`).", STRING),
                "server_id": described(
                    "The server incarnation that published the row; a reader "
                    "takes only the live service's own.",
                    STRING,
                ),
                "row": described(
                    "What other pages show of it.",
                    object_schema(
                        {
                            "title": described("The page's title.", STRING),
                            "session_cwd": described(
                                "The claimant session's working directory, or null.",
                                {"type": ["string", "null"]},
                            ),
                            "activity": described(
                                "The page's activity, bounded to the fields a row "
                                "shows (`compact_activity`).",
                                {
                                    "type": "object",
                                    "properties": {
                                        "counts": {
                                            "type": "object",
                                            "required": sorted(COUNT_FIELDS),
                                        }
                                    },
                                    "required": sorted(ACTIVITY_FIELDS),
                                },
                            ),
                            "on_user": described("How many rows On me holds.", COUNT),
                            "threads": described(
                                "What the Leaf panel counts of the threads (`thread_counts`): "
                                "the open threads, and of those the ones the user hasn't read.",
                                object_schema({"open": COUNT, "unread": COUNT}),
                            ),
                        }
                    ),
                ),
            }
        ),
    ),
    since=16,
)


def read_row(page_dir: Path, service: dict, *, record=None) -> dict | None:
    """The row this live service's own incarnation published for the page, from
    `record` where the caller has already read it."""
    if record is None:
        record = ROW.read(row_path(page_dir))
    if record is None or record["server_id"] != service["server_id"]:
        return None
    return record["row"]


class RowPublisher:
    """The serving process's held input key and last delivered compact row."""

    def __init__(self, page_dir: Path, server_id: str):
        self.page_dir = page_dir
        self.memory = memory_of(page_dir)
        self.server_id = server_id
        self.service = PageStateService(page_dir)
        self.reading = None
        self.live = None
        self.live_until = 0.0
        self.transition = None
        self.row = None
        self.path = row_path(page_dir)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def run(self) -> None:
        """Publish for this server process's lifetime, withdrawing failed output."""
        try:
            while True:
                changes, mark = page_changes(self.page_dir)
                self.refresh()
                delay = PRESENCE_CACHE_S
                if self.transition is not None:
                    delay = min(delay, max(0.0, self.transition - time.time()))
                changes.wait(mark, delay)
        except Exception as error:  # noqa: BLE001 - a producer must not die under a live lease
            print(
                f"leaf server: {self.page_dir}: row publication failed: {error}",
                file=sys.stderr,
                flush=True,
            )
            exit_serving(1)

    def refresh(self) -> None:
        """Publish changed own inputs, including activity aging without a tab."""
        reading = page_reading(self.page_dir)
        clock = time.monotonic()
        live = self.live
        if reading != self.reading or clock >= self.live_until:
            live = live_facts(self.page_dir, page_claim(self.page_dir))
            self.live_until = clock + PRESENCE_CACHE_S
        due = self.transition is not None and time.time() >= self.transition
        if (
            reading == self.reading
            and live == self.live
            and not due
            and self.path.is_file()
        ):
            return
        # Only an idle harness record with no watcher can mean an interrupted turn
        # left input nothing carries; `nudge_interrupted` decides from there.
        if (live["live_turn"] or {}).get("state") == "idle" and not live["listening"]:
            nudge_interrupted(self.page_dir)
        row, self.reading, self.live = self.service.activity_row()
        deadline = row["activity"]["next_transition_at"]
        self.transition = (
            datetime.fromisoformat(deadline).timestamp() if deadline else None
        )
        if row != self.row or not self.path.is_file():
            ROW.write(
                self.path,
                {
                    "page": str(self.page_dir),
                    "page_key": page_key(self.page_dir),
                    "server_id": self.server_id,
                    "row": row,
                },
            )
            self.row = row
