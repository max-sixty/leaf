"""Complete registry validation orchestration."""

from .layer import (
    _required_layer_declarations,
    _validate_event_contracts,
    _validate_layer_declarations,
)
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
