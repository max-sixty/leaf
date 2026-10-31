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

from .contract import gathering, is_element_name, registry_error
from .layer import merge_layer_declarations, stamp_composition
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
    validated: dict | None = None,
) -> PageRegistry:
    """Validate a page vocabulary and resolve its upgraded widgets.

    ``validated`` is a vocabulary already validated, such as the active revision's:
    a composition equal to it is not validated again. A composition that is
    validated is stamped (`registry.layer.stamp_composition`) before its examples
    are; one equal to ``validated`` already is.

    ``widget_paths`` contains available page-root-relative file names, including
    ``widgets/<tag>.js`` from the layer and ``page/widgets/<tag>.js`` from the
    authored page. ``declaration_sources`` records ``layer`` or ``page`` for each
    element and each ``$data.contracts.<name>`` declaration; ``widget_sources``
    records the winning relative path for each upgraded element. Inputs and their
    nested declarations remain untouched.
    """
    if "$layer" in page_declarations:
        raise registry_error("page-layer", source)
    registry = deepcopy(layer_registry)
    merge_layer_declarations(registry, deepcopy(page_declarations))
    fresh = registry != validated
    if fresh:
        validate_registry(registry, source)
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
    widget_sources = {}
    available = set(widget_paths)
    # Each example and each widget's module is found or missed independently, so one
    # refusal names every problem among them (`contract.gathering`).
    with gathering() as unit:
        if fresh and page_declarations:
            # Example validation consumes source/instance readers which themselves
            # load page registries. Import it after those owners have finished
            # initializing.
            from leaf.validation.composition import validate_registry_examples

            with unit():
                validate_registry_examples(registry, source)
        for tag, entry in registry.items():
            if not is_element_name(tag):
                continue
            declaration_sources[tag] = "page" if tag in page_declarations else "layer"
            if entry["x-upgrade"]:
                with unit():
                    widget_sources[tag] = _implementation(tag, available, source)
    return PageRegistry(registry, declaration_sources, widget_sources)


def _implementation(tag: str, available: set, source) -> str:
    """The module that upgrades `tag`: the page's own over the layer's."""
    candidates = (f"page/widgets/{tag}.js", f"widgets/{tag}.js")
    implementation = next((path for path in candidates if path in available), None)
    if implementation is None:
        raise registry_error("missing-module", source, tag, expected=list(candidates))
    return implementation
