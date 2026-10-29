"""Instructions for a page's selected vocabulary, before markup is authored.

Shared package instructions are always present. Component instructions follow an
explicit selection and its registry-declared dependencies, never the current HTML:
that reading must be available before the author writes or copies any markup.
Vocabulary entries have one reader, the author; data contracts and packages keep
separate audiences for the different responsibilities they actually declare.
"""

from collections.abc import Collection
from pathlib import Path

from .refusals import Refused
from .registry.contract import is_element_name
from .registry.storage import layer_record, require_candidate, selected
from .schema import INSTRUCTIONS_DIR
from .structure import SourceDocument


def instruction_selection(
    registry: dict, entries: Collection[str], contracts: Collection[str]
) -> tuple[list[str], list[str]]:
    """Close an explicit vocabulary selection over examples and data inputs.

    Optional member alternatives are not dependencies. An optional component used
    in the selected entry's example is, because copying that example uses it.
    Sets bound cyclic examples and shared dependencies to one reading each.
    """
    declarations = {
        name: entry for name, entry in registry.items() if not name.startswith("$")
    }
    selectors = [name for name in declarations if not is_element_name(name)]
    data_contracts = registry.get("$data", {}).get("contracts", {})
    selected_entries = set()
    selected_contracts = set(contracts)
    pending = list(entries)
    while pending:
        name = pending.pop()
        if name not in declarations:
            # Authors land here asking for a Layout class, which the page's CSS
            # provides and page-layout.md describes, outside the registry.
            raise Refused(
                f"unknown instructions vocabulary entry {name!r}: the page's registry"
                " declares no element or idiom by that name (its keys list the"
                " vocabulary); Layout classes such as `layout-tiles` aren't entries,"
                " and page-layout.md describes them"
            )
        if name in selected_entries:
            continue
        selected_entries.add(name)
        entry = declarations[name]
        if example := entry.get("x-example"):
            nodes = [
                node
                for node in SourceDocument(example, fragment=True).tree.find_all(True)
                if node.source_location is not None
            ]
            pending.extend(node.tag for node in nodes if is_element_name(node.tag))
            pending.extend(
                selector
                for selector in selectors
                if any(node.matches(selector) for node in nodes)
            )
        selected_contracts.update(
            spec["contract"] for spec in entry.get("x-data", {}).values()
        )
    for contract in sorted(selected_contracts):
        if contract not in data_contracts:
            raise Refused(f"unknown instructions data contract {contract!r}")
    return sorted(selected_entries), sorted(selected_contracts)


def words(entry: dict) -> list[str]:
    """What each attribute of a vocabulary `entry` whose schema lists the words it
    takes (`enum`) may say, as its schema says it, such as the tones the layer
    paints (`registry.contract.stamp_words`): an author choosing one need not look
    it up."""
    return [
        f"`{attr}` takes one of: "
        + ", ".join(f"`{word}`" for word in spec["enum"])
        + "."
        for attr, spec in entry.get("properties", {}).items()
        if "enum" in spec
    ]


def page_instructions(
    page_dir: Path,
    *,
    entries: Collection[str] = (),
    contracts: Collection[str] = (),
) -> dict[str, str]:
    """Compose shared and selected instructions by their declared audience."""
    registry = require_candidate(page_dir).registry
    selected_entries, selected_contracts = instruction_selection(
        registry, entries, contracts
    )
    parts: dict[str, list[str]] = {}
    record = layer_record(page_dir)
    assert record is not None
    layer = selected(record, page_dir)
    for name, data in sorted(layer.directory_files[INSTRUCTIONS_DIR].items()):
        text = data.decode("utf-8").strip()
        if text:
            parts.setdefault(Path(name).stem, []).append(text)
    for contract in selected_contracts:
        declaration = registry["$data"]["contracts"][contract]
        for audience, text in sorted(declaration.get("instructions", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Data contract `{contract}`\n\n{text.strip()}"
            )
    for name in selected_entries:
        said = [
            text.strip()
            for text in (registry[name].get("x-instructions"), *words(registry[name]))
            if text
        ]
        if said:
            parts.setdefault("author", []).append(
                f"# Vocabulary `{name}`\n\n" + "\n\n".join(said)
            )
    return {
        audience: "\n\n".join(sections).rstrip() + "\n"
        for audience, sections in sorted(parts.items())
    }
