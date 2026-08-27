"""Static checks for the mutable source document."""

import sys
from pathlib import Path
from typing import NamedTuple

from leaf.data import data_binding_errors, read_data_store
from leaf.events import flocked, read_events, retractions, thread_structure
from leaf.files import list_revisions, revision_path
from leaf.passages import spoken
from leaf.projection import (
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
from leaf.validation import (
    addressable_instance_errors,
    ask_region_errors,
    declared_word_errors,
    id_errors,
    language_class_errors,
    line_ref_errors,
    media_errors,
    page_boundary_errors,
    reference_errors,
    report_errors,
    restatement_errors,
    structure_errors,
    suggestion_errors,
    unpointable_blocks,
    visual_part_errors,
    widget_errors,
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
    try:
        registry = load_registry(page_dir)
    except RegistryError as error:
        registry = None
        errors.append(str(error))
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
    was = {}
    dropped_advice = []
    if predecessor:
        previous_html = revision_path(page_dir, predecessor).read_text(encoding="utf-8")
        previous = parse_structure(previous_html)
        was = spoken(previous_html, registry or {})

    if registry is not None:
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
                read_data_store(page_dir),
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

    if predecessor and not committed_active and registry is not None:
        gone = previous.ids - parser.ids
        previous_parts = {
            (rec["attrs"]["id"], part)
            for rec in previous.lf_elements
            if rec["attrs"].get("id")
            for part in visual_parts(rec, registry)
        }
        current_parts = {
            (rec["attrs"]["id"], part)
            for rec in parser.lf_elements
            if rec["attrs"].get("id")
            for part in visual_parts(rec, registry)
        }
        dropped_parts = sorted(
            f"{section} · {part}"
            for section, part in previous_parts - current_parts
            if section in parser.ids
        )
        if dropped_parts:
            errors.append(
                f"visual parts present in revision r{predecessor} but dropped in "
                f"index.html (anchors on them will break): {dropped_parts}"
            )
        previous_projection = state_projection(
            events, previous.by_id, was, registry, predecessor
        )
        protected = protected_ids(
            retirement_holders(previous, registry),
            events,
            gone,
            previous_projection,
            was,
            registry,
        )
        dropped = sorted(gone & protected)
        dropped_advice = sorted(gone - protected)
        if dropped:
            errors.append(
                f"protected ids present in revision r{predecessor} but dropped in "
                "index.html (unresolved threads, standing state, or widget "
                f"retirement still need them): {dropped}"
            )

    now = spoken(html, registry or {})
    floors = retractions(events, predecessor)
    projection = state_projection(
        events, parser.by_id, now, registry or {}, predecessor, floors
    )
    if not committed_active:
        errors.extend(
            restatement_errors(
                parser,
                previous,
                was,
                now,
                predecessor,
                registry or {},
                projection,
                floors,
            )
        )
        errors.extend(
            report_errors(parser, previous, was, now, registry or {}, projection)
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

    taken = sorted(parser.ids & thread_structure(events).ids)
    if taken:
        errors.append(f"ids already taken by widget markup in a reply: {taken}")
    errors.extend(media_errors(parser, page_dir))

    theme_css = (
        (page_dir / "theme.css").read_text(encoding="utf-8")
        if (page_dir / "theme.css").exists()
        else ""
    )
    errors.extend(css_syntax_errors(parser.css, "page <style>"))
    for number, style in enumerate(parser.inline_styles, 1):
        errors.extend(css_syntax_errors(style, f"inline style #{number}", block=True))
    errors.extend(css_syntax_errors(theme_css, "theme.css"))
    errors.extend(inline_presentation_override_errors(parser))
    column = _column_width(parser.css, theme_css)
    errors.extend(_overwide_elements(parser, column, root_tokens(theme_css)))

    current_projection = state_projection(
        events, parser.by_id, now, registry or {}, active or 0
    )
    advice = [
        *(
            [f"ids dropped from revision r{predecessor}: {dropped_advice}"]
            if dropped_advice
            else []
        ),
        *(
            f"record behind the log: {line}"
            for line in record_lag(
                current_projection, parser.by_id, now, registry or {}
            )
        ),
        *unpointable_blocks(parser),
    ]
    return SourceCheck(
        data,
        html,
        parser,
        registry,
        projection,
        now,
        predecessor,
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
        from leaf.rendering import render_check

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
