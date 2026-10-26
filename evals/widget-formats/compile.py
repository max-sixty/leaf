"""Compile a flat JSON element tree into the same Leaf HTML grammar authors can write.

This is a syntax control, not a json-render implementation. Its flat root/elements
shape resembles JSON UI documents, but it permits lowercase HTML or Leaf tags
and HTML attribute names so these tasks differ in serialization alone.
"""

import json
import re
import sys
from html import escape
from pathlib import Path

TAG = re.compile(r"[a-z][a-z0-9-]*\Z")
ATTR = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:.-]*\Z")
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def compile_document(spec: object) -> str:
    """Reject malformed references rather than silently dropping authored content."""
    if not isinstance(spec, dict) or set(spec) != {"root", "elements"}:
        raise ValueError("document needs exactly root and elements")
    root, elements = spec["root"], spec["elements"]
    if not isinstance(root, str) or not isinstance(elements, dict):
        raise TypeError("root must be an ID and elements must be an object")
    if root not in elements:
        raise ValueError(f"unknown root: {root}")
    visited = set()

    def render(node_id: str, ancestors: frozenset[str]) -> str:
        if node_id in ancestors:
            raise ValueError(f"cycle at {node_id}")
        if node_id in visited:
            raise ValueError(f"element {node_id} has multiple parents")
        visited.add(node_id)
        node = elements.get(node_id)
        if not isinstance(node, dict) or set(node) != {"type", "props", "children"}:
            raise ValueError(f"element {node_id} needs type, props and children")
        tag, props, children = node["type"], node["props"], node["children"]
        if not isinstance(tag, str) or not TAG.fullmatch(tag):
            raise ValueError(f"invalid tag on {node_id}")
        if not isinstance(props, dict) or not isinstance(children, list):
            raise TypeError(f"element {node_id} needs object props and array children")
        attributes = []
        for name, value in props.items():
            if not isinstance(name, str) or not ATTR.fullmatch(name):
                raise ValueError(f"invalid attribute on {node_id}: {name}")
            if value is True:
                attributes.append(f" {name}")
            elif value is False or value is None:
                continue
            elif isinstance(value, str):
                attributes.append(f' {name}="{escape(value, quote=True)}"')
            else:
                raise ValueError(
                    f"attribute {name} on {node_id} must be text or boolean"
                )
        if tag in VOID and children:
            raise ValueError(f"void element {node_id} cannot have children")
        content = []
        for child in children:
            if isinstance(child, str):
                if child not in elements:
                    raise ValueError(f"unknown child {child} of {node_id}")
                content.append(render(child, ancestors | {node_id}))
            elif (
                isinstance(child, dict)
                and set(child) == {"text"}
                and isinstance(child["text"], str)
            ):
                value = child["text"]
                content.append(value if tag in {"style", "script"} else escape(value))
            else:
                raise ValueError(f"invalid child of {node_id}")
        opening = f"<{tag}{''.join(attributes)}>"
        return opening if tag in VOID else opening + "".join(content) + f"</{tag}>"

    html = render(root, frozenset())
    if len(visited) != len(elements):
        raise ValueError(
            "unreachable elements: " + ", ".join(sorted(set(elements) - visited))
        )
    if elements[root]["type"] != "html":
        raise ValueError("root element must have type html")
    return "<!doctype html>\n" + html + "\n"


def main() -> None:
    source, target = map(Path, sys.argv[1:])
    html = compile_document(json.loads(source.read_text()))
    target.write_text(html)


if __name__ == "__main__":
    main()
