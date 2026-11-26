"""CSS readings of authored HTML.

Delivery's reader (`_read_css`) parses a sheet once for its text and parsing mode,
whichever address delivers it, and reads from that parse what the sheet loads
(`css_dependencies`), what no address can deliver in it, and the sheet re-addressed
(`rewrite_css`). Capture, export, delivery and layer composition all read a sheet
through it.

Bounded readings of exact CSS text keep state requests from reparsing unchanged
stylesheets. Their results are read-only; edits select a new cache entry.

Each stylesheet is parsed on its own, matching browser EOF recovery. Composition
serializes that reading before adding wrappers, so a missing delimiter cannot put
the wrapper or a later sheet inside this sheet's last block, string or comment.
"""

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from leaf.base.findings import Finding
from leaf.source.capture_refusals import ArtifactError, capture_finding


def css_block(css):
    """What a block holds: the declarations it states, and the rules nested inside it. A
    style="" attribute is a block written without the braces around it."""
    import tinycss2

    return tinycss2.parse_blocks_contents(css, skip_comments=True, skip_whitespace=True)


@lru_cache(maxsize=32)
def css_stylesheet(css: str):
    """One independent stylesheet's read-only syntax tree, including EOF recovery,
    without its comments, which no reading needs and no page receives."""
    import tinycss2

    return tinycss2.parse_stylesheet(css, skip_comments=True)


def dropped_css(css: str, sheet: str, *, block=False) -> tuple[Finding, ...]:
    """Each declaration or nested rule a browser drops from a sheet that delivery's
    reader reads whole (`_read_css`), as `css-dropped`.

    The reader parses a stylesheet into its rules and their tokens, and refuses
    what it can't read: an error token anywhere, or a malformed top-level rule. A
    rule's block it keeps as tokens, which a browser parses as declarations and
    nested rules, dropping each one that doesn't parse, such as `broken;` in
    `p { color: red; broken; }`. Those are what this reports, so no problem is
    reported by both. A style attribute (`block`) the reader parses as its list of
    declarations, so it holds nothing more to drop. `sheet` names the sheet as its
    author finds it: a file, the page's <style>, or one element's style attribute.
    Advice, by the maintainer's decision: delivery reads such a sheet whole, so
    refusing it protects nothing of Leaf's, and the browser forgives the author's
    mistake."""
    if block:
        return ()
    errors = {}

    def walk(nodes):
        for node in nodes:
            if node.type in {"qualified-rule", "at-rule"} and node.content is not None:
                inner = css_block(node.content)
                for item in inner:
                    if item.type == "error":
                        key = (item.source_line, item.source_column, item.message)
                        errors.setdefault(
                            key,
                            Finding(
                                "css-dropped",
                                values={
                                    "sheet": sheet,
                                    "row": item.source_line,
                                    "column": item.source_column,
                                    "message": item.message,
                                },
                            ),
                        )
                walk(inner)

    walk(css_stylesheet(css))
    return tuple(errors.values())


# How a sheet or module sets a custom property by name: a declaration, an `@property`,
# or the name as a string, as `style.setProperty("--x", …)` writes it. A template
# literal that builds names from a prefix (`--lf-pane-${side}`) sets every name with
# that prefix.
_SETS_PROPERTY = re.compile(
    r"(--[\w-]+)\s*:|@property\s+(--[\w-]+)|[\"'`](--[\w-]+)[\"'`]"
)
_BUILDS_PROPERTY = re.compile(r"`(--[\w-]+)\$\{")


def set_properties(texts: Iterable[str]) -> tuple[frozenset[str], tuple[str, ...]]:
    """The custom properties these sheets and modules set by name, and the prefixes
    they build names from. A reading of text, not of a parsed sheet, so it over-counts:
    a name a comment mentions counts as set, and only a read nothing names is missed."""
    names, prefixes = set(), set()
    for text in texts:
        names |= {"".join(match) for match in _SETS_PROPERTY.findall(text)}
        prefixes |= set(_BUILDS_PROPERTY.findall(text))
    return frozenset(names), tuple(sorted(prefixes))


