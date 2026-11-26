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
its text and the revision a save names, read again whenever what the filesystem says
of the file moves (`file_sources`). The source's revision is
the first 16 digits of the file's, so a comment on what a widget drew from it records
the version of the file a save names, and a new label leaves it as it was. Its run
digests that observation, the path and the label, so it moves with every write and
every new label, and `updated` is when the file was last written. Readers judge its
value as they judge a publication's. Nothing else writes it: `leaf data set` and
`leaf data clear` refuse its id (`page_data`), and a publication under that id stands
behind it. A file the page can't read is a source holding the reason as its error. A
widget input of another contract can't draw it, which `page check` refuses
(`bound_file_conflicts`).
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from leaf.base.files import file_stamp, replace_files
from leaf.base.findings import Finding
from leaf.base.page_memory import memo
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
from leaf.source.data_contracts import data_bindings, payload_error
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
    return _judged(
        source,
        {
            "contract": publication["contract"],
            "revision": revision,
            "run": publication["run"],
            "updated": publication["updated"],
            "value": publication["value"],
        },
        registry,
    )


def _judged(source: str, reading: dict, registry: dict, key: str | None = None) -> dict:
    """`reading` as readers receive it: its value, or the error that keeps the value
    from fitting its contract's declaration in `registry`. `key` names the value
    (`value_key`), its revision unless given."""
    if "value" not in reading:
        return reading
    contract, value = reading["contract"], reading["value"]
    if error := _value_error(
        source, contract, value, key or reading["revision"], registry
    ):
        return {
            **{name: item for name, item in reading.items() if name != "value"},
            "error": error,
        }
    return reading


class _Files:
    """Each bound file's source by binding, and the digest of its whole value, kept
    under the observation of the file that also names its run and moves the page's
    news (`page_inputs`): its path, its label and its stamp with its change time
    (`file_stamp`'s `changed`). A source holding an error is read again each time,
    since its cause may lie in the file's path, which no stamp of the file names."""

    def __init__(self) -> None:
        self.held: dict[str, tuple] = {}


def _file_reading(
    page_dir: Path, binding: str, path: Path, label: str
) -> tuple[dict, str]:
    """The source of the bound file at `path`, and what names its value (`value_key`)."""
    seen = (str(path), label, file_stamp(path, changed=True))
    held = memo(page_dir, _Files).held
    kept = held.get(binding)
    if kept is not None and kept[0] == seen:
        return kept[1], kept[2]
    reading = _file_source(binding, path, seen)
    if "error" in reading:
        held.pop(binding, None)
        return reading, reading["revision"]
    key = value_revision(reading["value"])
    held[binding] = (seen, reading, key)
    return reading, key


def file_sources(page_dir: Path) -> dict[str, tuple[dict, str]]:
    """Each file the page binds as a source, by binding (the module header), with
    what names its value (`value_key`)."""
    paths = bound_paths(page_dir)
    named = labels(paths)
    held = memo(page_dir, _Files).held
    for binding in held.keys() - paths.keys():
        held.pop(binding, None)
    return {
        binding: _file_reading(page_dir, binding, path, named[binding])
        for binding, path in paths.items()
    }


def value_key(page_dir: Path, source: str, reading: dict) -> str:
    """What names `reading`'s value where two readings of `source` are compared, as the
    served state's tail compares them: its revision, which digests a publication's
    value, or for the bound file this process last read, a digest of its whole value,
    since the file's revision leaves out the label its value names."""
    kept = memo(page_dir, _Files).held.get(source)
    if kept is not None and all(
        kept[1][name] == reading[name] for name in ("revision", "run")
    ):
        return kept[2]
    return reading["revision"]


def _file_source(binding: str, path: Path, seen: tuple) -> dict:
    """The source of the file at `path` as `seen` found it, its path, label and
    what the filesystem says of it: a write, a rewrite of the same bytes included, or
    a new label moves the run, as a rerun of a publication does."""
    label = seen[1]
    run = hashlib.sha256(repr(seen).encode()).hexdigest()[:16]
    try:
        read, written = read_bound(path, label)
    except FileBindingError as error:
        return {
            "contract": FILE_CONTRACT,
            "revision": value_revision(str(error)),
            "run": run,
            "updated": now_iso(),
            "error": str(error),
        }
    return {
        "contract": FILE_CONTRACT,
        "revision": read["revision"][:16],
        "run": run,
        "updated": datetime.fromtimestamp(written)
        .astimezone()
        .isoformat(timespec="milliseconds"),
        "value": {
            "key": binding,
            "name": label,
            "text": read["text"],
            "revision": read["revision"],
        },
    }


def source_reading(page_dir: Path, source: str, registry: dict) -> dict | None:
    """One source as `read_data` gives it, or None where the page holds none. It reads
    only that source, the file it names where it is a bound file's."""
    paths = bound_paths(page_dir)
    if source in paths:
        reading, key = _file_reading(
            page_dir, source, paths[source], labels(paths)[source]
        )
        return _judged(source, reading, registry, key)
    return read_source(page_dir, source, registry)


def bound_file_conflicts(
    page_dir: Path, lf_elements: list, registry: dict
) -> list[Finding]:
    """Each input in a document that binds a bound file's id under another contract
    than the file's, which its widget can't draw."""
    files = bound_paths(page_dir)
    return [
        Finding(
            "file-contract",
            values={
                "source": source,
                "seat": {
                    "contract": spec["contract"],
                    "tag": rec["tag"],
                    **({"widget": rec["attrs"]["id"]} if "id" in rec["attrs"] else {}),
                    "input": input_name,
                    "line": rec["line"],
                },
            },
        )
        for _ordinal, rec, input_name, spec, source in data_bindings(
            lf_elements, registry
        )
        if source in files and spec["contract"] != FILE_CONTRACT
    ]


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
            **{
                binding: _judged(binding, reading, registry, key)
                for binding, (reading, key) in file_sources(page_dir).items()
            },
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
