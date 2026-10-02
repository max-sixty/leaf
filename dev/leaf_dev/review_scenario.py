"""The release-review task shared by the live Claude Code and Codex journeys.

Both hosts start with the same request and one stamped, undecided document. This
scenario uses only the current triage source on the default layer: the catalog's
packages, companion history and prior versions are outside the delivery experiment.
The runners own transport, timing, comments and assertions.
"""

import shutil
from pathlib import Path

from leaf_dev import ROOT
from leaf_dev.harness import run_leaf

REQUEST = (
    "I wrote a Leaf page at ./page. Serve it so I can review it in my browser, "
    "and handle the comments I leave on it."
)


def prepare(arm: Path, state: Path, page: Path) -> None:
    """Prepare the same release-review starting state using the host's Leaf arm."""
    run_leaf(arm, state, "page", "init", str(page), check=True)
    shutil.copy(ROOT / "examples" / "triage-board.html", page / "index.html")
    run_leaf(
        arm, state, "page", "stamp", str(page),
        "--text", "Release triage for review.", check=True,
    )  # fmt: skip
