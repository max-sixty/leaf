"""Shared structural and authored-markup validation rules."""

import re
from pathlib import Path

from leaf.schema import _DIR_FILES, MEDIA_DIR
from leaf.structure import OPTIONAL_END, SECTIONING_TAGS, _StructParser
from leaf.styles import inline_presentation_override_errors

# One media reference as a message's Markdown writes it, read with the layer's own
# naming rather than a second spelling of it: the digest is what tells a real
# reference from the word "/media/" standing in a sentence.
MEDIA_REFERENCE = re.compile(rf"/{MEDIA_DIR}/{_DIR_FILES[MEDIA_DIR]}")


def reserved_ids_error(ids: list) -> str:
    """The one sentence for an authored id in the runtime's own namespace, shared by the
    version lint and the thread-markup one — page ids and a reply's are one universe, so
    what keeps both clear of the runtime's is one rule. leaf.js coins document ids
    under `lf-` (`lf-composer-quote`) and points ARIA at them, so an authored id there
    redirects the reference to the page."""
    return (
        "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, "
        f"and points ARIA at them): {ids}"
    )


def reserved_marker_errors(parser) -> list:
    """The same trespass as a reserved id, and reserved the same way one is: the
    runtime writes data-lf-* attributes and lf- classes as its own record and
    reads them back, so an authored copy makes it misread the page — words
    inside .lf-chrome leave every reading, .lf-quiet clips them to a point, and
    data-lf-gen words become cells the file-side reading has no fence for."""
    return [
        f"<{tag}> at line {line} wears the runtime's own markers "
        f"({', '.join(markers)}); the lf- and data-lf- namespaces are the "
        "runtime's to write, whether or not it writes this name today"
        for tag, line, markers in parser.reserved_markers
    ]


def id_errors(parser) -> list:
    """What a parsed page's own names must not do: repeat, or trespass on the runtime's
    own namespace — its ids, and its markers. One reader, because the two gates that decision
    are asking the same thing of the same parser: a version, and a catalog example, which
    is markup an author writes from. Written twice, the second gate is the one that goes
    on not asking whatever the first one learns to."""
    errors = []
    if parser.duplicate_ids:
        errors.append(
            f"duplicate ids (anchors need unique targets): {parser.duplicate_ids}"
        )
    if parser.reserved_ids:
        errors.append(reserved_ids_error(parser.reserved_ids))
    return errors + reserved_marker_errors(parser)


def at(rec: dict, named: str = "") -> str:
    """Where a lint finding is, in the terms the author reads their own file in: the
    tag, whatever identifies the one meant — an id, or the attribute the rule is
    about — and the line the markup opens on. Every gate below opens its findings this
    way, so the shape is stated here rather than re-spelled at each of them; a reader
    scanning a page of them reads one shape, and a change to it is one edit."""
    return f"<{rec['tag']}{' ' + named if named else ''}> (line {rec['line']})"


def unpointable_blocks(parser: _StructParser) -> list:
    """Blocks a user will aim at whole that no anchor can name. Advice, never a
    gate:
    references/page-authoring.md's "Stable anchors" states the id rule, and this
    is its feedback loop. The page that introduced item anchoring hit this
    failure itself — its code blocks carried no ids, so a comment aimed at one fell
    through to the enclosing section and read as the gesture being broken rather
    than the page being bare, and nothing anywhere said so.

    A section or article is named outright; a block below one only where its aim
    escapes to a sectioning element. The ancestor's tag stands in for tightness —
    a figure around a table, a card around a pre — which no static read can
    measure, so a page-wide <div id> also passes for aim enough and the advice
    stays quiet. Undercounting is the right error for advice: a miss costs one
    aim landing wide, noise costs the register its authority."""
    lines = []
    for block in parser.bare_blocks:
        where = at(block)
        under = block["under"]
        if block["tag"] in ("section", "article"):
            lines.append(
                f"unpointable — {where} has no id, so no comment or reading "
                f"position can hold to it"
            )
        elif under is None:
            lines.append(
                f"unpointable — {where} has no id, nor anything enclosing it, "
                f"so no comment can name it"
            )
        elif under[0] in SECTIONING_TAGS:
            lines.append(
                f"unpointable — {where} has no id, so a comment aimed at it "
                f"lands on the whole of #{under[1]}"
            )
    return lines


