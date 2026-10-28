"""CSS readings of authored HTML.

Bounded readings of exact CSS text keep state requests from reparsing unchanged
stylesheets. Their results are read-only; edits select a new cache entry.

Each stylesheet is parsed on its own, matching browser EOF recovery. Composition
serializes that reading before adding wrappers, so a missing delimiter cannot put
the wrapper or a later sheet inside this sheet's last block, string or comment.
"""

from functools import lru_cache

from .findings import Finding


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


# Whether a declaration or rule a browser drops refuses its sheet (`dropped_css`):
# "error" refuses it, "advice" reports it beside a passing check.
DROPPED_SEVERITY = "error"


def dropped_css(css: str, sheet: str, *, block=False) -> tuple[Finding, ...]:
    """Each declaration or nested rule a browser drops from a sheet that delivery's
    reader reads whole (`revision_artifact._read_css`), as `css-dropped`.

    The reader parses a stylesheet into its rules and their tokens, and refuses
    what it can't read: an error token anywhere, or a malformed top-level rule. A
    rule's block it keeps as tokens, which a browser parses as declarations and
    nested rules, dropping each one that doesn't parse, such as `broken;` in
    `p { color: red; broken; }`. Those are what this reports, so no problem is
    reported by both. A style attribute (`block`) the reader parses as its list of
    declarations, so it holds nothing more to drop. `sheet` names the sheet as its
    author finds it: a file, the page's <style>, or one element's style attribute."""
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
                                severity=DROPPED_SEVERITY,
                            ),
                        )
                walk(inner)

    walk(css_stylesheet(css))
    return tuple(errors.values())
