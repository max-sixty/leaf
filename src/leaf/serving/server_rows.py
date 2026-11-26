"""Disposable neighbor-row delivery, computed by each serving page alone.

The document and log remain the authority. A server publishes their canonical
activity fold to state-home rows/<page-key>.json, together with its title, its
working directory and the user's counts its Leaf panel marks (On Me, open threads,
threads with unread words), which neighbors and Leaf's Claude Code band show. The record is bound to service.server_id, so another server
incarnation cannot inherit it; the server lease decides whether any row exists.
Deleting every row only hides neighbors until their next maintenance look. No
server removes its own row, since a server can die without a last word; the reader
that finds a readable row's server lease unheld deletes it
(`presence.other_leaves`).

A per-page producer checks this page's inputs and live harness, process and waiter
facts every presence-cache interval, or at the fold's next transition. Retained
servers spend no native subscriptions on maintenance. Changed inputs or a due
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

from leaf.agents.presence import PRESENCE_CACHE_S, live_facts, nudge_interrupted
from leaf.base.page_memory import memory_of
from leaf.base.rows import ROW, row_path
from leaf.base.service import page_claim
from leaf.base.state import page_key
from leaf.serving.served_state.service import PageStateService
from leaf.serving.server_lifetime import exit_serving
from leaf.source.page_inputs import page_reading


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
                self.refresh()
                delay = PRESENCE_CACHE_S
                if self.transition is not None:
                    delay = min(delay, max(0.0, self.transition - time.time()))
                time.sleep(delay)
        except Exception as error:
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
            and ROW.file(self.path).is_file()
        ):
            return
        # Only an idle harness record with no watcher can mean an interrupted turn
        # left input nothing carries; `nudge_interrupted` decides from there.
        assert live is not None
        if (live["live_turn"] or {}).get("state") == "idle" and not live["listening"]:
            nudge_interrupted(self.page_dir)
        row, self.reading, self.live = self.service.activity_row()
        deadline = row["activity"]["next_transition_at"]
        self.transition = (
            datetime.fromisoformat(deadline).timestamp() if deadline else None
        )
        if row != self.row or not ROW.file(self.path).is_file():
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
