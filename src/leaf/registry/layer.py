"""Layer registry composition: the kernel registry and each layer's declarations
merged into one vocabulary, and the facts stamped into it that its readers read.

Composing validates nothing; `registry.validation` does. A reader of a page reads its
layer's vocabulary merged and stamped, and Leaf validates the vocabulary wherever it
composes the layer's files (`layer._composition`)."""

import json
from pathlib import Path

from leaf.state import KERNEL_REGISTRY

from .contract import (
    MODULES,
    complete_declarations,
    module_paths,
    read_registry_declarations,
    registry_error,
    stamp_decisions,
    stamp_grammars,
    stamp_states,
    stamp_words,
)

# The `$events` members a layer may restate; the rest are the kernel's.
LAYER_OWNED_EVENTS = frozenset({"handling", "answering"})
# The facts both runtimes read from the kernel registry, each whole and none from a
# layer (`registry.kernel`): Python and the browser (`runtime/kernel-facts.js`) both
# read the running Leaf's own copy, so a layer's change would reach neither.
KERNEL_FACTS = frozenset({"$passages", "$names", "$marks", "$authored"})


def merge_layer_declarations(merged: dict, declarations: dict) -> None:
    """Fold one layer's top-level registry declarations into the merge.

    Every authored vocabulary entry replaces the earlier one whole, whether an
    element schema or a selector idiom: a half-old, half-new entry is no layer's
    declaration. A $ declaration holds shared layer facts, so its members merge.
    A member that is itself a map merges by its own keys:
    $languages.paths is indexed by extension, and a layer adding `.svelte` must not
    silently drop every shipped extension with it. Scalar and list members replace
    whole — a names list is one statement. `$events` is the exception: every member
    but `handling` and `answering` is Leaf's fixed kernel transport contract and its
    `protocol`, which no layer changes; so is each of `KERNEL_FACTS`, whole.

    Inside a map member the merge is JSON merge-patch: a later layer's value
    replaces the key, a new key joins, and `null` removes one — which is the
    only way a project can take a shipped reaction token off its bar, or a user
    an extension off `$languages.paths`, without restating the whole map.
    """
    for name, entry in declarations.items():
        earlier = merged.get(name)
        if not (name.startswith("$") and earlier is not None):
            merged[name] = entry
            continue
        if name in KERNEL_FACTS:
            if _canonical(entry) != _canonical(earlier):
                raise registry_error("fixed-kernel-fact", name=name)
            continue
        if name == "$events":
            # Only the kernel's own value passes, compared as JSON so that `true` or
            # `1.0` is not taken for a protocol of 1, and the kernel's copy is kept.
            for key in entry.keys() - LAYER_OWNED_EVENTS:
                if _canonical(entry[key]) != _canonical(earlier.get(key)):
                    raise registry_error("fixed-events", key=key)
            entry = {key: entry[key] for key in entry.keys() & LAYER_OWNED_EVENTS}
        combined = {**earlier, **entry}
        for key, value in entry.items():
            if isinstance(value, dict) and isinstance(earlier.get(key), dict):
                combined[key] = {
                    k: v for k, v in {**earlier[key], **value}.items() if v is not None
                }
        merged[name] = {k: v for k, v in combined.items() if v is not None}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True)


def merged_registry(packages: list[Path]) -> tuple[dict, str]:
    """The kernel registry's facts with each package's registry declarations merged
    over them, the module each declared element has among the packages' `widgets/`
    (`contract.MODULES`), each declaration's defaults written in
    (`contract.complete_declarations`), and the name a refusal gives the merge.

    Packages are additive at the top level; `merge_layer_declarations` holds the
    grain."""
    merged = {}
    merge_layer_declarations(merged, read_registry_declarations(KERNEL_REGISTRY))
    paths = []
    widgets = set()
    for package in packages:
        widgets.update(
            f"widgets/{module.name}" for module in (package / "widgets").glob("*.js")
        )
        path = package / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_declarations(merged, read_registry_declarations(path))
    if not paths:
        raise registry_error("no-incoming-registry")
    merged[MODULES] = module_paths(merged, widgets, "widgets")
    complete_declarations(merged)
    return merged, "merged registry (" + ", ".join(str(path) for path in paths) + ")"


def stamp_composition(registry: dict) -> dict:
    """Write into a validated vocabulary what its readers read rather than derive:
    `$decisions` (`registry.contract.stamp_decisions`) and `$states`
    (`registry.contract.stamp_states`), which the browser reads, and each declared
    attribute's words as its schema's `enum` (`registry.contract.stamp_words`) and
    the grammar of each attribute naming what Leaf looks up as its `pattern`
    (`registry.contract.stamp_grammars`), which validation and an author reading the
    entry read.

    Each composition that ends in a vocabulary stamps it, `page init`'s layer and a
    page's own declarations over it, overwriting whatever a layer declared under
    these names. A reader's composition stamps a vocabulary its process hasn't
    validated (`layer.compose_vocabulary`), so a registry a package broke after
    `page init` may fail here instead of being refused as invalid.
    """
    stamp_decisions(registry)
    stamp_states(registry)
    stamp_words(registry)
    stamp_grammars(registry)
    return registry
