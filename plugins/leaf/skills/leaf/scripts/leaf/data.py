"""Page-bound replace-in-place data snapshot storage and commands."""

import json
import re
from pathlib import Path

import click

from .data_contracts import DataError, page_data_bindings, payload_error
from .event_log import now_iso
from .files import write_json
from .registry.contract import is_aware_datetime
from .registry.storage import require_registry
from .schema import DATA_CONTRACT_NAME, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction


def empty_data() -> dict:
    return {"revision": 0, "sources": {}}


def read_data_store(page_dir: Path) -> dict:
    """Read the private wire-shaped store without judging package payloads.

    `data clear` uses this structural reading to recover a source whose old value no
    longer passes the package's current schema. Payload schemas ran at `data set`; this
    reader checks only the store envelope that downstream consumers rely on.
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
    except json.JSONDecodeError as error:
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
    for source, snapshot in sources.items():
        if (
            not isinstance(source, str)
            or re.fullmatch(DATA_SOURCE_NAME, source) is None
        ):
            raise DataError(f"{path}: invalid source name {source!r}")
        if (
            not isinstance(snapshot, dict)
            or set(snapshot) != {"contract", "updated", "value"}
            or not isinstance(snapshot["contract"], str)
            or re.fullmatch(DATA_CONTRACT_NAME, snapshot["contract"]) is None
            or not isinstance(snapshot["updated"], str)
        ):
            raise DataError(
                f"{path}: source {source!r} must contain only contract, updated, "
                "and value"
            )
        if not is_aware_datetime(snapshot["updated"]):
            raise DataError(
                f"{path}: source {source!r} updated must be an aware RFC 3339 instant"
            )
        try:
            json.dumps(snapshot["value"], allow_nan=False)
        except (TypeError, ValueError) as error:
            raise DataError(
                f"{path}: source {source!r} value is not JSON: {error}"
            ) from error
    return stored


def read_data(page_dir: Path) -> dict:
    """Read a store whose values were validated at `data set`.

    Re-vendoring validates the same stored values once against an incoming contract.
    Polling only reads the already-admitted store; it does not rerun every package
    schema on every request.
    """
    return read_data_store(page_dir)


def cmd_data_set(page_dir: Path, source: str, value) -> None:
    """Validate and atomically replace one source's complete value."""
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
        bindings, binding_errors = page_data_bindings(page_dir, registry)
        if binding_errors:
            raise DataError(
                "the page history has conflicting data bindings: "
                + "; ".join(binding_errors)
            )
        contract = bindings.get(source)
        if contract is None:
            available = sorted(bindings)
            raise DataError(
                f"source {source!r} is not bound by any page or thread widget; "
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
        sources = {
            **stored["sources"],
            source: {"contract": contract, "updated": now_iso(), "value": value},
        }
        write_json(
            page_dir / DATA_FILE,
            {"revision": stored["revision"] + 1, "sources": sources},
        )
    click.echo(f"set data source {source!r} at revision {stored['revision'] + 1}")


def cmd_data_clear(page_dir: Path, source: str) -> None:
    """Remove one source snapshot, including one its new schema cannot read."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir):
        stored = read_data_store(page_dir)
        if source not in stored["sources"]:
            click.echo(f"data source {source!r} is already clear")
            return
        sources = {
            key: value for key, value in stored["sources"].items() if key != source
        }
        write_json(
            page_dir / DATA_FILE,
            {"revision": stored["revision"] + 1, "sources": sources},
        )
    click.echo(f"cleared data source {source!r} at revision {stored['revision'] + 1}")
