"""Complete registry validation orchestration."""

from .layer import (
    required_layer_declarations,
    validate_event_contracts,
    validate_event_handling,
    validate_layer_declarations,
)
from .state import (
    retirement_slots,
    validate_awaiting_units,
    validate_retirement_facets,
)
from .widgets import (
    validate_widget_relations,
    validate_widget_schemas,
    widget_entries,
)


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary in its stable rejection order."""
    path = source
    kinds, names, paths, tones, data, tokens = required_layer_declarations(
        registry, path
    )
    validate_event_contracts(kinds, path)
    validate_event_handling(registry["$events"], kinds, path)
    validate_layer_declarations(registry, path, names, paths, tones, data, tokens)
    widgets = widget_entries(registry, path)
    validate_widget_schemas(widgets, path)
    slots = retirement_slots(registry)
    validate_widget_relations(registry, widgets, data, slots, path)
    validate_retirement_facets(slots, widgets, path)
    validate_awaiting_units(widgets, path)
    return registry
