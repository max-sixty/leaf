"""Typed data bindings, registry contracts, inventories, and lag."""

import re
from pathlib import Path
from urllib.parse import urlsplit

import click
import jmespath
from jmespath.exceptions import JMESPathError
from referencing.exceptions import Unresolvable

from .files import list_revisions
from .registry.schema import (
    aware_instant,
    json_validator,
    json_value,
    schema_error_message,
)
from .revision_artifact import read_revision
from .schema import DATA_SOURCE_NAME, DIR_FILES, MEDIA_DIR
from .structure import SourceDocument
from .thread_context import logged_fragment


class DataError(click.ClickException):
    """A malformed data store or payload at the page data boundary."""


def resource_urls(value, declaration: dict) -> set[str]:
    """Declared media references in a validated value, selected by JMESPath.

    Expressions return a URL string, an array of URL strings, or null for an
    absent optional field. Ordinary strings elsewhere in the value remain data.
    Local references use the canonical page media namespace; remote references
    stay remote and are never fetched by snapshot or export.
    """
    urls = set()
    for expression in declaration.get("resources", []):
        try:
            selected = jmespath.search(expression, value)
        except JMESPathError as error:
            raise DataError(f"resource expression {expression!r}: {error}") from error
        if selected is None:
            continue
        selected = [selected] if isinstance(selected, str) else selected
        if not isinstance(selected, list) or any(
            not isinstance(url, str) for url in selected
        ):
            raise DataError(
                f"resource expression {expression!r} must select URL strings"
            )
        for url in selected:
            try:
                remote = urlsplit(url)
                is_remote = remote.scheme in {"http", "https"} and bool(remote.netloc)
            except ValueError:
                is_remote = False
            if not re.fullmatch(rf"/{MEDIA_DIR}/{DIR_FILES[MEDIA_DIR]}", url) and not (
                is_remote and not any(char.isspace() for char in url)
            ):
                raise DataError(
                    f"resource expression {expression!r}: {url!r} must be a "
                    "canonical /media/ URL or an HTTP(S) URL"
                )
            urls.add(url)
    return urls


def data_bindings(lf_elements: list, registry: dict):
    """Every seat one document binds: its ordinal, element, input, spec, and source.

    The widget schema owns missing and malformed attributes, so a binding exists
    only once that boundary has accepted a canonical source id; a seat without one
    yields nothing here rather than an error of its own. Every reader of the
    element-by-input relation walks it through this one generator.
    """
    for ordinal, rec in enumerate(lf_elements):
        for input_name, spec in registry.get(rec["tag"], {}).get("x-data", {}).items():
            source = rec["attrs"].get(spec["source"])
            if isinstance(source, str) and re.fullmatch(DATA_SOURCE_NAME, source):
                yield ordinal, rec, input_name, spec, source


def declared_data_bindings(
    lf_elements: list,
    registry: dict,
    document: str = "markup",
) -> tuple[dict, dict, list[str]]:
    """Read concrete source ids and their first seats from one document."""
    bindings = {}
    seats = {}
    errors = []
    for _ordinal, rec, input_name, spec, source in data_bindings(lf_elements, registry):
        contract = spec["contract"]
        seat = f"{document} <{rec['tag']}> input `{input_name}` (line {rec['line']})"
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


def merge_data_document_readings(
    documents: list[tuple[list, str, dict]],
) -> tuple[dict, list[str]]:
    """Read each document independently; later documents own current bindings.

    Conflicting contracts inside one document are ambiguous input. A later version,
    thread, or candidate may freely replace an earlier source binding. Captured
    registries remain attached to their historical documents, never reinterpreted
    through an incoming layer.
    """
    bindings = {}
    errors = []
    for lf_elements, document, registry in documents:
        found, _seats, found_errors = declared_data_bindings(
            lf_elements, registry, document
        )
        errors.extend(found_errors)
        bindings.update(found)
    return bindings, errors


