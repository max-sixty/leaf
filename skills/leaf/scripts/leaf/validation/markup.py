"""Shared structural and authored-markup validation rules."""

from pathlib import Path

from markdown_it import MarkdownIt

from leaf.schema import MEDIA_DIR, SERVED_PATH
from leaf.structure import (
    PAGE_ALLOCATIONS,
    SECTIONING_TAGS,
    SourceDocument,
    allocation_expects,
    links_with_rel,
)
from leaf.styles import inline_presentation_override_errors

_message_markdown = MarkdownIt("commonmark")


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
    """What a parsed markup's own names must not do: repeat, hold whitespace, or trespass
    on the runtime's own namespace — its ids, and its markers. One reader, because every
    gate that decides this is asking the same thing of the same parser: a version, a
    catalog example, which is markup an author writes from, and a message's widget
    markup, since page ids and a reply's are one universe. Written twice, the second
    gate is the one that goes on not asking whatever the first one learns to."""
    errors = []
    if parser.duplicate_ids:
        errors.append(
            f"duplicate ids (anchors need unique targets): {parser.duplicate_ids}"
        )
    # HTML forbids whitespace in an id, and nothing downstream refuses one: the browser
    # still finds the element, so a comment anchors on the whole string and the page
    # reads as working. The id is then a thread's address, and renaming it means moving
    # the thread first; authoring is the one moment the fix costs nothing.
    if parser.spaced_ids:
        errors.append(
            f"ids containing whitespace, which HTML forbids in an id: {parser.spaced_ids}"
        )
    # leaf.js coins document ids under `lf-` (`lf-composer-quote`) and points ARIA at
    # them, so an authored id there redirects the reference to the page.
    if parser.reserved_ids:
        errors.append(
            "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, "
            f"and points ARIA at them): {parser.reserved_ids}"
        )
    # A command's ID names a widget or a message, whichever the page holds; the log
    # mints message ids in this shape, so an authored one could name both.
    if parser.event_shaped_ids:
        errors.append(
            "ids shaped like the event ids the log mints (eight hex digits), which "
            f"commands would read as a message: {parser.event_shaped_ids}"
        )
    return errors + reserved_marker_errors(parser)


def at(rec: dict, named: str = "") -> str:
    """Where a lint finding is, in the terms the author reads their own file in: the
    tag, whatever identifies the one meant — an id, or the attribute the rule is
    about — and the line the markup opens on. Every gate below opens its findings this
    way, so the shape is stated here rather than re-spelled at each of them; a reader
    scanning a page of them reads one shape, and a change to it is one edit."""
    return f"<{rec['tag']}{' ' + named if named else ''}> (line {rec['line']})"


def unpointable_blocks(parser: SourceDocument) -> list:
    """Blocks a user will aim at whole that no anchor can name. Advice, never a
    gate:
    references/page-authoring.md's "Stable anchors" states the id rule, and this
    is its feedback loop. The page that introduced addressable-element anchoring hit this
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


def structure_errors(parser: SourceDocument) -> list:
    """Structural complaints and source elements missing a required end tag."""
    errors = list(parser.errors)
    if parser.unclosed:
        errors.append(
            "unclosed tags: "
            + ", ".join(f"<{tag}> (line {line})" for tag, line in parser.unclosed)
        )
    return errors


def document_declaration_errors(parser: SourceDocument) -> list:
    """Delivery declares the document's base, headers, and import map, and addresses
    every request Leaf's runtime makes by them. Markup that declares its own, in a page
    or in a message quoted into one, sends those requests elsewhere, navigates the page,
    or leaves its modules unable to resolve, and a message does so in every revision."""
    return [
        f"<{item['tag']}> (line {item['line']}) declares something about the whole "
        "document, which delivery owns"
        for item in parser.document_declarations
    ]


def page_boundary_errors(parser: SourceDocument) -> list:
    """Authored content lies under the page's one main content boundary."""
    errors = []
    direct_heads = [line for line, is_direct in parser.head_elements if is_direct]
    if (
        len(parser.head_lines) != 1
        or len(parser.head_elements) != 1
        or len(direct_heads) != 1
    ):
        errors.append(
            "the page must have one explicit <head> directly under <html>; "
            f"found {len(parser.head_lines)} head tags, {len(parser.head_elements)} "
            f"parsed heads, and {len(direct_heads)} direct html heads"
        )
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


