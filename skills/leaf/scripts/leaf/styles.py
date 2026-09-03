"""CSS and readable-column readings of authored HTML.

Bounded readings of exact CSS text keep state requests from reparsing unchanged
stylesheets. Their results are read-only; edits select a new cache entry.
"""

from functools import lru_cache

import tinycss2

from .structure import OVERFLOW_PROPS, _StructParser

# ---------- the readable column ----------
# A rule, a style="" and a width="" are the three places a document states a width.
# The first two are CSS, so tinycss2 reads them; the third is an attribute, so the
# markup parser does.
#
# Three patterns over the file's text came first, and each answered something adjacent
# to the question asked: the document read as a stylesheet handed a screenshot's base64
# to the rule walker, `width` needed a lookbehind to exclude `max-width` because it
# matched a name instead of reading a property, and the scan for `style=""` never saw
# one written with the other quote. Hand-rolling the parser is the same mistake a level
# down, and harder to see, because a hand-rolled parser is right about the grammar it
# was written against: the brace walk those patterns became knew that a comment's braces
# are not braces, and still read a `}` inside `content: "}"` as the end of the block,
# dropping every declaration after it in that rule; still read a rule holding both
# declarations and a nested rule as declaring nothing of its own; and still told a fixed
# `900px` from a `calc(100% - 900px)` by asking whether the string ended in `px`, which
# `900px !important` does not. CSS has no parser in the stdlib, so the dependency is a
# real cost — one more wheel behind every `version check`, ~6ms to read the theme — and
# it buys the grammar whole rather than one bug's worth at a time.


def css_block(css):
    """What a block holds: the declarations it states, and the rules nested inside it. A
    style="" attribute is a block written without the braces around it."""
    return tinycss2.parse_blocks_contents(css, skip_comments=True, skip_whitespace=True)


@lru_cache(maxsize=32)
def css_rules(css: str) -> tuple:
    """(selector, block, conditional) per qualified rule, at every depth — a rule that
    holds both declarations and a nested rule states one of its own. `conditional` is
    true for a rule inside an at-rule, which applies only when a condition this check
    never evaluates holds: `@media print`, a viewport query. Nesting alone is not a
    condition, so a rule nested in a conditional one is conditional and no more."""
    return tuple(
        _rules(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True))
    )


def _css_unclosed_blocks(css: str) -> int:
    """How many blocks a stylesheet leaves open at end of file.

    The CSS parser auto-closes these (so tinycss2 reports no error), which is
    exactly what makes one dangerous here: stylesheets are layer sources that
    concatenate, so a block left open swallows every rule after it — the rest
    of the file's and every later layer's — into its own scope. Counted
    outside comments and strings; an over-closed sheet floors at zero, since
    the stray brace is a parse error tinycss2 already names."""
    depth = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end == -1 else end + 2
        elif ch in "\"'":
            quote = ch
            i += 1
            while i < len(css) and css[i] not in (quote, "\n"):
                i += 2 if css[i] == "\\" else 1
            i += 1
        else:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            i += 1
    return depth


@lru_cache(maxsize=32)
def css_syntax_errors(css: str, source: str, *, block=False) -> tuple[str, ...]:
    """Every parse error in a stylesheet or declaration block, including nested rules."""
    parse = (
        css_block
        if block
        else lambda value: tinycss2.parse_stylesheet(
            value, skip_comments=True, skip_whitespace=True
        )
    )
    errors = []
    seen = set()
    if not block and (depth := _css_unclosed_blocks(css)):
        errors.append(
            f"{source}: {depth} block(s) left open at end of file — every rule "
            "after the unclosed brace, this stylesheet's or a later layer's, "
            "lands inside its scope"
        )

    def record(node):
        key = (node.source_line, node.source_column, node.message)
        if key in seen:
            return
        seen.add(key)
        errors.append(
            f"{source} syntax error at "
            f"{node.source_line}:{node.source_column}: {node.message}"
        )

    def walk_tokens(tokens):
        for token in tokens:
            if token.type == "error":
                record(token)
            for attr in ("arguments", "content"):
                nested = getattr(token, attr, None)
                if isinstance(nested, list):
                    walk_tokens(nested)

    def walk_rules(nodes):
        for node in nodes:
            if node.type == "error":
                record(node)
            for attr in ("prelude", "value"):
                tokens = getattr(node, attr, None)
                if isinstance(tokens, list):
                    walk_tokens(tokens)
            if node.type in {"qualified-rule", "at-rule"} and node.content is not None:
                walk_tokens(node.content)
                walk_rules(css_block(node.content))

    walk_rules(parse(css))
    return tuple(errors)


