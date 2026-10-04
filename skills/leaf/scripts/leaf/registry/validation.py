"""Complete registry validation orchestration."""

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

# The vocabularies this process has validated, by a digest of their content, oldest
# first. Validation is a pure function of the vocabulary, `source` naming it only in a
# rejection, and every page vendored from one layer composes the same one: the suite's
# pages, a site build's examples, and a harness's pages each validated it anew, about a
# tenth of a second apiece for the bundled packages.
_VALIDATED: dict[bytes, None] = {}
_VALIDATED_LIMIT = 16


def validate_registry(registry: dict, source) -> dict:
    """Validate one complete vocabulary in its stable rejection order."""
    key = hashlib.blake2b(
        json.dumps(registry, sort_keys=True, separators=(",", ":")).encode(),
        digest_size=16,
    ).digest()
    if key in _VALIDATED:
        return registry
    _validate(registry, source)
    _VALIDATED[key] = None
    while len(_VALIDATED) > _VALIDATED_LIMIT:
        _VALIDATED.pop(next(iter(_VALIDATED)), None)
    return registry


def _validate(registry: dict, source) -> None:
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
