"""Page-bound current data and immutable capture storage."""

import json
import os
import re
import stat
from pathlib import Path

import click

from .data_contracts import (
    DataError,
    page_data_bindings,
    page_data_snapshot_references,
    payload_error,
    valid_snapshot_id,
)
from .event_log import now_iso
from .files import write_json
from .registry.contract import is_aware_datetime
from .registry.storage import require_registry
from .schema import (
    DATA_CONTRACT_NAME,
    DATA_FILE,
    DATA_SOURCE_NAME,
    MAX_CAPTURE_BYTES,
    MAX_SAFE_INTEGER,
)
from .service import PageTransaction
from .structure import parse_structure


def empty_data() -> dict:
    return {"revision": 0, "sources": {}}


def _safe_positive_integer(value: str, what: str) -> int:
    if not valid_snapshot_id(value):
        raise DataError(f"{what} must be a JavaScript-safe positive integer")
    return int(value)


def _next_revision(stored: dict) -> int:
    if stored["revision"] >= MAX_SAFE_INTEGER:
        raise DataError("data revision exhausted the JavaScript-safe integer range")
    return stored["revision"] + 1


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
        start = _safe_positive_integer(start_text, "line range start")
        end = _safe_positive_integer(end_text, "line range end")
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


def read_data_store(page_dir: Path) -> dict:
    """Read the private wire-shaped store without judging package payloads.

    `data clear` uses this structural reading to recover a source whose old value no
    longer passes the package's current schema. Payload schemas ran at `data set` or
    `data capture`; this reader checks only the envelope downstream consumers rely on.
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
    if (
        isinstance(revision, bool)
        or not isinstance(revision, int)
        or not 0 <= revision <= MAX_SAFE_INTEGER
    ):
        raise DataError(
            f"{path}: revision must be a JavaScript-safe non-negative integer"
        )
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
            <= {"contract", "updated", "value", "label", "lines", "snapshots"}
            or not isinstance(source_store["contract"], str)
            or re.fullmatch(DATA_CONTRACT_NAME, source_store["contract"]) is None
        ):
            raise DataError(
                f"{path}: source {source!r} must contain a contract and only current "
                "value or snapshot fields"
            )
        has_current = "updated" in source_store or "value" in source_store
        if has_current and not {"updated", "value"} <= set(source_store):
            raise DataError(
                f"{path}: source {source!r} current value needs both updated and value"
            )
        if not has_current and ({"label", "lines"} & set(source_store)):
            raise DataError(
                f"{path}: source {source!r} capture metadata needs a current value"
            )
        if has_current:
            _validate_stored_snapshot(path, source, source_store)
        snapshots = source_store.get("snapshots", {})
        if not isinstance(snapshots, dict):
            raise DataError(f"{path}: source {source!r} snapshots must be an object")
        for snapshot_id, snapshot in snapshots.items():
            if not isinstance(snapshot_id, str):
                raise DataError(
                    f"{path}: source {source!r} has invalid snapshot id {snapshot_id!r}"
                )
            try:
                parsed_snapshot_id = _safe_positive_integer(
                    snapshot_id, f"{path}: source {source!r} snapshot id"
                )
            except DataError as error:
                raise DataError(
                    f"{path}: source {source!r} has invalid snapshot id "
                    f"{snapshot_id!r}: {error.format_message()}"
                ) from error
            if parsed_snapshot_id > revision:
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


def read_data(page_dir: Path) -> dict:
    """Read a store whose values were validated at their write boundary.

    Re-vendoring validates the same stored values once against an incoming contract.
    Polling only reads the already-admitted store; it does not rerun every package
    schema on every request.
    """
    return read_data_store(page_dir)


def _write_source(
    page_dir: Path, source: str, value, capture: dict | None = None
) -> int:
    """Validate and atomically write one current value and optional capture."""
    try:
        # Validate the value the store and browser will actually receive. Python's
        # encoder accepts values JSON itself cannot express directly — tuples become
        # arrays and non-string mapping keys become strings — so validating the
        # pre-serialization object can admit a value its own schema rejects on disk.
        value = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise DataError(f"source {source!r} value is not JSON: {error}") from error
    with PageTransaction(page_dir):
        registry = require_registry(page_dir)
        if re.fullmatch(DATA_SOURCE_NAME, source) is None:
            raise DataError(f"invalid source name {source!r}")
        extra = []
        authored = page_dir / "index.html"
        if authored.exists():
            extra.append(
                (
                    parse_structure(authored.read_text(encoding="utf-8")).lf_elements,
                    "index.html",
                )
            )
        bindings, binding_errors = page_data_bindings(page_dir, registry, extra=extra)
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
        stored = read_data_store(page_dir)
        standing = stored["sources"].get(source)
        if standing is not None and standing["contract"] != contract:
            raise DataError(
                f"source {source!r} is now bound to contract {contract!r}, but its "
                f"standing snapshot uses {standing['contract']!r}; use a new source "
                "id for the new meaning"
            )
        if error := payload_error(source, contract, value, registry):
            raise DataError(error)
        revision = _next_revision(stored)
        current = {"updated": now_iso(), "value": value, **(capture or {})}
        source_store = {"contract": contract, **current}
        snapshots = (standing or {}).get("snapshots", {})
        if capture is not None:
            snapshots = {**snapshots, str(revision): current}
        if snapshots:
            source_store["snapshots"] = snapshots
        sources = {**stored["sources"], source: source_store}
        write_json(
            page_dir / DATA_FILE,
            {"revision": revision, "sources": sources},
        )
    return revision


def cmd_data_set(page_dir: Path, source: str, value) -> None:
    """Validate and atomically replace one source's complete current value."""
    revision = _write_source(page_dir, source, value)
    click.echo(f"set data source {source!r} at revision {revision}")