def _rules(nodes, conditional=False):
    """`nodes` and every rule nested inside them, as (selector, block, conditional)."""
    for node in nodes:
        if node.type == "qualified-rule":
            block = css_block(node.content)
            yield tinycss2.serialize(node.prelude).strip(), block, conditional
            yield from _rules(block, conditional)
        elif node.type == "at-rule" and node.content:
            yield from _rules(css_block(node.content), True)


def _number(text: str):
    """`text` as a number, or None when it is not one. A width="" attribute states a
    bare count of pixels, so it has no unit for the CSS parser to read."""
    try:
        return float(text)
    except ValueError:
        return None


def _lone_px(value):
    """The pixel length a value states outright, or None. A value keeps the whitespace
    around it, which is a token like any other and not part of what the value says."""
    tokens = [t for t in value if t.type != "whitespace"]
    if (
        len(tokens) == 1
        and tokens[0].type == "dimension"
        and tokens[0].lower_unit == "px"
    ):
        return tokens[0].value
    return None


def root_tokens(css: str) -> dict:
    """The pixel lengths a stylesheet states outright as custom properties on the root.

    A width naming one of these states a number as certainly as writing it out, so the
    readings below resolve it. Only the root, and only unconditionally: a token set on
    some element or inside a query is that element's or that condition's, and taking it
    for the page's would be the same reading the column refuses a media query for.

    One level. A token defined as another token is a stylesheet answering a different
    question than these readings ask, and following it would be a resolver rather than
    the two facts this needs."""
    tokens = {}
    for selector, block, conditional in css_rules(css):
        if conditional or selector.strip() != ":root":
            continue
        for declaration in block:
            if declaration.type == "declaration" and declaration.name.startswith("--"):
                px = _lone_px(declaration.value)
                if px is not None:
                    tokens[declaration.name] = px
    return tokens


def _px(declaration, tokens: dict | None = None):
    """The pixel length a declaration states, or None where it states something else: a
    percentage, a vw, a calc() with a px term inside it. Only a fixed pixel length is a
    hard overflow, and only a lone length is fixed.

    A lone `var()` naming a root token is one too. The stylesheet stated the number and
    then named it, and a check that stopped at the name would read the fallback width
    for a theme that had tidied its own constants into `:root` — which is a check that
    quietly stops measuring the moment the file it measures gets tidier. The `var()`'s
    own fallback answers where nothing declared the token, which is what the browser
    would use."""
    value = [t for t in declaration.value if t.type != "whitespace"]
    px = _lone_px(value)
    if px is not None:
        return px
    if len(value) == 1 and value[0].type == "function" and value[0].lower_name == "var":
        args = [t for t in value[0].arguments if t.type != "whitespace"]
        if args and args[0].type == "ident" and args[0].value.startswith("--"):
            named = (tokens or {}).get(args[0].value)
            if named is not None:
                return named
            if len(args) > 2 and args[1] == ",":
                return _lone_px(args[2:])
    return None


def _px_widths(declarations, props: tuple, tokens: dict | None = None):
    """(property, pixels) per declaration in `props` pinned to a fixed pixel length."""
    for declaration in declarations:
        if declaration.type == "declaration" and declaration.lower_name in props:
            px = _px(declaration, tokens)
            if px is not None:
                yield declaration.lower_name, px


# What a page is measured against when no rule claims the column. A default, not a
# reading: it is the width every other check's number comes from, so a page that says
# nothing still gets measured rather than silently passing.
COLUMN_FALLBACK = 780


