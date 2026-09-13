"""Bind captured authored dependencies to one revision's delivery address.

Capture validates the graph; delivery only changes how its resources are addressed.
HTML source spans preserve prose and unrelated attributes, JavaScript rewriting names
only parsed imports, and CSS rewriting names only imports and url() values. The same
document therefore works at the live, stamped-version, and immutable-revision URLs.
"""

import html
from urllib.parse import quote, urlsplit

import tinycss2
import turbohtml
from tinycss2.serializer import serialize_string_value

from .revision_artifact import Resource, resolve_dependency, rewrite_module
from .structure import SourceDocument, rewrite_resource_attribute


def _resource_url(value: str, logical_path: str, asset_root: str) -> str:
    if value.startswith(("#", "data:")):
        return value
    target = resolve_dependency(value, logical_path)
    fragment = urlsplit(value).fragment
    return (
        asset_root.rstrip("/")
        + quote(target, safe="/")
        + ("#" + fragment if fragment else "")
    )


def _stylesheet(source: str, logical_path: str, asset_root: str, *, block=False) -> str:
    parse = tinycss2.parse_declaration_list if block else tinycss2.parse_stylesheet
    tokens = parse(source)
    changed = False

    def replace(token):
        nonlocal changed
        value = _resource_url(token.value, logical_path, asset_root)
        if value == token.value:
            return
        changed = True
        token.value = value
        quoted = '"' + serialize_string_value(value) + '"'
        token.representation = f"url({quoted})" if token.type == "url" else quoted

    def walk(items):
        for token in items:
            if token.type == "url":
                replace(token)
            elif token.type == "function" and token.lower_name == "url":
                [value] = [
                    item
                    for item in token.arguments
                    if item.type not in {"whitespace", "comment"}
                ]
                replace(value)
            elif token.type == "at-rule" and token.lower_at_keyword == "import":
                first = next(
                    item
                    for item in token.prelude
                    if item.type not in {"whitespace", "comment"}
                )
                if first.type == "string":
                    replace(first)
            for name in ("prelude", "content", "arguments", "value"):
                nested = getattr(token, name, None)
                if isinstance(nested, list):
                    walk(nested)

    walk(tokens)
    return tinycss2.serialize(tokens) if changed else source


def deliver_resource(resource: Resource, logical_path: str, asset_root: str) -> bytes:
    """Address a resource by its captured path, including page-widget aliases.

    Trusted layer JavaScript still uses the runtime's own route-scoping rules. A
    page widget served through ``widgets/<tag>.js`` must pass its manifest path
    here (``/page/widgets/<tag>.js``), which is the base of its authored imports.
    """
    if resource.mime == "application/javascript" and logical_path.startswith("/page/"):
        return rewrite_module(resource.data, logical_path, asset_root)
    if resource.mime == "text/css" and logical_path.startswith("/page/"):
        return _stylesheet(
            resource.data.decode("utf-8"), logical_path, asset_root
        ).encode("utf-8")
    return resource.data


def deliver_document(source: str, asset_root: str) -> str:
    """Rebase an admitted authored document before delivery inserts its own head."""
    document = SourceDocument(source)
    replacements = []
    index = document._source_index

    def attribute(element, name, value):
        span = element.source_location.attrs[name]
        replacements.append(
            (
                index(span.start_line, span.start_col),
                index(span.end_line, span.end_col),
                f'{name}="{html.escape(value, quote=True)}"',
            )
        )

    for element in document.tree.descendants:
        if (
            not isinstance(element, turbohtml.Element)
            or element.source_location is None
        ):
            continue
        attrs = element.attrs
        location = element.source_location
        if element.tag == "script" and attrs.get("src"):
            target = resolve_dependency(attrs["src"], "/index.html", module=True)
            attribute(element, "src", asset_root.rstrip("/") + quote(target, safe="/"))
        if element.tag == "link" and "stylesheet" in (attrs.get("rel") or []):
            attribute(
                element, "href", _resource_url(attrs["href"], "/index.html", asset_root)
            )
        if element.tag != "script":
            for name, value in attrs.items():
                if not isinstance(value, str):
                    continue
                delivered = rewrite_resource_attribute(
                    element.tag,
                    attrs,
                    name,
                    value,
                    lambda reference: (
                        _resource_url(reference, "/index.html", asset_root)
                        if reference.startswith(
                            ("/page/", "page/", "./page/", "/media/")
                        )
                        else reference
                    ),
                )
                if delivered != value:
                    attribute(element, name, delivered)
        if attrs.get("style"):
            value = _stylesheet(attrs["style"], "/index.html", asset_root, block=True)
            if value != attrs["style"]:
                attribute(element, "style", value)
        if element.tag in {"script", "style"} and location.end_tag is not None:
            start = index(location.start_tag.end_line, location.start_tag.end_col)
            end = index(location.end_tag.start_line, location.end_tag.start_col)
            body = source[start:end]
            if element.tag == "script" and not attrs.get("src"):
                delivered = rewrite_module(
                    body.encode("utf-8"), "/index.html", asset_root
                ).decode("utf-8")
            elif element.tag == "style":
                delivered = _stylesheet(body, "/index.html", asset_root)
            else:
                continue
            if delivered != body:
                replacements.append((start, end, delivered))

    for start, end, value in sorted(replacements, reverse=True):
        source = source[:start] + value + source[end:]
    return source
