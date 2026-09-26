"""CSS readings of authored HTML.

Bounded readings of exact CSS text keep state requests from reparsing unchanged
stylesheets. Their results are read-only; edits select a new cache entry.
"""

from collections.abc import Mapping
from functools import lru_cache

import tinycss2

from .structure import SourceDocument

# tinycss2 reads every stylesheet and style="" here. Patterns over the text came first,
# and each was right only about the grammar it was written against: a brace walk that
# knew a comment's braces are not braces still read a `}` inside `content: "}"` as the
# end of the block. The dependency buys the grammar whole.


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
    condition, so a rule nested in a conditional one is conditional and no more, and
    neither is `@layer`, which orders its rules and always applies them."""
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
            # A cascade layer orders rules rather than conditioning them.
            layered = node.lower_at_keyword == "layer"
            yield from _rules(css_block(node.content), conditional or not layered)


PRESENTATION_PROPERTIES = {
    "all",
    "display",
    "visibility",
}


def inline_style_at(inline: dict) -> str:
    """Name one style="" by the element and line an author finds it at."""
    return f"<{inline['tag']} style> (line {inline['line']})"


def inline_presentation_override_errors(parser: SourceDocument) -> list:
    """Inline importance outranks even the theme's first important cascade layer."""
    errors = []
    for inline in parser.inline_styles:
        for declaration in css_block(inline["style"]):
            if (
                declaration.type == "declaration"
                and declaration.important
                and declaration.lower_name in PRESENTATION_PROPERTIES
            ):
                errors.append(
                    f"{inline_style_at(inline)} makes protected presentation property "
                    f"{declaration.lower_name} important"
                )
    return errors


# ---------- page CSS that fights the layout ----------
# Leaf keeps the user's place in the regions it knows: the page, a pane, a bounded
# block. Page CSS stays free inside a block, so this is advice rather than an error: a box
# the page makes scroll vertically keeps no reading position across a revision or a
# reflow. Sideways scrolling is the theme's own answer to a wide table or listing, and a
# bound says nothing about it, so only the block axis is read.
SCROLL_VALUES = {"auto", "scroll"}
SCROLL_PROPS = {"overflow", "overflow-y", "overflow-block"}


def _scrolls(block) -> list:
    return [
        declaration.lower_name
        for declaration in block
        if declaration.type == "declaration"
        and declaration.lower_name in SCROLL_PROPS
        and SCROLL_VALUES
        & {t.lower_value for t in declaration.value if t.type == "ident"}
    ]


def scroller_css_advice(parser: SourceDocument, stylesheets: Mapping[str, str]) -> list:
    """Page CSS that makes a box scroll, each line naming the rule and the property. The
    page's CSS is its `<style>`, its `style` attributes, and `stylesheets`: the files it
    links from `page/`, by path, as the revision's capture resolved them
    (`RevisionArtifact.page_stylesheets`)."""
    # Each sheet by the prefix its rules are named with: the page's own <style> needs
    # none, and a linked file is named by its path.
    sheets = {"": parser.css, **{f"{path} ": css for path, css in stylesheets.items()}}
    stated = [
        (f"{prefix}rule `{selector}`", block)
        for prefix, css in sheets.items()
        for selector, block, _ in css_rules(css)
    ] + [
        (inline_style_at(inline), css_block(inline["style"]))
        for inline in parser.inline_styles
    ]
    return [
        f"{where} sets {prop} to scroll, and Leaf keeps no reading position "
        "in a scroller page CSS makes; bound the block with data-bound=start|end instead"
        for where, block in stated
        for prop in _scrolls(block)
    ]
