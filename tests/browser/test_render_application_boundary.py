"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json
import re
from itertools import pairwise

import pytest
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_READING,
    LIVE_V1,
    SEATED_OBLIGATION_PAGE,
    live_url,
)
from render_harness import (
    PANEL,
    PANEL_THREAD,
    consume_browser_errors,
    expect_obligations_answered,
    expect_open_threads,
    holding,
    http_error_console,
    is_problem,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_control,
    panel_menu,
    panel_settled,
    refuse,
    round_trip,
    said,
    sending,
    stamp_page,
    stored_draft_text,
    take_browser_errors,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf import interaction_log as interaction_model
from leaf import thread as thread_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from leaf.schema import ELEMENT_ID

THREAD_READER = r"""
import {LeafElement, html, readThreads, threadSummary, threadTurns} from '/runtime/widget-api.js';
customElements.define('lf-thread-reader', class extends LeafElement {
  render() {
    const collection = readThreads();
    this.collection = collection;
    this.sameReading = collection === readThreads();
    this.topic = collection.threads[0] && threadSummary(collection.threads[0]).topic;
    return html`<pre>${collection.threads.map(thread =>
      threadTurns(thread).map(message => message.body.text).join('\n')
    ).join('\n')}</pre>`;
  }
});
"""

THREAD_READER_DECLARATION = {
    "description": "A read-only package thread view.",
    "type": "object",
    "properties": {"id": {"type": "string"}},
    "required": ["id"],
    "additionalProperties": False,
    "x-content": "empty",
    "x-upgrade": True,
    "x-example": '<lf-thread-reader id="reader-example"></lf-thread-reader>',
}

THREAD_FILTER = r"""
import {LeafElement, html, repeat, signal, threadActions, readThreads, threadSummary} from '/runtime/widget-api.js';
customElements.define('lf-thread-filter', class extends LeafElement {
  query = signal('');
  setup() { this.query.value = this.getAttribute('filter') ?? ''; }
  render() {
    const collection = readThreads();
    this.collection = collection;
    this.sameReading = collection === readThreads();
    this.updates = (this.updates ?? 0) + 1;
    const shown = collection.threads.filter(thread =>
      threadSummary(thread).topic.toLowerCase().includes(this.query.value.toLowerCase()));
    return html`<input aria-label=${`Filter ${this.id}`} .value=${this.query.value}
      @input=${event => { this.query.value = event.target.value; }}>
      <ul>${repeat(shown, thread => thread.key, thread => html`<li><button
        @click=${() => threadActions.open(thread.key)}>${threadSummary(thread).topic}</button></li>`)}</ul>`;
  }
});
"""

THREAD_FILTER_DECLARATION = {
    "description": "An instance-local filter over Leaf's shared Thread reading.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "filter": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": False,
    "x-content": "empty",
    "x-upgrade": True,
    "x-example": '<lf-thread-filter id="example"></lf-thread-filter>',
}


def test_browser_interactions_are_recorded_beside_server_requests(browser, serve):
    """A user gesture remains visible even when it changes no semantic page state."""
    url = serve(
        leaf_page(
            "Interaction trace",
            '<h1>Interaction trace</h1><input id="trace-input" aria-label="Entry">'
            '<button id="trace-button">Continue</button>',
        )
    )
    page = open_page(browser, url)

    def contains(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    with page.expect_response(lambda response: contains(response, "input")):
        page.locator("#trace-input").fill("hello")
    with page.expect_response(lambda response: contains(response, "click")):
        page.locator("#trace-button").click()
    page.locator("h1").click()
    with page.expect_response(lambda response: contains(response, "command")):
        page.keyboard.press("?")
    with page.expect_response(
        lambda response: contains(response, "interaction_omitted")
    ):
        page.locator("#trace-input").fill("é" * 25_000)

    rows = [
        json.loads(line)
        for line in (serve.page_dir / interaction_model.INTERACTIONS_FILE)
        .read_text()
        .splitlines()
    ]
    inputs = [row for row in rows if row.get("type") == "input"]
    clicks = [row for row in rows if row.get("type") == "click"]
    commands = [row for row in rows if row.get("type") == "command"]
    omitted = [row for row in rows if row.get("type") == "interaction_omitted"]
    assert any(
        row["value"] == "hello"
        and any("input#trace-input" in part for part in row["target"])
        for row in inputs
    )
    assert any(
        any("button#trace-button" in part for part in row["target"]) for row in clicks
    )
    reference = next(row for row in commands if row["id"] == "command.reference.open")
    assert reference["title"]
    assert "description" in reference
    assert reference["focus"]["target"] == "body"
    assert reference["scroll"] == [0, 0]
    assert len({row["session"] for row in inputs + clicks + commands}) == 1
    assert omitted
    assert all(
        row["originalType"] in {"beforeinput", "input"}
        and row["reason"] == "record_exceeds_limit"
        and row["bytes"] > 40_000
        and row["monotonic_ms"] >= 0
        and row["visibility"] == "visible"
        and row["observed_at"]
        for row in omitted
    )
    assert "é" * 25_000 not in json.dumps(rows, ensure_ascii=False)
    assert any(
        row.get("source") == "server"
        and row["method"] == "POST"
        and row["path"] == "/api/interaction"
        and row["status"] == 204
        for row in rows
    )


def test_reply_timing_records_send_and_words_when_the_panel_opens(browser, serve):
    """The diagnostic's one browser clock spans local Send and actual reply words.

    A reply behind the closed panel has no visible words. Opening the panel records
    them once, without message text, linked by its admitted ID and the send's attempt.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Timing feedback",
                "<h1>Timing feedback</h1>"
                '<lf-local id="timing-local" choice="idle"></lf-local>',
            ),
            page_files={
                "registry.json": json.dumps(PAGE_DECLARATION),
                "widgets/lf-local.js": PAGE_WIDGET,
            },
        ),
    )
    write(page_comment(page), "Which job comes first?")
    with sending(page, "the timing question"):
        page.locator(".lf-fp-send").click()
    # The send opens the new thread's view; put it away, so the reply arrives unseen.
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    question = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event["author"] == "user"
    )
    answer = thread_model.post_reply(
        serve.page_dir,
        {"responds": question["id"]},
        "The roof comes first.",
    )
    told(page)

    def trace_has(response, kind):
        return (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == kind
                for entry in response.request.post_data_json["entries"]
            )
        )

    # A real diagnostic flush is the completion edge for the absence: all earlier
    # queued rows are persisted before this later user gesture's row is acknowledged.
    with page.expect_response(lambda response: trace_has(response, "click")):
        page.locator("h1").click()
    trace = interaction_model.read_interactions(serve.page_dir)
    assert not any(row.get("type") == "reply_visible" for row in trace)

    # Unrelated preparation prevents global presentation proof, while the reply's
    # own rendered words are already visible. Feedback telemetry must not wait on it.
    page.evaluate("""() => {
      const held = Promise.withResolvers();
      window.releaseTimingPreparation = held.resolve;
      document.querySelector('#timing-local').controller.present(held.promise);
    }""")
    with page.expect_response(lambda response: trace_has(response, "reply_visible")):
        view = open_panel_thread(page, question["id"])
        expect(view.locator(".lf-msg.agent .lf-msg-text")).to_have_text(
            "The roof comes first."
        )
    assert page.evaluate("""async () => (await window.__lfCheckApi())
        .readApplicationPresentation().pending.includes('widget:timing-local:preparation')""")
    page.evaluate("releaseTimingPreparation()")
    rendered(page)
    trace = interaction_model.read_interactions(serve.page_dir)
    submitted = next(
        row
        for row in trace
        if row.get("type") == "event_submit" and row["attempt"] == question["attempt"]
    )
    visible = [row for row in trace if row.get("type") == "reply_visible"]
    assert len(visible) == 1
    shown = visible[0]
    assert shown["reply_id"] == answer["id"]
    assert shown["presentation_kind"] == "message_words"
    assert shown["reply_kind"] == "answer"
    assert shown["session"] == submitted["session"]
    assert shown["monotonic_ms"] >= submitted["monotonic_ms"]
    assert shown["visibility"] == submitted["visibility"] == "visible"
    assert "text" not in shown and "text" not in submitted


def test_browser_trace_records_where_touch_events_are_not_exposed(browser, serve):
    """Firefox on a desktop without a touch screen, and Safari on a Mac, expose no
    `TouchEvent` interface. Chromium and Playwright's WebKit always do, so the page
    removes it before any module evaluates. A tap's native events still arrive, and
    the trace still reads their touch points."""
    url = serve(leaf_page("Trace desktop", '<h1 id="trace-target">Trace desktop</h1>'))
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=True
    )
    page = open_page(
        browser, url, context=context, init_script="delete window.TouchEvent"
    )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "click"
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        page.locator("#trace-target").tap()

    rows = [
        json.loads(line)
        for line in (serve.page_dir / interaction_model.INTERACTIONS_FILE)
        .read_text()
        .splitlines()
    ]
    assert any(
        row.get("type") == "touchstart" and len(row["touches"]) == 1 for row in rows
    )


def test_browser_trace_sheds_repeated_gestures_when_delivery_stalls(browser, serve):
    url = serve(leaf_page("Trace backlog", '<h1 id="trace-target">Trace backlog</h1>'))
    page = open_page(browser, url)
    page.route("**/api/interaction", lambda route: route.fulfill(status=503))
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction") and response.status == 503
        )
    ):
        page.locator("#trace-target").click()
    page.locator("#trace-target").evaluate("""node => {
      for (let i = 0; i < 1200; i++)
        node.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true, pointerId: 1, clientX: i,
        }));
      node.click();
    }""")
    page.unroute("**/api/interaction")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "click"
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        pass

    rows = [
        json.loads(line)
        for line in (serve.page_dir / interaction_model.INTERACTIONS_FILE)
        .read_text()
        .splitlines()
    ]
    browser_rows = [row for row in rows if row.get("source") == "client"]
    assert any(row["type"] == "click" for row in browser_rows)
    assert sum(row["type"] == "pointermove" for row in browser_rows) < 512
    sequences = sorted(row["sequence"] for row in browser_rows)
    assert any(later - earlier > 1 for earlier, later in pairwise(sequences))
    consume_browser_errors(page, http_error_console(503))


def test_browser_trace_keeps_actions_ahead_of_new_repeated_observations(browser, serve):
    url = serve(leaf_page("Trace actions", '<h1 id="trace-target">Trace actions</h1>'))
    page = open_page(browser, url)
    page.route("**/api/interaction", lambda route: route.fulfill(status=503))
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction") and response.status == 503
        )
    ):
        page.locator("#trace-target").click()
    page.wait_for_timeout(100)
    page.locator("#trace-target").evaluate("""node => {
      for (let i = 0; i < 600; i++)
        node.dispatchEvent(new MouseEvent('click', {
          bubbles: true, clientX: i,
        }));
      for (let i = 0; i < 100; i++)
        node.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true, pointerId: 1, clientX: i,
        }));
    }""")
    page.unroute("**/api/interaction")
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/interaction")
            and response.ok
            and any(
                entry["type"] == "click" and entry["pointer"]["x"] == 599
                for entry in response.request.post_data_json["entries"]
            )
        )
    ):
        pass

    rows = [
        json.loads(line)
        for line in (serve.page_dir / interaction_model.INTERACTIONS_FILE)
        .read_text()
        .splitlines()
    ]
    browser_rows = [row for row in rows if row.get("source") == "client"]
    assert sum(row["type"] == "click" for row in browser_rows) == 512
    assert not any(row["type"] == "pointermove" for row in browser_rows)
    consume_browser_errors(page, http_error_console(503))


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
<button id="focused-control" type="button">Inspect continuity</button>
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
import {
  html, keeps, layerFact, LeafElement, live,
} from "/runtime/widget-api.js";

customElements.define("lf-local", class extends LeafElement {
  createRenderRoot() {
    return this.attachShadow({mode: "open"});
  }

  setup() {
    layerFact("$tones");
    keeps(this, "data-page-widget", "ready");
    const held = globalThis.__heldLocalPresentations?.get(this.id);
    if (held) this.controller.present(held);
  }

  // The gesture writes its own result into the output, which a deferral holds the
  // widget's drawing over.
  choose() {
    this.dataset.gestures = String(Number(this.dataset.gestures || 0) + 1);
    const sent = this.controller.dispatch({
      kind: "action",
      verb: "choose",
      detail: { value: "chosen" },
    });
    if (!sent) return;
    this.renderRoot.querySelector("output").value = sent.reading.state.choose.value;
    keeps(this, "data-delivery", "pending");
    sent.delivery.then(accepted => {
      keeps(this, "data-delivery", accepted ? "accepted" : "refused");
    });
  }

  render() {
    if (globalThis.__failLocalRender) {
      globalThis.__failedLocalRenders =
        Number(globalThis.__failedLocalRenders || 0) + 1;
      throw new Error("deliberate render failure");
    }
    const {state, actions} = this.reading;
    keeps(this, "data-rendered-choice", state.choose.value);
    this.dataset.readings = String(Number(this.dataset.readings || 0) + 1);
    return html`<button ?disabled=${!actions.choose.available} @click=${this.choose}>Choose</button>
      <output .value=${live(state.choose.value)}></output>`;
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
)


def test_current_readiness_releases_a_connected_page_widget(browser, serve):
    """The readiness edge includes a late module's owner and first gesture route."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page = open_page(
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
          const control = owner.shadowRoot.querySelector('button');
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
        "data-rendered-choice", "chosen"
    )
    round_trip(page)
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "accepted")
    expect(page.locator("#page-local")).to_have_attribute(
        "data-rendered-choice", "chosen"
    )


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
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(url, wait_until="load")
    page.wait_for_function(
        "() => document.querySelector('#page-local')?.dataset.startupInvalidated"
    )
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    assert held, "the positive control did not hold the first authoritative state"
    expect(page.locator("#page-local").get_by_role("button")).to_be_disabled()
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")
    waiting = page.evaluate(
        """async () => {
              const runtime = await window.__lfCheckApi();
              window.readStartupApplication = runtime.readApplication;
              window.readStartupPresentation = runtime.readApplicationPresentation;
              const application = runtime.readApplication();
              const presentation = runtime.readApplicationPresentation();
              return {
                phase: application.phase,
                epoch: application.semanticEpoch,
                presented: presentation.presentedEpoch,
                pending: presentation.pending,
                current: runtime.applicationPresented(),
              };
            }"""
    )
    assert waiting["phase"] == "waiting"
    assert waiting["presented"] == waiting["epoch"]
    assert waiting["pending"] == []
    assert waiting["current"] is True

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(page.locator("#page-local").get_by_role("button")).to_be_enabled()
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")
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


