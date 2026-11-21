"""Registry composition and current declaration validation, and what an author's
own declarations advise.

Composition refuses only what breaks the vocabulary (`registry.validation`). What a
layer's own declarations do that works but may not be what their author meant, such
as a restated kernel fact or an example a page could not hold, is advice only that
author can act on: `declaration_advice` reads it, and the commands that check what
an author wrote report it, `package check` for a package, `page init` for the
packages it selects, and `page check` for a page's own declarations. Composition
itself, which every reader of a page runs, reports nothing.
"""

from pathlib import Path

from leaf.data_contracts import declared_data_bindings
from leaf.findings import Finding
from leaf.registry.contract import (
    element_declarations,
    is_element_name,
    read_registry_declarations,
    registry_finding,
)
from leaf.registry.layer import kernel_fact_advice, merged_registry, stamp_composition
from leaf.registry.validation import event_clause_advice, validate_registry
from leaf.registry.widgets import widget_advice
from leaf.structure import SourceDocument

from .instances import markup_findings


def layer_advice(roots: list[Path], registry: dict) -> list[Finding]:
    """What each of `roots`, a layer's packages, advises of its own `registry.json`
    (`declaration_advice`), in `registry`, the stamped vocabulary they compose. A
    page's own declarations its check has already read (`source.source_advice`)."""
    return [
        finding
        for root in roots
        if (path := root / "registry.json").is_file()
        for finding in declaration_advice(
            read_registry_declarations(path) or {}, registry, path
        )
    ]


def declaration_advice(declarations: dict, registry: dict, path) -> list[Finding]:
    """What one layer's `declarations`, read from `path`, advise their author in the
    stamped vocabulary `registry` they compose: each kernel fact they restate
    (`registry.layer.kernel_fact_advice`), each clause for an event kind there isn't
    (`registry.validation.event_clause_advice`), and of each element they declare,
    what its declaration leaves an instance to supply (`registry.widgets.widget_advice`)
    and an example a page could not hold (`_example_advice`)."""
    found = [
        *kernel_fact_advice(declarations, path),
        *event_clause_advice(declarations, registry, path),
    ]
    elements = element_declarations(registry)
    for tag in declarations:
        if is_element_name(tag) and tag in registry:
            found += widget_advice(tag, registry, elements, path)
            found += _example_advice(tag, registry, path)
    return found


def _example_advice(tag: str, registry: dict, path) -> list[Finding]:
    """An example a page could not hold, named by the first refusal it would meet:
    advice, since an example is documentation that no reader the user relies on
    needs valid, and a page that redeclares a layer's widget can invalidate the
    layer's examples."""
    if (example := registry[tag].get("example")) is None:
        return []
    parser = SourceDocument(example, fragment=True)
    errors = markup_findings(
        parser,
        registry,
        lambda: declared_data_bindings(parser.lf_elements, registry)[1],
    )
    if refused := [error for error in errors if error.refuses]:
        return [
            registry_finding(
                "invalid-example", path, tag, finding=refused[0].json(text=False)
            )
        ]
    return []


def incoming_registry(packages: list) -> dict:
    """The merged registry (`registry.layer.merged_registry`) `page init` will vendor,
    validated and stamped."""
    merged, source = merged_registry(packages)
    return stamp_composition(validate_registry(merged, source))
