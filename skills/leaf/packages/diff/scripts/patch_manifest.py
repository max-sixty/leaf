#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["unidiff>=1"]
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes the manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE SOURCE

The manifest is the form of the contract whose `patch` fields `/api/state` defers
(`records.deferred`), so a large review sends each file's patch only when its
disclosure opens.

This only splits the patch into files and reads each one's paths and counts. `lf-diff`
alone judges what it can present, so an entry it refuses, such as a binary or copy
diff or a malformed hunk, is stored and refused when its file opens, where the
widget's failure reaches the agent. `tests/diff_patch_cases.json` holds both readers to
the paths of the patches lf-diff accepts.
"""

import codecs
import json
import re
import sys

from unidiff import PatchSet, UnidiffParseError

_PATH_ONLY_RENAME = re.compile(
    r"diff --git .+\nsimilarity index 100%\nrename from .+\nrename to .+\n*"
)
_RENAME = re.compile(r"^rename from (.+)\nrename to (.+)$", re.MULTILINE)


def _git_path(token: str) -> str:
    """One path as Git writes it, with its C-style quoting decoded."""
    if token.startswith('"'):
        return codecs.escape_decode(token[1:-1].encode())[0].decode()
    return token


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    (patched,) = PatchSet.from_string(section)
    # A rename names both paths on lines of their own, where a path-only one has no
    # ---/+++ sides and its `diff --git` line is ambiguous once a path holds " b/".
    if renamed := _RENAME.search(section):
        previous, path = map(_git_path, renamed.groups())
    else:
        path = _git_path(patched.path)
    return {
        "path": path,
        **({"previousPath": previous} if renamed else {}),
        # A binary rename is hunkless too, and listing it as a rename would hide its
        # content change.
        "kind": "rename" if _PATH_ONLY_RENAME.fullmatch(section) else "patch",
        "additions": patched.added,
        "deletions": patched.removed,
        "patch": section,
    }


def patch_manifest(source: str) -> dict:
    """One captured Git patch as the `unified-diff` contract's file manifest.

    Each entry carries the file's paths, its change counts, and the verbatim section
    of the captured text that `lf-diff` renders once its disclosure opens, which is
    why the source is split here rather than rebuilt from unidiff's reading."""
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
    except (UnidiffParseError, UnicodeDecodeError) as error:
        print(f"patch_manifest: {error}", file=sys.stderr)
        return 1
    json.dump(manifest, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