OBLIGATION_PAGE = leaf_page(
    "obligations wait for admission",
    """
<lf-ask id="release-decision"><h1>Ship this release?</h1>
  <lf-options id="release-options" choose>
    <lf-option id="release-ship">Ship it</lf-option>
    <lf-option id="release-hold">Hold it</lf-option>
  </lf-options>
</lf-ask>
""",
)


def test_versions_wait_for_a_reading_of_the_log(browser, serve):
    """An offline page that never read its log cannot say its obligations are answered.

    The first state read is refused, so presentation releases the authored page under an
    offline status with no admitted reading. Nothing then says whether the authored obligation
    still stands, and version navigation waits for the saved reading."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route("**/api/state*", refuse)
    page.goto(serve(OBLIGATION_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfPresented === '1'")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile("Lost the connection")
    )
    # Versions waits for a reading of the log too.
    versions = panel_menu(page).locator('.lf-fp-item[data-row="versions"]')
    expect(versions).to_be_disabled()


def test_admission_keeps_the_obligation_open_until_the_answer_is_in_the_log(
    browser, serve
):
    """An answer the log has not taken in leaves its obligation open.

    The pick is the user's at once — that is their own gesture drawn on their own
    widget. Which obligations still stand is the server's fold, so the count
    moves when the state this POST returns is adopted, and not before."""
    page = open_page(browser, serve(OBLIGATION_PAGE))

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#release-ship .lf-pick").click()
    holding(page, held, 1, "the answer held outside the admitted log")

    expect(page.locator("#release-ship .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    expect_obligations_answered(page, "0/1")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_obligations_answered(page, "1/1")


PAGE_DECLARATION = {
    "lf-local": {
        "description": "A page-owned local widget.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "choice": {"type": "string"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-state": {
            "choose": {
                "unit": "widget",
                "record": {"kind": "value", "attr": "choice"},
            }
        },
        "x-example": '<lf-local id="local-example" choice="idle"></lf-local>',
    }
}


def test_page_owned_registry_and_widget_use_the_captured_public_api(browser, serve):
    # The widget the test takes out and puts back stands last in the page, where neither
    # moves anything else.
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-ask id="package-ask"><h2>Package choice</h2>'
        '<lf-options id="package-options" choose>'
        '<lf-option id="package-a">A</lf-option>'
        '<lf-option id="package-b">B</lf-option>'
        "</lf-options></lf-ask>",
    ).replace("</main>", '<lf-local id="page-local" choice="idle"></lf-local></main>')
    version_url = serve(
        source,
        page_files={
            "registry.json": json.dumps(PAGE_DECLARATION),
            "widgets/lf-local.js": PAGE_WIDGET,
        },
    )

    page = open_page(browser, live_url(version_url))

    expect(page.locator("#page-local")).to_have_attribute("data-page-widget", "ready")
    expect(page.locator("#package-options .lf-pick")).to_have_count(2)
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
    holding(page, held, 1, "the resumed choose")
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
    # A verb the widget does not send throws rather than vanishing without a word.
    assert 'cannot dispatch "chose"' in page.evaluate(
        "(() => { try { pageLocal.controller.dispatch({kind: 'action', verb: 'chose'});"
        " return ''; } catch (error) { return error.message; } })()"
    )
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    round_trip(page)
    expect(page.locator("#page-local")).to_have_attribute("data-delivery", "accepted")
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    drifted = page.evaluate(
        """() => {
          pageLocal.id = 'drifted-local';
          const reading = pageLocal.controller.read();
          return {
            available: reading.actions.choose.available,
            undo: reading.actions.choose.undo.length,
          };
        }"""
    )
    assert drifted == {"available": False, "undo": 0}
    page.evaluate("pageLocal.id = 'page-local'")

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
            reading: sent.reading.state.choose.value,
            objectTarget,
            stale: controller.dispatch({
              kind: 'undo',
              target: candidate.attempt ?? candidate.id,
            }) === null,
          };
        }"""
    )
    assert stale_refused == {"reading": "idle", "objectTarget": True, "stale": True}
    holding(page, undo, 1, "the undo of the accepted choose")
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
    # Another widget's action leaves this one's reading as it was. Its return draws
    # once to restore subscriptions.
    page.evaluate("document.querySelector('main').append(pageLocal)")
    rendered(page)
    assert page.evaluate("Number(pageLocal.dataset.readings)") == readings + 1
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")