def authored_allocation_errors(parser: SourceDocument) -> list:
    """Authored allocations use the layer's named values, and a page's own allocation
    stands on its `body`."""
    return (
        [
            f"{at(item, item['attr'] + '=' + repr(item['value']))} has an invalid value; "
            f"expected {expected}"
            for item in parser.authored_allocations
            if (expected := allocation_expects(item["attr"], item["value"]))
        ]
        + [
            f"{at(item, item['attr'])} states the height of a widget that draws into "
            f"its box, and <{item['tag']}> is not one: a block takes the height of what "
            "it holds"
            for item in parser.authored_allocations
            if item["attr"] == "data-height" and not item["tag"].startswith("lf-")
        ]
        + [
            f"{at(item, item['attr'])} belongs on <body>, where it says whether the page "
            f"keeps a rail"
            for item in parser.authored_allocations
            if item["attr"] in PAGE_ALLOCATIONS and item["tag"] != "body"
        ]
        + [
            f"{at(item, item['attr'])} sizes a block in the page's flow, and <main> is the "
            "page: its width is a Layout class on it (layout-wide, layout-sidebar, "
            "layout-workspace)"
            for item in parser.authored_allocations
            if item["attr"] not in PAGE_ALLOCATIONS | {"data-height"}
            and item["tag"] == "main"
        ]
    )


def unarranged_main(parser: SourceDocument) -> list:
    """Advice for a `main` with no Layout class. Nothing arranges such a page, so its
    blocks run the window's width; the page's own CSS may mean exactly that, which is
    why this is advice rather than an error."""
    main = next((node for node in parser.nodes if node["tag"] == "main"), None)
    if main is None or any(
        name.startswith("layout-") for name in main["attrs"].get("class", "").split()
    ):
        return []
    return [
        (
            "<main> has no Layout class, so nothing arranges the page and its blocks "
            'run the window\'s width; class="layout-column" sets the reading column, '
            "unless the page's own CSS arranges it"
        )
    ]


def fragment_style_errors(parser: SourceDocument) -> list:
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
    sends — that is what an element declaration and its theme rules are for — and a rule
    of a message's own has nowhere honest to sit, because the message is not the
    page and its markup is frozen in the log where no version can revise it."""
    errors = []
    if parser.css.strip():
        errors.append(
            "<style> in message markup becomes a stylesheet of the whole document it "
            "is put into; a widget's look belongs in the layer's theme, beside its "
            "element declaration"
        )
    if links_with_rel(parser.links, "stylesheet"):
        errors.append(
            "<link rel=stylesheet> in message markup dresses the whole document it is "
            "put into; the page serves the one vendored theme it was reviewed with"
        )
    return (
        errors
        + authored_allocation_errors(parser)
        + inline_presentation_override_errors(parser)
    )


def media_errors(parser: SourceDocument, page_dir: Path) -> list:
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
    """The same reference in a message's Markdown, which is the other way one arrives.

    Markup names a picture in an attribute, where the parsed reading above finds it;
    a message names one as a Markdown destination, which that reading cannot see — so
    an agent sending a screenshot, the very shape `media_errors` was written for, came
    through the one door that never asked. `check_markup` runs only when `--markup` is
    given, and text on its own reached the log unread.

    A reference is a rendered link or image destination, never a scan of the words.
    Parsing the Markdown resolves referenced definitions and leaves fenced examples
    and unused definitions as text, so neither asks for a file the page will not load."""
    refs = {
        url
        for token in _message_markdown.parse(text)
        for child in token.children or ()
        if child.type in {"link_open", "image"}
        if (url := child.attrGet("href" if child.type == "link_open" else "src"))
        and url.startswith(f"/{MEDIA_DIR}/")
    }
    return _unanswered_media(refs, page_dir)


def _unanswered_media(refs, page_dir: Path) -> list:
    """Every `/media/…` reference the page will not answer: one whose name the server
    never serves (`schema.MEDIA_DIGEST`), whatever the directory holds under it, and
    one the directory has not got."""
    errors = []
    for ref in sorted(refs):
        if not SERVED_PATH.fullmatch(ref):
            errors.append(
                f"{ref} isn't a name `leaf page media` gives, so the page never "
                "serves it"
            )
        elif not (page_dir / ref.lstrip("/")).is_file():
            errors.append(
                f"{ref} isn't in the page directory; `leaf page media` puts it there"
            )
    return errors
