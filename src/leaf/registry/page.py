"""Effective page declarations and revision-bound widget implementation paths.

The selected layer supplies a complete registry. A page contributes declarations
after it using the same merge grains as packages. Declaration replacement and
widget implementation selection are independent: a declaration can retain the
layer's widget, and a page widget can replace an unchanged layer declaration.

Composition consumes an already captured file inventory, so revision capture can
bind these choices to the exact bytes it stores without rereading the page.
"""

from collections.abc import Collection
from copy import deepcopy
from typing import NamedTuple

from .contract import (
    MODULES,
    complete_declarations,
    gathering,
    is_element_name,
    module_paths,
    registry_error,
    validate_modules,
)
from .layer import merge_layer_declarations, stamp_composition


class PageRegistry(NamedTuple):
    registry: dict
    declaration_sources: dict[str, str]
    widget_sources: dict[str, str]


def compose_page_registry(
    layer_registry: dict,
    page_declarations: dict,
    widget_paths: Collection[str],
    *,
    source="page/registry.json",
    validated: tuple[dict, dict] | None = None,
) -> PageRegistry:
    """Validate a page vocabulary and resolve its widgets' modules.

    ``validated`` is the layer and page declarations of a composition already
    validated, such as the active revision's: a composition of the same two is not
    validated again. The layer arrives stamped, so a composition is stamped
    (`registry.layer.stamp_composition`) where it is validated or declares anything
    over the layer, before its examples are validated.

    ``widget_paths`` contains available page-root-relative file names, including
    ``widgets/<tag>.js`` from the layer and ``page/widgets/<tag>.js`` from the
    authored page. ``declaration_sources`` records ``layer`` or ``page`` for each
    element and each ``$data.contracts.<name>`` declaration; ``widget_sources``
    records the winning relative path for each element a module upgrades, the
    vocabulary's ``contract.MODULES``. Inputs and their nested declarations remain
    untouched.
    """
    if "$layer" in page_declarations:
        raise registry_error("page-layer", source)
    registry = deepcopy(layer_registry)
    merge_layer_declarations(registry, deepcopy(page_declarations))
    # The page's own module over the layer's.
    registry[MODULES] = module_paths(
        registry, set(widget_paths), "page/widgets", "widgets"
    )
    complete_declarations(registry)
    # Compared by input, since the stamps make a composition unequal to the
    # unstamped merge of the same inputs.
    fresh = (layer_registry, page_declarations) != validated
    if fresh:
        from .validation import validate_registry

        validate_registry(registry, source)
    else:
        # The reused validation read these declarations with the modules they had
        # then, and a module file can go while its declaration stands.
        validate_modules(registry, source)
    if fresh or page_declarations:
        # Examples validate against the vocabulary as pages read it, stamped.
        stamp_composition(registry)
    declaration_sources = {
        f"$data.contracts.{name}": (
            "page"
            if name in page_declarations.get("$data", {}).get("contracts", {})
            else "layer"
        )
        for name in registry.get("$data", {}).get("contracts", {})
    }
    # Each example is validated independently, so one refusal names every problem
    # among them (`contract.gathering`).
    with gathering() as unit:
        if fresh and page_declarations:
            # Example validation consumes source/instance readers which themselves
            # load page registries. Import it after those owners have finished
            # initializing.
            from leaf.validation.composition import validate_registry_examples

            with unit():
                validate_registry_examples(registry, source)
    for tag in registry:
        if is_element_name(tag):
            declaration_sources[tag] = "page" if tag in page_declarations else "layer"
    return PageRegistry(registry, declaration_sources, dict(registry[MODULES]))