def structure_errors(parser: _StructParser) -> list:
    """A fed parser's structural complaints, plus the tags it was left holding
    open at the end of its input."""
    errors = list(parser.errors)
    leftover = [(t, ln) for t, ln, *_ in parser.stack if t not in OPTIONAL_END]
    if leftover:
        errors.append(
            "unclosed tags: " + ", ".join(f"<{t}> (line {ln})" for t, ln in leftover)
        )
    return errors


def page_boundary_errors(parser: _StructParser) -> list:
    """Authored content lies under the page's one main content boundary."""
    errors = []
    direct = [line for line, is_direct in parser.main_elements if is_direct]
    if (
        len(parser.body_lines) != 1
        or len(parser.main_elements) != 1
        or len(direct) != 1
    ):
        errors.append(
            "the page must have one <main> directly under <body>; "
            f"found {len(parser.body_lines)} bodies, {len(parser.main_elements)} mains, "
            f"and {len(direct)} direct body mains"
        )
    if parser.outside_main:
        errors.append(
            "paintable authored content must stay inside the one <main> directly "
            "under <body>; found " + str(parser.outside_main)
        )
    return errors


def fragment_style_errors(parser: _StructParser) -> list:
    """A message may not dress the document it is put into.

    A version's <style> is the page's own, and the gates a version answers to read
    it as such — syntax, the column it may not overflow, the presentation
    properties the theme keeps. A fragment has no page of its own: the runtime
    parses an agent's reply markup into a template and moves those nodes into the
    message body, where a <style> among them becomes a document stylesheet like
    any other. `<style>main h1 { color: red !important }</style>` in a reply was
    accepted here and repainted the version's own heading, past every gate the
    same rule in a version answers to; an inline `!important` on a protected
    property outranked the theme's first cascade layer the same way.

    Nothing is lost by refusing them. The layer already dresses a widget an agent
    sends — that is what a registry entry and its theme rules are for — and a rule
    of a message's own has nowhere honest to sit, because the message is not the
    page and its markup is frozen in the log where no version can revise it."""
    errors = []
    if parser.css.strip():
        errors.append(
            "<style> in message markup becomes a stylesheet of the whole document it "
            "is put into; a widget's look belongs in the layer's theme, beside its "
            "registry entry"
        )
    if parser.stylesheets:
        errors.append(
            "<link rel=stylesheet> in message markup dresses the whole document it is "
            "put into; the page serves the one vendored theme it was reviewed with"
        )
    return errors + inline_presentation_override_errors(parser)


def media_errors(parser: _StructParser, page_dir: Path) -> list:
    """A /media/ reference the page directory can't answer, which renders as a broken
    image. The render gate would catch it as a 404, but that runs once a page; this
    runs at every door markup comes through, and a missing file is as deterministic as
    a missing id.

    Both doors, because a widget carrying pictures is exactly the shape an agent sends
    in a reply — here is what it looks like now, and after — and the fragment door was
    the one that didn't ask. A version can be rewritten; a reply is frozen in an
    append-only log the moment it is accepted, so an unanswerable reference posted
    there is two broken images for as long as the page exists, and no later check
    would ever mention them.

    Asked at each door rather than in the vocabulary contract, for the reason
    `check_markup` gives where that choice is made."""
    return _unanswered_media(parser.media_refs, page_dir)


def text_media_errors(text: str, page_dir: Path) -> list:
    """The same reference in a message's prose, which is the other way one arrives.

    Markup names a picture in an attribute, where the parsed reading above finds it;
    a message names one in Markdown, which that reading cannot see — so an agent
    sending a screenshot, the very shape `media_errors` was written for, came through
    the one door that never asked. `check_markup` runs only when `--markup` is given,
    and text on its own reached the log unread.

    Read by the layer's own name for a file rather than by scanning for the word:
    `/media/` in a sentence is the author's prose, and a content-addressed digest is
    a reference. What the shape lets through, the file below answers for."""
    return _unanswered_media(set(MEDIA_REFERENCE.findall(text)), page_dir)


def _unanswered_media(refs, page_dir: Path) -> list:
    return [
        f"{ref} isn't in the page directory; `leaf page media` puts it there"
        for ref in sorted(refs)
        if not (page_dir / ref.lstrip("/")).is_file()
    ]
