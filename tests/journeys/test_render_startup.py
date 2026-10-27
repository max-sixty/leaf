"""Initial presentation, polling, presence, and projected-data tests."""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import pytest
from click.testing import CliRunner
from interact_support import (
    wait_for,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_navigation import (
    data_projection_page,
)
from render_harness import (
    FEATURE_GALLERY,
    LONG_PAGE,
    _traffic,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_menu,
    panel_view,
    refuse,
    round_trip,
    select_words,
    sending,
    ticked,
    told,
    watched,
    write,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import user_views as user_views_model
from leaf.registry.storage import load_registry, served_layer
from leaf.render_checks import rendered, wait_until_ready
from leaf.served_state.reading import page_reading, source_readings

pytestmark = pytest.mark.shifts_unsurveyed

from browser.startup import HELD_KEYS_PAGE, _hold_startup
from browser.threads import open_panel_thread


@pytest.mark.watch_shifts
def test_the_gallery_embeds_an_ordinary_stamped_page(browser, serve):
    """Authored iframe markup opens a durable version rather than a practice copy."""
    url = live_url(serve(FEATURE_GALLERY))
    page = open_page(browser, url + "#bg-durable-embedding")
    expect(page.locator("#bg-durable-embedding")).to_be_in_viewport()
    page.locator("#bg-durable-frame-open").click()
    frame = page.locator("#bg-durable-frame").element_handle().content_frame()
    wait_until_ready(frame)
    assert urlparse(frame.url).path == "/versions/v2.html"
    expect(frame.locator("#bg-choice-ask h3")).to_have_text(
        "Which map should the sample team carry?"
    )
    open_threads(frame)
    expect(frame.locator(panel_view("threads"))).to_be_visible()
    frame.goto(frame.url)
    wait_until_ready(frame)
    assert urlparse(frame.url).path == "/versions/v2.html"
    expect(frame.locator("#bg-choice-ask h3")).to_have_text(
        "Which map should the sample team carry?"
    )


def test_a_preview_names_its_checkout_and_copies_diagnostics(browser, serve):
    preview = {
        "example": "triage-board",
        "checkout": "fb77",
        "interaction": "user",
        "started": "2026-08-31T12:00:00+00:00",
        "input": {"source": "triage-board", "authored": "test"},
    }
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    producer = {
        "commit": "26499ea1abcd",
        "dirty": True,
        "committed": (datetime.now().astimezone() - timedelta(days=3)).isoformat(
            timespec="seconds"
        ),
    }

    def provenance(route):
        response = route.fetch()
        reading = response.json()
        reading["layer"]["producer"] = producer
        route.fulfill(response=response, json=reading)

    context.route("**/api/state*", provenance)
    page = open_page(
        browser,
        serve(leaf_page("Preview", "<h1>Preview</h1>"), preview=preview),
        context=context,
    )
    # The leaf's menu names the preview on its copy row, and the copy says so where
    # the empty field's placeholder would.
    badge = panel_menu(page).locator('.lf-fp-item[data-row="preview"]')
    expect(badge).to_have_text("Copy preview diagnostics")
    expect(badge).to_have_attribute("title", "User · fb77@26499ea1abcd+ · 3d ago")
    badge.click()
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "placeholder", re.compile("^Preview diagnostics copied")
    )
    diagnostics = page.evaluate("() => navigator.clipboard.readText()")
    assert "example: triage-board" in diagnostics
    assert "checkout: fb77" in diagnostics
    assert "interaction: user" in diagnostics
    assert "commit: 26499ea1abcd" in diagnostics
    assert "dirty: true" in diagnostics
    assert f"committed: {producer['committed']}" in diagnostics
    assert "layer generation:" in diagnostics
    assert "layer fingerprint: sha256:" in diagnostics
    assert "revision: 1" in diagnostics
    assert "event sequence: 1" in diagnostics
    assert "?t=" not in diagnostics
    page.close()

    context.unroute("**/api/state*", provenance)
    ordinary = open_page(
        browser,
        serve(leaf_page("Ordinary", "<h1>Ordinary</h1>")),
        context=context,
    )
    expect(
        panel_menu(ordinary).locator('.lf-fp-item[data-row="preview"]')
    ).to_have_count(0)
    layer = served_layer(load_registry(serve.page_dir)["$layer"])
    producer = layer.get("producer", {})
    identity = (
        producer["commit"][:8]
        if producer.get("commit")
        else "sha256:" + layer["fingerprint"].removeprefix("sha256:")[:12]
    )
    reference = ordinary.locator('.lf-fp-menu .lf-fp-item[data-row="layer"]')
    dated = producer.get("committed") or producer.get("installed")
    expect(reference).to_have_text("Copy Leaf version")
    expect(reference).to_have_attribute(
        "title",
        re.compile(
            rf"^Leaf {re.escape(identity)}{re.escape('+') if producer.get('dirty') else ''}"
            + (r" · (just now|\d+[mhd] ago)$" if dated else "$")
        ),
    )
    reference.click()
    expect(ordinary.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "placeholder", re.compile("^Leaf version copied")
    )
    diagnostics = ordinary.evaluate("() => navigator.clipboard.readText()")
    assert f"fingerprint: {layer['fingerprint']}" in diagnostics
    if producer.get("commit"):
        assert f"commit: {producer['commit']}" in diagnostics
    if producer.get("committed"):
        assert f"committed: {producer['committed']}" in diagnostics


def test_a_page_that_never_presents_lets_its_held_keys_go(browser, serve):
    """The hold is for a page on its way. One still unpresented ten seconds in has
    faulted, so what was held is dropped and later presses reach the page as they come
    rather than waiting on a presentation that is not arriving."""
    url = serve(HELD_KEYS_PAGE)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held, _ = _hold_startup(page, "module")
    page.goto(url, wait_until="commit")
    holding(page, held, 1, "the runtime module")
    page.evaluate(
        "() => { window.heard = [];"
        " document.addEventListener('keydown', (e) => heard.push(e.key)); }"
    )
    page.keyboard.press("t")
    echo = page.locator(".lf-held-keys")
    expect(echo).to_be_visible()
    assert page.evaluate("heard") == [], "the positive control: the press was held"

    expect(echo).to_have_count(0)
    page.keyboard.press("x")
    assert page.evaluate("heard") == ["x"]


def test_opt_in_page_interface_joins_initial_widget_settlement(browser, serve):
    """Page interface preparation holds the first widget upgrade."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    watched(page)
    page.add_init_script(
        """
        document.addEventListener('lf-page-interface', event => {
          event.detail.present(new Promise(resolve => {
            window.releaseHeldPageInterface = resolve;
          }));
        });
        """
    )
    page.goto(
        serve(leaf_page("Held interface", "<h1>Held interface</h1>")),
        wait_until="load",
    )
    page.wait_for_function("() => window.releaseHeldPageInterface !== undefined")
    page.evaluate(
        """async () => {
          const {nextFrame} = await window.__lfWidgetApi();
          await new Promise(resolve => nextFrame(() => nextFrame(resolve)));
        }"""
    )
    expect(page.locator("body")).not_to_have_attribute("data-lf-upgraded", "1")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    page.evaluate("releaseHeldPageInterface()")
    wait_until_ready(page)


def test_more_than_six_live_documents_share_an_origin_without_stalling(browser, serve):
    """Live feeds leave HTTP slots available for startup, gestures and revisions."""
    url = live_url(serve(LONG_PAGE))
    with browser.new_context() as context:
        pages = [open_page(browser, url, context=context) for _ in range(8)]
        last = pages[-1]
        write(page_comment(last), "All eight views are live.")
        with sending(last, "the eighth view's comment"):
            last.locator(".lf-fp-field .lf-compose-submit").click()
        assert any(
            event.get("text") == "All eight views are live."
            for event in events_model.read_events(serve.page_dir)
        )
        (serve.page_dir / "index.html").write_text(
            LONG_PAGE.replace(">Long<", ">Updated across tabs<")
        )
        for page in pages:
            told(page)
            expect(page.locator("#t")).to_have_text("Updated across tabs")


@pytest.mark.parametrize("answer", ["ready", "offline"])
def test_slow_history_keeps_decisions_safe_and_status_honest(browser, serve, answer):
    """Presentation is not a state answer; every Decision route needs the same reading."""
    source = leaf_page(
        "Slow decision",
        '<h1>Slow decision</h1><lf-ask id="decision"><h2>Proceed?</h2>'
        '<lf-options id="pick" choose><lf-option id="yes">Proceed</lf-option>'
        '<lf-option id="no">Wait</lf-option></lf-options></lf-ask>',
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    posts = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            and request.post_data_json["kind"] == "action"
            else None
        ),
    )
    page.goto(serve(source), wait_until="load")
    holding(page, held, 1, "the unanswered private-state read")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    # Cross the former ten-second presentation deadline with a read still in flight.
    # This is the interval that used to invent an offline answer and release choices.
    page.wait_for_function("performance.now() > 11_000")
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", "Page menu · Loading comments and choices…"
    )
    assert len(held) == 1
    if answer == "ready":
        # An ordinary error in a usable page must not start recovery that could
        # reload the document and discard an early comment while history waits.
        page.evaluate("setTimeout(() => { throw new Error('post-upgrade fault'); })")
        page.wait_for_timeout(50)
        expect(page.locator("html")).not_to_have_attribute("data-lf-startup-error")
        expect(page.get_by_text("Leaf couldn't start", exact=False)).to_have_count(0)
        consume_browser_errors(page, "post-upgrade fault")
    first = page.locator("#pick .lf-pick").first
    second = page.locator("#pick .lf-pick").nth(1)
    expect(first).to_have_attribute("aria-disabled", "true")
    first.focus()
    page.keyboard.press("Space")
    second.dispatch_event("click")
    page.keyboard.press("1")
    expect(page.locator(".lf-held-keys kbd")).to_have_text("1")
    expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
    expect(page.locator("#no")).not_to_have_attribute("chosen", "")
    assert posts == []
    page.unroute("**/api/state*")
    if answer == "offline":
        page.route("**/api/state*", refuse)
        for route in held:
            refuse(route)
        expect(page.locator(".lf-fp-leaf")).to_have_attribute(
            "aria-label", re.compile("Lost the connection")
        )
        expect(page.locator(".lf-held-keys")).to_have_count(0)
        expect(first).to_have_attribute("aria-disabled", "true")
        first.focus()
        page.keyboard.press("1")
        page.keyboard.press("Space")
        second.dispatch_event("click")
        expect(page.locator("#yes")).not_to_have_attribute("chosen", "")
        expect(page.locator("#no")).not_to_have_attribute("chosen", "")
        assert posts == []
        page.unroute("**/api/state*")
        wait_until_ready(page)
        first.focus()
        page.keyboard.press("1")
    else:
        for route in held:
            route.continue_()
        wait_until_ready(page)
    expect(page.locator("#yes")).to_have_attribute("chosen", "")
    round_trip(page)
    assert len(posts) == 1, "the held or fresh digit should send exactly once"
    first.focus()
    page.keyboard.press("Space")
    round_trip(page)
    second.click()
    round_trip(page)
    assert [post["detail"] for post in posts] == [
        {"value": ["yes"]},
        {"value": []},
        {"value": ["no"]},
    ]


def test_offline_reaction_waits_for_its_saved_state(browser, serve):
    """An unknown saved state cannot invent an add; recovery toggles the actual saved event."""
    source = leaf_page(
        "Saved reaction", '<h1>Saved reaction</h1><button id="target">A target</button>'
    )
    saved = {
        "id": "saved-reaction",
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "keep",
        "anchor": {"section": "target"},
    }
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    posts = []
    page.on(
        "request",
        lambda request: (
            posts.append(request.post_data_json)
            if request.url.endswith("/api/event")
            else None
        ),
    )
    page.route("**/api/state*", refuse)
    page.goto(serve(source, events=[saved]), wait_until="load")
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile("Lost the connection")
    )
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    assert posts == []
    select_words(page, "#target")
    page.keyboard.press("c")
    page.keyboard.press("Tab")
    chip = page.locator('.lf-response-options .lf-react[data-token="keep"]')
    expect(chip).to_have_attribute("aria-disabled", "true")
    chip.dispatch_event("click")
    chip.focus()
    page.keyboard.press("Space")
    assert posts == []
    page.keyboard.press("Escape")
    page.unroute("**/api/state*")
    wait_until_ready(page)
    page.locator("#target").click()
    page.keyboard.press("e")
    page.keyboard.press("1")
    round_trip(page)
    assert [(post["kind"], post.get("undoes")) for post in posts] == [
        ("undo", "saved-reaction")
    ]


def test_thread_timestamps_age_without_new_state(browser, serve):
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    [comment] = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    ]
    open_panel_thread(page, comment["id"])
    timestamp = page.locator(".lf-msg-head time").first
    expect(timestamp).to_have_text("just now")
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    ticked(page)
    expect(timestamp).to_have_text("3h ago")


def test_an_idle_page_keeps_its_dom_and_data_subscriptions_at_rest(browser, serve):
    """An unchanged clock must not render state or redraw an unchanged source.

    Observe mutations over two actual timer ticks instead of imposing a machine-speed
    budget. Clock aging has its own rendered-word test in the projection suite.
    """
    page = open_page(browser, data_projection_page(serve))
    ticked(page)
    page.evaluate(
        """async () => {
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          const feed = document.querySelector('lf-feed');
          const show = feed.show;
          window.idleDeliveries = 0;
          feed.show = function (snapshot) {
            window.idleDeliveries++;
            return show.call(this, snapshot);
          };
          window.idleMutations = 0;
          window.idleObserver = new MutationObserver(records => window.idleMutations += records.length);
          window.idleObserver.observe(document.documentElement,
            {subtree: true, childList: true, attributes: true, characterData: true});
        }"""
    )
    ticked(page)
    ticked(page)
    assert page.evaluate(
        """() => {
          window.idleObserver.disconnect();
          return {mutations: window.idleMutations, deliveries: window.idleDeliveries};
        }"""
    ) == {"mutations": 0, "deliveries": 0}


def test_failed_clock_paints_do_not_starve_other_widgets_or_restart_polling(
    browser, serve
):
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """async () => {
          const {LeafElement, noChange, clockValue} = await window.__lfWidgetApi();
          window.clockVersion = 0;
          const probes = [];
          for (const stage of ['read', 'paint', 'async']) {
            const tag = `lf-clock-${stage}`;
            customElements.define(tag, class extends LeafElement {
              render() {
                const version = clockValue(() => {
                  if (stage === 'read' && window.clockVersion)
                    throw new Error('read broke');
                  return window.clockVersion;
                });
                this.failing = version && stage === 'async';
                if (!version || this.failing) return noChange;
                throw new Error('paint broke');
              }
              async getUpdateComplete() {
                const result = await super.getUpdateComplete();
                if (this.failing) throw new Error('async broke');
                return result;
              }
            });
            const probe = document.createElement(tag);
            document.body.append(probe);
            probes.push(probe);
          }
          customElements.define('lf-clock-healthy', class extends LeafElement {
            render() {
              window.healthyClock = clockValue(() => window.clockVersion);
              return noChange;
            }
          });
          const healthy = document.createElement('lf-clock-healthy');
          document.body.append(healthy);
          await Promise.all([...probes, healthy].map(probe => probe.updateComplete));
          window.clockVersion = 1;
        }"""
    )
    ticked(page)
    assert page.evaluate("window.healthyClock") == 1
    told(page)  # Error reports legitimately change the log and cause one state read.
    ticked(page)
    asked = _traffic(page).asked
    page.evaluate("window.clockVersion = 2")
    ticked(page)
    ticked(page)
    assert page.evaluate("window.healthyClock") == 2
    assert _traffic(page).asked == asked
    consume_browser_errors(page, "read broke", "paint broke", "async broke")
    errors = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "error"
    ]
    # Each failure is reported, through whichever route met it: the clock's tick, the
    # element's render boundary, or the page's error handler.
    assert {error.splitlines()[0].rsplit(": ", 1)[-1] for error in errors} == {
        "read broke",
        "paint broke",
        "async broke",
    }
    assert all("\n" in error for error in errors), errors


def test_user_view_context_waits_for_a_samples_viewport_allocation(browser, serve):
    """A connected sample reports real allocated views, never a zero-sized one."""
    source = leaf_page(
        "Sample view",
        """<h1>Sample view</h1>
<lf-sample id="practice" label="Practice">
  <template id="practice-source" data-sample>
    <h2>Contained page</h2><p>Read this in its allocated viewport.</p>
  </template>
</lf-sample>""",
    )
    page = open_page(browser, serve(source))
    element = page.locator("#practice iframe")
    frame = element.element_handle().content_frame()
    wait_until_ready(frame)
    rendered(frame)
    view_url = urljoin(frame.url, "api/user-view")
    reports = []
    page.on(
        "request",
        lambda request: (
            reports.append(request.post_data_json) if request.url == view_url else None
        ),
    )

    def accepted(response):
        return response.url == view_url and response.status == 204

    with page.expect_response(accepted) as first:
        element.evaluate(
            """frame => {
              frame.style.setProperty('width', '650px', 'important');
              frame.style.setProperty('height', '400px', 'important');
            }"""
        )
    initial = first.value.request.post_data_json
    assert initial["viewport"]["width"] > 0
    assert initial["viewport"]["height"] > 0
    assert initial["visual_viewport"]["width"] > 0
    assert initial["visual_viewport"]["height"] > 0
    saved_style = element.evaluate("frame => frame.style.cssText")
    before = len(reports)
    element.evaluate(
        """frame => {
          for (const property of ['width', 'height', 'min-width', 'min-height', 'border-width'])
            frame.style.setProperty(property, '0px', 'important');
        }"""
    )
    # Zero width is the state that stays: the sample sizes its frame to its content, so
    # one frame later a zero-wide document stands as tall as its words wrapped one per
    # line. Either axis at zero is unallocated (user-view.js).
    frame.wait_for_function(
        """() => document.documentElement.clientWidth === 0 &&
          visualViewport.width === 0"""
    )
    # The sample has an opaque origin, so its window.frameElement is null; the
    # parent can still verify that the iframe itself remains connected.
    assert element.evaluate("frame => frame.isConnected")
    # Cover the observer's 10-second heartbeat and 300ms resize quiet interval.
    page.wait_for_timeout(11_000)
    assert reports[before:] == [], "the unallocated sample sent a user view"

    with page.expect_response(accepted) as restored:
        element.evaluate(
            "(frame, style) => { frame.style.cssText = style; }", saved_style
        )
    recovered = restored.value.request.post_data_json
    assert recovered["session"] == initial["session"]
    assert recovered["sequence"] > initial["sequence"]
    assert recovered["viewport"]["width"] > 0
    assert recovered["viewport"]["height"] > 0
    assert recovered["visual_viewport"]["width"] > 0
    assert recovered["visual_viewport"]["height"] > 0
    assert element.evaluate("frame => frame.isConnected")


def test_user_view_context_follows_real_tabs_without_changing_the_page(browser, serve):
    """Agent context names each actual document and its checks, even when a tab
    keeps an earlier revision. Observations never become decisions or freshness
    changes, and hidden reports release their own view without hiding another."""
    source = leaf_page(
        "View observation",
        '<h1 id="view-heading">Service capacity</h1>'
        '<svg id="capacity-drawing" class="drawing" viewBox="0 0 1200 80">'
        '<text x="20" y="40" font-size="12">Ten thousand requests</text></svg>',
    )
    url = serve(source)
    directory = serve.page_dir
    first = open_page(browser, url)

    def views():
        return user_views_model.read_user_views(
            directory, files_model.latest_revision(directory)
        )["sessions"]

    seen = wait_for(
        views,
        lambda records: len(records) == 1 and records[0]["checks"] is not None,
        failure="the live document never reported its view and checks",
    )
    identity = seen[0]["session"]
    assert seen[0]["visible"] and seen[0]["freshness"] == "fresh"
    assert seen[0]["checks"]["matches_view"]
    assert seen[0]["checks"]["reading"]["checks"]["shrunk_labels"]["drawings"]
    file_reading = page_reading(directory)
    source_reading = source_readings(directory)
    asked = _traffic(first).asked

    first.set_viewport_size({"width": 600, "height": 720})
    first.emulate_media(color_scheme="dark", reduced_motion="reduce")
    changed = wait_for(
        views,
        lambda records: (
            records[0]["viewport"]["width"] == 600
            and records[0]["color_scheme"] == "dark"
            and records[0]["checks"]["matches_view"]
        ),
        failure="resizing and changing scheme did not reach the agent view",
    )[0]
    assert changed["session"] == identity
    assert changed["reduced_motion"]
    assert changed["checks"]["viewport"] == {"width": 600, "height": 720}
    assert page_reading(directory) == file_reading
    assert source_readings(directory) == source_reading
    assert _traffic(first).asked == asked

    second = open_page(browser, live_url(url))
    seen = wait_for(
        views,
        lambda records: len(records) == 2 and all(r["checks"] for r in records),
        failure="the second document replaced the first view",
    )
    assert len({r["session"] for r in seen}) == 2
    assert {r["viewport"]["width"] for r in seen} == {
        600,
        second.viewport_size["width"],
    }
    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(directory)])
    assert state.exit_code == 0, state.output
    assert len(json.loads(state.output)["user_views"]["sessions"]) == 2
    assert "user_views" not in second.evaluate(
        "async () => await (await fetch(new URL('api/state', document.querySelector('link[rel=canonical]').href))).json()"
    )

    # Headless Chrome cannot naturally hide one tab, so deliver the platform
    # lifecycle input used by the existing news visibility regression above.
    first.evaluate(
        """() => {
          Object.defineProperty(document, 'visibilityState', {
            configurable: true, value: 'hidden',
          });
          document.dispatchEvent(new Event('visibilitychange'));
        }"""
    )
    hidden = wait_for(
        views,
        lambda records: any(
            r["session"] == identity and not r["visible"] for r in records
        ),
        failure="hiding one document did not release its view",
    )
    assert sum(r["visible"] for r in hidden) == 1

    (directory / "index.html").write_text(
        source.replace("Service capacity", "Updated capacity")
    )
    told(second)
    seen = wait_for(
        views,
        lambda records: any(
            r["revision"] == 2 and r["checks"] and r["checks"]["matches_view"]
            for r in records
        ),
        failure="the new revision never reached its visible document's reading",
    )
    old = next(r for r in seen if r["session"] == identity)
    current = next(r for r in seen if r["session"] != identity)
    assert old["revision"] == 1 and not old["matches_active_revision"]
    assert current["revision"] == 2 and current["matches_active_revision"]


def test_bad_shadow_words_after_upgrade_keep_the_page_usable(browser, serve):
    entry = {
        "description": "Late shadow words.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-shadow": True,
        "x-example": '<lf-probe id="probe"></lf-probe>',
    }
    widget = """import {once, shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-probe',class extends HTMLElement {connectedCallback(){if(!once(this))return;const p=document.createElement('p');p.textContent='Good words';shadowStage(this,[p]);}});"""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/api/state*", lambda r: held.append(r))
    page.goto(
        serve(
            leaf_page(
                "Late shadow", '<h1>Late shadow</h1><lf-probe id="probe"></lf-probe>'
            ),
            layer_registry={"lf-probe": entry},
            layer_widgets={"lf-probe.js": widget},
        ),
        wait_until="load",
    )
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    page.evaluate(
        """async()=>{const host=document.querySelector('lf-probe');host.shadowRoot.append(document.createTextNode('Broken author words'));const {textNodesUnder}=await window.__lfCheckApi();[...textNodesUnder(document.body)];}"""
    )
    assert page.evaluate("document.documentElement.hasAttribute('data-lf-interactive')")
    expect(
        page.get_by_role("status").filter(has_text="Leaf couldn't start")
    ).to_have_count(0)
    consume_browser_errors(page, "staged bare text")
    page.unroute("**/api/state*")
    for r in held:
        r.continue_()
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    select_words(page, "h1")
    page.keyboard.press("c")
    write(page_comment(page), "Still usable.")
    expect(page_comment(page)).to_have_js_property("value", "Still usable.")


@pytest.mark.parametrize("answer", ["ready", "offline"])
@pytest.mark.parametrize("focus", ["sample", "chrome"])
def test_first_history_answer_keeps_an_open_quote_draft(browser, serve, answer, focus):
    """Presentation applies saved facts without re-deciding the user's open composer."""
    source = leaf_page(
        "Uninterrupted draft",
        '<h1>Uninterrupted draft</h1><p id="passage">The prototype needs a mobile check.</p>'
        '<lf-sample id="practice" label="Practice" window>'
        '<template id="practice-source" data-sample>'
        '<h1>Practice</h1><button id="inspect">Inspect</button>'
        "</template></lf-sample>",
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    page.goto(serve(source), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-upgraded", "1")
    select_words(page, "#passage")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "Keep these words.")
    field.evaluate("field => field.setSelectionRange(7, 7)")
    if focus == "sample":
        child = page.locator("#practice iframe").element_handle().content_frame()
        child.locator("#inspect").click()
    else:
        page.locator(".lf-fp-leaf").focus()
        page.evaluate("getSelection().removeAllRanges()")
    expect(field).to_be_visible()
    page.unroute("**/api/state*")
    for route in held:
        if answer == "ready":
            route.continue_()
        else:
            route.abort("internetdisconnected")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(field).to_be_visible()
    expect(field).to_have_js_property("value", "Keep these words.")
    assert field.evaluate("field => [field.selectionStart, field.selectionEnd]") == [
        7,
        7,
    ]
    expect(page.get_by_role("status").filter(has_text="Draft kept")).to_have_count(0)
    if answer == "offline":
        consume_browser_errors(page, "net::ERR_INTERNET_DISCONNECTED")
