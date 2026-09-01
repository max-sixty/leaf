"""Read the companions shipped beside authored examples."""

import json
import re
from pathlib import Path

# A prior version ships under examples/versions/, so no builder's `*.html` glob over
# the top of examples/ reads one as an example of its own.
PRIOR_VERSION = re.compile(r"\.v([1-9][0-9]*)$")


def example_versions(source: Path) -> list[Path]:
    """Every authored version of one example, oldest first.

    The example's own file is its current version, and for most examples that is the
    whole list. One that was revised ships each earlier version as
    `examples/versions/<stem>.vN.html`; every builder stamps this list in order, so
    the page a reader opens carries the version chooser, the changes-since marks, and
    a thread opened against the document before the revision.
    """
    priors = sorted(
        (source.parent / "versions").glob(f"{source.stem}.v*.html"),
        key=lambda path: int(PRIOR_VERSION.search(path.stem).group(1)),
    )
    return [*priors, source]


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
