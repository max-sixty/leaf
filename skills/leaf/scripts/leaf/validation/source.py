"""Static checks for the mutable source document."""

from pathlib import Path
from typing import NamedTuple

from leaf.data import empty_data, read_data
from leaf.data_contracts import (
    data_document_errors,
    initial_data_document_readings,
    measurement_lag,
    working_data_document_readings,
)
from leaf.registry.contract import RegistryError
from leaf.registry.storage import read_page_registry
from leaf.revision_artifact import ArtifactError, RevisionArtifact, capture_artifact
from leaf.schema import VENDORED_FILES
from leaf.structure import LF_META, SourceDocument, links_with_rel
from leaf.styles import (
    _column_width,
    _overwide_elements,
    css_syntax_errors,
    inline_presentation_override_errors,
    inline_style_at,
    root_tokens,
)
from leaf.thread_context import comment_ids, specimen_events, thread_structure
from leaf.validation.compatibility import candidate_vocabulary_gaps
from leaf.validation.instances import (
    addressable_instance_errors,
    ask_surface_errors,
    declared_word_errors,
    language_class_errors,
    layout_errors,
    line_ref_errors,
    reference_errors,
    request_offer_errors,
    suggestion_errors,
    visual_part_errors,
    widget_errors,
)
from leaf.validation.markup import (
    authored_width_errors,
    id_errors,
    media_errors,
    missing_outline,
    page_boundary_errors,
    structure_errors,
    unpointable_blocks,
)
from leaf.validation.source_history import (
    RevisionReading,
    continuity_errors,
    revision_reading,
    transition_errors,
    transition_reading,
)


class SourceCheck(NamedTuple):
    """One complete reading of the exact source bytes."""

    document: SourceDocument
    registry: dict | None
    projection: object
    spoken: dict
    predecessor: int
    errors: list[str]
    advice: list[str]
    column: int
    artifact: RevisionArtifact | None = None


def _source_bytes(page_dir: Path) -> tuple[bytes, str | None]:
    path = page_dir / "index.html"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return b"", f"no {path}; write index.html first"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        return data, f"{path} is not UTF-8: {error}"
    return data, None


def _document_errors(page_dir: Path, parser) -> list[str]:
    """Validate the authored document shell before reading its vocabulary."""
    errors = []
    for missing in [name for name in VENDORED_FILES if not (page_dir / name).exists()]:
        errors.append(
            f"{missing} missing from the page directory; run `leaf page init` "
            "to vendor the layer"
        )

    errors.extend(structure_errors(parser))
    errors.extend(page_boundary_errors(parser))
    errors.extend(authored_width_errors(parser))

    for script in parser.external_scripts:
        if (
            set(script["attrs"]) != {"type", "src"}
            or script["attrs"].get("type") != "module"
        ):
            errors.append(
                f"<script src> (line {script['line']}) must be an authored module "
                'with exactly type="module" and src'
            )

    for script in parser.inline_scripts:
        if script["attrs"] != {"type": "module"}:
            errors.append(
                f"<script> (line {script['line']}) must be an authored module "
                f'with exactly type="module"; found attributes {script["attrs"]}'
            )
    for executable in parser.executable_attributes:
        errors.append(
            f"<{executable['tag']}> (line {executable['line']}) uses executable "
            f"attribute {executable['name']}; put authored behavior in a "
            '<script type="module"> block'
        )

    stylesheets = links_with_rel(parser.links, "stylesheet")
    for stylesheet in stylesheets:
        if set(stylesheet["attrs"]) != {"rel", "href"}:
            errors.append(
                f"<link rel=stylesheet> (line {stylesheet['line']}) must have exactly rel and href"
            )

    for link in links_with_rel(parser.links, "canonical"):
        errors.append(
            f'<link rel="canonical"> (line {link["line"]}): the served document names '
            "the page root itself, and a page whose head declares a second address "
            "leaves a crawler to choose between them. Write the title and description; "
            "the address is delivery's."
        )

    declared_policies = [
        meta
        for meta in parser.http_equivs
        if meta["equiv"].lower() == "content-security-policy"
    ]
    for policy in declared_policies:
        errors.append(
            f"<meta http-equiv=Content-Security-Policy> (line {policy['line']}) "
            "belongs to delivery"
        )

    for encoding in parser.encoding_metas:
        errors.append(
            f"<meta charset> (line {encoding['line']}) belongs to delivery; "
            "Leaf declares UTF-8 before authored head content"
        )

    for meta in parser.named_metas:
        if not meta["name"].startswith("lf-"):
            continue  # ordinary document metadata: a title, a description, a card
        where = f'<meta name="{meta["name"]}"> (line {meta["line"]})'
        if meta["name"] not in LF_META:
            errors.append(f"{where}: unknown lf- meta; known: {sorted(LF_META)}")
            continue
        allowed = LF_META[meta["name"]]
        if allowed is not None and meta["content"] not in allowed:
            errors.append(
                f"{where}: content must be one of {sorted(allowed)}, "
                f"found {meta['content']!r}"
            )

    errors.extend(id_errors(parser))
    return errors