def data_document_readings(
    document: SourceDocument, label: str, registry: dict
) -> list:
    """Read one identity space and its sample children against their captured layer.

    Samples inherit the parent's data store. Their consumers therefore belong in its
    producer inventory, while their widget ids remain scoped to the child document.
    A parent binding owns the producer when its sample reuses the source under a
    different contract: the child reads that copied value under its own contract.
    """
    readings = []
    for sample in document.samples:
        readings.extend(
            data_document_readings(
                sample["document"],
                f"{label} sample {sample['attrs'].get('id', '<unnamed>')!r}",
                registry,
            )
        )
    readings.append((document.lf_elements, label, registry))
    return readings


def page_data_document_readings(
    page_dir: Path, events: list, registry: dict
) -> list[tuple[list, str, dict]]:
    """Read each historical data consumer with its captured registry.

    Thread markup uses its admitted revision's registry; seeded markup on a page
    without revisions uses the initial registry. These readings permit historical
    producers and inventories without restricting later documents' bindings.
    """
    documents = []
    registries = {}
    for revision in list_revisions(page_dir):
        reading = read_revision(page_dir, revision)
        registries[revision] = reading.registry
        documents.append(
            data_document_readings(
                reading.document, f"revision r{revision}", reading.registry
            )
        )
    active_document = documents.pop() if documents else None
    for event in events:
        if event.get("markup"):
            revision = event.get("revision") or max(registries, default=None)
            documents.append(
                data_document_readings(
                    logged_fragment(event),
                    f"event {event['id']!r} markup",
                    registries[revision] if registries else registry,
                )
            )
    # The active document owns current bindings ahead of older thread markup.
    if active_document is not None:
        documents.append(active_document)
    return [reading for group in documents for reading in group]


def working_data_document_readings(
    page_dir: Path,
    registry: dict,
    events: list,
    *,
    authored: SourceDocument | None = None,
    incoming: list[tuple[SourceDocument, str]] | None = None,
) -> list[tuple[list, str, dict]]:
    """Immutable readings plus candidate documents under the candidate registry."""
    documents = page_data_document_readings(page_dir, events, registry)
    if authored is None:
        source = page_dir / "index.html"
        if source.exists():
            authored = SourceDocument(source.read_text(encoding="utf-8"))
    if authored is not None:
        documents.extend(data_document_readings(authored, "index.html", registry))
    for document, label in incoming or []:
        documents.extend(data_document_readings(document, label, registry))
    return documents


def initial_data_document_readings(
    authored: SourceDocument, events: list, registry: dict
) -> list:
    """A fresh page's source and seeded markup share its initial registry."""
    documents = data_document_readings(authored, "index.html", registry)
    for event in events:
        if event.get("markup"):
            documents.extend(
                data_document_readings(
                    logged_fragment(event), f"event {event['id']!r} markup", registry
                )
            )
    return documents


def working_data_bindings(
    page_dir: Path,
    registry: dict,
    events: list,
) -> tuple[dict, list[str]]:
    """Latest source bindings, with the current authored document taking precedence."""
    return merge_data_document_readings(
        working_data_document_readings(page_dir, registry, events),
    )


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
        raise DataError("conflicting data bindings: " + "; ".join(errors))
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


def data_binding_inventory(lf_elements: list, registry: dict) -> dict:
    """The page's source ids, contracts, and consuming widget inputs."""
    inventory = {}
    for _ordinal, rec, input_name, spec, source in data_bindings(lf_elements, registry):
        binding = inventory.setdefault(
            source,
            {"contract": spec["contract"], "consumers": []},
        )
        binding["consumers"].append(
            {"widget": rec["attrs"].get("id"), "input": input_name}
        )
    return {source: inventory[source] for source in sorted(inventory)}


