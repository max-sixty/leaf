"""Instructions for a page's selected vocabulary, before markup is authored.

Shared package instructions are always present. Component instructions follow an
explicit selection and its registry-declared dependencies, never the current HTML:
that reading must be available before the author writes or copies any markup.
Widget instructions have one reader, the author; data contracts and packages keep
separate audiences for the different responsibilities they actually declare.
"""

import json
import shlex
import sys
from collections.abc import Collection
from pathlib import Path

from .registry.storage import read_page_registry
from .schema import INSTRUCTIONS_DIR
from .structure import SourceDocument


def instruction_selection(
    registry: dict, widgets: Collection[str], contracts: Collection[str]
) -> tuple[list[str], list[str]]:
    """Close an explicit selection over required members, examples, and data inputs.

    Optional member alternatives are not dependencies. An optional component used
    in the selected entry's example is, because copying that example uses it.
    Sets bound cyclic examples and shared dependencies to one reading each.
    """
    declarations = {
        tag: entry for tag, entry in registry.items() if tag.startswith("lf-")
    }
    data_contracts = registry.get("$data", {}).get("contracts", {})
    selected_widgets = set()
    selected_contracts = set(contracts)
    pending = list(widgets)
    while pending:
        tag = pending.pop()
        if tag not in declarations:
            sys.exit(f"unknown instructions widget {tag!r}")
        if tag in selected_widgets:
            continue
        selected_widgets.add(tag)
        entry = declarations[tag]
        pending.extend(entry.get("x-required-members", {}))
        if example := entry.get("x-example"):
            pending.extend(
                node["tag"]
                for node in SourceDocument(example).nodes
                if node["tag"].startswith("lf-")
            )
        selected_contracts.update(
            spec["contract"] for spec in entry.get("x-data", {}).values()
        )
    for contract in sorted(selected_contracts):
        if contract not in data_contracts:
            sys.exit(f"unknown instructions data contract {contract!r}")
    return sorted(selected_widgets), sorted(selected_contracts)


def page_instructions(
    page_dir: Path,
    *,
    widgets: Collection[str] = (),
    contracts: Collection[str] = (),
) -> dict[str, str]:
    """Compose shared and selected instructions by their declared audience.

    The author's reading points to other audiences in this same selection, so an
    assigned producer does not accidentally read a different set of contracts.
    """
    vocabulary = read_page_registry(page_dir)
    if vocabulary is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    registry = vocabulary.registry
    selected_widgets, selected_contracts = instruction_selection(
        registry, widgets, contracts
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
    for tag in selected_widgets:
        if text := registry[tag].get("x-instructions"):
            parts.setdefault("author", []).append(
                f"# Widget `<{tag}>`\n\n{text.strip()}"
            )
    if "author" in parts and (others := sorted(parts.keys() - {"author"})):
        names = [f"`{audience}`" for audience in others]
        named = " and ".join(
            [", ".join(names[:-1]), names[-1]] if len(names) > 1 else names
        )
        selection = [
            argument
            for option, values in (("--widget", widgets), ("--contract", contracts))
            for value in sorted(set(values))
            for argument in (option, value)
        ]
        suffix = f" {shlex.join(selection)}" if selection else ""
        parts["author"].append(
            f"# Other audiences\n\nThis selection also carries instructions for {named}. "
            "Whoever takes one of those roles, you or an agent you assign, reads "
            f"`leaf page instructions <page> <audience>{suffix}` before acting in it."
        )
    return {
        audience: "\n\n".join(sections).rstrip() + "\n"
        for audience, sections in sorted(parts.items())
    }


def cmd_instructions(
    page_dir: Path,
    audience: str | None,
    *,
    widgets: Collection[str] = (),
    contracts: Collection[str] = (),
) -> None:
    instructions = page_instructions(page_dir, widgets=widgets, contracts=contracts)
    if audience is None:
        # A selection with no audiences is a real answer, `[]`, not silence.
        print(json.dumps(list(instructions)))
        return
    if text := instructions.get(audience):
        print(text, end="" if text.endswith("\n") else "\n")
        return
    available = ", ".join(instructions) or "none"
    sys.exit(
        f"instructions audience {audience!r} is not available; available: {available}"
    )
