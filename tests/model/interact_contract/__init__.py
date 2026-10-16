"""Event admission, registry and layer contracts, and page checks under a page's
vocabulary, with the helpers their test modules share."""

from interact_support import element_declaration


def _stateful_page_declaration(page_dir, tag="lf-local"):
    declaration = element_declaration(tag, upgrade=True)
    widgets = page_dir / "page" / "widgets"
    widgets.mkdir(exist_ok=True)
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