def test_a_returning_widget_repaints_to_restore_subscriptions(browser, serve):
    """A returning widget draws once to restore subscriptions, including after a
    failed render."""
    source = LIVE_V1.replace(
        "</main>", '<lf-local id="page-local" choice="idle"></lf-local></main>'
    )
    page = open_page(
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
    expect(page.locator("#page-local")).to_have_attribute("data-page-widget", "ready")
    leave_and_return = """async () => {
      const settle = () => new Promise((resolve) => setTimeout(resolve));
      const {readApplicationPresentation} =
        await window.__lfCheckApi();
      const owner = document.querySelector('#page-local');
      const parent = owner.parentNode;
      const readings = Number(owner.dataset.readings);
      owner.remove();
      await settle();
      parent.append(owner);
      await settle();
      return {
        drawn: Number(owner.dataset.readings) - readings,
        failed: Number(globalThis.__failedLocalRenders || 0),
        pending: readApplicationPresentation().pending,
      };
    }"""
    assert page.evaluate(leave_and_return) == {"drawn": 1, "failed": 0, "pending": []}

    # Resuming a deferral draws the same reading again, and this draw fails.
    page.evaluate(
        "globalThis.__failLocalRender = true; "
        "document.querySelector('#page-local').controller.defer()(); true"
    )
    expect(page.locator("#page-local .lf-error")).to_have_text(
        "<lf-local> failed: deliberate render failure"
    )
    assert page.evaluate(leave_and_return) == {"drawn": 0, "failed": 2, "pending": []}
    errors = take_browser_errors(page)
    assert [said(error) for error in errors] == [
        'leaf: <lf-local id="page-local"> failed: deliberate render failure'
    ] * 2


@pytest.mark.parametrize("lifetime", ["light", "shadow-child", "shadow-host"])
def test_widget_controller_owns_presentation_across_values_and_lifetimes(
    browser, serve, lifetime
):
    """One widget owns distinct render and preparation regions across its lifetime."""
    # The owner is removed and reattached by script below. Keep it after the page's
    # content so that neither operation moves text the reader did not ask to move.
    widget = '<lf-local id="page-local" choice="idle"></lf-local>'
    declarations = PAGE_DECLARATION
    modules = {"widgets/lf-local.js": PAGE_WIDGET}
    if lifetime != "light":
        widget = (
            f'<lf-controller-stage id="controller-stage">{widget}</lf-controller-stage>'
        )
        declarations = {
            **declarations,
            "lf-controller-stage": {
                "description": "A declared shadow stage for the controller lifetime.",
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "markup",
                "x-upgrade": True,
                "x-shadow": True,
                "x-example": '<lf-controller-stage id="stage-example"><p id="stage-words">Words</p></lf-controller-stage>',
            },
        }
        modules["widgets/lf-controller-stage.js"] = """\
import { once, shadowStage } from '/runtime/widget-api.js';
customElements.define('lf-controller-stage', class extends HTMLElement {
  connectedCallback() { if (once(this)) shadowStage(this, [...this.children]); }
});
"""
    source = LIVE_V1.replace(
        "</main>",
        f"{widget}</main>",
    )
    page = open_page(
        browser,
        live_url(
            serve(
                source,
                page_files={
                    "registry.json": json.dumps(declarations),
                    **modules,
                },
            )
        ),
    )
    page.locator("#page-local").evaluate("node => { window.pageLocal = node; }")
    page.evaluate(
        """async () => {
          const presentation = await window.__lfCheckApi();
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
    page.wait_for_function("preparationReady")

    # Deferral installs a held render ticket for each selected value. Refusal publishes
    # the newest authoritative value, but neither it nor the older optimistic ticket may
    # count as presented until the one-shot resume paints that newest reading.
    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    before = int(page.locator("#page-local").get_attribute("data-readings"))
    page.evaluate("() => { window.resumeLocal = pageLocal.controller.defer(); }")
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    assert page.evaluate("Number(pageLocal.dataset.readings)") == before
    page.wait_for_function(
        "readLeafPresentation().pending.join() === 'widget:page-local:render'"
    )
    holding(page, held_events, 1, "the deferred choose")
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
        "entry => entry.event.attempt === attempt && entry.state === 'refused')",
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
    rendered(page)  # A deferred local edit does not hold mechanical rendering.
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
    page.wait_for_function("presentationReady")
    page.unroute("**/api/event")

    # A removed owner pauses its one retained subscription and retires both regions.
    # Releasing a local edit after removal must not paint that detached owner.
    # Reconnecting the same instance catches up once and reattaches
    # its still-pending preparation at the same semantic epoch, so an already resolved
    # readiness call cannot be reused as proof for the replacement renderer.
    # Leave the widget by a real gesture before probing its lifetime: removing a
    # focused control would also change shortcut context without user input.
    page.locator("#live-title").click()
    rendered(page)
    page.evaluate(
        """lifetime => {
          window.localLifetimeOwner = lifetime === 'shadow-host'
            ? document.querySelector('#controller-stage') : pageLocal;
          window.localLifetimeParent = localLifetimeOwner.parentNode;
        }""",
        lifetime,
    )
    page.evaluate(
        """() => {
          window.beforeDetachedReading = Number(pageLocal.dataset.readings);
          window.resumeDetached = pageLocal.controller.defer();
          window.reconnectPreparation = heldPreparation();
          pageLocal.controller.present(reconnectPreparation.promise);
          window.beforeRemovalReady = false;
          whenLeafPresented().then(() => { beforeRemovalReady = true; });
          localLifetimeOwner.remove();
          resumeDetached();
        }"""
    )
    page.wait_for_function("beforeRemovalReady")
    rendered(
        page
    )  # A removed owner's unresolved preparation no longer holds rendering.
    assert page.evaluate("Number(pageLocal.dataset.readings)") == page.evaluate(
        "beforeDetachedReading"
    )
    assert page.evaluate("readLeafPresentation().pending") == []
    detached_edit = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "page-local",
            "action": "choose",
            "detail": {"value": "chosen"},
        },
    )
    told(page)
    assert page.evaluate("Number(pageLocal.dataset.readings)") == page.evaluate(
        "beforeDetachedReading"
    )
    assert page.evaluate("pageLocal.dataset.renderedChoice") == "idle"
    page.evaluate(
        """() => {
          localLifetimeParent.append(localLifetimeOwner);
          window.reconnectedReady = false;
          whenLeafPresented().then(() => { reconnectedReady = true; });
          return true;
        }"""
    )
    assert page.evaluate("reconnectedReady") is False
    assert (
        page.evaluate(
            "Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
        )
        is False
    )
    assert page.evaluate("Number(pageLocal.dataset.readings)") == page.evaluate(
        "beforeDetachedReading + 1"
    )
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    assert page.evaluate("readLeafPresentation().pending") == [
        "widget:page-local:preparation"
    ]
    page.evaluate("reconnectPreparation.release('reconnected')")
    page.wait_for_function("reconnectedReady")
    append_command(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": detached_edit["id"]},
    )
    told(page)
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("idle")

    # A synchronous render failure cannot escape the publisher or leave a partial
    # widget as presentation proof. The widget reports it once, shows the visible
    # fail-soft box, and settles its region.
    held_failure = []
    page.route("**/api/event", lambda route: held_failure.append(route))
    page.evaluate("window.__failLocalRender = true; true")
    page.locator("#page-local").get_by_role("button", name="Choose").click()
    holding(page, held_failure, 1, "the failing render's action")
    expect(page.locator("#page-local .lf-error")).to_have_text(
        "<lf-local> failed: deliberate render failure"
    )
    page.wait_for_function("readLeafPresentation().pending.length === 0")
    assert page.evaluate("window.__failedLocalRenders") == 1
    errors = take_browser_errors(page)
    assert [said(error) for error in errors] == [
        'leaf: <lf-local id="page-local"> failed: deliberate render failure'
    ]


@pytest.mark.parametrize(
    "mode", ["siblings", "superseded", "reconnected", "registered-detached"]
)
def test_preparation_waits_for_all_capable_work(browser, serve, mode):
    """Failures and reconnects retain every producer that can still commit DOM."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Preparation",
                '<h1>Preparation</h1><lf-local id="page-local" choice="idle"></lf-local>',
            ),
            page_files={
                "registry.json": json.dumps(PAGE_DECLARATION),
                "widgets/lf-local.js": PAGE_WIDGET,
            },
        ),
    )
    page.locator("#page-local").evaluate("""owner => {
      window.preparationOwner = owner;
      window.preparationParent = owner.parentNode;
    }""")
    if mode == "registered-detached":
        page.evaluate("preparationOwner.remove()")
    page.evaluate("""() => {
      const owner = preparationOwner;
      const first = new Promise((done, fail) => {
        window.finishPreparation = done;
        window.rejectPreparation = fail;
      });
      owner.controller.present(first.then(() => { owner.dataset.late = 'committed'; }));
    }""")
    if mode == "registered-detached":
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "page-local",
                "action": "choose",
                "detail": {"value": "chosen"},
            },
        )
        told(page)
    elif mode != "siblings":
        page.get_by_role("button", name="Choose", exact=True).click()
        expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    page.evaluate("""() => {
      const owner = preparationOwner;
      const second = new Promise(done => { window.releaseSibling = done; });
      owner.controller.present(second);
    }""")
    if mode in {"reconnected", "registered-detached"}:
        if mode == "reconnected":
            page.get_by_role("heading", name="Preparation", exact=True).click()
            page.evaluate("preparationOwner.remove()")
        rendered(page)
        page.evaluate("preparationParent.append(preparationOwner)")
    if mode != "siblings":
        page.evaluate("releaseSibling()")
    else:
        page.evaluate("rejectPreparation(new Error('deliberate preparation failure'))")
        expect(page.locator("#page-local .lf-error")).to_contain_text(
            "deliberate preparation failure"
        )
    one_frame(page)
    assert not page.evaluate(
        "Object.values(document.querySelector('script[data-lf-entry]').lfRenderingState()).every(Boolean)"
    )
    if mode in {"reconnected", "registered-detached"}:
        page.evaluate("finishPreparation()")
        rendered(page)
        expect(page.locator("#page-local")).to_have_attribute("data-late", "committed")
        return
    if mode == "superseded":
        page.evaluate("rejectPreparation(new Error('deliberate preparation failure'))")
    expect(page.locator("#page-local .lf-error")).to_contain_text(
        "deliberate preparation failure"
    )
    errors = take_browser_errors(page)
    assert errors and all(
        is_problem(error, "deliberate preparation failure") for error in errors
    )
    page.evaluate("releaseSibling()")
    rendered(page)


