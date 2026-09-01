"""Typed data bindings, registry contracts, inventories, and lag."""

import re
from pathlib import Path

import click
from referencing.exceptions import Unresolvable

from .files import list_revisions, revision_path
from .registry.contract import aware_instant, json_validator
from .schema import DATA_SOURCE_NAME
from .structure import parse_structure


class DataError(click.ClickException):
    """A malformed snapshot store or payload at the page data boundary."""


def valid_snapshot_id(value) -> bool:
    """Whether a selector names a positive decimal data revision."""
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None


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


def declared_data_snapshot_references(lf_elements: list, registry: dict) -> dict:
    """Read source-scoped immutable snapshot ids selected by one document."""
    references = {}
    for rec in lf_elements:
        for spec in registry.get(rec["tag"], {}).get("x-data", {}).values():
            snapshot_attr = spec.get("snapshot")
            if snapshot_attr is None:
                continue
            source = rec["attrs"].get(spec["source"])
            snapshot = rec["attrs"].get(snapshot_attr)
            if (
                isinstance(source, str)
                and re.fullmatch(DATA_SOURCE_NAME, source)
                and valid_snapshot_id(snapshot)
            ):
                references.setdefault(source, set()).add(snapshot)
    return references


def data_snapshot_selections(documents: list[tuple[list, str]], registry: dict) -> dict:
    """Exact immutable selection at each document/widget/input coordinate."""
    selections = {}
    for lf_elements, document in documents:
        for ordinal, rec in enumerate(lf_elements):
            for input_name, spec in (
                registry.get(rec["tag"], {}).get("x-data", {}).items()
            ):
                snapshot_attr = spec.get("snapshot")
                if snapshot_attr is None:
                    continue
                source = rec["attrs"].get(spec["source"])
                snapshot = rec["attrs"].get(snapshot_attr)
                if not (
                    isinstance(source, str)
                    and re.fullmatch(DATA_SOURCE_NAME, source)
                    and valid_snapshot_id(snapshot)
                ):
                    continue
                coordinate = (
                    document,
                    ordinal,
                    rec["tag"],
                    rec["attrs"].get("id"),
                    rec["line"],
                    input_name,
                )
                selections[coordinate] = (source, snapshot)
    return selections


def merge_data_bindings(
    documents: list[tuple[list, str]], registry: dict
) -> tuple[dict, list[str]]:
    """Fold document bindings into one page-lifetime identity map."""
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
    events: list,
) -> list[tuple[list, str]]:
    """The immutable page and thread documents that can consume external data."""
    documents = []
    for revision in list_revisions(page_dir):
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        documents.append((parse_structure(html).lf_elements, f"revision r{revision}"))
    for event in events:
        if markup := event.get("markup"):
            documents.append(
                (
                    parse_structure(markup).lf_elements,
                    f"event {event['id']!r} markup",
                )
            )
    return documents


def working_data_documents(
    page_dir: Path,
    events: list,
    *,
    authored: list | None = None,
    incoming: list[tuple[list, str]] | None = None,
) -> list[tuple[list, str]]:
    """Immutable documents plus the current source and boundary candidates."""
    documents = page_data_documents(page_dir, events)
    if authored is None:
        source = page_dir / "index.html"
        if source.exists():
            authored = parse_structure(source.read_text(encoding="utf-8")).lf_elements
    if authored is not None:
        documents.append((authored, "index.html"))
    documents.extend(incoming or [])
    return documents


def working_data_bindings(
    page_dir: Path,
    registry: dict,
    events: list,
) -> tuple[dict, list[str]]:
    """Source contracts across immutable documents and the current source."""
    return merge_data_bindings(
        working_data_documents(page_dir, events),
        registry,
    )


def working_data_snapshot_references(
    page_dir: Path,
    registry: dict,
    events: list,
) -> dict:
    """Snapshot ids selected by immutable documents and the current source."""
    references = {}
    for lf_elements, _document in working_data_documents(page_dir, events):
        for source, snapshots in declared_data_snapshot_references(
            lf_elements, registry
        ).items():
            references.setdefault(source, set()).update(snapshots)
    return references


