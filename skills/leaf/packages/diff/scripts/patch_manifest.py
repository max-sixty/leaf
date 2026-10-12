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
disclosure opens. An entry the contract excludes, a copy or a file with no textual
hunks other than a path-only rename, is refused here, with the reason on stderr and
exit status 1, rather than stored.

The input is a patch as `git diff` writes it. unidiff reads its hunks and paths, and a
malformed patch is not diagnosed here. `tests/diff_patch_cases.json` holds this and the
widget to one table of cases.
"""

import codecs
import json
import re
import sys

from unidiff import PatchSet, UnidiffParseError


class PatchError(ValueError):
    """An entry the `unified-diff` contract excludes."""


_PATH_ONLY_RENAME = re.compile(
    r"diff --git .+\nsimilarity index 100%\nrename from .+\nrename to .+\n*"
)
_RENAME = re.compile(r"^rename from (.+)\nrename to (.+)$", re.MULTILINE)


def _unquote(token: str) -> str:
    """One path as Git writes it, with its C-style quoting decoded."""
    if token.startswith('"'):
        return codecs.escape_decode(token[1:-1].encode())[0].decode()
    return token


def _git_path(token: str, marker: str) -> str | None:
    """The path one ---/+++ side names, its `a/` or `b/` marker removed, or None for
    /dev/null.

    lf-diff reads only Git's default markers, and without them nothing says where the
    path starts, so a patch written with `--no-prefix` or other markers is refused."""
    if token == "/dev/null":
        return None
    token = _unquote(token)
    if not token.startswith(marker):
        raise PatchError(
            f"{token} lacks Git's {marker} prefix; write the patch with "
            "`git diff --src-prefix=a/ --dst-prefix=b/`"
        )
    return token[len(marker) :]


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    if re.search(r"^copy (?:from|to) ", section, re.MULTILINE):
        raise PatchError(
            "unsupported copy diff; omit copy metadata and provide textual @@ "
            "hunks for an edited destination"
        )
    (patched,) = PatchSet.from_string(section)
    previous = _git_path(patched.source_file, "a/")
    path = _git_path(patched.target_file, "b/") or previous
    # A rename names both paths on lines of their own, where a path-only one has no
    # ---/+++ sides and its `diff --git` line is ambiguous once a path holds " b/".
    if renamed := _RENAME.search(section):
        previous, path = map(_unquote, renamed.groups())
    # unidiff stops reading a hunk at the length its @@ header gives, so a line past
    # it would leave the stored counts short of what lf-diff refuses on opening.
    # Lines end only at "\n", as Git writes them.
    body = section.partition("\n@@")[2].split("\n")
    if sum(line[:1] in ("+", "-") for line in body) != patched.added + patched.removed:
        raise PatchError(
            f"hunk line counts in {path} do not match their @@ headers; pass "
            "`git diff` output alone"
        )
    # Only Git's exact path-only rename omits textual hunks; a binary rename is
    # hunkless too, and listing it as a rename would hide its content change.
    path_only = _PATH_ONLY_RENAME.fullmatch(section) is not None
    if not patched and not path_only:
        raise PatchError(
            f"unsupported hunkless diff for {path}; describe binary, mode-only "
            "and empty added or deleted files in prose"
        )
    return {
        "path": path,
        **({"previousPath": previous} if renamed else {}),
        "kind": "rename" if path_only else "patch",
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
    except (PatchError, UnidiffParseError, UnicodeDecodeError) as error:
        print(f"patch_manifest: {error}", file=sys.stderr)
        return 1
    json.dump(manifest, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