def long_thread(page_dir, thread_id, text):
    """A thread whose turns already fill the panel's thread view to its cap, ending on
    the user's, so the answer the user waits for is drawn below the fold rather than
    growing the view."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": thread_id,
            "author": "user",
            "revision": 1,
            "text": text,
        },
    )
    for turn in range(6):
        for author in ("agent", "user"):
            append_carried_log_record(
                page_dir,
                {
                    "kind": "reply",
                    "author": author,
                    "revision": 1,
                    "parent": thread_id,
                    "text": f"Turn {turn} from the {author}. " * 6,
                },
            )


def arrived(page, thread_id):
    """Wait until the page's thread reading holds `thread_id`, and return it. A page
    whose presentation is held can't be `told`, which waits for it."""
    page.evaluate(
        "async () => { window.__lfThreadsApi = await window.__lfWidgetApi(); }"
    )
    page.wait_for_function(
        "id => window.__lfThreadsApi.readThreads().threads.some((t) => t.id === id)",
        arg=thread_id,
    )
    return thread_id


def test_thread_presentation_waits_for_its_frozen_widgets_only(browser, serve):
    """The thread parent absorbs descendants without joining unrelated page work."""
    source = LIVE_V1.replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live first</h1>'
        '<lf-local id="page-local" choice="idle"></lf-local>',
    )
    page = open_page(
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
          const presentation = await window.__lfCheckApi();
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

    long_thread(serve.page_dir, "frozen-widget-question", "Show the frozen widget.")
    # The panel's thread view is the reader that draws the reply's widget.
    open_panel_thread(page, arrived(page, "frozen-widget-question"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "frozen-widget-question",
            "text": "This widget prepares inside the thread.",
            "markup": '<lf-local id="thread-local" choice="idle"></lf-local>',
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "thread-local",
            "action": "choose",
            "detail": {"value": "chosen"},
        },
    )
    page.wait_for_function(
        """() => {
          const pending = readLeafPresentation().pending;
          return document.querySelector('.lf-floating-panel #thread-local') &&
            pending.includes('thread') &&
            pending.includes('widget:thread-local:preparation') &&
            pending.includes('widget:page-local:preparation');
        }""",
    )
    page.evaluate(
        "threadReady = false; allReady = false; "
        "whenLeafRegionsPresented(['thread'], () => true)"
        ".then(() => { threadReady = true; }); "
        "whenLeafPresented().then(() => { allReady = true; }); true"
    )
    assert page.evaluate("threadReady") is False
    page.evaluate("threadPreparation.release('thread')")
    page.wait_for_function("threadReady")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")
    expect(page.locator(".lf-floating-panel #thread-local")).to_have_attribute(
        "data-rendered-choice", "chosen"
    )
    assert page.evaluate("allReady") is False
    assert "widget:page-local:preparation" in page.evaluate(
        "readLeafPresentation().pending"
    )
    page.evaluate("pagePreparation.release('page')")
    page.wait_for_function("allReady")

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
    long_thread(
        serve.page_dir, "failing-widget-question", "Show another frozen widget."
    )
    open_panel_thread(page, arrived(page, "failing-widget-question"))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "failing-widget-question",
            "text": "This widget fails its preparation.",
            "markup": '<lf-local id="thread-failing" choice="idle"></lf-local>',
        },
    )
    page.wait_for_function(
        """() => document.querySelector('.lf-floating-panel #thread-failing') &&
          readLeafPresentation().pending.includes('thread') &&
          readLeafPresentation().pending.includes(
            'widget:thread-failing:preparation'
          )""",
    )
    expect_open_threads(page, 2)
    page.evaluate(
        "threadReady = false; "
        "whenLeafRegionsPresented(['thread'], () => true)"
        ".then(() => { threadReady = true; }); "
        "failedThreadPreparation.reject(new Error('frozen descendant failure')); true"
    )
    page.wait_for_function("threadReady")
    expect(page.locator(".lf-floating-panel #thread-failing")).to_have_count(1)
    expect_open_threads(page, 2)
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: frozen descendant failure"
    ]


THREAD_ACTIONS = r"""
import {LeafElement, noChange, keeps, readThreads, threadActions} from '/runtime/widget-api.js';
customElements.define('lf-thread-actions', class extends LeafElement {
  setup() {
    this.innerHTML = '<input aria-label="Package reply"><button>Reply</button>' +
      '<button>Resolve</button><button>Reopen</button><button>React</button>';
    this.querySelectorAll('button').forEach(button => button.onclick = () => {
      const key = this.thread.key;
      const agent = this.thread.msgs.find(message => message.author === 'agent');
      this.last = button.textContent === 'Reply'
        ? threadActions.reply(key, this.querySelector('input').value)
        : button.textContent === 'Resolve'
          ? threadActions.resolve(key)
          : button.textContent === 'Reopen'
            ? threadActions.reopen(key)
            : threadActions.setReaction(key, agent.key, 'keep', !agent.reactions.choices.find(choice => choice.name === 'keep').inForce);
      keeps(this, 'data-accepted', this.last !== null);
    });
  }
  render() {
    this.thread = readThreads().threads[0];
    keeps(this, 'data-resolved', Boolean(this.thread?.resolved));
    keeps(this, 'data-reacted', Boolean(this.thread?.msgs.find(msg => msg.author === 'agent')?.reactions?.choices.find(choice => choice.name === 'keep')?.inForce));
    return noChange;
  }
});
"""

THREAD_ACTIONS_DECLARATION = {
    "description": "A package's own Thread action controls.",
    "type": "object",
    "properties": {"id": {"type": "string"}},
    "required": ["id"],
    "additionalProperties": False,
    "x-content": "empty",
    "x-upgrade": True,
    "x-example": '<lf-thread-actions id="actions-example"></lf-thread-actions>',
}


