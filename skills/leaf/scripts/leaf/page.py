"""Instructions for a page's selected vocabulary, before markup is authored.

Shared package instructions are always present. Component instructions follow an
explicit selection and its registry-declared dependencies, never the current HTML:
that reading must be available before the author writes or copies any markup.
Vocabulary entries have one reader, the author; data contracts and packages keep
separate audiences for the different responsibilities they actually declare.
"""

import json
import sys
from collections.abc import Collection
from pathlib import Path

from .registry.contract import is_element_name
from .registry.storage import read_page_registry
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
            sys.exit(f"unknown instructions vocabulary entry {name!r}")
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
            sys.exit(f"unknown instructions data contract {contract!r}")
    return sorted(selected_entries), sorted(selected_contracts)


def page_instructions(
    page_dir: Path,
    *,
    entries: Collection[str] = (),
    contracts: Collection[str] = (),
) -> dict[str, str]:
    """Compose shared and selected instructions by their declared audience."""
    vocabulary = read_page_registry(page_dir)
    if vocabulary is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    registry = vocabulary.registry
    selected_entries, selected_contracts = instruction_selection(
        registry, entries, contracts
    )
    parts: dict[str, list[str]] = {}
    directory = page_dir / INSTRUCTIONS_DIR
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.setdefault(path.stem, []).append(text)
    for contract in selected_contracts:
        declaration = registry["$data"]["contracts"][contract]
        for audience, text in sorted(declaration.get("instructions", {}).items()):
            parts.setdefault(audience, []).append(
                f"# Data contract `{contract}`\n\n{text.strip()}"
            )
    for name in selected_entries:
        if text := registry[name].get("x-instructions"):
            parts.setdefault("author", []).append(
                f"# Vocabulary `{name}`\n\n{text.strip()}"
            )
    return {
        audience: "\n\n".join(sections).rstrip() + "\n"
        for audience, sections in sorted(parts.items())
    }


def cmd_instructions(
    page_dir: Path,
    *,
    entries: Collection[str] = (),
    contracts: Collection[str] = (),
) -> None:
    print(
        json.dumps(
            page_instructions(page_dir, entries=entries, contracts=contracts),
            ensure_ascii=False,
        )
    )
