"""Read the external-data companions shipped beside authored examples."""

import json
from pathlib import Path


def data_operations(source: Path) -> list[dict]:
    """Return captures first, then replaceable values, for one example source."""
    companion = source.with_suffix(".data.json")
    if not companion.exists():
        return []
    document = json.loads(companion.read_text(encoding="utf-8"))

    operations = []
    for name, spec in document.pop("$captures", {}).items():
        operations.append(
            {
                "kind": "capture",
                "source": name,
                "input_file": source.parent / spec["file"],
                "format": spec.get("format", "text"),
                "label": spec.get("label"),
                "lines": spec.get("lines"),
            }
        )
    operations.extend(
        {"kind": "set", "source": name, "value": value, "capture_label": None}
        for name, value in document.items()
    )
    return operations
