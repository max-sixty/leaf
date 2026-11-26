"""Static checks for the mutable source document."""

from pathlib import Path
from typing import NamedTuple

from leaf.base.findings import Finding
from leaf.log.events import build_threads
from leaf.log.thread_context import placed_thread, thread_ids, thread_names
from leaf.records.authored_checks.documents import (
    authored_document_checks,
    sample_errors,
)
from leaf.records.authored_checks.source_history import (
    EMPTY_READING,
    NO_PREDECESSOR,
    PredecessorReading,
    predecessor_reading,
    revision_reanchors,
)
from leaf.records.markup_checks.markup import unpointable_blocks
from leaf.source.capture_refusals import ArtifactError
from leaf.source.data import bound_file_conflicts, read_contracts, read_data
from leaf.source.data_contracts import measurement_lag
from leaf.source.layer import other_serving_leaf
from leaf.source.reading import SourceReading
from leaf.source.registry.contract import RegistryError
from leaf.source.registry.storage import IncompatibleLayer
from leaf.source.revision_artifact import (
    RevisionArtifact,
    active_enclosing,
    capture_artifact,
    document_drops,
    page_files,
    resource_type,
)
from leaf.source.structure import SourceDocument
from leaf.source.styles import css_drops
from leaf.source.vocabulary import read_page_registry


class SourceCheck(NamedTuple):
    """One complete reading of the exact source bytes.

    `reading` is the document under `registry` (none where the page has no
    vocabulary), read once for the whole check; the revision activation writes from
    it adopts it (`revision_artifact.write_artifact`). `declarations` are the page's
    own, which `registry` composes over its layer. `errors` holds what refuses the
    source and `notes` what the check advises, which `source_advice` reports.
    `advice` names the threads the revision would relocate; `source_advice` reads the
    source's other drift."""

    reading: SourceReading
    registry: dict | None
    errors: list[Finding]
    advice: list[Finding]
    artifact: RevisionArtifact | None = None
    reanchors: dict | None = None
    revision: PredecessorReading = NO_PREDECESSOR
    notes: tuple[Finding, ...] = ()
    declarations: dict | None = None

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


def _page_file_drops(page_dir: Path) -> list[Finding]:
    """Each declaration or rule a browser drops from a stylesheet under `page/`
    (`styles.css_drops`), as the document's own sheets get from
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
    pending = {finding.values["thread"]: finding for finding in checked.advice}
    names = thread_names(events)
    placed = {}
    for event in events:
        if event["kind"] != "comment" and (thread := placed_thread(event, names)):
            placed[thread] = event
    threads = build_threads(events, active_enclosing(page_dir))
    recorded = [
        Finding(
            "relocated-anchor",
            values={
                "thread": thread,
                "section": (event["anchor"] or {}).get("section"),
            },
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
    """What `page check` and the first reply on a revision
    (`thread._revision_advice`) advise beside what `check_source` found: the
    source's non-blocking drift, what the page's own declarations advise
    (`declarations.declaration_advice`), and a live server running another Leaf
    (`layer.other_serving_leaf`). It is read apart from the check, which every
    reply and activation runs, because judging the page's recorded data can take a
    cold process about 200 ms on a large page."""
    from leaf.records.authored_checks.declarations import declaration_advice

    parser = checked.document
    stored_data = read_data(page_dir, checked.registry)
    served = other_serving_leaf(page_dir)
    return [
        *checked.notes,
        *(
            declaration_advice(
                checked.declarations,
                checked.registry,
                page_dir / "page" / "registry.json",
            )
            if checked.registry is not None and checked.declarations
            else ()
        ),
        *measurement_lag(parser.lf_elements, checked.registry or {}, stored_data),
        *(
            Finding(
                "unreadable-data",
                values={"source": source, "error": reading["error"]},
            )
            for source, reading in stored_data["sources"].items()
            if "error" in reading
        ),
        *unpointable_blocks(parser),
        *(
            [
                Finding(
                    "another-leaf-serving",
                    values={
                        "page": str(page_dir),
                        "path": served.get("path"),
                        "commit": served.get("commit"),
                    },
                )
            ]
            if served is not None
            else []
        ),
    ]


def check_source(page_dir: Path, events: list) -> SourceCheck:
    """Validate current source declarations and derive automatic anchor moves.

    Each finding's code decides whether it refuses the source (`errors`) or is
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
    document_errors = authored_document_checks(
        document,
        events,
        registry,
        thread_ids(events),
    )
    errors.extend(document_errors)
    errors.extend(
        sample_errors(page_dir, document, events, document, registry, contracts)
    )
    if registry is not None:
        errors.extend(bound_file_conflicts(page_dir, document.lf_elements, registry))
    # The capture reads the document and the files it names whatever the markup
    # holds, so one check reports both; it needs only the vocabulary. Each problem
    # has one of the two as its owner (`documents.authored_document_checks`), and a
    # source with errors keeps no capture.
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
    notes = tuple(error for error in errors if not error.refuses)
    errors = [error for error in errors if error.refuses]
    if errors:
        artifact = None
    revision = predecessor_reading(page_dir, data, events, artifact)
    reanchors, advice = revision_reanchors(
        events, reading, revision, candidate_revision=revision.candidate
    )
    return SourceCheck(
        reading,
        registry,
        errors,
        advice,
        artifact,
        reanchors,
        revision,
        notes,
        page_registry.declarations if page_registry is not None else None,
    )
