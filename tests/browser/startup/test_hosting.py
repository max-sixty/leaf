"""Where a page lives beyond its own tab: embedded at its own origin, arriving as a live
sample in a frame, and published on the Leaf website."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import SHORT_SUGGESTION, live_url
from render_harness import (
    consume_browser_errors,
    holding,
    http_error_console,
    is_problem,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
    refuse,
    watched,
)

from leaf.log import event_log as events_model
from leaf.source.render_checks import evaluate_probe, rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_live_page_embeds_at_its_own_origin_and_cannot_run_its_data(browser, serve):
    """A same-origin frame is an ordinary operable page; data never runs as code."""
    source = leaf_page(
        "Boundaries",
        """<h1 id="h">Boundaries</h1>
<lf-group id="decision" label="Proceed?"><h2 id="decision-h">Proceed?</h2><lf-options id="pick">
<lf-option id="yes">Proceed</lf-option><lf-option id="no">Wait</lf-option>
</lf-options></lf-group>""",
        head="""<script type="module">
window.authoredModuleRan = true;
</script>""",
    )
    page = open_page(browser, live_url(serve(source)))
    page.wait_for_function("() => window.authoredModuleRan === true")
    assert (
        page.evaluate(
            """async () => {
                  try {
                    await import('/api/state');
                    return 'executed';
                  } catch {
                    return 'blocked';
                  }
                }"""
        )
        == "blocked"
    )
    errors = consume_browser_errors(page, 'MIME type of "application/json"')
    assert any(
        is_problem(error, 'MIME type of "application/json"') for error in errors
    ), errors
    framed = page.locator("body").evaluate(
        """async (body, url) => {
              const frame = document.createElement('iframe');
              frame.id = 'framed-leaf';
              frame.src = url;
              const loaded = new Promise((resolve, reject) => {
                frame.addEventListener('load', resolve, {once: true});
                setTimeout(() => reject(new Error('framed Leaf did not settle')), 5000);
              });
              body.append(frame);
              await loaded;
              return frame.contentDocument?.querySelector('#h')?.textContent ?? null;
            }""",
        page.url,
    )
    assert framed == "Boundaries"
    frame = page.frame_locator("#framed-leaf")
    expect(frame.locator("body")).to_have_attribute("data-lf-presented", "1")
    frame.locator("#yes").click()
    page.wait_for_function(
        "() => document.querySelector('#yes')?.hasAttribute('selected')"
    )
    assert any(
        event.get("kind") == "action"
        and event.get("widget") == "pick"
        and event.get("detail") == {"value": ["yes"]}
        for event in events_model.read_events(serve.page_dir)
    )


@pytest.mark.parametrize("outcome", ["presented", "abandoned", "offline", "slow"])
def test_public_startup_reports_upgrade_separately_from_held_state(
    browser, serve, outcome, request
):
    """Public telemetry names the independent browser and state milestones.

    A local delivered document gets the public release marker at the HTTP boundary.
    The real widget runtime upgrades while its first state read is held. A full
    Resource Timing buffer must not lose that response, an unrelated page's state
    must not stand in for it, and later polling or departure must not send again.
    A refused request has a Resource Timing entry but no state response to report.
    """
    url = serve(SHORT_SUGGESTION)
    page = browser.new_page()
    request.addfinalizer(page.close)
    reports = []
    held = []

    def public_document(route):
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace(
                "data-lf-server=", f'data-lf-release="{"a" * 64}" data-lf-server=', 1
            ),
        )

    def report(route):
        reports.append(route.request.post_data_json)
        route.fulfill(status=204)

    page.route("**/versions/v1.html?*", public_document)
    page.route("**/api/performance", report)
    page.route("**/api/state", lambda route: held.append(route))
    page.route("**/other/api/state", lambda route: route.fulfill(json={}))
    page.add_init_script(
        """performance.setResourceTimingBufferSize(1);
        window.firstStateResponses = [];
        new PerformanceObserver(list => {
          for (const entry of list.getEntries())
            if (new URL(entry.name).pathname === '/api/state')
              window.firstStateResponses.push(entry.responseEnd);
        }).observe({type: 'resource', buffered: true});"""
    )
    page.goto(url, wait_until="load")
    page.wait_for_function("document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state read"
    expect(page.locator("body")).not_to_have_attribute("data-lf-presented", "1")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Loading comments and choices…")
    )
    assert reports == []
    assert page.evaluate("firstStateResponses") == []
    if outcome == "slow":
        page.clock.install()
        page.clock.fast_forward(16_000)
        assert reports == [], "a usable page waiting on state is not a startup timeout"
    upgraded_before_release = page.evaluate("Math.round(performance.now())")
    page.evaluate("async () => await (await fetch('/other/api/state')).json()")

    if outcome == "abandoned":
        with page.expect_response("**/api/performance"):
            page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
        assert len(reports) == 1
        assert reports[0]["firstStateResponseMs"] is None
        assert reports[0]["presentedMs"] is None

    released_at = page.evaluate("Math.round(performance.now())")
    if outcome != "abandoned":
        with page.expect_response("**/api/performance"):
            first = held.pop(0)
            if outcome == "offline":
                refuse(first)
                expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
            else:
                first.continue_()
                wait_until_ready(page)
    else:
        held.pop(0).continue_()
        wait_until_ready(page)
    page.wait_for_function("firstStateResponses.length === 1")
    with page.expect_request("**/api/state"):
        page.evaluate("void fetch('/api/state').then(response => response.json())")
    holding(page, held, 1, "the follow-up state read")
    held.pop(0).continue_()
    page.wait_for_function("firstStateResponses.length === 2")
    page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide'))")
    assert len(reports) == 1
    reading = reports[0]
    assert reading["outcome"] == (
        "presented" if outcome in {"offline", "slow"} else outcome
    )
    assert 0 <= reading["upgradedMs"] <= upgraded_before_release
    if outcome in {"presented", "slow"}:
        first_response = page.evaluate("Math.round(firstStateResponses[0])")
        assert reading["firstStateResponseMs"] == first_response
        assert first_response <= reading["presentedMs"]
        if outcome != "slow":
            # The slow case advances the JS timer clock, not Resource Timing.
            assert released_at <= first_response
        assert page.evaluate(
            """performance.getEntriesByType('resource').every(entry =>
                new URL(entry.name).pathname !== '/api/state')"""
        ), "the response remained in the global timeline; eviction was not tested"
    elif outcome == "offline":
        assert reading["firstStateResponseMs"] is None
        assert reading["presentedMs"] >= reading["upgradedMs"]


def test_a_website_example_shows_its_public_session_reference(browser, serve):
    url = live_url(
        serve(
            leaf_page("Website reference", "<h1>Website reference</h1>"),
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        )
    )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    watched(page)

    def identify(response_route):
        response = response_route.fetch()
        response_route.fulfill(
            response=response,
            headers={
                **response.headers,
                "Leaf-Session-Reference": "239383829012",
            },
        )

    page.route("**/api/state*", identify)
    page.goto(url, wait_until="load")
    wait_until_ready(page)
    # The reference is no part of the status the panel's field says; About this page
    # shows it and copies it in one press.
    expect(panel_field(page)).not_to_have_attribute(
        "placeholder", re.compile("239383829012")
    )
    about = about_this_page(page)
    expect(about.get_by_label("Session reference", exact=True)).to_have_text(
        "239383829012"
    )
    about.get_by_role("button", name="Copy Session reference", exact=True).click()
    page.wait_for_function(
        "navigator.clipboard.readText().then(text => text === '239383829012')"
    )


def about_this_page(page):
    """Open About this page from the leaf's menu and return the dialog; it alone shows
    the session reference (panel/page-about.js, the `about` group)."""
    panel_control(page, "inspection").click()
    about = page.get_by_role("dialog", name="About this page", exact=True)
    expect(about).to_be_visible()
    return about


@pytest.mark.parametrize(
    ("response", "status_words", "problem"),
    [
        (
            {"status": 503, "body": ""},
            "Lost the connection — reconnecting",
            http_error_console(503),
        ),
        (
            {"status": 200, "body": "{"},
            "Couldn't show the latest",
            "read failed",
        ),
    ],
)
def test_a_website_session_reference_survives_a_failed_first_read(
    browser, serve, response, status_words, problem
):
    url = live_url(serve(leaf_page("Failed website read", "<h1>Still a page</h1>")))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route(
        "**/api/state*",
        lambda route: route.fulfill(
            **response,
            headers={"Leaf-Session-Reference": "239383829012"},
        ),
    )
    try:
        page.goto(url, wait_until="load")
        expect(panel_field(page)).to_have_attribute(
            "placeholder", re.compile(status_words)
        )
        expect(
            about_this_page(page).get_by_label("Session reference", exact=True)
        ).to_have_text("239383829012")
    finally:
        page.close()
    # The route stands for the whole test and the page asks again every two seconds,
    # so what it said is a complete list only once the page is gone.
    consume_browser_errors(page, problem)


SAMPLE_DOCUMENT = re.compile(r"/api/samples/([^/]+)/$")


# A page that does not start Leaf, answered for a sample document to make it fail.
NOT_LEAF = {"status": 200, "content_type": "text/html", "body": "<p>Unavailable</p>"}


def held_sample_page(
    browser, serve, body, *, head="", hold_first=True, documents=1, **options
):
    """A page whose live sample documents wait until `release()`: every sample's when
    `hold_first`, otherwise all but the first sample a page allocates, so an outer
    sample presents while the one inside it waits. `documents` is how many are held
    before this returns. `release(failing)` answers the documents of the samples whose
    element ids `failing` names with a page that does not start Leaf, and lets the
    rest through. `options` go to `new_page`. Returns the page and `release`."""
    page = browser.new_page(viewport={"width": 1200, "height": 900}, **options)
    watched(page)
    held = []
    passing = []
    # Each sample's allocation: its template, posted, and its document, answered.
    allocations = []
    page.on(
        "response",
        lambda response: (
            response.request.method == "POST"
            and response.url.endswith("/api/samples")
            and allocations.append(response)
        ),
    )

    def route(request_route):
        match = SAMPLE_DOCUMENT.search(request_route.request.url)
        assert match is not None
        sample = match.group(1)
        if not hold_first and (not passing or sample in passing):
            passing.append(sample)
            request_route.continue_()
        else:
            held.append(request_route)

    page.route(SAMPLE_DOCUMENT, route)
    page.goto(serve(leaf_page("Sample arrival", body, head=head)), wait_until="commit")
    holding(page, held, documents, "the samples' documents")

    def release(failing=()):
        templates = {f"{sample}-source" for sample in failing}
        broken = {
            next(SAMPLE_DOCUMENT.finditer(allocation.json()["url"])).group(1)
            for allocation in allocations
            if allocation.request.post_data_json["template"] in templates
        }
        page.unroute(SAMPLE_DOCUMENT)
        for each in held:
            match_2 = SAMPLE_DOCUMENT.search(each.request.url)
            assert match_2 is not None
            if match_2.group(1) in broken:
                each.fulfill(**NOT_LEAF)
            else:
                each.continue_()

    return page, release


def readiness(frame):
    return frame.evaluate(
        "document.querySelector('script[data-lf-entry]').lfReadiness(null)"
    )


def live_sample(sample_id, attributes="", content="<p>Practice</p>"):
    return (
        f'<lf-sample id="{sample_id}"{attributes}><template id="{sample_id}-source"'
        f" data-sample>{content}</template></lf-sample>"
    )


# A window sample whose child holds a window sample in view, which starts with the
# child but doesn't hold its presentation, so the child presents while the inner
# sample's document can wait, and a link out of Leaf.
NESTED = (
    '<h1>Containing page</h1><lf-sample id="outer" window>'
    '<template id="outer-source" data-sample><h1>Outer</h1>'
    '<a href="about:blank" id="leave">Leave</a>'
    '<lf-sample id="inner" window><template id="inner-source" data-sample>'
    "<p>Inner</p></template></lf-sample></template></lf-sample>"
)


def test_a_sample_the_reader_would_see_arrive_holds_presentation(browser, serve):
    """A block sample whose growth the reader would see presents with the page, so
    the page's first presented frame already holds it at its child's height. A sample
    whose arrival would not be seen does not hold it
    (`test_a_sample_reached_while_loading_holds_growth_the_reader_did_not_cause`)."""
    page, release = held_sample_page(
        browser, serve, "<h1>Containing page</h1>" + live_sample("practice")
    )
    page.evaluate("""() => {
        window.presentedAtSampleReady = document.querySelector('#practice').ready.then(
            () => document.body.hasAttribute('data-lf-presented'));
    }""")
    release()
    wait_until_ready(page)
    assert page.evaluate("presentedAtSampleReady") is False


# A sample document's registry, which its upgrade reads after the document loads.
SAMPLE_REGISTRY = re.compile(r"/api/samples/[^/]+/revisions/[^/]+/registry\.json$")

# A board sample whose recorded moves, which its page applies after upgrading, take two
# of the four cards in its taller column to the other, so the page arrives shorter than
# it upgrades.
MOVED_BOARD = (
    '<script id="moves" type="application/json">['
    + ",".join(
        '{"kind": "action", "author": "user", "widget": "board", "action": "move",'
        f' "detail": {{"unit": "card-{card}", "value": "done", "rank": "{rank}"}}}}'
        for card, rank in ((1, "a"), (2, "b"))
    )
    + "]</script>"
    + live_sample(
        "practice",
        content='<lf-board id="board"><lf-column id="ready" label="Ready">'
        + "".join(
            f'<lf-card id="card-{card}" label="Card {card}">Card {card}</lf-card>'
            for card in range(1, 5)
        )
        + '</lf-column><lf-column id="done" label="Done">'
        '<lf-card id="card-5" label="Card 5">Card 5</lf-card></lf-column></lf-board>',
    ).replace("data-sample>", 'data-sample data-sample-events="moves">')
)


def held_block_sample(browser, serve):
    """A page with `MOVED_BOARD` half a window below the window's foot, within a window
    of it, so it starts off screen, its page loaded and its registry held so that page
    doesn't upgrade. Returns the page, the frame, its page and the held requests."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    watched(page)
    held = []
    page.route(SAMPLE_REGISTRY, lambda request_route: held.append(request_route))
    page.goto(
        serve(
            leaf_page(
                "Sample below",
                '<h1>Containing page</h1><div style="height: 150vh"></div>'
                + MOVED_BOARD
                + "<p id=after>After the sample</p>",
            )
        ),
        wait_until="commit",
    )
    holding(page, held, 1, "the sample's registry")
    frame = page.locator("#practice iframe")
    child = frame.element_handle().content_frame()
    assert child is not None
    child.wait_for_load_state("load")
    rendered(page)
    return page, frame, child, held


