"""Static checks for the mutable source document."""

import sys
from pathlib import Path
from typing import NamedTuple

from leaf.data import data_binding_errors, empty_data, measurement_lag, read_data_store
from leaf.event_log import flocked, read_events
from leaf.events import retractions
from leaf.files import list_revisions, revision_path
from leaf.passages import spoken
from leaf.projection import (
    StateProjection,
    protected_ids,
    record_lag,
    retirement_holders,
    state_projection,
)
from leaf.registry import RegistryError, load_registry, visual_parts
from leaf.schema import VENDORED_FILES
from leaf.service import transition_lock
from leaf.structure import LF_META, PAGE_CSP, parse_structure
from leaf.styles import (
    _column_width,
    _overwide_elements,
    css_syntax_errors,
    inline_presentation_override_errors,
    root_tokens,
)
from leaf.thread_context import thread_structure
from leaf.validation.instances import (
    addressable_instance_errors,
    ask_region_errors,
    declared_word_errors,
    language_class_errors,
    line_ref_errors,
    reference_errors,
    suggestion_errors,
    visual_part_errors,
    widget_errors,
)
from leaf.validation.markup import (
    id_errors,
    media_errors,
    page_boundary_errors,
    structure_errors,
    unpointable_blocks,
)
from leaf.validation.transitions import report_errors, restatement_errors


class SourceCheck(NamedTuple):
    """One complete reading of the exact source bytes."""

    data: bytes
    html: str
    parser: object
    registry: dict | None
    projection: object
    spoken: dict
    predecessor: int
    errors: list[str]
    advice: list[str]
    column: int


class _RevisionReading(NamedTuple):
    """The active and predecessor documents this exact source is checked against."""

    revisions: list[int]
    active: int
    committed_active: bool
    predecessor: int
    previous: object
    previous_words: dict


class _TransitionReading(NamedTuple):
    """The current document's words and standing projection at its predecessor."""

    words: dict
    floors: dict
    projection: StateProjection


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

    scripts = parser.external_scripts
    if len(scripts) != 1:
        errors.append(
            f"expected exactly one external <script src> tag, found {len(scripts)}"
            + (f": {[script['attrs']['src'] for script in scripts]}" if scripts else "")
        )
    elif scripts[0]["attrs"] != {"src": "/leaf.js", "type": "module"}:
        errors.append(
            'the only external script must be exactly <script type="module" '
            f'src="/leaf.js">, found attributes {scripts[0]["attrs"]}'
        )
    elif scripts[0]["parent"] != "head" or not scripts[0]["early_head"]:
        errors.append(
            "the /leaf.js module must be in <head> before <body> can paint; "
            "its <head> must be the document's direct, initial head"
        )

    stylesheets = parser.stylesheets
    if len(stylesheets) != 1 or stylesheets[0]["attrs"] != {
        "rel": "stylesheet",
        "href": "/theme.css",
    }:
        errors.append(
            "the page must link exactly one stylesheet, always-applicable and exactly "
            '<link rel="stylesheet" href="/theme.css">, found '
            f"{[asset['attrs'] for asset in stylesheets]}"
        )
    elif stylesheets[0]["parent"] != "head" or not stylesheets[0]["early_head"]:
        errors.append(
            "the /theme.css stylesheet must be in <head> before <body> can paint; "
            "its <head> must be the document's direct, initial head"
        )

    declared_csp = [
        meta["content"]
        for meta in parser.http_equivs
        if meta["equiv"].lower() == "content-security-policy"
    ]
    if declared_csp != [PAGE_CSP]:
        errors.append(
            "the page must declare the layer's one CSP, "
            f'<meta http-equiv="Content-Security-Policy" content="{PAGE_CSP}">'
            + (f"; found {declared_csp}" if declared_csp else "")
        )

    for meta in parser.lf_metas:
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


def _revision_reading(
    page_dir: Path,
    data: bytes,
    events: list,
    registry: dict | None,
) -> _RevisionReading:
    """Read the predecessor whose still-standing decisions this source must keep."""
    revisions = list_revisions(page_dir)
    active = revisions[-1] if revisions else 0
    active_data = revision_path(page_dir, active).read_bytes() if active else None
    same_as_active = active_data == data
    committed_active = bool(
        active
        and same_as_active
        and any(
            event["kind"] == "note" and event["revision"] == active for event in events
        )
    )
    predecessor = (
        active
        if committed_active
        else (revisions[-2] if same_as_active and len(revisions) > 1 else active)
    )
    previous = parse_structure("")
    previous_words = {}
    if predecessor:
        previous_html = revision_path(page_dir, predecessor).read_text(encoding="utf-8")
        previous = parse_structure(previous_html)
        previous_words = spoken(previous_html, registry or {})
    return _RevisionReading(
        revisions,
        active,
        committed_active,
        predecessor,
        previous,
        previous_words,
    )


