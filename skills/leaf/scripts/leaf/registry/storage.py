"""Vendored registry storage and page lookup."""

import re
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


def layer_metadata(page_dir: Path) -> dict:
    """The identity recorded by this page's complete vendored layer."""
    path = page_dir / "registry.json"
    registry = read_registry_entries(path)
    layer = (registry or {}).get("$layer", {})
    generation = layer.get("generation")
    if not isinstance(generation, str) or not generation:
        raise RegistryError(
            f"{path}: vendored registry lacks $layer.generation; run `leaf page init`"
        )
    packages = layer.get("packages", [])
    if (
        not isinstance(packages, list)
        or not all(isinstance(value, str) and value for value in packages)
        or len(set(packages)) != len(packages)
    ):
        raise RegistryError(
            f"{path}: $layer.packages must be a unique list of non-empty strings"
        )
    fingerprint = layer.get("fingerprint")
    if fingerprint is not None and not (
        isinstance(fingerprint, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", fingerprint)
    ):
        raise RegistryError(f"{path}: $layer.fingerprint must be a SHA-256 identity")
    producer = layer.get("producer")
    if producer is not None and not isinstance(producer, dict):
        raise RegistryError(f"{path}: $layer.producer must be an object")
    if producer is not None:
        commit = producer.get("commit")
        dirty = producer.get("dirty")
        if commit is not None and not (
            isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit)
        ):
            raise RegistryError(
                f"{path}: $layer.producer.commit must be a Git object name"
            )
        if dirty is not None and not isinstance(dirty, bool):
            raise RegistryError(f"{path}: $layer.producer.dirty must be true or false")
        producer = {
            **({"commit": commit} if commit is not None else {}),
            **({"dirty": dirty} if dirty is not None else {}),
        }
    return {
        "generation": generation,
        "fingerprint": fingerprint,
        "packages": packages,
        **({"producer": producer} if producer else {}),
    }


def layer_generation(page_dir: Path) -> str:
    """The epoch shared by this page's vendored runtime and server contract."""
    return layer_metadata(page_dir)["generation"]


def require_registry(page_dir: Path) -> dict:
    """The vendored vocabulary, for a command that has nothing to do without one."""
    registry = load_registry(page_dir)
    if registry is None:
        sys.exit(f"no registry.json in {page_dir}; run `leaf page init` first")
    return registry
