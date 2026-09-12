"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json

from playwright.sync_api import expect
from render_support import (
    LIVE_READING,
    LIVE_V1,
    LIVE_V2,
    holding,
    live_url,
    open_page,
    stamp_page,
    told,
    wait_for_revision,
)

PAGE_MODULE = """\
import { label } from "./helper.js";
const state = globalThis.__pageModuleState ?? { loads: 0 };
state.loads += 1;
state.label = label;
globalThis.__pageModuleState = state;
document.documentElement.dataset.pageModule = `${label}:${state.loads}`;
"""

ACTIVATION_READING = f"""\
<p id="live-reading">{LIVE_READING}</p>
<button id="standing-control" type="button">Inspect continuity</button>
<lf-ask id="activation-decision"><h2>Activate the revision?</h2>
<lf-options id="activation-choice" choose>
  <lf-option id="activation-go">Continue</lf-option>
  <lf-option id="activation-wait">Wait</lf-option>
</lf-options></lf-ask>
"""


def activation_page(source):
    return source.replace(
        "</head>", '<script type="module" src="/page/app.js"></script>\n</head>'
    ).replace(f'<p id="live-reading">{LIVE_READING}</p>', ACTIVATION_READING)


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


def test_a_settled_delivery_activates_one_fresh_document_with_continuity(
    held_events, serve
):
    """One activation waits for its old document, then restores only Leaf state."""
    browser, held = held_events
    source = activation_page(LIVE_V1)
    version_url = serve(
        source,
        page_files={
            "app.js": PAGE_MODULE,
            "helper.js": 'export const label = "first";',
        },
    )
    page, errors = open_page(browser, live_url(version_url))
    expect(page.locator("html")).to_have_attribute("data-page-module", "first:1")
    first_document = page.evaluate("performance.timeOrigin")
    page.evaluate("window.__pageModuleState.oldDocumentOnly = true")

    threads = page.locator(".lf-threads-toggle")
    threads.click()
    draft = page.locator(".lf-general textarea")
    draft.fill("Keep this recoverable draft in the page instance.")
    threads.click()

    page.locator("#live-reading").evaluate(
        "el => { el.scrollIntoView({block: 'start'}); scrollBy(0, -120); }"
    )
    page.locator("#activation-go .lf-pick").click()
    holding(page, held, 1, "the unresolved option pick")
    standing = page.locator("#standing-control")
    standing.click()
    expect(standing).to_be_focused()
    reading_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert page.evaluate("scrollY") > 0

    try:
        (serve.page_dir / "page" / "helper.js").write_text(
            'export const label = "second";'
        )
        stamp_page(
            serve.page_dir, activation_page(LIVE_V2), "activate the complete page"
        )
        told(page)

        expect(page.locator(".lf-latest-chip")).to_be_visible()
        assert page.evaluate("performance.timeOrigin") == first_document
        expect(page).to_have_title("Live first")
        expect(standing).to_be_focused()
        assert len(held) == 1

        # The explicit door may release a composition hold, but it cannot release the
        # delivery hold. Put the reader back on the authored destination afterwards so
        # the eventual handoff has the same standing the automatic attempt observed.
        with page.expect_response("**/api/state*"):
            page.locator(".lf-latest-chip").click()
        told(page)
        assert page.evaluate("performance.timeOrigin") == first_document
        standing.click()
        expect(standing).to_be_focused()
        assert len(held) == 1
    finally:
        held.pop(0).continue_()

    wait_for_revision(page, 2)
    expect(page.locator("html")).to_have_attribute("data-page-module", "second:1")
    assert page.evaluate("performance.timeOrigin") != first_document
    assert page.evaluate("window.__pageModuleState") == {
        "loads": 1,
        "label": "second",
    }
    expect(page.locator("#standing-control")).to_be_focused()
    expect(page.locator("#activation-go")).to_have_attribute("chosen", "")
    restored_top = page.locator("#live-reading").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(restored_top - reading_top) < 2, (reading_top, restored_top)
    threads.click()
    expect(page.locator(".lf-general textarea")).to_have_value(
        "Keep this recoverable draft in the page instance."
    )
    assert errors == []

    historical, historical_errors = open_page(browser, version_url, pin=True)
    expect(historical.locator("html")).to_have_attribute("data-page-module", "first:1")
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
