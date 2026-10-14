"""Joint browser proof for immutable page inputs and fresh revision activation."""

import json
import re
from datetime import UTC, datetime
from itertools import pairwise

import pytest
from interact_support import append_carried_log_record, append_command
from leaf import event_log as events_model
from leaf import interaction_log as interaction_model
from leaf import thread as thread_model
from leaf.render_checks import one_frame, rendered, wait_until_ready
from leaf.schema import ELEMENT_ID
from leaf_dev.response_times import page_timings
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_READING,
    LIVE_V1,
    SEATED_ASK_PAGE,
    live_url,
)
from render_harness import (
    consume_browser_errors,
    expect_asks_answered,
    holding,
    is_problem,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    refuse,
    reported_browser_errors,
    round_trip,
    said,
    scroll_settled,
    sending,
    take_browser_errors,
    told,
    write,
)

THREAD_READER = r"""
import {keepsText, watchProjection, readThreads, threadSummary, threadTurns} from '/runtime/widget-api.js';
customElements.define('lf-thread-reader', class extends HTMLElement {
  connectedCallback() {
    this.output = document.createElement('pre');
    this.append(this.output);
    this.stop = watchProjection(this, () => {
      const collection = readThreads();
      this.reading = collection;
      this.sameReading = collection === readThreads();
      keepsText(this.output, collection.threads.map(thread =>
        threadTurns(thread).map(message => message.body.text).join('\n')
      ).join('\n'));
      this.topic = collection.threads[0] && threadSummary(collection.threads[0]).topic;
    });
  }
  disconnectedCallback() { this.stop(); }
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
import {keepsText, threadActions, readThreads, threadSummary, watchProjection} from '/runtime/widget-api.js';
customElements.define('lf-thread-filter', class extends HTMLElement {
  connectedCallback() {
    if (!this.input) {
      this.input = document.createElement('input');
      this.input.setAttribute('aria-label', `Filter ${this.id}`);
      this.input.value = this.getAttribute('filter') ?? '';
      this.list = document.createElement('ul');
      this.input.addEventListener('input', () => this.paint());
      this.append(this.input, this.list);
    }
    this.stop ??= watchProjection(this, () => {
      const collection = readThreads();
      this.reading = collection;
      this.sameReading = collection === readThreads();
      this.updates = (this.updates ?? 0) + 1;
      this.paint();
    });
  }
  paint() {
    if (!this.reading) return;
    const query = this.input.value.toLowerCase();
    const shown = this.reading.threads
      .filter(thread => threadSummary(thread).topic.toLowerCase().includes(query));
    // Each row is kept and says only what changed.
    const items = [...this.list.children];
    shown.forEach((thread, index) => {
      let item = items[index];
      if (!item) {
        item = document.createElement('li');
        item.append(document.createElement('button'));
        this.list.append(item);
      }
      keepsText(item.firstChild, threadSummary(thread).topic);
      item.firstChild.onclick = () => threadActions.open(thread.key);
    });
    for (const item of items.slice(shown.length)) item.remove();
  }
  disconnectedCallback() {
    this.stop?.();
    this.stop = null;
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

THREAD_MIRROR = r"""
import {keeps, mountThreadViews, threadSummary} from '/runtime/widget-api.js';
customElements.define('lf-thread-mirror', class extends HTMLElement {
  connectedCallback() {
    if (!this.outlet) {
      this.input = document.createElement('input');
      this.input.setAttribute('aria-label', `Filter ${this.id}`);
      this.input.value = this.getAttribute('filter') ?? '';
      this.outlet = document.createElement('div');
      this.append(this.input, this.outlet);
      this.input.addEventListener('input', () => this.consumer?.update());
    }
    this.consumer ??= mountThreadViews(this, (collection, surfaces) => {
      this.updates = (this.updates ?? 0) + 1;
      (this.signals ??= []).push(surfaces.signal);
      if (this.holding) {
        keeps(this, 'data-held', true);
        return new Promise(resolve => (this.releases ??= []).push(resolve));
      }
      const query = this.input.value.toLowerCase();
      for (const thread of collection.threads)
        if (threadSummary(thread).topic.toLowerCase().includes(query))
          surfaces.thread(thread.key, this.outlet);
    });
  }
  disconnectedCallback() {
    this.consumer?.unregister();
    this.consumer = null;
  }
});
"""

THREAD_MIRROR_DECLARATION = {
    "description": "A package-owned mirror of core Thread conversations.",
    "type": "object",
    "properties": {"id": {"type": "string"}, "filter": {"type": "string"}},
    "required": ["id"],
    "additionalProperties": False,
    "x-content": "empty",
    "x-upgrade": True,
    "x-example": '<lf-thread-mirror id="mirror-example"></lf-thread-mirror>',
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
        page.locator(".lf-general .lf-compose-submit").click()
    question = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event["author"] == "user"
    )
    answer = thread_model.post_reply(
        serve.page_dir,
        {"to": question["id"], "for": question["id"]},
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
        page.locator(".lf-threads-toggle").click()
        expect(page.locator(".lf-thread .lf-msg.agent .lf-msg-text")).to_have_text(
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
    sample = next(
        sample
        for sample in page_timings(serve.page_dir, since=None, until=datetime.now(UTC))[
            "samples"
        ]
        if sample["input_id"] == question["id"]
    )
    measured = sample["milestones"]["send_to_visible"]
    assert measured["event_id"] == answer["id"]
    assert measured["session"] == shown["session"]
    assert (
        measured["elapsed_s"]
        == (shown["monotonic_ms"] - submitted["monotonic_ms"]) / 1000
    )


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
    consume_browser_errors(page, {"code": "failed-load", "status": 503})


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
    consume_browser_errors(page, {"code": "failed-load", "status": 503})


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
import {
  html, keeps, layerFact, once, render, widgetController,
} from "/runtime/widget-api.js";

customElements.define("lf-local", class extends HTMLElement {
  controller = widgetController(this);
  reading = this.controller.read();

  constructor() {
    super();
    this.attachShadow({mode: "open"});
  }

  connectedCallback() {
    this.paint();
    if (!once(this)) return;
    layerFact("$tones");
    keeps(this, "data-page-widget", "ready");
    this.controller.subscribe(reading => {
      this.reading = reading;
      this.dataset.renderOrder = `${this.dataset.renderOrder || ""}subscribe,`;
      keeps(this, "data-subscriber-choice", this.dataset.renderedChoice);
      this.dataset.readings = String(Number(this.dataset.readings || 0) + 1);
      this.paint();
    });
    const held = globalThis.__heldLocalPresentations?.get(this.id);
    if (held) this.controller.present(held);
  }

  choose() {
    keeps(this, "data-render-order", "");
    this.dataset.gestures = String(Number(this.dataset.gestures || 0) + 1);
    const sent = this.controller.dispatch({
      kind: "action",
      verb: "choose",
      detail: { value: "chosen" },
    });
    if (!sent) return;
    this.reading = sent.reading;
    keeps(this, "data-delivery", "pending");
    this.paint();
    sent.delivery.then(accepted => {
      keeps(this, "data-delivery", accepted ? "accepted" : "refused");
    });
  }

  renderState(state) {
    if (globalThis.__failLocalRender) {
      globalThis.__failedLocalRenders =
        Number(globalThis.__failedLocalRenders || 0) + 1;
      throw new Error("deliberate render failure");
    }
    keeps(this, "data-rendered-choice", state.choose.value);
    this.dataset.renderOrder = `${this.dataset.renderOrder || ""}render,`;
    this.paint();
  }

  paint() {
    const choice = this.reading.state.choose?.value ?? this.getAttribute("choice");
    const available = this.reading.actions.choose?.available ?? false;
    render(html`<button ?disabled=${!available} @click=${this.choose}>Choose</button>
      <output>${choice}</output>`, this.shadowRoot, {host: this});
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

    # The order is read in the turn that sends the gesture, where the claim lives: the
    # widget clears it in `choose`, and the optimistic publication renders the owner and
    # then runs its subscribers before the click returns. Waiting for it afterwards reads
    # a state the page passes through, because the delivery outcome, the admitted event,
    # and the cleared ledger each publish a further reading of their own; the
    # single-pair window closes as soon as the round trip lands.
    installed = page.evaluate(
        """() => {
          const owner = document.querySelector('#page-local');
          const control = owner.shadowRoot.querySelector('button');
          control.click();
          return {
            defined: customElements.get('lf-local') === owner.constructor,
            connected: owner.dataset.pageWidget,
            gestures: owner.dataset.gestures,
            order: owner.dataset.renderOrder,
          };
        }"""
    )
    assert installed == {
        "defined": True,
        "connected": "ready",
        "gestures": "1",
        "order": "render,subscribe,",
    }
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")
    expect(page.locator("#page-local")).to_have_attribute(
        "data-subscriber-choice", "chosen"
    )
    round_trip(page)
    order = page.locator("#page-local").get_attribute("data-render-order")
    assert re.fullmatch(r"(?:render,subscribe,)+", order), order


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


APPROVAL_PAGE = leaf_page(
    "approval waits for admission",
    """
