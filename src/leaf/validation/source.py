"""Static checks for the mutable source document."""

from pathlib import Path
from typing import NamedTuple

from leaf.data import read_contracts, read_data
from leaf.data_contracts import (
    data_document_errors,
    data_document_readings,
    initial_data_document_readings,
    measurement_lag,
)
from leaf.findings import Finding, Rejected
from leaf.passages import SourceReading
from leaf.registry.contract import RegistryError
from leaf.registry.storage import IncompatibleLayer, read_page_registry
from leaf.revision_artifact import (
    ArtifactError,
    RevisionArtifact,
    capture_artifact,
    css_drops,
    document_drops,
    page_files,
    resource_type,
)
from leaf.sample_content import initial_sample_events
from leaf.structure import SourceDocument
from leaf.thread_context import thread_ids, thread_names, thread_structure
from leaf.validation.instances import (
    instance_errors,
    reference_errors,
    suggestion_errors,
)
from leaf.validation.markup import (
    authored_allocation_errors,
    document_declaration_errors,
    id_errors,
    page_boundary_errors,
    structure_errors,
    unanswered_media,
    unpointable_blocks,
)
from leaf.validation.source_history import (
    EMPTY_READING,
    NO_PREDECESSOR,
    PredecessorReading,
    predecessor_reading,
    revision_reanchors,
)


class SourceCheck(NamedTuple):
    """One complete reading of the exact source bytes.

    `reading` is the document under `registry` (none where the page has no
    vocabulary), read once for the whole check; the revision activation writes from
    it adopts it (`revision_artifact.write_artifact`). `errors` holds what refuses
    the source and `notes` what the check found at a lesser severity, which
    `source_advice` reports. `advice` names the threads the revision would
    relocate; `source_advice` reads the source's other drift."""

    reading: SourceReading
    registry: dict | None
    errors: list[Finding]
    advice: list[Finding]
    artifact: RevisionArtifact | None = None
    reanchors: dict | None = None
    revision: PredecessorReading = NO_PREDECESSOR
    notes: tuple[Finding, ...] = ()

    @property
    def document(self) -> SourceDocument:
        return self.reading.document


def _source_bytes(page_dir: Path) -> tuple[bytes, Finding | None]:
    path = page_dir / "index.html"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return b"", Finding("no-source", values={"path": str(path)})
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        return data, Finding(
            "not-utf8", values={"path": str(path), "error": str(error)}
        )
    return data, None


def _document_errors(page_dir: Path, parser) -> list[Finding]:
    """Validate the authored document shell before reading its vocabulary."""
    errors = structure_errors(parser)
    errors.extend(page_boundary_errors(parser))
    errors.extend(authored_allocation_errors(parser))

    errors.extend(document_declaration_errors(parser))

    errors.extend(id_errors(parser))
    return errors


def _instance_errors(
    events: list,
    parser,
    registry: dict | None,
    thread_ids: set[str],
) -> list[Finding]:
    """Validate authored instances against their document's event and id namespace."""
    if registry is None:
        return []
    errors = instance_errors(parser, registry)
    errors.extend(
        reference_errors(
            parser.lf_elements,
            registry,
            parser.ids,
            parser.by_id,
            thread_ids=thread_ids,
        )
    )
    errors.extend(suggestion_errors(parser.lf_elements, registry))
    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(Finding("ids-taken-by-messages", values={"ids": taken}))
    return errors


def _authored_document_checks(
    page_dir, document, events, registry, readings, thread_ids
):
    """The same authored-page gate for the root and each isolated child document.

    The stylesheets a document's delivery rewrites, its children's among them, and
    the files it names are read once for the whole document: by the capture
    (`revision_artifact.capture_artifact`) and `check_source`'s `document_drops`,
    or for a message no capture reads, by its gate (`admission`)."""
    errors = _document_errors(page_dir, document)
    errors.extend(_instance_errors(events, document, registry, thread_ids))
    if registry is not None:
        errors.extend(data_document_errors(readings))
    return errors


