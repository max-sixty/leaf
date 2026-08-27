"""Page-bound, contract-validated replace-in-place data snapshots."""

import json
import re
from pathlib import Path

import click
from referencing.exceptions import Unresolvable

from .events import now_iso, read_events
from .files import list_revisions, revision_path, write_json
from .registry import is_aware_datetime, json_validator, require_registry
from .schema import DATA_CONTRACT_NAME, DATA_FILE, DATA_SOURCE_NAME
from .service import PageTransaction
from .structure import parse_structure


class DataError(click.ClickException):
    """A malformed snapshot store or payload at the page data boundary."""


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


def declared_data_bindings(
    lf_elements: list,
    registry: dict,
    document: str = "markup",
) -> tuple[dict, dict, list[str]]:
    """Read concrete source ids and their first seats from one document."""
    bindings = {}
    seats = {}
    errors = []
    for rec in lf_elements:
        for input_name, spec in registry.get(rec["tag"], {}).get("x-data", {}).items():
            source = rec["attrs"].get(spec["source"])
            if (
                not isinstance(source, str)
                or re.fullmatch(DATA_SOURCE_NAME, source) is None
            ):
                # The widget schema owns missing and malformed attributes. A binding
                # exists only after that boundary has accepted a canonical source id.
                continue
            contract = spec["contract"]
            seat = (
                f"{document} <{rec['tag']}> input `{input_name}` (line {rec['line']})"
            )
            if source in bindings and bindings[source] != contract:
                errors.append(
                    f"source {source!r} is bound to both contract "
                    f"{bindings[source]!r} at {seats[source]} and contract "
                    f"{contract!r} at {seat}; use a new source id for the new meaning"
                )
                continue
            bindings[source] = contract
            seats[source] = seat
    return bindings, seats, errors


def merge_data_bindings(
    documents: list[tuple[list, str]], registry: dict
) -> tuple[dict, list[str]]:
    """Fold bindings from immutable documents into one page-lifetime identity map."""
    bindings = {}
    seats = {}
    errors = []
    for lf_elements, document in documents:
        found, found_seats, found_errors = declared_data_bindings(
            lf_elements, registry, document
        )
        errors.extend(found_errors)
        for source, contract in found.items():
            if source in bindings and bindings[source] != contract:
                errors.append(
                    f"source {source!r} is bound to both contract "
                    f"{bindings[source]!r} at {seats[source]} and contract "
                    f"{contract!r} at {found_seats[source]}; use a new source id for "
                    "the new meaning"
                )
                continue
            bindings[source] = contract
            seats[source] = found_seats[source]
    return bindings, errors


def page_data_documents(
    page_dir: Path,
    events: list | None = None,
    extra: list[tuple[list, str]] | None = None,
) -> list[tuple[list, str]]:
    """The immutable page and thread documents that can consume external data."""
    documents = []
    for revision in list_revisions(page_dir):
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        documents.append((parse_structure(html).lf_elements, f"revision r{revision}"))
    for event in read_events(page_dir) if events is None else events:
        if markup := event.get("markup"):
            documents.append(
                (
                    parse_structure(markup).lf_elements,
                    f"event {event['id']!r} markup",
                )
            )
    documents.extend(extra or [])
    return documents


def page_data_bindings(
    page_dir: Path,
    registry: dict,
    events: list | None = None,
    extra: list[tuple[list, str]] | None = None,
) -> tuple[dict, list[str]]:
    """One source-to-contract map across versions and frozen thread documents."""
    return merge_data_bindings(
        page_data_documents(page_dir, events, extra),
        registry,
    )


def page_data_binding_inventory(
    page_dir: Path,
    registry: dict,
    events: list | None = None,
) -> dict:
    """Page-lifetime bindings in the form a producer needs from `page state`."""
    documents = page_data_documents(page_dir, events)
    bindings, errors = merge_data_bindings(documents, registry)
    if errors:
        raise DataError(
            "the page history has conflicting data bindings: " + "; ".join(errors)
        )
    inventory = {}
    for lf_elements, document in documents:
        for source, binding in data_binding_inventory(lf_elements, registry).items():
            standing = inventory.setdefault(
                source,
                {"contract": bindings[source], "consumers": []},
            )
            standing["consumers"].extend(
                {**consumer, "document": document} for consumer in binding["consumers"]
            )
    return {source: inventory[source] for source in sorted(inventory)}


def data_binding_inventory(lf_elements: list, registry: dict) -> dict:
    """The page's source ids, contracts, and consuming widget inputs."""
    inventory = {}
    for rec in lf_elements:
        for input_name, spec in registry.get(rec["tag"], {}).get("x-data", {}).items():
            source = rec["attrs"].get(spec["source"])
            if (
                not isinstance(source, str)
                or re.fullmatch(DATA_SOURCE_NAME, source) is None
            ):
                continue
            binding = inventory.setdefault(
                source,
                {"contract": spec["contract"], "consumers": []},
            )
            binding["consumers"].append(
                {"widget": rec["attrs"].get("id"), "input": input_name}
            )
    return {source: inventory[source] for source in sorted(inventory)}


def data_binding_errors(
    page_dir: Path,
    registry: dict,
    stored: dict,
    events: list | None = None,
    extra: list[tuple[list, str]] | None = None,
) -> list[str]:
    """Page-lifetime conflicts and standing snapshots that contradict them."""
    bindings, errors = page_data_bindings(page_dir, registry, events, extra)
    for source, contract in bindings.items():
        snapshot = stored["sources"].get(source)
        if snapshot is not None and snapshot["contract"] != contract:
            errors.append(
                f"source {source!r} is bound to contract {contract!r}, but its "
                f"standing snapshot uses {snapshot['contract']!r}; use a new source "
                "id for the new meaning"
            )
    return errors


def payload_error(source: str, contract: str, value, registry: dict) -> str | None:
    declaration = registry.get("$data", {}).get("contracts", {}).get(contract)
    if declaration is None:
        declared = sorted(registry.get("$data", {}).get("contracts", {}))
        return (
            f"source {source!r} uses undeclared contract {contract!r}; "
            f"available contracts are {declared}"
        )
    try:
        error = min(
            json_validator(declaration["schema"]).iter_errors(value),
            key=str,
            default=None,
        )
    except RecursionError:
        return (
            f"source {source!r} contract {contract!r} could not validate its value: "
            "a recursive reference did not terminate"
        )
    except Unresolvable as error:
        return (
            f"source {source!r} contract {contract!r} could not validate its value: "
            f"unresolved reference {error.ref!r}"
        )
    if error is None:
        return None
    return (
        f"source {source!r} value is invalid for contract {contract!r} at "
        f"{error.json_path}: {error.message}"
    )


def data_contract_errors(stored: dict, registry: dict) -> list[str]:
    return [
        error
        for source, snapshot in stored["sources"].items()
        if (
            error := payload_error(
                source, snapshot["contract"], snapshot["value"], registry
            )
        )
    ]


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