def unguarded_reads(
    css: str, is_set: Callable[[str], bool]
) -> Iterator[tuple[str, int]]:
    """Each `var(--name)` in a declaration's value that computes to nothing, as its name
    and line: one with no fallback whose name `is_set` refuses. Such a declaration is
    invalid at computed-value time, so the property falls back to what it inherits or
    its initial value, and the page shows no sign of it. A fallback is read only when
    its own `var()`'s name is unset, since a browser substitutes it only then: in
    `var(--present, var(--missing))` nothing reads `--missing` while `--present` is
    set. A rule's prelude, such as `@supports (color: var(--probe))`, tests syntax
    rather than reading the property, so only declarations, at any depth of nested
    rules, are read."""

    def values(nodes):
        for node in nodes:
            if node.type == "function" and node.lower_name == "var":
                arguments = [
                    item
                    for item in node.arguments
                    if item.type not in ("whitespace", "comment")
                ]
                if arguments and arguments[0].type == "ident":
                    name = arguments[0].value
                    if is_set(name):
                        continue
                    if len(arguments) == 1:
                        yield name, node.source_line
                        continue
            for part in ("content", "arguments"):
                inner = getattr(node, part, None)
                if isinstance(inner, list):
                    yield from values(inner)

    def rules(nodes):
        for node in nodes:
            if node.type == "declaration":
                yield from values(node.value)
            elif (
                node.type in ("qualified-rule", "at-rule") and node.content is not None
            ):
                yield from rules(css_block(node.content))

    yield from rules(css_stylesheet(css))


def _css_meaningful(tokens) -> list:
    return [item for item in tokens if item.type not in {"whitespace", "comment"}]


def _is_stylesheet_url(url: str) -> bool:
    """Whether an `@import` names a stylesheet. A URL no sheet may load is refused
    where the sheet's references are resolved, so it isn't refused here."""
    # Imported here: the URL reader loads a WHATWG URL parser, which `package run`,
    # reading only a sheet's declarations, never needs.
    from leaf.source.resource_urls import dependency_reference

    try:
        reference = dependency_reference(url, "/index.css")
    except ArtifactError:
        return True
    return reference is None or Path(reference[0]).suffix == ".css"


def _css_references(tokens, refused: list[Finding], invalid: list):
    """Yield each token in parsed CSS whose value is a URL the stylesheet loads, add
    each finding about one that it doesn't yield to `refused`, whose code says whether
    it refuses (`css-import`) or advises (`css-url`), and each parse error to
    `invalid`, which `_read_css` reports as the sheet's syntax error rather than a
    refused URL.

    Those are a `url()` in either spelling, a string argument of `image-set()`, and
    the string form of a top-level `@import`. An `@import` nested in a block is
    ignored in either spelling, as a browser ignores it: tinycss2 reads one as a bare
    at-keyword inside the block's content rather than as a rule, and everything up to
    its `;` is skipped. The tokens are the parser's own, so a caller that rewrites one
    and serializes the tree changes that URL and nothing else.
    """
    nested_import = False
    for token in tokens:
        if nested_import:
            nested_import = not (token.type == "literal" and token.value == ";")
            continue
        if token.type == "at-keyword" and token.lower_value == "import":
            nested_import = True
            continue
        if token.type == "error":
            invalid.append(token)
        elif token.type == "url":
            yield token
        elif token.type == "function" and token.lower_name == "url":
            values = _css_meaningful(token.arguments)
            if len(values) == 1 and values[0].type == "string":
                yield values[0]
            # A parse error among its arguments is the sheet's syntax error, which
            # the walk into them below records, so the url() isn't reported too.
            elif not any(value.type == "error" for value in values):
                refused.append(
                    Finding(
                        "css-url",
                        values={
                            "row": token.source_line,
                            "column": token.source_column,
                        },
                    )
                )
        elif token.type == "function" and token.lower_name in {
            "image-set",
            "-webkit-image-set",
        }:
            yield from (item for item in token.arguments if item.type == "string")
        elif token.type == "at-rule" and token.lower_at_keyword == "import":
            # The prelude is read here once, and a refused import loads nothing, so
            # its URLs are neither followed nor refused again.
            values = _css_meaningful(token.prelude)
            before = (len(refused), len(invalid))
            imported = list(_css_references(token.prelude, refused, invalid))
            if values and values[0].type == "string":
                imported.insert(0, values[0])
            if (len(refused), len(invalid)) != before:
                continue
            if not imported or not _is_stylesheet_url(imported[0].value):
                refused.append(capture_finding("css-import"))
                continue
            yield from imported
            continue
        for attribute in ("prelude", "content", "arguments", "value"):
            nested = getattr(token, attribute, None)
            if isinstance(nested, list):
                yield from _css_references(nested, refused, invalid)


