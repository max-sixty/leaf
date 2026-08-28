"""Vendored registry storage and page lookup."""

import sys
from pathlib import Path

from leaf.files import file_stamp

from .contract import RegistryError, read_registry_entries
from .validation import validate_registry

_registries = {}  # registry.json -> (its stamp, the vocabulary it holds)


def read_registry(path: Path):
    """Read and validate one complete registry vocabulary, once per vendored file.

    `page init` writes a page's registry.json and nothing writes it again, while an
    action POST asks for the whole vocabulary before it can check a single press —
    so every press re-linted forty frozen entries, an order of magnitude more work
    than the contract check it was preparing for."""
    stamp = file_stamp(path)
    if stamp and (held := _registries.get(path)) and held[0] == stamp:
        return held[1]
    entries = read_registry_entries(path)
    registry = None if entries is None else validate_registry(entries, path)
    if stamp:
        _registries[path] = (stamp, registry)
    return registry


def load_registry(page_dir: Path):
    """The page's complete vendored vocabulary, or None before `page init`."""
    return read_registry(page_dir / "registry.json")


def layer_generation(page_dir: Path) -> str:
    """The epoch shared by this page's vendored runtime and server contract."""
    registry = read_registry_entries(page_dir / "registry.json")
    generation = (registry or {}).get("$layer", {}).get("generation")
    if not isinstance(generation, str) or not generation:
        raise RegistryError(
            f"{page_dir / 'registry.json'}: vendored registry lacks $layer.generation; "
            "run `leaf page init`"
        )
    return generation


def require_registry(page_dir: Path) -> dict:
    """The vendored vocabulary, for a command that has nothing to do without one."""
    registry = load_registry(page_dir)
    if registry is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    return registry