def page_data_binding_inventory(
    page_dir: Path,
    registry: dict,
    events: list,
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
            consumer = {"widget": rec["attrs"].get("id"), "input": input_name}
            if (snapshot_attr := spec.get("snapshot")) and (
                selected := rec["attrs"].get(snapshot_attr)
            ):
                consumer["snapshot"] = selected
            binding["consumers"].append(consumer)
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
    stored: dict,
    events: list,
    *,
    authored: list | None = None,
    incoming: list[tuple[list, str]] | None = None,
) -> list[str]:
    """Working-document conflicts and standing snapshots that contradict them."""
    documents = working_data_documents(
        page_dir,
        events,
        authored=authored,
        incoming=incoming,
    )
    bindings, errors = merge_data_bindings(documents, registry)
    for source, contract in bindings.items():
        snapshot = stored["sources"].get(source)
        if snapshot is not None and snapshot["contract"] != contract:
            errors.append(
                f"source {source!r} is bound to contract {contract!r}, but its "
                f"standing snapshot uses {snapshot['contract']!r}; use a new source "
                "id for the new meaning"
            )
    for lf_elements, document in documents:
        for rec in lf_elements:
            for input_name, spec in (
                registry.get(rec["tag"], {}).get("x-data", {}).items()
            ):
                snapshot_attr = spec.get("snapshot")
                if snapshot_attr is None:
                    continue
                source = rec["attrs"].get(spec["source"])
                selected = rec["attrs"].get(snapshot_attr)
                if not (
                    isinstance(source, str)
                    and re.fullmatch(DATA_SOURCE_NAME, source)
                    and valid_snapshot_id(selected)
                ):
                    continue
                source_store = stored["sources"].get(source)
                snapshots = (
                    source_store.get("snapshots", {})
                    if isinstance(source_store, dict)
                    else {}
                )
                if selected not in snapshots:
                    errors.append(
                        f"{document} <{rec['tag']}> input `{input_name}` (line "
                        f"{rec['line']}) selects snapshot {selected!r} from source "
                        f"{source!r}, but data.json does not contain it"
                    )
    return list(dict.fromkeys(errors))


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
        fragments = declaration.get("fragments")
        items = (
            value.get(fragments["items"])
            if fragments and isinstance(value, dict)
            else None
        )
        if items is not None:
            if not isinstance(items, list):
                return (
                    f"source {source!r} contract {contract!r} fragment field "
                    f"{fragments['items']!r} must be an array"
                )
            keys = set()
            duplicates = set()
            for index, item in enumerate(items):
                key = item.get(fragments["key"]) if isinstance(item, dict) else None
                if not isinstance(key, str) or not key:
                    return (
                        f"source {source!r} contract {contract!r} fragment item "
                        f"{index} needs a non-empty string {fragments['key']!r}"
                    )
                if fragments["value"] not in item:
                    return (
                        f"source {source!r} contract {contract!r} fragment item "
                        f"{index} needs {fragments['value']!r}"
                    )
                if key in keys:
                    duplicates.add(key)
                keys.add(key)
            if duplicates:
                return (
                    f"source {source!r} contract {contract!r} fragment keys must be "
                    f"unique; repeated {sorted(duplicates)}"
                )
        return None
    return (
        f"source {source!r} value is invalid for contract {contract!r} at "
        f"{error.json_path}: {error.message}"
    )


def data_contract_errors(stored: dict, registry: dict) -> list[str]:
    errors = []
    for source, source_store in stored["sources"].items():
        contract = source_store["contract"]
        if "value" in source_store and (
            error := payload_error(source, contract, source_store["value"], registry)
        ):
            errors.append(error)
        for snapshot_id, snapshot in source_store.get("snapshots", {}).items():
            if error := payload_error(source, contract, snapshot["value"], registry):
                errors.append(f"snapshot {snapshot_id}: {error}")
    return errors
