#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["unidiff>=1"]
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes the manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE SOURCE

Each record describes the native operation, paths, modes and binary status. Its
hunkCount tells a reader whether textual evidence exists; only those records carry
a patch, deferred by /api/state until their disclosure opens. Binary payloads are
not stored. Invalid or incomplete text hunks fail before a value reaches data set.

unidiff owns the Git reading. Leaf preserves its exact textual sections and adds
copy meaning, which unidiff otherwise classifies as a rename. Native delete/add
sections replacing a file type become one file owner with complete old/new evidence.
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


def _moved_paths(section: str) -> tuple[str | None, str | None, str | None]:
    paths = {}
    for operation in ("rename", "copy"):
        previous = re.search(rf"^{operation} from (.*)$", section, re.MULTILINE)
        current = re.search(rf"^{operation} to (.*)$", section, re.MULTILINE)
        if bool(previous) != bool(current):
            raise PatchError(f"unified diff has an incomplete {operation} block")
        if previous is not None:
            paths[operation] = (
                _decode_git_path(previous.group(1)),
                _decode_git_path(current.group(1)),
            )
    if len(paths) > 1:
        raise PatchError("unified diff mixes rename and copy metadata")
    if not paths:
        return None, None, None
    operation, (previous, current) = next(iter(paths.items()))
    if not previous or not current:
        raise PatchError(f"unified diff has an empty {operation} path")
    return operation, previous, current


def _metadata(section: str, file: PatchedFile) -> None:
    """Validate metadata the dependency can otherwise absorb without interpreting.

    Binary payloads are opaque: the record says that Git changed binary content,
    without storing or interpreting its compressed bytes.
    """
    if bool(re.search(r"^old mode ", section, re.MULTILINE)) != bool(
        re.search(r"^new mode ", section, re.MULTILINE)
    ):
        raise PatchError("unified diff has an incomplete mode change")
    for line in section.splitlines()[1:]:
        if line.startswith("@@"):
            return
        if file and line.startswith(("--- ", "+++ ")):
            continue
        if line == "GIT binary patch":
            return
        if not line:
            continue
        if (
            re.fullmatch(
                r"(?:old mode|new mode|new file mode|deleted file mode) [0-7]{6}"
                r"|(?:dis)?similarity index [0-9]+%"
                r"|(?:rename|copy) (?:from|to) .+"
                r"|index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?"
                r"|Binary files .+ differ",
                line,
            )
            is None
        ):
            raise PatchError(
                f"unified diff has unexpected metadata for {file.path}: {line}"
            )


def _check_hunks(section: str, file: PatchedFile) -> None:
    """Require the parsed hunks to account for every source line.

    unidiff ends a hunk when its declared counts are met and absorbs remaining lines
    as metadata. An extra source line must instead refuse incomplete evidence.
    """
    body_text = section.rstrip("\n")
    lines = body_text.split("\n")
    first_hunk = next(
        index for index, line in enumerate(lines) if line.startswith("@@")
    )
    body = lines[first_hunk:]
    if len(body) != len(file) + sum(len(hunk) for hunk in file):
        raise PatchError(
            f"hunk line counts for {file.path} do not match the lines under them"
        )
    # A transport may strip a blank context line's marker. The browser refuses it,
    # so capture must not store evidence the page cannot draw.
    if not all(body):
        raise PatchError(
            f"unsupported hunks for {file.path}: an empty line has no marker"
        )