def _parse_css(source: str, declarations: bool):
    """A stylesheet, or with `declarations` the body of a `style` attribute."""
    import tinycss2

    if declarations:
        return tinycss2.parse_declaration_list(source)
    return tinycss2.parse_stylesheet(source)


@dataclass(frozen=True)
class _CssReading:
    """One stylesheet's parse, kept as its serialization around the URLs it loads.

    `refused` holds what the walk refused, which no address can deliver, and
    `invalid` each syntax error in the parse, which none can deliver either: this
    reader is the one judge of what a sheet must not hold, and `dropped_css`
    reports only what it reads but a browser drops. `advice` holds what the walk
    found that delivery carries as written but a browser drops, such as a url() of
    two values (`css_drops`).
    `references` holds each URL token as `_css_references` finds it, as its value,
    its written representation and its type. `segments` is the serialized sheet
    split around them, one more segment than references, or None where the split
    cannot be made (`_read_css`), and `order` names the reference between each pair
    of segments: the walk visits an `image-set`'s strings before its `url()`s, so
    the order a sheet writes its URLs in is not the order they are found in.
    Joining the segments with each reference's representation is the serialization
    `rewrite_css` would write with that reference changed, so a re-addressing costs
    a join rather than a parse."""

    references: tuple[tuple[str, str, str], ...]
    segments: tuple[str, ...] | None
    order: tuple[int, ...] = ()
    refused: tuple[Finding, ...] = ()
    invalid: tuple[Finding, ...] = ()
    advice: tuple[Finding, ...] = ()


# Delimits each URL in a sheet's serialization while `_read_css` splits it. Private
# use code points, so a sheet that contains one is read without a split.
_CSS_MARK = ("", "")


@lru_cache(maxsize=512)
def _read_css(source: str, declarations: bool) -> _CssReading:
    """Parse a stylesheet, kept by its text and parsing mode (`declarations`) rather than
    by the address that delivers it.

    A sheet's text is the same for every page that selects the same layer and every
    revision that captured it, while the address it is delivered at names one
    revision. Parsing the composed theme takes a few hundred milliseconds, which a
    parse keyed on the address paid again for every new revision's first document.
    The bound is in entries: a document's `style` attributes are sheets too, and a
    few large layer sheets must outlast a page's worth of them."""
    tokens = _parse_css(source, declarations)
    problems = []
    invalid = []
    found = list(_css_references(tokens, problems, invalid))
    refused = [problem for problem in problems if problem.refuses]
    advice = tuple(problem for problem in problems if not problem.refuses)
    references = tuple(
        (token.value, token.representation, token.type) for token in found
    )
    # A refused or invalid sheet is never delivered (`rewrite_css`), and its parse
    # may hold nodes tinycss2 can't serialize, so it isn't split.
    if (
        refused
        or invalid
        or any(mark in source for mark in _CSS_MARK)
        or len(set(map(id, found))) != len(found)
    ):
        return _CssReading(
            references,
            None,
            refused=tuple(refused),
            advice=advice,
            invalid=tuple(
                {
                    (node.source_line, node.source_column, node.message): Finding(
                        "css-syntax",
                        values={
                            "row": node.source_line,
                            "column": node.source_column,
                            "message": node.message,
                        },
                    )
                    for node in invalid
                }.values()
            ),
        )
    for index, token in enumerate(found):
        token.representation = f"{_CSS_MARK[0]}{index}{_CSS_MARK[1]}"
    import tinycss2

    parts = re.split(
        f"{_CSS_MARK[0]}([0-9]+){_CSS_MARK[1]}", tinycss2.serialize(tokens)
    )
    order = tuple(int(index) for index in parts[1::2])
    if sorted(order) != list(range(len(found))):
        return _CssReading(references, None, advice=advice)
    return _CssReading(references, tuple(parts[0::2]), order, advice=advice)


def css_dependencies(
    source: str,
    sheet: str,
    declarations: bool = False,
    refused: list[Finding] | None = None,
) -> tuple[str, ...]:
    """The URLs a stylesheet loads, collecting what delivery's reader can't read in
    it as `resource_urls.javascript_imports` does: each syntax error, and each URL no
    address can deliver. `sheet` names the stylesheet as its author finds it: a file's
    path, the page's <style>, or one element's style attribute. The parse is shared by
    every sheet with the same text (`_read_css`), so a refusal of the text is told its
    sheet here."""
    reading = _read_css(source, declarations)
    problems = [
        *(finding.but(values={"sheet": sheet}) for finding in reading.invalid),
        *(finding.but(values={"file": sheet}) for finding in reading.refused),
    ]
    if refused is not None:
        refused.extend(problems)
    elif problems:
        raise ArtifactError(problems)
    return tuple(value for value, _, _ in reading.references)


