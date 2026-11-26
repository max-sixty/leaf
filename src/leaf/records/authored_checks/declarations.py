"""What an author's own registry declarations advise.

Composition refuses only what breaks the vocabulary (`registry.validation`). What a
layer's own declarations do that works but may not be what their author meant, such
as a restated kernel fact or an example a page could not hold, is advice only that
author can act on: `declaration_advice` reads it, and the commands that check what
an author wrote report it, `package check` for a package, `page init` for the
packages it selects, and `page check` for a page's own declarations. Composition
itself, which every reader of a page runs, reports nothing.
"""

from pathlib import Path

from leaf.base.findings import Finding
from leaf.records.markup_checks.instances import markup_findings
from leaf.source.registry.contract import (
    is_element_name,
    read_registry_declarations,
    registry_finding,
)
from leaf.source.registry.layer import kernel_fact_advice
from leaf.source.registry.validation import event_clause_advice
from leaf.source.registry.widgets import widget_advice
from leaf.source.structure import SourceDocument


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
    for tag in declarations:
        if is_element_name(tag) and tag in registry:
            found += widget_advice(tag, registry, path)
            found += _example_advice(tag, registry, path)
    return found


def _example_advice(tag: str, registry: dict, path) -> list[Finding]:
    """An example a page could not hold, named by the first refusal it would meet in
    the example or the child of a live sample it declares: advice, since an example
    is documentation that no reader the user relies on needs valid, and a page that
    redeclares a layer's widget can invalidate the layer's examples."""
    if (example := registry[tag].get("example")) is None:
        return []
    errors = []
    pending: list[tuple[SourceDocument, tuple[str | None, ...]]] = [
        (SourceDocument(example, fragment=True), ())
    ]
    for document, samples in pending:
        errors += [
            found.but(samples=samples) for found in markup_findings(document, registry)
        ]
        pending += [
            (sample["document"], (*samples, sample["attrs"].get("id")))
            for sample in document.samples
        ]
    if refused := [error for error in errors if error.refuses]:
        return [
            registry_finding(
                "invalid-example", path, tag, finding=refused[0].json(text=False)
            )
        ]
    return []
