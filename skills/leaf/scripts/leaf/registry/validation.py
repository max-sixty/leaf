"""Complete registry validation orchestration.

Validity is a function of a vocabulary's content alone, so the process remembers
each vocabulary it has accepted and does not validate the same content twice. One
server validates the same captured layer for every page it activates: a gallery's
live samples are each a fresh page carrying their parent's vocabulary, and checking
every widget schema again per sample held the gallery's samples back by seconds.
A rejection is not remembered, so it is raised again in the words of its own source.
"""

import hashlib
import json

from .contract import retirement_slots
from .layer import (
    required_layer_declarations,
    validate_event_contracts,
    validate_event_handling,
    validate_layer_declarations,
)
from .state import validate_answered_conditions
from .widgets import (
    element_declarations,
    validate_widget_relations,
    validate_widget_schemas,
)

# Digests of the canonical JSON of every vocabulary this process has accepted.
_accepted: set[str] = set()


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary in its stable rejection order."""
    digest = hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest()
    if digest in _accepted:
        return registry
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
    _accepted.add(digest)
    return registry