def _declares_column(block) -> bool:
    """Whether a rule says it draws the readable column, in the block that draws it.

    A stylesheet knows which of its rules is the column, and this asks it. The rule
    setting the column's max-width sets `--lf-column: 1` beside it, so the cascade wins
    the two together and the claim cannot drift from the width — the same shape as
    `--lf-frame`, which a box declares where it draws its frame.

    Before this, seven container names stood in for the answer: `main`, `body`,
    `article`, `.container`, `.wrap`, `.content`, `.page`. A name list is wrong in both
    directions at once. Too wide, because the column is the baseline every other width
    on the page is measured against, and any rule that happened to be spelled `.content`
    moved it — `.content { max-width: 1400px }` doubles the number and takes the
    overflow check quiet, which reads as a page with nothing wrong in it. Too narrow,
    because a page whose column is `.prose` was measured against the fallback instead
    and failed for widths that fit. Neither shows up as an error; both show up as a
    check that has stopped asking."""
    return any(
        declaration.type == "declaration"
        and declaration.name == "--lf-column"
        and tinycss2.serialize(declaration.value).strip() == "1"
        for declaration in block
    )


def _column_width(page_css: str, theme_css: str) -> int:
    """The readable-column width, from the max-width of the rule claiming the column.
    A page's own <style> wins over the vendored theme, which wins over the fallback.

    Only what a stylesheet states outright counts: a column is the baseline everything
    else is measured against, so it has to be certain, and a conditional rule states a
    column for some condition rather than for the page. Reading them too let a page
    disable this check with one line of print CSS — `@media print { main { max-width:
    2000px } }` measured every screen element against 2000px."""
    for css in (page_css, theme_css):
        tokens = root_tokens(css)
        widths = [
            px
            for _, block, conditional in css_rules(css)
            if not conditional and _declares_column(block)
            for _, px in _px_widths(block, ("max-width",), tokens)
        ]
        if widths:
            return int(max(widths))
    return COLUMN_FALLBACK


def _overwide_elements(
    parser: _StructParser, column: int, theme_tokens: dict | None = None
) -> list:
    """Everything a version pins wider than the column: its own rules, its inline
    styles, and the width="" attributes that count as pixels.

    A conditional rule counts here, where it cannot define the column: a pin is a risk
    rather than a baseline, and it overflows whenever its condition holds.

    A width naming a token resolves against the page's own root first and the layer's
    behind it, which is the order the cascade reads them in. A page pinning
    `var(--wide)` is stating the layer's number, and a reading that knew only the page's
    own tokens would let the vocabulary's own widths through unmeasured."""
    hits = []
    tokens = {**(theme_tokens or {}), **root_tokens(parser.css)}
    for selector, block, _ in css_rules(parser.css):
        for prop, px in _px_widths(block, OVERFLOW_PROPS, tokens):
            if px > column:
                hits.append(
                    f"rule `{selector}` sets {prop}: {px:g}px (column is {column}px)"
                )
    for style in parser.inline_styles:
        for prop, px in _px_widths(css_block(style), OVERFLOW_PROPS, tokens):
            if px > column:
                hits.append(f"inline style {prop}: {px:g}px (column is {column}px)")
    for tag, value in parser.attr_widths:
        px = _number(value)
        if px is not None and px > column:
            hits.append(f'<{tag} width="{value}"> exceeds column ({column}px)')
    return hits


PRESENTATION_PROPERTIES = {
    "all",
    "display",
    "interactivity",
    "opacity",
    "pointer-events",
    "visibility",
}


def inline_presentation_override_errors(parser: _StructParser) -> list:
    """Inline importance outranks even the theme's first important cascade layer."""
    errors = []
    for number, style in enumerate(parser.inline_styles, 1):
        for declaration in css_block(style):
            if (
                declaration.type == "declaration"
                and declaration.important
                and declaration.lower_name in PRESENTATION_PROPERTIES
            ):
                errors.append(
                    f"inline style #{number} makes protected presentation property "
                    f"{declaration.lower_name} important"
                )
    return errors
