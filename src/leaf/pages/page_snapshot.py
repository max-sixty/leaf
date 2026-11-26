"""One frozen input for browser validation and export previews."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path

from leaf.agents.presence import presence_fingerprint, presence_with_activity
from leaf.base.files import (
    document_descriptor,
    list_revisions,
    revision_path,
    version_descriptors,
)
from leaf.base.state import now_iso
from leaf.records.transaction import PageTransaction
from leaf.serving.drafts import no_drafts
from leaf.serving.served_state.context import PageRead
from leaf.source.data import read_data
from leaf.source.data_contracts import resource_urls
from leaf.source.layer import served_layer
from leaf.source.page_inputs import join_reading
from leaf.source.reading import SourceReading
from leaf.source.revision_artifact import (
    Resource,
    RevisionArtifact,
    artifact_name,
    capture_artifact,
    capture_local_resource,
    read_artifact,
    read_revision,
)
from leaf.source.runtime_selection import executing
from leaf.source.structure import SourceDocument
from leaf.source.vocabulary import read_page_registry


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
    reading: str
    source_error: str | None = None
    # The drafts its taker froze with it. A browser check or an export is no reading
    # of what the user is writing, so it holds none; leaf.page's saved answers hold
    # those its replacement container restores (`leaf_website.storage`).
    frozen_drafts: dict = field(default_factory=no_drafts)

    # A capture answers what a page server asks of its page
    # (`served_state.service.PageSource`), from what it froze, and takes no writes.
    writable = False

    def through(self, sequence: int) -> PageSnapshot:
        """This snapshot served as the page stood once event `sequence` was appended
        (`PageRead.through`)."""
        return replace(self, context=self.context.through(sequence))

    def active_revision(self) -> int:
        assert self.context.active is not None
        return self.context.active["revision"]

    def artifact(self, revision: int) -> RevisionArtifact:
        return self.artifacts[revision]

    def revision(self, revision: int) -> SourceReading:
        return self.context.revision(revision)

    def events(self) -> list[dict]:
        return list(self.context.events)

    def published_versions(self, events: list[dict]) -> set[int]:
        return {item["version"] for item in self.context.versions}

    def served_document(self) -> tuple[RevisionArtifact, int, int | None]:
        active = self.context.active
        assert active is not None
        return self.artifacts[active["revision"]], active["revision"], active["version"]

    def sample_inputs(self, revision: int) -> tuple[RevisionArtifact, list, dict]:
        return self.artifacts[revision], list(self.context.events), self.context.data

    def news(self) -> str:
        return self.reading

    def drafts(self) -> dict:
        return self.frozen_drafts

    def other_pages(self) -> list[dict]:
        # A capture shows its page alone: what it reads is the page's, frozen.
        return []

    @contextmanager
    def state_read(self) -> Generator[tuple[PageRead, str, str | None]]:
        yield self.context, self.reading, self.source_error

    def state_reading(self, reading: str, state: dict) -> str:
        # A frozen reading cannot advance on its clock. Refresh is driven by
        # a successor publication, never a deadline within this same input.
        state["activity"]["next_transition_at"] = None
        return reading


def capture_page_snapshot(
    page_dir: Path,
    document: SourceDocument,
    revision: int,
    *,
    url: str,
    artifact: RevisionArtifact | None = None,
    transaction: PageTransaction | None = None,
    process: bool = True,
    log: list[dict] | None = None,
    data: dict | None = None,
) -> PageSnapshot:
    """Freeze a candidate and every page authority it is projected against.

    The log, the revisions it can name, the stored data and the page's presence are
    read together under the page's append lease, which every gesture waits for. A
    host publishing from an existing transition lends its held transaction. Other
    callers take the lease for those reads alone, so a capture holds up a gesture
    only while it reads them (root `AGENTS.md`, "Responsiveness"). The capture
    executes the candidate before it takes the lease, since that reads nothing of
    the log, and each listed revision after it releases the lease, since a revision
    never changes once its marker is listed (`revision_artifact`).

    `log` and `data` are the part of the page's log and stored data to freeze in
    place of all of them, which every reading of the capture folds from
    (`exporting`).
    """
    if artifact is not None and artifact.html != document.data:
        raise ValueError("preview artifact does not contain the checked document")
    # The server delivering the snapshot supplies its runtime and this Leaf's
    # probes beside it (`runtime_selection`), so the probes call the runtime
    # they were written against, whichever Leaf captured the revision.
    selected = executing(artifact or _artifact_of(page_dir, document, revision))
    registry = copy.deepcopy(selected.registry)
    with (
        nullcontext(transaction)
        if transaction is not None
        else PageTransaction(page_dir) as page
    ):
        events = tuple(copy.deepcopy(page.events if log is None else log))
        revisions = list_revisions(page_dir)
        versions = tuple(copy.deepcopy(version_descriptors(list(events), revisions)))
        data = read_data(page_dir, registry) if data is None else data
        present, live_stream = presence_with_activity(
            page_dir, list(events), process=process
        )
        observed_at = now_iso()
        taken = time.time()
    artifacts: dict[int, RevisionArtifact] = {
        number: executing(read_artifact(page_dir, number)) for number in revisions
    }
    artifacts[revision] = selected
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
    layer = served_layer(registry["$layer"], page_dir)
    # Stored revisions take their held readings; a candidate the snapshot
    # captured is the checked document under its capture's vocabulary.
    stored_readings = {
        revision: read_revision(page_dir, revision) for revision in revisions
    }
    shown = stored_readings.get(revision)
    readings: dict[int, SourceReading] = dict(stored_readings)
    if shown is None or shown.digest != selected.digest:
        readings[revision] = SourceReading(document, selected.registry)
    # Read at capture, so a snapshot serves what it froze even if the page
    # directory later moves or goes away.
    for reading in readings.values():
        _ = (reading.document, reading.registry)
    # So does the layer each one is served under, which names the page's own
    # package copies (`vendoring`).
    layers = {
        _layer_key(metadata): served_layer(metadata, page_dir)
        for metadata in (reading.registry["$layer"] for reading in readings.values())
    }
    revision_names = {
        revision: revision_path(page_dir, revision).name for revision in revisions
    }
    revision_names[revision] = artifact_name(revision, selected) + ".html"
    snapshot_active = document_descriptor(
        revision,
        list(events),
        url=url,
        executable=selected.executable,
        activated_at=(
            shown.activated_at
            if shown is not None and shown.digest == selected.digest
            else observed_at
        ),
    )
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
    reading = join_reading(files_reading, presence_fingerprint(present))
    return PageSnapshot(
        context=PageRead(
            active=snapshot_active,
            events=list(events),
            revisions=frozenset(readings),
            revision=readings.__getitem__,
            registry=registry,
            stored_layer=lambda: layer,
            serve_layer=lambda metadata: layers[_layer_key(metadata)],
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
        reading=reading,
    )


def _artifact_of(
    page_dir: Path, document: SourceDocument, revision: int
) -> RevisionArtifact:
    """`revision`'s stored artifact where it holds `document`, or else `document`
    captured under the page's current layer."""
    if revision in list_revisions(page_dir):
        stored = read_artifact(page_dir, revision)
        if stored.html == document.data:
            return stored
    page_registry = read_page_registry(page_dir)
    if page_registry is None:
        raise ValueError(f"no registry.json in {page_dir}; run `leaf page init` first")
    return capture_artifact(
        page_dir,
        document,
        page_registry.registry,
        declaration_sources=page_registry.declaration_sources,
        widget_sources=page_registry.widget_sources,
    )


def _layer_key(metadata: dict) -> str:
    return json.dumps(metadata, sort_keys=True)
