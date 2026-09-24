"""Page-bound external data: one plain JSON file per source.

`data.json` records the contract each source id was first bound to, which it keeps
for the page's lifetime; `data/<source>.json` holds that source's current value as
ordinary JSON. `leaf data set` validates before it writes, but any
process may replace a value file, so every reading validates the value against its
contract and reports a failing one as that source's `error` rather than its value.

A source's revision is a digest of its file's bytes and `updated` its modification
time. Nothing retains an earlier value: a reader or anchor naming a revision the
source no longer holds is reading a replaced value. A document that must keep one
value binds a source id nothing rewrites.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import click

from .data_contracts import DataError, payload_error, working_data_bindings
from .files import json_bytes, replace_files
from .registry.storage import read_page_registry
from .schema import DATA_CONTRACT_NAME, DATA_DIR, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction


class StaleDataError(DataError):
    """A deferred-value request named a source revision the source no longer holds."""


def source_file(page_dir: Path, source: str) -> Path:
    return page_dir / DATA_DIR / f"{source}.json"


def read_contracts(page_dir: Path) -> dict[str, str]:
    """Source id → the contract `data.json` records for it."""
    path = page_dir / DATA_FILE
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (UnicodeDecodeError, ValueError) as error:
        raise DataError(f"{path}: invalid JSON ({error})") from error
    sources = stored.get("sources") if isinstance(stored, dict) else None
    if not isinstance(sources, dict) or set(stored) != {"sources"}:
        raise DataError(f"{path}: data must be an object with only sources")
    contracts = {}
    for source, entry in sources.items():
        if (
            re.fullmatch(DATA_SOURCE_NAME, source) is None
            or not isinstance(entry, dict)
            or set(entry) != {"contract"}
            or not isinstance(entry["contract"], str)
            or re.fullmatch(DATA_CONTRACT_NAME, entry["contract"]) is None
        ):
            raise DataError(f"{path}: source {source!r} must record only a contract")
        contracts[source] = entry["contract"]
    return contracts


# (source, contract declaration, revision) → validation error. Every state reading
# re-reads each value file, and a large value costs far more to validate than to
# digest, so a server judges each distinct value once.
_JUDGED: dict[tuple[str, str, str], str | None] = {}


def _value_error(source: str, contract: str, value, revision: str, registry: dict):
    declaration = json.dumps(
        registry.get("$data", {}).get("contracts", {}).get(contract), sort_keys=True
    )
    key = source, declaration, revision
    if key not in _JUDGED:
        if len(_JUDGED) >= 1024:
            _JUDGED.clear()
        _JUDGED[key] = payload_error(source, contract, value, registry)
    return _JUDGED[key]


def _refuse_constant(name: str):
    """Python's reader accepts NaN and Infinity; JSON, and the browser, do not."""
    raise ValueError(f"{name} is not JSON")


def read_source(page_dir: Path, source: str, contract: str, registry: dict) -> dict:
    """One source as readers receive it: its contract, and, once a value file
    exists, that file's revision, `updated` instant, and `value` or `error`."""
    path = source_file(page_dir, source)
    try:
        data = path.read_bytes()
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return {"contract": contract}
    reading = {
        "contract": contract,
        "revision": hashlib.sha256(data).hexdigest()[:16],
        "updated": datetime.fromtimestamp(modified)
        .astimezone()
        .isoformat(timespec="seconds"),
    }
    try:
        value = json.loads(data, parse_constant=_refuse_constant)
    except (UnicodeDecodeError, ValueError) as error:
        return {**reading, "error": f"source {source!r} is not JSON: {error}"}
    if error := _value_error(source, contract, value, reading["revision"], registry):
        return {**reading, "error": error}
    return {**reading, "value": value}


def read_data(page_dir: Path, registry: dict | None) -> dict:
    """Every recorded source, read and judged against `registry`.

    `version` digests the source revisions, so two readings of the same values
    compare equal whatever else changed between them. A page whose layer cannot be
    read has no contracts to judge its values by, and reads as holding none."""
    sources = (
        {
            source: read_source(page_dir, source, contract, registry)
            for source, contract in sorted(read_contracts(page_dir).items())
        }
        if registry is not None
        else {}
    )
    identity = json.dumps(
        {source: reading.get("revision") for source, reading in sources.items()}
    )
    return {
        "version": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "sources": sources,
    }


def data_errors(stored: dict) -> list[str]:
    """Why each source whose current value fails its contract cannot be read."""
    return [
        reading["error"] for reading in stored["sources"].values() if "error" in reading
    ]


