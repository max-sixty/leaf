"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json

from playwright.sync_api import expect
from render_support import LIVE_V1, live_url, open_page, round_trip

PAGE_MODULE = """\
import { label } from "./helper.js";
document.documentElement.dataset.pageModule = label;
"""

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
          const sent = controller.dispatch({
            kind: 'undo',
            target: candidate.attempt ?? candidate.id,
          });
          window.undoDelivery = sent.delivery;
          return {
            reading: sent.reading.state.choice.value,
            stale: controller.dispatch({
              kind: 'undo',
              target: candidate.attempt ?? candidate.id,
            }) === null,
          };
        }"""
    )
    assert stale_refused == {"reading": "idle", "stale": True}
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
