"""The input boundary for served-state folds.

Live readers construct this inside their page transaction and keep that transaction
through projection: revision documents remain lazy. Frozen previews supply captured
readings instead, so every fold, including historical gesture words, stays inside
the capture. Neither mode chooses its inputs again downstream.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path

from ..data import read_data
from ..files import (
    active_descriptor,
    document_descriptor,
    list_revisions,
    version_descriptors,
)
from ..passages import SourceReading
from ..presence import presence_with_activity
from ..registry.contract import RegistryError
from ..registry.storage import layer_metadata, page_vocabulary
from ..revision_artifact import read_revision
from ..state import now_iso


@dataclass(frozen=True)
class PageRead:
    active: dict | None
    events: list[dict]
    revisions: frozenset[int]
    revision: Callable[[int], SourceReading]
    registry: dict | None
    layer: dict
    stored_data: Callable[[], dict]
    versions: tuple[dict, ...]
    presence: dict
    live_stream: dict | None
    now: str
    taken: float

    @cached_property
    def work(self):
        from .work import work_state

        active = self.active
        return work_state(
            self.events,
            self.revision(active["revision"]) if active else None,
            active["revision"] if active else None,
            self.presence,
            self.now,
            self.live_stream,
            revisions=self.revisions,
            revision_reader=self.revision,
        )

    @cached_property
    def data(self) -> dict:
        return self.stored_data()

    def through(self, sequence: int) -> PageRead:
        """The read as it stood once event `sequence` was appended: the log and the
        versions it had stamped by then, without a live streaming reply.

        A browser compares a document view at the boundary its state was read at, and
        `leaf page picture` serves a page as it stood when a comment was posted."""
        latest = self.events[-1]["seq"] if self.events else 0
        if sequence > latest:
            raise ValueError(
                f"view sequence {sequence} is newer than log sequence {latest}"
            )
        events = [event for event in self.events if event["seq"] <= sequence]
        active = self.active
        if active is not None:
            active = document_descriptor(
                active["revision"],
                events,
                url=active["url"],
                executable=active["executable"],
                activated_at=active["activated_at"],
            )
        return replace(
            self,
            active=active,
            events=events,
            versions=tuple(version_descriptors(events, self.revisions)),
            live_stream=None,
        )


def read_page(
    page_dir: Path,
    events: list[dict],
    *,
    layer_identity: dict | None = None,
    now: str | None = None,
) -> PageRead:
    """Take live inputs without materializing the page's immutable history.

    The caller owns the transaction for this read and its consumers. Admission's
    explicit interpretation under an incoming registry is a separate boundary.
    """
    active = active_descriptor(page_dir, events)
    try:
        registry = page_vocabulary(page_dir, active["revision"] if active else None)
    except RegistryError:
        registry = None
    revisions = frozenset(list_revisions(page_dir))
    present, live_stream = presence_with_activity(page_dir, events)
    return PageRead(
        active=active,
        events=events,
        revisions=revisions,
        revision=lambda revision: read_revision(page_dir, revision),
        registry=registry,
        layer=(
            registry["$layer"]
            if active is not None and registry is not None
            else layer_metadata(page_dir)
            if layer_identity is None
            else layer_identity
        ),
        stored_data=lambda: read_data(page_dir, registry),
        versions=tuple(version_descriptors(events, revisions)),
        presence=present,
        live_stream=live_stream,
        now=now or now_iso(),
        taken=time.time(),
    )