def test_a_block_sample_out_of_view_keeps_the_page_arriving_until_it_has_its_height(
    browser, serve
):
    """A block sample that starts just below the window takes its page's height as that
    page arrives, moving what follows it, so the containing page reads as arriving
    until then though the frame is off screen, and a reader that waits for the page
    finds the frame at the height the page arrived at, not the one it upgraded at."""
    page, frame, child, held = held_block_sample(browser, serve)
    assert readiness(page) == "arrived"
    page.unroute(SAMPLE_REGISTRY)
    for each in held:
        each.continue_()
    wait_until_ready(page)
    body = "() => Math.ceil(document.body.getBoundingClientRect().height)"
    assert frame.evaluate("frame => frame.clientHeight") == child.evaluate(body)


def test_a_check_asking_for_near_work_takes_over_a_block_sample_s_wait(browser, serve):
    """A check that asks for all near work brings each frame whose page the containing
    page stopped counting into view itself (`start_near_work`), so once it asks, the
    page stops waiting for an off-screen block sample's height and marks its frame for
    the check."""
    page, frame, _, held = held_block_sample(browser, serve)
    evaluate_probe(page, "startNearWork")
    rendered(page)
    assert readiness(page) is None
    assert frame.evaluate("frame => frame.hasAttribute('data-lf-unseen')")
    page.unroute(SAMPLE_REGISTRY)
    for each in held:
        each.continue_()


