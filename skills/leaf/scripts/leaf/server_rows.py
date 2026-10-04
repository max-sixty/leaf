"""Disposable neighbor-row delivery, computed by each serving page alone.

The document and log remain the authority. A server publishes their canonical
activity fold to state-home rows/<page-key>.json, together with its title and
working directory. The record is bound to service.server_id, so another server
incarnation cannot inherit it; the server lease decides whether any row exists.
Deleting every row only hides neighbors until their next maintenance look.

A per-page producer checks this page's file stamps every 100 ms and live host,
process and waiter facts every presence-cache interval. Changed inputs or the fold's next
transition trigger a local transaction and fold; quiet looks never reread the
log or document. Only changed row content is replaced. Neighbor consumers read
this small output and server liveness, without folding any neighboring page.
The lifetime supervisor runs independently: a page writer holding the transaction
must never prevent a stop. A failed producer ends the serving process, so its
lease withdraws the row. The enabled service remains eligible for the existing
server revival path.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .files import read_json
from .presence import PRESENCE_CACHE_S, live_facts
from .served_state.reading import page_reading
from .served_state.service import PageStateService
from .service import page_claim
from .state import page_key, state_home_path, write_json

ACTIVITY_FIELDS = frozenset(
    {
        "kind",
        "held",
        "dropped",
        "detail",
        "observed",
        "observed_kind",
        "counts",
        "ts",
        "next_transition_at",
    }
)
COUNT_FIELDS = frozenset(
    {"active", "handling", "queued", "picked_up", "pending", "overdue", "total"}
)


def compact_activity(activity: dict) -> dict:
    """The bounded presentation contract; owed moves and reply bodies stay local."""
    return {key: activity[key] for key in ACTIVITY_FIELDS}


def row_path(page_dir: Path) -> Path:
    return state_home_path() / "rows" / f"{page_key(page_dir)}.json"


def read_row(page_dir: Path, service: dict) -> dict | None:
    """Read compatible output from this live service's own publication."""
    record = read_json(row_path(page_dir))
    if not isinstance(record, dict) or not {"server_id", "row"} <= record.keys():
        return None
    row = record["row"]
    if (
        not isinstance(record["server_id"], str)
        or record["server_id"] != service.get("server_id")
        or not isinstance(row, dict)
        or not {"title", "session_cwd", "activity"} <= row.keys()
    ):
        return None
    activity = row["activity"]
    if (
        not isinstance(row["title"], str)
        or not isinstance(activity, dict)
        or not ACTIVITY_FIELDS <= activity.keys()
        or not isinstance(activity["counts"], dict)
        or not COUNT_FIELDS <= activity["counts"].keys()
    ):
        return None
    return row


class RowPublisher:
    """The serving process's held input key and last delivered compact row."""

    def __init__(self, page_dir: Path, server_id: str):
        self.page_dir = page_dir
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
                self.refresh()
                time.sleep(0.1)
        except Exception as error:  # noqa: BLE001 - a producer must not die under a live lease
            print(
                f"leaf server: {self.page_dir}: row publication failed: {error}",
                file=sys.stderr,
                flush=True,
            )
            os._exit(1)

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
        row, self.reading, self.live = self.service.activity_row()
        deadline = row["activity"]["next_transition_at"]
        self.transition = (
            datetime.fromisoformat(deadline).timestamp() if deadline else None
        )
        if row != self.row or not self.path.is_file():
            write_json(self.path, {"server_id": self.server_id, "row": row})
            self.row = row
