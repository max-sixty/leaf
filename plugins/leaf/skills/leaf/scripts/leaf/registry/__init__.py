"""Registry storage, validation orchestration, and page-facing readings."""

import sys
from pathlib import Path

from leaf.files import file_stamp

from . import contract as _contract
from .layer import (
    _required_layer_declarations,
    _validate_event_contracts,
    _validate_layer_declarations,
)
from .layer import merge_layer_entries as merge_layer_entries
from .state import (
    _validate_awaiting_units,
    _validate_retirement_facets,
    retirement_slots,
)
from .widgets import (
    _validate_widget_relations,
    _validate_widget_schemas,
    _widget_entries,
)

RegistryError = _contract.RegistryError
aware_instant = _contract.aware_instant
is_aware_datetime = _contract.is_aware_datetime
json_validator = _contract.json_validator
read_registry_entries = _contract.read_registry_entries
state_specs = _contract.state_specs
visual_parts = _contract.visual_parts

_registries = {}  # registry.json -> (its stamp, the vocabulary it holds)


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary in its stable rejection order."""
    path = source
    kinds, names, paths, tones, data, tokens = _required_layer_declarations(
        registry, path
    )
    _validate_event_contracts(kinds, path)
    _validate_layer_declarations(registry, path, names, paths, tones, data, tokens)
    widgets = _widget_entries(registry, path)
    _validate_widget_schemas(widgets, path)
    slots = retirement_slots(registry)
    _validate_widget_relations(widgets, data, slots, path)
    _validate_retirement_facets(slots, widgets, path)
    _validate_awaiting_units(widgets, path)
    return registry


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
