"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json

from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    BOTH_STAMPS,
    LIVE_READING,
    LIVE_V1,
    LIVE_V2,
    holding,
    live_url,
    open_page,
    panel_settled,
    round_trip,
    stamp_page,
    told,
    wait_for_revision,
    watched,
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
      this.dataset.renderOrder = `${this.dataset.renderOrder || ""}subscribe,`;
      this.dataset.subscriberChoice = this.dataset.renderedChoice;
      this.dataset.readings = String(Number(this.dataset.readings || 0) + 1);
      this.requestUpdate();
    });
    const held = globalThis.__heldLocalPresentations?.get(this.id);
    if (held) this.controller.present(held);
  }

  disconnectedCallback() {
    this.stop?.();
    this.stop = null;
    super.disconnectedCallback();
  }

  choose() {
    this.dataset.renderOrder = "";
    this.dataset.gestures = String(Number(this.dataset.gestures || 0) + 1);
    const sent = this.controller.dispatch({
      kind: "action",
      verb: "choose",
      detail: { choice: "chosen" },
      references: {
        source: this.controller.reference(document.getElementById("live-reading")),
      },
    });
    if (!sent) return;
    this.reading = sent.reading;
    this.dataset.delivery = "pending";
    this.requestUpdate();
    sent.delivery.then(accepted => {
      this.dataset.delivery = accepted ? "accepted" : "refused";
    });
  }

  renderState(state) {
    if (globalThis.__failLocalRender) {
      globalThis.__failedLocalRenders =
        Number(globalThis.__failedLocalRenders || 0) + 1;
      throw new Error("deliberate render failure");
    }
    this.dataset.renderedChoice = state.choice.value;
    this.dataset.renderOrder = `${this.dataset.renderOrder || ""}render,`;
    this.requestUpdate();
  }

  async scheduleUpdate() {
    const held = globalThis.__heldLocalUpdate;
    globalThis.__heldLocalUpdate = null;
    if (held) await held;
    return super.scheduleUpdate();
  }

  render() {
    const choice = this.reading.state.choice?.value ?? this.getAttribute("choice");
    const available = this.reading.actions.choose?.available ?? false;
    return html`<button ?disabled=${!available} @click=${this.choose}>Choose</button>
      <output>${choice}</output>`;
  }
});
"""

STARTUP_PROJECTION_WIDGET = PAGE_WIDGET.replace(
    "    const held = globalThis.__heldLocalPresentations?.get(this.id);",
    """\
    if (!this.dataset.startupInvalidated) {
      this.dataset.startupInvalidated = "1";
      this.controller.defer()();
    }
    const held = globalThis.__heldLocalPresentations?.get(this.id);""",
).replace(
    "    this.dataset.renderedChoice = state.choice.value;",
    """\
    this.dataset.renderedChoice = state.choice.value;
    this.dataset.controllerRenders = String(
      Number(this.dataset.controllerRenders || 0) + 1
    );""",
)


def test_current_readiness_releases_a_connected_page_widget(browser, serve):
    """The readiness edge includes a late module's owner and first gesture route."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page, errors = open_page(
        browser,
        live_url(
            serve(
                source,
                page_files={
                    "registry.json": json.dumps(PAGE_DECLARATION),
                    "widgets/lf-local.js": PAGE_WIDGET,
                },
            )
        ),
    )

    installed = page.evaluate(
        """() => {
          const owner = document.querySelector('#page-local');
          const control = owner.renderRoot.querySelector('button');
          control.click();
          return {
            defined: customElements.get('lf-local') === owner.constructor,
            connected: owner.dataset.pageWidget,
            gestures: owner.dataset.gestures,
          };
        }"""
    )
    assert installed == {"defined": True, "connected": "ready", "gestures": "1"}
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    expect(page.locator("#page-local")).to_have_attribute(
        "data-render-order", "render,subscribe,"
    )
    expect(page.locator("#page-local")).to_have_attribute(
        "data-subscriber-choice", "chosen"
    )
    assert errors == []
    page.close()