def _instance_errors(
    events: list,
    parser,
    registry: dict | None,
    comment_ids: set[str],
) -> list[str]:
    """Validate authored instances against their document's event and id namespace."""
    errors = []
    if registry is None:
        return errors
    errors.extend(widget_errors(parser.lf_elements, registry))
    errors.extend(layout_errors(parser.lf_elements, registry))
    errors.extend(visual_part_errors(parser.lf_elements, registry))
    errors.extend(addressable_instance_errors(parser.lf_elements, registry))
    errors.extend(ask_surface_errors(parser.lf_elements, registry))
    errors.extend(request_offer_errors(parser.lf_elements, registry))
    errors.extend(
        reference_errors(parser.lf_elements, registry, parser.ids, parser.by_id)
    )
    errors.extend(language_class_errors(parser.language_blocks, registry))
    errors.extend(declared_word_errors(parser.lf_elements, registry))
    errors.extend(line_ref_errors(parser.lf_elements, registry))
    errors.extend(suggestion_errors(parser.lf_elements, registry, comment_ids))
    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(f"ids already taken by widget markup in a reply: {taken}")
    return errors


def _authored_document_checks(
    page_dir, document, events, registry, stored, readings, comment_ids
):
    """The same authored-page gate for the root and each isolated child document."""
    errors = _document_errors(page_dir, document)
    errors.extend(_instance_errors(events, document, registry, comment_ids))
    if registry is not None:
        errors.extend(data_document_errors(readings, stored))
    errors.extend(media_errors(document, page_dir))
    column, presentation_errors = _presentation_errors(page_dir, document)
    errors.extend(presentation_errors)
    return column, errors


def _presentation_errors(page_dir: Path, parser) -> tuple[int, list[str]]:
    """Validate authored and vendored CSS and return the readable column width.

    Every sheet the page vendors is checked, not theme.css alone: shadow.css is the
    one each widget's shadow root adopts, so a malformed rule there reaches a reader
    as an unstyled widget with nothing said about it. The column and its tokens are
    the theme's, which is the sheet the document itself is laid out by.
    """
    vendored = {
        name: (page_dir / name).read_text(encoding="utf-8")
        if (page_dir / name).exists()
        else ""
        for name in VENDORED_FILES
        if name.endswith(".css")
    }
    theme_css = vendored["theme.css"]
    errors = list(css_syntax_errors(parser.css, "page <style>"))
    for inline in parser.inline_styles:
        errors.extend(
            css_syntax_errors(inline["style"], inline_style_at(inline), block=True)
        )
    for name, css in vendored.items():
        errors.extend(css_syntax_errors(css, name))
    errors.extend(inline_presentation_override_errors(parser))
    column = _column_width(parser.css, theme_css)
    errors.extend(_overwide_elements(parser, column, root_tokens(theme_css)))
    return column, errors