<lf-ask id="release-decision"><h1>Ship this release?</h1>
  <lf-options id="release-options" choose>
    <lf-option id="release-ship">Ship it</lf-option>
    <lf-option id="release-hold">Hold it</lf-option>
  </lf-options>
</lf-ask>
""",
    head='<meta name="lf-review" content="sign-off">',
)


def test_approval_waits_for_a_reading_of_the_log(browser, serve):
    """An offline page that never read its log cannot say its Asks are answered.

    The first state read is refused, so presentation releases the authored page under the
    offline banner with no admitted reading. Nothing then says whether the authored Ask
    still stands, and approval stays shut rather than reading that silence as every Ask
    answered."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route("**/api/state*", refuse)
    page.goto(serve(APPROVAL_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfPresented === '1'")
    expect(page.locator(".lf-status-detail")).to_contain_text("Server offline")
    approval = page.locator(".lf-signoff")
    expect(approval).to_be_visible()
    expect(approval).to_be_disabled()
    expect(approval).to_have_attribute(
        "title", "Approval waits until this page has read its current state"
    )


@pytest.mark.parametrize("expanded", [False, True])
def test_admission_holds_approval_until_the_answer_is_in_the_log(
    browser, serve, expanded
):
    """An answer the log has not taken in cannot open the irreversible approval.

    The pick is the user's at once — that is their own gesture drawn on their own
    widget. Which Asks still stand is the server's fold, so the count and the gate
    move when the state this POST returns is adopted, and not before."""
    page = open_page(browser, serve(APPROVAL_PAGE))
    approval = page.locator(".lf-signoff")
    expect(approval).to_be_disabled()

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("#release-ship .lf-pick").click()
    holding(page, held, 1, "the answer held outside the admitted log")

    expect(page.locator("#release-ship .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    expect_asks_answered(page, "0/1")
    expect(approval).to_be_disabled()
    expect(approval).to_have_attribute(
        "title", "Answer every ask before approving this work"
    )

    if expanded:
        page.keyboard.press("?")
        expect(page.locator(".lf-shortcut-bar")).to_have_attribute(
            "data-lf-expanded", "true"
        )
    # Admission may repack contextual hints and More inside the same bottom band.
    band = page.locator(".lf-shortcut-bar")
    before = band.bounding_box()
    assert before is not None

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_asks_answered(page, "1/1")
    expect(approval).to_be_enabled()
    expect(approval).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )

    rendered(page)
    assert band.bounding_box() == before


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
    # Another widget's action leaves this one's reading as it was, so its return draws
    # nothing again.
    page.evaluate("document.querySelector('main').append(pageLocal)")
    rendered(page)
    assert page.evaluate("Number(pageLocal.dataset.readings)") == readings
    expect(page.locator("#page-local").get_by_role("status")).to_have_text("chosen")


def test_a_returning_controller_widget_draws_again_only_a_changed_reading(
    browser, serve
):
    """A controller-driven widget follows the return rule data and projection watchers
    follow: a render that failed stands across a departure and return, so the author
    is told once, and a return draws nothing again while the reading is unchanged."""
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
    assert page.evaluate(leave_and_return) == {"drawn": 0, "failed": 0, "pending": []}

    # Resuming a deferral draws the same reading again, and this draw fails.
    page.evaluate(
        "globalThis.__failLocalRender = true; "
        "document.querySelector('#page-local').controller.defer()(); true"
    )
    expect(page.locator("#page-local .lf-error")).to_have_text(
        "<lf-local> failed: <lf-local> renderState threw: deliberate render failure"
    )
    assert page.evaluate(leave_and_return) == {"drawn": 0, "failed": 1, "pending": []}
    errors = take_browser_errors(page)
    assert [said(error) for error in errors] == [
        (
            "leaf: paint failed for lf-local#page-local: <lf-local> renderState threw: "
            "deliberate render failure"
        )
    ]


def test_a_subscriber_added_after_the_first_render_fails_by_the_paint_rule(
    browser, serve
):
    """A subscriber that joins a drawn reading draws through the widget's paint, so
    its failure is reported once, as that paint's, and the widget shows its fail-soft
    box."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Late subscriber",
                '<h1>Late subscriber</h1><lf-local id="page-local" choice="idle">'
                "</lf-local>",
            ),
            page_files={
                "registry.json": json.dumps(PAGE_DECLARATION),
                "widgets/lf-local.js": PAGE_WIDGET,
            },
        ),
    )
    expect(page.locator("#page-local")).to_have_attribute("data-page-widget", "ready")
    page.evaluate(
        "document.querySelector('#page-local').controller.subscribe(() => {"
        " throw new Error('late subscriber failure'); }); true"
    )
    expect(page.locator("#page-local .lf-error")).to_have_text(
        "<lf-local> failed: late subscriber failure"
    )
    reported_browser_errors(
        page, "leaf: paint failed for lf-local#page-local: late subscriber failure"
    )


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
    page.wait_for_function("readLeafPresentation().pending.length === 0")
    assert page.evaluate("window.__failedLocalRenders") == 1
    errors = take_browser_errors(page)
    assert [said(error) for error in errors] == [
        (
            "leaf: paint failed for lf-local#page-local: <lf-local> renderState threw: "
            "deliberate render failure"
        )
    ]
    assert "Caused by: Error: deliberate render failure" in errors[0].values["text"]


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

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "frozen-widget-question",
            "author": "user",
            "revision": 1,
            "text": "Show the frozen widget.",
        },
    )
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
          return document.querySelector('#thread-local') &&
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
    expect(page.locator("#thread-local")).to_have_attribute(
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
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "failing-widget-question",
            "author": "user",
            "revision": 1,
            "text": "Show another frozen widget.",
        },
    )
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
        """() => document.querySelector('#thread-failing') &&
          readLeafPresentation().pending.includes('thread') &&
          readLeafPresentation().pending.includes(
            'widget:thread-failing:preparation'
          )""",
    )
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    page.evaluate(
        "threadReady = false; "
        "whenLeafRegionsPresented(['thread'], () => true)"
        ".then(() => { threadReady = true; }); "
        "failedThreadPreparation.reject(new Error('frozen descendant failure')); true"
    )
    page.wait_for_function("threadReady")
    expect(page.locator("#thread-failing")).to_have_count(1)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads: 2")
    expect(page.locator(".lf-thread-panel .lf-auxiliary-title")).to_have_text("Threads")
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: frozen descendant failure"
    ]


@pytest.mark.parametrize("route", ["t", "Shift+T", "ArrowDown", "click"])
def test_choosing_beside_a_withdrawn_notice_holds_the_chosen_card(
    browser, serve, route
):
    """From a withdrawn thread's notice, `t`, `T`, an arrow or a press chooses the card
    beside it, and releasing the notice's room moves none of what the user sees there."""
    before = [f"before-{i}" for i in range(12)]
    after = [f"after-{i}" for i in range(20)]
    sections = [*before, "withdrawn", *after]
    url = serve(
        leaf_page(
            "Withdrawn among threads",
            "<h1>Review</h1>"
            + "".join(f'<p id="{name}">Passage {name}.</p>' for name in sections),
        )
    )
    for name in sections:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "id": name,
                "author": "user",
                "revision": 1,
                "anchor": {"section": name},
                "text": f"Conversation {name}.",
            },
        )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator('.lf-threads > [data-id="withdrawn"]')
    card.locator(".lf-thread-summary").scroll_into_view_if_needed()
    card.locator(".lf-thread-summary").click()
    rendered(page)
    # Cards in view on both sides of the open one, and room scrolled past to take its
    # release.
    page.locator("leaf-thread-list").evaluate(
        "(list, card) => { list.scrollTop += card.getBoundingClientRect().top"
        " - list.getBoundingClientRect().top - 100; }",
        card.element_handle(),
    )
    scroll_settled(page, "leaf-thread-list")
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "revision": 1, "undoes": "withdrawn"},
    )
    told(page)
    notice = page.locator('[data-withdrawn="withdrawn"]')
    expect(notice.locator("button")).to_be_focused()
    chosen = page.locator(
        f'.lf-threads > [data-id="{before[-1] if route == "Shift+T" else after[0]}"]'
    )
    top = chosen.evaluate("node => node.getBoundingClientRect().top")

    if route == "click":
        chosen.locator(".lf-thread-summary").click()
    else:
        page.keyboard.press(route)
    rendered(page)
    expect(notice).to_have_count(0)
    expect(chosen).to_have_attribute("open", "")
    expect(chosen.locator(".lf-thread-summary")).to_be_focused()
    assert chosen.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        top, abs=0.5
    )


