#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE SOURCE

Each record keys a file's raw Git evidence by its destination path. The browser
alone derives and validates display metadata. Textual hunks render when opened;
compressed binary payloads are omitted after their Git marker. Sections sharing
a path travel together, including a native delete/add file-type replacement.
"""

import codecs
import io
import json
import re
import sys


def _git_path(token: str) -> str:
    """One path as Git writes it, with its C-style quoting decoded."""
    if token.startswith('"'):
        return codecs.escape_decode(token[1:-1].encode())[0].decode()
    return token


def patch_manifest(source: str) -> dict:
    """Group native Git evidence by destination without interpreting its changes."""
    files = {}
    for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE):
        if not section.startswith("diff --git "):
            continue
        if moved := re.search(r"^(?:rename|copy) to (.+)$", section, re.MULTILINE):
            path = _git_path(moved.group(1))
        else:
            # Non-moving Git headers repeat the same path. Halving preserves
            # spaces and embedded " b/" without parsing the file's metadata.
            header = section.partition("\n")[0].removeprefix("diff --git ")
            path = _git_path(header[: (len(header) - 1) // 2]).removeprefix("a/")
        if marker := re.search(r"^GIT binary patch$", section, re.MULTILINE):
            section = section[: marker.end()] + "\n"
        files[path] = files.get(path, "") + section
    return {"files": [{"path": path, "patch": patch} for path, patch in files.items()]}


def main() -> int:
    assert isinstance(sys.stdin, io.TextIOWrapper)
    assert isinstance(sys.stdout, io.TextIOWrapper)
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