def _source_advice(
    parser,
    registry: dict | None,
    stored_data: dict,
    revision: RevisionReading,
    dropped_ids: list[str],
) -> list[str]:
    """Report non-blocking drift after every error-producing phase has run."""
    return [
        *(
            [f"ids dropped from revision r{revision.predecessor}: {dropped_ids}"]
            if dropped_ids
            else []
        ),
        *(
            f"measurement behind its source: {line}"
            for line in measurement_lag(
                parser.lf_elements,
                registry or {},
                stored_data,
            )
        ),
        *unpointable_blocks(parser),
        *missing_outline(parser, registry or {}),
    ]


def check_source(
    page_dir: Path,
    events: list,
    *,
    allow_transition: bool = True,
) -> SourceCheck:
    """Check ``index.html`` against the last activated revision."""
    data, source_error = _source_bytes(page_dir)
    if source_error:
        return SourceCheck(SourceDocument(""), None, None, {}, 0, [source_error], [], 0)
    html = data.decode("utf-8")
    document = SourceDocument(html)
    errors = []
    page_registry = None
    try:
        page_registry = read_page_registry(page_dir)
        registry = page_registry.registry if page_registry is not None else None
    except RegistryError as error:
        registry = None
        errors.append(str(error))
    stored_data = read_data(page_dir) if registry is not None else empty_data()
    readings = (
        working_data_document_readings(
            page_dir, registry, events, authored=document.lf_elements
        )
        if registry is not None
        else []
    )
    column, document_errors = _authored_document_checks(
        page_dir,
        document,
        events,
        registry,
        stored_data,
        readings,
        comment_ids(events),
    )
    errors.extend(document_errors)
    documents = [(document, events, "")]
    for parent, parent_events, parent_name in documents:
        for specimen in parent.specimens:
            name = (
                parent_name + f"specimen {specimen['attrs'].get('id', '<unnamed>')!r}: "
            )
            child = specimen["document"]
            selected = set(specimen["attrs"].get("data-specimen-threads", "").split())
            # A template may precede its seed log, and the selection reads against
            # whatever the log holds — so the child checked here is the child
            # allocation would build from this document and this history.
            child_events = [
                {**event, "seq": index}
                for index, event in enumerate(
                    specimen_events(parent, parent_events, selected), 1
                )
            ]
            documents.append((child, child_events, name))
            child_readings = initial_data_document_readings(
                child.lf_elements, child_events, registry
            )
            _, child_errors = _authored_document_checks(
                page_dir,
                child,
                child_events,
                registry,
                stored_data,
                child_readings,
                selected,
            )
            initial = RevisionReading(0, False, 0, SourceDocument(""), {}, {})
            transition = transition_reading(child, child_events, registry, initial)
            child_errors.extend(
                transition_errors(child, registry, initial, transition, False)
            )
            errors.extend(name + error for error in child_errors)
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
            errors.append(str(error))
    revision = revision_reading(page_dir, data, events, artifact)

    source_history_errors, dropped_advice = continuity_errors(
        events, document, registry, revision
    )
    errors.extend(source_history_errors)
    if registry is not None and revision.predecessor:
        errors.extend(
            candidate_vocabulary_gaps(
                page_dir,
                events,
                document,
                registry,
                revision.predecessor,
            )
        )

    transition = transition_reading(document, events, registry, revision)
    errors.extend(
        transition_errors(document, registry, revision, transition, allow_transition)
    )

    advice = _source_advice(
        document,
        registry,
        stored_data,
        revision,
        dropped_advice,
    )
    return SourceCheck(
        document,
        registry,
        transition.projection,
        transition.words,
        revision.predecessor,
        errors,
        advice,
        column,
        artifact,
    )
