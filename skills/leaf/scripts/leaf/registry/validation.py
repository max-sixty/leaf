"""Complete registry validation orchestration."""

from .layer import (
    required_layer_declarations,
    validate_event_contracts,
    validate_event_handling,
    validate_layer_declarations,
)
from .state import (
    retirement_slots,
    validate_answered_conditions,
)
from .widgets import (
    element_declarations,
    validate_widget_relations,
    validate_widget_schemas,
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
    declarations = element_declarations(registry, path)
    validate_widget_schemas(declarations, data, path)
    slots = retirement_slots(registry)
    validate_widget_relations(registry, declarations, data, slots, path)
    validate_answered_conditions(declarations, path)
    return registry
