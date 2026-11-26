"""A page's data bindings across its history, and the commands that write its
sources: `leaf data set` (`cmd_data_set`) and `leaf data clear` (`cmd_data_clear`).

A source's binding is read from every document the page has held, in order: each
earlier revision's document, each message's markup as it now reads, the active
revision's document and the current source. A later document's binding replaces an
earlier one's (`working_data_bindings`).

Reading a message's markup as it now reads takes the log
(`thread_context.thread_structure`), and a write holds the page transaction while it
validates its value against those bindings and replaces the source's publication. So
this module sits in `records`, beside the transaction and above the log. One
document's bindings and the contracts that judge a value stay in `source`, in
`data_contracts`, as do the publication file and its readers, in `data`.
"""

import json
import re
from pathlib import Path
from uuid import uuid4

from leaf.base.files import latest_revision
from leaf.base.findings import Finding
from leaf.base.json_block import json_value
from leaf.base.schema import DATA_SOURCE_NAME
from leaf.base.state import now_iso
from leaf.log.thread_context import thread_structure
from leaf.records.transaction import PageTransaction
from leaf.source.data import (
    PUBLICATION,
    data_of,
    read_data,
    read_source,
    source_file,
    write_data,
)
from leaf.source.data_contracts import (
    DataError,
    authored_readings,
    data_binding_inventory,
    data_document_readings,
    merge_data_document_readings,
    payload_error,
)
from leaf.source.file_bindings import bound_paths
from leaf.source.revision_artifact import read_revision, revision_history
from leaf.source.vocabulary import read_page_registry


def page_data_document_readings(
    page_dir: Path, events: list, registry: dict
) -> list[tuple[list, str, dict]]:
    """Read each historical data consumer with its captured registry.

    A message's markup, as it now reads (`thread_structure`), uses the registry of
    the revision its wording was admitted with; a seeded message on a page without
    revisions uses the newest. These readings permit historical producers and
    inventories without restricting later documents' bindings.
    """
    documents = [
        [
            (records, f"revision r{revision}{label}", declarations)
            for records, label, declarations in readings
        ]
        for revision, readings in revision_history(page_dir).data_documents
    ]
    active_document = documents.pop() if documents else None
    newest = latest_revision(page_dir)
    structure = thread_structure(events)
    for message, fragment in structure.fragments.items():
        revision = structure.wordings[message][-1].get("revision") or newest
        selected_registry = (
            registry if revision is None else read_revision(page_dir, revision).registry
        )
        documents.append(
            data_document_readings(
                fragment, f"event {message!r} markup", selected_registry
            )
        )
    # The active document owns current bindings ahead of older messages' markup.
    if active_document is not None:
        documents.append(active_document)
    return [reading for group in documents for reading in group]


def working_data_bindings(
    page_dir: Path,
    registry: dict,
    events: list,
) -> tuple[dict, list[Finding]]:
    """Latest source bindings, with the current authored document taking precedence."""
    return merge_data_document_readings(
        [
            *page_data_document_readings(page_dir, events, registry),
            *authored_readings(page_dir, registry),
        ]
    )


def bound_data(page_dir: Path, registry: dict, events: list) -> dict:
    """The page's data (`data.read_data`) less each source no revision or message of
    the page binds, such as a file the page grants an editor alone or one only an
    unpublished source binds (`data.data_of`)."""
    bindings, _errors = merge_data_document_readings(
        page_data_document_readings(page_dir, events, registry)
    )
    return data_of(read_data(page_dir, registry), bindings)


def page_data_binding_inventory(
    page_dir: Path,
    registry: dict,
    events: list,
) -> dict:
    """Current producer bindings and their matching document consumers.

    A later binding replaces an earlier contract for the same source. Consumers of
    that former contract keep their captured registry and may receive a missing or
    invalid current value; they do not constrain the producer's next write.
    """
    documents = page_data_document_readings(page_dir, events, registry)
    bindings, errors = merge_data_document_readings(documents)
    if errors:
        raise DataError("conflicting data bindings: " + "; ".join(map(str, errors)))
    inventory = {
        source: {"contract": contract, "consumers": []}
        for source, contract in bindings.items()
    }
    for lf_elements, document, document_registry in documents:
        for source, binding in data_binding_inventory(
            lf_elements, document_registry
        ).items():
            if binding["contract"] != bindings[source]:
                continue
            inventory[source]["consumers"].extend(
                {**consumer, "document": document} for consumer in binding["consumers"]
            )
    return {source: inventory[source] for source in sorted(inventory)}


def _published(page_dir: Path, source: str) -> None:
    """Refuse a write or clear of `source` that no publication of the page could
    take: a malformed id, or a bound file's, whose file is its source
    (`data.file_sources`) and what a write changes."""
    if re.fullmatch(DATA_SOURCE_NAME, source) is None:
        raise DataError(f"invalid source name {source!r}")
    if source in bound_paths(page_dir):
        raise DataError(
            f"source {source!r} is a bound file; write the file itself, and the page "
            "shows each write"
        )


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
    with PageTransaction(page_dir) as page:
        _published(page_dir, source)
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
    with PageTransaction(page_dir):
        _published(page_dir, source)
        try:
            PUBLICATION.file(source_file(page_dir, source)).unlink()
            cleared = True
        except FileNotFoundError:
            cleared = False
    return {"source": source, "cleared": cleared}
