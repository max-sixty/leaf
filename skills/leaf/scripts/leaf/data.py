"""Page-bound current data and immutable capture storage."""

import codecs
import json
import re
from pathlib import Path

import click
from unidiff import PatchedFile, PatchSet, UnidiffParseError

from .data_contracts import (
    DataError,
    payload_error,
    working_data_bindings,
    working_data_snapshot_references,
)
from .event_log import now_iso
from .files import write_json
from .registry.contract import is_aware_datetime
from .registry.storage import read_page_registry
from .schema import DATA_CONTRACT_NAME, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction

# From here to `unified_diff_manifest`, whose docstring states the division: unidiff
# reads the hunks, and everything here owns the manifest built around them.
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
        raise DataError(f"invalid quoted Git path {path!r}")
    inner = path[1:-1]
    if _GIT_QUOTED_PATH.fullmatch(inner) is None:
        raise DataError(f"invalid quoted Git path {path!r}")
    encoded = codecs.escape_decode(inner.encode("utf-8"))[0]
    if 0 in encoded:
        raise DataError("quoted Git path contains a NUL byte")
    try:
        return encoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DataError(f"quoted Git path is not UTF-8: {path!r}") from error


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
    raise DataError(f"unified diff path {token!r} has no {marker} side marker")


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
        raise DataError(f"unsupported hunks for {path}: {detail}") from error
    if len(parsed) != 1:
        raise DataError(f"unified diff repeats a file header inside {path}")
    patched = parsed[0]
    if not patched:
        raise DataError(
            f"unsupported hunkless diff for {path}; only exact path-only renames "
            "may omit textual @@ hunks"
        )
    lines = body_text.rstrip("\n").split("\n")
    first_hunk = next(
        index for index, line in enumerate(lines) if line.startswith("@@")
    )
    body = lines[first_hunk:]
    if len(body) != len(patched) + sum(len(hunk) for hunk in patched):
        raise DataError(
            f"hunk line counts for {path} do not match the lines under them"
        )
    # unidiff reads a bare empty line as an empty context line, for a patch that
    # crossed a transport which strips trailing whitespace. `lf-diff` refuses one,
    # so capture refuses it too rather than storing evidence the page cannot draw.
    if not all(body):
        raise DataError(f"unsupported hunks for {path}: an empty line has no marker")
    return patched


def _manifest_file(section: str) -> dict:
    """One manifest entry for one `diff --git` section of the captured patch."""
    if re.search(r"^copy (?:from|to) ", section, re.MULTILINE):
        raise DataError(
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
            raise DataError(
                "unified diff has no ---/+++ file-header pair before its first hunk"
            )
        if previous is not None or renamed is not None:
            raise DataError(
                "unsupported hunkless rename; only the exact four-line "
                "path-only form may omit textual @@ hunks"
            )
        raise DataError(f"unsupported hunkless diff: {header}")

    # Git leaves ordinary spaces unquoted in `diff --git` and terminates the
    # unambiguous ---/+++ paths with a tab instead, so the header is compared with
    # the pair rebuilt from those paths rather than split at a guessed space. An
    # added or deleted file names /dev/null on one side and the surviving path on
    # both sides of the header.
    old_path = None if marked_old == "/dev/null" else _marked_bare_path(marked_old, "a")
    new_path = None if marked_new == "/dev/null" else _marked_bare_path(marked_new, "b")
    if old_path is None and new_path is None:
        raise DataError("diff file has no old or new path")
    old_path = old_path or new_path
    new_path = new_path or old_path
    if header != (
        f"diff --git {_diff_header_path('a', old_path)} "
        f"{_diff_header_path('b', new_path)}"
    ):
        raise DataError(
            "unified diff ---/+++ paths disagree with its diff --git header"
        )
    if (previous is not None and previous != _decode_git_path(old_path)) or (
        renamed is not None and renamed != _decode_git_path(new_path)
    ):
        raise DataError("unified diff rename paths disagree with its diff --git header")

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


def unified_diff_manifest(source: str) -> dict:
    """One captured Git patch as Leaf's fragmented manifest.

    Leaf owns the manifest and unidiff owns the hunks inside it. Each entry
    carries the file's key and paths, its change counts, and the verbatim section
    of the captured text that `lf-diff` renders once its disclosure opens — which
    is why the source is split here rather than rebuilt from unidiff's reading.

    Capture refuses what the widget cannot present as review evidence. Two of
    those refusals are Leaf's alone: copy metadata, which unidiff reads as a
    rename, and a hunkless entry that is not the exact four-line path-only
    rename, which it reports as a file with no hunks."""
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
        entry = _manifest_file(section)
        if entry["path"] in paths:
            raise DataError(f"unified diff repeats file path {entry['path']!r}")
        paths.add(entry["path"])
        files.append(entry)
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


def browser_data_from(stored: dict, registry: dict | None) -> dict:
    """Project a complete source store to the lightweight browser snapshot.

    ``data.json`` remains the complete authority.  A contract may mark one field on
    each item as a separately delivered fragment; page state carries the surrounding
    manifest and the fragment door reads the omitted value from that same store.
    """
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


def browser_data(page_dir: Path, registry: dict | None) -> dict:
    """Read and project the page's current source store for a live response."""
    return browser_data_from(read_data(page_dir), registry)


def data_fragment(
    stored: dict,
    registry: dict,
    *,
    data_revision: int,
    source: str,
    key: str,
    snapshot_id: str | None = None,
) -> dict:
    """Project one fragment from the exact source store a tab accepted."""
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


def read_data_fragment(
    page_dir: Path,
    registry: dict,
    *,
    data_revision: int,
    source: str,
    key: str,
    snapshot_id: str | None = None,
) -> dict:
    """Read and project one fragment from the page's current source store."""
    return data_fragment(
        read_data(page_dir),
        registry,
        data_revision=data_revision,
        source=source,
        key=key,
        snapshot_id=snapshot_id,
    )


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
        registry = read_page_registry(page_dir).registry
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
        registry = read_page_registry(page_dir).registry
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
