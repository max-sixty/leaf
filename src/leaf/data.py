"""Page-bound external data: one durable publication per source.

`data/<source>.json` (`PUBLICATION`) holds a source's one publication: the
`contract` it was set under, its opaque `run` receipt, `updated` instant, and
complete `value`. The page holds a source exactly while that file exists.
`leaf data set` validates the value against the contract the source is bound to at
the write (`data_contracts.working_data_bindings`) and writes the four together
through `write_data`, which a sample's copy of its parent's data also uses;
`leaf data clear` removes the file, so the source's next write takes its binding
then. A reader trusts the file's shape and judges only the value, against the
recorded contract's declaration in the registry it reads under, which a later
layer may have changed. Readers take the recorded contract rather than the
document's binding, so a state read never reads the page's history; a later
document that binds the source to another contract governs from its next write.

A source's revision identifies its encoded value; its run identifies the write,
including a rerun with the same value. Both survive copying the page directory.
Nothing retains an earlier value: a reader or anchor naming a revision the source
no longer holds is reading a replaced value. A document that must keep one value
binds a source id nothing rewrites.
"""

import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from .data_contracts import (
    DataError,
    payload_error,
    record_labels,
    working_data_bindings,
)
from .files import file_stamp, replace_files
from .page_memory import memo
from .registry.schema import json_value
from .registry.storage import read_page_registry
from .schema import DATA_DIR, DATA_SOURCE_NAME
from .service import PageTransaction
from .state import (
    STRING,
    TIME,
    Record,
    described,
    json_bytes,
    now_iso,
    object_schema,
)

PUBLICATION = Record(
    "data-source",
    described(
        "One source's publication, in the page directory's `data/<source>.json`, "
        "which `leaf data set` writes whole.",
        object_schema(
            {
                "contract": described(
                    "The data contract the value was validated against at the write.",
                    STRING,
                ),
                "run": described(
                    "An opaque receipt naming the write, a rerun with the same value "
                    "included.",
                    STRING,
                ),
                "updated": described("When the value was written.", TIME),
                "value": described("The source's complete value.", {}),
            }
        ),
    ),
    since=16,
)


class StaleDataError(DataError):
    """A deferred-value request named a source revision the source no longer holds."""


def source_file(page_dir: Path, source: str) -> Path:
    return page_dir / DATA_DIR / f"{source}.json"


def _source_names(page_dir: Path) -> list[str]:
    """Each source the page holds a publication file for."""
    try:
        names = [entry.name for entry in (page_dir / DATA_DIR).iterdir()]
    except FileNotFoundError:
        return []
    return sorted(
        name.removesuffix(".json") for name in names if name.endswith(".json")
    )


def read_contracts(page_dir: Path) -> dict[str, str]:
    """Source id → the contract its publication was set under."""
    readings = {
        source: _publication(page_dir, source) for source in _source_names(page_dir)
    }
    return {
        source: kept[0]["contract"]
        for source, kept in readings.items()
        if kept is not None
    }


def write_data(page_dir: Path, publications: dict[str, dict]) -> None:
    """Atomically replace these sources' publications: their one writer."""
    (page_dir / DATA_DIR).mkdir(exist_ok=True)
    replace_files(
        [
            (source_file(page_dir, source), PUBLICATION.encode(publication), False)
            for source, publication in publications.items()
        ]
    )


# (source, contract declaration, revision) → validation error. A large value costs far
# more to validate than to digest, so a server judges each distinct value once, through
# a rerun that rewrites it and under every registry that declares its contract alike.
_JUDGED: dict[tuple[str, str, str], str | None] = {}
_UNJUDGED = object()


def _value_error(source: str, contract: str, value, revision: str, registry: dict):
    declaration = json.dumps(
        [
            registry.get("$data", {}).get("contracts", {}).get(contract),
            sorted(record_labels(contract, registry)),
        ],
        sort_keys=True,
    )
    key = source, declaration, revision
    held = _JUDGED.get(key, _UNJUDGED)
    if held is not _UNJUDGED:
        return held
    if len(_JUDGED) >= 1024:
        _JUDGED.clear()
    error = payload_error(f"source {source!r}", contract, value, registry)
    _JUDGED[key] = error
    return error


class _Publications:
    """Each source's publication and the revision its value digests to, kept under its
    file's stamp. Every state reading reads every source, and parsing and digesting a
    large value costs far more than a stat. Readers share the kept value and never
    change it."""

    def __init__(self) -> None:
        self.held: dict[str, tuple] = {}


