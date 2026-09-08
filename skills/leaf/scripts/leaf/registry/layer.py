"""Layer registry composition and contract validation."""

import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from leaf.schema import ASSETS, DATA_CONTRACT_NAME, EXTENSION_SCHEMA, HTML_NAME

from .contract import (
    GUIDANCE_READER,
    RegistryError,
    read_registry_entries,
    unresolved_schema_reference,
)


def kernel_event_kinds() -> dict:
    """The fixed event records produced and consumed by Leaf's kernel."""
    return read_registry_entries(ASSETS / "registry.json")["$events"]["kinds"]


def merge_layer_entries(merged: dict, entries: dict) -> None:
    """Fold one layer's top-level registry entries into the merge.

    A tag entry replaces the earlier one whole; schemas never deep-merge,
    because a half-old, half-new contract is no layer's vocabulary. A $ entry
    holds shared layer facts, so its members merge. Under replace-whole, a project
    declaring one idiom vendored a $idioms holding exactly that idiom — its theme
    rules kept styling, theme.css concatenating where the registry did not, while
    the vendored registry silently dropped the shipped ten. A member that is itself
    a map merges by its own keys for the same reason one level down:
    $languages.paths is indexed by extension, and a layer adding `.svelte` must not
    silently drop every shipped extension with it. Scalar and list members replace
    whole — a names list is one statement. `$events.kinds` is the exception: it is
    Leaf's fixed kernel transport contract, and a layer cannot change it.

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
        if (
            name == "$events"
            and "kinds" in entry
            and entry["kinds"] != earlier.get("kinds")
        ):
            raise RegistryError(
                "$events.kinds is Leaf's fixed transport contract and cannot be "
                "changed by a layer"
            )
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {
                    k: v for k, v in {**earlier[key], **value}.items() if v is not None
                }
        merged[name] = {k: v for k, v in combined.items() if v is not None}


def required_layer_declarations(registry: dict, path):
    try:
        kinds = registry["$events"]["kinds"]
        names = registry["$languages"]["names"]
        paths = registry["$languages"]["paths"]
        tones = registry["$tones"]["names"]
        data = registry["$data"]
        tokens = registry["$reactions"]["tokens"]
    except (KeyError, TypeError):
        raise RegistryError(
            f"{path}: registry must declare $events.kinds, $languages.names/paths, "
            "$tones.names, $data, and $reactions.tokens"
        ) from None
    return kinds, names, paths, tones, data, tokens


def validate_event_handling(events: dict, kinds: dict, path) -> None:
    """`$events.handling` is read directly by every batch a wait prints, so a
    layer that restates a kind is held to the shape the consumer assumes: a
    declared kind, one non-empty sentence. The complete vendored registry must
    carry the map; individual kind guidance remains optional."""
    handling = events.get("handling")
    if not isinstance(handling, dict) or any(
        kind not in kinds or not isinstance(text, str) or not text.strip()
        for kind, text in handling.items()
    ):
        raise RegistryError(
            f"{path}: $events.handling must map declared kinds to one non-empty "
            "sentence each"
        )


def validate_event_contracts(kinds: dict, path) -> None:
    if kinds != kernel_event_kinds():
        raise RegistryError(
            f"{path}: $events.kinds must equal Leaf's fixed transport contract"
        )


def validate_layer_declarations(
    registry: dict, path, names, paths, tones, data, tokens
) -> None:
    # $keys documents exactly the x- keys the lint admits, one string per key: the
    # keys are closed here (EXTENSION_SCHEMA), so a member for a key that cannot be
    # declared is documentation of nothing, and a key with no member is one an author
    # reads the registry for and finds unsaid. Agents query it and the site's table is
    # generated from it, which is what makes the pin worth keeping.
    keys = registry.get("$keys")
    admitted = set(EXTENSION_SCHEMA["properties"])
    documented = set(keys or {}) - {"description"}
    if (
        not isinstance(keys, dict)
        or not isinstance(keys.get("description"), str)
        or not all(isinstance(text, str) and text for text in keys.values())
        or documented != admitted
    ):
        raise RegistryError(
            f"{path}: $keys must carry a description and one paragraph per x- key the "
            f"lint admits — missing {sorted(admitted - documented)}, "
            f"unadmitted {sorted(documented - admitted)}"
        )
    if (
        not isinstance(names, list)
        or not all(isinstance(name, str) for name in names)
        or len(names) != len(set(names))
    ):
        raise RegistryError(
            f"{path}: $languages.names must be a unique list of strings"
        )
    if not isinstance(paths, dict) or not all(
        isinstance(extension, str) and language in names
        for extension, language in paths.items()
    ):
        raise RegistryError(
            f"{path}: $languages.paths must map extensions to declared languages"
        )
    # Shape, not just presence, because `declared_word_errors` asks a list for membership
    # and a string answers the same question by substring: a layer declaring
    # `"names": "ok"` would pass every one-letter tone and paint none of them, which is
    # exactly the invisible failure the check exists to catch.
    if (
        not isinstance(tones, list)
        or not all(isinstance(tone, str) for tone in tones)
        or len(tones) != len(set(tones))
    ):
        raise RegistryError(f"{path}: $tones.names must be a unique list of strings")
    if (
        not isinstance(data, dict)
        or set(data) != {"description", "contracts"}
        or not isinstance(data.get("description"), str)
        or not data["description"]
        or not isinstance(data.get("contracts"), dict)
    ):
        raise RegistryError(
            f"{path}: $data must carry a description and a contracts object"
        )
    for contract, declaration in data["contracts"].items():
        if (
            not isinstance(contract, str)
            or re.fullmatch(DATA_CONTRACT_NAME, contract) is None
        ):
            raise RegistryError(f"{path}: $data has invalid contract name {contract!r}")
        if (
            not isinstance(declaration, dict)
            or not {"description", "schema"} <= set(declaration)
            or set(declaration) - {"description", "schema", "guidance", "fragments"}
            or not isinstance(declaration.get("description"), str)
            or not declaration["description"]
            or not isinstance(declaration.get("schema"), dict)
        ):
            raise RegistryError(
                f"{path}: $data contract {contract!r} must carry a description and "
                "schema, with optional guidance and fragments"
            )
        fragments = declaration.get("fragments")
        if fragments is not None and (
            not isinstance(fragments, dict)
            or set(fragments) != {"items", "key", "value"}
            or any(
                not isinstance(field, str) or not field for field in fragments.values()
            )
            or len(set(fragments.values())) != 3
        ):
            raise RegistryError(
                f"{path}: $data contract {contract!r} fragments must name distinct "
                "non-empty items, key, and value fields"
            )
        guidance_errors = sorted(
            GUIDANCE_READER.iter_errors(declaration.get("guidance", {})),
            key=str,
        )
        if guidance_errors:
            raise RegistryError(
                f"{path}: $data contract {contract!r} guidance is invalid: "
                f"{guidance_errors[0].message}"
            )
        try:
            Draft202012Validator.check_schema(declaration["schema"])
        except SchemaError as error:
            raise RegistryError(
                f"{path}: $data contract {contract!r} has an invalid JSON Schema: "
                f"{error.message}"
            ) from error
        if reference := unresolved_schema_reference(declaration["schema"]):
            raise RegistryError(
                f"{path}: $data contract {contract!r} schema reference {reference!r} "
                "does not resolve within the package; data contracts must be "
                "self-contained"
            )
    # Each token whole: the runtime paints `glyph`, the panel's narrowing reads
    # `settles`, and off-page readers expose `means` only when a package supplies it.
    # A missing glyph or misspelled behavior would otherwise fail silently.
    if not isinstance(tokens, dict) or not all(
        isinstance(name, str)
        and re.fullmatch(HTML_NAME, name)
        and isinstance(entry, dict)
        and not set(entry) - {"glyph", "means", "settles"}
        and isinstance(entry.get("glyph"), str)
        and entry["glyph"].strip()
        and len(entry["glyph"]) <= 4
        and (
            "means" not in entry
            or (isinstance(entry["means"], str) and bool(entry["means"]))
        )
        and isinstance(entry.get("settles", False), bool)
        for name, entry in tokens.items()
    ):
        raise RegistryError(
            f"{path}: $reactions.tokens must map lowercase token names to entries "
            "with a short `glyph` of at most four code points, optionally a non-empty "
            "`means`, and optionally a boolean `settles`"
        )