def cmd_data_capture(
    page_dir: Path,
    source: str,
    text_file: Path,
    lines: str | None = None,
    label: str | None = None,
) -> None:
    """Capture UTF-8 text as both the current value and an immutable snapshot."""
    try:
        descriptor = os.open(text_file, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise DataError(f"{text_file} is not a regular file")
            if before.st_size > MAX_CAPTURE_BYTES:
                raise DataError(
                    f"{text_file} exceeds the {MAX_CAPTURE_BYTES}-byte capture limit"
                )
            raw = handle.read(MAX_CAPTURE_BYTES + 1)
            after = os.fstat(handle.fileno())
    except OSError as error:
        raise DataError(f"could not read {text_file}: {error}") from error
    if len(raw) > MAX_CAPTURE_BYTES:
        raise DataError(
            f"{text_file} exceeds the {MAX_CAPTURE_BYTES}-byte capture limit"
        )
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity or len(raw) != after.st_size:
        raise DataError(f"{text_file} changed while it was read; try again")
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DataError(f"{text_file} is not UTF-8: {error}") from error
    if "\0" in value:
        raise DataError(f"{text_file} contains U+0000, which HTML cannot preserve")
    # HTML parsing and serialization normalize carriage-return line endings. Normalize
    # once at admission so live rendering, comments, and standalone export share the
    # exact same string.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if lines is not None:
        match = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)", lines)
        if match is None:
            raise DataError("lines must be a one-based inclusive START:END range")
        start = _safe_positive_integer(match.group(1), "line range start")
        end = _safe_positive_integer(match.group(2), "line range end")
        available = value.splitlines(keepends=True)
        if end < start or end > len(available):
            raise DataError(
                f"lines {lines} are outside {text_file}, which has "
                f"{len(available)} lines"
            )
        value = "".join(available[start - 1 : end])
    capture_label = text_file.name if label is None else label
    if not capture_label:
        raise DataError("label must be a non-empty string")

    capture = {"label": capture_label}
    if lines is not None:
        capture["lines"] = lines
    revision = _write_source(page_dir, source, value, capture)
    click.echo(f"captured data source {source!r} as snapshot {revision}")


def cmd_data_clear(page_dir: Path, source: str) -> None:
    """Remove current and unreferenced captures, even under a changed schema."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir):
        stored = read_data_store(page_dir)
        if source not in stored["sources"]:
            click.echo(f"data source {source!r} is already clear")
            return
        registry = require_registry(page_dir)
        extra = []
        authored = page_dir / "index.html"
        if authored.exists():
            extra.append(
                (
                    parse_structure(authored.read_text(encoding="utf-8")).lf_elements,
                    "index.html",
                )
            )
        referenced = page_data_snapshot_references(page_dir, registry, extra=extra)
        standing = stored["sources"][source]
        retained = {
            snapshot_id: snapshot
            for snapshot_id, snapshot in standing.get("snapshots", {}).items()
            if snapshot_id in referenced.get(source, set())
        }
        sources = dict(stored["sources"])
        sources[source] = {"contract": standing["contract"]}
        if retained:
            sources[source]["snapshots"] = retained
        if sources == stored["sources"]:
            click.echo(f"data source {source!r} is already clear")
            return
        revision = _next_revision(stored)
        write_json(
            page_dir / DATA_FILE,
            {"revision": revision, "sources": sources},
        )
    click.echo(f"cleared data source {source!r} at revision {revision}")
