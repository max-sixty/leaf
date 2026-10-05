"""One frozen input for browser validation and export previews."""

import copy
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from .data import read_data
from .data_contracts import resource_urls
from .files import (
    list_revisions,
    revision_label,
    revision_path,
    version_descriptors,
)
from .passages import SourceReading
from .presence import other_leaves, presence_fingerprint, presence_with_activity
from .registry.storage import read_page_registry
from .revision_artifact import (
    Resource,
    RevisionArtifact,
    artifact_name,
    capture_artifact,
    capture_local_resource,
    read_artifact,
    read_revision,
)
from .served_state.context import PageRead
from .served_state.reading import join_reading
from .service import PageTransaction
from .state import now_iso
from .structure import SourceDocument


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """The exact page facts an ephemeral browser server may expose.

    Everything it serves is read at capture: each revision's reading has its
    document and registry in hand, so a later request reads nothing from the page
    directory for them. Declared data media is frozen beside its current value;
    it never changes an immutable authored revision's artifact."""

    context: PageRead
    artifacts: dict[int, RevisionArtifact]
    data_resources: dict[str, Resource]
    revision_names: dict[int, str]
    others: tuple[dict, ...]
    reading: str


def capture_page_snapshot(
    page_dir: Path,
    document: SourceDocument,
    active: dict,
    *,
    artifact: RevisionArtifact | None = None,
) -> PageSnapshot:
    """Freeze a candidate and every page authority it is projected against."""
    if artifact is not None and artifact.html != document.data:
        raise ValueError("preview artifact does not contain the checked document")
    with PageTransaction(page_dir) as page:
        events = tuple(copy.deepcopy(page.events))
        snapshot_active = copy.deepcopy(active)
        versions = tuple(copy.deepcopy(version_descriptors(page_dir, list(events))))
        revisions = list_revisions(page_dir)
        artifacts = {
            revision: read_artifact(page_dir, revision) for revision in revisions
        }
        selected = artifact or artifacts.get(active["revision"])
        if selected is None or selected.html != document.data:
            page_registry = read_page_registry(page_dir)
            if page_registry is None:
                raise ValueError(
                    f"no registry.json in {page_dir}; run `leaf page init` first"
                )
            selected = capture_artifact(
                page_dir,
                document,
                page_registry.registry,
                declaration_sources=page_registry.declaration_sources,
                widget_sources=page_registry.widget_sources,
            )
        artifacts[active["revision"]] = selected
        registry = copy.deepcopy(selected.registry)
        data = read_data(page_dir, registry)
        # External data remains current even in a historical document. Its media
        # belongs to this frozen reading, not the immutable authored revision.
        data_urls = {
            url
            for source in data["sources"].values()
            if "value" in source
            for url in resource_urls(
                source["value"], registry["$data"]["contracts"][source["contract"]]
            )
            if url.startswith("/media/")
        }
        data_resources = {
            url: capture_local_resource(page_dir, url) for url in sorted(data_urls)
        }
        layer = copy.deepcopy(registry["$layer"])
        # Stored revisions take their held readings; a candidate the snapshot
        # captured is the checked document under its capture's vocabulary.
        readings = {
            revision: read_revision(page_dir, revision) for revision in revisions
        }
        shown = readings.get(active["revision"])
        if shown is None or shown.digest != selected.digest:
            readings[active["revision"]] = SourceReading(document, selected.registry)
        # Read inside the transaction, so a snapshot serves what it froze even if
        # the page directory later moves or goes away.
        for reading in readings.values():
            _ = (reading.document, reading.registry)
        revision_names = {
            revision: revision_path(page_dir, revision).name for revision in revisions
        }
        revision_names[active["revision"]] = (
            artifact_name(active["revision"], artifacts[active["revision"]]) + ".html"
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
        # A preview serves the frozen candidate, not whatever the page directory
        # holds, so its executable identity is that capture's rather than the live
        # revision's.
        snapshot_active["executable"] = artifacts[active["revision"]].executable
        taken = time.time()
    files_reading = hashlib.sha256(
        repr(
            (
                document.digest,
                events[-1]["seq"] if events else 0,
                data["version"],
                layer["fingerprint"],
                versions,
            )
        ).encode()
    ).hexdigest()[:16]
    reading = join_reading(files_reading, presence_fingerprint(present, list(others)))
    return PageSnapshot(
        context=PageRead(
            active=snapshot_active,
            events=list(events),
            revisions=frozenset(readings),
            revision=readings.__getitem__,
            registry=registry,
            layer=layer,
            stored_data=lambda: data,
            versions=versions,
            presence=copy.deepcopy(present),
            live_stream=copy.deepcopy(live_stream),
            now=observed_at,
            taken=taken,
        ),
        artifacts=artifacts,
        data_resources=data_resources,
        revision_names=revision_names,
        others=others,
        reading=reading,
    )
