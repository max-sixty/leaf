"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json

from playwright.sync_api import expect
from render_support import LIVE_V1, live_url, open_page

PAGE_MODULE = """\
import { label } from "./helper.js";
document.documentElement.dataset.pageModule = label;
"""

PAGE_WIDGET = """\
import { layerFact } from "/runtime/widget-api.js";

customElements.define("lf-local", class extends HTMLElement {
  connectedCallback() {
    layerFact("$tones");
    this.dataset.pageWidget = "ready";
  }
});
"""

PAGE_DECLARATION = {
    "lf-local": {
        "description": "A page-owned local widget.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": True,
        "x-verbatim": True,
        "x-example": '<lf-local id="local-example">Example</lf-local>',
    }
}


def test_page_module_dependencies_activate_and_remain_historical(browser, serve):
    source = LIVE_V1.replace(
        "</head>", '<script type="module" src="/page/app.js"></script>\n</head>'
    )
    version_url = serve(
        source,
        page_files={
            "app.js": PAGE_MODULE,
            "helper.js": 'export const label = "first";',
        },
    )
    page, errors = open_page(browser, live_url(version_url))
    expect(page.locator("html")).to_have_attribute("data-page-module", "first")
    first_document = page.evaluate("performance.timeOrigin")

    (serve.page_dir / "page" / "helper.js").write_text('export const label = "second";')

    expect(page.locator("html")).to_have_attribute("data-page-module", "second")
    assert page.evaluate("performance.timeOrigin") != first_document
    assert errors == []

    historical, historical_errors = open_page(browser, version_url, pin=True)
    expect(historical.locator("html")).to_have_attribute("data-page-module", "first")
    assert historical_errors == []
    historical.close()
    page.close()


def test_page_owned_registry_and_widget_use_the_captured_public_api(browser, serve):
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local">Page behavior</lf-local>',
    )
    version_url = serve(
        source,
        page_files={
            "registry.json": json.dumps(PAGE_DECLARATION),
            "widgets/lf-local.js": PAGE_WIDGET,
        },
    )

    page, errors = open_page(browser, live_url(version_url))

    expect(page.locator("#page-local")).to_have_attribute("data-page-widget", "ready")
    assert errors == []
    page.close()