@pytest.mark.parametrize("surface", ["margin", "outlet"])
def test_compact_reader_draws_the_native_interactive_message(browser, serve, surface):
    """A thread the page draws holds its message's widgets, where the user answers them."""
    target = "jobs" if surface == "outlet" else "notes"
    source = (
        SEATED_OBLIGATION_PAGE
        if surface == "outlet"
        else leaf_page("Native reply", '<h1>Native reply</h1><p id="notes">Notes</p>')
    )
    url = serve(source)
    for event in [
        {
            "id": "native-thread",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which channel?",
            "anchor": {"section": target},
        },
        {
            "id": "native-message",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "native-thread",
            "text": "Choose a channel.",
            "markup": '<lf-options id="native-channel" choose><lf-option id="native-email">Email</lf-option></lf-options>',
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    if surface == "margin":
        page.get_by_role("button", name=re.compile("Thread, Your turn")).first.click()
        compact = page.locator(".lf-margin-thread")
    else:
        compact = page.locator('#jobs .lf-page-thread[data-thread="native-thread"]')
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    email = compact.locator('.lf-msg[data-message="native-message"] #native-email')
    expect(email).to_be_visible()
    with sending(page, "answer the native interactive reply"):
        email.click()
    expect(email.get_by_role("checkbox")).to_be_checked()


@pytest.mark.parametrize("owner", ["root", "middle"])
def test_frozen_obligation_reveals_its_exact_message_in_a_selective_primary(
    browser, serve, owner
):
    """A message-only primary materializes the widget's turn, including later replies."""
    module = """
    import {registerThreadPresentation, threadTurns} from '/runtime/widget-api.js';
    customElements.define('lf-message-reader', class extends HTMLElement {
      connectedCallback() {
        this.outlet = document.createElement('section');
        this.append(this.outlet);
        this.presentation = registerThreadPresentation(this, {
          render: (collection, parts) => {
            const thread = collection.threads[0];
            if (!thread) return;
            const message = threadTurns(thread).find(message =>
              message.key === (this.message ?? thread.root.key));
            parts.message(thread.key, message.key, this.outlet);
          },
          reveal: (key, request) => { this.message = request.message; },
        });
      }
      disconnectedCallback() { this.presentation.unregister(); }
    });
    """
    url = serve(
        leaf_page(
            "Selective message reader",
            '<h1>Selective message reader</h1><lf-message-reader id="reader"></lf-message-reader>',
        ),
        layer_registry={
            "lf-message-reader": {
                **THREAD_READER_DECLARATION,
                "x-example": '<lf-message-reader id="reader-example"></lf-message-reader>',
            }
        },
        layer_widgets={"lf-message-reader.js": module},
    )
    for message in ["root", "middle", "last"]:
        event = {
            "id": message,
            "attempt": f"key-{message}",
            "kind": "comment" if message == "root" else "reply",
            "author": "agent",
            "revision": 1,
            "text": f"The {message} turn.",
            **({"parent": "root"} if message != "root" else {}),
        }
        if message == owner:
            event["markup"] = (
                '<lf-options id="channel" choose>'
                '<lf-option id="email">Email</lf-option></lf-options>'
            )
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    reader = page.locator("#reader")
    expect(reader.locator('.lf-msg[data-event="root"]')).to_be_visible()
    if owner == "middle":
        expect(reader.locator("#channel")).to_have_count(0)
    assert page.evaluate("""async () => {
      const api = await window.__lfWidgetApi();
      return await api.obligationActions.open('widget:channel');
    }""")
    assert reader.evaluate("node => node.message") == f"key-{owner}"
    expect(reader.locator(f'.lf-msg[data-event="{owner}"]')).to_be_visible()
    email = reader.locator("#email")
    expect(email).to_be_in_viewport()
    with sending(page, "answer the ask in its addressed native turn"):
        email.click()
    expect(email.get_by_role("checkbox")).to_be_checked()


def package_workspace(serve, *, before_reader="", primary=True):
    """Run the shipped package example against real event admission."""
    from render_harness import ROOT

    companion = ROOT / "examples/developer/feature-gallery.page"
    url = serve(
        leaf_page(
            "Package reader",
            '<h1>Package reader</h1><p id="notes">Announcement notes</p>'
            + before_reader
            + (
                '<lf-conversation-workspace id="workspace"></lf-conversation-workspace>'
                if primary
                else ""
            ),
        ),
        layer_registry={
            "lf-conversation-workspace": json.loads(
                (companion / "registry.json").read_text()
            )["lf-conversation-workspace"]
        },
        layer_widgets={
            "lf-conversation-workspace.js": (
                companion / "widgets/lf-conversation-workspace.js"
            ).read_text()
        },
    )
    for event in [
        {
            "id": "channel-question",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which channel?",
            "markup": '<lf-ask id="channel-ask"><h3>Channel</h3><lf-options id="channel-options" choose><lf-option id="email">Email</lf-option><lf-option id="chat">Chat</lf-option></lf-options></lf-ask>',
        },
        {
            "id": "opening",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep it concise.",
        },
        {
            "id": "answer",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "opening",
            "text": "One paragraph.",
        },
        {
            "id": "proofread",
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "proofread",
            "owner": "user",
            "subject": {"kind": "element", "id": "notes"},
            "title": "Proofread announcement",
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    return url


def test_package_answer_summary_waits_for_widget_completion(browser, serve):
    """A selected value remains partial until the multiple-choice obligation is done."""
    url = package_workspace(serve)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "partial-question",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which extras?",
            "markup": '<lf-options id="extras" choose multiple><lf-option id="extra-chat" chosen>Chat</lf-option></lf-options>',
        },
    )
    page = open_page(browser, url)
    workspace = page.locator("#workspace")
    counts = workspace.locator(".counts")
    workspace.get_by_role("button", name="Which extras? Chat", exact=True).click()
    expect(workspace.locator("#extra-chat").get_by_role("checkbox")).to_be_checked()
    expect(counts).to_have_text("3 waiting on me")
    with sending(page, "complete the selected extras"):
        workspace.locator("#extras").get_by_role(
            "button", name="Done: these picks are complete", exact=True
        ).click()
    expect(counts).to_have_text("2 waiting on me · 1 answered · Chat")


def test_public_queue_commands_recheck_membership_and_restore_refusals(browser, serve):
    page = open_page(browser, package_workspace(serve))
    page.evaluate("async () => { window.api = await window.__lfWidgetApi(); }")
    key = page.evaluate(
        "api.queueItemKey(api.readQueues().on_user.find(item => item.id === 'proofread'))"
    )
    assert page.evaluate(
        "api.queueActions.done(api.queueItemKey(api.readQueues().on_user.find(item => item.obligation?.source.kind === 'widget'))) === null"
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.evaluate("key => { window.doneDelivery = api.queueActions.done(key); }", key)
    holding(page, held, 1, "a package Done awaiting admission")
    assert page.evaluate(
        "!api.readQueues().on_user.some(item => item.id === 'proofread')"
    )
    assert page.evaluate("api.readQueues().done.some(item => item.id === 'proofread')")
    assert page.evaluate("key => api.queueActions.done(key) === null", key)
    held[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "ok": False,
                "final": True,
                "attempt": held[0].request.post_data_json["attempt"],
                "error": "Deliberate refusal",
            }
        ),
    )
    page.unroute("**/api/event")
    assert page.evaluate("doneDelivery") is None
    round_trip(page)
    assert page.evaluate(
        "api.readQueues().on_user.some(item => item.id === 'proofread')"
    )
    with sending(page, "a current package Done"):
        page.locator("#workspace").get_by_role(
            "button", name="Done", exact=True
        ).click()
    assert page.evaluate("key => api.queueActions.done(key) === null", key)
    assert page.evaluate("key => api.queueActions.open(key)", key)
    expect(page.locator("#notes")).to_be_focused()
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("todo") == "proofread"
    ] == ["todo_end"]


def test_failed_primary_reader_restores_the_same_native_obligation_in_core(
    browser, serve
):
    page = open_page(browser, package_workspace(serve))
    expect(page.locator("#workspace lf-option#email")).to_be_visible()
    page.evaluate("""() => {
      const workspace = document.querySelector('#workspace');
      window.nativeOption = workspace.querySelector('#email');
      const render = workspace.present.bind(workspace);
      workspace.present = (...args) => {
        workspace.present = render;
        throw new Error('Deliberate primary failure');
      };
      window.failedRender = workspace.presentation.update().then(() => false, () => true);
    }""")
    assert page.evaluate("failedRender")
    consume_browser_errors(
        page, "leaf: Presentation failed: Deliberate primary failure"
    )
    # The failed reader gives its place back to Leaf's own, so the floating panel opens
    # the thread, the same native Ask in it, where the package's reader would have.
    page.wait_for_function(
        "() => !document.querySelector('#workspace').presentation.primary"
    )
    panel_control(page, "queue").click()
    page.locator(f'{PANEL} [data-obligation="widget:channel-options"]').get_by_role(
        "button", name="Show", exact=True
    ).click()
    panel_settled(page, view="thread")
    in_panel = page.locator(PANEL_THREAD).locator("lf-option#email")
    expect(in_panel).to_be_visible()
    assert in_panel.evaluate("node => node === nativeOption")
    # Drawing again, the package's reader takes the place, and the thread, back. The
    # user has put the panel's view away first: a redraw is news, which may not carry
    # what they are reading out of the panel into the page.
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    # Chrome reports no shift within 500ms of input, so the redraw lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    page.evaluate("document.querySelector('#workspace').presentation.update()")
    email = page.locator("lf-option#email")
    expect(email).to_be_visible()
    assert email.evaluate("node => node === nativeOption")
    with sending(page, "answer the restored native obligation"):
        email.click()
    expect(page.locator("#workspace .counts")).to_contain_text("Email")


