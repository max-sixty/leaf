"""Shared structural and authored-markup validation rules."""

from pathlib import Path
from urllib.parse import urlsplit

from leaf.findings import Finding, element_at
from leaf.passages import block_markdown
from leaf.schema import MEDIA_DIR, SERVED_PATH
from leaf.structure import (
    AUTHORED_ALLOCATIONS,
    POINTABLE_TAGS,
    SECTIONING_TAGS,
    SourceDocument,
    allocation_valid,
    links_with_rel,
)


def found_at(code: str, rec: dict, id: str = "", **values) -> Finding:
    """A finding about one parsed element, named as the author reads their own file:
    its tag, with its id where the words name the one meant, and the line its markup
    opens on. Every gate below makes its element findings here, so a reader scanning
    a page of them reads one shape."""
    return Finding(code, element_at(rec["tag"], id), {"line": rec["line"], **values})


def reserved_marker_errors(parser) -> list[Finding]:
    """The same trespass as a reserved id, and reserved the same way one is: the
    runtime writes data-lf-* attributes and lf- classes as its own record and
    reads them back, so an authored copy makes it misread the page — words
    inside .lf-chrome leave every reading, .lf-quiet clips them to a point, and
    data-lf-gen words become cells the file-side reading has no fence for."""
    return [
        Finding("reserved-markers", element_at(tag), {"line": line, "markers": markers})
        for tag, line, markers in parser.authoring.reserved_markers
    ]


def id_errors(parser) -> list[Finding]:
    """What a parsed markup's own names must not do: repeat, hold whitespace, or trespass
    on the runtime's own namespace — its ids, and its markers. One reader, because every
    gate that decides this is asking the same thing of the same parser: a version, a
    catalog example, which is markup an author writes from, and a message's widget
    markup, since page ids and a reply's are one universe. Written twice, the second
    gate is the one that goes on not asking whatever the first one learns to."""
    errors = []
    if parser.duplicate_ids:
        errors.append(Finding("duplicate-ids", values={"ids": parser.duplicate_ids}))
    # HTML forbids whitespace in an id, and nothing downstream refuses one: the browser
    # still finds the element, so a comment anchors on the whole string and the page
    # reads as working. The id is then a thread's address, and renaming it means moving
    # the thread first; authoring is the one moment the fix costs nothing.
    if parser.spaced_ids:
        errors.append(Finding("spaced-ids", values={"ids": parser.spaced_ids}))
    # leaf.js coins document ids under `lf-` (`lf-composer-quote`) and points ARIA at
    # them, so an authored id there redirects the reference to the page.
    if parser.reserved_ids:
        errors.append(Finding("reserved-ids", values={"ids": parser.reserved_ids}))
    # A command's ID names a widget or a message, whichever the page holds; the log
    # mints message ids in this shape, so an authored one could name both.
    if parser.event_shaped_ids:
        errors.append(
            Finding("event-shaped-ids", values={"ids": parser.event_shaped_ids})
        )
    return errors + reserved_marker_errors(parser)


def unpointable_blocks(parser: SourceDocument) -> list[Finding]:
    """Blocks whose element-selection target is missing or too broad. Advice, never a
    gate:
    references/page-authoring.md's "Stable anchors" states the id rule, and this
    is its feedback loop. The page that introduced addressable-element anchoring hit this
    failure itself — its code blocks carried no ids, so a comment aimed at one fell
    through to the enclosing section and read as the gesture being broken rather
    than the page being bare, and nothing anywhere said so.

    Prose and headings are named only when no enclosing id can receive the aim.
    A section or article is named outright; other whole-block targets below one
    only where their aim escapes to a sectioning element. The ancestor's tag
    stands in for tightness — a figure around a table, a card around a pre — which
    no static read can measure, so a page-wide <div id> also passes for aim enough and the advice
    stays quiet. Undercounting is the right error for advice: a miss costs one
    aim landing wide, noise costs the register its authority."""
    found = []
    for block in parser.authoring.bare_blocks:
        under = block["under"]
        if block["tag"] in ("section", "article"):
            found.append(found_at("unpointable-section", block))
        elif under is None:
            found.append(found_at("unpointable", block))
        elif block["tag"] in POINTABLE_TAGS and under[0] in SECTIONING_TAGS:
            found.append(found_at("unpointable-wide", block, enclosing=under[1]))
    return [finding.but(severity="advice") for finding in found]


def structure_errors(parser: SourceDocument) -> list[Finding]:
    """Structural complaints and source elements missing a required end tag."""
    errors = list(parser.authoring.errors)
    if parser.authoring.unclosed:
        elements = [
            {"tag": tag, "line": line} for tag, line in parser.authoring.unclosed
        ]
        errors.append(Finding("unclosed", values={"elements": elements}))
    return errors


