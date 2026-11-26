"""Page-bound external data: one durable publication per source.

`data/<source>.json` (`PUBLICATION`) holds a source's one publication: the
`contract` it was set under, its opaque `run` receipt, `updated` instant, and
complete `value`. The page holds a source exactly while that file exists.
`leaf data set` validates the value against the contract the source is bound to at
the write (`page_data.working_data_bindings`) and writes the four together
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

A file the page binds (`file_bindings`) is a source too, under its binding's id:
a `text-document` valued `{key, name, text, revision}`, the binding, the file's label,
its text and the revision a save names, read again whenever its stamp moves
(`file_sources`). Its run is the file's revision and `updated` when the file was last
written. Nothing else writes it: `leaf data set` refuses its id (`page_data`), and a
publication under that id stands behind it. A file the page can't read is a source
holding the reason as its error.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from leaf.base.files import file_stamp, replace_files
from leaf.base.page_memory import Slot, memo
from leaf.base.schema import DATA_DIR
from leaf.base.state import (
    STRING,
    TIME,
    Record,
    described,
    json_bytes,
    now_iso,
    object_schema,
)
from leaf.source.data_contracts import payload_error
from leaf.source.file_bindings import FileBindingError, bound_paths, labels, read_bound

# The contract a bound file is a source under. The `default` package declares it, and
# every layer composes that package.
FILE_CONTRACT = "text-document"

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


def source_file(page_dir: Path, source: str) -> Path:
    return page_dir / DATA_DIR / f"{source}.json"


def _source_names(page_dir: Path) -> list[str]:
    """Each source the page holds a publication file of this shape for."""
    return sorted(path.stem for path in PUBLICATION.glob(page_dir / DATA_DIR))


def read_contracts(page_dir: Path) -> dict[str, str]:
    """Source id → the contract its publication was set under, or a bound file's."""
    readings = {
        source: _publication(page_dir, source) for source in _source_names(page_dir)
    }
    return {
        **{
            source: kept[0]["contract"]
            for source, kept in readings.items()
            if kept is not None
        },
        **dict.fromkeys(bound_paths(page_dir), FILE_CONTRACT),
    }


def write_data(page_dir: Path, publications: dict[str, dict]) -> None:
    """Atomically replace these sources' publications: their one writer."""
    (page_dir / DATA_DIR).mkdir(exist_ok=True)
    replace_files(
        [
            (
                PUBLICATION.file(source_file(page_dir, source)),
                PUBLICATION.encode(publication),
                False,
            )
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
        registry.get("$data", {}).get("contracts", {}).get(contract), sort_keys=True
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
    stamp = file_stamp(PUBLICATION.file(path))
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
        else (publication, value_revision(publication["value"]))
    )
    held[source] = (stamp, reading)
    return reading


def value_revision(value) -> str:
    """The revision a source holding `value` reads as: a digest of its encoding."""
    return hashlib.sha256(json_bytes(value)).hexdigest()[:16]


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


class _Files(Slot):
    """Every bound file's source, kept while no binding, label or file stamp moves."""


def file_sources(page_dir: Path) -> dict[str, dict]:
    """Each file the page binds as a source, by binding (the module header)."""
    paths = bound_paths(page_dir)
    named = labels(paths)
    key = tuple(
        (binding, path, file_stamp(path), named[binding])
        for binding, path in paths.items()
    )
    return memo(page_dir, _Files).get(
        key,
        lambda: {
            binding: _file_source(binding, path, named[binding])
            for binding, path in paths.items()
        },
    )


def _file_source(binding: str, path: Path, label: str) -> dict:
    try:
        read, written = read_bound(path, label)
    except FileBindingError as error:
        revision = value_revision(str(error))
        return {
            "contract": FILE_CONTRACT,
            "revision": revision,
            "run": revision,
            "updated": now_iso(),
            "error": str(error),
        }
    value = {
        "key": binding,
        "name": label,
        "text": read["text"],
        "revision": read["revision"],
    }
    return {
        "contract": FILE_CONTRACT,
        "revision": value_revision(value),
        "run": read["revision"],
        "updated": datetime.fromtimestamp(written)
        .astimezone()
        .isoformat(timespec="milliseconds"),
        "value": value,
    }


def read_data(page_dir: Path, registry: dict | None) -> dict:
    """Every source the page holds, the files it binds among them, read and judged
    against `registry`, with their `data_version`. A page whose layer cannot be read
    has no contracts to judge its values by, and reads as holding none."""
    names = _source_names(page_dir)
    # A source the page no longer holds keeps nothing.
    held = memo(page_dir, _Publications).held
    for source in held.keys() - set(names):
        held.pop(source, None)
    readings = (
        {
            **{source: read_source(page_dir, source, registry) for source in names},
            **file_sources(page_dir),
        }
        if registry is not None
        else {}
    )
    sources = {
        source: reading for source, reading in readings.items() if reading is not None
    }
    return {"version": data_version(sources), "sources": sources}


def data_version(sources: dict) -> str:
    """The version of data holding these source readings (`read_source`): a digest of
    each source's contract, publication and validity, so a changed contract or
    validation result is news even when the value matches, and a rerun is news even
    when it writes the same value."""
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
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


def data_errors(stored: dict) -> list[str]:
    """Why a published source's value fails its current contract."""
    return [
        reading["error"] for reading in stored["sources"].values() if "error" in reading
    ]
