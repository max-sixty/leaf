"""Merged registry storage, layer composition, and page-facing readings."""

import sys
from pathlib import Path

from leaf import registry_contract as _contract
from leaf.files import file_stamp

RegistryError = _contract.RegistryError
aware_instant = _contract.aware_instant
is_aware_datetime = _contract.is_aware_datetime
json_validator = _contract.json_validator
read_registry_entries = _contract.read_registry_entries
retirement_slots = _contract.retirement_slots
state_specs = _contract.state_specs
validate_registry = _contract.validate_registry
visual_parts = _contract.visual_parts

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


def merge_layer_entries(merged: dict, entries: dict) -> None:
    """Fold one layer's top-level registry entries into the merge.

    A tag entry replaces the earlier one whole; schemas never deep-merge,
    because a half-old, half-new contract is no layer's vocabulary. A $ entry
    merges by member: it is not a contract but the layer's namespace of shared
    facts. Under replace-whole, a project declaring its one idiom vendored a
    $idioms holding exactly that idiom — its theme rules kept styling,
    theme.css concatenating where the registry did not, while `page catalog`
    silently dropped the shipped ten. A member that is itself a map merges by
    its own keys for the same reason one level down: $languages.paths is
    indexed by extension, and a layer adding `.svelte` must not silently drop
    every shipped extension with it. Scalar and list members replace whole —
    a names list is one statement — and the grain here decides nothing the
    gates don't re-check: validation and the vocabulary stamp read the merged
    result, whichever layer each piece came from.

    Inside a map member the merge is JSON merge-patch: a later layer's value
    replaces the key, a new key joins, and `null` removes one — which is the
    only way a project can take a shipped reaction token off its bar, or a user
    an extension off `$languages.paths`, without restating the whole map.
    """
    for name, entry in entries.items():
        earlier = merged.get(name)
        if not (name.startswith("$") and earlier is not None):
            merged[name] = entry
            continue
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {
                    k: v for k, v in {**earlier[key], **value}.items() if v is not None
                }
        merged[name] = {k: v for k, v in combined.items() if v is not None}


def reaction_tokens(registry: dict | None) -> dict:
    """The merged reaction vocabulary, token → entry, in declared order."""
    return (registry or {}).get("$reactions", {}).get("tokens", {})


def described(event: dict, registry: dict | None) -> dict:
    """A reaction event with its token's `means` beside it, so whoever reads the
    line — `leaf wait`'s consumer, `page state`'s — meets a custom token
    already explained. A token the vendored layer no longer declares keeps its
    word and says nothing more. Any other event passes through as it is."""
    token = event.get("token")
    if not token:
        return event
    entry = reaction_tokens(registry).get(token)
    return {**event, "means": entry["means"]} if entry else event
