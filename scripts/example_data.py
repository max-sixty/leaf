"""Read the external-data companions shipped beside authored examples."""

import json
from pathlib import Path

CAPTURES = "$captures"


def data_operations(source: Path) -> list[dict]:
    """Return captures first, then replaceable values, for one example source."""
    companion = source.with_suffix(".data.json")
    if not companion.exists():
        return []
    document = json.loads(companion.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError(f"{companion}: expected an object")
    captures = document.pop(CAPTURES, {})
    if not isinstance(captures, dict):
        raise TypeError(f"{companion}: {CAPTURES} must be an object")

    operations = []
    example_dir = source.parent.resolve()
    for name, spec in captures.items():
        if (
            not isinstance(spec, dict)
            or "text-file" not in spec
            or not set(spec) <= {"text-file", "label", "lines"}
            or not isinstance(spec["text-file"], str)
        ):
            raise ValueError(
                f"{companion}: capture {name!r} needs text-file and optional "
                "label or lines"
            )
        text_file = (source.parent / spec["text-file"]).resolve()
        if text_file.parent != example_dir:
            raise ValueError(
                f"{companion}: capture {name!r} text-file must be a sibling"
            )
        operations.append(
            {
                "kind": "capture",
                "source": name,
                "text_file": text_file,
                "label": spec.get("label"),
                "lines": spec.get("lines"),
            }
        )
    operations.extend(
        {"kind": "set", "source": name, "value": value}
        for name, value in document.items()
    )
    return operations
