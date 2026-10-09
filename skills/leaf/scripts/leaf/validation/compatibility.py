"""Registry composition and current declaration validation."""

from leaf.registry.contract import RegistryError, read_registry_declarations
from leaf.registry.layer import merge_layer_declarations, stamp_composition
from leaf.registry.validation import validate_registry
from leaf.structure import SourceDocument

from .instances import fragment_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or (example := entry.get("x-example")) is None:
            continue
        parser = SourceDocument(example)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise RegistryError(f"{source}: <{tag}> x-example is invalid: {errors[0]}")
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
        raise RegistryError("the incoming layer has no registry.json")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    validate_registry_examples(validate_registry(merged, source), source)
    return stamp_composition(merged)