def document_declaration_errors(parser: SourceDocument) -> list[Finding]:
    """Delivery declares the document's base, headers, and import map, and addresses
    every request Leaf's runtime makes by them. Markup that declares its own, in a page
    or in a message quoted into one, sends those requests elsewhere, navigates the page,
    or leaves its modules unable to resolve, and a message does so in every revision."""
    return [
        found_at("document-declaration", item)
        for item in parser.authoring.document_declarations
    ]


def page_boundary_errors(parser: SourceDocument) -> list[Finding]:
    """Authored content lies under the page's one main content boundary."""
    errors = []
    direct_heads = [
        line for line, is_direct in parser.authoring.head_elements if is_direct
    ]
    if (
        len(parser.authoring.head_lines) != 1
        or len(parser.authoring.head_elements) != 1
        or len(direct_heads) != 1
    ):
        errors.append(
            Finding(
                "head-count",
                values={
                    "tags": len(parser.authoring.head_lines),
                    "parsed": len(parser.authoring.head_elements),
                    "direct": len(direct_heads),
                },
            )
        )
    direct = [line for line, is_direct in parser.authoring.main_elements if is_direct]
    if (
        len(parser.authoring.body_lines) != 1
        or len(parser.authoring.main_elements) != 1
        or len(direct) != 1
    ):
        errors.append(
            Finding(
                "main-count",
                values={
                    "bodies": len(parser.authoring.body_lines),
                    "mains": len(parser.authoring.main_elements),
                    "direct": len(direct),
                },
            )
        )
    if parser.authoring.outside_main:
        errors.append(
            Finding("outside-main", values={"content": parser.authoring.outside_main})
        )
    return errors


def authored_allocation_errors(parser: SourceDocument) -> list[Finding]:
    """Authored allocations use the layer's named values: one of the names `allowed`
    lists, or, where it is None, a whole number of CSS pixels."""
    return [
        found_at(
            "allocation-value",
            item,
            attr=item["attr"],
            value=item["value"],
            allowed=list(values) if isinstance(values, tuple) else None,
        )
        for item in parser.authoring.authored_allocations
        if not allocation_valid(item["attr"], item["value"])
        for values in [AUTHORED_ALLOCATIONS[item["attr"]]]
    ]


def fragment_style_errors(parser: SourceDocument) -> list[Finding]:
    """A message may not dress the document it is put into.

    A version's <style> is the page's own, and the gates a version answers to read
    it as such — its syntax and the column it may not overflow. A fragment has no
    page of its own: the runtime parses an agent's reply markup into a template and
    moves those nodes into the message body, where a <style> among them becomes a
    document stylesheet like any other. `<style>main h1 { color: red !important
    }</style>` in a reply was accepted here and repainted the version's own heading,
    past every gate the same rule in a version answers to.

    Nothing is lost by refusing them. The layer already dresses a widget an agent
    sends — that is what an element declaration and its theme rules are for — and a rule
    of a message's own has nowhere honest to sit, because the message is not the
    page and its markup is frozen in the log where no version can revise it."""
    errors = []
    if any(sheet["css"].strip() for sheet in parser.authoring.style_blocks):
        errors.append(Finding("message-style", "<style>"))
    if links_with_rel(parser.authoring.links, "stylesheet"):
        errors.append(Finding("message-stylesheet", "<link>"))
    return errors + authored_allocation_errors(parser)


def text_media_errors(text: str, page_dir: Path) -> list[Finding]:
    """The same reference in a message's Markdown, which is the other way one arrives.

    Markup names a picture in an attribute or a stylesheet, where the parsed reading
    finds it (`revision_artifact.uncaptured_errors`); a message names one as a
    Markdown destination, which that reading cannot see — so an agent sending a
    screenshot came through the one door that never asked. `check_markup` runs only when `--markup` is
    given, and text on its own reached the log unread.

    A reference is a rendered link or image destination, never a scan of the words.
    Parsing the Markdown resolves referenced definitions and leaves fenced examples
    and unused definitions as text, so neither asks for a file the page will not load."""
    refs = {
        url
        for token in block_markdown().parse(text)
        for child in token.children or ()
        if child.type in {"link_open", "image"}
        if (url := child.attrGet("href" if child.type == "link_open" else "src"))
        and url.startswith(f"/{MEDIA_DIR}/")
    }
    return unanswered_media(refs, page_dir)


def unanswered_media(refs, page_dir: Path) -> list[Finding]:
    """Every `/media/…` reference the page will not answer: one whose name the server
    never serves (`schema.MEDIA_DIGEST`), whatever the directory holds under it, and
    one the directory has not got."""
    errors = []
    for ref in sorted(refs):
        path = urlsplit(ref).path
        if not SERVED_PATH.fullmatch(path):
            errors.append(Finding("unserved-media", values={"ref": ref}))
        elif not (page_dir / path.lstrip("/")).is_file():
            errors.append(Finding("missing-media", values={"ref": ref}))
    return errors