def test_a_narrow_window_samples_status_keeps_its_row_as_it_arrives_or_fails(
    browser, serve
):
    """A narrow window sample's status row keeps its size whatever it says, so
    neither the frame nor what follows moves when "Loading sample…" clears or a
    failure too long for the row replaces it, open or shut. The reader opens the
    failure to read it whole by Tab and Enter or by a press. At a mouse the row is a
    line high, so any growth of it shows."""
    page, release = held_sample_page(
        browser,
        serve,
        "<h1>Containing page</h1>"
        + live_sample("broken", " window")
        + live_sample("practice", " window")
        + "<p><button id=after>After the samples</button></p>",
        head="<style>#broken, #practice { width: 180px }</style>",
        documents=2,
    )
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator(".lf-sample-status")).to_have_text(["Loading sample…"] * 2)
    places = """() => ['#broken iframe', '#practice iframe', '#after'].map(selector => {
        const box = document.querySelector(selector).getBoundingClientRect();
        return [box.left, box.top + scrollY, box.width, box.height];
    })"""
    before = page.evaluate(places)
    release(failing={"broken"})
    status = page.locator("#broken .lf-sample-status")
    summary = status.locator("details > summary")
    expect(summary).to_have_text("The sample document did not start Leaf")
    wait_until_ready(page)
    expect(page.locator("#practice .lf-sample-status")).to_have_text("")
    assert page.evaluate(places) == before
    clipped = "summary => summary.scrollWidth > summary.clientWidth"
    assert summary.evaluate(clipped)

    page.locator("#broken").get_by_role("button", name="Full view").focus()
    page.keyboard.press("Tab")
    expect(summary).to_be_focused()
    page.keyboard.press("Enter")
    expect(status.locator("details")).to_have_attribute("open", "")
    assert not summary.evaluate(clipped)
    assert page.evaluate(places) == before

    summary.click()
    expect(status.locator("details")).not_to_have_attribute("open", "")
    summary.click()
    expect(status.locator("details")).to_have_attribute("open", "")
    assert not summary.evaluate(clipped)
    assert page.evaluate(places) == before


