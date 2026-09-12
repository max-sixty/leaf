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
    round_trip,
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
import { LitElement, html, layerFact, widgetController } from "/runtime/widget-api.js";

customElements.define("lf-local", class extends LitElement {
  controller = widgetController(this);
  reading = this.controller.read();
  stop = null;

  connectedCallback() {
    super.connectedCallback();
    layerFact("$tones");
    this.dataset.pageWidget = "ready";
    this.stop ??= this.controller.subscribe(reading => {
      this.reading = reading;
      this.dataset.readings = String(Number(this.dataset.readings || 0) + 1);
      this.requestUpdate();
    });
  }

  disconnectedCallback() {
    this.stop?.();
    this.stop = null;
    super.disconnectedCallback();
  }

  choose() {
    const sent = this.controller.dispatch({
      kind: "action",
      verb: "choose",
      detail: { choice: "chosen" },
    });
    if (!sent) return;
    this.reading = sent.reading;
    this.dataset.delivery = "pending";
    this.requestUpdate();
    sent.delivery.then(accepted => {
      this.dataset.delivery = accepted ? "accepted" : "refused";
    });
  }

  render() {
    const choice = this.reading.state.choice?.value ?? this.getAttribute("choice");
    const available = this.reading.actions.choose?.available ?? false;
    return html`<button ?disabled=${!available} @click=${this.choose}>Choose</button>
      <output>${choice}</output>`;
  }
});
"""

PAGE_DECLARATION = {
    "lf-local": {
        "description": "A page-owned local widget.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "choice": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-state": {
            "choose": {
                "detail": {
                    "type": "object",
                    "properties": {"choice": {"type": "string"}},
                    "required": ["choice"],
                    "additionalProperties": False,
                },
                "facet": "choice",
                "unit": "widget",
                "record": {"kind": "value", "attr": "choice", "value": "choice"},
            }
        },
        "x-example": '<lf-local id="local-example" choice="idle"></lf-local>',
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
        '<lf-local id="page-local" choice="idle"></lf-local>'
        '<lf-ask id="package-ask"><h2>Package choice</h2>'
        '<lf-options id="package-options" choose>'
        '<lf-option id="package-a">A</lf-option>'
        '<lf-option id="package-b">B</lf-option>'
        '</lf-options></lf-ask>',
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
    expect(page.locator("#package-options .lf-pick")).to_have_count(2)
    boundary = page.evaluate(
        """async () => {
          const api = await window.__lfRuntimeImport('/runtime/widget-api.js');
          const removed = [
            'actionAvailable', 'actionStands', 'sendAction', 'actionSequence',
            'watchActions', 'requestAvailable', 'sendRequest',
            'watchRequestLifecycle', 'standingState', 'projectionChanged', 'settle',
            'applicationState', 'readApplication', 'currentProjection',
          ];
          window.legacyActionEvents = 0;
          document.addEventListener('lf-actions', () => legacyActionEvents += 1);
          return removed.filter(name => name in api);
        }"""
    )
    assert boundary == []

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    deferred_at = page.evaluate(
        "window.pageLocal = document.querySelector('#page-local'); "
        "window.resumeLocal = pageLocal.controller.defer(); "
        "Number(pageLocal.dataset.readings)"
    )
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "pending")
    assert page.evaluate("Number(pageLocal.dataset.readings)") == deferred_at
    resumed_at = page.evaluate(
        "resumeLocal(); const once = Number(pageLocal.dataset.readings); "
        "resumeLocal(); [once, Number(pageLocal.dataset.readings)]"
    )
    assert resumed_at == [deferred_at + 1, deferred_at + 1]
    assert len(held) == 1
    attempt = held[0].request.post_data_json["attempt"]
    held[0].fulfill(
        status=200,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "refused")
    page.unroute("**/api/event")

    assert page.evaluate(
        "pageLocal = document.querySelector('#page-local'); "
        "pageLocal.controller.dispatch({kind: 'undo', target: 'not-a-candidate'}) === null"
    )
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    round_trip(page)
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "accepted")
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")

    undo = []
    page.route("**/api/event", lambda route: undo.append(route))
    stale_refused = page.evaluate(
        """() => {
          const controller = pageLocal.controller;
          const candidate = controller.read().actions.choose.undo[0];
          const objectTarget = controller.dispatch({
            kind: 'undo',
            target: candidate,
          }) === null;
          const sent = controller.dispatch({
            kind: 'undo',
            target: candidate.attempt ?? candidate.id,
          });
          window.undoDelivery = sent.delivery;
          return {
            reading: sent.reading.state.choice.value,
            objectTarget,
            stale: controller.dispatch({
              kind: 'undo',
              target: candidate.attempt ?? candidate.id,
            }) === null,
          };
        }"""
    )
    assert stale_refused == {"reading": "idle", "objectTarget": True, "stale": True}
    assert len(undo) == 1
    undo_attempt = undo[0].request.post_data_json["attempt"]
    undo[0].fulfill(
        status=200,
        json={
            "ok": False,
            "attempt": undo_attempt,
            "error": "undo refused before append",
            "final": True,
        },
    )
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    page.unroute("**/api/event")

    readings = int(page.locator("#page-local").get_attribute("data-readings"))
    page.evaluate("window.pageLocal = document.querySelector('#page-local'); pageLocal.remove()")
    page.locator("#package-a").click()
    round_trip(page)
    assert page.evaluate("Number(pageLocal.dataset.readings)") == readings
    page.evaluate("document.querySelector('main').append(pageLocal)")
    expect(page.locator("#page-local")).to_have_attribute(
        "data-readings", str(readings + 1)
    )
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    assert page.evaluate("legacyActionEvents") == 0
    assert errors == []
    page.close()
