"""One frozen input for browser validation and export previews."""

import copy
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from .data import browser_data_from, read_data
from .event_log import now_iso
from .files import (
    list_revisions,
    revision_label,
    revision_name,
    revision_path,
    version_descriptors,
)
from .presence import other_leaves, presence_fingerprint, presence_with_activity
from .registry.storage import layer_metadata, require_registry
from .service import PageTransaction
from .structure import SourceDocument


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """The exact page facts an ephemeral browser server may expose."""

    document: SourceDocument
    active: dict
    events: tuple[dict, ...]
    registry: dict
    layer: dict
    data: dict
    browser_data: dict
    versions: tuple[dict, ...]
    documents: dict[int, SourceDocument]
    revision_names: dict[int, str]
    presence: dict
    live_stream: dict | None
    others: tuple[dict, ...]
    now: str
    taken: float
    reading: str


def capture_page_snapshot(
    page_dir: Path, document: SourceDocument, active: dict
) -> PageSnapshot:
    """Freeze a candidate and every page authority it is projected against."""
    with PageTransaction(page_dir) as page:
        events = tuple(copy.deepcopy(page.events))
        snapshot_active = copy.deepcopy(active)
        registry = copy.deepcopy(require_registry(page_dir))
        layer = copy.deepcopy(layer_metadata(page_dir))
        data = read_data(page_dir)
        versions = tuple(copy.deepcopy(version_descriptors(page_dir, list(events))))
        revisions = list_revisions(page_dir)
        documents = {
            revision: SourceDocument(
                revision_path(page_dir, revision).read_text(encoding="utf-8")
            )
            for revision in revisions
        }
        documents[active["revision"]] = document
        revision_names = {
            revision: revision_path(page_dir, revision).name for revision in revisions
        }
        revision_names[active["revision"]] = revision_name(
            active["revision"], document.data
        )
        present, live_stream = presence_with_activity(page_dir, list(events))
        others = tuple(copy.deepcopy(other_leaves(page_dir)))
        observed_at = now_iso()
        snapshot_active["label"] = (
            f"v{snapshot_active['version']}"
            if snapshot_active.get("version") is not None
            else revision_label(list(events), snapshot_active["revision"])
        )
        snapshot_active.setdefault("activated_at", observed_at)
        taken = time.time()
    browser_data = browser_data_from(copy.deepcopy(data), registry)
    files_reading = hashlib.sha256(
        repr(
            (
                document.digest,
                events[-1]["seq"] if events else 0,
                data["revision"],
                layer["fingerprint"],
                versions,
            )
        ).encode()
    ).hexdigest()[:16]
    reading = (
        files_reading
        + "."
        + presence_fingerprint(
            present["listening"], present["session_alive"], list(others)
        )
    )
    return PageSnapshot(
        document=document,
        active=snapshot_active,
        events=events,
        registry=registry,
        layer=layer,
        data=data,
        browser_data=browser_data,
        versions=versions,
        documents=documents,
        revision_names=revision_names,
        presence=copy.deepcopy(present),
        live_stream=copy.deepcopy(live_stream),
        others=others,
        now=observed_at,
        taken=taken,
        reading=reading,
    )