def _registry_errors(
    page_dir: Path,
    events: list,
    parser,
    registry: dict | None,
    revisions: list[int],
) -> tuple[dict, list[str]]:
    """Validate authored instances and stored data against the vendored vocabulary."""
    stored_data = empty_data()
    errors = []
    if registry is None:
        return stored_data, errors
    stored_data = read_data_store(page_dir)
    errors.extend(widget_errors(parser.lf_elements, registry))
    errors.extend(visual_part_errors(parser.lf_elements, registry))
    history = [
        (
            parse_structure(
                revision_path(page_dir, revision).read_text(encoding="utf-8")
            ).lf_elements,
            f"revision r{revision}",
        )
        for revision in revisions
    ]
    errors.extend(
        data_binding_errors(
            page_dir,
            registry,
            stored_data,
            events,
            [*history, (parser.lf_elements, "index.html")],
        )
    )
    errors.extend(addressable_instance_errors(parser.lf_elements, registry))
    errors.extend(ask_region_errors(parser.lf_elements, registry))
    errors.extend(reference_errors(parser.lf_elements, registry, parser.ids))
    errors.extend(language_class_errors(parser.language_blocks, registry))
    errors.extend(declared_word_errors(parser.lf_elements, registry))
    errors.extend(line_ref_errors(parser.lf_elements, registry))
    errors.extend(
        suggestion_errors(
            parser.lf_elements,
            registry,
            {event["id"] for event in events if event["kind"] == "comment"},
        )
    )
    for tag, entry in registry.items():
        if (
            tag.startswith("lf-")
            and entry["x-upgrade"]
            and not (page_dir / "widgets" / f"{tag}.js").is_file()
        ):
            errors.append(
                f"registry marks <{tag}> as upgraded but widgets/{tag}.js "
                "isn't vendored; run `leaf page init`"
            )
    return stored_data, errors


def _continuity_errors(
    events: list,
    parser,
    registry: dict | None,
    revision: _RevisionReading,
) -> tuple[list[str], list[str]]:
    """Protect predecessor anchors, standing state, and retirement holders."""
    if not revision.predecessor or revision.committed_active or registry is None:
        return [], []
    gone = revision.previous.ids - parser.ids
    previous_parts = {
        (record["attrs"]["id"], part)
        for record in revision.previous.lf_elements
        if record["attrs"].get("id")
        for part in visual_parts(record, registry)
    }
    current_parts = {
        (record["attrs"]["id"], part)
        for record in parser.lf_elements
        if record["attrs"].get("id")
        for part in visual_parts(record, registry)
    }
    dropped_parts = sorted(
        f"{section} · {part}"
        for section, part in previous_parts - current_parts
        if section in parser.ids
    )
    errors = []
    if dropped_parts:
        errors.append(
            f"visual parts present in revision r{revision.predecessor} but dropped in "
            f"index.html (anchors on them will break): {dropped_parts}"
        )
    previous_projection = state_projection(
        events,
        revision.previous.by_id,
        revision.previous_words,
        registry,
        revision.predecessor,
    )
    protected = protected_ids(
        retirement_holders(revision.previous, registry),
        events,
        gone,
        previous_projection,
        revision.previous_words,
        registry,
    )
    dropped = sorted(gone & protected)
    dropped_advice = sorted(gone - protected)
    if dropped:
        errors.append(
            f"protected ids present in revision r{revision.predecessor} but dropped in "
            "index.html (unresolved threads, standing state, or widget "
            f"retirement still need them): {dropped}"
        )
    return errors, dropped_advice


def _transition_reading(
    html: str,
    events: list,
    parser,
    registry: dict | None,
    revision: _RevisionReading,
) -> _TransitionReading:
    """Project standing log changes onto this source from its predecessor."""
    words = spoken(html, registry or {})
    floors = retractions(events, revision.predecessor)
    projection = state_projection(
        events,
        parser.by_id,
        words,
        registry or {},
        revision.predecessor,
        floors,
    )
    return _TransitionReading(words, floors, projection)