def sample_errors(
    page_dir: Path,
    parent: SourceDocument,
    events: list,
    holder: SourceDocument,
    registry: dict | None,
    contracts: dict,
) -> list[Finding]:
    """Check each live sample `holder` declares as allocation would build it.

    `holder` is `parent` for a page's own templates, or a message in `events`, the
    log of `parent`. Each child is checked as a page against its initial history,
    and then the samples it declares in turn."""
    errors = []
    pending = [(parent, events, holder, ())]
    for document, document_events, declaring, outer in pending:
        for sample in declaring.samples:
            samples = (*outer, sample["attrs"].get("id"))
            child = sample["document"]
            selected = set(sample["attrs"].get("data-sample-threads", "").split())
            # A template may precede its seed log, and the selection reads against
            # whatever the log holds — so the child checked here is the child
            # allocation would build from this document and this history.
            try:
                child_events = (
                    initial_sample_events(
                        page_dir,
                        document,
                        document_events,
                        declaring,
                        sample,
                        registry,
                        contracts,
                    )
                    if registry is not None
                    else []
                )
            except Rejected as error:
                errors.extend(found.but(samples=samples) for found in error.findings)
                child_events = []
            pending.append((child, child_events, child, samples))
            child_readings = initial_data_document_readings(
                child, child_events, registry or {}
            )
            child_errors = _authored_document_checks(
                page_dir,
                child,
                child_events,
                registry,
                child_readings,
                selected | thread_ids(child_events),
            )
            errors.extend(error.but(samples=samples) for error in child_errors)
    return errors


def uncaptured_sample_errors(page_dir: Path, holder: SourceDocument) -> list[Finding]:
    """Each /media/ file the page won't answer that an attribute names in a live
    sample child of the message `holder`, or a child of one, which the message's own
    reading leaves out. Its stylesheets, those in its samples included, the message
    gate reads whole (`revision_artifact.uncaptured_errors`). A page's own children
    are captured with it; no capture reads a message."""
    errors = []
    pending = [(holder, ())]
    for declaring, outer in pending:
        for sample in declaring.samples:
            samples = (*outer, sample["attrs"].get("id"))
            pending.append((sample["document"], samples))
            errors.extend(
                error.but(samples=samples)
                for error in unanswered_media(
                    sample["document"].authoring.media_refs, page_dir
                )
            )
    return errors


def _page_file_drops(page_dir: Path) -> list[Finding]:
    """Each declaration or rule a browser drops from a stylesheet under `page/`
    (`revision_artifact.css_drops`), as the document's own sheets get from
    `check_source`. What delivery's reader can't read in one, or a file that isn't
    UTF-8, the capture refuses."""
    found = []
    for path in page_files(page_dir):
        if resource_type(path) != "text/css":
            continue
        try:
            css = (page_dir / path.lstrip("/")).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found.extend(css_drops(css, path))
    return found


def moved_threads(
    page_dir: Path, events: list, after: int, checked: SourceCheck
) -> list[Finding]:
    """The open threads that revisions after `after` moved and that still stand
    where the move put them.

    The server activates a valid save before anyone checks it, writing a `reanchor`
    event for each thread the revision moved, so the moves are read from the log;
    the moves activating `checked` would make (`checked.advice`) take their
    thread's place. A reply that has since placed the thread itself, resolving it,
    or taking back the reaction that opened it leaves the move out. `page check` asks for the moves at the active revision,
    and the first reply on a revision (`thread._revision_advice`) for those since
    the agent's last reply."""
    from leaf.events import build_threads
    from leaf.revision_artifact import active_enclosing

    pending = {finding.values["thread"]: finding for finding in checked.advice}
    names = thread_names(events)
    placed = {}
    for event in events:
        if event["kind"] == "reanchor":
            placed[event["thread"]] = event
        elif event["kind"] == "reply" and "anchor" in event:
            placed[names[event["parent"]]] = event
    threads = build_threads(events, active_enclosing(page_dir))
    recorded = [
        Finding(
            "relocated-anchor",
            values={
                "thread": thread,
                "section": (event["anchor"] or {}).get("section"),
            },
            severity="advice",
        )
        for thread, event in placed.items()
        if event["kind"] == "reanchor"
        and event["revision"] > after
        and thread not in pending
        and thread in threads
        and not threads[thread]["resolved"]
    ]
    return [*recorded, *pending.values()]


