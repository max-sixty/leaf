"""`widget_form.py` grades a saved page's widgets by how its package defines them."""

import json

import pytest

from leaf.source.registry.storage import write_layer
from leaf_dev.widget_form import get_assert

PAGE = '<lf-rating id="r"></lf-rating><lf-margin-note id="n">Caveat.</lf-margin-note>'
COMPONENT = """import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
defineWidget("lf-rating", Rating);
"""
DECLARED = ("lf-rating", "lf-margin-note")


def grade(
    tmp_path,
    modules,
    page=PAGE,
    declared=DECLARED,
    home="packages/review-kit",
    selects=("./review-kit",),
):
    package = tmp_path / "page" / home
    (package / "widgets").mkdir(parents=True)
    (tmp_path / "page" / "index.html").write_text(page)
    write_layer(tmp_path / "page", {"packages": list(selects), "generation": "0" * 32})
    (package / "registry.json").write_text(json.dumps({tag: {} for tag in declared}))
    for name, text in modules.items():
        (package / "widgets" / name).write_text(text)
    context = {
        "providerResponse": {"metadata": {"work": str(tmp_path)}},
        "config": {"drawing": ["lf-rating"], "drawless": ["lf-margin-note"]},
    }
    return get_assert("", context)


@pytest.mark.parametrize(
    "module",
    [
        COMPONENT,
        # Under another name, and with a space before the call's parenthesis.
        """import { defineWidget as widget } from "/runtime/effect-widget.js";
widget("lf-rating", Rating);
""",
        """import { defineWidget } from "/runtime/effect-widget.js";
defineWidget ("lf-rating", Rating);
""",
        """import { defineWidget } from "/runtime/effect-widget.js";
defineWidget(/* the tag */ "lf-rating", Rating);
""",
        """import * as adapter from "/runtime/effect-widget.js";
adapter.defineWidget("lf-rating", Rating);
""",
    ],
)
def test_a_package_component_and_a_drawless_declaration_pass(tmp_path, module):
    assert grade(tmp_path, {"lf-rating.js": module})["pass"]


@pytest.mark.parametrize(
    "modules",
    [
        # The tag is a plain element, though the file also defines another component,
        # or names a component only in a comment.
        {
            "lf-rating.js": """import { defineWidget } from "/runtime/effect-widget.js";
defineWidget("lf-other", Other);
customElements.define("lf-rating", class extends HTMLElement {});
"""
        },
        {
            "lf-rating.js": """// defineWidget("lf-rating", Rating);
customElements.define ("lf-rating", class extends HTMLElement {});
"""
        },
        {
            "lf-rating.js": """import { html } from "/vendor/lit.js";
customElements.define("lf-rating", class extends HTMLElement {});
"""
        },
        {
            "lf-rating.js": """import { defineWidget } from "/runtime/effect-widget.js";
if (false) defineWidget("lf-rating", Rating);
window.customElements.define("lf-rating", class extends HTMLElement {});
"""
        },
        {
            "lf-rating.js": COMPONENT
            + """const { html } = await import("/vendor/lit.js");
"""
        },
        # The widget that draws nothing has a module.
        {"lf-rating.js": COMPONENT, "lf-margin-note.js": "// nothing\n"},
        {
            "lf-rating.js": COMPONENT,
            "notes.js": """import { defineWidget } from "/runtime/effect-widget.js";
defineWidget("lf-margin-note", Note);
""",
        },
    ],
)
def test_a_widget_written_another_way_fails(tmp_path, modules):
    assert not grade(tmp_path, modules)["pass"]


def test_each_widget_must_be_declared_by_a_package_and_placed(tmp_path):
    modules = {"lf-rating.js": COMPONENT}
    assert not grade(tmp_path / "unplaced", modules, page="<p>None.</p>")["pass"]
    assert not grade(
        tmp_path / "commented", modules, page=f"<p>None.</p><!-- {PAGE} -->"
    )["pass"]
    assert not grade(tmp_path / "undeclared", modules, declared=("lf-rating",))["pass"]
    assert not grade(tmp_path / "page-local", modules, home="page")["pass"]
    assert not grade(tmp_path / "unselected", modules, selects=("./other-kit",))["pass"]


def test_a_page_module_that_overrides_the_package_fails(tmp_path):
    overriding = tmp_path / "page" / "page" / "widgets"
    overriding.mkdir(parents=True)
    (overriding / "lf-rating.js").write_text(COMPONENT)
    assert not grade(tmp_path, {"lf-rating.js": COMPONENT})["pass"]