# Hold each command the page sends a sample's document over the private port the
# host publishes on the entry script (host/sample.js, `connect`), so the document's own
# arrival lands before any answer: `heldCommands` sends them on.
HOLD_COMMANDS = """entry => {
  window.heldCommands = [];
  const binding = Object.getOwnPropertyDescriptor(
    HTMLScriptElement.prototype, 'lfDocumentPort');
  Object.defineProperty(entry, 'lfDocumentPort', {
    configurable: true,
    get() { return binding.get.call(this); },
    set(port) {
      binding.set.call(this, port);
      const post = port.postMessage;
      port.postMessage = function (message, ...rest) {
        if (message?.method === undefined) return post.call(this, message, ...rest);
        heldCommands.push(() => post.call(this, message, ...rest));
      };
    },
  });
}"""


def test_a_reset_sample_has_drawn_its_new_page_once_the_page_reads_arrived(
    browser, serve
):
    """A sample the reader resets in view draws its new page's arrival, Reset
    available again and its status clear, before the page reads arrived, however
    late the child answers a command the containing page sends it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Sample reset", "<h1>Containing page</h1>" + live_sample("practice")
            )
        ),
    )
    page.locator("script[data-lf-entry]").evaluate(HOLD_COMMANDS)
    allocated = []
    page.on(
        "request",
        lambda request: (
            request.method == "POST"
            and request.url.endswith("/api/samples")
            and allocated.append(request)
        ),
    )
    sample = page.locator("#practice")
    sample.get_by_role("button", name="Reset").click()
    wait_until_ready(page)
    drawn = sample.evaluate("""sample => [
        sample.querySelector('.lf-sample-action').getAttribute('aria-disabled'),
        sample.querySelector('.lf-sample-status').textContent]""")
    page.evaluate("() => heldCommands.forEach(send => send())")
    assert len(allocated) == 1
    assert drawn == [None, ""]
