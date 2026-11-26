"""Shared structural and authored-markup validation rules."""

import json
from collections import Counter

from leaf.base.findings import Finding, element_at
from leaf.base.schema import ASSETS
from leaf.source.passages import markdown_dialect
from leaf.source.structure import (
    AUTHORED_ALLOCATIONS,
    SECTION_TAGS,
    SECTIONING_TAGS,
    WHOLE_BLOCK_TAGS,
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


# Each name a `language-…` class may give a language Leaf colours, mapped to its
# grammar: each grammar's name and Shiki's aliases for it, which build/vendor.mjs writes
# into the library's table as one line of JSON (`syntaxLanguageNames`), and
# syntax-tokens.js reads a class by.
_NAMES_LINE = "export const syntaxLanguageNames = "
COLOURED_LANGUAGES: dict[str, str] = next(
    json.loads(line.removeprefix(_NAMES_LINE).removesuffix(";"))
    for line in (ASSETS / "runtime" / "lib" / "syntax-languages.js")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.startswith(_NAMES_LINE)
)
# The language a formula's LaTeX is written in, as GitHub's and remark-math's Markdown
# name it: the browser typesets a `<code>` naming it rather than colouring it
# (runtime/readings/formulas.js), and leaves a widget naming it uncoloured.
FORMULA_LANGUAGE = "math"


def language_advice(parser) -> list[Finding]:
    """Each `language-…` class, on any element, naming a language Leaf neither colours
    nor typesets, so its code stays the colour of its ink. Advice, not a gate: the name
    may be a misspelling, which nothing else on the page says, or a language Leaf has
    no grammar for, which the class still names truly to any other reader."""
    return [
        Finding(
            "uncoloured-language",
            element_at(tag),
            {
                "line": line,
                "language": name,
                "names": sorted(set(COLOURED_LANGUAGES.values())),
            },
        )
        for tag, line, name in parser.authoring.code_languages
        if name not in COLOURED_LANGUAGES
        and (name != FORMULA_LANGUAGE or tag != "code")
    ]


# HTML's elements whose text shows as written: code, and text that no markup inside
# could format, as an option's or the title's.
LITERAL_TEXT_TAGS = frozenset(
    {"code", "pre", "kbd", "samp", "script", "style", "textarea", "title", "option"}
)


def markdown_advice(parser: SourceDocument) -> list[Finding]:
    """Each element whose own text Leaf's Markdown, as a message reads it, would format
    as a code span, `**` bold or a link, outside the elements whose text
    shows as written (`LITERAL_TEXT_TAGS`). HTML reads no Markdown, so the page shows
    the backticks, asterisks and brackets. Agents write Markdown in chat and in every
    thread message, and carry text from Markdown sources, such as an issue's title or
    a subagent's report, into a page's HTML, where nothing else in their path reports
    the syntax left showing. `*` and `_` emphasis is left out, since paths, globs and
    error text use those marks in their own sense. Advice, since the author may mean
    the syntax as text, which the words say how to mark.

    This reads the page's words for something other than quoting, anchoring or
    showing them, an exception to root `AGENTS.md`'s "Read what the page states". It
    decides no fact Leaf holds about the page and changes nothing the page does."""

    def formats(text: str) -> bool:
        # Each construct spells one of these, and most text holds none, which saves
        # the parse.
        if "`" not in text and "**" not in text and "](" not in text:
            return False
        return any(
            token.type == "code_inline"
            or (token.type == "strong_open" and token.markup == "**")
            or (
                token.type == "link_open"
                and token.markup not in {"linkify", "autolink"}
            )
            for token in markdown_dialect(True).parseInline(text)[0].children or ()
        )

    elements = []

    def visit(node: dict) -> None:
        if node["tag"] in LITERAL_TEXT_TAGS:
            return
        if any(isinstance(child, str) and formats(child) for child in node["content"]):
            elements.append({"tag": node["tag"], "line": node["line"]})
        for child in node["content"]:
            if isinstance(child, dict):
                visit(child)

    # A fragment, as a message's HTML, holds text between its top-level elements.
    for node in parser.authoring.content:
        if isinstance(node, dict):
            visit(node)
    if not elements:
        return []
    return [Finding("literal-markdown", values={"elements": elements})]


def markup_advice(parser) -> list[Finding]:
    """The advice any authored markup takes that reads only the markup
    (`instances.markup_findings`): a class naming a language Leaf doesn't colour
    (`language_advice`), and Markdown an HTML element shows as typed
    (`markdown_advice`). Which blocks a comment can aim at (`unpointable_blocks`) and
    where an allocation holds (`instances.inert_allocation_advice`) are a page's
    alone."""
    return [*language_advice(parser), *markdown_advice(parser)]


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
    where their aim lands wide. It does on a sectioning element, and on any element
    that takes the aim of two or more of them, so a comment there can't say which
    it is about, as one id on a table of screenshots leaves each screenshot. A
    whole block that holds another, or anything with an id, is left to what it
    holds: a table that only arranges its screenshots is named by them, and a
    figure whose picture has an id needs none. An element that takes one block's
    aim is read as tight around it — a figure around a table, a card around a pre —
    which no static read can measure, so a page-wide <div id> around one block also
    passes for aim enough and the advice stays quiet. Undercounting is the right
    error for advice: a miss costs one aim landing wide, noise costs the register
    its authority.

    Each reason is one finding listing its blocks in `values.elements` (tag and line,
    and for a wide aim the enclosing id), so a page with no ids reads one line of
    advice with one fix, not a line per block."""
    blocks = [block for block in parser.authoring.bare_blocks if not block["holds"]]
    aims = Counter(
        block["under"] for block in blocks if block["tag"] in WHOLE_BLOCK_TAGS
    )
    found: dict[str, list[dict]] = {}
    for block in blocks:
        under = block["under"]
        if block["tag"] in SECTION_TAGS:
            code, extra = "unpointable-section", {}
        elif under is None:
            code, extra = "unpointable", {}
        elif block["tag"] in WHOLE_BLOCK_TAGS and (
            under[0] in SECTIONING_TAGS or aims[under] > 1
        ):
            code, extra = "unpointable-wide", {"enclosing": under[1]}
        else:
            continue
        found.setdefault(code, []).append(
            {"tag": block["tag"], "line": block["line"], **extra}
        )
    return [
        Finding(code, values={"elements": elements}) for code, elements in found.items()
    ]


def repair_errors(parser: SourceDocument) -> list[Finding]:
    """Where the HTML parser had to repair the markup, so the tree it read is not the
    one written: a non-void element written self-closing (`self-closing`), and source
    elements missing a required end tag (`unclosed`)."""
    errors = list(parser.authoring.self_closing)
    if parser.authoring.unclosed:
        elements = [
            {"tag": tag, "line": line} for tag, line in parser.authoring.unclosed
        ]
        errors.append(Finding("unclosed", values={"elements": elements}))
    return errors


def structure_errors(parser: SourceDocument) -> list[Finding]:
    """The parser's complaints about the markup: an unnamed sample, a `<noscript>`,
    and its repairs (`repair_errors`)."""
    return [*parser.authoring.errors, *repair_errors(parser)]


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
    """Delivery and export need explicit head and body wrappers, which refuse, and a
    Layout arranges the one `main` directly under `body`, which a page may leave out
    or double, so its count is advice."""
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
    if len(parser.authoring.body_lines) != 1:
        errors.append(
            Finding("body-count", values={"tags": len(parser.authoring.body_lines)})
        )
    direct = [line for line, is_direct in parser.authoring.main_elements if is_direct]
    if len(parser.authoring.main_elements) != 1 or len(direct) != 1:
        errors.append(
            Finding(
                "main-count",
                values={
                    "mains": len(parser.authoring.main_elements),
                    "direct": len(direct),
                },
            )
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
    }</style>` in a reply would repaint the version's own heading, past every gate
    the same rule in a version answers to.

    Nothing is lost by refusing them. The layer already dresses a widget an agent
    sends — that is what an element declaration and its theme rules are for — and a rule
    of a message's own has nowhere honest to sit, because the message is not the
    page and its markup stands in the log, where no version can revise it."""
    errors = []
    if any(sheet["css"].strip() for sheet in parser.authoring.style_blocks):
        errors.append(Finding("message-style", "<style>"))
    if links_with_rel(parser.authoring.links, "stylesheet"):
        errors.append(Finding("message-stylesheet", "<link>"))
    return errors + authored_allocation_errors(parser)
