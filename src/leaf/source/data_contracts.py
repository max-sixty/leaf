"""One document's typed data bindings and inventory, the registry contracts that
judge a value, and measurement lag. `page_data` reads the bindings across a page's
history.

A document's reading (`data_document_readings`) retains only binding records and
data declarations, so a reading of the page's history survives eviction of its
source parses without retaining parser nodes, unrelated widget metadata, or a
complete vocabulary.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from leaf.base.findings import Finding, element_at
from leaf.base.json_block import json_value
from leaf.base.refusals import Refused
from leaf.base.schema import DATA_SOURCE_NAME, DIR_FILES, MEDIA_DIR
from leaf.source.registry.schema import json_validator
from leaf.source.structure import SourceDocument


class DataError(Refused):
    """A malformed data store or payload at the page data boundary."""


def resource_urls(value, declaration: dict) -> set[str]:
    """Declared media references in a validated value, selected by JMESPath.

    Expressions return a URL string, an array of URL strings, or null for an
    absent optional field. Ordinary strings elsewhere in the value remain data.
    Local references use the canonical page media namespace; remote references
    stay remote and are never fetched by snapshot or export.
    """
    import jmespath
    from jmespath.exceptions import JMESPathError

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
        for input_name, spec in registry.get(rec["tag"], {}).get("inputs", {}).items():
            source = rec["attrs"].get(spec.get("source"))
            if isinstance(source, str) and re.fullmatch(DATA_SOURCE_NAME, source):
                yield ordinal, rec, input_name, spec, source


def declared_data_bindings(
    lf_elements: list,
    registry: dict,
    document: str | None = None,
) -> tuple[dict, list[Finding]]:
    """Read concrete source ids and their first seats from one document, and each
    later seat binding a source under another contract than its first.

    Two contracts for one source conflict only within one document, and which
    contract a seat has depends on the registry it is read under. Every gate reads
    its own document's bindings under the registry the document is stored with
    (`markup_checks.instances.instance_errors`), and a sample's child is a document
    of its own, with its own gate. A page's history is read under those same
    registries (`page_data.page_data_document_readings`), so it holds no conflict.
    A sample's child reads the messages it copies under its own registry, so it
    checks them under that one as it copies them (`documents.initial_sample_events`). `document` names the document in each seat
    for a reader holding several, as a page's history is; a gate's finding names
    none, since the gate says which document it read."""
    bindings = {}
    seats = {}
    errors = []
    for _ordinal, rec, input_name, spec, source in data_bindings(lf_elements, registry):
        contract = spec["contract"]
        seat = {
            "contract": contract,
            **({"document": document} if document is not None else {}),
            "tag": rec["tag"],
            **({"widget": rec["attrs"]["id"]} if "id" in rec["attrs"] else {}),
            "input": input_name,
            "line": rec["line"],
        }
        if source in bindings and bindings[source] != contract:
            found = Finding(
                "contract-conflict",
                values={"source": source, "first": seats[source], "then": seat},
            )
            # Widgets of one tag without ids on one line make one seat.
            if found not in errors:
                errors.append(found)
            continue
        bindings[source] = contract
        seats[source] = seat
    return bindings, errors


def merge_data_document_readings(
    documents: list[tuple[list, str, dict]],
) -> tuple[dict, list[Finding]]:
    """Read each document independently; later documents own current bindings.

    Conflicting contracts inside one document are ambiguous input. A later version,
    thread, or candidate may freely replace an earlier source binding. Captured
    registries remain attached to their historical documents, never reinterpreted
    through an incoming layer.
    """
    bindings = {}
    errors = []
    for lf_elements, document, registry in documents:
        found, found_errors = declared_data_bindings(lf_elements, registry, document)
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
    declarations = {
        rec["tag"]: {
            "inputs": declaration,
        }
        for rec in document.lf_elements
        if (declaration := registry.get(rec["tag"], {}).get("inputs"))
    }
    records = [
        {
            "tag": rec["tag"],
            "line": rec["line"],
            "attrs": {
                key: rec["attrs"][key]
                for key in {
                    "id",
                    *(
                        spec["source"]
                        for spec in declarations[rec["tag"]]["inputs"].values()
                        if "source" in spec
                    ),
                }
                if key in rec["attrs"]
            },
        }
        for rec in document.lf_elements
        if rec["tag"] in declarations
    ]
    readings.append((records, label, declarations))
    return readings


def authored_readings(page_dir: Path, registry: dict) -> list[tuple[list, str, dict]]:
    """The current source under the candidate registry."""
    source = page_dir / "index.html"
    if not source.exists():
        return []
    authored = SourceDocument(source.read_text(encoding="utf-8"))
    return data_document_readings(authored, "index.html", registry)


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

    An input (`inputs`) that declares `measured` joins the live half (its source)
    to the frozen half (the run receipt attribute it names). Invalid attributes stay
    with widget validation, and an unset source says only that no later run is known, so
    neither becomes advice here.
    """
    entries = []
    for rec in lf_elements:
        for spec in registry.get(rec["tag"], {}).get("inputs", {}).values():
            if "measured" not in spec:
                continue
            source = rec["attrs"].get(spec.get("source"))
            captured = rec["attrs"].get(spec["measured"])
            snapshot = (
                stored["sources"].get(source) if isinstance(source, str) else None
            )
            current = snapshot.get("run") if isinstance(snapshot, dict) else None
            if not captured or not current or current == captured:
                continue
            entries.append(
                {
                    "tag": rec["tag"],
                    "widget": rec["attrs"].get("id"),
                    "line": rec["line"],
                    "source": source,
                    "run": captured,
                    "current_run": current,
                }
            )
    return entries


