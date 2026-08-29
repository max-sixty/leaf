"""Typed data bindings, registry contracts, inventories, and lag."""

import re
from pathlib import Path

import click
from referencing.exceptions import Unresolvable

from .event_log import read_events
from .files import list_revisions, revision_path
from .registry.contract import aware_instant, json_validator
from .schema import DATA_SOURCE_NAME
from .structure import parse_structure


class DataError(click.ClickException):
    """A malformed snapshot store or payload at the page data boundary."""


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