def source_advice(page_dir: Path, checked: SourceCheck) -> list[Finding]:
    """The source's non-blocking drift, which `page check` and the first reply on
    a revision (`thread._revision_advice`) report beside what `check_source` found.
    It is read apart from the check, which every reply and activation runs, because
    judging the page's recorded data can take a cold process about 200 ms on a large
    page."""
    parser = checked.document
    stored_data = read_data(page_dir, checked.registry)
    return [
        *checked.notes,
        *measurement_lag(parser.lf_elements, checked.registry or {}, stored_data),
        *(
            Finding(
                "unreadable-data",
                values={"source": source, "error": reading["error"]},
                severity="advice",
            )
            for source, reading in stored_data["sources"].items()
            if "error" in reading
        ),
        *unpointable_blocks(parser),
    ]


def check_source(page_dir: Path, events: list) -> SourceCheck:
    """Validate current source declarations and derive automatic anchor moves.

    Each finding's severity decides whether it refuses the source (`errors`) or is
    reported beside it (`notes`)."""
    data, source_error = _source_bytes(page_dir)
    if source_error:
        return SourceCheck(EMPTY_READING, None, [source_error], [])
    html = data.decode("utf-8")
    document = SourceDocument(html)
    errors = []
    page_registry = None
    try:
        page_registry = read_page_registry(page_dir)
        registry = page_registry.registry if page_registry is not None else None
        if page_registry is None:
            errors.append(Finding("no-layer", values={"page": str(page_dir)}))
    except IncompatibleLayer as error:
        return SourceCheck(
            SourceReading(document, None), None, list(error.findings), []
        )
    except RegistryError as error:
        registry = None
        errors.extend(error.findings)
    reading = SourceReading(document, registry)
    contracts = read_contracts(page_dir)
    # A conflicting binding lies within one document, and history holds none
    # (`data_contracts.data_binding_errors`), so the check reads this one alone.
    readings = (
        data_document_readings(document, "index.html", registry)
        if registry is not None
        else []
    )
    document_errors = _authored_document_checks(
        page_dir,
        document,
        events,
        registry,
        readings,
        thread_ids(events),
    )
    errors.extend(document_errors)
    errors.extend(
        sample_errors(page_dir, document, events, document, registry, contracts)
    )
    # The capture reads the document and the files it names whatever the markup
    # holds, so one check reports both; it needs only the vocabulary. Each problem
    # has one of the two as its owner (`_authored_document_checks`), and a source
    # with errors keeps no capture.
    artifact = None
    if registry is not None:
        assert page_registry is not None
        try:
            artifact = capture_artifact(
                page_dir,
                document,
                registry,
                declaration_sources=page_registry.declaration_sources,
                widget_sources=page_registry.widget_sources,
            )
        except ArtifactError as error:
            errors.extend(error.findings)
    errors.extend(document_drops(document))
    errors.extend(_page_file_drops(page_dir))
    notes = tuple(error for error in errors if error.severity != "error")
    errors = [error for error in errors if error.severity == "error"]
    if errors:
        artifact = None
    revision = predecessor_reading(page_dir, data, events, artifact)
    reanchors, advice = revision_reanchors(
        events, reading, revision, candidate_revision=revision.candidate
    )
    return SourceCheck(
        reading, registry, errors, advice, artifact, reanchors, revision, notes
    )
