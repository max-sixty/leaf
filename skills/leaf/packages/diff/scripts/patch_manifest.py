#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Build the `unified-diff` contract's file manifest from a Git patch.

Reads a UTF-8 patch on stdin and writes manifest JSON on stdout, ready for
`leaf data set`:

    git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE SOURCE

Each record describes the native operation, paths, modes and binary status and
keeps its Git evidence in a deferred patch. Metadata-only evidence is read before
its row appears; textual hunks load when their file opens. Compressed binary
payloads are omitted: the Git binary marker records their presence.

This reads metadata and counts without judging what the widget can present.
`lf-diff` alone parses and judges the evidence, reporting a refusal to the agent.
Native delete/add sections replacing a file type share one logical file owner.
`tests/diff_patch_cases.json` holds both readers to the accepted patches' paths.
"""

import codecs
import json
import re
import sys

_MOVE = re.compile(r"^(rename|copy) from (.+)\n\1 to (.+)$", re.MULTILINE)


def _git_path(token: str) -> str:
    """One path as Git writes it, with its C-style quoting decoded."""
    if token.startswith('"'):
        return codecs.escape_decode(token[1:-1].encode())[0].decode()
    return token


def _mode(section: str, label: str) -> str | None:
    match = re.search(rf"^{label} ([0-7]{{6}})$", section, re.MULTILINE)
    return match.group(1) if match else None


def _manifest_file(section: str) -> dict:
    """Read one native section without validating its headers or hunks."""
    header, _, rest = section.partition("\n")
    if moved := _MOVE.search(rest):
        previous, path = map(_git_path, moved.group(2, 3))
        operation = moved.group(1)
    else:
        # Non-moving Git headers repeat one path, with a/ and b/ markers. Halving
        # preserves spaces and embedded " b/"; a missing marker stays for the widget
        # to refuse under its own name.
        both = header.removeprefix("diff --git ")
        previous = None
        path = _git_path(both[: (len(both) - 1) // 2]).removeprefix("a/")
        operation = (
            "add"
            if re.search(r"^new file mode ", rest, re.MULTILINE)
            else "delete"
            if re.search(r"^deleted file mode ", rest, re.MULTILINE)
            else "modify"
        )
    index = re.search(r"^index \S+ ([0-7]{6})$", rest, re.MULTILINE)
    mode = index.group(1) if index else None
    old_mode = (
        None
        if operation == "add"
        else _mode(rest, "deleted file mode") or _mode(rest, "old mode") or mode
    )
    new_mode = (
        None
        if operation == "delete"
        else _mode(rest, "new file mode") or _mode(rest, "new mode") or mode
    )
    lines = rest.partition("\n@@")[2].split("\n")
    # Keep the binary marker and its metadata, without storing Git's opaque bytes.
    marker = re.search(r"^GIT binary patch$", section, re.MULTILINE)
    patch = section[: marker.end()] + "\n" if marker else section
    return {
        "path": path,
        **({"previousPath": previous} if previous is not None else {}),
        "operation": operation,
        "hunkCount": len(re.findall(r"^@@ ", rest, re.MULTILINE)),
        "binary": bool(
            re.search(
                r"^(?:Binary files .+ differ|GIT binary patch)$", rest, re.MULTILINE
            )
        ),
        **({"oldMode": old_mode} if old_mode is not None else {}),
        **({"newMode": new_mode} if new_mode is not None else {}),
        "additions": sum(line.startswith("+") for line in lines),
        "deletions": sum(line.startswith("-") for line in lines),
        "patch": patch,
    }


def _replacement(records: list[dict]) -> dict | None:
    """Combine the two native sections of a file-type replacement.

    Other repeated paths stay separate for the manifest contract to refuse.
    The widget checks the combined record against its own reading of both sections.
    """
    if len(records) != 2 or {record["operation"] for record in records} != {
        "delete",
        "add",
    }:
        return None
    deleted = next(record for record in records if record["operation"] == "delete")
    added = next(record for record in records if record["operation"] == "add")
    old_mode, new_mode = deleted.get("oldMode"), added.get("newMode")
    if (
        old_mode is None
        or new_mode is None
        or (int(old_mode, 8) & 0o170000) == (int(new_mode, 8) & 0o170000)
    ):
        return None
    return {
        "path": added["path"],
        "operation": "modify",
        "hunkCount": int(any(record["hunkCount"] for record in records)),
        "binary": deleted["binary"] or added["binary"],
        "oldMode": old_mode,
        "newMode": new_mode,
        "additions": added["additions"],
        "deletions": deleted["deletions"],
        "patch": "".join(record["patch"] for record in records),
    }


def patch_manifest(source: str) -> dict:
    """Capture native file metadata and preserve its deferred Git evidence."""
    files = {}
    for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE):
        if section.startswith("diff --git "):
            record = _manifest_file(section)
            files.setdefault(record["path"], []).append(record)
    captured = []
    for records in files.values():
        replacement = _replacement(records)
        captured.extend([replacement] if replacement else records)
    return {"files": captured}


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
