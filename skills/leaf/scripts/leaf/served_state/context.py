"""The input boundary for served-state folds.

Live readers construct this inside their page transaction and keep that transaction
through projection: revision documents remain lazy. Frozen previews supply captured
readings instead, so every fold, including historical gesture words, stays inside
the capture. Neither mode chooses its inputs again downstream.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path

from ..data import read_data
from ..files import active_descriptor, list_revisions, version_descriptors
from ..passages import SourceReading
from ..presence import presence_with_activity
from ..registry.contract import RegistryError
from ..registry.storage import layer_metadata, page_vocabulary
from ..revision_artifact import read_revision
from ..session_cleanup import now_iso


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
    def data(self) -> dict:
        return self.stored_data()

    def through(self, sequence: int) -> "PageRead":
        """A comparison at an observed log boundary, without a live streaming reply."""
        latest = self.events[-1]["seq"] if self.events else 0
        if sequence > latest:
            raise ValueError(
                f"view sequence {sequence} is newer than log sequence {latest}"
            )
        return replace(
            self,
            events=[event for event in self.events if event["seq"] <= sequence],
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
    present, live_stream = presence_with_activity(page_dir, events)
    return PageRead(
        active=active,
        events=events,
        revisions=frozenset(list_revisions(page_dir)),
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
        versions=tuple(version_descriptors(page_dir, events)),
        presence=present,
        live_stream=live_stream,
        now=now or now_iso(),
        taken=time.time(),
    )