def test_queue_obligation_arrival_selects_the_primary_reader(browser, serve):
    page = open_page(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    page.evaluate("async () => { window.api = await window.__lfWidgetApi(); }")
    assert page.evaluate(
        "async () => { const item = api.readQueues().on_user.find(item => item.obligation?.source.kind === 'widget'); return await api.queueActions.open(api.queueItemKey(item)); }"
    )
    expect(workspace.locator("lf-option#email")).to_be_visible()
    assert page.evaluate(
        "document.querySelector('#workspace').contains(document.querySelector('#email'))"
    )
    # The primary reader takes the Ask; the panel opens no view of its thread.
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_cancelled_primary_travel_adds_no_return_checkpoint(browser, serve):
    """A newer Tab keeps its focus and history while a primary layout completes, and
    superseding a navigation completes its promise even when a renderer is blocked."""
    page = open_page(browser, package_workspace(serve))
    entries = page.evaluate("history.length")
    page.evaluate("""async () => {
      const api = await window.__lfWidgetApi();
      const workspace = document.querySelector('#workspace');
      const present = workspace.present.bind(workspace);
      const reached = Promise.withResolvers();
      const blocked = Promise.withResolvers();
      workspace.present = (...args) => {
        workspace.present = present;
        reached.resolve();
        return blocked.promise.then(() => present(...args));
      };
      window.releasePrimaryLayout = blocked.resolve;
      window.cancelledPrimaryTravel = api.threadActions.open('opening', {part:'reply'});
      await reached.promise;
    }""")
    page.keyboard.press("Tab")
    page.evaluate("""() => {
      let active = document.activeElement;
      while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
      window.newerTabTarget = active;
    }""")
    assert page.evaluate("""async () => {
      releasePrimaryLayout();
      return await cancelledPrimaryTravel === null;
    }""")
    assert page.evaluate("history.length") == entries
    assert page.evaluate("""() => {
      let active = document.activeElement;
      while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
      return active === newerTabTarget;
    }""")


@pytest.mark.parametrize("edit_again", [False, True])
def test_package_creation_refusal_preserves_the_current_draft(
    browser, serve, edit_again
):
    page = open_page(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    input = workspace.get_by_role("textbox", name="New conversation")
    input.fill("Refused conversation")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    workspace.get_by_role("button", name="Start conversation").click()
    holding(page, held, 1, "a package creation awaiting admission")
    expect(input).to_have_value("")
    if edit_again:
        input.fill("A later draft")
    held[0].fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(
            {
                "ok": False,
                "final": True,
                "attempt": held[0].request.post_data_json["attempt"],
                "error": "Deliberate creation refusal",
            }
        ),
    )
    page.unroute("**/api/event")
    expect(input).to_have_value(
        "A later draft" if edit_again else "Refused conversation"
    )


def test_keyed_shadow_row_restores_replaced_slotted_editor_and_caret(browser, serve):
    """A keyed row hands the user's draft to its replacement through a native slot."""
    url = serve(
        leaf_page(
            "Keyed slotted editor",
            '<h1>Keyed slotted editor</h1><lf-keyed-slot-list id="list"></lf-keyed-slot-list>',
        ),
        layer_registry={
            "lf-keyed-slot-list": {
                "description": "A keyed shadow row with a native slotted editor.",
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "empty",
                "x-shadow": True,
                "x-upgrade": True,
            }
        },
        layer_widgets={
            "lf-keyed-slot-list.js": """
            import {holdFocus, shadowStage} from '/runtime/widget-api.js';
            customElements.define('lf-keyed-slot-list', class extends HTMLElement {
              connectedCallback() {
                this.scope = document.createElement('section');
                this.row = document.createElement('div');
                this.row.dataset.row = 'draft';
                const slot = document.createElement('slot');
                slot.name = 'editor';
                this.row.append(slot);
                this.scope.append(this.row);
                this.editor = document.createElement('input');
                this.editor.slot = 'editor';
                this.editor.setAttribute('aria-label', 'Draft');
                this.append(this.editor);
                shadowStage(this, [this.scope]);
              }
              replaceEditor() {
                const restore = holdFocus(this.scope, {key: 'data-row'});
                const row = this.row.cloneNode(true);
                const editor = this.editor.cloneNode(true);
                row.dataset.revision = '2';
                editor.placeholder = 'Updated draft';
                editor.value = this.editor.value;
                this.row.replaceWith(row);
                this.editor.replaceWith(editor);
                this.row = row;
                this.editor = editor;
                return restore();
              }
            });
            """
        },
    )
    page = open_page(browser, url)
    editor = page.get_by_role("textbox", name="Draft", exact=True)
    editor.fill("half a thought")
    editor.evaluate("node => node.setSelectionRange(4, 9, 'backward')")
    assert editor.evaluate("node => node.assignedSlot !== null")
    assert page.evaluate("document.querySelector('#list').replaceEditor()")
    expect(editor).to_be_focused()
    expect(editor).to_have_value("half a thought")
    assert editor.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [4, 9, "backward"]


@pytest.mark.parametrize("while_pending", ["stay", "choose-earlier"])
def test_packages_and_panel_share_threads_through_gestures_and_authored_content(
    browser, serve, while_pending
):
    """One public reading carries both optimistic turns and live authored unit state."""
    url = serve(
        leaf_page(
            "Shared Threads",
            '<h1>Shared Threads</h1><lf-thread-reader id="reader"></lf-thread-reader>',
        ),
        layer_registry={"lf-thread-reader": THREAD_READER_DECLARATION},
        layer_widgets={"lf-thread-reader.js": THREAD_READER},
    )
    for event in [
        {
            "id": "question",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "**Decision**",
        },
        {
            "id": "answer",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "question",
            "text": "Choose a direction.",
            "markup": '<lf-options id="direction" choose><lf-option id="north">North</lf-option><lf-option id="south">South</lf-option></lf-options>',
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    reader = page.locator("#reader")
    expect(reader).to_contain_text("Decision")
    record = reader.evaluate("""node => {
      const reading = node.collection;
      const cloned = structuredClone(reading);
      const allFrozen = value => !value || typeof value !== 'object' ||
        (Object.isFrozen(value) && Object.values(value).every(allFrozen));
      return {reading: cloned, frozen: allFrozen(reading), same: node.sameReading, topic: node.topic};
    }""")
    assert record["frozen"] and record["same"]
    assert record["topic"] == "Decision"
    root, reply = record["reading"]["threads"][0]["msgs"]
    assert root["text"] == "**Decision**" and root["body"]["text"].strip() == "Decision"
    assert reply["body"]["document"] == {"thread": "question", "message": "answer"}
    assert reply["body"]["kind"] == "authored"
    assert "North" in reply["body"]["text"]
    assert '"markup"' not in json.dumps(record) and '"html"' not in json.dumps(record)
    open_threads(page)
    # The agent answered without naming the thread, so it reads its opening words.
    expect(page.locator(".lf-fp-thread")).to_contain_text("Decision")
    open_panel_thread(page, "question")
    expect(page.locator("#direction")).to_have_count(1)
    message_top = page.locator("#direction").evaluate(
        "node => node.getBoundingClientRect().top"
    )
    with sending(page, "choose North in the authored reply"):
        page.locator("#north .lf-pick").click()
    round_trip(page)
    assert (
        page.locator("#direction").evaluate("node => node.getBoundingClientRect().top")
        == message_top
    )
    assert reader.evaluate("""node => node.collection.threads[0].msgs[1].body.units
      .find(unit => unit.id === 'direction').state.choose.value""") == ["north"]

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    box = page_comment(page)
    send = page.locator(".lf-fp-field .lf-compose-submit")
    write(box, "Pending **words**")
    send.click()
    holding(page, held, 1, "the shared collection's pending root")
    expect(reader).to_contain_text("Pending words")
    pending = reader.evaluate(
        "node => node.collection.threads.find(thread => thread.root.pending)"
    )
    # The send opens the pending thread's view in the panel.
    expect(page.locator(PANEL_THREAD)).to_contain_text("Pending words")
    held.pop().continue_()
    round_trip(page)
    admitted = reader.evaluate(
        "(node, key) => node.collection.threads.find(thread => thread.key === key)",
        pending["key"],
    )
    assert admitted["id"] != pending["id"]
    assert admitted["root"]["key"] == pending["root"]["key"]
    selected = page.locator(f'{PANEL_THREAD}[data-thread="{admitted["id"]}"]')
    expect(selected).to_be_visible()

    box = page_comment(page)
    write(box, "Refused words")
    send.click()
    holding(page, held, 1, "the shared collection's refused root")
    expect(reader).to_contain_text("Refused words")
    expect(page.locator(PANEL_THREAD)).to_contain_text("Refused words")
    if while_pending == "choose-earlier":
        # Refusal restores the earlier selection only while the provisional root
        # still owns it; a later user choice must remain the selected conversation.
        selected = open_panel_thread(page, "question")
    # Chrome reports no shift within 500ms of input, so the refusal lands after it:
    # taking back the view the send opened moves nothing the pointer was not near.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    route = held.pop()
    route.fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": route.request.post_data_json["attempt"],
            "error": "refused before append",
            "final": True,
        },
    )
    round_trip(page)
    consume_browser_errors(page, http_error_console(400))
    expect(reader).not_to_contain_text("Refused words")
    assert stored_draft_text(page, "general") == "Refused words"
    if while_pending == "choose-earlier":
        # The field takes no keys from a user who has moved on: the thread they chose
        # stays open in it, and the words wait in the page comment.
        expect(box).to_have_count(0)
        expect(selected).to_be_visible()
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
        expect(box).to_have_js_property("value", "Refused words")
    else:
        # Where the send left the user, the field returns to the refused words.
        expect(box).to_be_focused()
        expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    expect(page.locator('[data-thread^="pending:"]')).to_have_count(0)
    page.unroute("**/api/event")


def test_package_thread_widgets_keep_local_filters_and_independent_subscriptions(
    browser, serve
):
    """Two widget instances observe one Thread collection and route through core."""
    url = serve(
        leaf_page(
            "Thread widget instances",
            "<h1>Thread widget instances</h1>"
            '<lf-thread-filter id="first" filter="Alpine"></lf-thread-filter>'
            '<lf-thread-filter id="second" filter="Bay"></lf-thread-filter>',
        ),
        layer_registry={"lf-thread-filter": THREAD_FILTER_DECLARATION},
        layer_widgets={"lf-thread-filter.js": THREAD_FILTER},
    )
    for thread_id, words in [("alpine", "Alpine"), ("bay", "Bay")]:
        append_carried_log_record(
            serve.page_dir,
            {
                "id": thread_id,
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": words,
            },
        )
    page = open_page(browser, url)
    first = page.locator("#first")
    second = page.locator("#second")
    expect(first.locator("li")).to_have_text("Alpine")
    expect(second.locator("li")).to_have_text("Bay")
    assert first.evaluate("node => node.sameReading")
    assert second.evaluate("node => node.sameReading")

    second.locator("input").fill("Cedar")
    before = [widget.evaluate("node => node.updates") for widget in (first, second)]
    with sending(page, "a Thread visible to both package widgets"):
        write(page_comment(page), "Cedar")
        page.locator(".lf-fp-field .lf-compose-submit").click()
    expect(second.locator("li")).to_have_text("Cedar")
    expect(first.locator("li")).to_have_text("Alpine")
    for widget, count in zip((first, second), before):
        assert widget.evaluate("node => node.updates") > count
        assert widget.evaluate(
            "node => node.collection.threads.some(thread => thread.root.body.text.trim() === 'Cedar')"
        )

    # Clear the user's filter before this lifecycle test removes its widget.
    second.locator("input").fill("")
    # The widget taken out stands last, so taking it out moves nothing else.
    removed = second.element_handle()
    second.evaluate("node => node.remove()")
    stopped_at = removed.evaluate("node => node.updates")
    first.locator("input").fill("Delta")
    first_before = first.evaluate("node => node.updates")
    with sending(page, "another Thread after one widget disconnected"):
        write(page_comment(page), "Delta")
        page.locator(".lf-fp-field .lf-compose-submit").click()
    expect(first.locator("li")).to_have_text("Delta")
    assert first.evaluate("node => node.updates") > first_before
    assert removed.evaluate("node => node.updates") == stopped_at

    thread_id = first.evaluate(
        "node => node.collection.threads.find(thread => thread.root.body.text.trim() === 'Delta').id"
    )
    # The widget's route through core opens the thread's view in the panel.
    first.locator("button", has_text="Delta").click()
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{thread_id}"]')).to_be_visible()


def test_package_thread_actions_share_core_admission_and_current_availability(
    browser, serve
):
    """Package controls use the core reply, settlement, reaction and undo paths."""
    url = serve(
        leaf_page(
            "Thread actions",
            '<h1>Thread actions</h1><lf-thread-actions id="actions"></lf-thread-actions>',
        ),
        layer_registry={"lf-thread-actions": THREAD_ACTIONS_DECLARATION},
        layer_widgets={"lf-thread-actions.js": THREAD_ACTIONS},
    )
    for event in [
        {
            "id": "thread-action-root",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Choose an approach.",
        },
        {
            "id": "thread-action-agent",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "thread-action-root",
            "text": "I propose one.",
        },
    ]:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    actions = page.locator("#actions")
    expect(actions).to_have_attribute("data-resolved", "false")
    actions.get_by_role("textbox", name="Package reply").fill("Package answer")
    with sending(page, "a package reply"):
        actions.get_by_role("button", name="Reply").click()
    assert (
        events_model.read_events(serve.page_dir)[-1]["parent"] == "thread-action-root"
    )
    view = open_panel_thread(page, "thread-action-root")
    expect(view).to_contain_text("Package answer")

    with sending(page, "a package resolution"):
        actions.get_by_role("button", name="Resolve").click()
    expect(actions).to_have_attribute("data-resolved", "true")
    with sending(page, "a package reply that reopens the thread"):
        actions.get_by_role("button", name="Reply").click()
    expect(actions).to_have_attribute("data-accepted", "true")
    expect(actions).to_have_attribute("data-resolved", "false")

    with sending(page, "a package reaction"):
        actions.get_by_role("button", name="React").click()
    expect(actions).to_have_attribute("data-reacted", "true")
    assert actions.evaluate("""node => {
      const thread = node.thread;
      const agent = thread.msgs.find(message => message.author === 'agent');
      const choice = agent.reactions.choices.find(choice => choice.name === 'keep');
      return thread.offers.reply && thread.offers.resolve && !thread.offers.reopen &&
        choice.inForce && choice.glyph && choice.label && Object.isFrozen(choice);
    }""")
    assert page.evaluate("""async () => {
      const {threadActions,readThreads} = await window.__lfWidgetApi();
      const thread = readThreads().threads[0];
      const agent = thread.msgs.find(message => message.author === 'agent');
      return threadActions.setReaction(thread.key, agent.key, 'keep', true) === null;
    }""")
    # The package's resolve moved the panel on from the thread; the user reads its
    # reaction back in the thread's view.
    open_panel_thread(page, "thread-action-root")
    pressed = page.locator(
        f'{PANEL_THREAD}[data-thread="thread-action-root"] .lf-react[aria-pressed="true"]'
    )
    expect(pressed).to_have_count(1)
    # Taking the reaction back is drawn while the log has yet to answer it.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    actions.get_by_role("button", name="React").click()
    holding(page, held, 1, "the same reaction withdrawn")
    expect(actions).to_have_attribute("data-reacted", "false")
    expect(pressed).to_have_count(0)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(pressed).to_have_count(0)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("author") == "user" and event["kind"] != "comment"
    ] == ["reply", "resolve", "reply", "reply", "undo"]


