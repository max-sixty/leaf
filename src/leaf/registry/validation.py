"""Complete registry validation orchestration."""

import hashlib
import json

from .contract import element_declarations, gathering
from .layer import check_layer_facts, validate_layer_declarations
from .widgets import (
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
    """Validate one complete vocabulary, refusing with the first problem in each
    independent unit (`contract.gathering`)."""
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


def _validate(registry: dict, path) -> None:
    """The layer facts' shape first, since every later check reads it. Then the
    layer's other facts beside the element declarations, which read nothing of
    each other, and only once every declaration holds alone does each meet the
    others, so a declaration's relations never read another half-validated."""
    check_layer_facts(registry, path)
    declarations = element_declarations(registry)
    with gathering() as unit:
        with unit():
            validate_layer_declarations(registry, path)
        with unit():
            validate_widget_schemas(declarations, path)
            validate_widget_relations(registry, declarations, registry["$data"], path)
