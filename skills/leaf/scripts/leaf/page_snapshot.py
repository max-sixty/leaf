"""One frozen input for browser validation and export previews."""

from __future__ import annotations

import copy
import hashlib
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from .data import read_data
from .data_contracts import resource_urls
from .files import (
    document_descriptor,
    list_revisions,
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
    probe_resources,
    read_artifact,
    read_revision,
)
from .served_state.context import PageRead
from .served_state.reading import join_reading
from .service import PageTransaction
from .state import now_iso
from .structure import SourceDocument
from .user_views import FRESH_FOR_S


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

    # A capture answers what a page server asks of its page
    # (`served_state.service.PageSource`), from what it froze, and takes no writes.
    writable = False

    def through(self, sequence: int) -> PageSnapshot:
        """This snapshot served as the page stood once event `sequence` was appended
        (`PageRead.through`)."""
        return replace(self, context=self.context.through(sequence))

    def active_revision(self) -> int:
        return self.context.active["revision"]

    def artifact(self, revision: int) -> RevisionArtifact:
        return self.artifacts[revision]

    def revision(self, revision: int) -> SourceReading:
        return self.context.revision(revision)

    def active_registry(self) -> dict:
        return self.context.registry

    def data_source(self, source: str, registry: dict) -> dict | None:
        return self.context.data["sources"].get(source)

    def events(self) -> list[dict]:
        return list(self.context.events)

    def published_versions(self, events: list[dict]) -> set[int]:
        return {item["version"] for item in self.context.versions}

    def served_document(self) -> tuple[RevisionArtifact, int, int | None]:
        active = self.context.active
        return self.artifacts[active["revision"]], active["revision"], active["version"]

    def sample_inputs(self, revision: int) -> tuple[RevisionArtifact, list, dict]:
        return self.artifacts[revision], list(self.context.events), self.context.data

    def user_views(self) -> dict:
        # Captured render previews are instruments, not the user's reading.
        return {"fresh_for_s": FRESH_FOR_S, "sessions": []}

    def news(self) -> str:
        return self.reading

    def other_pages(self) -> list[dict]:
        return list(self.others)

    @contextmanager
    def state_read(self, *, with_token: bool = False):
        yield self.context, self.reading, None

    def state_reading(self, reading: str, state: dict) -> str:
        return reading


def capture_page_snapshot(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    *,
    url: str,
    artifact: RevisionArtifact | None = None,
) -> PageSnapshot:
    """Freeze a candidate and every page authority it is projected against."""
    if artifact is not None and artifact.html != document.data:
        raise ValueError("preview artifact does not contain the checked document")
    with PageTransaction(page_dir) as page:
        events = tuple(copy.deepcopy(page.events))
        revisions = list_revisions(page_dir)
        versions = tuple(copy.deepcopy(version_descriptors(list(events), revisions)))
        artifacts = {
            revision: read_artifact(page_dir, revision) for revision in revisions
        }
        selected = artifact or artifacts.get(revision)
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
        # The snapshot's readers are this Leaf's probes, which call its runtime by
        # name, so it serves them whichever Leaf captured the revision; a runtime
        # lacking a name they import fails to link (`render_checks.ProbesUnlinked`).
        selected = replace(
            selected, resources={**selected.resources, **probe_resources()}
        )
        artifacts[revision] = selected
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
        shown = readings.get(revision)
        if shown is None or shown.digest != selected.digest:
            readings[revision] = SourceReading(document, selected.registry)
        # Read inside the transaction, so a snapshot serves what it froze even if
        # the page directory later moves or goes away.
        for reading in readings.values():
            _ = (reading.document, reading.registry)
        revision_names = {
            revision: revision_path(page_dir, revision).name for revision in revisions
        }
        revision_names[revision] = (
            artifact_name(revision, artifacts[revision]) + ".html"
        )
        present, live_stream = presence_with_activity(page_dir, list(events))
        others = tuple(copy.deepcopy(other_leaves(page_dir)))
        observed_at = now_iso()
        snapshot_active = document_descriptor(
            revision,
            list(events),
            url=url,
            executable=selected.executable,
            activated_at=observed_at,
        )
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
            stored_layer=lambda: layer,
            stored_data=lambda: data,
            bound_files=dict,
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