def _transition_errors(
    parser,
    registry: dict | None,
    revision: _RevisionReading,
    transition: _TransitionReading,
    allow_transition: bool,
) -> list[str]:
    """Validate decision retractions and report settlements in changed source."""
    if revision.committed_active:
        return []
    errors = restatement_errors(
        parser,
        revision.previous,
        revision.previous_words,
        transition.words,
        revision.predecessor,
        registry or {},
        transition.projection,
        transition.floors,
    )
    errors.extend(
        report_errors(
            parser,
            revision.previous,
            revision.previous_words,
            transition.words,
            registry or {},
            transition.projection,
        )
    )
    if not allow_transition:
        if parser.restated:
            errors.append(
                "index.html carries restated decisions; stamp these exact bytes "
                "to record their retraction"
            )
        if parser.overruled:
            errors.append(
                "index.html overrules standing reports; stamp these exact bytes "
                "to record their settlement"
            )
    return errors


def _presentation_errors(page_dir: Path, parser) -> tuple[int, list[str]]:
    """Validate authored and vendored CSS and return the readable column width."""
    theme_css = (
        (page_dir / "theme.css").read_text(encoding="utf-8")
        if (page_dir / "theme.css").exists()
        else ""
    )
    errors = css_syntax_errors(parser.css, "page <style>")
    for number, style in enumerate(parser.inline_styles, 1):
        errors.extend(css_syntax_errors(style, f"inline style #{number}", block=True))
    errors.extend(css_syntax_errors(theme_css, "theme.css"))
    errors.extend(inline_presentation_override_errors(parser))
    column = _column_width(parser.css, theme_css)
    errors.extend(_overwide_elements(parser, column, root_tokens(theme_css)))
    return column, errors


def _source_advice(
    events: list,
    parser,
    registry: dict | None,
    stored_data: dict,
    revision: _RevisionReading,
    transition: _TransitionReading,
    dropped_ids: list[str],
) -> list[str]:
    """Report non-blocking drift after every error-producing phase has run."""
    current_projection = state_projection(
        events,
        parser.by_id,
        transition.words,
        registry or {},
        revision.active or 0,
    )
    return [
        *(
            [f"ids dropped from revision r{revision.predecessor}: {dropped_ids}"]
            if dropped_ids
            else []
        ),
        *(
            f"record behind the log: {line}"
            for line in record_lag(
                current_projection,
                parser.by_id,
                transition.words,
                registry or {},
            )
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
        return SourceCheck(
            data, "", parse_structure(""), None, None, {}, 0, [source_error], [], 0
        )
    html = data.decode("utf-8")
    parser = parse_structure(html)
    errors = _document_errors(page_dir, parser)
    try:
        registry = load_registry(page_dir)
    except RegistryError as error:
        registry = None
        errors.append(str(error))
    revision = _revision_reading(page_dir, data, events, registry)
    stored_data, registry_errors = _registry_errors(
        page_dir, events, parser, registry, revision.revisions
    )
    errors.extend(registry_errors)

    continuity_errors, dropped_advice = _continuity_errors(
        events, parser, registry, revision
    )
    errors.extend(continuity_errors)

    transition = _transition_reading(html, events, parser, registry, revision)
    errors.extend(
        _transition_errors(parser, registry, revision, transition, allow_transition)
    )

    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(f"ids already taken by widget markup in a reply: {taken}")
    errors.extend(media_errors(parser, page_dir))

    column, presentation_errors = _presentation_errors(page_dir, parser)
    errors.extend(presentation_errors)
    advice = _source_advice(
        events,
        parser,
        registry,
        stored_data,
        revision,
        transition,
        dropped_advice,
    )
    return SourceCheck(
        data,
        html,
        parser,
        registry,
        transition.projection,
        transition.words,
        revision.predecessor,
        errors,
        advice,
        column,
    )


def cmd_check(
    page_dir: Path,
    render: bool = False,
    *,
    transition_held: bool = False,
    events_override: list | None = None,
) -> int:
    """Check the mutable source without activating or stamping it."""
    if not transition_held:
        with flocked(transition_lock(page_dir)):
            return cmd_check(
                page_dir,
                render,
                transition_held=True,
                events_override=events_override,
            )
    events = read_events(page_dir) if events_override is None else events_override
    result = check_source(page_dir, events)
    if result.errors:
        print(f"✗ index.html: {len(result.errors)} issue(s)", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        for line in result.advice:
            print(f"  · {line}", file=sys.stderr)
        return 1
    print(
        "✓ index.html: parses, widgets validate, one module script + theme link, "
        "protected ids and decisions carried over, nothing overflows the "
        f"{result.column}px column"
    )
    for line in result.advice:
        print(f"  · {line}")
    if render:
        from leaf.render_gate.command import render_check

        revisions = list_revisions(page_dir)
        active = revisions[-1] if revisions else 0
        revision = active
        if not active or revision_path(page_dir, active).read_bytes() != result.data:
            revision = active + 1
        return render_check(
            page_dir,
            source=result.data,
            revision=revision,
            transition_held=True,
        )
    return 0
