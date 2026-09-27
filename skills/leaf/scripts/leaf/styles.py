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


# At-rules whose block holds style rules. Every other block — keyframes, a font face, a
# registered property, a page box — holds no selector to narrow.
_GROUPING_RULES = {"media", "supports", "container", "layer", "scope", "starting-style"}
# The pseudo-elements CSS2 spelled with one colon.
_LEGACY_PSEUDO_ELEMENTS = {"before", "after", "first-line", "first-letter"}


def _subject_end(member: list) -> int:
    """Where a complex selector's subject compound ends: before its pseudo-element, or at
    the end of the selector. The tokens are the selector's top level, so a colon inside
    :is() or an attribute value sits in a block and is never seen here."""
    for at, token in enumerate(member[:-1]):
        after = member[at + 1]
        if (
            token.type == "literal"
            and token.value == ":"
            and (
                (after.type == "literal" and after.value == ":")
                or (
                    after.type == "ident"
                    and after.lower_value in _LEGACY_PSEUDO_ELEMENTS
                )
            )
        ):
            return at
    end = len(member)
    while end and member[end - 1].type in {"whitespace", "comment"}:
        end -= 1
    return end


# The elements every widget stands inside, so none can contain them.
_ROOT_SUBJECTS = {"html", "body"}


def _subject_start(member: list, end: int) -> int:
    """Where the subject compound starts: after the last top-level combinator."""
    start = end
    while start and not (
        member[start - 1].type == "whitespace"
        or (member[start - 1].type == "literal" and member[start - 1].value in ">+~")
    ):
        start -= 1
    return start


def _confined_selectors(prelude: list, where: str) -> str:
    members, member = [], []
    for token in [*prelude, None]:
        if token is None or (token.type == "literal" and token.value == ","):
            end = _subject_end(member)
            subject = member[_subject_start(member, end) : end]
            if subject and (
                (
                    subject[0].type == "ident"
                    and subject[0].lower_value in _ROOT_SUBJECTS
                )
                or (
                    len(subject) > 1
                    and subject[0].type == "literal"
                    and subject[0].value == ":"
                    and subject[1].type == "ident"
                    and subject[1].lower_value == "root"
                )
            ):
                raise ValueError(
                    f"`{tinycss2.serialize(member).strip()}` styles "
                    f"`{tinycss2.serialize(subject)}`, which no widget contains"
                )
            members.append(
                tinycss2.serialize(member[:end])
                + where
                + tinycss2.serialize(member[end:])
            )
            member = []
        else:
            member.append(token)
    return ",".join(members)


def _states(nodes) -> bool:
    """Whether a rule's block declares anything for the rule's own subject: directly, or
    inside a condition such as `@media` nested in it, which applies to the same element."""
    return any(
        node.type == "declaration"
        or (
            node.type == "at-rule"
            and node.content is not None
            and node.lower_at_keyword in _GROUPING_RULES
            and _states(tinycss2.parse_blocks_contents(node.content))
        )
        for node in nodes
    )


def _confined_block(nodes, where: str) -> str:
    out = []
    for node in nodes:
        if node.type == "qualified-rule":
            inner = tinycss2.parse_blocks_contents(node.content)
            # A rule with no declarations of its own styles nothing: its selector is
            # the `&` its nested rules extend, and confining it would confine their
            # ancestors too, where each of them is confined at its own subject.
            styles = _states(inner)
            prelude = (
                _confined_selectors(node.prelude, where)
                if styles
                else tinycss2.serialize(node.prelude)
            )
            out.append(f"{prelude}{{{_confined_block(inner, where)}}}")
        elif (
            node.type == "at-rule"
            and node.content is not None
            and node.lower_at_keyword in _GROUPING_RULES
        ):
            inner = tinycss2.parse_blocks_contents(node.content)
            out.append(
                f"@{node.at_keyword}{tinycss2.serialize(node.prelude)}"
                f"{{{_confined_block(inner, where)}}}"
            )
        elif node.type == "declaration":
            out.append(node.serialize() + ";")
        else:
            out.append(node.serialize())
    return "".join(out)


def confined(css: str, where: str) -> str:
    """`css` with every style rule, at every depth, matching only where `where` does too.

    `where` joins the subject compound of each complex selector, ahead of any
    pseudo-element, so it reads the element the rule styles. Written as a :where(), it
    weighs nothing, and each rule keeps the rank its author gave it. A rule whose subject
    is the root or the body can never meet it, so it raises ValueError naming the rule
    rather than returning a rule that matches nothing."""
    return _confined_block(tinycss2.parse_stylesheet(css), where)


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
