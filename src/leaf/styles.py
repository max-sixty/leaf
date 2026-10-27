"""CSS readings of authored HTML.

Bounded readings of exact CSS text keep state requests from reparsing unchanged
stylesheets. Their results are read-only; edits select a new cache entry.

Each stylesheet is parsed on its own, matching browser EOF recovery. Composition
serializes that reading before adding wrappers, so a missing delimiter cannot put
the wrapper or a later sheet inside this sheet's last block, string or comment.
"""

from functools import lru_cache

import tinycss2

from .findings import Finding


def css_block(css):
    """What a block holds: the declarations it states, and the rules nested inside it. A
    style="" attribute is a block written without the braces around it."""
    return tinycss2.parse_blocks_contents(css, skip_comments=True, skip_whitespace=True)


@lru_cache(maxsize=32)
def css_stylesheet(css: str):
    """One independent stylesheet's read-only syntax tree, including EOF recovery."""
    return tinycss2.parse_stylesheet(css)


@lru_cache(maxsize=32)
def css_syntax_errors(css: str, source: str, *, block=False) -> tuple[Finding, ...]:
    """Every parse error in a stylesheet or declaration block, including nested rules.
    `source` names the sheet as its author finds it: a file, the page's <style>, or
    one element's style attribute."""
    parse = css_block if block else css_stylesheet
    errors = []
    seen = set()

    def record(node):
        key = (node.source_line, node.source_column, node.message)
        if key in seen:
            return
        seen.add(key)
        errors.append(
            Finding(
                "css-syntax",
                values={
                    "sheet": source,
                    "row": node.source_line,
                    "column": node.source_column,
                    "message": node.message,
                },
            )
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


def inline_style_at(inline: dict) -> str:
    """Name one style="" by the element and line an author finds it at."""
    return f"<{inline['tag']} style> (line {inline['line']})"