def _manifest_file(section: str) -> dict:
    """Native file operations and textual hunks are independent evidence."""
    try:
        parsed = PatchSet.from_string(section)
    except UnidiffParseError as error:
        raise PatchError(f"invalid unified diff: {str(error).strip()}") from error
    if len(parsed) != 1:
        raise PatchError("unified diff needs one file per diff --git section")
    file = parsed[0]
    operation, previous, moved = _moved_paths(section)
    header = section.split("\n", 1)[0]
    marked_old, marked_new = _diff_marked_paths(section)
    if file:
        if marked_old is None or marked_new is None:
            raise PatchError(
                "unified diff has no ---/+++ file-header pair before its first hunk"
            )
        _check_hunks(section, file)
    _metadata(section, file)
    old_token = marked_old if marked_old is not None else file.source_file
    new_token = marked_new if marked_new is not None else file.target_file
    old_path = None if old_token == "/dev/null" else _marked_bare_path(old_token, "a")
    new_path = None if new_token == "/dev/null" else _marked_bare_path(new_token, "b")
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
    old_path, new_path = _decode_git_path(old_path), _decode_git_path(new_path)
    if operation is not None and (previous != old_path or moved != new_path):
        raise PatchError(
            f"unified diff {operation} paths disagree with its diff --git header"
        )
    if operation is None and old_path != new_path:
        raise PatchError(
            "unified diff has changed paths without rename or copy metadata"
        )
    operation = operation or (
        "add" if file.is_added_file else "delete" if file.is_removed_file else "modify"
    )
    if file and operation in ("add", "delete"):
        hunk = file[0]
        consuming = operation == "delete"
        start = hunk.source_start if consuming else hunk.target_start
        absent_start = hunk.target_start if consuming else hunk.source_start
        absent_length = hunk.target_length if consuming else hunk.source_length
        if len(file) != 1 or start != 1 or absent_start != 0 or absent_length != 0:
            raise PatchError(f"unified diff {operation} must capture its complete file")
    if not file and not file.is_binary_file:
        if operation == "modify" and file.source_mode == file.target_mode:
            raise PatchError(
                f"unified diff has no content or metadata change for {file.path}"
            )
        if operation in ("rename", "copy") and not re.search(
            r"^similarity index 100%$", section, re.MULTILINE
        ):
            raise PatchError(
                f"unified diff {operation} with changed content needs textual hunks"
            )
    return {
        "path": new_path,
        **({"previousPath": previous} if previous is not None else {}),
        "operation": operation,
        "hunkCount": len(file),
        "binary": file.is_binary_file,
        **({"oldMode": file.source_mode} if file.source_mode is not None else {}),
        **({"newMode": file.target_mode} if file.target_mode is not None else {}),
        "additions": file.added,
        "deletions": file.removed,
        **({"patch": section} if file else {}),
    }


def _replacement(records: list[tuple[dict, str]]) -> dict:
    """Git deletes and adds the same path when its file type changes.

    That is one logical file owner. Its native sections remain exact textual
    evidence; compressed binary bytes are not a textual payload.
    """
    if len(records) != 2 or {record["operation"] for record, _ in records} != {
        "delete",
        "add",
    }:
        raise PatchError(f"unified diff repeats file path {records[0][0]['path']!r}")
    deleted = next(record for record, _ in records if record["operation"] == "delete")
    added = next(record for record, _ in records if record["operation"] == "add")
    old_mode, new_mode = deleted.get("oldMode"), added.get("newMode")
    if (
        old_mode is None
        or new_mode is None
        or (int(old_mode, 8) & 0o170000) == (int(new_mode, 8) & 0o170000)
    ):
        raise PatchError(
            f"unified diff repeats file path {deleted['path']!r} without a file type replacement"
        )
    textual = any(record["hunkCount"] for record, _ in records)
    sections = []
    if textual:
        for record, section in records:
            if record["binary"]:
                marker = "GIT binary patch\n"
                if marker in section:
                    section = section[: section.index(marker) + len(marker)]
            sections.append(section)
    return {
        "path": added["path"],
        "operation": "modify",
        "hunkCount": int(textual),
        "binary": deleted["binary"] or added["binary"],
        "oldMode": old_mode,
        "newMode": new_mode,
        "additions": added["additions"],
        "deletions": deleted["deletions"],
        **({"patch": "".join(sections)} if textual else {}),
    }


def patch_manifest(source: str) -> dict:
    """Capture native Git operations; defer only the textual hunks a reader opens.

    unidiff owns paths, modes, binary status and hunks. Leaf keeps the exact textual
    section and records copy meaning, which unidiff otherwise classifies as a rename.
    """
    sections = [
        section
        for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE)
        if section.startswith("diff --git ")
    ]
    if not sections:
        raise PatchError("unified diff contains no files")

    files = {}
    for section in sections:
        entry = _manifest_file(section)
        files.setdefault(entry["path"], []).append((entry, section))
    return {
        "files": [
            records[0][0] if len(records) == 1 else _replacement(records)
            for records in files.values()
        ]
    }


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
