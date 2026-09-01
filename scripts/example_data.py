"""Read the external-data companions shipped beside authored examples."""

import json
import re
from pathlib import Path


def unified_diff_manifest(path: Path) -> dict:
    """Split one fixture patch into the manifest Leaf delivers file by file."""
    text = path.read_text(encoding="utf-8")
    sections = [
        section
        for section in re.split(r"(?=^diff --git )", text, flags=re.MULTILINE)
        if section.startswith("diff --git ")
    ]
    if not sections:
        raise ValueError(f"{path}: unified diff contains no files")
    files = []
    for section in sections:
        previous = re.search(r"^rename from (.+)$", section, re.MULTILINE)
        renamed = re.search(r"^rename to (.+)$", section, re.MULTILINE)
        if previous or renamed:
            if not previous or not renamed:
                raise ValueError(f"{path}: incomplete rename block")
            file_path = renamed.group(1)
            kind = "rename"
        else:
            after = re.search(r"^\+\+\+ (.+)$", section, re.MULTILINE)
            before = re.search(r"^--- (.+)$", section, re.MULTILINE)
            chosen = after.group(1) if after and after.group(1) != "/dev/null" else None
            chosen = chosen or (before.group(1) if before else None)
            if not chosen or chosen == "/dev/null":
                raise ValueError(f"{path}: diff file has no old or new path")
            file_path = re.sub(r"^[ab]/", "", chosen)
            kind = "patch"
        additions = deletions = 0
        in_hunk = False
        for line in section.splitlines():
            if line.startswith("@@ "):
                in_hunk = True
            elif in_hunk and line.startswith("+"):
                additions += 1
            elif in_hunk and line.startswith("-"):
                deletions += 1
        files.append(
            {
                "key": file_path,
                "path": file_path,
                **({"previousPath": previous.group(1)} if previous else {}),
                "kind": kind,
                "additions": additions,
                "deletions": deletions,
                "patch": section,
            }
        )
    return {"files": files}


def imported_value(source: Path, spec: dict):
    """Read one structured fixture import beside its authored example."""
    if set(spec) != {"unified-diff-file", "label"}:
        raise ValueError(
            f"{source.with_suffix('.data.json')}: import must carry "
            "unified-diff-file and label"
        )
    return unified_diff_manifest(source.parent / spec["unified-diff-file"])


def data_operations(source: Path) -> list[dict]:
    """Return captures first, then replaceable values, for one example source."""
    companion = source.with_suffix(".data.json")
    if not companion.exists():
        return []
    document = json.loads(companion.read_text(encoding="utf-8"))

    operations = [
        {
            "kind": "set",
            "source": name,
            "value": imported_value(source, spec),
            "capture_label": spec["label"],
        }
        for name, spec in document.pop("$imports", {}).items()
    ]
    for name, spec in document.pop("$captures", {}).items():
        operations.append(
            {
                "kind": "capture",
                "source": name,
                "text_file": source.parent / spec["text-file"],
                "label": spec.get("label"),
                "lines": spec.get("lines"),
            }
        )
    operations.extend(
        {"kind": "set", "source": name, "value": value, "capture_label": None}
        for name, value in document.items()
    )
    return operations
