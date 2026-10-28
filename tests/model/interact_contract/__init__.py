"""Event admission, registry and layer contracts, and page checks under a page's
vocabulary, with the helpers their test modules share."""

from copy import deepcopy

from interact_support import declare_on_page, element_declaration

from leaf.registry.storage import read_page_registry


def vocabulary(page_dir) -> dict:
    """A copy of the page's candidate vocabulary for a test to change, without the
    `$layer` selection no declaration may name."""
    return {
        key: value
        for key, value in deepcopy(read_page_registry(page_dir).registry).items()
        if key != "$layer"
    }


def declare_vocabulary(page_dir, registry: dict) -> None:
    """Declare on the page each entry and `$` member in which `registry`, a changed
    `vocabulary`, differs from the page's layer (`declare_on_page`)."""
    declare_on_page(page_dir, lambda current: current.update(registry))


def _stateful_page_declaration(page_dir, tag="lf-local"):
    declaration = element_declaration(tag, upgrade=True)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)
    (widgets / f"{tag}.js").write_text("export function upgrade() {}\n")
    declaration["properties"].update(
        {
            "restated": {"type": "boolean"},
            "value": {"type": "string"},
        }
    )
    state = {
        "unit": "widget",
        "record": {"kind": "value", "attr": "value"},
    }
    declaration["x-state"] = {"first": state}
    return declaration


def _value_verb(attr):
    """A widget-unit verb that records one attribute's value."""
    return {"unit": "widget", "record": {"kind": "value", "attr": attr}}