def test_waiting_projection_settles_before_ready_state_reopens_it(browser, serve):
    """Provisional chrome cannot deadlock the state read that replaces it."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    url = live_url(
        serve(
            source,
            page_files={
                "registry.json": json.dumps(PAGE_DECLARATION),
                "widgets/lf-local.js": STARTUP_PROJECTION_WIDGET,
            },
        )
    )
    held = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/api/state*", lambda route: held.append(route))
    try:
        page.goto(url, wait_until="load")
        page.wait_for_function(
            "() => document.querySelector('#page-local')?.dataset.startupInvalidated"
        )
        expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
        assert held, "the positive control did not hold the first authoritative state"
        expect(page.locator("#page-local").get_by_role("button")).to_be_disabled()
        expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")
        expect(page.locator("#page-local")).to_have_attribute(
            "data-controller-renders", "1"
        )
        waiting = page.evaluate(
            """async () => {
              const entry = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
              const runtime = await import(
                new URL('runtime/semantic-state.js', new URL(entry, location.href)).href
              );
              window.readStartupApplication = runtime.readApplication;
              window.readStartupPresentation = runtime.readApplicationPresentation;
              const application = runtime.readApplication();
              const presentation = runtime.readApplicationPresentation();
              return {
                phase: application.phase,
                epoch: application.semanticEpoch,
                presented: presentation.presentedEpoch,
                pending: presentation.pending,
              };
            }"""
        )
        assert waiting["phase"] == "waiting"
        assert waiting["presented"] == waiting["epoch"]
        assert waiting["pending"] == []
        assert page.evaluate(
            "document.querySelector('script[data-lf-entry]').lfCurrentPresentationReady()"
        )

        held.pop(0).continue_()
        page.wait_for_function(BOTH_STAMPS)
        expect(page.locator("#page-local").get_by_role("button")).to_be_enabled()
        expect(page.locator("#page-local")).to_have_attribute(
            "data-controller-renders", "2"
        )
        ready = page.evaluate(
            """() => {
              const application = readStartupApplication();
              const presentation = readStartupPresentation();
              return {
                phase: application.phase,
                epoch: application.semanticEpoch,
                presented: presentation.presentedEpoch,
                pending: presentation.pending,
              };
            }"""
        )
        assert ready["phase"] == "ready"
        assert ready["epoch"] > waiting["epoch"]
        assert ready["presented"] == ready["epoch"]
        assert ready["pending"] == []
        assert errors == []
    finally:
        page.close()


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
                "references": {"source": {}},
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
        '<section id="reference-section"><p data-reference-source>Source</p>'
        "<strong data-reference-removal>Removal</strong></section>"
        '<lf-local id="page-local" choice="idle"></lf-local>'
        '<lf-ask id="package-ask"><h2>Package choice</h2>'
        '<lf-options id="package-options" choose>'
        '<lf-option id="package-a">A</lf-option>'
        '<lf-option id="package-b">B</lf-option>'
        "</lf-options></lf-ask>",
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

    reference_contract = page.evaluate(
        """() => {
          const controller = document.querySelector('#page-local').controller;
          const invalid = [];
          for (const references of [
            undefined,
            {source: {kind: 'id', id: 'live-reading'}, extra: {kind: 'id', id: 'x'}},
            {source: {kind: 'id', id: ''}},
          ]) {
            try {
              controller.dispatch({
                kind: 'action', verb: 'choose', detail: {choice: 'chosen'}, references,
              });
              invalid.push(false);
            } catch (error) {
              invalid.push(error instanceof TypeError);
            }
          }
          return {
            invalid,
            source: controller.reference(document.getElementById('live-reading')),
            structural: controller.reference(document.querySelector('[data-reference-source]')),
            ambiguous: (() => {
              const section = document.getElementById('reference-section');
              section.append(document.createElement('p'));
              try {
                controller.reference(section.querySelector('p'));
                return false;
              } catch (error) {
                return error instanceof TypeError;
              }
            })(),
          };
        }"""
    )
    assert reference_contract == {
        "invalid": [True, True, True],
        "source": {"kind": "id", "id": "live-reading"},
        "structural": {
            "kind": "structure",
            "anchor": "reference-section",
            "path": [{"tree": "light", "tag": "p"}],
        },
        "ambiguous": True,
    }

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    stale_references = page.evaluate(
        """(structural) => {
          const controller = document.querySelector('#page-local').controller;
          const removal = document.querySelector('[data-reference-removal]');
          const detached = controller.reference(removal);
          removal.remove();
          const dispatch = (reference) => controller.dispatch({
            kind: 'action',
            verb: 'choose',
            detail: {choice: 'chosen'},
            references: {source: reference},
          });
          return {
            ambiguous: dispatch(structural),
            detached: dispatch(detached),
          };
        }""",
        reference_contract["structural"],
    )
    assert stale_references == {"ambiguous": None, "detached": None}
    assert held == []
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
    assert held[0].request.post_data_json["references"] == {
        "source": {"kind": "id", "id": "live-reading"}
    }
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
    drifted = page.evaluate(
        """() => {
          pageLocal.id = 'drifted-local';
          const reading = pageLocal.controller.read();
          pageLocal.id = 'page-local';
          return {
            available: reading.actions.choose.available,
            undo: reading.actions.choose.undo.length,
          };
        }"""
    )
    assert drifted == {"available": False, "undo": 0}

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
    page.evaluate(
        "window.pageLocal = document.querySelector('#page-local'); pageLocal.remove()"
    )
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


def test_widget_controller_owns_presentation_across_values_and_lifetimes(
    browser, serve
):
    """One widget owns distinct render and preparation regions across its lifetime."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page, errors = open_page(
        browser,
        live_url(
            serve(
                source,
                page_files={
                    "registry.json": json.dumps(PAGE_DECLARATION),
                    "widgets/lf-local.js": PAGE_WIDGET,
                },
            )
        ),
    )
    page.evaluate(
        """async () => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          window.pageLocal = document.querySelector('#page-local');
          window.whenLeafPresented = presentation.whenApplicationPresented;
          window.whenLeafRegionsPresented =
            presentation.whenApplicationRegionsPresented;
          window.readLeafApplication = presentation.readApplication;
          window.readLeafPresentation = presentation.readApplicationPresentation;
          window.heldPreparation = () => {
            let release;
            const promise = new Promise(resolve => { release = resolve; });
            return {promise, release};
          };
        }"""
    )

    held_render = page.evaluate(
        """() => {
          window.heldWidgetUpdate = heldPreparation();
          window.__heldLocalUpdate = heldWidgetUpdate.promise;
          window.stopHeldWidgetReading = pageLocal.controller.subscribe(() => {});
          return readLeafPresentation().pending;
        }"""
    )
    assert held_render == ["widget:page-local:render"]
    page.evaluate("heldWidgetUpdate.release(); stopHeldWidgetReading()")
    page.wait_for_function("readLeafPresentation().pending.length === 0", timeout=3000)

    # Several children prepared by one owner are one requirement. A later call for the
    # same reading includes the earlier promise rather than superseding it.
    returned = page.evaluate(
        """() => {
          window.firstPreparation = heldPreparation();
          window.secondPreparation = heldPreparation();
          const first = pageLocal.controller.present(firstPreparation.promise);
          const second = pageLocal.controller.present(secondPreparation.promise);
          window.preparationReady = false;
          whenLeafPresented().then(() => { preparationReady = true; });
          return {
            first: first === firstPreparation.promise,
            second: second === secondPreparation.promise,
            pending: readLeafPresentation().pending,
          };
        }"""
    )
    assert returned == {
        "first": True,
        "second": True,
        "pending": ["widget:page-local:preparation"],
    }
    page.evaluate("firstPreparation.release('first')")
    assert page.evaluate("preparationReady") is False
    page.evaluate("secondPreparation.release('second')")
    page.wait_for_function("preparationReady", timeout=3000)

    # Deferral installs a held render ticket for each selected value. Refusal publishes
    # the newest authoritative value, but neither it nor the older optimistic ticket may
    # count as presented until the one-shot resume paints that newest reading.
    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    page.evaluate("window.pageLocal = document.querySelector('#page-local')")
    before = int(page.locator("#page-local").get_attribute("data-readings"))
    page.evaluate(
        "document.body.classList.add('lf-dragging'); "
        "window.resumeLocal = pageLocal.controller.defer(); true"
    )
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    assert page.evaluate("Number(pageLocal.dataset.readings)") == before
    assert page.evaluate("readLeafPresentation().pending") == [
        "widget:page-local:render",
        "projection:chrome",
    ]
    page.evaluate(
        "projectionReady = false; "
        "whenLeafRegionsPresented(['projection:chrome'], () => true)"
        ".then(() => { projectionReady = true; }); "
        "document.body.classList.remove('lf-dragging'); true"
    )
    page.wait_for_function("projectionReady", timeout=3000)
    assert page.evaluate("readLeafPresentation().pending") == [
        "widget:page-local:render"
    ]
    attempt = held_events[0].request.post_data_json["attempt"]
    held_events[0].fulfill(
        status=200,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    page.wait_for_function(
        "attempt => readLeafApplication().unresolved.some("
        "entry => entry.event.attempt === attempt && entry.answered)",
        arg=attempt,
    )
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "refused")
    assert page.evaluate("Number(pageLocal.dataset.readings)") == before
    assert page.locator("#page-local").get_by_role("status").text_content() == "chosen"
    page.evaluate(
        "presentationReady = false; "
        "whenLeafPresented().then(() => { presentationReady = true; }); true"
    )
    assert page.evaluate("presentationReady") is False
    resumed = page.evaluate(
        "resumeLocal(); const once = Number(pageLocal.dataset.readings); "
        "resumeLocal(); [once, Number(pageLocal.dataset.readings)]"
    )
    assert resumed == [before + 1, before + 1]
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "refused")
    page.wait_for_function(
        "attempt => !readLeafApplication().unresolved.some("
        "entry => entry.event.attempt === attempt)",
        arg=attempt,
    )
    page.wait_for_function("presentationReady", timeout=3000)
    page.unroute("**/api/event")

    # A removed owner retires both regions. Reconnecting the same instance reattaches
    # its still-pending preparation at the same semantic epoch, so an already resolved
    # readiness call cannot be reused as proof for the replacement renderer.
    page.evaluate(
        """() => {
          window.pageLocal = document.querySelector('#page-local');
          window.reconnectPreparation = heldPreparation();
          pageLocal.controller.present(reconnectPreparation.promise);
          window.beforeRemovalReady = false;
          whenLeafPresented().then(() => { beforeRemovalReady = true; });
          pageLocal.remove();
        }"""
    )
    page.wait_for_function("beforeRemovalReady", timeout=3000)
    page.evaluate(
        """() => {
          document.querySelector('main').append(pageLocal);
          window.reconnectedReady = false;
          whenLeafPresented().then(() => { reconnectedReady = true; });
          return true;
        }"""
    )
    assert page.evaluate("reconnectedReady") is False
    assert page.evaluate("readLeafPresentation().pending") == [
        "widget:page-local:preparation"
    ]
    page.evaluate("reconnectPreparation.release('reconnected')")
    page.wait_for_function("reconnectedReady", timeout=3000)

    # A synchronous render failure cannot escape the publisher or leave a partial
    # widget as presentation proof. The coordinator reports it, installs the existing
    # visible fail-soft body, and settles the region once even with several auxiliary
    # subscribers on that reading.
    held_failure = []
    page.route("**/api/event", lambda route: held_failure.append(route))
    page.evaluate(
        "pageLocal.controller.subscribe(() => {}); "
        "pageLocal.controller.subscribe(() => {}); "
        "window.__failLocalRender = true; true"
    )
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    holding(page, held_failure, 1, "the failing render's action")
    expect(page.locator("#page-local .lf-error")).to_have_text(
        "<lf-local> failed: <lf-local> renderState threw: deliberate render failure"
    )
    page.wait_for_function("readLeafPresentation().pending.length === 0", timeout=3000)
    assert page.evaluate("window.__failedLocalRenders") == 1
    assert errors == [
        "leaf: Presentation failed: <lf-local> renderState threw: deliberate render failure"
    ]
    page.close()