def css_drops(
    source: str, sheet: str, declarations: bool = False
) -> tuple[Finding, ...]:
    """What a browser drops from a sheet delivery's reader reads whole: what the
    reader's walk advises (`_CssReading.advice`) and what `dropped_css` finds,
    and nothing from one it refuses, whose syntax error `css_dependencies` reports
    and whose later rules a reparse would only misread. `sheet` names it as
    `css_dependencies` does."""
    reading = _read_css(source, declarations)
    if reading.invalid:
        return ()
    return (
        *(finding.but(values={"sheet": sheet}) for finding in reading.advice),
        *dropped_css(source, sheet, block=declarations),
    )


def css_syntax_errors(
    source: str, sheet: str, declarations: bool = False
) -> list[Finding]:
    """Every syntax error in a stylesheet: what delivery's reader can't read
    (`css-syntax`), or else what it reads but a browser drops (`css_drops`).
    `sheet` names it as `css_dependencies` does."""
    return [
        *(
            finding.but(values={"sheet": sheet})
            for finding in _read_css(source, declarations).invalid
        ),
        *css_drops(source, sheet, declarations),
    ]


def rewrite_css(source: str, address, *, declarations: bool = False) -> str:
    """Re-address every URL `source` loads through `address`, the rest byte-for-byte.

    `address` takes a URL as written and returns its replacement, or None when
    unavailable: the containing declaration or import is then omitted. Other
    declarations, including the enclosing layout rules, remain.
    Delivery and export re-address through this, and capture collects its
    dependencies from the same `_css_references`, so all three agree on which URLs a
    sheet has.
    """
    from tinycss2.serializer import serialize_string_value

    reading = _read_css(source, declarations)
    if reading.refused or reading.invalid:
        raise ArtifactError(
            [
                *(
                    finding.but(values={"sheet": "stylesheet"})
                    for finding in reading.invalid
                ),
                *reading.refused,
            ]
        )
    targets = {value: address(value) for value, _, _ in reading.references}
    if all(target == value for value, target in targets.items()):
        return source
    if reading.segments is not None and None not in targets.values():
        written = [reading.segments[0]]
        for index, segment in zip(reading.order, reading.segments[1:], strict=True):
            value, representation, kind = reading.references[index]
            target = targets[value]
            if target != value:
                quoted = '"' + serialize_string_value(target) + '"'
                representation = f"url({quoted})" if kind == "url" else quoted
            written.extend((representation, segment))
        return "".join(written)
    return _rewrite_parsed(source, targets, declarations)


def _rewrite_parsed(source: str, targets: dict, declarations: bool) -> str:
    """`rewrite_css` over a fresh parse, for an omitted URL or an unsplit sheet, which
    `rewrite_css` has read with nothing refused."""
    import tinycss2
    from tinycss2.serializer import serialize_string_value

    tokens = _parse_css(source, declarations)
    ignored = []
    omitted = {reference for reference, value in targets.items() if value is None}

    def available(entries):
        kept = []
        for entry in entries:
            # A declaration the browser drops, such as `broken;`, parses as an error
            # node, which can't be serialized; drop it as the browser does.
            if entry.type == "error":
                continue
            if entry.type == "declaration" or (
                entry.type == "at-rule" and entry.lower_at_keyword == "import"
            ):
                if any(
                    token.value in omitted
                    for token in _css_references([entry], ignored, ignored)
                ):
                    continue
            elif getattr(entry, "content", None) is not None:
                children = available(tinycss2.parse_blocks_contents(entry.content))
                entry.content = tinycss2.parse_component_value_list(
                    tinycss2.serialize(children)
                )
            kept.append(entry)
        return kept

    if omitted:
        tokens = available(tokens)
    for token in list(_css_references(tokens, ignored, ignored)):
        value = targets[token.value]
        if value == token.value:
            continue
        quoted = '"' + serialize_string_value(value) + '"'
        token.representation = f"url({quoted})" if token.type == "url" else quoted
        token.value = value
    return tinycss2.serialize(tokens)