def measurement_lag_entries(lf_elements: list, registry: dict, stored: dict) -> list:
    """Authored measurements whose bound source has completed a later run.

    The widget declaration joins the frozen half (its timestamp attribute) to the live
    half (one x-data input). Invalid attributes stay with widget validation, and an
    unset source says only that no later run is known, so neither becomes advice here.
    """
    entries = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        measured = entry.get("x-measured")
        if not measured:
            continue
        input_spec = entry.get("x-data", {}).get(measured["input"])
        if not input_spec:
            continue  # registry validation owns the malformed declaration
        source = rec["attrs"].get(input_spec["source"])
        captured = rec["attrs"].get(measured["at"])
        snapshot = stored["sources"].get(source) if isinstance(source, str) else None
        captured_at = aware_instant(captured) if isinstance(captured, str) else None
        updated_at = (
            aware_instant(snapshot["updated"])
            if isinstance(snapshot, dict) and isinstance(snapshot.get("updated"), str)
            else None
        )
        if captured_at is None or updated_at is None or updated_at <= captured_at:
            continue
        entries.append(
            {
                "tag": rec["tag"],
                "widget": rec["attrs"].get("id"),
                "line": rec["line"],
                "source": source,
                "at": captured,
                "updated": snapshot["updated"],
            }
        )
    return entries


def measurement_lag(lf_elements: list, registry: dict, stored: dict) -> list[str]:
    """`measurement_lag_entries` as source-check advice lines."""
    lines = []
    for entry in measurement_lag_entries(lf_elements, registry, stored):
        identity = f" id={entry['widget']!r}" if entry["widget"] else ""
        lines.append(
            f"<{entry['tag']}{identity}> (line {entry['line']}) pins source "
            f"{entry['source']!r} at {entry['at']}, but that source was updated at "
            f"{entry['updated']}"
        )
    return lines


def data_binding_errors(
    page_dir: Path,
    registry: dict,
    events: list,
    *,
    authored: SourceDocument | None = None,
    incoming: list[tuple[SourceDocument, str]] | None = None,
) -> list[str]:
    """Conflicting simultaneous bindings inside the working documents."""
    documents = working_data_document_readings(
        page_dir,
        registry,
        events,
        authored=authored,
        incoming=incoming,
    )
    return data_document_errors(documents)


def data_document_errors(documents: list[tuple[list, str, dict]]) -> list[str]:
    """Ambiguous simultaneous bindings within each authored document."""
    _bindings, errors = merge_data_document_readings(documents)
    return list(dict.fromkeys(errors))


def payload_error(source: str, contract: str, value, registry: dict) -> str | None:
    declaration = registry.get("$data", {}).get("contracts", {}).get(contract)
    if declaration is None:
        declared = sorted(registry.get("$data", {}).get("contracts", {}))
        return (
            f"source {source!r} uses undeclared contract {contract!r}; "
            f"available contracts are {json_value(declared)}"
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
        try:
            resource_urls(value, declaration)
        except DataError as error:
            return f"source {source!r} contract {contract!r}: {error.message}"
        records = declaration.get("records")
        items = (
            value.get(records["items"]) if records and isinstance(value, dict) else None
        )
        if items is not None:
            if not isinstance(items, list):
                return (
                    f"source {source!r} contract {contract!r} record field "
                    f"{records['items']!r} must be an array"
                )
            keys = set()
            duplicates = set()
            for index, item in enumerate(items):
                key = item.get(records["key"]) if isinstance(item, dict) else None
                if not isinstance(key, str) or not key:
                    return (
                        f"source {source!r} contract {contract!r} record "
                        f"{index} needs a non-empty string {records['key']!r}"
                    )
                if "deferred" in records and records["deferred"] not in item:
                    return (
                        f"source {source!r} contract {contract!r} record "
                        f"{index} needs {records['deferred']!r}"
                    )
                if key in keys:
                    duplicates.add(key)
                keys.add(key)
            if duplicates:
                return (
                    f"source {source!r} contract {contract!r} record keys must be "
                    f"unique; repeated {json_value(sorted(duplicates))}"
                )
        return None
    return (
        f"source {source!r} value is invalid for contract {contract!r} at "
        f"{error.json_path}: {schema_error_message(error)}"
    )
