"""Registry composition and current declaration validation."""

from leaf.data_contracts import declared_data_bindings
from leaf.findings import note
from leaf.registry.contract import registry_finding
from leaf.registry.layer import merged_registry, stamp_composition
from leaf.registry.validation import validate_registry
from leaf.structure import SourceDocument

from .instances import fragment_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Check each catalog example where registry layers become one
    (`_validate_example`)."""
    for tag, entry in registry.items():
        if tag.startswith("$") or (example := entry.get("example")) is None:
            continue
        _validate_example(tag, example, registry, source)
    return registry


def _validate_example(tag: str, example: str, registry: dict, source):
    """Note an example a page could not hold, by the first refusal it would meet:
    advice, since an example is documentation that no reader the user relies on
    needs valid, and a page that redeclares a layer's widget can invalidate the
    layer's examples."""
    parser = SourceDocument(example, fragment=True)
    errors = fragment_errors(parser, registry) + id_errors(parser)
    errors += declared_data_bindings(parser.lf_elements, registry)[1]
    if refused := [error for error in errors if error.refuses]:
        note(
            registry_finding(
                "invalid-example", source, tag, finding=refused[0].json(text=False)
            )
        )


def incoming_registry(packages: list) -> dict:
    """The merged registry (`registry.layer.merged_registry`) `page init` will vendor,
    validated, stamped, and with each catalog example validated over it."""
    merged, source = merged_registry(packages)
    # Examples validate against the vocabulary as pages read it, stamped.
    stamped = stamp_composition(validate_registry(merged, source))
    return validate_registry_examples(stamped, source)
