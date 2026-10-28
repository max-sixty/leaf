"""Registry composition and current declaration validation."""

from leaf.data_contracts import declared_data_bindings, payload_error
from leaf.registry.contract import (
    gathering,
    read_registry_declarations,
    registry_error,
)
from leaf.registry.layer import merge_layer_declarations, stamp_composition
from leaf.registry.validation import validate_registry
from leaf.state import KERNEL_REGISTRY
from leaf.structure import SourceDocument

from .instances import fragment_errors
from .markup import id_errors


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one,
    refusing with the first problem in each (`registry.contract.gathering`)."""
    with gathering() as unit:
        for tag, entry in registry.items():
            if tag.startswith("$") or (example := entry.get("x-example")) is None:
                continue
            with unit():
                _validate_example(tag, entry, example, registry, source)
    return registry


def _validate_example(tag: str, entry: dict, example: str, registry: dict, source):
    parser = SourceDocument(example, fragment=True)
    errors = fragment_errors(parser, registry) + id_errors(parser)
    bindings, binding_errors = declared_data_bindings(parser.lf_elements, registry)
    errors += binding_errors
    if errors:
        raise registry_error(
            "invalid-example", source, tag, finding=errors[0].json(text=False)
        )
    for name, value in entry.get("x-example-data", {}).items():
        reason = (
            payload_error(name, bindings[name], value, registry)
            if name in bindings
            else f"source {name!r} is not bound in x-example"
        )
        if reason:
            raise registry_error("example-data", source, tag, reason=reason)


def incoming_registry(packages: list) -> dict:
    """The merged registry `page init` will vendor: the kernel registry's facts, then
    each layer's declarations over them.

    Packages are additive at the top level; merge_layer_declarations holds the grain.
    """
    merged = {}
    merge_layer_declarations(merged, read_registry_declarations(KERNEL_REGISTRY))
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
    # Examples validate against the vocabulary as pages read it, stamped.
    stamped = stamp_composition(validate_registry(merged, source))
    return validate_registry_examples(stamped, source)
