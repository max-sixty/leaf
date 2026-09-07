"""Choose the pull-request test surface from changed repository paths.

Product and shared test-harness changes run the complete suite. Documentation
and unrelated workflow changes need only the everyday suite, while a change to
an individual test module adds that module's nightly cases. The CI workflow and
its timing data run the complete path they configure. Unknown paths take that
route too, so a new product area cannot silently bypass browser coverage.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

FAST_PREFIXES = (".github/", "docs/")
FAST_SUFFIXES = (".md",)
FULL_FILES = frozenset({".github/workflows/ci.yaml", ".test_durations"})


def is_test_module(path: str) -> bool:
    return (
        path.startswith("tests/test_") and path.endswith(".py") and path.count("/") == 1
    )


def select(
    changed_paths: Iterable[str], *, existing_paths: Iterable[str] | None = None
) -> dict[str, object]:
    paths = tuple(changed_paths)
    existing = set(paths if existing_paths is None else existing_paths)
    test_modules = sorted(
        {path for path in paths if path in existing and is_test_module(path)}
    )
    full = any(
        path in FULL_FILES
        or (
            not path.startswith(FAST_PREFIXES)
            and not path.endswith(FAST_SUFFIXES)
            and not is_test_module(path)
        )
        for path in paths
    )
    return {"full": full, "test_modules": test_modules}


if __name__ == "__main__":
    changed = [path for path in sys.stdin.buffer.read().decode().split("\0") if path]
    existing = [path for path in changed if Path(path).is_file()]
    print(json.dumps(select(changed, existing_paths=existing), separators=(",", ":")))