def deferred_records(value, contract: str, registry: dict) -> dict | None:
    """The contract's `records` declaration when this validated value's records
    carry a field Leaf delivers on demand (`records.deferred`).

    A contract may admit both an inline value and a record array. The deferred
    field applies only to an object carrying the declared item array.
    """
    spec = (
        registry.get("$data", {}).get("contracts", {}).get(contract, {}).get("records")
    )
    return (
        spec
        if spec is not None
        and "deferred" in spec
        and isinstance(value, dict)
        and isinstance(value.get(spec["items"]), list)
        else None
    )


def data_manifest(value, contract: str, registry: dict):
    """Keep a contract's records while leaving each deferred field at its source.

    Both browser delivery and agent inspection use this projection. It never
    mutates its input and returns the original value when nothing is deferred.
    """
    spec = deferred_records(value, contract, registry)
    if spec is None:
        return value
    return {
        **value,
        spec["items"]: [
            {key: item for key, item in record.items() if key != spec["deferred"]}
            for record in value[spec["items"]]
        ],
    }


def browser_data_from(stored: dict, registry: dict) -> dict:
    """The reading a browser receives: each value with its deferred fields omitted,
    which the deferred door serves from the same source file."""
    return {
        "version": stored["version"],
        "sources": {
            source: (
                {
                    **reading,
                    "value": data_manifest(
                        reading["value"], reading["contract"], registry
                    ),
                }
                if "value" in reading
                else reading
            )
            for source, reading in stored["sources"].items()
        },
    }


def deferred_value(
    reading: dict | None, registry: dict, *, source: str, revision: str, key: str
) -> dict:
    """One record's deferred field in the source value at `revision`, which must
    still be current.

    `reading` is the source as `read_source` read it, or None where the page records
    no such source."""
    if reading is None:
        raise DataError(f"unknown data source {source!r}")
    if reading.get("revision") != revision:
        raise StaleDataError(
            f"data source {source!r} no longer holds revision {revision!r}"
        )
    value = reading.get("value")
    spec = deferred_records(value, reading["contract"], registry)
    if spec is None:
        raise DataError(f"data source {source!r} defers no record field")
    matches = [
        item
        for item in value[spec["items"]]
        if isinstance(item, dict) and item.get(spec["key"]) == key
    ]
    if len(matches) != 1:
        reason = "unknown" if not matches else "duplicate"
        raise DataError(f"{reason} record key {key!r} in data source {source!r}")
    item = matches[0]
    if spec["deferred"] not in item:
        raise DataError(
            f"record {key!r} in data source {source!r} has no deferred value"
        )
    return {
        "source": source,
        "contract": reading["contract"],
        "revision": revision,
        "key": key,
        "value": item[spec["deferred"]],
    }


def _write_source(page_dir: Path, source: str, value) -> dict:
    """Validate and atomically replace one source's value, returning its reading."""
    try:
        # Validate the value the file will actually hold. Python's encoder accepts
        # values JSON itself cannot express directly — tuples become arrays and
        # non-string mapping keys become strings — so validating the
        # pre-serialization object can admit a value its own schema rejects on disk.
        value = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise DataError(f"source {source!r} value is not JSON: {error}") from error
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir) as page:
        registry = read_page_registry(page_dir).registry
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
            raise DataError(
                f"source {source!r} is not bound by the page source, a version, or "
                f"a thread widget; choose one of {sorted(bindings)}"
            )
        contracts = read_contracts(page_dir)
        recorded = contracts.get(source)
        if recorded is not None and recorded != contract:
            raise DataError(
                f"source {source!r} is now bound to contract {contract!r}, but it "
                f"was recorded with {recorded!r}; use a new source id for the new "
                "meaning"
            )
        if error := payload_error(source, contract, value, registry):
            raise DataError(error)
        writes = [(source_file(page_dir, source), json_bytes(value), False)]
        if recorded is None:
            contracts[source] = contract
            index = {
                "sources": {
                    name: {"contract": contracts[name]} for name in sorted(contracts)
                }
            }
            writes.append((page_dir / DATA_FILE, json_bytes(index), False))
        replace_files(writes)
        return read_source(page_dir, source, contract, registry)


def _report_write(verb: str, source: str, reading: dict) -> None:
    click.echo(
        f"{verb} data source {source!r} at revision {reading['revision']}, "
        f"updated {reading['updated']}"
    )


def cmd_data_set(page_dir: Path, source: str, value) -> None:
    """Validate and atomically replace one source's complete current value."""
    _report_write("set", source, _write_source(page_dir, source, value))


def cmd_data_clear(page_dir: Path, source: str) -> None:
    """Remove one source's value; its id keeps the contract it was recorded with."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir):
        try:
            source_file(page_dir, source).unlink()
        except FileNotFoundError:
            click.echo(f"data source {source!r} is already clear")
            return
    click.echo(f"cleared data source {source!r}")
