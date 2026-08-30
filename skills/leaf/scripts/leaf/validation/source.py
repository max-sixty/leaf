"""Static checks for the mutable source document."""

from pathlib import Path
from typing import NamedTuple

from leaf.data import empty_data, read_data_store
from leaf.data_contracts import data_binding_errors, measurement_lag
from leaf.projection import record_lag, state_projection
from leaf.registry.contract import RegistryError
from leaf.registry.storage import load_registry
from leaf.schema import VENDORED_FILES
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
    decision_region_errors,
    declared_word_errors,
    language_class_errors,
    line_ref_errors,
    reference_errors,
    request_offer_errors,
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
from leaf.validation.source_history import (
    RevisionReading,
    TransitionReading,
    continuity_errors,
    revision_reading,
    transition_errors,
    transition_reading,
)


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


def _registry_errors(
    page_dir: Path,
    events: list,
    parser,
    registry: dict | None,
) -> tuple[dict, list[str]]:
    """Validate authored instances and stored data against the vendored vocabulary."""
    stored_data = empty_data()
    errors = []
    if registry is None:
        return stored_data, errors
    stored_data = read_data_store(page_dir)
    errors.extend(widget_errors(parser.lf_elements, registry))
    errors.extend(visual_part_errors(parser.lf_elements, registry))
    errors.extend(
        data_binding_errors(
            page_dir,
            registry,
            stored_data,
            events,
            authored=parser.lf_elements,
        )
    )
    errors.extend(addressable_instance_errors(parser.lf_elements, registry))
    errors.extend(decision_region_errors(parser.lf_elements, registry))
    errors.extend(request_offer_errors(parser.lf_elements, registry))
    errors.extend(
        reference_errors(parser.lf_elements, registry, parser.ids, parser.by_id)
    )
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
    revision: RevisionReading,
    transition: TransitionReading,
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
    revision = revision_reading(page_dir, data, events, registry)
    stored_data, registry_errors = _registry_errors(page_dir, events, parser, registry)
    errors.extend(registry_errors)

    source_history_errors, dropped_advice = continuity_errors(
        events, parser, registry, revision
    )
    errors.extend(source_history_errors)

    transition = transition_reading(html, events, parser, registry, revision)
    errors.extend(
        transition_errors(parser, registry, revision, transition, allow_transition)
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