def test_an_unavailable_list_preserves_the_selected_conversation(browser, serve):
    """A placeholder has no identity inventory from which to retire a choice."""
    url = serve(
        leaf_page(
            "Unavailable threads",
            '<h1>Review</h1><p id="earlier">Earlier passage.</p>'
            '<p id="later">Later passage.</p>',
        )
    )
    for identity, section in [("earlier-thread", "earlier"), ("later-thread", "later")]:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "id": identity,
                "author": "user",
                "revision": 1,
                "anchor": {"section": section},
                "text": f"Accepted conversation on {section}.",
            },
        )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    selected = page.locator('.lf-thread[data-id="later-thread"]')
    expect(page.locator(".lf-thread").first).not_to_have_attribute(
        "data-id", "later-thread"
    )
    selected.locator(".lf-thread-summary").click()
    expect(selected).to_have_attribute("open", "")
    general = page_comment(page)
    # Exercise the presentation owner's real unavailable reading. Keep focus outside
    # the list, so title restoration cannot conceal losing the selected conversation.
    page.evaluate(
        """async () => {
          const list = document.querySelector('leaf-thread-list');
          window.availableThreadReading = list.model;
          const unavailable = {...list.model,
            rows: [{kind: 'empty', key: 'unavailable',
              text: 'Current threads temporarily unavailable.'}],
            count: null,
            pageSeats: new Map(),
          };
          await list.present(unavailable);
          list.commit(unavailable);
        }"""
    )
    expect(page.locator("leaf-thread-list")).to_contain_text(
        "Current threads temporarily unavailable."
    )
    expect(selected).to_have_count(0)
    expect(general).to_be_focused()
    page.evaluate(
        """async () => {
          const list = document.querySelector('leaf-thread-list');
          const available = window.availableThreadReading;
          const partial = {...available,
            rows: [available.rows.find(row => row.kind === 'thread'),
              {kind: 'empty', key: 'unavailable', text: 'Threads unavailable.'}],
            count: null,
          };
          await list.present(partial);
          list.commit(partial);
          await list.present(available);
          list.commit(available);
        }"""
    )
    expect(selected).to_have_attribute("open", "")
    expect(general).to_be_focused()


