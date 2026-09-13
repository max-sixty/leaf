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

from .contract import RegistryError
from .layer import merge_layer_declarations
from .validation import validate_registry


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
) -> PageRegistry:
    """Validate a page vocabulary and resolve its upgraded widgets.

    ``widget_paths`` contains available page-root-relative file names, including
    ``widgets/<tag>.js`` from the layer and ``page/widgets/<tag>.js`` from the
    authored page. ``declaration_sources`` records ``layer`` or ``page`` for each
    element; ``widget_sources`` records the winning relative path for each
    upgraded element. Inputs and their nested declarations remain untouched.
    """
    if "$layer" in page_declarations:
        raise RegistryError(f"{source}: $layer belongs to the selected layer")
    registry = deepcopy(layer_registry)
    merge_layer_declarations(registry, deepcopy(page_declarations))
    validate_registry(registry, source)

    # Example validation consumes source/instance readers which themselves load
    # page registries. Import it after those owners have finished initializing.
    from leaf.validation.compatibility import validate_registry_examples

    if page_declarations:
        validate_registry_examples(registry, source)
    declaration_sources = {}
    widget_sources = {}
    available = set(widget_paths)
    for tag, entry in registry.items():
        if not tag.startswith("lf-"):
            continue
        declaration_sources[tag] = "page" if tag in page_declarations else "layer"
        if not entry["x-upgrade"]:
            continue
        candidates = (f"page/widgets/{tag}.js", f"widgets/{tag}.js")
        implementation = next((path for path in candidates if path in available), None)
        if implementation is None:
            raise RegistryError(
                f"{source}: <{tag}> is upgraded but its module is missing; "
                f"expected {candidates[0]} or {candidates[1]}"
            )
        widget_sources[tag] = implementation
    return PageRegistry(registry, declaration_sources, widget_sources)
