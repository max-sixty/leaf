"""Read the companions shipped beside authored examples."""

import json
import re
from pathlib import Path

# A prior version ships under the source directory's versions/, so a builder's
# top-level `*.html` glob never reads one as a page of its own.
PRIOR_VERSION = re.compile(r"\.v([1-9][0-9]*)$")


def example_versions(source: Path) -> list[Path]:
    """Every authored version of one example, oldest first.

    The example's own file is its current version, and for most examples that is the
    whole list. One that was revised ships each earlier version as
    the source directory's `versions/<stem>.vN.html`; every builder stamps this list in
    order, so the page a reader opens carries the version chooser, the changes-since
    marks, and a thread opened against the document before the revision.
    """
    priors = sorted(
        (source.parent / "versions").glob(f"{source.stem}.v*.html"),
        key=lambda path: int(PRIOR_VERSION.search(path.stem).group(1)),
    )
    # The published number is the position in this list, so a gap in the file names
    # would renumber every later version without a word; refuse it instead.
    numbers = [int(PRIOR_VERSION.search(path.stem).group(1)) for path in priors]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(
            f"{source.name}: prior versions must run v1 to v{len(numbers)} without "
            f"a gap, found {numbers}"
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
