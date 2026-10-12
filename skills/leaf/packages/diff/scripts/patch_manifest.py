#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes the manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE SOURCE

The manifest is the form of the contract whose `patch` fields `/api/state` defers
(`records.deferred`), so a large review sends each file's patch only when its
disclosure opens.

This only splits the patch into files and reads each one's paths and counts; it
judges nothing. `lf-diff` alone judges what it can present, so an entry it refuses,
such as a binary or copy diff or a malformed hunk, is stored and refused when its
file opens, where the widget's failure reaches the agent. `tests/diff_patch_cases.json`
holds both readers to the paths of the patches lf-diff accepts.
"""

import codecs
import json
import re
import sys

_PATH_ONLY_RENAME = re.compile(
    r"diff --git .+\nsimilarity index 100%\nrename from .+\nrename to .+\n*"
)
_MOVE = re.compile(r"^(rename|copy) from (.+)\n\1 to (.+)$", re.MULTILINE)


def _git_path(token: str) -> str:
    """One path as Git writes it, with its C-style quoting decoded."""
    if token.startswith('"'):
        return codecs.escape_decode(token[1:-1].encode())[0].decode()
    return token


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    header, _, rest = section.partition("\n")
    # A rename or copy names both paths on lines of their own. Otherwise Git's header
    # names one path twice, `a/<path> b/<path>`, so its first half is the path behind
    # its marker, whatever spaces or " b/" the path holds. A path without the marker
    # stays whole, for lf-diff to refuse under its own name.
    if moved := _MOVE.search(rest):
        previous, path = map(_git_path, moved.group(2, 3))
    else:
        both = header.removeprefix("diff --git ")
        previous = None
        path = _git_path(both[: (len(both) - 1) // 2]).removeprefix("a/")
    lines = rest.partition("\n@@")[2].split("\n")
    renamed = moved is not None and moved.group(1) == "rename"
    return {
        "path": path,
        **({"previousPath": previous} if renamed else {}),
        # A binary rename is hunkless too, and listing it as a rename would hide its
        # content change.
        "kind": "rename" if _PATH_ONLY_RENAME.fullmatch(section) else "patch",
        "additions": sum(line.startswith("+") for line in lines),
        "deletions": sum(line.startswith("-") for line in lines),
        "patch": section,
    }


def patch_manifest(source: str) -> dict:
    """One captured Git patch as the `unified-diff` contract's file manifest.

    Each entry carries the file's paths, its change counts, and the verbatim section
    of the captured text that `lf-diff` renders once its disclosure opens."""
    return {
        "files": [
            _manifest_file(section)
            for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE)
            if section.startswith("diff --git ")
        ]
    }


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        manifest = patch_manifest(sys.stdin.read())
    except UnicodeDecodeError as error:
        print(f"patch_manifest: {error}", file=sys.stderr)
        return 1
    json.dump(manifest, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
