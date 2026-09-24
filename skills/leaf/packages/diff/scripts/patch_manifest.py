#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = ["unidiff>=1"]
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes the manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | packages/diff/scripts/patch_manifest.py | leaf data set PAGE SOURCE

The manifest is the form of the contract whose `patch` fields `/api/state` defers
(`records.deferred`), so a large review sends each file's patch only when its
disclosure opens. A patch `lf-diff` cannot present as review evidence is refused
here, with the reason on stderr and exit status 1, rather than stored.

unidiff reads the hunks; everything else here owns the manifest built around them.
"""

import codecs
import json
import re
import sys

from unidiff import PatchedFile, PatchSet, UnidiffParseError


class PatchError(ValueError):
    """A patch the diff widget cannot present."""


_GIT_QUOTED_PATH = re.compile(
    r'(?:[^\\]|\\(?:[abtnvfr"\\]|[0-3][0-7]{2}|[0-7]{1,2}(?![0-7])))*'
)


def _decode_git_path(path: str) -> str:
    """Decode the C-style quoting Git uses for diff path fields.

    unidiff hands a quoted path back as Git wrote it, so the manifest decodes it
    here and refuses an escape Git would not have written."""
    if not path.startswith('"'):
        return path
    if len(path) < 2 or not path.endswith('"'):
        raise PatchError(f"invalid quoted Git path {path!r}")
    inner = path[1:-1]
    if _GIT_QUOTED_PATH.fullmatch(inner) is None:
        raise PatchError(f"invalid quoted Git path {path!r}")
    encoded = codecs.escape_decode(inner.encode("utf-8"))[0]
    if 0 in encoded:
        raise PatchError("quoted Git path contains a NUL byte")
    try:
        return encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchError(f"quoted Git path is not UTF-8: {path!r}") from error


def _diff_header_path(side: str, path: str) -> str:
    """One bare path written the way its `diff --git` side names it."""
    return (
        f'"{side}/{path[1:]}'
        if path.startswith('"') and path.endswith('"')
        else f"{side}/{path}"
    )


def _marked_bare_path(token: str, side: str) -> str:
    """One ---/+++ path token with its side marker removed, still quoted where Git
    quoted it.

    Git writes the marker itself, so the leading two characters are never part of
    the path, and stripping them before decoding keeps the quoting that the
    `diff --git` header is compared against. A capture made with `--no-prefix` or a
    mnemonic prefix is refused here: the widget reads the default markers."""
    marker = f"{side}/"
    if token.startswith('"') and token.endswith('"'):
        if token[1:3] == marker:
            return f'"{token[3:]}'
    elif token.startswith(marker):
        return token[2:]
    raise PatchError(f"unified diff path {token!r} has no {marker} side marker")


def _diff_marked_paths(section: str) -> tuple[str | None, str | None]:
    """Read the adjacent ---/+++ file headers before the first textual hunk."""
    lines = section.split("\n")
    first_hunk = next(
        (index for index, line in enumerate(lines) if line.startswith("@@")),
        len(lines),
    )
    marked = lines[1:first_hunk]
    old = [
        (index, line[4:])
        for index, line in enumerate(marked)
        if line.startswith("--- ")
    ]
    new = [
        (index, line[4:])
        for index, line in enumerate(marked)
        if line.startswith("+++ ")
    ]
    if not old and not new:
        return None, None
    if len(old) != 1 or len(new) != 1 or new[0][0] != old[0][0] + 1:
        raise PatchError("unified diff needs one adjacent ---/+++ file-header pair")
    # A traditional unified header may append a timestamp after a tab. Git's quoted
    # paths keep whitespace inside the quotes and need no special casing here.
    return old[0][1].split("\t", 1)[0], new[0][1].split("\t", 1)[0]


def _diff_rename_paths(section: str) -> tuple[str | None, str | None]:
    previous = re.search(r"^rename from (.+)$", section, re.MULTILINE)
    renamed = re.search(r"^rename to (.+)$", section, re.MULTILINE)
    if bool(previous) != bool(renamed):
        raise PatchError("unified diff has an incomplete rename block")
    return (
        _decode_git_path(previous.group(1)) if previous is not None else None,
        _decode_git_path(renamed.group(1)) if renamed is not None else None,
    )


def _path_only_rename(section: str) -> tuple[str, str] | None:
    lines = section.rstrip("\n").split("\n")
    if len(lines) != 4 or lines[1] != "similarity index 100%":
        return None
    previous = re.fullmatch(r"rename from (.+)", lines[2])
    renamed = re.fullmatch(r"rename to (.+)", lines[3])
    if previous is None or renamed is None:
        return None
    old_path = previous.group(1)
    new_path = renamed.group(1)
    if old_path == '""' or new_path == '""':
        return None
    if lines[0] != (
        f"diff --git {_diff_header_path('a', old_path)} "
        f"{_diff_header_path('b', new_path)}"
    ):
        return None
    return _decode_git_path(old_path), _decode_git_path(new_path)


def _parsed_hunks(section: str, path: str) -> PatchedFile:
    """unidiff's reading of one section's textual hunks.

    unidiff ends a hunk as soon as its @@ header's declared counts are met, and
    hands any line after that back to the file parser, which absorbs it as patch
    metadata. So the reading counts as evidence only once the hunks account for
    every line from the first @@ header on."""
    # One view of where the section ends, for the parse and the count below: the
    # blank lines a patch may carry between files are neither hunk nor metadata.
    body_text = section.rstrip("\n") + "\n"
    try:
        parsed = PatchSet.from_string(body_text)
    except UnidiffParseError as error:
        # unidiff ends a refusal that quotes a line with that line's own newline.
        detail = str(error).strip()
        raise PatchError(f"unsupported hunks for {path}: {detail}") from error
    if len(parsed) != 1:
        raise PatchError(f"unified diff repeats a file header inside {path}")
    patched = parsed[0]
    if not patched:
        raise PatchError(
            f"unsupported hunkless diff for {path}; only exact path-only renames "
            "may omit textual @@ hunks"
        )
    lines = body_text.rstrip("\n").split("\n")
    first_hunk = next(
        index for index, line in enumerate(lines) if line.startswith("@@")
    )
    body = lines[first_hunk:]
    if len(body) != len(patched) + sum(len(hunk) for hunk in patched):
        raise PatchError(
            f"hunk line counts for {path} do not match the lines under them"
        )
    # unidiff reads a bare empty line as an empty context line, for a patch that
    # crossed a transport which strips trailing whitespace. `lf-diff` refuses one,
    # so capture refuses it too rather than storing evidence the page cannot draw.
    if not all(body):
        raise PatchError(f"unsupported hunks for {path}: an empty line has no marker")
    return patched


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    if re.search(r"^copy (?:from|to) ", section, re.MULTILINE):
        raise PatchError(
            "unsupported copy diff; omit copy metadata and provide textual @@ "
            "hunks for an edited destination"
        )
    pure_rename = _path_only_rename(section)
    if pure_rename is not None:
        previous, path = pure_rename
        return {
            "key": path,
            "path": path,
            "previousPath": previous,
            "kind": "rename",
            "additions": 0,
            "deletions": 0,
            "patch": section,
        }

    header = section.split("\n", 1)[0]
    previous, renamed = _diff_rename_paths(section)
    marked_old, marked_new = _diff_marked_paths(section)
    if marked_old is None or marked_new is None:
        if re.search(r"^@@", section, re.MULTILINE):
            raise PatchError(
                "unified diff has no ---/+++ file-header pair before its first hunk"
            )
        if previous is not None or renamed is not None:
            raise PatchError(
                "unsupported hunkless rename; only the exact four-line "
                "path-only form may omit textual @@ hunks"
            )
        raise PatchError(f"unsupported hunkless diff: {header}")

    # Git leaves ordinary spaces unquoted in `diff --git` and terminates the
    # unambiguous ---/+++ paths with a tab instead, so the header is compared with
    # the pair rebuilt from those paths rather than split at a guessed space. An
    # added or deleted file names /dev/null on one side and the surviving path on
    # both sides of the header.
    old_path = None if marked_old == "/dev/null" else _marked_bare_path(marked_old, "a")
    new_path = None if marked_new == "/dev/null" else _marked_bare_path(marked_new, "b")
    if old_path is None and new_path is None:
        raise PatchError("diff file has no old or new path")
    old_path = old_path or new_path
    new_path = new_path or old_path
    if header != (
        f"diff --git {_diff_header_path('a', old_path)} "
        f"{_diff_header_path('b', new_path)}"
    ):
        raise PatchError(
            "unified diff ---/+++ paths disagree with its diff --git header"
        )
    if (previous is not None and previous != _decode_git_path(old_path)) or (
        renamed is not None and renamed != _decode_git_path(new_path)
    ):
        raise PatchError(
            "unified diff rename paths disagree with its diff --git header"
        )

    path = renamed or _decode_git_path(new_path)
    patched = _parsed_hunks(section, path)
    return {
        "key": path,
        "path": path,
        **({"previousPath": previous} if previous is not None else {}),
        "kind": "patch",
        "additions": patched.added,
        "deletions": patched.removed,
        "patch": section,
    }


def patch_manifest(source: str) -> dict:
    """One captured Git patch as the `unified-diff` contract's file manifest.

    Leaf owns the manifest and unidiff owns the hunks inside it. Each entry
    carries the file's key and paths, its change counts, and the verbatim section
    of the captured text that `lf-diff` renders once its disclosure opens — which
    is why the source is split here rather than rebuilt from unidiff's reading.

    It refuses what the widget cannot present as review evidence. Two of
    those refusals are Leaf's alone: copy metadata, which unidiff reads as a
    rename, and a hunkless entry that is not the exact four-line path-only
    rename, which it reports as a file with no hunks."""
    sections = [
        section
        for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE)
        if section.startswith("diff --git ")
    ]
    if not sections:
        raise PatchError("unified diff contains no files")

    files = []
    paths = set()
    for section in sections:
        entry = _manifest_file(section)
        if entry["path"] in paths:
            raise PatchError(f"unified diff repeats file path {entry['path']!r}")
        paths.add(entry["path"])
        files.append(entry)
    return {"files": files}


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        manifest = patch_manifest(sys.stdin.read())
    except (PatchError, UnicodeDecodeError) as error:
        print(f"patch_manifest: {error}", file=sys.stderr)
        return 1
    json.dump(manifest, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
