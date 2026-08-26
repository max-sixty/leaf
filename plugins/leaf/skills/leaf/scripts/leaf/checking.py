"""Static and browser-backed version check orchestration."""

import sys
from pathlib import Path

from leaf.data import data_binding_errors, read_data_store
from leaf.events import flocked, read_events, retractions, thread_structure
from leaf.files import list_versions, version_name, version_path
from leaf.passages import spoken
from leaf.projection import (
    decisions,
    record_lag,
    retirable_ids,
    retirement_holders,
    state_projection,
)
from leaf.registry import load_registry
from leaf.rendering import render_check
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
    widget_errors,
)


def cmd_check(
    page_dir: Path,
    version,
    render: bool = False,
    transition_held: bool = False,
    events_override: list | None = None,
) -> int:
    if not transition_held:
        with flocked(transition_lock(page_dir)):
            return cmd_check(
                page_dir,
                version,
                render,
                transition_held=True,
                events_override=events_override,
            )
    versions = list_versions(page_dir)
    if not versions:
        sys.exit(
            f"no versions in {page_dir / 'versions'}; write versions/v1.html first"
        )
    selected = version if version is not None else versions[-1]
    if selected not in versions:
        sys.exit(f"no v{version}.html in {page_dir / 'versions'}")
    name = version_name(selected)
    html = version_path(page_dir, selected).read_text(encoding="utf-8")

    errors = []

    for missing in [f for f in VENDORED_FILES if not (page_dir / f).exists()]:
        errors.append(
            f"{missing} missing from the page directory; run `leaf page init` "
            "to vendor the layer"
        )

    parser = parse_structure(html)
    errors.extend(structure_errors(parser))
    errors.extend(page_boundary_errors(parser))

    scripts = parser.external_scripts
    if len(scripts) != 1:
        errors.append(
            f"expected exactly one external <script src> tag, found {len(scripts)}"
            + (f": {[s['attrs']['src'] for s in scripts]}" if scripts else "")
        )
    elif scripts[0]["attrs"] != {"src": "/leaf.js", "type": "module"}:
        attrs = scripts[0]["attrs"]
        errors.append(
            'the only external script must be exactly <script type="module" '
            f'src="/leaf.js">, found attributes {attrs}'
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
        m["content"]
        for m in parser.http_equivs
        if m["equiv"].lower() == "content-security-policy"
    ]
    if declared_csp != [PAGE_CSP]:
        errors.append(
            "the page must declare the layer's one CSP, "
            f'<meta http-equiv="Content-Security-Policy" content="{PAGE_CSP}">'
            + (f" — found {declared_csp}" if declared_csp else "")
        )

    for meta in parser.lf_metas:
        where = f'<meta name="{meta["name"]}"> (line {meta["line"]})'
        if meta["name"] not in LF_META:
            errors.append(f"{where}: unknown lf- meta — known: {sorted(LF_META)}")
            continue
        allowed = LF_META[meta["name"]]
        if allowed is not None and meta["content"] not in allowed:
            errors.append(
                f"{where}: content must be one of {sorted(allowed)}, found {meta['content']!r}"
            )

    errors.extend(id_errors(parser))

    events = read_events(page_dir) if events_override is None else events_override
    registry = load_registry(page_dir)
    if registry is not None:
        errors.extend(widget_errors(parser.lf_elements, registry))
        errors.extend(
            data_binding_errors(
                page_dir,
                registry,
                read_data_store(page_dir),
                events,
            )
        )
        errors.extend(addressable_instance_errors(parser.lf_elements, registry))
        errors.extend(ask_region_errors(parser.lf_elements, registry))
        errors.extend(reference_errors(parser.lf_elements, registry, parser.ids))
        errors.extend(language_class_errors(parser.language_blocks, registry))
        errors.extend(declared_word_errors(parser.lf_elements, registry))
        errors.extend(line_ref_errors(parser.lf_elements, registry))
        # A family lint reads its own slots off the registry, so it stands with
        # the checks that need one — a page missing registry.json has already
        # been told to vendor the layer, and there is nothing to lint against.
        errors.extend(
            suggestion_errors(
                parser.lf_elements,
                registry,
                {e["id"] for e in events if e["kind"] == "comment"},
            )
        )
        for tag, entry in registry.items():
            if not tag.startswith("lf-"):
                continue
            if (
                entry["x-upgrade"]
                and not (page_dir / "widgets" / f"{tag}.js").is_file()
            ):
                errors.append(
                    f"registry marks <{tag}> as upgraded but widgets/{tag}.js "
                    f"isn't vendored; run `leaf page init`"
                )

    # "Previous" is the last *published* version before this one — the page the
    # user was actually looking at, which is what `leaf comment` anchors
    # against and what the browser diffs against. The file before it on disk may be an
    # abandoned draft no note ever released: ids nobody saw, words nobody could
    # have decided on. The first published version has no predecessor, so it
    # stands against an empty one: nothing of its can have been dropped and
    # nothing decided, which is exactly what makes a `restated` on it an error
    # like any other unearned one.
    noted = {e["version"] for e in events if e["kind"] == "note"}
    earlier = [
        candidate
        for candidate in versions
        if candidate < selected and candidate in noted
    ]
    prev, prev_num, was = parse_structure(""), 0, {}
    if earlier:
        prev_num = earlier[-1]
        prev_name = version_name(prev_num)
        prev_html = version_path(page_dir, prev_num).read_text(encoding="utf-8")
        prev = parse_structure(prev_html)
        was = spoken(prev_html, registry or {})
        # An id may retire when the log has settled what holds it; everything
        # else must survive, or the anchors on it break.
        gone = prev.ids - parser.ids
        # With the family lints above, and for their reason: which ids a settled
        # widget licenses is the holder/slot declaration's answer, so with no
        # registry there is nothing to ask it — and every id a decision legitimately
        # retired would read as dropped, stacked on the "vendor the layer" error the
        # page already has.
        if registry is not None:
            previous_projection = state_projection(
                events, prev.by_id, was, registry, prev_num
            )
            dropped = sorted(
                gone
                - retirable_ids(
                    retirement_holders(prev, registry),
                    events,
                    gone,
                    decisions(previous_projection.actions, registry),
                    was,
                )
            )
            if dropped:
                errors.append(
                    f"ids present in {prev_name} but dropped in {name} "
                    f"(anchors on them will break): {dropped}"
                )
    # And the decisions recorded on the ids that stayed — the reviewer channel's
    # gate, then its mirror for the agent channel's standing reports.
    now = spoken(html, registry or {})
    floors = retractions(events, prev_num)
    projection = state_projection(
        events, parser.by_id, now, registry or {}, prev_num, floors
    )
    errors.extend(
        restatement_errors(
            parser,
            prev,
            was,
            now,
            prev_num,
            registry or {},
            projection,
            floors,
        )
    )
    errors.extend(report_errors(parser, prev, was, now, registry or {}, projection))

    # Thread markup is frozen in the log and rendered into the panel; a page id
    # colliding with one would steal its action replays.
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

    if errors:
        print(f"✗ {name}: {len(errors)} issue(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(
        f"✓ {name}: parses, widgets validate, one module script + theme link, "
        f"ids and decisions carried over, nothing overflows the {column}px column"
    )
    # Advice, never a gate: silence is blessed and replay resolves it, but a
    # log-less reader (a printout, a transcript's audience) sees only the markup,
    # so say where it lags the log. Loudest at the end of the exchange — the final
    # version is the page that must read right without the log.
    current_projection = state_projection(
        events, parser.by_id, now, registry or {}, selected
    )
    for line in record_lag(current_projection, parser.by_id, now, registry or {}):
        print(f"  · record behind the log — {line}")
    # Same register, different debt: a block the id rule missed, named while the
    # author can still cheaply mint one.
    for line in unpointable_blocks(parser):
        print(f"  · {line}")
    # Render only what passed the static half: an unparsable page would drown
    # the browser's report in consequences of what the lint already named.
    return render_check(page_dir, selected, transition_held=True) if render else 0