def measurement_lag(lf_elements: list, registry: dict, stored: dict) -> list[Finding]:
    """`measurement_lag_entries` as source-check advice."""
    return [
        Finding(
            "measurement-lag",
            element_at(entry["tag"], entry["widget"] or ""),
            {
                "line": entry["line"],
                "source": entry["source"],
                "run": entry["run"],
                "current_run": entry["current_run"],
            },
        )
        for entry in measurement_lag_entries(lf_elements, registry, stored)
    ]


def payload_error(producer: str, contract: str, value, registry: dict) -> str | None:
    """Validate one produced value; `producer` is its reader-facing identity.

    External sources and exercised widget outputs share the same schema, resource
    and record invariants. Output withdrawal is not a value and bypasses this check.
    """
    declaration = registry.get("$data", {}).get("contracts", {}).get(contract)
    if declaration is None:
        declared = sorted(registry.get("$data", {}).get("contracts", {}))
        return (
            f"{producer} uses undeclared contract {contract!r}; "
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
            f"{producer} contract {contract!r} could not validate its value: "
            "a recursive reference did not terminate"
        )
    if error is None:
        try:
            resource_urls(value, declaration)
        except DataError as error:
            return f"{producer} contract {contract!r}: {error}"
        records = declaration.get("records")
        items = (
            value.get(records["items"]) if records and isinstance(value, dict) else None
        )
        if items is not None:
            if not isinstance(items, list):
                return (
                    f"{producer} contract {contract!r} record field "
                    f"{records['items']!r} must be an array"
                )
            keys = set()
            duplicates = set()
            for index, item in enumerate(items):
                key = item.get(records["key"]) if isinstance(item, dict) else None
                if not isinstance(key, str) or not key:
                    return (
                        f"{producer} contract {contract!r} record "
                        f"{index} needs a non-empty string {records['key']!r}"
                    )
                if key in keys:
                    duplicates.add(key)
                keys.add(key)
            if duplicates:
                return (
                    f"{producer} contract {contract!r} record keys must be "
                    f"unique; repeated {json_value(sorted(duplicates))}"
                )
        return None
    return (
        f"{producer} value is invalid for contract {contract!r} at "
        f"{error.json_path}: {error.message}"
    )


def output_findings(
    readings: list[dict],
    registry: dict,
    implementations: dict | None = None,
    declaration_sources: dict[str, str] | None = None,
) -> list[Finding]:
    """Judge exercised outputs, naming both the code and declaration owners.

    A page can override either the module or its declaration independently. Captured
    provenance reports both, without choosing which side should change. Direct render
    probes may lack that artifact; they still report the producer and contract.
    """
    found = []
    for reading in readings:
        if error := payload_error(
            f"output {reading['output']!r}",
            reading["contract"],
            reading["value"],
            registry,
        ):
            implementation = (implementations or {}).get(reading["tag"], {})
            finding = Finding(
                "invalid-output",
                at=element_at(reading["tag"], reading["id"]),
                values={
                    "tag": reading["tag"],
                    "output": reading["output"],
                    "contract": reading["contract"],
                    "owner": {"layer": "package", "page": "page"}.get(
                        implementation.get("owner"), "widget"
                    ),
                    "declaration_owner": {"layer": "package", "page": "page"}.get(
                        (declaration_sources or {}).get(reading["tag"])
                    ),
                    "contract_owner": {"layer": "package", "page": "page"}.get(
                        (declaration_sources or {}).get(
                            f"$data.contracts.{reading['contract']}"
                        )
                    ),
                    "module": implementation.get("path"),
                    **(
                        {"document": reading["document"]}
                        if "document" in reading
                        else {}
                    ),
                    "error": error,
                },
            )
            if finding not in found:
                found.append(finding)
    return found