def test_conversation_presentation_waits_for_its_frozen_widgets_only(browser, serve):
    """The conversation parent absorbs descendants without joining unrelated page work."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page, errors = open_page(
        browser,
        live_url(
            serve(
                source,
                page_files={
                    "registry.json": json.dumps(PAGE_DECLARATION),
                    "widgets/lf-local.js": PAGE_WIDGET,
                },
            )
        ),
    )
    page.evaluate(
        """async () => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          const held = () => {
            let release, reject;
            const promise = new Promise((resolve, fail) => {
              release = resolve;
              reject = fail;
            });
            return {promise, release, reject};
          };
          window.pagePreparation = held();
          window.threadPreparation = held();
          window.__heldLocalPresentations = new Map([
            ['thread-local', threadPreparation.promise],
          ]);
          document.querySelector('#page-local').controller.present(
            pagePreparation.promise
          );
          window.whenLeafPresented = presentation.whenApplicationPresented;
          window.whenLeafRegionsPresented =
            presentation.whenApplicationRegionsPresented;
          window.readLeafPresentation = presentation.readApplicationPresentation;
        }"""
    )

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "frozen-widget-question",
            "author": "user",
            "revision": 1,
            "text": "Show the frozen widget.",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "revision": 1,
            "parent": "frozen-widget-question",
            "text": "This widget prepares inside the conversation.",
            "markup": '<lf-local id="thread-local" choice="idle"></lf-local>',
        },
    )
    page.wait_for_function(
        """() => {
          const pending = readLeafPresentation().pending;
          return document.querySelector('#thread-local') &&
            pending.includes('conversation') &&
            pending.includes('widget:thread-local:preparation') &&
            pending.includes('widget:page-local:preparation');
        }""",
        timeout=5000,
    )
    page.evaluate(
        "conversationReady = false; allReady = false; "
        "whenLeafRegionsPresented(['conversation'], () => true)"
        ".then(() => { conversationReady = true; }); "
        "whenLeafPresented().then(() => { allReady = true; }); true"
    )
    assert page.evaluate("conversationReady") is False
    page.evaluate("threadPreparation.release('thread')")
    page.wait_for_function("conversationReady", timeout=3000)
    assert page.evaluate("allReady") is False
    assert "widget:page-local:preparation" in page.evaluate(
        "readLeafPresentation().pending"
    )
    page.evaluate("pagePreparation.release('page')")
    page.wait_for_function("allReady", timeout=3000)

    # A descendant owns its own fail-soft result. Its failure reports once and settles,
    # while the parent list, count, and narrowing keep the same candidate reading.
    page.evaluate(
        """() => {
          window.failedThreadPreparation = (() => {
            let reject;
            const promise = new Promise((_resolve, fail) => { reject = fail; });
            return {promise, reject};
          })();
          window.__heldLocalPresentations.set(
            'thread-failing', failedThreadPreparation.promise
          );
        }"""
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "failing-widget-question",
            "author": "user",
            "revision": 1,
            "text": "Show another frozen widget.",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "revision": 1,
            "parent": "failing-widget-question",
            "text": "This widget fails its preparation.",
            "markup": '<lf-local id="thread-failing" choice="idle"></lf-local>',
        },
    )
    page.wait_for_function(
        """() => document.querySelector('#thread-failing') &&
          readLeafPresentation().pending.includes('conversation') &&
          readLeafPresentation().pending.includes(
            'widget:thread-failing:preparation'
          )""",
        timeout=5000,
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (2)")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    page.evaluate(
        "conversationReady = false; "
        "whenLeafRegionsPresented(['conversation'], () => true)"
        ".then(() => { conversationReady = true; }); "
        "failedThreadPreparation.reject(new Error('frozen descendant failure')); true"
    )
    page.wait_for_function("conversationReady", timeout=3000)
    expect(page.locator("#thread-failing")).to_have_count(1)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (2)")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    assert errors == ["leaf: Presentation failed: frozen descendant failure"]
    page.close()


def test_conversation_readiness_waits_for_the_keyed_thread_list(browser, serve):
    """The existing conversation ticket includes Lit ordering without replacing a card."""
    url = serve(LIVE_V1)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "standing-thread",
            "author": "user",
            "revision": 1,
            "text": "Keep this draft and its exact card.",
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    reply = page.locator('.lf-thread[data-id="standing-thread"] textarea')
    reply.fill("half a thought")
    reply.evaluate("input => input.setSelectionRange(4, 4)")
    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    page.evaluate(
        """async () => {
          const application = await window.__lfRuntimeImport('/runtime/application.js');
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          const list = document.querySelector('leaf-thread-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.scheduleUpdate = () => {
            if (!armed) return schedule();
            armed = false;
            return held.then(schedule);
          };
          window.releaseThreadList = release;
          window.readLeafPresentation = presentation.readApplicationPresentation;
          window.standingThread = document.querySelector(
            '.lf-thread[data-id="standing-thread"]'
          );
          application.createComment({
            attempt: 'held-thread-list',
            text: 'A second thread arrives.',
          });
        }"""
    )
    page.wait_for_function(
        "readLeafPresentation().pending.includes('conversation')", timeout=3000
    )
    pending_card = page.locator('.lf-thread[data-attempt="held-thread-list"]')
    expect(pending_card).to_have_count(0)
    assert page.evaluate(
        """() => {
          const current = document.querySelector(
            '.lf-thread[data-id="standing-thread"]'
          );
          const input = current.querySelector('textarea');
          return current === standingThread && document.activeElement === input &&
            input.value === 'half a thought' && input.selectionStart === 4;
        }"""
    )

    page.evaluate("releaseThreadList()")
    page.wait_for_function(
        "!readLeafPresentation().pending.includes('conversation')", timeout=3000
    )
    expect(pending_card).to_have_count(1)
    assert page.evaluate(
        """() => {
          const current = document.querySelector(
            '.lf-thread[data-id="standing-thread"]'
          );
          const input = current.querySelector('textarea');
          return current === standingThread && document.activeElement === input &&
            input.value === 'half a thought' && input.selectionStart === 4;
        }"""
    )
    held_events[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert errors == []
    page.close()
