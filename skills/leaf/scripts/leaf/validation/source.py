"""Static checks for the mutable source document."""

from pathlib import Path
from typing import NamedTuple

from leaf.data import read_contracts, read_data
from leaf.data_contracts import (
    data_document_errors,
    initial_data_document_readings,
    measurement_lag,
    working_data_document_readings,
)
from leaf.findings import Finding
from leaf.passages import SourceReading
from leaf.registry.contract import RegistryError
from leaf.registry.storage import read_page_registry
from leaf.revision_artifact import ArtifactError, RevisionArtifact, capture_artifact
from leaf.sample_content import initial_sample_events
from leaf.schema import VENDORED_FILES
from leaf.structure import LF_META, SourceDocument, script_kind
from leaf.styles import (
    css_syntax_errors,
    inline_style_at,
)
from leaf.thread_context import thread_ids, thread_structure
from leaf.validation.instances import (
    instance_errors,
    reference_errors,
    suggestion_errors,
)
from leaf.validation.markup import (
    authored_allocation_errors,
    document_declaration_errors,
    id_errors,
    media_errors,
    page_boundary_errors,
    structure_errors,
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
    it adopts it (`revision_artifact.write_artifact`)."""

    reading: SourceReading
    registry: dict | None
    errors: list[Finding]
    advice: list[Finding]
    artifact: RevisionArtifact | None = None
    reanchors: dict | None = None
    revision: PredecessorReading = NO_PREDECESSOR

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
    errors = [
        Finding("missing-vendored", values={"file": name})
        for name in VENDORED_FILES
        if not (page_dir / name).exists()
    ]

    errors.extend(structure_errors(parser))
    errors.extend(page_boundary_errors(parser))
    errors.extend(authored_allocation_errors(parser))

    # A page's scripts are its author's, of any kind, so long as each runs after Leaf
    # has read the page: the runtime holds the authored main as the page's baseline and
    # listens for errors from the moment its module runs, and a deferred script or a
    # module runs after it, in document order. A parser-blocking or async script can
    # run first, changing what Leaf reads as authored and throwing where no check
    # hears it.
    for script in [*parser.inline_scripts, *parser.external_scripts]:
        attrs = script["attrs"]
        kind = script_kind(attrs)
        if kind not in {"module", "classic"}:
            continue
        if "async" in attrs:
            errors.append(Finding("async-script", "<script>", {"line": script["line"]}))
        elif kind == "classic" and not ("src" in attrs and "defer" in attrs):
            errors.append(
                Finding("parser-blocking-script", "<script>", {"line": script["line"]})
            )

    errors.extend(document_declaration_errors(parser))

    for meta in parser.named_metas:
        if not meta["name"].startswith("lf-"):
            continue  # ordinary document metadata: a title, a description, a card
        where = {"name": meta["name"], "line": meta["line"]}
        if meta["name"] not in LF_META:
            errors.append(
                Finding("unknown-meta", "<meta>", {**where, "known": sorted(LF_META)})
            )
            continue
        allowed = LF_META[meta["name"]]
        if allowed is not None and meta["content"] not in allowed:
            errors.append(
                Finding(
                    "meta-content",
                    "<meta>",
                    {**where, "allowed": sorted(allowed), "found": meta["content"]},
                )
            )

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
    errors = instance_errors(parser.lf_elements, registry)
    errors.extend(
        reference_errors(parser.lf_elements, registry, parser.ids, parser.by_id)
    )
    errors.extend(suggestion_errors(parser.lf_elements, registry, thread_ids))
    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(Finding("ids-taken-by-messages", values={"ids": taken}))
    return errors


def _authored_document_checks(
    page_dir, document, events, registry, readings, thread_ids
):
    """The same authored-page gate for the root and each isolated child document."""
    errors = _document_errors(page_dir, document)
    errors.extend(_instance_errors(events, document, registry, thread_ids))
    if registry is not None:
        errors.extend(data_document_errors(readings))
    errors.extend(media_errors(document, page_dir))
    errors.extend(_presentation_errors(document))
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
            except ValueError as error:
                errors.append(
                    Finding(
                        "sample-history", values={"error": str(error)}, samples=samples
                    )
                )
                child_events = []
            pending.append((child, child_events, child, samples))
            child_readings = initial_data_document_readings(
                child, child_events, registry
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


def _presentation_errors(parser) -> list[Finding]:
    """Validate the page's own CSS: its <style> and each inline style."""
    errors = list(css_syntax_errors(parser.css, "page <style>"))
    for inline in parser.inline_styles:
        errors.extend(
            css_syntax_errors(inline["style"], inline_style_at(inline), block=True)
        )
    return errors


def _source_advice(
    parser,
    registry: dict | None,
    stored_data: dict,
    revision: PredecessorReading,
    dropped_ids: list[str],
) -> list[Finding]:
    """Report non-blocking drift after every error-producing phase has run."""
    return [
        *(
            [
                Finding(
                    "dropped-ids",
                    values={"revision": revision.predecessor, "ids": dropped_ids},
                    severity="advice",
                )
            ]
            if dropped_ids
            else []
        ),
        *measurement_lag(parser.lf_elements, registry or {}, stored_data),
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
    """Validate current source declarations and derive automatic anchor moves."""
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
    except RegistryError as error:
        registry = None
        errors.extend(error.findings)
    reading = SourceReading(document, registry)
    stored_data = read_data(page_dir, registry)
    contracts = read_contracts(page_dir)
    readings = (
        working_data_document_readings(page_dir, registry, events, authored=document)
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
    artifact = None
    if not errors and registry is not None:
        try:
            artifact = capture_artifact(
                page_dir,
                document,
                registry,
                declaration_sources=page_registry.declaration_sources,
                widget_sources=page_registry.widget_sources,
            )
        except ArtifactError as error:
            errors.append(Finding("capture-failed", values={"error": str(error)}))
    revision = predecessor_reading(page_dir, data, events, artifact)

    dropped_advice = sorted(revision.previous.document.ids - document.ids)

    advice = _source_advice(
        document,
        registry,
        stored_data,
        revision,
        dropped_advice,
    )
    reanchors, anchor_advice = revision_reanchors(
        events, reading, revision, candidate_revision=revision.candidate
    )
    advice.extend(anchor_advice)
    return SourceCheck(reading, registry, errors, advice, artifact, reanchors, revision)
