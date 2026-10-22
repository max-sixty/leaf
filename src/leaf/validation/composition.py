"""Registry composition and current declaration validation."""

from leaf.registry.contract import read_registry_declarations, registry_error
from leaf.registry.layer import merge_layer_declarations, stamp_composition
from leaf.registry.validation import validate_registry
from leaf.structure import SourceDocument

from .instances import fragment_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if tag.startswith("$") or (example := entry.get("x-example")) is None:
            continue
        parser = SourceDocument(example, fragment=True)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise registry_error(
                "invalid-example", source, tag, finding=errors[0].json(text=False)
            )
    return registry


def incoming_registry(packages: list) -> dict:
    """The merged registry `page init` will vendor.

    Packages are additive at the top level; merge_layer_declarations holds the grain.
    """
    merged = {}
    paths = []
    for package in packages:
        path = package / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_declarations(merged, read_registry_declarations(path))
    if not paths:
        raise registry_error("no-incoming-registry")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    validate_registry_examples(validate_registry(merged, source), source)
    return stamp_composition(merged)