def test_thread_readiness_waits_for_the_keyed_thread_list(browser, serve):
    """Readiness includes the real Lit paint, preserving the existing editor."""
    url = serve(LIVE_V1)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "kept-thread",
            "author": "user",
            "revision": 1,
            "text": "Keep this draft and its exact card.",
        },
    )
    page = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator('.lf-thread[data-id="kept-thread"] .lf-thread-summary').click()
    reply = page.locator('.lf-thread[data-id="kept-thread"] leaf-text')
    write(reply, "half a thought")
    reply.evaluate("input => input.setSelectionRange(4, 4)")
    card = page.locator('.lf-thread[data-id="kept-thread"]').element_handle()

    def assert_draft_retained():
        assert card.evaluate("node => node.isConnected"), "the card was replaced"
        expect(reply).to_be_focused()
        expect(reply).to_have_js_property("value", "half a thought")
        assert reply.evaluate(
            "input => [input.selectionStart, input.selectionEnd]"
        ) == [4, 4]

    held_events = []
    page.route("**/api/event", lambda route: held_events.append(route))
    page.evaluate(
        """async () => {
          const application = await window.__lfWidgetApi();
          const list = document.querySelector('leaf-thread-list');
          const schedule = list.scheduleUpdate.bind(list);
          const perform = list.performUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          window.threadListReleased = false;
          list.scheduleUpdate = () => {
            window.threadListHeld = true;
            return held.then(schedule);
          };
          list.performUpdate = (...args) => {
            window.threadListHeld = true;
            return window.threadListReleased ? perform(...args) : undefined;
          };
          window.releaseThreadList = () => {
            window.threadListReleased = true;
            release();
          };
          document.addEventListener('keydown', event => {
            if (event.key === 'F9') window.releaseThreadList();
          });
          application.threadActions.create({
            attempt: 'held-thread-list',
            text: 'A second thread arrives.',
          });
        }"""
    )
    # The held owner was actually called. Read the same readiness door as page
    # authors and the render gate, without naming its internal renderer tickets.
    page.wait_for_function("() => window.threadListHeld === true")
    assert (
        page.evaluate(
            "() => document.querySelector('script[data-lf-entry]').lfReadiness(null, 'presented')"
        )
        == "presented"
    )
    pending_card = page.locator('.lf-thread[data-attempt="held-thread-list"]')
    expect(pending_card).to_have_count(0)
    assert_draft_retained()

    # The synthetic release needs an input edge to distinguish it from passive news.
    page.keyboard.press("F9")
    wait_until_ready(page, through="presented")
    expect(pending_card).to_have_count(1)
    assert_draft_retained()
    holding(page, held_events, 1, "the comment made behind the held thread list")
    held_events[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)


