"""Page-bound current data and immutable capture storage."""

import json
import re
from pathlib import Path

import click

from .data_contracts import (
    DataError,
    payload_error,
    working_data_bindings,
    working_data_snapshot_references,
)
from .event_log import now_iso
from .files import write_json
from .registry.contract import is_aware_datetime
from .registry.storage import require_registry
from .schema import DATA_CONTRACT_NAME, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction

_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>[0-9]+)(?:,(?P<old_count>[0-9]+))? "
    r"\+(?P<new_start>[0-9]+)(?:,(?P<new_count>[0-9]+))? @@(?: .*)?$"
)
_GIT_PATH_TOKEN = r'(?:(?:"(?:\\.|[^"\\])*")|\S+)'

_GIT_PATH_ESCAPES = {
    "a": 0x07,
    "b": 0x08,
    "t": 0x09,
    "n": 0x0A,
    "v": 0x0B,
    "f": 0x0C,
    "r": 0x0D,
    '"': 0x22,
    "\\": 0x5C,
}


def _decode_git_path(path: str) -> str:
    """Decode the C-style quoting Git uses for diff path fields."""
    if not path.startswith('"'):
        return path
    if len(path) < 2 or not path.endswith('"'):
        raise DataError(f"invalid quoted Git path {path!r}")
    encoded = bytearray()
    inner = path[1:-1]
    index = 0
    while index < len(inner):
        character = inner[index]
        if character != "\\":
            encoded.extend(character.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index == len(inner):
            raise DataError(f"invalid quoted Git path {path!r}")
        escaped = inner[index]
        if escaped in _GIT_PATH_ESCAPES:
            encoded.append(_GIT_PATH_ESCAPES[escaped])
            index += 1
            continue
        if escaped in "01234567":
            end = index + 1
            while end < min(index + 3, len(inner)) and inner[end] in "01234567":
                end += 1
            byte = int(inner[index:end], 8)
            if byte > 0xFF:
                raise DataError(f"invalid quoted Git path escape \\{inner[index:end]}")
            encoded.append(byte)
            index = end
            continue
        raise DataError(f"invalid quoted Git path escape \\{escaped}")
    if 0 in encoded:
        raise DataError("quoted Git path contains a NUL byte")
    try:
        return encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DataError(f"quoted Git path is not UTF-8: {path!r}") from error


def _diff_header_path(side: str, path: str) -> str:
    return (
        f'"{side}/{path[1:]}'
        if path.startswith('"') and path.endswith('"')
        else f"{side}/{path}"
    )


def _diff_header_paths(
    section: str,
    marked_old: str | None = None,
    marked_new: str | None = None,
) -> tuple[str, str]:
    header = section.split("\n", 1)[0]
    match = re.fullmatch(
        rf"diff --git (?P<old>{_GIT_PATH_TOKEN}) (?P<new>{_GIT_PATH_TOKEN})",
        header,
    )
    if match is None:
        # Git leaves ordinary spaces unquoted in `diff --git` and terminates the
        # unambiguous ---/+++ paths with a tab instead. Reconstruct the header from
        # that already-parsed pair rather than guessing where one path ends.
        if marked_old is None or marked_new is None:
            raise DataError(f"invalid Git diff header: {header}")
        old = None if marked_old == "/dev/null" else _diff_display_path(marked_old)
        new = None if marked_new == "/dev/null" else _diff_display_path(marked_new)
        old = old or new
        new = new or old
        if (
            old is None
            or new is None
            or header
            != (
                f"diff --git {_diff_header_path('a', old)} "
                f"{_diff_header_path('b', new)}"
            )
        ):
            raise DataError(f"invalid Git diff header: {header}")
        return old, new
    old = _decode_git_path(match.group("old"))
    new = _decode_git_path(match.group("new"))
    if not old.startswith("a/") or not new.startswith("b/"):
        raise DataError(f"invalid Git diff paths: {header}")
    return old[2:], new[2:]


def _diff_display_path(path: str) -> str:
    """Decode one Git header path and remove its a/ or b/ side marker."""
    decoded = _decode_git_path(path)
    return decoded[2:] if decoded.startswith(("a/", "b/")) else decoded


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
        raise DataError("unified diff needs one adjacent ---/+++ file-header pair")
    # A traditional unified header may append a timestamp after a tab. Git's quoted
    # paths keep whitespace inside the quotes and need no special casing here.
    return old[0][1].split("\t", 1)[0], new[0][1].split("\t", 1)[0]


def _diff_rename_paths(section: str) -> tuple[str | None, str | None]:
    previous = re.search(r"^rename from (.+)$", section, re.MULTILINE)
    renamed = re.search(r"^rename to (.+)$", section, re.MULTILINE)
    if bool(previous) != bool(renamed):
        raise DataError("unified diff has an incomplete rename block")
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


def _diff_hunk_counts(section: str, path: str) -> tuple[int, int]:
    """Validate every textual hunk and return its additions and deletions."""
    lines = section.rstrip("\n").split("\n")
    starts = [index for index, line in enumerate(lines) if line.startswith("@@")]
    if not starts:
        raise DataError(
            f"unsupported hunkless diff for {path}; only exact path-only renames "
            "may omit textual @@ hunks"
        )
    additions = deletions = 0
    for position, start in enumerate(starts):
        header = _HUNK_HEADER.fullmatch(lines[start])
        if header is None:
            raise DataError(f"invalid hunk header for {path}: {lines[start]}")
        old_expected = int(header.group("old_count") or 1)
        new_expected = int(header.group("new_count") or 1)
        old_seen = new_seen = 0
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        for line in lines[start + 1 : end]:
            if line == r"\ No newline at end of file":
                continue
            if not line or line[0] not in " +-":
                raise DataError(f"invalid hunk line for {path}: {line!r}")
            if line[0] in " -":
                old_seen += 1
            if line[0] in " +":
                new_seen += 1
            if line[0] == "-":
                deletions += 1
            elif line[0] == "+":
                additions += 1
        if (old_seen, new_seen) != (old_expected, new_expected):
            raise DataError(
                f"hunk line counts for {path} are {old_seen} old and {new_seen} new; "
                f"the header declares {old_expected} old and {new_expected} new"
            )
    return additions, deletions


def unified_diff_manifest(source: str) -> dict:
    """Parse one supported Git unified patch into Leaf's fragmented manifest."""
    sections = [
        section
        for section in re.split(r"(?=^diff --git )", source, flags=re.MULTILINE)
        if section.startswith("diff --git ")
    ]
    if not sections:
        raise DataError("unified diff contains no files")

    files = []
    paths = set()
    for section in sections:
        if re.search(r"^copy (?:from|to) ", section, re.MULTILINE):
            raise DataError(
                "unsupported copy diff; omit copy metadata and provide textual @@ "
                "hunks for an edited destination"
            )
        previous, renamed = _diff_rename_paths(section)
        pure_rename = _path_only_rename(section)
        if pure_rename is not None:
            previous, path = pure_rename
            additions = deletions = 0
            kind = "rename"
        else:
            old_header, new_header = _diff_marked_paths(section)
            header_old, header_new = _diff_header_paths(section, old_header, new_header)
            if old_header is None or new_header is None:
                if re.search(r"^@@", section, re.MULTILINE):
                    raise DataError(
                        "unified diff has no ---/+++ file-header pair before its first hunk"
                    )
                if previous is not None or renamed is not None:
                    raise DataError(
                        "unsupported hunkless rename; only the exact four-line "
                        "path-only form may omit textual @@ hunks"
                    )
                header = section.split("\n", 1)[0]
                raise DataError(f"unsupported hunkless diff: {header}")
            if old_header == new_header == "/dev/null":
                raise DataError("diff file has no old or new path")
            marked_old = (
                "/dev/null"
                if old_header == "/dev/null"
                else _diff_display_path(old_header)
            )
            marked_new = (
                "/dev/null"
                if new_header == "/dev/null"
                else _diff_display_path(new_header)
            )
            if (marked_old != "/dev/null" and marked_old != header_old) or (
                marked_new != "/dev/null" and marked_new != header_new
            ):
                raise DataError(
                    "unified diff ---/+++ paths disagree with its diff --git header"
                )
            if (previous is not None and previous != header_old) or (
                renamed is not None and renamed != header_new
            ):
                raise DataError(
                    "unified diff rename paths disagree with its diff --git header"
                )
            selected = new_header if new_header != "/dev/null" else old_header
            path = renamed or _diff_display_path(selected)
            additions, deletions = _diff_hunk_counts(section, path)
            kind = "patch"
        if path in paths:
            raise DataError(f"unified diff repeats file path {path!r}")
        paths.add(path)
        files.append(
            {
                "key": path,
                "path": path,
                **({"previousPath": previous} if previous is not None else {}),
                "kind": kind,
                "additions": additions,
                "deletions": deletions,
                "patch": section,
            }
        )
    return {"files": files}


def empty_data() -> dict:
    return {"revision": 0, "sources": {}}


def _validate_stored_snapshot(
    path: Path, source: str, snapshot: dict, snapshot_id: str | None = None
) -> None:
    identity = f" snapshot {snapshot_id!r}" if snapshot_id is not None else ""
    if not isinstance(snapshot["updated"], str) or not is_aware_datetime(
        snapshot["updated"]
    ):
        raise DataError(
            f"{path}: source {source!r}{identity} updated must be an aware RFC 3339 "
            "instant"
        )
    if "label" in snapshot and (
        not isinstance(snapshot["label"], str) or not snapshot["label"]
    ):
        raise DataError(
            f"{path}: source {source!r}{identity} label must be a non-empty string"
        )
    if "lines" in snapshot and (
        not isinstance(snapshot["lines"], str)
        or re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", snapshot["lines"]) is None
    ):
        raise DataError(f"{path}: source {source!r}{identity} lines must be START:END")
    if "lines" in snapshot:
        start_text, end_text = snapshot["lines"].split(":")
        start = int(start_text)
        end = int(end_text)
        if end < start:
            raise DataError(
                f"{path}: source {source!r}{identity} lines must end at or after "
                "they start"
            )
    try:
        json.dumps(snapshot["value"], allow_nan=False)
    except (TypeError, ValueError) as error:
        raise DataError(
            f"{path}: source {source!r}{identity} value is not JSON: {error}"
        ) from error


def read_data(page_dir: Path) -> dict:
    """Read the private wire-shaped store without judging package payloads.

    Payload schemas ran at `data set` or `data capture`, and re-vendoring checks
    the stored values once against an incoming contract; this reader checks only
    the envelope downstream consumers rely on, so `data clear` can recover a
    source whose old value no longer passes the package's current schema and a
    poll never reruns every package schema.
    """
    path = page_dir / DATA_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return empty_data()
    except UnicodeDecodeError as error:
        raise DataError(f"{path}: invalid JSON ({error})") from error
    try:
        stored = json.loads(text)
    except (json.JSONDecodeError, ValueError) as error:
        raise DataError(f"{path}: invalid JSON ({error})") from error
    if not isinstance(stored, dict) or set(stored) != {"revision", "sources"}:
        raise DataError(
            f"{path}: data must be an object with only revision and sources"
        )
    revision = stored["revision"]
    sources = stored["sources"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise DataError(f"{path}: revision must be a non-negative integer")
    if not isinstance(sources, dict):
        raise DataError(f"{path}: sources must be an object")
    for source, source_store in sources.items():
        if (
            not isinstance(source, str)
            or re.fullmatch(DATA_SOURCE_NAME, source) is None
        ):
            raise DataError(f"{path}: invalid source name {source!r}")
        if (
            not isinstance(source_store, dict)
            or "contract" not in source_store
            or not set(source_store)
            <= {
                "contract",
                "revisions",
                "revision",
                "updated",
                "value",
                "label",
                "lines",
                "snapshots",
            }
            or not isinstance(source_store["contract"], str)
            or re.fullmatch(DATA_CONTRACT_NAME, source_store["contract"]) is None
        ):
            raise DataError(
                f"{path}: source {source!r} must contain a contract and only current "
                "value or snapshot fields"
            )
        revisions = source_store.get("revisions")
        if (
            not isinstance(revisions, list)
            or not revisions
            or any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or not 1 <= item <= revision
                for item in revisions
            )
            or revisions != sorted(set(revisions))
        ):
            raise DataError(
                f"{path}: source {source!r} revisions must be sorted unique positive "
                f"integers no greater than data revision {revision}"
            )
        has_current = bool({"revision", "updated", "value"} & set(source_store))
        if has_current and not {"revision", "updated", "value"} <= set(source_store):
            raise DataError(
                f"{path}: source {source!r} current value needs revision, updated, "
                "and value"
            )
        if not has_current and ({"label", "lines"} & set(source_store)):
            raise DataError(
                f"{path}: source {source!r} capture metadata needs a current value"
            )
        if has_current:
            source_revision = source_store["revision"]
            if (
                isinstance(source_revision, bool)
                or not isinstance(source_revision, int)
                or not 1 <= source_revision <= revision
                or source_revision not in revisions
            ):
                raise DataError(
                    f"{path}: source {source!r} revision must be a positive integer "
                    f"no greater than data revision {revision}"
                )
            _validate_stored_snapshot(path, source, source_store)
        snapshots = source_store.get("snapshots", {})
        if not isinstance(snapshots, dict):
            raise DataError(f"{path}: source {source!r} snapshots must be an object")
        for snapshot_id, snapshot in snapshots.items():
            if not isinstance(snapshot_id, str):
                raise DataError(
                    f"{path}: source {source!r} has invalid snapshot id {snapshot_id!r}"
                )
            if (
                re.fullmatch(r"[1-9][0-9]*", snapshot_id) is None
                or int(snapshot_id) > revision
                or int(snapshot_id) not in revisions
            ):
                raise DataError(
                    f"{path}: source {source!r} has invalid snapshot id {snapshot_id!r}"
                )
            if (
                not isinstance(snapshot, dict)
                or not {"updated", "value", "label"} <= set(snapshot)
                or not set(snapshot) <= {"updated", "value", "label", "lines"}
            ):
                raise DataError(
                    f"{path}: source {source!r} snapshot {snapshot_id!r} must contain "
                    "updated, value, label, and optional lines"
                )
            _validate_stored_snapshot(path, source, snapshot, snapshot_id)
    return stored


def data_fragments(value, contract: str, registry: dict) -> dict | None:
    """The split-delivery coordinate of this validated value's manifest branch.

    A contract may admit both an inline value and a manifest. Its fragment
    declaration applies only to an object carrying the declared item array.
    """
    spec = (
        registry.get("$data", {})
        .get("contracts", {})
        .get(contract, {})
        .get("fragments")
    )
    return (
        spec
        if spec is not None
        and isinstance(value, dict)
        and isinstance(value.get(spec["items"]), list)
        else None
    )


def data_manifest(value, contract: str, registry: dict):
    """Keep a contract's manifest while leaving large payloads at their source.

    Both browser delivery and agent inspection use this projection. It never
    mutates its input and returns the original value when there is no split.
    """
    spec = data_fragments(value, contract, registry)
    if spec is None:
        return value
    return {
        **value,
        spec["items"]: [
            {key: item for key, item in record.items() if key != spec["value"]}
            for record in value[spec["items"]]
        ],
    }


def browser_data(page_dir: Path, registry: dict | None) -> dict:
    """Project the source store to the lightweight snapshot sent in page state.

    ``data.json`` remains the complete authority.  A contract may mark one field on
    each item as a separately delivered fragment; page state carries the surrounding
    manifest and the fragment door reads the omitted value from that same store.
    """
    stored = read_data(page_dir)
    # State remains readable when an older page's frozen vocabulary no longer
    # validates against this layer. Without a trustworthy fragment declaration,
    # send the complete value: the broken registry already prevents interaction,
    # while the readable state lets the browser and Stop hook explain that failure.
    if registry is None:
        return stored
    for source_store in stored["sources"].values():
        source_store.pop("revisions", None)
        for snapshot in [source_store, *source_store.get("snapshots", {}).values()]:
            if "value" in snapshot:
                snapshot["value"] = data_manifest(
                    snapshot["value"], source_store["contract"], registry
                )
    return stored


def read_data_fragment(
    page_dir: Path,
    registry: dict,
    *,
    data_revision: int,
    source: str,
    key: str,
    snapshot_id: str | None = None,
) -> dict:
    """Read one declared fragment from the exact source revision a tab accepted."""
    stored = read_data(page_dir)
    if stored["revision"] != data_revision:
        raise DataError(
            f"data revision {data_revision} is stale; current revision is "
            f"{stored['revision']}"
        )
    source_store = stored["sources"].get(source)
    if source_store is None:
        raise DataError(f"unknown data source {source!r}")
    selected = source_store
    if snapshot_id is not None:
        selected = source_store.get("snapshots", {}).get(snapshot_id)
        if selected is None:
            raise DataError(f"data source {source!r} has no snapshot {snapshot_id!r}")
    value = selected.get("value")
    spec = data_fragments(value, source_store["contract"], registry)
    if spec is None:
        raise DataError(f"data source {source!r} has no fragmented value")
    items = value[spec["items"]]
    matches = [
        item
        for item in items
        if isinstance(item, dict) and item.get(spec["key"]) == key
    ]
    if len(matches) != 1:
        reason = "unknown" if not matches else "duplicate"
        raise DataError(f"{reason} fragment key {key!r} in data source {source!r}")
    item = matches[0]
    if spec["value"] not in item:
        raise DataError(f"fragment {key!r} in data source {source!r} has no value")
    return {
        "revision": stored["revision"],
        "source": source,
        "contract": source_store["contract"],
        **({"snapshot": snapshot_id} if snapshot_id is not None else {}),
        "key": key,
        "value": item[spec["value"]],
    }


def _write_source(
    page_dir: Path, source: str, value, capture: dict | None = None
) -> tuple[int, str]:
    """Validate and atomically write one current value and optional capture,
    returning the data revision and the `updated` instant it stamped."""
    try:
        # Validate the value the store and browser will actually receive. Python's
        # encoder accepts values JSON itself cannot express directly — tuples become
        # arrays and non-string mapping keys become strings — so validating the
        # pre-serialization object can admit a value its own schema rejects on disk.
        value = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise DataError(f"source {source!r} value is not JSON: {error}") from error
    with PageTransaction(page_dir) as page:
        registry = require_registry(page_dir)
        if re.fullmatch(DATA_SOURCE_NAME, source) is None:
            raise DataError(f"invalid source name {source!r}")
        bindings, binding_errors = working_data_bindings(
            page_dir, registry, page.events
        )
        if binding_errors:
            raise DataError(
                "the page history has conflicting data bindings: "
                + "; ".join(binding_errors)
            )
        contract = bindings.get(source)
        if contract is None:
            available = sorted(bindings)
            raise DataError(
                f"source {source!r} is not bound by the page source, a version, or "
                "a thread widget; "
                f"choose one of {available}"
            )
        stored = read_data(page_dir)
        standing = stored["sources"].get(source)
        if standing is not None and standing["contract"] != contract:
            raise DataError(
                f"source {source!r} is now bound to contract {contract!r}, but its "
                f"standing snapshot uses {standing['contract']!r}; use a new source "
                "id for the new meaning"
            )
        if error := payload_error(source, contract, value, registry):
            raise DataError(error)
        revision = stored["revision"] + 1
        current = {
            "revision": revision,
            "updated": now_iso(),
            "value": value,
            **(capture or {}),
        }
        revisions = [*(standing or {}).get("revisions", []), revision]
        source_store = {"contract": contract, "revisions": revisions, **current}
        snapshots = (standing or {}).get("snapshots", {})
        if capture is not None:
            captured = {
                key: value for key, value in current.items() if key != "revision"
            }
            snapshots = {**snapshots, str(revision): captured}
        if snapshots:
            source_store["snapshots"] = snapshots
        sources = {**stored["sources"], source: source_store}
        write_json(
            page_dir / DATA_FILE,
            {"revision": revision, "sources": sources},
        )
    return revision, current["updated"]


def cmd_data_set(
    page_dir: Path, source: str, value, capture_label: str | None = None
) -> None:
    """Validate and atomically replace one source's complete current value."""
    if capture_label is not None and not capture_label:
        raise DataError("capture label must be a non-empty string")
    capture = {"label": capture_label} if capture_label is not None else None
    revision, updated = _write_source(page_dir, source, value, capture)
    verb = "captured" if capture is not None else "set"
    click.echo(
        f"{verb} data source {source!r} at revision {revision}, updated {updated}"
    )


def cmd_data_capture(
    page_dir: Path,
    source: str,
    input_file: Path,
    lines: str | None = None,
    label: str | None = None,
    capture_format: str = "text",
) -> None:
    """Capture one UTF-8 file as the current value and an immutable snapshot."""
    try:
        value = input_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise DataError(f"could not read {input_file}: {error}") from error
    if capture_format not in {"text", "unified-diff"}:
        raise DataError(f"unsupported capture format {capture_format!r}")
    if capture_format == "unified-diff":
        if lines is not None:
            raise DataError("lines can only select part of a text capture")
        value = unified_diff_manifest(value)
    if lines is not None:
        match = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)", lines)
        if match is None:
            raise DataError("lines must be a one-based inclusive START:END range")
        start = int(match.group(1))
        end = int(match.group(2))
        available = value.splitlines(keepends=True)
        if end < start or end > len(available):
            raise DataError(
                f"lines {lines} are outside {input_file}, which has "
                f"{len(available)} lines"
            )
        value = "".join(available[start - 1 : end])
    capture_label = input_file.name if label is None else label
    if not capture_label:
        raise DataError("label must be a non-empty string")

    capture = {"label": capture_label}
    if lines is not None:
        capture["lines"] = lines
    revision, updated = _write_source(page_dir, source, value, capture)
    click.echo(
        f"captured data source {source!r} as snapshot {revision}, updated {updated}"
    )


def cmd_data_clear(page_dir: Path, source: str) -> None:
    """Remove current and unreferenced captures, even under a changed schema."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir) as page:
        stored = read_data(page_dir)
        if source not in stored["sources"]:
            click.echo(f"data source {source!r} is already clear")
            return
        registry = require_registry(page_dir)
        referenced = working_data_snapshot_references(page_dir, registry, page.events)
        standing = stored["sources"][source]
        retained = {
            snapshot_id: snapshot
            for snapshot_id, snapshot in standing.get("snapshots", {}).items()
            if snapshot_id in referenced.get(source, set())
        }
        sources = dict(stored["sources"])
        sources[source] = {
            "contract": standing["contract"],
            "revisions": standing["revisions"],
        }
        if retained:
            sources[source]["snapshots"] = retained
        if sources == stored["sources"]:
            click.echo(f"data source {source!r} is already clear")
            return
        revision = stored["revision"] + 1
        write_json(
            page_dir / DATA_FILE,
            {"revision": revision, "sources": sources},
        )
    click.echo(f"cleared data source {source!r} at revision {revision}")