@pytest.mark.parametrize("width", [693, 1440])
def test_panel_authored_message_button_reaches_primary_reader(browser, serve, width):
    """Threads routes a thread whose widget a primary reader owns to that reader."""
    page = open_page(browser, package_workspace(serve))
    page.set_viewport_size({"width": width, "height": 900})
    workspace = page.locator("#workspace")
    page.evaluate("window.nativeEmail = document.querySelector('#email')")
    # The thread's row in Threads takes the user to the reader that owns its widget.
    open_threads(page)
    page.locator('.lf-fp-thread[data-key="channel-question"]').click()
    panel_settled(page, open=False)
    message = workspace.locator('.lf-msg[data-event="channel-question"]')
    email = message.locator("#email")
    expect(email).to_be_in_viewport()
    assert email.evaluate("node => node === nativeEmail")
    with sending(page, "answer in the primary reader reached from Threads"):
        email.click()
    expect(email.get_by_role("checkbox")).to_be_checked()


def test_nested_primary_reader_keeps_native_scope_navigation_and_read_evidence(
    browser, serve
):
    """Forwarding slots preserve native widgets and respect rendered inert ancestors."""
    from render_harness import ROOT

    companion = ROOT / "examples/developer/feature-gallery.page"
    registry = {
        "lf-conversation-workspace": json.loads(
            (companion / "registry.json").read_text()
        )["lf-conversation-workspace"]
    }
    registry["lf-nested-reader"] = {
        "description": "A declared nested physical reader stage.",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "empty",
        "x-shadow": True,
        "x-upgrade": True,
    }
    module = (companion / "widgets/lf-conversation-workspace.js").read_text()
    module = module.replace(
        "body.append(index, this.reader);",
        """const nested = offer('lf-nested-reader');
        nested.style.display = 'block';
        nested.style.minWidth = '0';
        nested.style.minHeight = '0';
        nested.inert = true;
        const nestedStyle = document.createElement('style');
        nestedStyle.textContent = '.reader { height:100%; min-height:0; overflow:auto; }';
        shadowStage(nested, [nestedStyle, this.reader]);
        body.append(index, nested);""",
    )
    url = serve(
        leaf_page(
            "Nested package reader",
            '<h1>Nested package reader</h1><lf-conversation-workspace id="workspace"></lf-conversation-workspace>',
        ),
        layer_registry=registry,
        layer_widgets={
            "lf-conversation-workspace.js": module,
            "lf-nested-reader.js": "customElements.define('lf-nested-reader', class extends HTMLElement {});",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "nested-question",
            "attempt": "nested-question-key",
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which channel?",
            "markup": '<lf-ask id="channel-ask"><h3>Channel</h3><lf-options id="channel-options" choose><lf-option id="email">Email</lf-option><lf-option id="chat">Chat</lf-option></lf-options></lf-ask>',
        },
    )
    page = open_page(browser, url)
    workspace = page.locator("#workspace")
    email = workspace.locator("lf-option#email")
    expect(email).to_be_visible()
    page.evaluate(
        """async () => {
        window.api = await window.__lfWidgetApi();
        window.nestedOption = document.querySelector('#email');
        }"""
    )
    assert email.evaluate("node => node.getRootNode() === document")
    assert page.evaluate(
        "document.querySelector('#workspace').shadowRoot.querySelector('lf-nested-reader').shadowRoot !== null"
    )
    workspace.get_by_role("button", name="Feed", exact=True).click()
    assert email.evaluate(
        "node => node === nestedOption && node.closest('#workspace') !== null"
    )
    round_trip(page)
    assert page.evaluate("api.readThreads().threads[0].unread") == [
        {"message": "nested-question", "version": "nested-question"}
    ]
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
    ]
    page.evaluate(
        "document.querySelector('#workspace').shadowRoot.querySelector('lf-nested-reader').inert = false"
    )
    workspace.get_by_role("button", name="Shelf", exact=True).click()
    expect(
        workspace.locator('.lf-msg[data-event="nested-question"]')
    ).not_to_have_class(re.compile(r"\blf-unread\b"))
    round_trip(page)
    assert [
        event["messages"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
    ] == [[{"message": "nested-question", "version": "nested-question"}]]
    assert email.evaluate("node => node === nestedOption")
    assert page.evaluate(
        "async () => await api.threadActions.open('nested-question-key', {message:'nested-question-key'}) !== null"
    )
    expect(workspace.locator('.lf-msg[data-event="nested-question"]')).to_be_focused()
    assert page.evaluate(
        "api.currentLocationIn(document.querySelector('#workspace').reader)"
    )
    assert page.evaluate(
        "typeof api.holdFocus(document.querySelector('#workspace').reader) === 'function'"
    )
    assert email.evaluate(
        "node => node === nestedOption && node.getRootNode() === document"
    )
    with sending(page, "answer through a nested package reader"):
        email.click()
    expect(workspace.locator(".counts")).to_contain_text("Email")


@pytest.mark.parametrize("mode", ["Conversation", "Feed", "Reply only"])
def test_primary_reading_holds_remote_changes_before_package_layout(
    browser, serve, mode
):
    """A primary reader keeps one shown thread reading until its native notice opens it."""
    page = open_page(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    if mode == "Reply only":
        workspace.evaluate("""async workspace => {
          const api = await window.__lfWidgetApi();
          const outlet = workspace.outlet('reply-only');
          workspace.present = (collection, parts) => {
            api.setChildren(workspace.reader, [outlet]);
            parts.reply(collection.threads.find(thread => thread.id === 'opening').key, outlet);
          };
          await workspace.presentation.update({release: true});
        }""")
    else:
        workspace.get_by_role("button", name=mode, exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    write(editor, "Keep this draft while updates wait.")
    assert editor.evaluate("""async editor => {
      const {scrollerFor} = await window.__lfWidgetApi();
      const {readingRegionFor} = await window.__lfCheckApi();
      const reader = document.querySelector('#workspace').reader;
      return scrollerFor(editor) === reader && readingRegionFor(editor).body === reader;
    }""")
    editor.evaluate("node => node.setSelectionRange(2, 8, 'backward')")
    page.evaluate("""() => {
      const workspace = document.querySelector('#workspace');
      window.readerNodes = [...workspace.reader.children];
      window.heldMessage = workspace.querySelector('[data-event="answer"]');
      window.heldEditor = workspace.querySelector('leaf-text');
    }""")
    before = editor.bounding_box()
    page.wait_for_timeout(600)  # Let Chrome's recent-input grace expire before news.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "agent",
            "message": "answer",
            "text": "A much longer edited answer. " * 25,
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "later-answer",
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "opening",
            "text": "A later turn.",
        },
    )
    told(page)
    if mode != "Reply only":
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_have_text(
            "One paragraph."
        )
    expect(workspace.locator('[data-event="later-answer"]')).to_have_count(0)
    assert page.evaluate("""() => {
      const current = [...document.querySelector('#workspace').reader.children];
      return current.length === readerNodes.length && current.every((node, i) => node === readerNodes[i]);
    }""")
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", "Keep this draft while updates wait.")
    assert editor.evaluate(
        "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
    ) == [2, 8, "backward"]
    assert editor.bounding_box() == before
    workspace.evaluate("async node => await node.presentation.update()")
    if mode != "Reply only":
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_have_text(
            "One paragraph."
        )
    expect(workspace.locator('[data-event="later-answer"]')).to_have_count(0)
    assert editor.bounding_box() == before
    workspace.get_by_role(
        "button", name="1 new reply · 1 message edited", exact=True
    ).click()
    if mode != "Reply only":
        expect(workspace.locator('[data-event="later-answer"]')).to_contain_text(
            "A later turn."
        )
        expect(workspace.locator('[data-event="answer"] .lf-msg-text')).to_contain_text(
            "A much longer edited answer."
        )
        assert page.evaluate(
            "document.querySelector('#workspace [data-event=answer]') === heldMessage"
        )
    expect(
        workspace.get_by_role(
            "button", name="1 new reply · 1 message edited", exact=True
        )
    ).to_have_count(0)
    expect(editor).to_have_js_property("value", "Keep this draft while updates wait.")
    rendered(page)


def test_primary_reader_revision_replaces_owner_without_losing_thread_draft(
    browser, serve
):
    """An authored owner replacement carries the thread's session and frozen widgets."""
    page = open_page(browser, live_url(package_workspace(serve)))
    page.evaluate(
        """() => {
        window.originalWorkspace = document.querySelector('#workspace');
        window.originalOption = document.querySelector('#email');
        window.originalDocument = performance.timeOrigin;
        }"""
    )
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    editor = workspace.get_by_role("textbox", name="Reply", exact=True)
    words = "Keep this unfinished answer across the revision."
    write(editor, words)
    editor.evaluate("node => node.setSelectionRange(2, 8, 'backward')")
    before = editor.evaluate("node => [node.selectionStart, node.selectionEnd]")
    stamp_page(
        serve.page_dir,
        leaf_page(
            "Package reader",
            '<h1>Package reader</h1><p id="notes">Revised announcement notes</p><lf-conversation-workspace id="replacement"></lf-conversation-workspace>',
        ),
        "Replace the reader owner while retaining its conversations",
    )
    told(page)
    # The panel's row notice for the newer version, pressed without taking the
    # editor's focus first, as a press on it does.
    page.locator(".lf-fp-row-notice-press").filter(has_text="Latest").dispatch_event(
        "click"
    )
    wait_for_revision(page, 2)
    assert page.evaluate("performance.timeOrigin === originalDocument")
    assert page.evaluate("!originalWorkspace.isConnected")
    replacement = page.locator("#replacement")
    reply = replacement.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_have_js_property("value", words)
    assert reply.evaluate("node => [node.selectionStart, node.selectionEnd]") == before
    expect(
        replacement.locator('.lf-page-thread[data-thread="opening"]')
    ).to_contain_text("One paragraph.")
    replacement.get_by_role("button", name=re.compile(r"Which channel\?")).click()
    email = replacement.locator("lf-option#email")
    expect(email).to_be_visible()
    assert email.evaluate(
        "node => node === originalOption && node.getRootNode() === document"
    )
    with sending(
        page, "answer the unchanged native obligation after reader replacement"
    ):
        email.click()
    expect(replacement.locator(".counts")).to_contain_text("Email")
    replacement.get_by_role("button", name="Keep it concise.", exact=True).click()
    reply = replacement.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_have_js_property("value", words)
    with sending(page, "send the thread draft carried across reader replacement"):
        reply.press("Control+Enter")
    expect(
        replacement.locator('.lf-page-thread[data-thread="opening"]')
    ).to_contain_text(words)
    assert [
        event["parent"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event.get("text") == words
    ] == ["opening"]


def test_primary_parts_keep_identity_and_nomination_order_through_admission(
    browser, serve
):
    """A shared outlet follows nomination order without remounting admitted turns."""
    page = open_page(browser, package_workspace(serve))
    page.evaluate("""async () => {
      window.api = await window.__lfWidgetApi();
      const workspace = document.querySelector('#workspace');
      const present = (collection, parts) => {
        const messages = collection.threads.flatMap(thread =>
          api.threadTurns(thread).map(message => [thread, message]));
        if (workspace.reversed) messages.reverse();
        for (const [thread, message] of messages)
          parts.message(thread.key, message.key, workspace.reader);
      };
      document.addEventListener('keydown', async event => {
        if (event.key === 'F8') {
          workspace.present = present;
          workspace.reader.replaceChildren();
          await workspace.presentation.update();
          window.firstPart = workspace.querySelector('[data-event="answer"]');
        }
        if (event.key === 'F9') {
          workspace.reversed = true;
          await workspace.presentation.update();
        }
        if (event.key === 'F10')
          window.created = api.threadActions.create({text:'Retain this turn'});
      });
    }""")
    page.keyboard.press("F8")
    rendered(page)
    order = """node => [...node.shadowRoot.querySelector('.reader').children]
      .flatMap(slot => slot.assignedElements())
      .map(part => part.querySelector('.lf-msg').dataset.event)"""
    workspace = page.locator("#workspace")
    assert workspace.evaluate(order) == ["channel-question", "opening", "answer"]
    page.keyboard.press("F9")
    rendered(page)
    assert workspace.evaluate(order) == ["answer", "opening", "channel-question"]
    assert page.evaluate("document.querySelector('[data-event=answer]') === firstPart")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("F10")
    holding(page, held, 1, "the new fragment's admission")
    rendered(page)
    page.evaluate("""() => {
      window.pendingPart = document.querySelector('.lf-msg[data-attempt="' + created.key + '"]');
    }""")
    assert page.evaluate("pendingPart !== null")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    page.evaluate("created.delivery")
    rendered(page)
    assert page.evaluate("""() => pendingPart.isConnected &&
      document.querySelector('.lf-msg[data-attempt="' + created.key + '"]') === pendingPart &&
      !pendingPart.dataset.event.startsWith('pending:')""")