THREAD_ACTIONS = r"""
import {keeps, readThreads, threadActions, watchProjection} from '/runtime/widget-api.js';
customElements.define('lf-thread-actions', class extends HTMLElement {
  connectedCallback() {
    this.innerHTML = '<input aria-label="Package reply"><button>Reply</button>' +
      '<button>Resolve</button><button>Reopen</button><button>React</button>';
    this.stop = watchProjection(this, () => {
      this.thread = readThreads().threads[0];
      keeps(this, 'data-resolved', Boolean(this.thread?.resolved));
      keeps(this, 'data-reacted', Boolean(this.thread?.msgs.find(msg => msg.author === 'agent')?.reactions?.choices.find(choice => choice.name === 'keep')?.inForce));
    });
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
  disconnectedCallback() { this.stop(); }
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
def test_compact_reader_opens_the_native_interactive_message(browser, serve, surface):
    """A compact reader's button addresses message content, not its own reply row."""
    target = "jobs" if surface == "outlet" else "notes"
    source = (
        SEATED_ASK_PAGE
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
        page.get_by_role(
            "button", name=re.compile("Thread, My turn to answer")
        ).first.click()
        compact = page.locator(".lf-margin-thread")
    else:
        compact = page.locator('#jobs .lf-page-thread[data-thread="native-thread"]')
    panel = page.locator(".lf-thread-panel")
    expect(panel).not_to_have_class(re.compile(r"\bopen\b"))
    button = compact.get_by_role("button", name="Open interactive reply")
    expect(button).to_be_visible()
    button.focus()
    button.press("Enter")
    panel_settled(page)
    expect(panel).to_have_class(re.compile(r"\bopen\b"))
    message = panel.locator('.lf-msg[data-mid="native-message"]')
    expect(message).to_be_focused()
    email = message.locator("#native-email")
    expect(email).to_be_in_viewport()
    with sending(page, "answer the native interactive reply"):
        email.click()
    expect(email.get_by_role("checkbox")).to_be_checked()


@pytest.mark.parametrize("owner", ["root", "middle"])
def test_frozen_ask_reveals_its_exact_message_in_a_selective_primary(
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
      return await api.askActions.open('widget:channel');
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
    """A selected value remains partial until the multiple-choice ask is done."""
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
    expect(counts).to_have_text("2 asks on me")
    with sending(page, "complete the selected extras"):
        workspace.locator("#extras").get_by_role(
            "button", name="Done: these picks are complete", exact=True
        ).click()
    expect(counts).to_have_text("1 asks on me · 1 answered · Chat")


def test_public_queue_commands_recheck_membership_and_restore_refusals(browser, serve):
    page = open_page(browser, package_workspace(serve))
    page.evaluate("async () => { window.api = await window.__lfWidgetApi(); }")
    key = page.evaluate(
        "api.queueItemKey(api.readQueues().on_user.find(item => item.id === 'proofread'))"
    )
    assert page.evaluate(
        "api.queueActions.done(api.queueItemKey(api.readQueues().on_user.find(item => item.ask?.source.kind === 'widget'))) === null"
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


def test_failed_primary_reader_restores_the_same_native_ask_in_core(browser, serve):
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
    assert page.evaluate(
        "nativeOption.isConnected && nativeOption.closest('.lf-thread') !== null"
    )
    page.evaluate("document.querySelector('#workspace').presentation.update()")
    email = page.locator("lf-option#email")
    expect(email).to_be_visible()
    assert email.evaluate("node => node === nativeOption")
    with sending(page, "answer the restored native Ask"):
        email.click()
    expect(page.locator("#workspace .counts")).to_contain_text("Email")


@pytest.mark.parametrize("fault", ["detached-outlet", "retained-list"])
def test_primary_native_content_survives_sibling_preparation_faults(
    browser, serve, fault
):
    page = open_page(browser, package_workspace(serve))
    page.evaluate(
        """fault => {
      const workspace = document.querySelector('#workspace');
      window.nativeOption = workspace.querySelector('#email');
      const list = document.querySelector('leaf-thread-list');
      const present = list.present.bind(list);
      if (fault === 'retained-list') {
        list.present = model => {
          list.present = present;
          throw new Error('Deliberate sibling failure');
        };
      } else {
        let release;
        const gate = new Promise(resolve => { release = resolve; });
        window.releaseSibling = release;
        list.present = model => {
          list.present = present;
          window.siblingWaiting = true;
          return gate.then(() => present(model));
        };
      }
      window.faultDelivery = workspace.presentation.update().catch(() => null);
    }""",
        fault,
    )
    if fault == "detached-outlet":
        page.wait_for_function("window.siblingWaiting === true")
        page.evaluate("""() => {
          document.querySelector('#workspace').reader.firstElementChild.remove();
          releaseSibling();
        }""")
    page.evaluate("faultDelivery")
    consume_browser_errors(
        page,
        "leaf: Presentation failed: "
        + (
            "Deliberate sibling failure"
            if fault == "retained-list"
            else "A primary Thread outlet must remain inside its connected owner"
        ),
    )
    assert page.evaluate("nativeOption.isConnected")
    page.evaluate("document.querySelector('#workspace').presentation.update()")
    email = page.locator("#workspace lf-option#email")
    expect(email).to_be_visible()
    assert email.evaluate("node => node === nativeOption")
    with sending(page, "answer after sibling recovery"):
        email.click()
    expect(page.locator("#workspace .counts")).to_contain_text("Email")


def test_queue_ask_arrival_selects_the_primary_reader(browser, serve):
    page = open_page(browser, package_workspace(serve))
    workspace = page.locator("#workspace")
    workspace.get_by_role("button", name="Keep it concise.", exact=True).click()
    page.evaluate("async () => { window.api = await window.__lfWidgetApi(); }")
    assert page.evaluate(
        "async () => { const item = api.readQueues().on_user.find(item => item.ask?.source.kind === 'widget'); return await api.queueActions.open(api.queueItemKey(item)); }"
    )
    expect(workspace.locator("lf-option#email")).to_be_visible()
    assert page.evaluate(
        "document.querySelector('#workspace').contains(document.querySelector('#email'))"
    )
    assert page.evaluate(
        "document.querySelector('leaf-thread-list').getBoundingClientRect().width === 0"
    )


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