def _publication(page_dir: Path, source: str) -> tuple[dict, str] | None:
    """The source's publication and its value's revision, or None before one exists."""
    path = source_file(page_dir, source)
    stamp = file_stamp(path)
    held = memo(page_dir, _Publications).held
    if stamp is None:
        held.pop(source, None)
        return None
    kept = held.get(source)
    if kept is not None and kept[0] == stamp:
        return kept[1]
    publication = PUBLICATION.read(path)
    reading = (
        None
        if publication is None
        else (
            publication,
            hashlib.sha256(json_bytes(publication["value"])).hexdigest()[:16],
        )
    )
    held[source] = (stamp, reading)
    return reading


def read_source(page_dir: Path, source: str, registry: dict) -> dict | None:
    """One source as readers receive it: its contract, revision, run receipt,
    `updated` instant, and `value` or `error`; None where the page holds none."""
    kept = _publication(page_dir, source)
    if kept is None:
        return None
    publication, revision = kept
    contract, value = publication["contract"], publication["value"]
    reading = {
        "contract": contract,
        "revision": revision,
        "run": publication["run"],
        "updated": publication["updated"],
    }
    if error := _value_error(source, contract, value, revision, registry):
        return {**reading, "error": error}
    return {**reading, "value": value}


def read_data(page_dir: Path, registry: dict | None) -> dict:
    """Every source the page holds, read and judged against `registry`.

    `version` digests each source's contract, publication and validity, so a
    changed contract or validation result is news even when the value matches.
    A rerun is news even when it writes the same value. A page whose layer cannot be
    read has no contracts to judge its values by, and reads as holding none."""
    names = _source_names(page_dir)
    # A source the page no longer holds keeps nothing.
    held = memo(page_dir, _Publications).held
    for source in held.keys() - set(names):
        held.pop(source, None)
    readings = (
        {source: read_source(page_dir, source, registry) for source in names}
        if registry is not None
        else {}
    )
    sources = {
        source: reading for source, reading in readings.items() if reading is not None
    }
    identity = json.dumps(
        {
            source: [
                reading["contract"],
                reading.get("revision"),
                reading.get("run"),
                reading.get("error"),
                "value" in reading,
            ]
            for source, reading in sources.items()
        }
    )
    return {
        "version": hashlib.sha256(identity.encode()).hexdigest()[:16],
        "sources": sources,
    }


def data_errors(stored: dict) -> list[str]:
    """Why a published source's value fails its current contract."""
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


def browser_data_from(stored: dict, registry: dict | None) -> dict:
    """The reading a browser receives: each value with its deferred fields omitted,
    which the deferred door serves from the same source file."""
    return {
        "version": stored["version"],
        "sources": {
            source: (
                {
                    **reading,
                    "value": data_manifest(
                        reading["value"], reading["contract"], registry or {}
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

    `reading` is the source as `read_source` read it, or None where the page holds
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
    # `read_source` judged the value by its contract (`payload_error`): every record
    # is an object with a unique key. Its item schema decides which fields it carries.
    assert value is not None
    item = next(
        (item for item in value[spec["items"]] if item[spec["key"]] == key), None
    )
    if item is None:
        raise DataError(f"unknown record key {key!r} in data source {source!r}")
    if spec["deferred"] not in item:
        raise DataError(
            f"record {key!r} in data source {source!r} has no deferred field "
            f"{spec['deferred']!r}"
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
                "conflicting data bindings: " + "; ".join(map(str, binding_errors))
            )
        contract = bindings.get(source)
        if contract is None:
            raise DataError(
                f"source {source!r} is not bound by the page source, a version, or "
                f"a thread widget; choose one of {json_value(sorted(bindings))}"
            )
        if error := payload_error(f"source {source!r}", contract, value, registry):
            raise DataError(error)
        write_data(
            page_dir,
            {
                source: {
                    "contract": contract,
                    "run": uuid4().hex,
                    "updated": now_iso(),
                    "value": value,
                }
            },
        )
        reading = read_source(page_dir, source, registry)
        assert reading is not None
        return reading


def cmd_data_set(page_dir: Path, source: str, value) -> dict:
    """Validate and atomically replace one source's complete current value, and
    return the written source's reading, less the value the writer just handed in."""
    reading = _write_source(page_dir, source, value)
    return {"source": source} | {
        key: item for key, item in reading.items() if key != "value"
    }


def cmd_data_clear(page_dir: Path, source: str) -> dict:
    """Remove one source's publication, its value with the contract it was set
    under; its next write takes the binding it has then."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    with PageTransaction(page_dir):
        try:
            source_file(page_dir, source).unlink()
            cleared = True
        except FileNotFoundError:
            cleared = False
    return {"source": source, "cleared": cleared}
